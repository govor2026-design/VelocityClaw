from __future__ import annotations

from typing import Any


def persist_queue_job(queue: Any, job: Any) -> None:
    """Persist a queue job through the queue-owned persistence boundary.

    This compatibility boundary keeps API modules from reaching into the
    queue's protected implementation while the queue storage backend remains
    internal to ``RunQueue``.
    """
    persist = getattr(queue, "_persist_job", None)
    if persist is None or not callable(persist):
        raise TypeError("Queue does not provide a persistence implementation")
    persist(job)
