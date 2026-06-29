from profiles.schema import AuthorProfile
from utils.llm import call_llm


def _build_prompt(profile: AuthorProfile) -> str:
    ps = profile.post_structure
    rules = [
        f"Максимальная длина: {ps.max_length_chars} символов",
        f"Эмодзи: {'разрешены' if ps.use_emoji else 'запрещены'}",
        f"Хэштеги: {'обязательны' if ps.use_hashtags else 'не использовать'}",
    ]

    parts = [profile.agent_prompts.qa]
    if profile.tone_description:
        parts.append(f"\nСтиль автора:\n{profile.tone_description}")
    if profile.forbidden_phrases:
        phrases = ", ".join(f'"{p}"' for p in profile.forbidden_phrases)
        parts.append(f"\nЗапрещённые фразы (удалить если есть): {phrases}")
    parts.append("\nПравила для проверки:\n" + "\n".join(f"- {r}" for r in rules))
    return "\n".join(parts)


async def qa_check(formatted: str, profile: AuthorProfile) -> str:
    """Agent 5: quality check — fix issues or return as-is."""
    return await call_llm(
        system_prompt=_build_prompt(profile),
        user_content=f"Пост для проверки:\n{formatted}",
        max_tokens=700,
    )
