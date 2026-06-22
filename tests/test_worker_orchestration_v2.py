import asyncio

from velocity_claw.config.settings import Settings
from velocity_claw.core.queue import RunQueue


async def wait_for(predicate, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def test_worker_pool_bounds_concurrency_and_refills_queued_jobs():
    async def scenario():
        queue = RunQueue(max_concurrency=2)
        jobs = [queue.enqueue(f"task-{index}") for index in range(5)]
        current = 0
        maximum = 0
        observed_slots = set()

        async def runner(task, context):
            nonlocal current, maximum
            current += 1
            maximum = max(maximum, current)
            job = next(item for item in jobs if item.task == task)
            observed_slots.add(job.worker_slot)
            await asyncio.sleep(0.03)
            current -= 1
            return {"status": "completed", "task": task}

        initially_scheduled = queue.schedule_pending(runner)
        assert len(initially_scheduled) == 2
        assert queue.tracked_task_count() == 2

        await wait_for(lambda: all(job.status == "completed" for job in jobs))
        await wait_for(lambda: queue.tracked_task_count() == 0)

        assert maximum == 2
        assert observed_slots == {"slot-1", "slot-2"}
        assert queue.runtime_summary()["scheduling_capacity"] == 2

    asyncio.run(scenario())


def test_cancelling_queued_job_prevents_runner_execution():
    async def scenario():
        queue = RunQueue(max_concurrency=1)
        first = queue.enqueue("first")
        second = queue.enqueue("second")
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        calls = []

        async def runner(task, context):
            calls.append(task)
            if task == "first":
                first_started.set()
                await release_first.wait()
            return {"status": "completed"}

        assert queue.schedule_pending(runner) == [first.job_id]
        await first_started.wait()
        cancelled = queue.cancel(second.job_id)
        assert cancelled.status == "cancelled"

        release_first.set()
        await wait_for(lambda: first.status == "completed")
        await wait_for(lambda: queue.tracked_task_count() == 0)

        assert calls == ["first"]
        assert second.status == "cancelled"
        assert second.attempts == 0

    asyncio.run(scenario())


def test_cancelling_running_job_interrupts_runner_task():
    async def scenario():
        queue = RunQueue(max_concurrency=1)
        job = queue.enqueue("long-running")
        started = asyncio.Event()
        interrupted = asyncio.Event()

        async def runner(task, context):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                interrupted.set()
                raise

        assert queue.schedule(job.job_id, runner) is True
        await started.wait()
        cancelled = queue.cancel(job.job_id)
        assert cancelled.status == "cancelled"

        await wait_for(interrupted.is_set)
        await wait_for(lambda: queue.tracked_task_count() == 0)

        assert job.status == "cancelled"
        assert job.terminal_reason == "cancelled_by_operator"
        assert job.worker_slot is None
        assert any(event["reason"] == "runner_task_cancelled" for event in job.history)

    asyncio.run(scenario())


def test_drain_pauses_refill_and_resume_schedules_remaining_jobs():
    async def scenario():
        queue = RunQueue(max_concurrency=1)
        first = queue.enqueue("first")
        second = queue.enqueue("second")
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        calls = []

        async def runner(task, context):
            calls.append(task)
            if task == "first":
                first_started.set()
                await release_first.wait()
            return {"status": "completed"}

        queue.schedule_pending(runner)
        await first_started.wait()

        drained = await queue.drain(timeout_seconds=0.01)
        assert drained["status"] == "timeout"
        assert drained["timed_out"] is True
        assert queue.runtime_summary()["accepting_work"] is False

        release_first.set()
        await wait_for(lambda: first.status == "completed")
        await wait_for(lambda: queue.tracked_task_count() == 0)
        assert second.status == "queued"

        resumed = queue.resume(runner)
        assert resumed == [second.job_id]
        await wait_for(lambda: second.status == "completed")
        assert calls == ["first", "second"]

    asyncio.run(scenario())


def test_shutdown_cancels_workers_and_refuses_new_schedules():
    async def scenario():
        queue = RunQueue(max_concurrency=1)
        job = queue.enqueue("shutdown-me")
        started = asyncio.Event()

        async def runner(task, context):
            started.set()
            await asyncio.Event().wait()

        assert queue.schedule(job.job_id, runner) is True
        await started.wait()

        result = await queue.shutdown(timeout_seconds=1, cancel_running=True)
        assert result["status"] == "stopped"
        assert result["timed_out"] is False
        assert job.status == "cancelled"
        assert queue.runtime_summary()["accepting_work"] is False

        new_job = queue.enqueue("after-shutdown")
        assert queue.schedule(new_job.job_id, runner) is False

    asyncio.run(scenario())


def test_queue_settings_use_prefixed_environment(monkeypatch):
    monkeypatch.setenv("VELOCITY_CLAW_ENV", "test")
    monkeypatch.setenv("VELOCITY_CLAW_QUEUE_MAX_CONCURRENCY", "4")
    monkeypatch.setenv("VELOCITY_CLAW_QUEUE_MAX_ATTEMPTS", "9")
    monkeypatch.setenv("VELOCITY_CLAW_QUEUE_RECOVER_ON_STARTUP", "false")
    monkeypatch.setenv("VELOCITY_CLAW_QUEUE_SHUTDOWN_TIMEOUT_SECONDS", "25")

    settings = Settings()

    assert settings.queue_max_concurrency == 4
    assert settings.queue_max_attempts == 9
    assert settings.queue_recover_on_startup is False
    assert settings.queue_shutdown_timeout_seconds == 25
