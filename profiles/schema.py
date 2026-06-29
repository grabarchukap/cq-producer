import re
from pydantic import BaseModel, field_validator


class PostStructure(BaseModel):
    max_length_chars: int
    paragraphs: dict[str, int]  # {"min": int, "max": int}
    use_emoji: bool
    use_hashtags: bool
    hashtag_style: str = ""
    formatting_hints: str = ""


class AgentPrompts(BaseModel):
    expand: str
    tone: str
    format: str
    qa: str
    edit: str


class AuthorProfile(BaseModel):
    id: str
    display_name: str
    language: str = "ru"
    tone_description: str = ""
    forbidden_phrases: list[str] = []
    post_structure: PostStructure
    agent_prompts: AgentPrompts
    examples: list[dict] = []

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9_]{1,32}$", v):
            raise ValueError(
                f"Profile id '{v}' must match [a-z0-9_] with max 32 chars"
            )
        return v
