import json
import logging

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import asyncio

import config
from bot import admin, handlers, router
from bot.case import export_and_notify
from profiles.loader import load_profiles
from storage.db import get_pending_cases, init_db
from utils.data_dir import ensure_data_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# httpx logs every request URL at INFO, and Telegram API URLs contain the bot token
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def _retry_pending_cases(bot) -> None:
    """On startup, retry export for any cases that didn't make it last time."""
    pending = await get_pending_cases()
    if not pending:
        return
    logger.info("Found %d pending case(s) — retrying export", len(pending))
    for row in pending:
        await export_and_notify(
            bot, row["id"], json.loads(row["answers"]), row.get("username")
        )


async def post_init(application: Application) -> None:
    """Runs once after the Application is fully initialised."""
    ensure_data_dir()
    await init_db()
    load_profiles()
    await application.bot.set_my_commands([
        BotCommand("start", "Главное меню"),
    ])
    mode = "polling" if config.DEV_MODE else "webhook"
    logger.info("Initialisation complete — %s mode", mode)
    asyncio.create_task(_retry_pending_cases(application.bot))


def main() -> None:
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .concurrent_updates(False)
        .build()
    )

    # ── Commands ──────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("admin", admin.cmd_admin))

    # ── Messages ──────────────────────────────────────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router.route_text))
    app.add_handler(MessageHandler(filters.VOICE, router.route_voice))

    # ── Callbacks ─────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(router.route_callback))

    if config.DEV_MODE:
        logger.info("DEV_MODE — starting with polling")
        app.run_polling(drop_pending_updates=True)
    else:
        # The bot token is used as the URL path so the endpoint is not guessable.
        webhook_url = f"{config.WEBHOOK_URL.rstrip('/')}/{config.TELEGRAM_BOT_TOKEN}"
        logger.info(
            "Starting webhook on 0.0.0.0:%d  path=/%s",
            config.WEBHOOK_PORT,
            config.TELEGRAM_BOT_TOKEN[:8] + "…",
        )
        app.run_webhook(
            listen="0.0.0.0",
            port=config.WEBHOOK_PORT,
            url_path=config.TELEGRAM_BOT_TOKEN,
            webhook_url=webhook_url,
            secret_token=config.WEBHOOK_SECRET_TOKEN or None,
            drop_pending_updates=True,
        )


if __name__ == "__main__":
    # Python 3.12+ no longer implicitly creates an event loop.
    # PTB 21 calls asyncio.get_event_loop() internally inside run_polling/run_webhook,
    # so we must set one explicitly before calling main().
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
