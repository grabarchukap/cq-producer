# cq-producer — Граф знаний / Architecture Map

## Что делает проект

Telegram-бот «Мысль → Пост». Принимает голосовое сообщение или текст от авторизованного пользователя, прогоняет через цепочку из 5 AI-агентов и возвращает готовый пост в стиле выбранного автора (Tone of Voice). После генерации — интерактивная правка через 6-й агент.

---

## Стек

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.12+ |
| Telegram | python-telegram-bot 21 (async, polling / webhook) |
| LLM | Anthropic API — claude-sonnet-4-6 |
| STT | OpenAI Whisper API (whisper-1, язык ru) |
| БД | SQLite + aiosqlite (WAL mode) |
| Профили | JSON-файлы + Pydantic v2 |
| Конфиг | python-dotenv |

---

## Файловая карта

```
cq-producer/
│
├── main.py              # Точка входа: сборка PTB Application, polling/webhook
├── config.py            # Загрузка .env; _require() для обязательных переменных
├── orchestrator.py      # run_pipeline() и run_edit() — склеивает агентов
│
├── agents/
│   ├── stt.py           # Agent 1: transcribe(audio_bytes) → str  [Whisper API]
│   ├── expand.py        # Agent 2: expand(raw_text, profile) → draft
│   ├── tone.py          # Agent 3: apply_tone(draft, profile) → toned
│   ├── format.py        # Agent 4: format_post(toned, profile) → formatted
│   ├── qa.py            # Agent 5: qa_check(formatted, profile) → final_post
│   └── edit.py          # Agent 6: edit_post(post, request, profile) → new_post
│
├── bot/
│   ├── states.py        # enum UserState (IDLE/PROCESSING/EDITING), AdminState
│   ├── keyboards.py     # Все inline keyboards (tov_selection, post_actions, admin_menu…)
│   ├── handlers.py      # cmd_start, on_input, on_edit, on_post_callback, on_tov_selected
│   ├── admin.py         # cmd_admin, on_message (FSM), on_callback (inline buttons)
│   └── router.py        # route_text, route_voice, route_callback — центральный роутер
│
├── profiles/
│   ├── schema.py        # Pydantic: AuthorProfile, PostStructure, AgentPrompts
│   ├── loader.py        # load/cache/CRUD профилей; dict _cache в памяти
│   └── authors/
│       ├── _template.json   # Шаблон для create_profile()
│       └── *.json           # Профили авторов (techwriter, motivator, …)
│
├── storage/
│   ├── db.py            # init_db, is_allowed, add_user, remove_user, list_users, save_post
│   └── posts.db         # SQLite-файл, создаётся при первом запуске
│
├── utils/
│   ├── llm.py           # call_llm(system, user, max_tokens) → str
│   ├── retry.py         # @with_retry(max_attempts, base_delay) — exponential backoff
│   └── sanitize.py      # sanitize(text): strip HTML + LLM delimiters, cap 4000 chars
│
├── .env                 # Секреты — не коммитить
├── .env.example         # Шаблон переменных
├── requirements.txt
├── setup.bat            # Создаёт .venv и устанавливает зависимости (Windows)
└── start.bat            # Запускает main.py через .venv (Windows)
```

---

## Пайплайн данных

```
ВХОД
 ├─ Голосовое → [Agent 1: STT / Whisper] → транскрипт (str)
 └─ Текст     → [sanitize()]             → очищенный текст (str)
                        │
               [Agent 2: Expand]
               сырой текст → связный черновик
                        │
               [Agent 3: Tone]
               черновик + tone_description + forbidden_phrases + examples
               → текст в стиле автора
                        │
               [Agent 4: Format]
               + post_structure (длина, абзацы, emoji, hashtags)
               → отформатированный пост
                        │
               [Agent 5: QA]
               орфография, стиль, запрещённые фразы, длина
               → финальный пост (str)
                        │
                    ВЫХОД → пользователю

Редактирование (отдельный путь):
  текущий пост + запрос пользователя → [Agent 6: Edit] → обновлённый пост
```

Оркестратор (`orchestrator.py`) управляет пайплайном и не знает о Telegram.
Агенты не знают друг о друге — только вход и выход.
Все LLM-вызовы через `utils/llm.py` → `@with_retry` (3 попытки, backoff 0.5→1→2s).

---

## FSM состояний

### Пользователь (`context.user_data["user_state"]`)

```
         /start
           │
         IDLE ◄──────────────────────────────┐
           │                                  │
    текст/голос                          кнопка «Готово»
           │                                  │
      PROCESSING ──── (finally) ────────► IDLE
                                              │
                                    кнопка «Редактировать»
                                              │
                                          EDITING
                                              │
                                   текст/голос с правкой
                                              │
                                       [Agent 6: Edit]
```

