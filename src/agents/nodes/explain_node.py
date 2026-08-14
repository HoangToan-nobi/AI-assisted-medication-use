from src.agents.nodes.guardrail_node import filter_banned_language
from src.agents.state import MedCheckState
from src.services.llm import get_llm
from src.services.tone_prompt import (
    FORMAT_INSTRUCTIONS,
    SAFETY_RULES,
    TONE_PATIENT_MARKER,
    TONE_PHARMACIST_MARKER,
    parse_tones,
)

_TRANSLATION_MARKER = "[BẢN_DỊCH]"

_SYSTEM_PROMPT = (
    "Bạn là một dược sĩ đang giải thích một tương tác giữa HAI HOẠT CHẤT cụ thể, "
    "dựa đúng trên dữ liệu tra cứu CSDL DDInter 2.0 được cung cấp ở tin nhắn tiếp "
    "theo — không phải dịch lại một tờ hướng dẫn sử dụng.\n\n"
    f"Phần {TONE_PATIENT_MARKER}: viết như đang trò chuyện trực "
    "tiếp, gần gũi với bệnh nhân — xưng \"mình\", gọi người đọc là \"bạn\", dùng từ "
    "ngữ đời thường, tránh văn phong hành chính/dịch thuật máy móc. Vào thẳng nội "
    "dung rủi ro cụ thể ngay câu đầu tiên — KHÔNG mở đầu bằng câu dẫn/rào đón kiểu "
    "\"Mình cần nói với bạn...\", \"Mình muốn chia sẻ...\", \"Điều quan trọng là...\". "
    "Khoảng 3-4 câu, ngắn gọn dễ hiểu nhưng thân thiện — sau câu đầu nêu rủi ro, "
    "mới giải thích ngắn gọn vì sao.\n\n"
    f"Phần {TONE_PHARMACIST_MARKER}: viết theo văn phong khoa học, "
    "chuyên nghiệp, súc tích, dành cho dược sĩ đang tra cứu nhanh — có thể dùng "
    "thuật ngữ dược lý/dược động học nếu mô tả gốc có đề cập (cơ chế, enzym, thụ "
    "thể, nồng độ huyết tương...), đi thẳng vào bản chất tương tác và hậu quả lâm "
    "sàng, không cần mào đầu xã giao, không lặp lại giọng văn thân mật của phần "
    "bệnh nhân. Khoảng 2-3 câu.\n\n"
    "Chỉ diễn giải lại đúng thông tin tương tác được cung cấp, không thêm dữ kiện y "
    "khoa nằm ngoài đó. Diễn đạt tự nhiên, đa dạng cách nói giữa các lần trả lời — "
    "tránh dùng đi dùng lại một câu công thức y hệt.\n\n"
    f"{FORMAT_INSTRUCTIONS}\n\n{SAFETY_RULES}\n\n"
    f"Sau 2 phần trên, thêm PHẦN THỨ BA bắt đầu bằng đúng dòng {_TRANSLATION_MARKER} "
    "— phần này KHÔNG áp dụng các quy tắc an toàn bên trên vì đây là BẢN DỊCH NGUYÊN "
    "VĂN, không phải diễn giải lại: dịch sát nghĩa, đầy đủ, KHÔNG rút gọn, KHÔNG "
    "thêm/bớt thông tin, từ tiếng Anh sang tiếng Việt đúng 'Mô tả CSDL' và 'Xử trí "
    "CSDL' được cung cấp ở tin nhắn tiếp theo, theo đúng 2 dòng:\n"
    "Mô tả: <bản dịch nguyên văn Mô tả CSDL>\n"
    "Xử trí: <bản dịch nguyên văn Xử trí CSDL, để trống nếu tin nhắn không có Xử trí CSDL>"
)


