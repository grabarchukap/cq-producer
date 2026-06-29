import json
import logging
import re
import time
from pathlib import Path
from pydantic import ValidationError
from profiles.schema import AuthorProfile

logger = logging.getLogger(__name__)

_AUTHORS_DIR = Path(__file__).parent / "authors"
_cache: dict[str, AuthorProfile] = {}

# Cyrillic → Latin transliteration table for slug generation
_TRANSLIT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _load_all() -> dict[str, AuthorProfile]:
    profiles: dict[str, AuthorProfile] = {}
    for path in sorted(_AUTHORS_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            profile = AuthorProfile.model_validate(data)
            profiles[profile.id] = profile
        except Exception as exc:
            logger.error("Failed to load profile '%s': %s", path.name, exc)
    return profiles


def load_profiles() -> None:
    """Load all profiles from disk into the in-memory cache."""
    global _cache
    _cache = _load_all()
    logger.info("Loaded %d author profile(s)", len(_cache))


def invalidate_cache() -> None:
    """Force a full reload from disk."""
    global _cache
    _cache = _load_all()


def get_profile(author_id: str) -> AuthorProfile:
    if author_id not in _cache:
        raise KeyError(f"Profile '{author_id}' not found")
    return _cache[author_id]


def list_profiles() -> list[AuthorProfile]:
    return list(_cache.values())


def _slug(name: str) -> str:
    """Generate a [a-z0-9_] slug from a display name (handles Cyrillic)."""
    s = name.lower()
    s = "".join(_TRANSLIT.get(c, c) for c in s)
    s = re.sub(r"[^a-z0-9_\s]", "", s)
    s = re.sub(r"\s+", "_", s.strip())
    s = s[:32]
    return s if s else f"author_{int(time.time())}"


def create_profile(display_name: str, tone_description: str) -> AuthorProfile:
    """Create a new profile from the template and save it to disk."""
    template_path = _AUTHORS_DIR / "_template.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))

    base_id = _slug(display_name)
    author_id = base_id
    counter = 1
    while (_AUTHORS_DIR / f"{author_id}.json").exists() or author_id in _cache:
        author_id = f"{base_id}_{counter}"
        counter += 1

    template["id"] = author_id
    template["display_name"] = display_name
    template["tone_description"] = tone_description
    template["examples"] = []

    profile = AuthorProfile.model_validate(template)
    path = _AUTHORS_DIR / f"{author_id}.json"
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    _cache[author_id] = profile
    logger.info("Created profile '%s'", author_id)
    return profile


def delete_profile(author_id: str) -> None:
    """Delete a profile from disk and remove it from the cache."""
    path = _AUTHORS_DIR / f"{author_id}.json"
    if path.exists():
        path.unlink()
    _cache.pop(author_id, None)
    logger.info("Deleted profile '%s'", author_id)


def add_example(author_id: str, post_text: str) -> None:
    """Append an example post to a profile and refresh the cache."""
    path = _AUTHORS_DIR / f"{author_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("examples", []).append({"post": post_text})
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    invalidate_cache()


def get_template() -> dict:
    """Return the raw template JSON."""
    template_path = _AUTHORS_DIR / "_template.json"
    return json.loads(template_path.read_text(encoding="utf-8"))


def update_profile_field(author_id: str, field_path: str, value) -> AuthorProfile:
    """Update a field by dot-notation path (e.g. 'post_structure.max_length_chars'), validate and save."""
    file_path = _AUTHORS_DIR / f"{author_id}.json"
    data = json.loads(file_path.read_text(encoding="utf-8"))
    keys = field_path.split(".")
    obj = data
    for key in keys[:-1]:
        obj = obj[key]
    obj[keys[-1]] = value
    profile = AuthorProfile.model_validate(data)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    invalidate_cache()
    return profile


def reset_profile_field(author_id: str, field_path: str) -> AuthorProfile:
    """Reset a field to its template default and save."""
    template = get_template()
    keys = field_path.split(".")
    obj = template
    for key in keys:
        obj = obj[key]
    return update_profile_field(author_id, field_path, obj)


def delete_example(author_id: str, index: int) -> None:
    """Remove an example post by index and refresh the cache."""
    path = _AUTHORS_DIR / f"{author_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    examples: list = data.get("examples", [])
    if not (0 <= index < len(examples)):
        raise IndexError(f"Example index {index} out of range")
    examples.pop(index)
    data["examples"] = examples
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    invalidate_cache()
