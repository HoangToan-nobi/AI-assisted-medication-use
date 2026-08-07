import re

from src.agents.state import MedCheckState

# Các cụm từ mang tính khuyên đổi/ngừng/kê thuốc - tuyệt đối không để lọt ra ngoài.
_BANNED_PATTERNS = [
    r"nên ngừng",
    r"ngừng dùng",
    r"nên đổi",
    r"đổi sang thuốc khác",
    r"hãy ngừng",
    r"kê đơn",
    r"kê thuốc",
    r"nên dùng thay",
    r"thay thế bằng thuốc",
    # Cụm tiếng Anh tương đương - dữ liệu thật DDInter 2.0 (Interaction/Management)
    # là tiếng Anh, LLM có thể lỡ giữ nguyên/paraphrase gần với câu gốc (GD6 mục 7.6).
    r"should be administered",
    r"should not be (?:used|taken) together",
    r"discontinue",
    r"stop taking",
    r"switch to",
    r"should be avoided",
    r"avoid (?:concurrent|concomitant) use",
]
_BANNED_REGEX = re.compile("|".join(_BANNED_PATTERNS), re.IGNORECASE)

_NEUTRAL_FALLBACK = (
    "Không thể đưa ra khuyến nghị thay đổi thuốc. Vui lòng hỏi dược sĩ hoặc "
    "bác sĩ để được tư vấn phù hợp."
)


async def guardrail_node(state: MedCheckState) -> dict:
    """Chặn hallucination (thiếu citation) và ngôn ngữ khuyên đổi/ngừng thuốc."""
    explanations = state.get("explanations", [])

    for explanation in explanations:
        if not explanation.get("nguon_trich_dan"):
            return {
                "error": (
                    "Giải thích thiếu nguồn trích dẫn - chặn để tránh hallucination."
                )
            }

    filtered_explanations = []
    for explanation in explanations:
        giai_thich = explanation.get("giai_thich", "")
        if _BANNED_REGEX.search(giai_thich):
            explanation = {**explanation, "giai_thich": _NEUTRAL_FALLBACK}
        filtered_explanations.append(explanation)

    return {"explanations": filtered_explanations}