def _split_translation(raw: str) -> tuple[str, str | None, str | None]:
    """Tách phần dịch nguyên văn (bắt đầu bằng _TRANSLATION_MARKER, do LLM luôn đặt
    SAU marker dược sĩ) ra khỏi phần còn lại TRƯỚC khi gọi parse_tones - nếu không
    tách trước, parse_tones sẽ dính luôn đoạn dịch vào cuối bản dược sĩ vì nó chỉ
    biết dừng ở hết chuỗi."""
    if _TRANSLATION_MARKER not in raw:
        return raw, None, None
    rest, block = raw.split(_TRANSLATION_MARKER, 1)
    mo_ta_vi: str | None = None
    xu_tri_vi: str | None = None
    for line in block.strip().splitlines():
        line = line.strip()
        if line.lower().startswith("mô tả:"):
            mo_ta_vi = line.split(":", 1)[1].strip() or None
        elif line.lower().startswith("xử trí:"):
            xu_tri_vi = line.split(":", 1)[1].strip() or None
    return rest, mo_ta_vi, xu_tri_vi

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
    """Các field dùng lại cho mọi nhánh — kèm xu_tri/thay_the/mo_ta chỉ để pharmacist
    xem sau (mo_ta là mô tả khoa học nguyên văn từ CSDL DDInter 2.0, KHÔNG qua AI
    diễn giải lại - dùng thử làm bản "khoa học, minh bạch" cho dược sĩ, song song
    với giai_thich/giai_thich_duoc_si do LLM viết lại theo 2 giọng điệu)."""
    return {
        "thuoc_a": result.get("thuoc_a"),
        "thuoc_b": result.get("thuoc_b"),
        "medication_a_id": result.get("medication_a_id"),
        "medication_b_id": result.get("medication_b_id"),
        "xu_tri": result.get("xu_tri"),
        "thay_the_a": result.get("thay_the_a"),
        "thay_the_b": result.get("thay_the_b"),
        "mo_ta": result.get("mo_ta"),
    }


async def explain_node(state: MedCheckState) -> dict:
    """Sinh giải thích cho từng kết quả tương tác (cấp hoạt chất), bắt buộc kèm
    nguồn trích dẫn và 2 giọng điệu song song: giai_thich (bệnh nhân) và
    giai_thich_duoc_si (dược sĩ)."""
    ranked_results = state.get("ranked_results", [])
    explanations = []

    for result in ranked_results:
        if result.get("khong_du_du_lieu"):
            explanations.append(
                {
                    **_base_fields(result),
                    "giai_thich": _NO_DATA_MESSAGE,
                    "giai_thich_duoc_si": _NO_DATA_MESSAGE,
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
                    "giai_thich_duoc_si": _UNCLASSIFIED_MESSAGE,
                    "nguon_trich_dan": result.get("nguon_trich_dan"),
                }
            )
            continue

        llm = get_llm()
        prompt = (
            f"Tương tác: {result.get('thuoc_a')} + {result.get('thuoc_b')}\n"
            f"Mức độ: {result.get('muc_do')}\n"
            f"Mô tả CSDL: {_truncate(result.get('mo_ta'), _MAX_MO_TA_CHARS)}\n"
            f"Xử trí CSDL: {_truncate(result.get('xu_tri'), _MAX_MO_TA_CHARS)}\n"
            f"Nguồn: {_truncate(result.get('nguon_trich_dan'), _MAX_NGUON_CHARS)}\n\n"
            "Hãy viết đủ CẢ 3 PHẦN theo đúng định dạng đã nêu, bằng tiếng Việt. Với 2 "
            "phần đầu, chỉnh giọng điệu theo đúng mức độ nghiêm trọng ở trên — nhẹ "
            "nhàng nếu mức độ nhẹ/trung bình, rõ ràng và nghiêm túc hơn nếu mức độ "
            "nặng, nhưng đừng gây hoang mang quá mức. Chỉ mô tả bản chất rủi ro và cơ "
            "chế, KHÔNG nêu thời điểm/liều dùng cụ thể. Với phần thứ ba, dịch nguyên "
            "văn không thêm bớt như đã nêu."
        )
        response = await llm.ainvoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        tones_text, mo_ta_vi, xu_tri_vi = _split_translation(response.content or "")
        patient_text, pharmacist_text = parse_tones(tones_text)

        explanations.append(
            {
                **_base_fields(result),
                "muc_do": result.get("muc_do"),
                "giai_thich": filter_banned_language(patient_text),
                "giai_thich_duoc_si": filter_banned_language(pharmacist_text),
                "nguon_trich_dan": result.get("nguon_trich_dan"),
                # Bản dịch nguyên văn (không qua diễn giải) từ tiếng Anh sang tiếng
                # Việt của mo_ta/xu_tri gốc trong CSDL - chỉ dược sĩ mới thấy (xem
                # _PHARMACIST_ONLY_FIELDS ở routes.py), đặt cạnh giai_thich_duoc_si.
                "mo_ta_dich": mo_ta_vi,
                "xu_tri_dich": xu_tri_vi,
            }
        )

    return {"explanations": explanations}
