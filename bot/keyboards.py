from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from profiles.schema import AuthorProfile

# ---------------------------------------------------------------------------
# Main menu — persistent reply keyboard
# Labels are used as routing keys in router.py — keep in sync
# ---------------------------------------------------------------------------

BTN_NEW_POST = "✍️ Создать новый пост"
BTN_CASE     = "📋 Я хочу поделиться кейсом"
BTN_ADMIN    = "⚙️ Админка"


def main_menu() -> ReplyKeyboardMarkup:
    """Bottom keyboard that acts as the app's home screen."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_NEW_POST)],
            [KeyboardButton(BTN_CASE)],
            [KeyboardButton(BTN_ADMIN)],
        ],
        resize_keyboard=True,
    )


# ---------------------------------------------------------------------------
# Inline keyboards
# ---------------------------------------------------------------------------

def tov_selection(profiles: list[AuthorProfile]) -> InlineKeyboardMarkup:
    """Keyboard for choosing a Tone of Voice profile."""
    rows = [
        [InlineKeyboardButton(p.display_name, callback_data=f"tov:{p.id}")]
        for p in profiles
    ]
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="tov:back")])
    return InlineKeyboardMarkup(rows)


def cancel_auth_button() -> InlineKeyboardMarkup:
    """Back button shown on the admin password prompt (no auth required)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад", callback_data="adm:cancel_auth")]
    ])


def post_actions() -> InlineKeyboardMarkup:
    """Buttons shown right after post generation."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Редактировать", callback_data="post:edit"),
        InlineKeyboardButton("✅ Готово", callback_data="post:done"),
    ]])


def edit_actions() -> InlineKeyboardMarkup:
    """Buttons shown after each edit iteration."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Ещё правка", callback_data="post:edit"),
        InlineKeyboardButton("✅ Готово", callback_data="post:done"),
    ]])


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Редактировать профиль", callback_data="adm:edit_profiles")],
        [InlineKeyboardButton("➕ Добавить ToV",          callback_data="adm:add_tov")],
        [InlineKeyboardButton("🗑 Удалить ToV",           callback_data="adm:del_tov")],
        [InlineKeyboardButton("📝 Добавить пример",       callback_data="adm:add_example")],
        [InlineKeyboardButton("❌ Удалить пример",        callback_data="adm:del_example")],
        [InlineKeyboardButton("👤 Добавить пользователя", callback_data="adm:add_user")],
        [InlineKeyboardButton("🚫 Удалить пользователя",  callback_data="adm:del_user")],
        [InlineKeyboardButton("📋 Список пользователей",  callback_data="adm:list_users")],
        [InlineKeyboardButton("🚪 Выйти из админки",      callback_data="adm:exit")],
    ])


def profile_edit_menu(profile: "AuthorProfile") -> InlineKeyboardMarkup:
    """Card for editing a single profile's settings."""
    ps = profile.post_structure
    lang_label = "🇷🇺 RU" if profile.language == "ru" else "🇬🇧 EN"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✏️ Название: {profile.display_name[:22]}", callback_data="adm:ep_pf:display_name")],
        [InlineKeyboardButton("📝 Описание стиля",                         callback_data="adm:ep_pf:tone_description")],
        [InlineKeyboardButton(f"🌐 Язык: {lang_label}",                    callback_data="adm:ep_pf:language")],
        [InlineKeyboardButton("🚫 Запрещённые фразы",                      callback_data="adm:ep_pf:forbidden_phrases")],
        [InlineKeyboardButton("📐 Структура поста →",                      callback_data="adm:ep_struct")],
        [InlineKeyboardButton("🤖 Промпты агентов →",                      callback_data="adm:ep_prompts")],
        [InlineKeyboardButton("◀️ К списку профилей",                      callback_data="adm:edit_profiles")],
    ])


