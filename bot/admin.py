import logging

from telegram import Update
from telegram.ext import ContextTypes

import profiles.loader as loader
import storage.db as db
from bot.keyboards import (
    admin_menu,
    back_button,
    bool_field_buttons,
    cancel_auth_button,
    examples_keyboard,
    lang_field_buttons,
    main_menu,
    post_structure_menu,
    profile_edit_menu,
    profile_list_keyboard,
    prompts_menu,
    text_field_buttons,
)
from bot.states import AdminState
from config import ADMIN_PASSWORD

logger = logging.getLogger(__name__)

# ── context.user_data keys ────────────────────────────────────────────────────
_K_STATE              = "admin_state"
_K_AUTHED             = "admin_authed"
_K_TOV_NAME           = "admin_pending_tov_name"
_K_AUTHOR             = "admin_pending_author"
_K_PROMPT_ID          = "admin_prompt_msg_id"
_K_ADMIN_MENU_MSG     = "admin_menu_msg_id"
_K_ADMIN_TRIGGER_MSG  = "admin_trigger_msg_id"
_K_MENU_MSG           = "main_menu_msg_id"      # shared with handlers.py
_K_EDIT_PROFILE       = "admin_edit_profile_id"
_K_EDIT_FIELD         = "admin_edit_field_name"

# ── Profile field metadata ────────────────────────────────────────────────────

# Maps the short field key used in callbacks to the dot-notation JSON path
_FIELD_PATH: dict[str, str] = {
    "display_name":      "display_name",
    "tone_description":  "tone_description",
    "language":          "language",
    "forbidden_phrases": "forbidden_phrases",
    "max_length_chars":  "post_structure.max_length_chars",
    "paragraphs_min":    "post_structure.paragraphs.min",
    "paragraphs_max":    "post_structure.paragraphs.max",
    "use_emoji":         "post_structure.use_emoji",
    "use_hashtags":      "post_structure.use_hashtags",
    "hashtag_style":     "post_structure.hashtag_style",
    "formatting_hints":  "post_structure.formatting_hints",
    "expand":            "agent_prompts.expand",
    "tone":              "agent_prompts.tone",
    "format":            "agent_prompts.format",
    "qa":                "agent_prompts.qa",
    "edit":              "agent_prompts.edit",
}

# Input type: "text" | "int" | "phrases" | "bool" | "lang" | "prompt"
_FIELD_TYPE: dict[str, str] = {
    "display_name":      "text",
    "tone_description":  "text",
    "language":          "lang",
    "forbidden_phrases": "phrases",
    "max_length_chars":  "int",
    "paragraphs_min":    "int",
    "paragraphs_max":    "int",
    "use_emoji":         "bool",
    "use_hashtags":      "bool",
    "hashtag_style":     "text",
    "formatting_hints":  "text",
    "expand":            "prompt",
    "tone":              "prompt",
    "format":            "prompt",
    "qa":                "prompt",
    "edit":              "prompt",
}

# Which submenu to return to after editing
_FIELD_BACK: dict[str, str] = {
    "display_name":      "prof_menu",
    "tone_description":  "prof_menu",
    "language":          "prof_menu",
    "forbidden_phrases": "prof_menu",
    "max_length_chars":  "struct_menu",
    "paragraphs_min":    "struct_menu",
    "paragraphs_max":    "struct_menu",
    "use_emoji":         "struct_menu",
    "use_hashtags":      "struct_menu",
    "hashtag_style":     "struct_menu",
    "formatting_hints":  "struct_menu",
    "expand":            "prompts_menu",
    "tone":              "prompts_menu",
    "format":            "prompts_menu",
    "qa":                "prompts_menu",
    "edit":              "prompts_menu",
}

