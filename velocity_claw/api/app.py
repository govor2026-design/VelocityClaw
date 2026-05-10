from __future__ import annotations

from fastapi import FastAPI

from velocity_claw.api.errors import install_api_error_handlers
from velocity_claw.api.server import create_app as create_base_app


def create_app() -> FastAPI:
    """Create the production API app with shared hardening installed."""
    app = create_base_app()
    install_api_error_handlers(app)
    app.state.api_error_handlers_installed = True
    return app
