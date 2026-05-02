import argparse
import asyncio
import json
from pathlib import Path

from velocity_claw.config.settings import load_settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.core.release import ReleaseReadinessEvaluator
from velocity_claw.core.runtime import exit_with_boundary
from velocity_claw.api.server import create_app
from scripts.generate_release_notes import write_release_notes
from scripts.validate_package import validate_package


def build_agent():
    settings = load_settings()
    return VelocityClawAgent(settings=settings)


def _append_signature(text: str) -> str:
    return f"{text.rstrip()}\n\nvelocity claw"


def _print_payload(payload, as_json: bool = False):
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if isinstance(payload, str):
        print(_append_signature(payload))
        return
    print(_append_signature(json.dumps(payload, ensure_ascii=False, indent=2)))


async def run_task_cli(task: str, as_json: bool = False):
    agent = build_agent()
    result = await agent.run_task(task)
    if as_json:
        _print_payload(result, as_json=True)
        return
    if isinstance(result, dict):
        output = [f"Задача: {result.get('task')}", f"Статус: {result.get('status')}" ]
        summary = result.get('summary', '')
        if summary:
            output.append(f"Итог: {summary}")
        plan = result.get('plan', '')
        if plan:
            output.append(f"План: {plan}")
        print(_append_signature("\n".join(output)))
    else:
        print(_append_signature(str(result)))


async def retry_run_cli(run_id: str, as_json: bool = False):
    agent = build_agent()
    result = await agent.retry_run(run_id)
    _print_payload(result, as_json=as_json)


def release_readiness_cli(as_json: bool = False):
    settings = load_settings()
    result = ReleaseReadinessEvaluator(settings).evaluate()
    _print_payload(result, as_json=as_json)


def validate_package_cli(as_json: bool = False):
    result = validate_package(Path.cwd())
    _print_payload(result, as_json=as_json)


def generate_release_notes_cli(as_json: bool = False):
    output_path = write_release_notes(Path.cwd())
    result = {"status": "ok", "path": str(output_path)}
    _print_payload(result, as_json=as_json)


def release_checklist_cli(as_json: bool = False):
    settings = load_settings()
    readiness = ReleaseReadinessEvaluator(settings).evaluate()
    package = validate_package(Path.cwd())
    notes_path = write_release_notes(Path.cwd())
    result = {
        "status": "ok",
        "version": package["version"],
        "package_validation": package,
        "release_readiness": readiness,
        "release_notes_path": str(notes_path),
        "ready": readiness.get("readiness") == "ready",
    }
    _print_payload(result, as_json=as_json)


def memory_cleanup_cli(days: int | None = None, keep_min_runs: int | None = None, vacuum: bool | None = None, as_json: bool = False):
    agent = build_agent()
    result = agent.memory.cleanup_retention(days=days, keep_min_runs=keep_min_runs, vacuum=vacuum)
    _print_payload(result, as_json=as_json)


def list_runs_cli(limit: int, as_json: bool = False):
    agent = build_agent()
    result = {"runs": agent.memory.list_recent_runs(limit=limit)}
    _print_payload(result, as_json=as_json)


def last_failed_cli(as_json: bool = False):
    agent = build_agent()
    result = agent.resume_last_failed_run() or {"status": "not_found", "detail": "No failed runs recorded"}
    _print_payload(result, as_json=as_json)


def retry_context_cli(run_id: str, as_json: bool = False):
    agent = build_agent()
    result = agent.build_retry_context(run_id)
    _print_payload(result, as_json=as_json)


def run_server():
    app = create_app()
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=app.state.settings.api_port, log_level="info")


def run_bot():
    from velocity_claw.telegram_bot.bot import VelocityClawTelegramBot
    settings = load_settings()
    bot = VelocityClawTelegramBot(settings=settings)
    bot.run()


def main():
    parser = argparse.ArgumentParser(description="Velocity Claw AI Agent")
    parser.add_argument("--task", type=str, help="Run a task with the agent")
    parser.add_argument("--server", action="store_true", help="Start FastAPI server")
    parser.add_argument("--telegram", action="store_true", help="Start Telegram bot")
    parser.add_argument("--status", action="store_true", help="Show agent status")
    parser.add_argument("--release-readiness", action="store_true", help="Show release readiness report")
    parser.add_argument("--validate-package", action="store_true", help="Validate package metadata")
    parser.add_argument("--generate-release-notes", action="store_true", help="Generate release notes into dist/release-notes.md")
    parser.add_argument("--release-checklist", action="store_true", help="Run local release checklist summary")
    parser.add_argument("--memory-cleanup", action="store_true", help="Clean old SQLite memory records by retention policy")
    parser.add_argument("--memory-retention-days", type=int, default=None, help="Override memory retention window in days")
    parser.add_argument("--memory-keep-min-runs", type=int, default=None, help="Minimum newest runs to keep during cleanup")
    parser.add_argument("--memory-no-vacuum", action="store_true", help="Skip SQLite VACUUM after cleanup")
    parser.add_argument("--runs", action="store_true", help="List recent runs")
    parser.add_argument("--runs-limit", type=int, default=10, help="Limit for --runs output")
    parser.add_argument("--last-failed", action="store_true", help="Show last failed run")
    parser.add_argument("--retry-context", type=str, help="Build retry context for a run id")
    parser.add_argument("--retry-run", type=str, help="Retry a previous run id with retry context")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    if args.server:
        run_server()
    elif args.telegram:
        run_bot()
    elif args.task:
        asyncio.run(run_task_cli(args.task, as_json=args.json))
    elif args.release_readiness:
        release_readiness_cli(as_json=args.json)
    elif args.validate_package:
        validate_package_cli(as_json=args.json)
    elif args.generate_release_notes:
        generate_release_notes_cli(as_json=args.json)
    elif args.release_checklist:
        release_checklist_cli(as_json=args.json)
    elif args.memory_cleanup:
        memory_cleanup_cli(
            days=args.memory_retention_days,
            keep_min_runs=args.memory_keep_min_runs,
            vacuum=not args.memory_no_vacuum,
            as_json=args.json,
        )
    elif args.runs:
        list_runs_cli(limit=args.runs_limit, as_json=args.json)
    elif args.last_failed:
        last_failed_cli(as_json=args.json)
    elif args.retry_context:
        retry_context_cli(args.retry_context, as_json=args.json)
    elif args.retry_run:
        asyncio.run(retry_run_cli(args.retry_run, as_json=args.json))
    elif args.status:
        agent = build_agent()
        _print_payload(agent.get_status(), as_json=args.json)
    else:
        parser.print_help()


if __name__ == "__main__":
    exit_with_boundary(main, component="cli")