# Human-readable descriptions shown above each field editor
_FIELD_DESC: dict[str, str] = {
    "display_name": (
        "✏️ <b>Название профиля</b>\n\n"
        "Имя автора, которое видит пользователь при выборе стиля."
    ),
    "tone_description": (
        "📝 <b>Описание стиля</b>\n\n"
        "Текст, описывающий манеру письма автора. "
        "На его основе AI переписывает пост в нужном стиле."
    ),
    "language": (
        "🌐 <b>Язык поста</b>\n\n"
        "Язык, на котором должен быть написан готовый пост."
    ),
    "forbidden_phrases": (
        "🚫 <b>Запрещённые фразы</b>\n\n"
        "Слова и выражения, которые AI никогда не должен использовать. "
        "Введи через запятую.\n\n"
        "Пример: <i>синергия, кейс, инсайт</i>"
    ),
    "max_length_chars": (
        "📏 <b>Максимальная длина поста</b>\n\n"
        "Ограничение на количество символов. "
        "AI обрежет или перепишет пост, если он окажется длиннее."
    ),
    "paragraphs_min": (
        "📄 <b>Минимум абзацев</b>\n\n"
        "Наименьшее допустимое количество смысловых блоков в посте."
    ),
    "paragraphs_max": (
        "📄 <b>Максимум абзацев</b>\n\n"
        "Наибольшее допустимое количество смысловых блоков в посте."
    ),
    "use_emoji": (
        "😊 <b>Использовать эмодзи</b>\n\n"
        "Разрешить ли AI добавлять эмодзи в текст поста."
    ),
    "use_hashtags": (
        "#️⃣ <b>Использовать хэштеги</b>\n\n"
        "Добавлять ли хэштеги в конец поста."
    ),
    "hashtag_style": (
        "🏷️ <b>Стиль хэштегов</b>\n\n"
        "Описание того, какие хэштеги использовать и как оформлять.\n\n"
        "Пример: <i>не более 3 штук, только по теме поста</i>"
    ),
    "formatting_hints": (
        "💡 <b>Подсказки форматирования</b>\n\n"
        "Дополнительные инструкции по оформлению поста.\n\n"
        "Пример: <i>разделяй абзацы пустой строкой, первое предложение — главная мысль</i>"
    ),
}

