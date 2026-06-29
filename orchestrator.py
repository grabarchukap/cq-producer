import logging
from collections.abc import Awaitable, Callable

from profiles.loader import get_profile
from utils.sanitize import sanitize
from agents import stt
from agents import expand
from agents import tone
from agents import format as fmt
from agents import qa
from agents import edit as edit_agent

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Awaitable[None]]


async def _notify(cb: ProgressCallback | None, msg: str) -> None:
    if cb:
        try:
            await cb(msg)
        except Exception as exc:
            logger.warning("on_progress callback failed: %s", exc)


async def run_pipeline(
    audio_bytes: bytes | None,
    text: str | None,
    author_id: str,
    on_progress: ProgressCallback | None = None,
) -> str:
    """Run agents 1–5 and return the final post.

    Raises ValueError with a user-friendly message on recoverable failures.
    """
    profile = get_profile(author_id)

    # Step 1 — STT or sanitize
    if audio_bytes:
        await _notify(on_progress, "🎙 Расшифровываю аудио...")
        raw_input = await stt.transcribe(audio_bytes)
    else:
        await _notify(on_progress, "📝 Обрабатываю текст...")
        raw_input = sanitize(text or "")
        if not raw_input:
            raise ValueError("Текст не может быть пустым.")

    # Step 2 — Expand
    await _notify(on_progress, "✍️ Разворачиваю мысль...")
    draft = await expand.expand(raw_input, profile)

    # Step 3 — Tone of Voice
    await _notify(on_progress, "🎨 Применяю стиль автора...")
    toned = await tone.apply_tone(draft, profile)

    # Step 4 — Format
    await _notify(on_progress, "📐 Форматирую пост...")
    formatted = await fmt.format_post(toned, profile)

    # Step 5 — QA
    await _notify(on_progress, "✅ Проверяю качество...")
    final_post = await qa.qa_check(formatted, profile)

    # Post history is disabled by default.
    # To enable: uncomment and pass user_id as a parameter.
    # await storage.db.save_post(user_id, author_id, raw_input, final_post)

    return final_post


async def run_edit(
    current_post: str,
    user_request: str,
    author_id: str,
) -> str:
    """Run only agent 6 for a targeted edit (no full pipeline)."""
    profile = get_profile(author_id)
    return await edit_agent.edit_post(current_post, user_request, profile)


async def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio bytes to text. Thin wrapper so handlers don't import agents directly."""
    return await stt.transcribe(audio_bytes)
