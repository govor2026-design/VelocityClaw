from __future__ import annotations

from typing import Any

from velocity_claw.__version__ import __product_name__, __release_stage__, __version__


def build_version_payload(settings: Any) -> dict[str, Any]:
    return {
        "status": "ok",
        "product": __product_name__,
        "version": __version__,
        "release_stage": __release_stage__,
        "runtime": {
            "env": getattr(settings, "env", None),
            "execution_profile": getattr(settings, "execution_profile", None),
            "safe_mode": getattr(settings, "safe_mode", None),
            "trusted_mode": getattr(settings, "trusted_mode", None),
        },
    }
