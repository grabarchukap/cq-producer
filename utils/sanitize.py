import re
from config import MAX_INPUT_CHARS

_HTML_TAG_RE = re.compile(r"<[^>]+>")

# LLM role delimiters that could be used for prompt injection
_LLM_DELIMITER_RE = re.compile(
    r"<\s*/?\s*(system|human|assistant|user|context|instruction|prompt)\s*>",
    re.IGNORECASE,
)

# Obvious prompt injection phrases
_INJECTION_RE = re.compile(
    r"(ignore\s+(previous|all|prior)\s+instructions?|disregard\s+all|"
    r"jailbreak|system\s+prompt\s*:)",
    re.IGNORECASE,
)


def sanitize(text: str) -> str:
    """Strip HTML tags, LLM delimiters, and cap length at MAX_INPUT_CHARS."""
    if not text:
        return ""
    text = _HTML_TAG_RE.sub("", text)
    text = _LLM_DELIMITER_RE.sub("", text)
    text = _INJECTION_RE.sub("[удалено]", text)
    text = text.strip()
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]
    return text
