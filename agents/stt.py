import io
import logging
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, MAX_AUDIO_SIZE_BYTES
from utils.retry import with_retry

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if not OPENAI_API_KEY:
        raise ValueError(
            "Расшифровка голоса недоступна — OPENAI_API_KEY не задан."
        )
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


async def transcribe(audio_bytes: bytes) -> str:
    """Transcribe OGG audio bytes to Russian text via Whisper API."""
    size_mb = len(audio_bytes) / 1024 / 1024
    if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
        raise ValueError(
            f"Аудиофайл слишком большой ({size_mb:.1f} МБ). Максимум 25 МБ."
        )
    return await _transcribe_api(audio_bytes)


@with_retry(max_attempts=3, base_delay=0.5)
async def _transcribe_api(audio_bytes: bytes) -> str:
    """Internal: call Whisper API with retry (size already validated)."""
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.ogg"

    result = await _get_client().audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="ru",
    )

    text = (result.text or "").strip()
    if not text:
        raise ValueError(
            "Не удалось распознать речь — попробуй ещё раз или отправь текстом."
        )
    return text