`/start` всегда сбрасывает состояние в `IDLE` и очищает `current_post`.

### Админ (`context.user_data["admin_state"]`)

```
/admin
  │
AWAIT_PASSWORD ──(верный пароль)──► MENU
                                      │
              ┌───────────────────────┼──────────────────────┐
              │                       │                       │
       Добавить ToV             Управление               Управление
       AWAIT_TOV_NAME           примерами                whitelist
       AWAIT_TOV_STYLE          AWAIT_EXAMPLE            AWAIT_ADD_USER
                                SELECT_DEL_EXAMPLE       AWAIT_DEL_USER
```

Все admin-состояния хранятся отдельно от user-состояний в `context.user_data`.
Роутер проверяет admin_state первым — он имеет приоритет над user_state.

---

## Профиль автора (AuthorProfile)

```json
{
  "id": "techwriter",           // slug [a-z0-9_], макс. 32 символа
  "display_name": "...",        // отображается в боте
  "language": "ru",
  "tone_description": "...",    // описание стиля — идёт в Agent 3, 5, 6
  "forbidden_phrases": [],      // стоп-слова — идут в Agent 3, 5
  "post_structure": {           // правила платформы — идут в Agent 4, 5
    "max_length_chars": 1500,
    "paragraphs": {"min": 2, "max": 5},
    "use_emoji": false,
    "use_hashtags": false,
    "hashtag_style": "",
    "formatting_hints": ""
  },
  "agent_prompts": {            // скелеты системных промптов
    "expand": "...",
    "tone": "...",
    "format": "...",
    "qa": "...",
    "edit": "..."
  },
  "examples": [{"post": "..."}] // примеры постов автора — идут в Agent 3
}
```

Профили хранятся в `profiles/authors/*.json`, загружаются один раз при старте
в in-memory словарь `_cache`. Кэш инвалидируется при CRUD-операциях.

---

## Роутинг сообщений

```
Входящее сообщение
        │
   route_text / route_voice / route_callback
        │
        ├─ admin_state активен (не IDLE/MENU)?
        │         └─► admin.on_message()
        │
        ├─ user_state == EDITING?
        │         └─► handlers.on_edit()
        │
        ├─ user_state == PROCESSING?
        │         └─► «подожди» и выход
        │
        └─► handlers.on_input()
```

Callback prefix routing:
- `tov:*`  → `handlers.on_tov_selected()`
- `post:*` → `handlers.on_post_callback()`
- `adm:*`  → `admin.on_callback()`

---

## Контроль доступа

- **Whitelist** — таблица `whitelist` в SQLite. `@require_auth` на всех user-хендлерах.
- **Админка** — `/admin` + пароль из `.env`. Сессия живёт до `adm:exit` или перезапуска.
- **Sanitize** — `utils/sanitize.py` чистит HTML-теги и LLM-разделители на всём входящем тексте.
- **Audio limit** — проверка размера ≤ 25 МБ до вызова Whisper API.

---

## Переменные окружения

| Переменная | Обязательна | Описание |
|-----------|------------|---------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Токен бота |
| `ANTHROPIC_API_KEY` | ✅ | Ключ Anthropic (Claude) |
| `ADMIN_PASSWORD` | ✅ | Пароль /admin |
| `OPENAI_API_KEY` | ⚠️ опционально | Ключ OpenAI (без него нет STT) |
| `DEV_MODE` | — | `true` → polling, `false` → webhook |
| `WEBHOOK_URL` | если не DEV | Публичный URL |
| `WEBHOOK_PORT` | — | По умолчанию 8443 |
| `WEBHOOK_SECRET_TOKEN` | — | Рекомендуется для webhook |
| `CLAUDE_MODEL` | — | По умолчанию claude-sonnet-4-6 |

---

## Ключевые архитектурные решения (после рефакторинга)

- `concurrent_updates=False` — обновления обрабатываются последовательно, исключает race conditions
- `on_edit` защищён PROCESSING lock (аналогично `on_input`)
- `transcribe_audio()` вынесена в `orchestrator.py` — bot-слой не импортирует агентов напрямую
- Проверка размера файла в `stt.py` выполняется ДО `@with_retry`
- `on_callback` в admin проверяет `_K_AUTHED` перед любым действием
- `route_voice` проверяет `admin_state` наравне с `route_text`

---

## БД (SQLite)

**`whitelist`** — контроль доступа:
```sql
user_id  INTEGER PRIMARY KEY
username TEXT
added_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

**`posts`** — история постов (запись заглушена, таблица создаётся):
```sql
id         INTEGER PRIMARY KEY AUTOINCREMENT
user_id    INTEGER
author_id  TEXT
raw_input  TEXT
final_post TEXT
created_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

WAL mode включён при инициализации — читатели не блокируют писателей.
Каждая операция с БД открывает новое соединение (aiosqlite context manager).