_PROMPT_DESC: dict[str, str] = {
    "expand": (
        "<b>Expand</b> — черновик из транскрипта\n\n"
        "Получает сырой текст или транскрипт голосового. "
        "Задача: убрать слова-паразиты, заполнить пропуски, сохранить все идеи."
    ),
    "tone": (
        "<b>Tone</b> — применение стиля автора\n\n"
        "Получает черновик и описание стиля. "
        "Задача: переписать текст в манере автора."
    ),
    "format": (
        "<b>Format</b> — форматирование\n\n"
        "Получает пост и правила структуры. "
        "Задача: длина, количество абзацев, правила по эмодзи и хэштегам."
    ),
    "qa": (
        "<b>QA</b> — контроль качества\n\n"
        "Финальная проверка: орфография, пунктуация, соответствие стилю, запрещённые фразы."
    ),
    "edit": (
        "<b>Edit</b> — правки по запросу\n\n"
        "Получает текущий пост и запрос пользователя. "
        "Задача: внести только запрошенные изменения, сохранить стиль и структуру."
    ),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _try_delete(message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def _delete_by_id(context: ContextTypes.DEFAULT_TYPE, chat_id: int, key: str) -> None:
    msg_id = context.user_data.pop(key, None)
    if msg_id:
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass


def _current_value(profile, field_name: str) -> str:
    """Return the current field value as a display string."""
    ps = profile.post_structure
    ap = profile.agent_prompts
    values: dict[str, object] = {
        "display_name":      profile.display_name,
        "tone_description":  profile.tone_description,
        "language":          profile.language,
        "forbidden_phrases": ", ".join(profile.forbidden_phrases) if profile.forbidden_phrases else "(не задано)",
        "max_length_chars":  ps.max_length_chars,
        "paragraphs_min":    ps.paragraphs.get("min", 2),
        "paragraphs_max":    ps.paragraphs.get("max", 5),
        "use_emoji":         ps.use_emoji,
        "use_hashtags":      ps.use_hashtags,
        "hashtag_style":     ps.hashtag_style or "(не задано)",
        "formatting_hints":  ps.formatting_hints or "(не задано)",
        "expand":            ap.expand,
        "tone":              ap.tone,
        "format":            ap.format,
        "qa":                ap.qa,
        "edit":              ap.edit,
    }
    return str(values.get(field_name, ""))


async def _show_field_editor(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    admin_msg_id: int,
    profile,
    field_name: str,
) -> None:
    """Edit the admin panel message to show the field editor."""
    field_type = _FIELD_TYPE[field_name]
    current = _current_value(profile, field_name)

    if field_type == "bool":
        bool_val = profile.post_structure.use_emoji if field_name == "use_emoji" else profile.post_structure.use_hashtags
        text = f"{_FIELD_DESC[field_name]}\n\n<b>Текущее значение:</b> {'✅ Да' if bool_val else '❌ Нет'}"
        markup = bool_field_buttons(bool_val)
    elif field_type == "lang":
        text = f"{_FIELD_DESC[field_name]}\n\n<b>Текущий язык:</b> {current.upper()}"
        markup = lang_field_buttons(current)
    elif field_type == "prompt":
        desc = _PROMPT_DESC[field_name]
        preview = current[:500] if current else "(не задано)"
        text = f"{desc}\n\n<b>Текущий промпт:</b>\n<code>{preview}</code>\n\nОтправь новый текст промпта:"
        markup = text_field_buttons()
    else:  # text, int, phrases
        preview = current[:300] if current else "(не задано)"
        text = f"{_FIELD_DESC[field_name]}\n\n<b>Текущее значение:</b>\n<code>{preview}</code>\n\nОтправь новое значение:"
        markup = text_field_buttons()

    await context.bot.edit_message_text(
        text, chat_id=chat_id, message_id=admin_msg_id,
        parse_mode="HTML", reply_markup=markup,
    )


async def _show_back_menu(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    admin_msg_id: int,
    profile,
    back_to: str,
) -> None:
    """Return to the appropriate submenu after editing a field."""
    if back_to == "struct_menu":
        await context.bot.edit_message_text(
            f"Структура поста — <b>{profile.display_name}</b>:",
            chat_id=chat_id, message_id=admin_msg_id,
            parse_mode="HTML", reply_markup=post_structure_menu(profile),
        )
    elif back_to == "prompts_menu":
        await context.bot.edit_message_text(
            f"Промпты — <b>{profile.display_name}</b>:",
            chat_id=chat_id, message_id=admin_msg_id,
            parse_mode="HTML", reply_markup=prompts_menu(),
        )
    else:  # prof_menu
        await context.bot.edit_message_text(
            f"Редактирование профиля: <b>{profile.display_name}</b>",
            chat_id=chat_id, message_id=admin_msg_id,
            parse_mode="HTML", reply_markup=profile_edit_menu(profile),
        )


# ── /admin command ────────────────────────────────────────────────────────────

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram import ReplyKeyboardRemove
    context.user_data[_K_STATE] = AdminState.AWAIT_PASSWORD
    context.user_data[_K_AUTHED] = False

    chat_id = update.effective_chat.id
    context.user_data[_K_ADMIN_TRIGGER_MSG] = update.effective_message.message_id
    await _delete_by_id(context, chat_id, _K_MENU_MSG)

    rm = await update.effective_message.chat.send_message(".", reply_markup=ReplyKeyboardRemove())
    await rm.delete()
    sent = await update.effective_message.chat.send_message(
        "Введи пароль администратора:",
        reply_markup=cancel_auth_button(),
    )
    context.user_data[_K_PROMPT_ID] = sent.message_id


# ── Text message handler ──────────────────────────────────────────────────────

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.user_data.get(_K_STATE, AdminState.IDLE)
    text = (update.message.text or "").strip()
    chat_id = update.message.chat.id
    admin_msg_id = context.user_data.get(_K_ADMIN_MENU_MSG)

    async def edit_admin(content: str, **kwargs) -> None:
        if admin_msg_id:
            await context.bot.edit_message_text(
                content, chat_id=chat_id, message_id=admin_msg_id, **kwargs
            )

    # ── Password ──────────────────────────────────────────────────────────────
    if state == AdminState.AWAIT_PASSWORD:
        prompt_id = context.user_data.pop(_K_PROMPT_ID, None)
        await _try_delete(update.message)
        if prompt_id:
            try:
                await context.bot.delete_message(chat_id, prompt_id)
            except Exception:
                pass

        if text == ADMIN_PASSWORD:
            context.user_data[_K_AUTHED] = True
            context.user_data[_K_STATE] = AdminState.MENU
            msg = await update.message.chat.send_message(
                "Панель администратора:", reply_markup=admin_menu(),
            )
            context.user_data[_K_ADMIN_MENU_MSG] = msg.message_id
        else:
            sent = await update.message.chat.send_message(
                "Неверный пароль. Попробуй ещё раз:",
                reply_markup=cancel_auth_button(),
            )
            context.user_data[_K_PROMPT_ID] = sent.message_id

    # ── Add ToV name ──────────────────────────────────────────────────────────
    elif state == AdminState.AWAIT_TOV_NAME:
        await _try_delete(update.message)
        context.user_data[_K_TOV_NAME] = text
        context.user_data[_K_STATE] = AdminState.AWAIT_TOV_STYLE
        await edit_admin(
            f"Имя: <b>{text}</b>\n\nТеперь опиши стиль автора (2–5 предложений):",
            parse_mode="HTML", reply_markup=back_button(),
        )

    # ── Add ToV style ─────────────────────────────────────────────────────────
    elif state == AdminState.AWAIT_TOV_STYLE:
        await _try_delete(update.message)
        name = context.user_data.get(_K_TOV_NAME, "")
        try:
            profile = loader.create_profile(display_name=name, tone_description=text)
            context.user_data[_K_STATE] = AdminState.MENU
            await edit_admin(
                f"Профиль <b>{profile.display_name}</b> создан (id: <code>{profile.id}</code>).",
                parse_mode="HTML", reply_markup=admin_menu(),
            )
        except Exception as exc:
            await edit_admin(f"Ошибка создания профиля: {exc}", reply_markup=back_button())

    # ── Add example ───────────────────────────────────────────────────────────
    elif state == AdminState.AWAIT_EXAMPLE:
        await _try_delete(update.message)
        author_id = context.user_data.get(_K_AUTHOR)
        if not author_id:
            context.user_data[_K_STATE] = AdminState.MENU
            await edit_admin("Ошибка: автор не выбран.", reply_markup=admin_menu())
            return
        try:
            loader.add_example(author_id, text)
            context.user_data[_K_STATE] = AdminState.MENU
            await edit_admin("Пример добавлен.", reply_markup=admin_menu())
        except Exception as exc:
            await edit_admin(f"Ошибка: {exc}", reply_markup=back_button())

    # ── Add user ──────────────────────────────────────────────────────────────
    elif state == AdminState.AWAIT_ADD_USER:
        await _try_delete(update.message)
        try:
            uid = int(text)
            await db.add_user(uid)
            context.user_data[_K_STATE] = AdminState.MENU
            await edit_admin(
                f"Пользователь <code>{uid}</code> добавлен.",
                parse_mode="HTML", reply_markup=admin_menu(),
            )
        except ValueError:
            await edit_admin("Введи числовой Telegram user_id:", reply_markup=back_button())

    # ── Delete user ───────────────────────────────────────────────────────────
    elif state == AdminState.AWAIT_DEL_USER:
        await _try_delete(update.message)
        try:
            uid = int(text)
            await db.remove_user(uid)
            context.user_data[_K_STATE] = AdminState.MENU
            await edit_admin(
                f"Пользователь <code>{uid}</code> удалён.",
                parse_mode="HTML", reply_markup=admin_menu(),
            )
        except ValueError:
            await edit_admin("Введи числовой Telegram user_id:", reply_markup=back_button())

    # ── Edit profile field (text input) ───────────────────────────────────────
    elif state == AdminState.AWAIT_EDIT_TEXT:
        await _try_delete(update.message)
        field_name = context.user_data.get(_K_EDIT_FIELD, "")
        author_id  = context.user_data.get(_K_EDIT_PROFILE, "")
        field_path = _FIELD_PATH.get(field_name, "")
        field_type = _FIELD_TYPE.get(field_name, "text")
        back_to    = _FIELD_BACK.get(field_name, "prof_menu")

        try:
            if field_type == "int":
                value = int(text)
            elif field_type == "phrases":
                value = [p.strip() for p in text.split(",") if p.strip()]
            else:  # text, prompt
                value = text

            profile = loader.update_profile_field(author_id, field_path, value)
            context.user_data[_K_STATE] = AdminState.MENU
            await _show_back_menu(context, chat_id, admin_msg_id, profile, back_to)
        except ValueError as exc:
            await edit_admin(
                f"Неверный формат: {exc}\n\nПопробуй ещё раз:",
                reply_markup=text_field_buttons(),
            )
        except Exception as exc:
            await edit_admin(f"Ошибка сохранения: {exc}", reply_markup=text_field_buttons())


# ── Callback query handler ────────────────────────────────────────────────────

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts    = query.data.split(":")
    action   = parts[1] if len(parts) > 1 else ""
    chat_id  = query.message.chat.id
    admin_msg_id = context.user_data.get(_K_ADMIN_MENU_MSG)

    # ── cancel_auth — no auth required ────────────────────────────────────────
    if action == "cancel_auth":
        context.user_data[_K_STATE] = AdminState.IDLE
        context.user_data[_K_AUTHED] = False
        context.user_data.pop(_K_PROMPT_ID, None)
        await query.message.delete()
        await _delete_by_id(context, chat_id, _K_ADMIN_TRIGGER_MSG)
        msg = await query.message.chat.send_message("Главное меню:", reply_markup=main_menu())
        context.user_data[_K_MENU_MSG] = msg.message_id
        return

    if not context.user_data.get(_K_AUTHED, False):
        await query.edit_message_text("Сессия истекла. Введи /admin чтобы войти снова.")
        return

    # ── Navigation ────────────────────────────────────────────────────────────
    if action == "back":
        context.user_data[_K_STATE] = AdminState.MENU
        await query.edit_message_text("Панель администратора:", reply_markup=admin_menu())

    elif action == "exit":
        context.user_data[_K_STATE] = AdminState.IDLE
        context.user_data[_K_AUTHED] = False
        context.user_data.pop(_K_ADMIN_MENU_MSG, None)
        await query.message.delete()
        await _delete_by_id(context, chat_id, _K_ADMIN_TRIGGER_MSG)
        msg = await query.message.chat.send_message("Главное меню:", reply_markup=main_menu())
        context.user_data[_K_MENU_MSG] = msg.message_id

    # ── Profile editing — entry ───────────────────────────────────────────────
    elif action == "edit_profiles":
        profiles = loader.list_profiles()
        if not profiles:
            await query.edit_message_text("Нет профилей для редактирования.", reply_markup=back_button())
            return
        await query.edit_message_text(
            "Выбери профиль для редактирования:",
            reply_markup=profile_list_keyboard(profiles, "adm:ep_select"),
        )

    elif action == "ep_select":
        author_id = parts[2] if len(parts) > 2 else ""
        try:
            profile = loader.get_profile(author_id)
        except KeyError:
            await query.edit_message_text("Профиль не найден.", reply_markup=back_button())
            return
        context.user_data[_K_EDIT_PROFILE] = author_id
        context.user_data[_K_STATE] = AdminState.MENU
        await query.edit_message_text(
            f"Редактирование профиля: <b>{profile.display_name}</b>",
            parse_mode="HTML", reply_markup=profile_edit_menu(profile),
        )

    elif action == "ep_menu":
        author_id = context.user_data.get(_K_EDIT_PROFILE, "")
        try:
            profile = loader.get_profile(author_id)
        except KeyError:
            await query.edit_message_text("Профиль не найден.", reply_markup=back_button())
            return
        context.user_data[_K_STATE] = AdminState.MENU
        await query.edit_message_text(
            f"Редактирование профиля: <b>{profile.display_name}</b>",
            parse_mode="HTML", reply_markup=profile_edit_menu(profile),
        )

    elif action == "ep_struct":
        author_id = context.user_data.get(_K_EDIT_PROFILE, "")
        try:
            profile = loader.get_profile(author_id)
        except KeyError:
            await query.edit_message_text("Профиль не найден.", reply_markup=back_button())
            return
        await query.edit_message_text(
            f"Структура поста — <b>{profile.display_name}</b>:",
            parse_mode="HTML", reply_markup=post_structure_menu(profile),
        )

    elif action == "ep_prompts":
        author_id = context.user_data.get(_K_EDIT_PROFILE, "")
        try:
            profile = loader.get_profile(author_id)
        except KeyError:
            await query.edit_message_text("Профиль не найден.", reply_markup=back_button())
            return
        await query.edit_message_text(
            f"Промпты — <b>{profile.display_name}</b>:",
            parse_mode="HTML", reply_markup=prompts_menu(),
        )

    # ── Profile editing — open field editor ──────────────────────────────────
    elif action in ("ep_pf", "ep_sf", "ep_sp"):
        field_name = parts[2] if len(parts) > 2 else ""
        author_id  = context.user_data.get(_K_EDIT_PROFILE, "")
        try:
            profile = loader.get_profile(author_id)
        except KeyError:
            await query.edit_message_text("Профиль не найден.", reply_markup=back_button())
            return
        context.user_data[_K_EDIT_FIELD] = field_name
        context.user_data[_K_STATE] = AdminState.AWAIT_EDIT_TEXT
        await _show_field_editor(context, chat_id, admin_msg_id, profile, field_name)

    # ── Profile editing — set bool ────────────────────────────────────────────
    elif action == "ep_set_bool":
        field_name = context.user_data.get(_K_EDIT_FIELD, "")
        author_id  = context.user_data.get(_K_EDIT_PROFILE, "")
        value      = (parts[2] == "true") if len(parts) > 2 else False
        field_path = _FIELD_PATH.get(field_name, "")
        back_to    = _FIELD_BACK.get(field_name, "prof_menu")
        try:
            profile = loader.update_profile_field(author_id, field_path, value)
            context.user_data[_K_STATE] = AdminState.MENU
            await _show_back_menu(context, chat_id, admin_msg_id, profile, back_to)
        except Exception as exc:
            await query.edit_message_text(f"Ошибка: {exc}", reply_markup=back_button())

    # ── Profile editing — set language ────────────────────────────────────────
    elif action == "ep_set_lang":
        author_id = context.user_data.get(_K_EDIT_PROFILE, "")
        value     = parts[2] if len(parts) > 2 else "ru"
        try:
            profile = loader.update_profile_field(author_id, "language", value)
            context.user_data[_K_STATE] = AdminState.MENU
            await _show_back_menu(context, chat_id, admin_msg_id, profile, "prof_menu")
        except Exception as exc:
            await query.edit_message_text(f"Ошибка: {exc}", reply_markup=back_button())

    # ── Profile editing — reset field to default ──────────────────────────────
    elif action == "ep_reset_field":
        field_name = context.user_data.get(_K_EDIT_FIELD, "")
        author_id  = context.user_data.get(_K_EDIT_PROFILE, "")
        field_path = _FIELD_PATH.get(field_name, "")
        back_to    = _FIELD_BACK.get(field_name, "prof_menu")
        try:
            profile = loader.reset_profile_field(author_id, field_path)
            context.user_data[_K_STATE] = AdminState.MENU
            await _show_back_menu(context, chat_id, admin_msg_id, profile, back_to)
        except Exception as exc:
            await query.edit_message_text(f"Ошибка сброса: {exc}", reply_markup=back_button())

    # ── Profile editing — back without saving ─────────────────────────────────
    elif action == "ep_back_field":
        field_name = context.user_data.get(_K_EDIT_FIELD, "")
        author_id  = context.user_data.get(_K_EDIT_PROFILE, "")
        back_to    = _FIELD_BACK.get(field_name, "prof_menu")
        context.user_data[_K_STATE] = AdminState.MENU
        try:
            profile = loader.get_profile(author_id)
            await _show_back_menu(context, chat_id, admin_msg_id, profile, back_to)
        except KeyError:
            await query.edit_message_text("Профиль не найден.", reply_markup=back_button())

    # ── ToV management ────────────────────────────────────────────────────────
    elif action == "add_tov":
        context.user_data[_K_STATE] = AdminState.AWAIT_TOV_NAME
        await query.edit_message_text(
            "Введи отображаемое имя нового профиля\n(например: «Алексей — аналитик»):",
            reply_markup=back_button(),
        )

    elif action == "del_tov":
        profiles = loader.list_profiles()
        if not profiles:
            await query.edit_message_text("Нет профилей для удаления.", reply_markup=back_button())
            return
        context.user_data[_K_STATE] = AdminState.SELECT_DELETE_TOV
        await query.edit_message_text(
            "Выбери профиль для удаления:",
            reply_markup=profile_list_keyboard(profiles, "adm:confirm_del_tov"),
        )

    elif action == "confirm_del_tov":
        author_id = parts[2] if len(parts) > 2 else ""
        try:
            loader.delete_profile(author_id)
            context.user_data[_K_STATE] = AdminState.MENU
            await query.edit_message_text(
                f"Профиль <code>{author_id}</code> удалён.",
                parse_mode="HTML", reply_markup=admin_menu(),
            )
        except Exception as exc:
            await query.edit_message_text(f"Ошибка: {exc}", reply_markup=back_button())

    # ── Example management ────────────────────────────────────────────────────
    elif action == "add_example":
        profiles = loader.list_profiles()
        if not profiles:
            await query.edit_message_text("Нет профилей.", reply_markup=back_button())
            return
        await query.edit_message_text(
            "Выбери профиль для добавления примера:",
            reply_markup=profile_list_keyboard(profiles, "adm:select_ex_author"),
        )

    elif action == "select_ex_author":
        author_id = parts[2] if len(parts) > 2 else ""
        context.user_data[_K_AUTHOR] = author_id
        context.user_data[_K_STATE]  = AdminState.AWAIT_EXAMPLE
        await query.edit_message_text(
            f"Отправь текст примера поста для профиля <code>{author_id}</code>:",
            parse_mode="HTML", reply_markup=back_button(),
        )

    elif action == "del_example":
        profiles = loader.list_profiles()
        if not profiles:
            await query.edit_message_text("Нет профилей.", reply_markup=back_button())
            return
        await query.edit_message_text(
            "Выбери профиль:", reply_markup=profile_list_keyboard(profiles, "adm:select_del_ex_author"),
        )

    elif action == "select_del_ex_author":
        author_id = parts[2] if len(parts) > 2 else ""
        try:
            profile = loader.get_profile(author_id)
        except KeyError:
            await query.edit_message_text("Профиль не найден.", reply_markup=back_button())
            return
        if not profile.examples:
            await query.edit_message_text("У этого профиля нет примеров.", reply_markup=back_button())
            return
        context.user_data[_K_STATE] = AdminState.SELECT_DEL_EXAMPLE
        await query.edit_message_text(
            "Выбери пример для удаления:",
            reply_markup=examples_keyboard(author_id, profile.examples),
        )

    elif action == "del_ex":
        author_id = parts[2] if len(parts) > 2 else ""
        try:
            idx = int(parts[3]) if len(parts) > 3 else -1
            loader.delete_example(author_id, idx)
            context.user_data[_K_STATE] = AdminState.MENU
            await query.edit_message_text("Пример удалён.", reply_markup=admin_menu())
        except Exception as exc:
            await query.edit_message_text(f"Ошибка: {exc}", reply_markup=back_button())

    # ── User (whitelist) management ───────────────────────────────────────────
    elif action == "add_user":
        context.user_data[_K_STATE] = AdminState.AWAIT_ADD_USER
        await query.edit_message_text(
            "Введи Telegram user_id пользователя (числовой):", reply_markup=back_button(),
        )

    elif action == "del_user":
        users = await db.list_users()
        if not users:
            await query.edit_message_text("Список пользователей пуст.", reply_markup=back_button())
            return
        lines = [f"<code>{u['user_id']}</code> — @{u['username'] or '—'}" for u in users]
        context.user_data[_K_STATE] = AdminState.AWAIT_DEL_USER
        await query.edit_message_text(
            "Пользователи:\n" + "\n".join(lines) + "\n\nВведи user_id для удаления:",
            parse_mode="HTML", reply_markup=back_button(),
        )

    elif action == "list_users":
        users = await db.list_users()
        if not users:
            await query.edit_message_text("Список пользователей пуст.", reply_markup=back_button())
            return
        lines = [
            f"<code>{u['user_id']}</code> — @{u['username'] or '—'} (добавлен {str(u['added_at'])[:10]})"
            for u in users
        ]
        await query.edit_message_text(
            "Пользователи:\n" + "\n".join(lines),
            parse_mode="HTML", reply_markup=back_button(),
        )
