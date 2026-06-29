from profiles.schema import AuthorProfile
from utils.llm import call_llm


async def expand(raw_text: str, profile: AuthorProfile) -> str:
    """Agent 2: turn raw transcript/text into a coherent draft."""
    return await call_llm(
        system_prompt=profile.agent_prompts.expand,
        user_content=f"Исходный текст:\n{raw_text}",
        max_tokens=600,
    )
