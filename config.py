import os
from dotenv import load_dotenv

load_dotenv()


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
WHISPER_MODEL: str = os.environ.get("WHISPER_MODEL", "small").strip()

GOOGLE_CREDENTIALS_FILE: str = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json").strip()
GOOGLE_TOKEN_FILE: str = os.environ.get("GOOGLE_TOKEN_FILE", "token.json").strip()
GOOGLE_DRIVE_FOLDER_ID: str = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()

MAX_INPUT_CHARS: int = 4_000
MAX_AUDIO_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
