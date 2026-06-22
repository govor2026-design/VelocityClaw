"""Velocity Claw memory package."""

from velocity_claw.memory.repo_context import install_repo_aware_memory_v2
from velocity_claw.memory.store import MemoryStore

install_repo_aware_memory_v2(MemoryStore)

__all__ = ["MemoryStore"]
