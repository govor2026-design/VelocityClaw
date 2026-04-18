import asyncio
from typing import Optional
from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.logs.logger import get_logger


class VelocityClawTelegramBot:
    def __init__(self, settings: Settings):
        try:
            from telegram.ext import ApplicationBuilder
        except ImportError as exc:
            raise ImportError(
                "python-telegram-bot is required for Telegram integration. Install it with `pip install python-telegram-bot`."
            ) from exc
        self.settings = settings
        self.logger = get_logger("velocity_claw.telegram")
        self.agent = VelocityClawAgent(settings=settings)
        self.app = ApplicationBuilder().token(settings.telegram_token).build()
        self._register_handlers()

    def _register_handlers(self):
        from telegram.ext import CommandHandler, MessageHandler, filters

        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(CommandHandler("status", self.status))
        self.app.add_handler(CommandHandler("model", self.model))
        self.app.add_handler(CommandHandler("reset", self.reset))
        self.app.add_handler(CommandHandler("plan", self.plan))
        self.app.add_handler(CommandHandler("logs", self.logs))
        self.app.add_handler(CommandHandler("stop", self.stop))
        self.app.add_handler(CommandHandler("task", self.task))
        self.app.add_handler(MessageHandler(filters.Document.ALL | filters.TEXT & ~filters.COMMAND, self.receive_message))

    async def _check_access(self, update) -> bool:
        if not self.settings.telegram_chat_id:
            return True
        return str(update.effective_chat.id) == str(self.settings.telegram_chat_id)

    async def start(self, update, context):
        if not await self._check_access(update):
            return await update.message.reply_text("Access denied.")
        await update.message.reply_text("Velocity Claw active. Отправь /help для списка команд.")

    async def help(self, update, context):
        if not await self._check_access(update):
            return await update.message.reply_text("Access denied.")
        await update.message.reply_text(
            "/start\n/help\n/status\n/model\n/reset\n/task <описание>\n/plan\n/logs\n/stop"
        )

    async def status(self, update, context):
        if not await self._check_access(update):
            return await update.message.reply_text("Access denied.")
        status = self.agent.get_status()
        await update.message.reply_text(str(status))

    async def model(self, update, context):
        if not await self._check_access(update):
            return await update.message.reply_text("Access denied.")
        await update.message.reply_text(f"Active model route: {self.agent.router.choose_provider('analysis')}")

    async def reset(self, update, context):
        if not await self._check_access(update):
            return await update.message.reply_text("Access denied.")
        result = self.agent.reset_context()
        await update.message.reply_text(str(result))

    async def plan(self, update, context):
        if not await self._check_access(update):
            return await update.message.reply_text("Access denied.")
        task = " ".join(context.args) if getattr(context, "args", None) else None
        if not task:
            return await update.message.reply_text("Укажите задачу после /plan.")
        plan = await self.agent.planner.create_plan(task)
        await update.message.reply_text(f"Plan:\n{plan}")

    async def logs(self, update, context):
        if not await self._check_access(update):
            return await update.message.reply_text("Access denied.")
        await update.message.reply_text("Logs available in velocity_claw/logs/velocity_claw.log")

    async def stop(self, update, context):
        if not await self._check_access(update):
            return await update.message.reply_text("Access denied.")
        await update.message.reply_text("Velocity Claw остановлен вручную.")
        await self.app.stop()

    async def task(self, update, context):
        if not await self._check_access(update):
            return await update.message.reply_text("Access denied.")
        task = " ".join(context.args) if getattr(context, "args", None) else None
        if not task and update.message.text:
            task = update.message.text.replace("/task", "", 1).strip()
        if not task:
            return await update.message.reply_text("Укажите описание задачи после /task.")
        await update.message.reply_text("Принято. Запускаю Velocity Claw.")
        report = await self.agent.run_task(task)
        await update.message.reply_text(f"Результат:\n{report}")

    async def receive_message(self, update, context):
        if not await self._check_access(update):
            return
        text = update.message.text or ""
        if text.strip():
            await update.message.reply_text("Принято. Обрабатываю задачу.")
            report = await self.agent.run_task(text)
            await update.message.reply_text(f"Результат:\n{report}")
        elif getattr(update.message, "document", None):
            await update.message.reply_text("Файл принят. Сейчас не поддерживается прямое выполнение вложений.")

    def run(self):
        self.app.run_polling()
