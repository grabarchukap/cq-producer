import asyncio
import logging
from datetime import datetime
from pathlib import Path

from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_DRIVE_FOLDER_ID, GOOGLE_TOKEN_FILE
from utils.llm import call_llm

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

_DRAFT_PROMPT_PATH = Path(__file__).parent / "draft_prompt.txt"


def load_draft_prompt() -> str:
    return _DRAFT_PROMPT_PATH.read_text(encoding="utf-8").strip()


def save_draft_prompt(text: str) -> None:
    _DRAFT_PROMPT_PATH.write_text(text.strip(), encoding="utf-8")


def _build_services():
    """Build authenticated Google Docs + Drive clients using OAuth2 token."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_path = Path(GOOGLE_TOKEN_FILE)
    if not token_path.exists():
        raise FileNotFoundError(
            f"Google token not found: {GOOGLE_TOKEN_FILE}. "
            "Run auth_google.py first to authorize."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")

    docs = build("docs", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)
    return docs, drive


def _format_qa(answers: list[dict]) -> str:
    lines = []
    for i, item in enumerate(answers, 1):
        q = item.get("question", f"Вопрос {i}")
        a = item.get("answer") or "(без ответа)"
        lines.append(f"Вопрос {i}: {q}\nОтвет: {a}")
    return "\n\n".join(lines)


def _create_doc_sync(
    docs_service,
    drive_service,
    title: str,
    qa_text: str,
    draft_text: str,
) -> str:
    """Create Google Doc in the target folder and return its URL."""
    file_metadata = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [GOOGLE_DRIVE_FOLDER_ID],
    }
    file = drive_service.files().create(
        body=file_metadata, fields="id"
    ).execute()
    doc_id = file["id"]

    separator = "─" * 50
    full_text = (
        f"{title}\n\n"
        f"{separator}\n"
        f"ИНТЕРВЬЮ\n"
        f"{separator}\n\n"
        f"{qa_text}\n\n"
        f"{separator}\n"
        f"ЧЕРНОВИК\n"
        f"{separator}\n\n"
        f"{draft_text}\n"
    )

    requests = [
        {
            "insertText": {
                "location": {"index": 1},
                "text": full_text,
            }
        },
        {
            "updateParagraphStyle": {
                "range": {"startIndex": 1, "endIndex": len(title) + 1},
                "paragraphStyle": {"namedStyleType": "HEADING_1"},
                "fields": "namedStyleType",
            }
        },
    ]
    docs_service.documents().batchUpdate(
        documentId=doc_id, body={"requests": requests}
    ).execute()

    return f"https://docs.google.com/document/d/{doc_id}/edit"


async def export_case(
    answers: list[dict],
    username: str | None,
    created_at: str | None = None,
) -> str:
    """Generate Claude draft + create Google Doc. Returns doc URL."""
    if not GOOGLE_DRIVE_FOLDER_ID:
        raise ValueError("GOOGLE_DRIVE_FOLDER_ID не задан в .env")

    qa_text = _format_qa(answers)

    draft_text = await call_llm(
        system_prompt=load_draft_prompt(),
        user_content=f"Интервью:\n\n{qa_text}",
        max_tokens=1500,
    )

    first_answer = (answers[0].get("answer") or "").strip() if answers else ""
    date_str = datetime.now().strftime("%d.%m.%Y")
    author_part = f"@{username}" if username else "пользователь"
    title = f"Кейс: {first_answer or author_part} — {date_str}"

    loop = asyncio.get_event_loop()
    docs_service, drive_service = await loop.run_in_executor(None, _build_services)
    url = await loop.run_in_executor(
        None, _create_doc_sync, docs_service, drive_service, title, qa_text, draft_text
    )

    logger.info("Case doc created: %s", url)
    return url
