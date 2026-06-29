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
from agents.gdocs import export_case
from bot import admin, handlers, router
from profiles.loader import load_profiles
from storage.db import get_pending_cases, init_db, list_notifiers, update_case_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _retry_pending_cases(bot) -> None:
    """On startup, retry export for any cases that didn't make it last time."""
    pending = await get_pending_cases()
    if not pending:
        return
    logger.info("Found %d pending case(s) — retrying export", len(pending))
    notifiers = await list_notifiers()
    for row in pending:
        import json as _json
        case_id = row["id"]
        answers = _json.loads(row["answers"])
        username = row.get("username")
        try:
            url = await export_case(answers=answers, username=username)
            await update_case_status(case_id, "done")
            # Notify
            first_answer = (answers[0].get("answer") or "").strip() if answers else ""
            author_part = f"@{username}" if username else "пользователь"
            text = (
                f"📋 Новый кейс от {author_part}\n"
                f"Клиент: {first_answer or '—'}\n\n"
                f"👉 <a href=\"{url}\">Открыть документ</a>"
            )
            for notifier in notifiers:
                try:
                    await bot.send_message(
                        notifier["user_id"], text, parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                except Exception as exc:
                    logger.warning("Notify failed for %s: %s", notifier["user_id"], exc)
        except Exception as exc:
            logger.error("Retry export failed for case %s: %s", case_id, exc)


async def post_init(application: Application) -> None:
    """Runs once after the Application is fully initialised."""
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
