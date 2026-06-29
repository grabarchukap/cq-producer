from profiles.schema import AuthorProfile
from utils.llm import call_llm


def _build_prompt(profile: AuthorProfile) -> str:
    parts = [profile.agent_prompts.tone]

    if profile.tone_description:
        parts.append(f"\nСтиль автора:\n{profile.tone_description}")

    if profile.forbidden_phrases:
        phrases = ", ".join(f'"{p}"' for p in profile.forbidden_phrases)
        parts.append(f"\nЗапрещённые фразы (не использовать): {phrases}")

    if profile.examples:
        parts.append("\nПримеры постов автора:")
        for ex in profile.examples:
            parts.append(f"---\n{ex.get('post', '')}")

    return "\n".join(parts)


async def apply_tone(draft: str, profile: AuthorProfile) -> str:
    """Agent 3: rewrite draft in the author's tone of voice."""
    return await call_llm(
        system_prompt=_build_prompt(profile),
        user_content=f"Черновик:\n{draft}",
        max_tokens=800,
    )
