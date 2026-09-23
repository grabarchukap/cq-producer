import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Directory holding the code. Everything here is read-only when running in Docker.
CODE_DIR: Path = Path(__file__).parent


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise RuntimeError(f"Required environment variable '{name}' is not set")
    return val


DEV_MODE: bool = os.environ.get("DEV_MODE", "false").lower() == "true"

TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")
ADMIN_PASSWORD: str = _require("ADMIN_PASSWORD")
WEBHOOK_URL: str = "" if DEV_MODE else _require("WEBHOOK_URL")

WEBHOOK_PORT: int = int(os.environ.get("WEBHOOK_PORT", "8443"))
WEBHOOK_SECRET_TOKEN: str = os.environ.get("WEBHOOK_SECRET_TOKEN", "").strip()

CLAUDE_MODEL: str = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6").strip()

# Groq speech-to-text (voice messages). Without a key voice input is disabled.
GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_STT_MODEL: str = os.environ.get("GROQ_STT_MODEL", "whisper-large-v3").strip()

# ── Writable data ────────────────────────────────────────────────────────────
# DATA_DIR keeps everything the bot writes outside the code directory (needed in
# Docker, where the code is mounted read-only). Unset → the original layout,
# with each file next to the module that owns it.
_data_dir_env: str = os.environ.get("DATA_DIR", "").strip()
DATA_DIR: Path | None = Path(_data_dir_env) if _data_dir_env else None

DB_PATH: str = str(DATA_DIR / "posts.db" if DATA_DIR else CODE_DIR / "storage" / "posts.db")
AUTHORS_DIR: Path = DATA_DIR / "authors" if DATA_DIR else CODE_DIR / "profiles" / "authors"
QUESTIONS_PATH: Path = (
    DATA_DIR / "questions.json" if DATA_DIR else CODE_DIR / "case_questions" / "questions.json"
)
DRAFT_PROMPT_PATH: Path = (
    DATA_DIR / "draft_prompt.txt" if DATA_DIR else CODE_DIR / "agents" / "draft_prompt.txt"
)

# Profile template — always read from the code, never written to
TEMPLATE_PATH: Path = CODE_DIR / "profiles" / "authors" / "_template.json"

GOOGLE_CREDENTIALS_FILE: str = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json").strip()
GOOGLE_TOKEN_FILE: str = os.environ.get("GOOGLE_TOKEN_FILE", "").strip() or str(
    DATA_DIR / "token.json" if DATA_DIR else "token.json"
)
GOOGLE_DRIVE_FOLDER_ID: str = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()

MAX_INPUT_CHARS: int = 4_000
MAX_AUDIO_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
