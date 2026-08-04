from src.agents.state import MedCheckState
from src.services.llm import get_llm

_SYSTEM_PROMPT = (
    "Bạn là trợ lý giải thích tương tác thuốc cho bệnh nhân. Chỉ diễn giải lại "
    "thông tin tương tác được cung cấp bằng ngôn ngữ dễ hiểu, ngắn gọn, bằng tiếng "
    "Việt. TUYỆT ĐỐI KHÔNG khuyên bệnh nhân ngừng, đổi, hoặc tự ý điều chỉnh liều/thời "
    "điểm dùng bất kỳ loại thuốc nào — kể cả khi thông tin gốc có đề cập cách dùng cụ "
    "thể. Luôn kết thúc bằng khuyến nghị hỏi ý kiến dược sĩ/bác sĩ."
)

# Cắt bớt Interaction/References_info dài (thật, có outlier tới 17-27k ký tự) trước
# khi đưa vào prompt LLM để tránh phí token/tràn context (GD6 mục 7.5). Bản đầy đủ
# vẫn được lưu/trả về nguyên vẹn trong nguon_trich_dan để hiển thị "xem thêm".
_MAX_MO_TA_CHARS = 1500
_MAX_NGUON_CHARS = 300

_UNCLASSIFIED_MESSAGE = (
    "DDInter chưa phân loại mức độ nghiêm trọng cho cặp thuốc này — cần thận "
    "trọng, hãy hỏi dược sĩ/bác sĩ trước khi tiếp tục dùng đồng thời."
)

_NO_DATA_MESSAGE = (
    "Chưa có dữ liệu trong CSDL DDInter 2.0 để đánh giá tương tác giữa hai thuốc "
    "này. Vui lòng hỏi dược sĩ/bác sĩ để được tư vấn cụ thể."
)


def _truncate(text: str | None, max_chars: int) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (đã rút gọn)"


def _base_fields(result: dict) -> dict:
    """Các field dùng lại cho mọi nhánh — kèm xu_tri/thay_the chỉ để pharmacist xem sau."""
    return {
        "thuoc_a": result.get("thuoc_a"),
        "thuoc_b": result.get("thuoc_b"),
        "medication_a_id": result.get("medication_a_id"),
        "medication_b_id": result.get("medication_b_id"),
        "xu_tri": result.get("xu_tri"),
        "thay_the_a": result.get("thay_the_a"),
        "thay_the_b": result.get("thay_the_b"),
    }


async def explain_node(state: MedCheckState) -> dict:
    """Sinh giải thích cho từng kết quả tương tác, bắt buộc kèm nguồn trích dẫn."""
    ranked_results = state.get("ranked_results", [])
    explanations = []

    for result in ranked_results:
        if result.get("khong_du_du_lieu"):
            explanations.append(
                {
                    **_base_fields(result),
                    "giai_thich": _NO_DATA_MESSAGE,
                    "nguon_trich_dan": "Không tìm thấy trong CSDL DDInter 2.0",
                }
            )
            continue

        if result.get("muc_do") == "chua_phan_loai":
            explanations.append(
                {
                    **_base_fields(result),
                    "muc_do": result.get("muc_do"),
                    "giai_thich": _UNCLASSIFIED_MESSAGE,
                    "nguon_trich_dan": result.get("nguon_trich_dan"),
                }
            )
            continue

        llm = get_llm()
        prompt = (
            f"Tương tác: {result.get('thuoc_a')} + {result.get('thuoc_b')}\n"
            f"Mức độ: {result.get('muc_do')}\n"
            f"Mô tả CSDL: {_truncate(result.get('mo_ta'), _MAX_MO_TA_CHARS)}\n"
            f"Nguồn: {_truncate(result.get('nguon_trich_dan'), _MAX_NGUON_CHARS)}\n\n"
            "Hãy giải thích ngắn gọn tương tác này cho bệnh nhân bằng tiếng Việt. "
            "Chỉ mô tả bản chất rủi ro, KHÔNG nêu thời điểm/liều dùng cụ thể."
        )
        response = await llm.ainvoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )

        explanations.append(
            {
                **_base_fields(result),
                "muc_do": result.get("muc_do"),
                "giai_thich": response.content,
                "nguon_trich_dan": result.get("nguon_trich_dan"),
            }
        )

    return {"explanations": explanations}
