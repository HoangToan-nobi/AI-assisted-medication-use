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
    # Gợi ý điều chỉnh thời điểm/khoảng cách dùng thuốc - dù không nêu con số cụ
    # thể vẫn là một hình thức "khuyên xử trí" mà AI không được phép tự đưa ra
    # (việc này thuộc về bác sĩ/dược sĩ).
    r"cách nhau",
    r"gần nhau",
    r"giãn cách",
    r"tách (?:thời điểm|liều|giờ|ra)",
    # Cụm tiếng Anh tương đương - dữ liệu thật DDInter 2.0 (Interaction/Management)
    # là tiếng Anh, LLM có thể lỡ giữ nguyên/paraphrase gần với câu gốc (GD6 mục 7.6).
    r"should be administered",
    r"should not be (?:used|taken) together",
    r"discontinue",
    r"stop taking",
    r"switch to",
    r"should be avoided",
    r"avoid (?:concurrent|concomitant) use",
    r"space (?:out|apart)",
    r"separate (?:the )?(?:doses|administration)",
]
_BANNED_REGEX = re.compile("|".join(_BANNED_PATTERNS), re.IGNORECASE)

_NEUTRAL_FALLBACK = (
    "Không thể đưa ra khuyến nghị thay đổi thuốc. Vui lòng hỏi dược sĩ hoặc "
    "bác sĩ để được tư vấn phù hợp."
)


def filter_banned_language(text: str) -> str:
    """Chặn ngôn ngữ khuyên đổi/ngừng thuốc trong 1 đoạn text - dùng chung cho mọi
    cấp (hoạt chất trong guardrail_node bên dưới, và thuốc/đơn thuốc trong
    rollup_explain, nơi không chạy qua node LangGraph này)."""
    if not text:
        return text
    if _BANNED_REGEX.search(text):
        return _NEUTRAL_FALLBACK
    return text


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
        updated = dict(explanation)
        if updated.get("giai_thich"):
            updated["giai_thich"] = filter_banned_language(updated["giai_thich"])
        if updated.get("giai_thich_duoc_si"):
            updated["giai_thich_duoc_si"] = filter_banned_language(updated["giai_thich_duoc_si"])
        filtered_explanations.append(updated)

    return {"explanations": filtered_explanations}