def post_structure_menu(profile: "AuthorProfile") -> InlineKeyboardMarkup:
    """Submenu for editing post_structure fields."""
    ps = profile.post_structure
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📏 Макс. символов: {ps.max_length_chars}",                     callback_data="adm:ep_sf:max_length_chars")],
        [InlineKeyboardButton(f"📄 Мин. абзацев: {ps.paragraphs.get('min', 2)}",              callback_data="adm:ep_sf:paragraphs_min")],
        [InlineKeyboardButton(f"📄 Макс. абзацев: {ps.paragraphs.get('max', 5)}",             callback_data="adm:ep_sf:paragraphs_max")],
        [InlineKeyboardButton(f"😊 Эмодзи: {'✅ вкл' if ps.use_emoji else '❌ выкл'}",        callback_data="adm:ep_sf:use_emoji")],
        [InlineKeyboardButton(f"#️⃣ Хэштеги: {'✅ вкл' if ps.use_hashtags else '❌ выкл'}",   callback_data="adm:ep_sf:use_hashtags")],
        [InlineKeyboardButton("🏷️ Стиль хэштегов",                                            callback_data="adm:ep_sf:hashtag_style")],
        [InlineKeyboardButton("💡 Подсказки форматирования",                                   callback_data="adm:ep_sf:formatting_hints")],
        [InlineKeyboardButton("◀️ Назад",                                                      callback_data="adm:ep_menu")],
    ])


def prompts_menu() -> InlineKeyboardMarkup:
    """Submenu for selecting which agent prompt to edit."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1️⃣ Expand — черновик из транскрипта", callback_data="adm:ep_sp:expand")],
        [InlineKeyboardButton("2️⃣ Tone — стиль автора",              callback_data="adm:ep_sp:tone")],
        [InlineKeyboardButton("3️⃣ Format — форматирование",          callback_data="adm:ep_sp:format")],
        [InlineKeyboardButton("4️⃣ QA — контроль качества",           callback_data="adm:ep_sp:qa")],
        [InlineKeyboardButton("5️⃣ Edit — правки по запросу",         callback_data="adm:ep_sp:edit")],
        [InlineKeyboardButton("◀️ Назад",                             callback_data="adm:ep_menu")],
    ])


def text_field_buttons() -> InlineKeyboardMarkup:
    """Buttons below a text/int/prompt field editor."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Сброс к дефолту", callback_data="adm:ep_reset_field"),
        InlineKeyboardButton("◀️ Назад",            callback_data="adm:ep_back_field"),
    ]])


def bool_field_buttons(current: bool) -> InlineKeyboardMarkup:
    """Buttons for a boolean field with current state highlighted."""
    yes = "✅ Да  ←" if current else "✅ Да"
    no  = "❌ Нет ←" if not current else "❌ Нет"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(yes, callback_data="adm:ep_set_bool:true"),
         InlineKeyboardButton(no,  callback_data="adm:ep_set_bool:false")],
        [InlineKeyboardButton("🔄 Сброс к дефолту", callback_data="adm:ep_reset_field"),
         InlineKeyboardButton("◀️ Назад",            callback_data="adm:ep_back_field")],
    ])


def lang_field_buttons(current: str) -> InlineKeyboardMarkup:
    """Buttons for language selection."""
    ru = "🇷🇺 RU ←" if current == "ru" else "🇷🇺 RU"
    en = "🇬🇧 EN ←" if current == "en" else "🇬🇧 EN"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(ru, callback_data="adm:ep_set_lang:ru"),
         InlineKeyboardButton(en, callback_data="adm:ep_set_lang:en")],
        [InlineKeyboardButton("◀️ Назад", callback_data="adm:ep_back_field")],
    ])


def profile_list_keyboard(
    profiles: list[AuthorProfile], callback_prefix: str
) -> InlineKeyboardMarkup:
    """Generic single-column profile selector."""
    rows = [
        [InlineKeyboardButton(p.display_name, callback_data=f"{callback_prefix}:{p.id}")]
        for p in profiles
    ]
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="adm:back")])
    return InlineKeyboardMarkup(rows)


def examples_keyboard(author_id: str, examples: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard for picking an example to delete."""
    rows = []
    for i, ex in enumerate(examples):
        preview = ex.get("post", "")[:40].replace("\n", " ")
        rows.append([InlineKeyboardButton(
            f"{i + 1}. {preview}…",
            callback_data=f"adm:del_ex:{author_id}:{i}",
        )])
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="adm:back")])
    return InlineKeyboardMarkup(rows)


def back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад в меню", callback_data="adm:back")]
    ])
