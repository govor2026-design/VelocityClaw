from types import SimpleNamespace

import pytest

from velocity_claw.core.queue_persistence import persist_queue_job


def test_persist_queue_job_delegates_to_queue_storage() -> None:
    calls = []
    job = SimpleNamespace(job_id="job-1")
    queue = SimpleNamespace(_persist_job=lambda persisted: calls.append(persisted))

    persist_queue_job(queue, job)

    assert calls == [job]


def test_persist_queue_job_rejects_missing_storage_boundary() -> None:
    with pytest.raises(TypeError, match="persistence implementation"):
        persist_queue_job(SimpleNamespace(), SimpleNamespace(job_id="job-1"))
