import logging
from groq import APIError, AsyncGroq, RateLimitError
from config import GROQ_API_KEY, GROQ_STT_MODEL, MAX_AUDIO_SIZE_BYTES
from utils.retry import with_retry

logger = logging.getLogger(__name__)

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=GROQ_API_KEY)
    return _client


async def transcribe(audio_bytes: bytes) -> str:
    """Transcribe OGG audio bytes to Russian text via the Groq Whisper API."""
    if not GROQ_API_KEY:
        raise ValueError("Распознавание голосовых не настроено — отправь текстом.")

    size_mb = len(audio_bytes) / 1024 / 1024
    if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
        raise ValueError(
            f"Аудиофайл слишком большой ({size_mb:.1f} МБ). Максимум 25 МБ."
        )

    # Every API failure becomes a ValueError — callers show its text to the user,
    # so a raw Groq error body must never reach the chat.
    try:
        text = (await _transcribe_api(audio_bytes)).strip()
    except RateLimitError:
        logger.warning("Groq rate limit hit while transcribing %.1f MB", size_mb)
        raise ValueError(
            "Лимит распознавания голосовых исчерпан — отправь текстом или попробуй позже."
        )
    except APIError as exc:
        logger.error("Groq transcription failed: %s", exc)
        raise ValueError(
            "Не удалось распознать голосовое — попробуй ещё раз или отправь текстом."
        )

    if not text:
        raise ValueError(
            "Не удалось распознать речь — попробуй ещё раз или отправь текстом."
        )
    return text


# One retry only: it rides out a short burst, but when the daily free-plan quota
# is gone there is nothing to wait for.
@with_retry(max_attempts=2, base_delay=0.5)
async def _transcribe_api(audio_bytes: bytes) -> str:
    result = await _get_client().audio.transcriptions.create(
        file=("voice.ogg", audio_bytes),
        model=GROQ_STT_MODEL,
        language="ru",
        response_format="text",
    )
    # response_format="text" yields a plain string; guard against the object form
    return result if isinstance(result, str) else getattr(result, "text", "")
