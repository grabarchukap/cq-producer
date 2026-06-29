import functools
import logging

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

from bot.keyboards import edit_actions, main_menu, post_actions, tov_selection
from bot.states import AdminState, UserState
from orchestrator import run_edit, run_pipeline, transcribe_audio
from profiles.loader import get_profile, list_profiles
from storage.db import is_allowed
from utils.sanitize import sanitize

logger = logging.getLogger(__name__)

# context.user_data keys
_K_STATE           = "user_state"
_K_AUTHOR          = "author_id"
_K_POST            = "current_post"
_K_MENU_MSG        = "main_menu_msg_id"
_K_TOV_MSG         = "tov_msg_id"
_K_AUTHOR_MSG      = "author_msg_id"
_K_EDIT_PROMPT_MSG = "edit_prompt_msg_id"
_K_NEW_POST_BTN    = "new_post_btn_msg_id"


async def _delete_msg(context: ContextTypes.DEFAULT_TYPE, chat_id: int, key: str) -> None:
    """Delete a tracked bot message and clear its key from user_data."""
    msg_id = context.user_data.pop(key, None)
    if msg_id:
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass


async def _try_delete(message) -> None:
    """Delete any message, swallowing errors."""
    try:
        await message.delete()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def require_auth(func):
    """Reject users not on the whitelist."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await is_allowed(update.effective_user.id):
            await update.effective_message.reply_text(
                "У вас нет доступа к этому боту."
            )
            return
        return await func(update, context)
    return wrapper


# ---------------------------------------------------------------------------
# /start — shows main menu
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — resets all state and shows the main menu keyboard."""
    context.user_data[_K_STATE] = UserState.IDLE
    context.user_data[_K_POST] = None
    context.user_data[_K_AUTHOR] = None
    context.user_data["admin_state"] = AdminState.IDLE
    context.user_data["admin_authed"] = False

    if not await is_allowed(update.effective_user.id):
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return

    msg = await update.message.reply_text("Главное меню:", reply_markup=main_menu())
    context.user_data[_K_MENU_MSG] = msg.message_id


# ---------------------------------------------------------------------------
# Main menu button: «Создать новый пост»
# ---------------------------------------------------------------------------

@require_auth
async def on_new_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete main menu message, hide keyboard, show profile selector."""
    context.user_data[_K_STATE] = UserState.IDLE
    context.user_data[_K_POST] = None
    context.user_data[_K_AUTHOR] = None

    # Track button-press message — delete it only if user presses "Назад"
    context.user_data[_K_NEW_POST_BTN] = update.message.message_id

    chat_id = update.effective_chat.id
    await _delete_msg(context, chat_id, _K_MENU_MSG)

    profiles = list_profiles()
    if not profiles:
        await update.message.reply_text(
            "Профили авторов не найдены. Обратитесь к администратору.",
        )
        msg = await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        context.user_data[_K_MENU_MSG] = msg.message_id
        return

    rm = await update.message.reply_text(".", reply_markup=ReplyKeyboardRemove())
    await rm.delete()
    msg = await update.message.reply_text("Выбери стиль автора:", reply_markup=tov_selection(profiles))
    context.user_data[_K_TOV_MSG] = msg.message_id


# ---------------------------------------------------------------------------
# Main menu button: «Я хочу поделиться кейсом» (placeholder)
# ---------------------------------------------------------------------------

@require_auth
async def on_case(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Placeholder — silently returns to main menu (always treated as back)."""
    await _try_delete(update.message)
    chat_id = update.effective_chat.id
    await _delete_msg(context, chat_id, _K_MENU_MSG)

    rm = await update.message.reply_text(".", reply_markup=ReplyKeyboardRemove())
    await rm.delete()
    msg = await update.message.reply_text("Главное меню:", reply_markup=main_menu())
    context.user_data[_K_MENU_MSG] = msg.message_id


# ---------------------------------------------------------------------------
# ToV selection callback
# ---------------------------------------------------------------------------

@require_auth
async def on_tov_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    author_id = query.data.split(":", 1)[1]
    chat = query.message.chat

    if author_id == "back":
        await query.message.delete()
        context.user_data.pop(_K_TOV_MSG, None)
        # User went back without starting a flow — delete the button-press message
        await _delete_msg(context, query.message.chat.id, _K_NEW_POST_BTN)
        msg = await chat.send_message("Главное меню:", reply_markup=main_menu())
        context.user_data[_K_MENU_MSG] = msg.message_id
        return

    try:
        profile = get_profile(author_id)
    except KeyError:
        await query.edit_message_text("Профиль не найден. Нажми /start снова.")
        return

    context.user_data[_K_AUTHOR] = author_id
    context.user_data[_K_STATE] = UserState.IDLE

    await query.message.delete()
    context.user_data.pop(_K_TOV_MSG, None)
    msg = await chat.send_message(
        f"Выбран стиль: <b>{profile.display_name}</b>\n\n"
        "Отправь голосовое сообщение или текст — создам пост.",
        parse_mode="HTML",
    )
    context.user_data[_K_AUTHOR_MSG] = msg.message_id


