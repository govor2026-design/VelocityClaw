"""Public project-memory v2 interface.

The implementation lives in ``context_v2_runtime`` so this module remains a stable
import path for the agent, tests, and third-party integrations.
"""

from velocity_claw.memory.context_v2_runtime import (
    ACTIVE_RUN_STATUSES,
    ProjectContextV2,
    REUSABLE_NOTE_TYPES,
    STOP_WORDS,
    TRACE_NOTE_TYPES,
    normalize_tokens,
    task_similarity,
)
from velocity_claw.memory.run_profile_v2 import install_run_profile_v2
from velocity_claw.memory.store import MemoryStore

install_run_profile_v2(MemoryStore)

__all__ = [
    "ACTIVE_RUN_STATUSES",
    "ProjectContextV2",
    "REUSABLE_NOTE_TYPES",
    "STOP_WORDS",
    "TRACE_NOTE_TYPES",
    "normalize_tokens",
    "task_similarity",
]
