"""Sinh giải thích 2 giọng điệu (bệnh nhân/dược sĩ) + bản dịch nguyên văn cho từng
cặp hoạt chất-thực phẩm/hoạt chất-bệnh nền (DDInter 2.0 DFI/DDSI) - gọi từ
src/api/routes.py sau khi có kết quả lookup_food_interactions/lookup_disease_interactions
(src/services/food_disease_lookup.py). Mirror đúng cơ chế 3 phần (2 giọng điệu +
[BẢN_DỊCH]) đang dùng cho cấp hoạt chất-hoạt chất (src/agents/nodes/explain_node.py),
để trải nghiệm/độ tin cậy nhất quán giữa 3 loại tương tác.

Chạy NGOÀI LangGraph agent (không phải node/tool) - xem lý do ở food_disease_lookup.py."""

import asyncio

from src.agents.nodes.guardrail_node import filter_banned_language
from src.services.llm import get_llm
from src.services.tone_prompt import (
    FORMAT_INSTRUCTIONS,
    SAFETY_RULES,
    TONE_PATIENT_MARKER,
    TONE_PHARMACIST_MARKER,
    TRANSLATION_MARKER,
    parse_tones,
    split_translation_block,
)

_MAX_TEXT_CHARS = 1500
_MAX_NGUON_CHARS = 300

_TRANSLATION_FIELDS_FOOD = [("mô tả:", "mo_ta_dich"), ("xử trí:", "xu_tri_dich")]
_TRANSLATION_FIELDS_DISEASE = [("mô tả:", "mo_ta_dich")]


def _truncate(text: str | None, max_chars: int) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (đã rút gọn)"


def _brand_names(hoat_chat_name: str | None, ingredient_to_products: dict[str, list[str]]) -> list[str]:
    if not hoat_chat_name:
        return []
    brands = ingredient_to_products.get(hoat_chat_name)
    if not brands:
        return []
    return list(dict.fromkeys(brands))


_FOOD_SYSTEM_PROMPT = (
    "Bạn là một dược sĩ đang giải thích tương tác giữa 1 HOẠT CHẤT và 1 LOẠI THỰC "
    "PHẨM, dựa đúng trên dữ liệu tra cứu CSDL DDInter 2.0 được cung cấp ở tin nhắn "
    "tiếp theo — không phải dịch lại một tờ hướng dẫn sử dụng.\n\n"
    f"Phần {TONE_PATIENT_MARKER}: viết như đang trò chuyện trực tiếp, gần gũi với "
    "bệnh nhân — xưng \"mình\", gọi người đọc là \"bạn\". Vào thẳng nội dung rủi ro "
    "cụ thể ngay câu đầu tiên. Khoảng 2-3 câu.\n\n"
    f"Phần {TONE_PHARMACIST_MARKER}: viết theo văn phong khoa học, chuyên nghiệp, "
    "súc tích, dành cho dược sĩ đang tra cứu nhanh. Khoảng 1-2 câu.\n\n"
    "Chỉ diễn giải lại đúng thông tin được cung cấp, không thêm dữ kiện y khoa nằm "
    "ngoài đó.\n\n"
    f"{FORMAT_INSTRUCTIONS}\n\n{SAFETY_RULES}\n\n"
    f"Sau 2 phần trên, thêm PHẦN THỨ BA bắt đầu bằng đúng dòng {TRANSLATION_MARKER} "
    "— phần này KHÔNG áp dụng các quy tắc an toàn bên trên vì đây là BẢN DỊCH NGUYÊN "
    "VĂN, không phải diễn giải lại: dịch sát nghĩa, đầy đủ, KHÔNG rút gọn, KHÔNG "
    "thêm/bớt thông tin, từ tiếng Anh sang tiếng Việt đúng 'Mô tả CSDL' và 'Xử trí "
    "CSDL' được cung cấp ở tin nhắn tiếp theo, theo đúng 2 dòng:\n"
    "Mô tả: <bản dịch nguyên văn Mô tả CSDL>\n"
    "Xử trí: <bản dịch nguyên văn Xử trí CSDL>"
)

_DISEASE_SYSTEM_PROMPT = (
    "Bạn là một dược sĩ đang giải thích tương tác giữa 1 HOẠT CHẤT và 1 BỆNH NỀN "
    "(tình trạng bệnh lý cần thận trọng khi dùng thuốc này), dựa đúng trên dữ liệu "
    "tra cứu CSDL DDInter 2.0 được cung cấp ở tin nhắn tiếp theo — không phải dịch "
    "lại một tờ hướng dẫn sử dụng.\n\n"
    f"Phần {TONE_PATIENT_MARKER}: viết như đang trò chuyện trực tiếp, gần gũi với "
    "bệnh nhân — xưng \"mình\", gọi người đọc là \"bạn\". Vào thẳng nội dung rủi ro "
    "cụ thể ngay câu đầu tiên. Khoảng 2-3 câu.\n\n"
    f"Phần {TONE_PHARMACIST_MARKER}: viết theo văn phong khoa học, chuyên nghiệp, "
    "súc tích, dành cho dược sĩ đang tra cứu nhanh. Khoảng 1-2 câu.\n\n"
    "Chỉ diễn giải lại đúng thông tin được cung cấp, không thêm dữ kiện y khoa nằm "
    "ngoài đó. TUYỆT ĐỐI KHÔNG khẳng định hay chẩn đoán người đọc có bệnh này — chỉ "
    "nói về việc dùng thuốc NẾU có tiền sử/đang mắc bệnh đó.\n\n"
    f"{FORMAT_INSTRUCTIONS}\n\n{SAFETY_RULES}\n\n"
    f"Sau 2 phần trên, thêm PHẦN THỨ BA bắt đầu bằng đúng dòng {TRANSLATION_MARKER} "
    "— phần này KHÔNG áp dụng các quy tắc an toàn bên trên vì đây là BẢN DỊCH NGUYÊN "
    "VĂN, không phải diễn giải lại: dịch sát nghĩa, đầy đủ, KHÔNG rút gọn, KHÔNG "
    "thêm/bớt thông tin, từ tiếng Anh sang tiếng Việt đúng 'Mô tả CSDL' được cung "
    "cấp ở tin nhắn tiếp theo, theo đúng dòng:\n"
    "Mô tả: <bản dịch nguyên văn Mô tả CSDL>"
)


