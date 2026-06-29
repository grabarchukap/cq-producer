import logging
from anthropic import AsyncAnthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from utils.retry import with_retry

logger = logging.getLogger(__name__)

# Hard cap on content sent to Claude (separate from user-facing input limit)
_MAX_CONTENT_CHARS = 8_000

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


@with_retry(max_attempts=3, base_delay=0.5)
async def call_llm(
    system_prompt: str,
    user_content: str,
    max_tokens: int,
    model: str = CLAUDE_MODEL,
) -> str:
    """Call Claude and return response text. Raises ValueError on empty response."""
    if len(user_content) > _MAX_CONTENT_CHARS:
        logger.warning("LLM user_content truncated from %d to %d chars", len(user_content), _MAX_CONTENT_CHARS)
        user_content = user_content[:_MAX_CONTENT_CHARS]

    message = await get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    if not message.content:
        raise ValueError("Empty response from LLM")

    text = message.content[0].text.strip()
    if not text:
        raise ValueError("Empty text in LLM response")

    return text
