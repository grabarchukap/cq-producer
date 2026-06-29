import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards import (
    case_confirm_cancel_buttons,
    case_confirm_done_buttons,
    case_confirm_skip_buttons,
    case_extra_buttons,
    case_question_buttons,
    main_menu,
)
from bot.states import CaseState
from case_questions.loader import load_questions
from orchestrator import transcribe_audio
from storage.db import get_pending_cases, list_notifiers, save_case, update_case_status
from agents.gdocs import export_case
from utils.sanitize import sanitize

logger = logging.getLogger(__name__)

# context.user_data keys
_K_STATE       = "case_state"
_K_Q_IDX       = "case_q_index"
_K_ANSWERS     = "case_answers"
_K_MSG_IDS     = "case_msg_ids"
_K_CONFIRM_MSG = "case_confirm_msg_id"
_K_PREV_STATE  = "case_prev_state"
_K_USER_ID     = "case_user_id"
_K_USERNAME    = "case_username"
_K_MENU_MSG    = "main_menu_msg_id"   # shared with handlers.py


# ── Helpers ───────────────────────────────────────────────────────────────────

def _track(context: ContextTypes.DEFAULT_TYPE, *msg_ids: int) -> None:
    """Add message IDs to the cleanup list."""
    ids: list = context.user_data.setdefault(_K_MSG_IDS, [])
    for mid in msg_ids:
        if mid not in ids:
            ids.append(mid)


