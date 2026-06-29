from profiles.schema import AuthorProfile
from utils.llm import call_llm


def _build_prompt(profile: AuthorProfile) -> str:
    ps = profile.post_structure
    rules = [
        f"Максимальная длина: {ps.max_length_chars} символов",
        f"Абзацев: от {ps.paragraphs.get('min', 1)} до {ps.paragraphs.get('max', 5)}",
        f"Эмодзи: {'разрешены' if ps.use_emoji else 'запрещены'}",
        f"Хэштеги: {'использовать' if ps.use_hashtags else 'не использовать'}",
    ]
    if ps.use_hashtags and ps.hashtag_style:
        rules.append(f"Стиль хэштегов: {ps.hashtag_style}")
    if ps.formatting_hints:
        rules.append(f"Структура и стиль: {ps.formatting_hints}")

    prompt = profile.agent_prompts.format
    prompt += "\n\nПравила форматирования:\n" + "\n".join(f"- {r}" for r in rules)
    return prompt


async def format_post(toned: str, profile: AuthorProfile) -> str:
    """Agent 4: apply formatting rules to the post."""
    return await call_llm(
        system_prompt=_build_prompt(profile),
        user_content=f"Текст для форматирования:\n{toned}",
        max_tokens=600,
    )
