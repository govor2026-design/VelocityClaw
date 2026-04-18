import argparse
import asyncio
from velocity_claw.config.settings import load_settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.api.server import create_app


def build_agent():
    settings = load_settings()
    return VelocityClawAgent(settings=settings)


def _append_signature(text: str) -> str:
    return f"{text.rstrip()}\n\nvelocity claw"


async def run_task_cli(task: str):
    agent = build_agent()
    result = await agent.run_task(task)
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
    args = parser.parse_args()

    if args.server:
        run_server()
    elif args.telegram:
        run_bot()
    elif args.task:
        asyncio.run(run_task_cli(args.task))
    elif args.status:
        print(_append_signature("Velocity Claw ready. Use --task, --server or --telegram."))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
