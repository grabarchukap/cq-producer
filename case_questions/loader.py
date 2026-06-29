import json
from pathlib import Path

_QUESTIONS_PATH = Path(__file__).parent / "questions.json"


def load_questions() -> list[dict]:
    """Load questions list from disk."""
    return json.loads(_QUESTIONS_PATH.read_text(encoding="utf-8"))


def save_questions(questions: list[dict]) -> None:
    """Persist questions list to disk."""
    _QUESTIONS_PATH.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_question(text: str) -> list[dict]:
    """Append a new question and return updated list."""
    questions = load_questions()
    new_id = max((q["id"] for q in questions), default=0) + 1
    questions.append({"id": new_id, "text": text})
    save_questions(questions)
    return questions


def update_question(index: int, text: str) -> list[dict]:
    """Update question text at zero-based index."""
    questions = load_questions()
    if not (0 <= index < len(questions)):
        raise IndexError(f"Question index {index} out of range")
    questions[index]["text"] = text
    save_questions(questions)
    return questions


def delete_question(index: int) -> list[dict]:
    """Delete question at zero-based index and return updated list."""
    questions = load_questions()
    if not (0 <= index < len(questions)):
        raise IndexError(f"Question index {index} out of range")
    questions.pop(index)
    save_questions(questions)
    return questions