async def _cleanup(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Delete all tracked interview messages."""
    confirm_id = context.user_data.pop(_K_CONFIRM_MSG, None)
    ids: list = context.user_data.pop(_K_MSG_IDS, [])
    all_ids = list(ids)
    if confirm_id and confirm_id not in all_ids:
        all_ids.append(confirm_id)
    for mid in all_ids:
        try:
            await context.bot.delete_message(chat_id, mid)
        except Exception:
            pass


def _reset(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all case-related keys from user_data."""
    for key in (
        _K_STATE, _K_Q_IDX, _K_ANSWERS, _K_MSG_IDS,
        _K_CONFIRM_MSG, _K_PREV_STATE, _K_USER_ID, _K_USERNAME,
    ):
        context.user_data.pop(key, None)
    context.user_data[_K_STATE] = CaseState.IDLE


async def _delete_confirm(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    confirm_id = context.user_data.pop(_K_CONFIRM_MSG, None)
    if confirm_id:
        try:
            await context.bot.delete_message(chat_id, confirm_id)
        except Exception:
            pass


# ── Question display ──────────────────────────────────────────────────────────

async def _show_question(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    idx: int,
    questions: list[dict],
) -> None:
    total = len(questions)
    text = f"<b>Вопрос {idx + 1} из {total}</b>\n\n{questions[idx]['text']}"
    msg = await context.bot.send_message(
        chat_id, text, parse_mode="HTML",
        reply_markup=case_question_buttons(),
    )
    _track(context, msg.message_id)


async def _show_extra(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[_K_STATE] = CaseState.EXTRA
    msg = await context.bot.send_message(
        chat_id,
        "Спасибо — основные вопросы разобрали.\n\n"
        "Есть что-то, что очень хочется добавить, но не уложилось в рамки заданных вопросов?",
        reply_markup=case_extra_buttons(),
    )
    _track(context, msg.message_id)


# ── Finish / cancel ───────────────────────────────────────────────────────────

async def _export_and_notify(
    bot,
    case_id: int,
    answers: list[dict],
    username: str | None,
) -> None:
    """Export case to Google Docs and notify all notifiers. Called after _finish cleanup."""
    try:
        url = await export_case(answers=answers, username=username)
        await update_case_status(case_id, "done")
    except Exception as exc:
        logger.error("Case export failed (id=%s): %s", case_id, exc)
        await update_case_status(case_id, "pending")
        return

    # Send notifications
    try:
        notifiers = await list_notifiers()
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
                logger.warning("Failed to notify user %s: %s", notifier["user_id"], exc)
    except Exception as exc:
        logger.error("Notification error: %s", exc)


async def _finish(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save answers to DB, return to main menu, then export in background."""
    answers = context.user_data.get(_K_ANSWERS, [])
    user_id = context.user_data.get(_K_USER_ID, 0)
    username = context.user_data.get(_K_USERNAME)

    case_id: int | None = None
    try:
        case_id = await save_case(user_id, username, answers)
    except Exception as exc:
        logger.error("Failed to save case for user %s: %s", user_id, exc)

    await _cleanup(context, chat_id)
    _reset(context)

    msg = await context.bot.send_message(
        chat_id,
        "Спасибо! Ответы записаны — скоро на их основе подготовим кейс.",
        reply_markup=main_menu(),
    )
    context.user_data[_K_MENU_MSG] = msg.message_id

    # Fire-and-forget export (doesn't block user)
    if case_id is not None:
        asyncio.create_task(
            _export_and_notify(context.bot, case_id, answers, username)
        )


async def _cancel(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel without saving."""
    await _cleanup(context, chat_id)
    _reset(context)

    msg = await context.bot.send_message(
        chat_id, "Главное меню:", reply_markup=main_menu(),
    )
    context.user_data[_K_MENU_MSG] = msg.message_id


# ── Public entry point ────────────────────────────────────────────────────────

async def start_case(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    btn_msg_id: int | None = None,
) -> None:
    """Initialize state and show question 1."""
    questions = load_questions()
    if not questions:
        msg = await update.effective_message.reply_text(
            "Список вопросов пуст. Обратитесь к администратору.",
            reply_markup=main_menu(),
        )
        context.user_data[_K_MENU_MSG] = msg.message_id
        return

    context.user_data[_K_STATE]    = CaseState.QUESTION
    context.user_data[_K_Q_IDX]    = 0
    context.user_data[_K_ANSWERS]  = []
    context.user_data[_K_MSG_IDS]  = []
    context.user_data[_K_USER_ID]  = update.effective_user.id
    context.user_data[_K_USERNAME] = update.effective_user.username

    if btn_msg_id:
        _track(context, btn_msg_id)

    await _show_question(update.effective_chat.id, context, 0, questions)


# ── Answer handler ────────────────────────────────────────────────────────────

async def on_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a text or voice answer during the interview."""
    state = context.user_data.get(_K_STATE)

    # During confirmation dialogs — silently delete user message
    if state in (CaseState.CONFIRM_SKIP, CaseState.CONFIRM_DONE, CaseState.CONFIRM_CANCEL):
        try:
            await update.effective_message.delete()
        except Exception:
            pass
        return

    if state not in (CaseState.QUESTION, CaseState.EXTRA):
        return

    message = update.effective_message
    _track(context, message.message_id)
    chat_id = update.effective_chat.id

    answer_text: str | None = None
    if message.voice:
        status = await message.reply_text("🎙 Распознаю...")
        _track(context, status.message_id)
        try:
            voice_file = await message.voice.get_file()
            audio_bytes = bytes(await voice_file.download_as_bytearray())
            answer_text = await transcribe_audio(audio_bytes)
            await status.delete()
            try:
                context.user_data[_K_MSG_IDS].remove(status.message_id)
            except ValueError:
                pass
        except Exception as exc:
            await status.edit_text(f"⚠️ {exc}")
            return
    elif message.text:
        answer_text = sanitize(message.text)

    if not answer_text:
        err = await message.reply_text("Напиши или отправь голосовое.")
        _track(context, err.message_id)
        return

    questions = load_questions()
    answers: list = context.user_data.setdefault(_K_ANSWERS, [])

    if state == CaseState.EXTRA:
        answers.append({"question": "Дополнительно", "answer": answer_text})
        await _finish(chat_id, context)
        return

    idx = context.user_data.get(_K_Q_IDX, 0)
    answers.append({"question": questions[idx]["text"], "answer": answer_text})
    next_idx = idx + 1
    context.user_data[_K_Q_IDX] = next_idx

    if next_idx >= len(questions):
        await _show_extra(chat_id, context)
    else:
        await _show_question(chat_id, context, next_idx, questions)


# ── Callback handler ──────────────────────────────────────────────────────────

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle case: inline keyboard callbacks."""
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]
    chat_id = query.message.chat_id
    state = context.user_data.get(_K_STATE)

    if action == "skip":
        context.user_data[_K_PREV_STATE] = state
        context.user_data[_K_STATE] = CaseState.CONFIRM_SKIP
        msg = await context.bot.send_message(
            chat_id,
            "Пропустить этот вопрос? Ответ сохранится как пустой.",
            reply_markup=case_confirm_skip_buttons(),
        )
        context.user_data[_K_CONFIRM_MSG] = msg.message_id

    elif action == "done":
        answers = context.user_data.get(_K_ANSWERS, [])
        questions = load_questions()
        answered = len([a for a in answers if a.get("answer")])
        total = len(questions)
        context.user_data[_K_PREV_STATE] = state
        context.user_data[_K_STATE] = CaseState.CONFIRM_DONE
        msg = await context.bot.send_message(
            chat_id,
            f"Завершить опрос? Уже отвеченные вопросы ({answered} из {total}) будут сохранены. "
            "На оставшиеся — запишем пустые ответы.",
            reply_markup=case_confirm_done_buttons(),
        )
        context.user_data[_K_CONFIRM_MSG] = msg.message_id

    elif action == "cancel":
        context.user_data[_K_PREV_STATE] = state
        context.user_data[_K_STATE] = CaseState.CONFIRM_CANCEL
        msg = await context.bot.send_message(
            chat_id,
            "Отменить опрос? Все ответы будут удалены и никуда не сохранятся.",
            reply_markup=case_confirm_cancel_buttons(),
        )
        context.user_data[_K_CONFIRM_MSG] = msg.message_id

    elif action == "extra_done":
        await _finish(chat_id, context)

    elif action == "yes_skip":
        await _delete_confirm(context, chat_id)
        questions = load_questions()
        idx = context.user_data.get(_K_Q_IDX, 0)
        answers: list = context.user_data.setdefault(_K_ANSWERS, [])
        answers.append({"question": questions[idx]["text"], "answer": None})
        next_idx = idx + 1
        context.user_data[_K_Q_IDX] = next_idx
        context.user_data[_K_STATE] = CaseState.QUESTION
        if next_idx >= len(questions):
            await _show_extra(chat_id, context)
        else:
            await _show_question(chat_id, context, next_idx, questions)

    elif action == "yes_done":
        await _delete_confirm(context, chat_id)
        questions = load_questions()
        answers = context.user_data.setdefault(_K_ANSWERS, [])
        idx = context.user_data.get(_K_Q_IDX, 0)
        for i in range(idx, len(questions)):
            answers.append({"question": questions[i]["text"], "answer": None})
        await _finish(chat_id, context)

    elif action == "yes_cancel":
        await _delete_confirm(context, chat_id)
        await _cancel(chat_id, context)

    elif action == "no":
        await _delete_confirm(context, chat_id)
        prev = context.user_data.pop(_K_PREV_STATE, CaseState.QUESTION)
        context.user_data[_K_STATE] = prev