async def _explain_food_row(row: dict) -> dict:
    llm = get_llm()
    prompt = (
        f"Hoạt chất: {row['hoat_chat']}\n"
        f"Thực phẩm: {row['thuc_pham']}\n"
        f"Mức độ: {row.get('muc_do')}\n"
        f"Mô tả CSDL: {_truncate(row.get('mo_ta'), _MAX_TEXT_CHARS)}\n"
        f"Xử trí CSDL: {_truncate(row.get('xu_tri'), _MAX_TEXT_CHARS)}\n"
        f"Nguồn: {_truncate(row.get('nguon_trich_dan'), _MAX_NGUON_CHARS)}\n\n"
        "Hãy viết đủ CẢ 3 PHẦN theo đúng định dạng đã nêu, bằng tiếng Việt."
    )
    response = await llm.ainvoke(
        [
            {"role": "system", "content": _FOOD_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )
    tones_text, translated = split_translation_block(response.content or "", _TRANSLATION_FIELDS_FOOD)
    patient_text, pharmacist_text = parse_tones(tones_text)
    return {
        "hoat_chat": row["hoat_chat"],
        "thuc_pham": row["thuc_pham"],
        "muc_do": row.get("muc_do"),
        "giai_thich": filter_banned_language(patient_text),
        "giai_thich_duoc_si": filter_banned_language(pharmacist_text),
        "nguon_trich_dan": row.get("nguon_trich_dan"),
        # Bản dịch nguyên văn - chỉ dược sĩ mới thấy (xem _PHARMACIST_ONLY_FIELDS ở routes.py).
        "mo_ta_dich": translated["mo_ta_dich"],
        "xu_tri_dich": translated["xu_tri_dich"],
    }


async def _explain_disease_row(row: dict) -> dict:
    llm = get_llm()
    prompt = (
        f"Hoạt chất: {row['hoat_chat']}\n"
        f"Bệnh nền: {row['ten_benh']}\n"
        f"Mức độ: {row.get('muc_do')}\n"
        f"Mô tả CSDL: {_truncate(row.get('mo_ta'), _MAX_TEXT_CHARS)}\n"
        f"Nguồn: {_truncate(row.get('nguon_trich_dan'), _MAX_NGUON_CHARS)}\n\n"
        "Hãy viết đủ CẢ 3 PHẦN theo đúng định dạng đã nêu, bằng tiếng Việt."
    )
    response = await llm.ainvoke(
        [
            {"role": "system", "content": _DISEASE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )
    tones_text, translated = split_translation_block(response.content or "", _TRANSLATION_FIELDS_DISEASE)
    patient_text, pharmacist_text = parse_tones(tones_text)
    return {
        "hoat_chat": row["hoat_chat"],
        "ten_benh": row["ten_benh"],
        "muc_do": row.get("muc_do"),
        "giai_thich": filter_banned_language(patient_text),
        "giai_thich_duoc_si": filter_banned_language(pharmacist_text),
        "nguon_trich_dan": row.get("nguon_trich_dan"),
        "mo_ta_dich": translated["mo_ta_dich"],
    }


async def build_food_interaction_explanations(
    rows: list[dict], ingredient_to_products: dict[str, list[str]]
) -> list[dict]:
    if not rows:
        return []
    explanations = await asyncio.gather(*(_explain_food_row(row) for row in rows))
    for row, exp in zip(rows, explanations):
        exp["san_pham"] = _brand_names(row["hoat_chat"], ingredient_to_products)
    return list(explanations)


async def build_disease_interaction_explanations(
    rows: list[dict], ingredient_to_products: dict[str, list[str]]
) -> list[dict]:
    if not rows:
        return []
    explanations = await asyncio.gather(*(_explain_disease_row(row) for row in rows))
    for row, exp in zip(rows, explanations):
        exp["san_pham"] = _brand_names(row["hoat_chat"], ingredient_to_products)
    return list(explanations)


def build_food_disease_warning_line(
    food_explanations: list[dict], disease_explanations: list[dict]
) -> str | None:
    """Câu liệt kê CỐ ĐỊNH (không qua LLM) tên thực phẩm/bệnh nền cần lưu ý, ghép
    thêm vào bảng tóm tắt tổng quan SAU đoạn LLM sinh về tương tác thuốc-thuốc -
    không có rủi ro bịa dữ kiện vì chỉ liệt kê thẳng tên đã khớp được trong DDInter."""
    foods = sorted({item["thuc_pham"] for item in food_explanations})
    diseases = sorted({item["ten_benh"] for item in disease_explanations})
    if not foods and not diseases:
        return None

    parts = []
    if foods:
        parts.append(f"tránh dùng chung với: {', '.join(foods)}")
    if diseases:
        parts.append(f"thận trọng nếu có tiền sử/đang mắc: {', '.join(diseases)}")
    return (
        "Ngoài ra, cần lưu ý " + "; ".join(parts) +
        ". Hãy trao đổi với dược sĩ/bác sĩ nếu bạn thuộc trường hợp này."
    )
