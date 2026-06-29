import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# HTTP status codes that should trigger a retry
_RETRYABLE_CODES = {429, 500, 502, 503, 504}


def with_retry(max_attempts: int = 3, base_delay: float = 0.5):
    """Decorator: retry an async function with exponential backoff.

    4xx errors (except 429) are NOT retried — they indicate a permanent failure.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            delay = base_delay
            last_exc: Exception

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    status = (
                        getattr(exc, "status_code", None)
                        or getattr(exc, "status", None)
                    )
                    # Don't retry permanent client errors
                    if status is not None and 400 <= status < 500 and status != 429:
                        raise
                    if attempt < max_attempts - 1:
                        logger.warning(
                            "%s attempt %d/%d failed: %s — retrying in %.1fs",
                            func.__name__,
                            attempt + 1,
                            max_attempts,
                            exc,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        delay *= 2

            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
