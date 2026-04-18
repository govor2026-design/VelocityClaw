from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from velocity_claw.config.settings import load_settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.logs.logger import get_logger


class TaskRequest(BaseModel):
    task: str
    context: Optional[Dict] = None


class StepResponse(BaseModel):
    id: int
    title: str
    status: str
    result: Optional[Dict] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskResponse(BaseModel):
    run_id: str
    task: str
    status: str
    summary: str
    steps: List[StepResponse]
    signature: str


class StatusResponse(BaseModel):
    status: str
    env: str
    safe_mode: bool
    trusted_mode: bool
    memory_enabled: bool
    signature: str


class ResetResponse(BaseModel):
    status: str
    signature: str


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="Velocity Claw API")
    app.state.settings = settings
    app.state.logger = get_logger("velocity_claw.api")
    app.state.agent = VelocityClawAgent(settings=settings)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/task", response_model=TaskResponse)
    async def task(request: TaskRequest):
        try:
            result = await app.state.agent.run_task(request.task, request.context)
            return TaskResponse(**result)
        except Exception as e:
            app.state.logger.error("Task execution failed: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/status", response_model=StatusResponse)
    def status():
        return StatusResponse(**app.state.agent.get_status())

    @app.post("/reset", response_model=ResetResponse)
    def reset():
        return ResetResponse(**app.state.agent.reset_context())

    return app