# ---------------------------------------------------------------------------
# Main input handler (IDLE state)
# ---------------------------------------------------------------------------

@require_auth
async def on_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Accept text or voice and run the full pipeline."""
    state = context.user_data.get(_K_STATE, UserState.IDLE)

    if state == UserState.PROCESSING:
        await update.effective_message.reply_text(
            "Подожди — я ещё обрабатываю предыдущий запрос."
        )
        return

    author_id = context.user_data.get(_K_AUTHOR)
    if not author_id:
        await update.effective_message.reply_text(
            "Сначала выбери стиль автора — нажми «✍️ Создать новый пост»"
        )
        return

    message = update.effective_message

    if not message.voice and not message.text:
        await message.reply_text("Отправь текст или голосовое сообщение.")
        return
    if message.text and not sanitize(message.text):
        await message.reply_text("Сообщение пустое или содержит недопустимые символы.")
        return

    # Delete "Выбран стиль:..." now that we have input
    await _delete_msg(context, update.effective_chat.id, _K_AUTHOR_MSG)

    context.user_data[_K_STATE] = UserState.PROCESSING
    status_msg = await message.reply_text("⏳ Начинаю...")

    async def on_progress(step_text: str) -> None:
        try:
            await status_msg.edit_text(step_text)
        except Exception:
            pass

    audio_bytes: bytes | None = None
    text: str | None = None
    try:
        if message.voice:
            await on_progress("🎙 Скачиваю аудио...")
            voice_file = await message.voice.get_file()
            audio_bytes = bytes(await voice_file.download_as_bytearray())
        else:
            text = sanitize(message.text)

        final_post = await run_pipeline(
            audio_bytes=audio_bytes,
            text=text,
            author_id=author_id,
            on_progress=on_progress,
        )
        context.user_data[_K_POST] = final_post
        await status_msg.edit_text(
            f"✅ Готово!\n\n{final_post}",
            reply_markup=post_actions(),
        )
    except ValueError as exc:
        await status_msg.edit_text(f"⚠️ {exc}")
    except Exception as exc:
        logger.error("Pipeline error for user %s: %s", update.effective_user.id, exc, exc_info=True)
        await status_msg.edit_text(
            "Произошла ошибка при генерации поста. Попробуй ещё раз."
        )
    finally:
        context.user_data[_K_STATE] = UserState.IDLE


# ---------------------------------------------------------------------------
# Edit handler (EDITING state)
# ---------------------------------------------------------------------------

@require_auth
async def on_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Apply a targeted edit to the current post."""
    if context.user_data.get(_K_STATE) != UserState.EDITING:
        return
    context.user_data[_K_STATE] = UserState.PROCESSING

    try:
        await _delete_msg(context, update.effective_chat.id, _K_EDIT_PROMPT_MSG)

        current_post = context.user_data.get(_K_POST)
        author_id = context.user_data.get(_K_AUTHOR)

        if not current_post or not author_id:
            await update.effective_message.reply_text(
                "Нет активного поста. Нажми /start чтобы начать заново."
            )
            context.user_data[_K_STATE] = UserState.IDLE
            return

        message = update.effective_message
        user_request: str | None = None

        if message.voice:
            voice_file = await message.voice.get_file()
            audio_bytes = bytes(await voice_file.download_as_bytearray())
            try:
                user_request = await transcribe_audio(audio_bytes)
            except Exception as exc:
                await message.reply_text(f"⚠️ {exc}")
                return
        elif message.text:
            user_request = sanitize(message.text)

        if not user_request:
            await message.reply_text("Напиши или скажи что нужно исправить.")
            return

        status_msg = await message.reply_text("✍️ Вношу правки...")
        try:
            new_post = await run_edit(current_post, user_request, author_id)
            context.user_data[_K_POST] = new_post
            await status_msg.edit_text(
                f"✅ Вот обновлённый пост:\n\n{new_post}",
                reply_markup=edit_actions(),
            )
        except Exception as exc:
            logger.error("Edit error for user %s: %s", update.effective_user.id, exc, exc_info=True)
            await status_msg.edit_text("Ошибка при правке. Попробуй ещё раз.")
    finally:
        if context.user_data.get(_K_STATE) == UserState.PROCESSING:
            context.user_data[_K_STATE] = UserState.EDITING


# ---------------------------------------------------------------------------
# Post action callbacks (edit / done buttons)
# ---------------------------------------------------------------------------

@require_auth
async def on_post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]

    if action == "edit":
        context.user_data[_K_STATE] = UserState.EDITING
        await query.edit_message_reply_markup(reply_markup=None)
        msg = await query.message.reply_text(
            "Напиши или отправь голосовое с тем, что нужно изменить."
        )
        context.user_data[_K_EDIT_PROMPT_MSG] = msg.message_id

    elif action == "done":
        context.user_data[_K_STATE] = UserState.IDLE
        context.user_data[_K_POST] = None
        await query.edit_message_reply_markup(reply_markup=None)
        msg = await query.message.reply_text("Главное меню:", reply_markup=main_menu())
        context.user_data[_K_MENU_MSG] = msg.message_id
