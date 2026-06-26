from __future__ import annotations

from typing import Any

from velocity_claw.core.failed_run_resume import install_failed_run_resume_instance


def install_failed_run_resume_class(agent_cls: type) -> None:
    if getattr(agent_cls, "_failed_run_resume_v2_installed", False):
        return

    original_init = agent_cls.__init__

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        install_failed_run_resume_instance(self)

    agent_cls.__init__ = __init__
    agent_cls._failed_run_resume_v2_installed = True
