from profiles.schema import AuthorProfile
from utils.llm import call_llm


async def edit_post(
    current_post: str, user_request: str, profile: AuthorProfile
) -> str:
    """Agent 6: apply targeted edits requested by the user."""
    parts = [profile.agent_prompts.edit]
    if profile.tone_description:
        parts.append(f"\nСтиль автора:\n{profile.tone_description}")
    system_prompt = "\n".join(parts)

    user_content = (
        f"Текущий пост:\n{current_post}\n\n"
        f"Запрос на правку: {user_request}"
    )
    return await call_llm(
        system_prompt=system_prompt,
        user_content=user_content,
        max_tokens=800,
    )
