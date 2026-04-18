from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from velocity_claw.config.settings import load_settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.logs.logger import get_logger


class TaskRequest(BaseModel):
    task: str


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="Velocity Claw API")
    app.state.settings = settings
    app.state.logger = get_logger("velocity_claw.api")
    app.state.agent = VelocityClawAgent(settings=settings)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/task")
    async def task(request: TaskRequest):
        result = await app.state.agent.run_task(request.task)
        return result

    @app.get("/status")
    def status():
        return app.state.agent.get_status()

    @app.post("/reset")
    def reset():
        return app.state.agent.reset_context()

    return app
