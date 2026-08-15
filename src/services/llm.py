from langchain_openai import ChatOpenAI

from src.config import get_settings


def get_llm() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=settings.llm_temperature,
        # Tu thu lai (backoff tang dan, co san trong langchain-openai) khi gap loi tam
        # thoi tu DeepSeek, bao gom rate limit (429).
        max_retries=3,
    )


async def ainvoke_llm(messages: list[dict]):
    """Goi LLM - khong con gioi han so luot goi dong thoi (da bo semaphore theo yeu
    cau test toc do toi da), chi giu retry tu dong o get_llm()."""
    return await get_llm().ainvoke(messages)
