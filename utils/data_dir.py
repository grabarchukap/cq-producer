import logging
import shutil
from pathlib import Path

from config import (
    AUTHORS_DIR,
    CODE_DIR,
    DATA_DIR,
    DRAFT_PROMPT_PATH,
    QUESTIONS_PATH,
)

logger = logging.getLogger(__name__)


def _copy_if_missing(src: Path, dst: Path) -> None:
    if dst.exists() or not src.exists():
        return
    shutil.copyfile(src, dst)
    logger.info("Seeded %s", dst)


def ensure_data_dir() -> None:
    """Create DATA_DIR and seed it with the defaults shipped in the code.

    Existing files are never overwritten, so the admin panel's edits survive a
    restart. A no-op when DATA_DIR is unset (files live next to the code then).
    """
    if DATA_DIR is None:
        return

    AUTHORS_DIR.mkdir(parents=True, exist_ok=True)

    for src in sorted((CODE_DIR / "profiles" / "authors").glob("*.json")):
        if src.name.startswith("_"):   # _template.json stays in the code
            continue
        _copy_if_missing(src, AUTHORS_DIR / src.name)

    _copy_if_missing(CODE_DIR / "case_questions" / "questions.json", QUESTIONS_PATH)
    _copy_if_missing(CODE_DIR / "agents" / "draft_prompt.txt", DRAFT_PROMPT_PATH)

    logger.info("Data directory ready: %s", DATA_DIR)
