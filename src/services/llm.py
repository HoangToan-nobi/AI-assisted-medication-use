from functools import lru_cache

from langchain_openai import ChatOpenAI

from src.config import get_settings


@lru_cache
def get_llm() -> ChatOpenAI:
    """Cache 1 instance duy nhất - trước đây tạo ChatOpenAI mới mỗi lệnh gọi, mất
    khả năng tái dùng connection pool (mỗi lệnh gọi phải bắt tay TCP+TLS lại từ đầu
    với DeepSeek). An toàn khi nhiều coroutine cùng gọi ainvoke() đồng thời qua
    asyncio.gather - đó chính là mục đích của connection pooling."""
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
