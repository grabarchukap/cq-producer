import asyncio
import logging
import os
import tempfile
from faster_whisper import WhisperModel
from config import WHISPER_MODEL, MAX_AUDIO_SIZE_BYTES

logger = logging.getLogger(__name__)

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        logger.info("Loading Whisper model '%s'...", WHISPER_MODEL)
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")
    return _model


async def transcribe(audio_bytes: bytes) -> str:
    """Transcribe OGG audio bytes to Russian text using faster-whisper locally."""
    size_mb = len(audio_bytes) / 1024 / 1024
    if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
        raise ValueError(
            f"Аудиофайл слишком большой ({size_mb:.1f} МБ). Максимум 25 МБ."
        )
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _transcribe_sync, audio_bytes)


def _transcribe_sync(audio_bytes: bytes) -> str:
    """Run faster-whisper synchronously (called from executor thread)."""
    model = _get_model()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        segments, _info = model.transcribe(tmp_path, language="ru", beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        os.unlink(tmp_path)
    if not text:
        raise ValueError(
            "Не удалось распознать речь — попробуй ещё раз или отправь текстом."
        )
    return text
