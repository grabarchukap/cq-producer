import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards import BTN_ADMIN, BTN_CASE, BTN_NEW_POST
from bot.states import AdminState, UserState
import bot.handlers as handlers
import bot.admin as admin

logger = logging.getLogger(__name__)

_K_ADMIN_STATE = "admin_state"
_K_USER_STATE = "user_state"


async def route_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route an incoming text message to the correct handler."""
    admin_state = context.user_data.get(_K_ADMIN_STATE, AdminState.IDLE)

    # Admin flow takes priority when an active admin state expects text input
    if admin_state not in (AdminState.IDLE, AdminState.MENU):
        await admin.on_message(update, context)
        return

    # Main menu button shortcuts — intercept before user state checks
    text = (update.message.text or "").strip()
    if text == BTN_NEW_POST:
        await handlers.on_new_post(update, context)
        return
    if text == BTN_CASE:
        await handlers.on_case(update, context)
        return
    if text == BTN_ADMIN:
        await admin.cmd_admin(update, context)
        return

    user_state = context.user_data.get(_K_USER_STATE, UserState.IDLE)

    if user_state == UserState.EDITING:
        await handlers.on_edit(update, context)
        return

    if user_state == UserState.PROCESSING:
        await update.message.reply_text(
            "Подожди — я ещё обрабатываю предыдущий запрос."
        )
        return

    await handlers.on_input(update, context)


async def route_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route an incoming voice message to the correct handler."""
    admin_state = context.user_data.get(_K_ADMIN_STATE, AdminState.IDLE)
    if admin_state not in (AdminState.IDLE, AdminState.MENU):
        await update.message.reply_text(
            "В режиме администратора голосовые не поддерживаются. Отправь текст."
        )
        return

    user_state = context.user_data.get(_K_USER_STATE, UserState.IDLE)

    if user_state == UserState.EDITING:
        await handlers.on_edit(update, context)
        return

    if user_state == UserState.PROCESSING:
        await update.message.reply_text(
            "Подожди — я ещё обрабатываю предыдущий запрос."
        )
        return

    await handlers.on_input(update, context)


async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route an inline keyboard callback to the correct handler."""
    data = update.callback_query.data or ""

    if data.startswith("adm:"):
        await admin.on_callback(update, context)
    elif data.startswith("tov:"):
        await handlers.on_tov_selected(update, context)
    elif data.startswith("post:"):
        await handlers.on_post_callback(update, context)
    else:
        logger.warning("Unknown callback data: %s", data)
        await update.callback_query.answer("Неизвестное действие")
