import asyncio

from velocity_claw.core.queue import RunQueue
from velocity_claw.core.queue_tracking import install_direct_run_tracking


async def wait_for(predicate, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def test_legacy_direct_run_is_tracked_cancelled_and_capacity_bounded():
    async def scenario():
        queue = RunQueue(max_concurrency=1)
        install_direct_run_tracking(queue)
        first = queue.enqueue("first")
        second = queue.enqueue("second")
        first_started = asyncio.Event()
        first_interrupted = asyncio.Event()
        calls = []

        async def runner(task, context):
            calls.append(task)
            if task == "first":
                first_started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    first_interrupted.set()
                    raise
            return {"status": "completed", "task": task}

        first_task = asyncio.create_task(queue.run_job(first.job_id, runner))
        await first_started.wait()
        assert queue.tracked_task_count() == 1

        second_task = asyncio.create_task(queue.run_job(second.job_id, runner))
        await second_task
        assert second.status == "queued"
        assert second.attempts == 0
        assert queue.tracked_task_count() == 1

        queue.cancel(first.job_id)
        await first_task
        await wait_for(first_interrupted.is_set)
        await wait_for(lambda: second.status == "completed")
        await wait_for(lambda: queue.tracked_task_count() == 0)

        assert first.status == "cancelled"
        assert calls == ["first", "second"]

    asyncio.run(scenario())
