"""Gộp (rollup) các dòng tương tác hoạt chất-thực phẩm/hoạt chất-bệnh nền (DDInter
2.0 DFI/DDSI) lên cấp THUỐC (biệt dược) rồi gọi LLM sinh 1 đoạn giải thích RIÊNG cho
từng cạnh thuốc-thực phẩm/thuốc-bệnh nền - cùng cơ chế gộp như build_product_edges
(src/services/rollup_explain.py) áp dụng cho thuốc-thuốc: nếu 1 thuốc có nhiều hoạt
chất cùng kỵ 1 loại thực phẩm/bệnh nền, gộp thành 1 thẻ duy nhất thay vì hiện riêng
từng hoạt chất.

Gọi từ src/api/routes.py sau khi có kết quả lookup_food_interactions/
lookup_disease_interactions (src/services/food_disease_lookup.py)."""

import asyncio

from src.agents.nodes.guardrail_node import filter_banned_language
from src.services.llm import ainvoke_llm
from src.services.rollup_explain import _severity_rank, literal_merge_translate
from src.services.tone_prompt import (
    FORMAT_INSTRUCTIONS,
    SAFETY_RULES,
    TONE_PATIENT_MARKER,
    TONE_PHARMACIST_MARKER,
    parse_tones,
)

_MAX_TEXT_CHARS = 1500

# Chỉ đưa tối đa từng này dòng hoạt chất (đã sắp nặng nhất trước) vào prompt sinh
# giải thích cấp thuốc, để tránh phình prompt khi 1 thuốc phối hợp có nhiều hoạt
# chất - giống hệt _MAX_CONTRIBUTING_PAIRS ở rollup_explain.py.
_MAX_CONTRIBUTING_ROWS = 5


def _truncate(text: str | None, max_chars: int) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (đã rút gọn)"


def _edge_key(product: str, name: str) -> str:
    return f"{product.lower()}::{name.lower()}"


def _group_rows(rows: list[dict], name_field: str, ingredient_to_products: dict[str, list[str]]) -> list[dict]:
    """Gộp các dòng (hoạt_chất, name_field) thành cạnh (thuốc, name_field) - mỗi cạnh
    giữ mức độ nặng nhất và danh sách dòng hoạt chất góp phần, port của
    build_product_edges (rollup_explain.py) cho thuốc-thuốc. 1 hoạt chất có thể
    thuộc nhiều thuốc đang kiểm tra -> tạo cạnh riêng cho MỖI thuốc (không gộp lẫn
    các thuốc khác nhau vào 1 thẻ), khớp đúng cách build_product_edges xử lý
    san_pham_a/san_pham_b."""
    edges: dict[str, dict] = {}
    for row in rows:
        muc_do = row.get("muc_do")
        if not muc_do:
            continue
        products = ingredient_to_products.get(row["hoat_chat"]) or [row["hoat_chat"]]
        name = row[name_field]
        incomplete = muc_do == "chua_phan_loai"

        for product in dict.fromkeys(products):
            key = _edge_key(product, name)
            edge = edges.get(key)
            if edge is None:
                edges[key] = {
                    "san_pham": product,
                    name_field: name,
                    "muc_do": muc_do,
                    "has_incomplete_pair": incomplete,
                    "contributing_rows": [row],
                }
                continue
            edge["contributing_rows"].append(row)
            edge["has_incomplete_pair"] = edge["has_incomplete_pair"] or incomplete
            if _severity_rank(muc_do) > _severity_rank(edge["muc_do"]):
                edge["muc_do"] = muc_do

    for edge in edges.values():
        edge["pair_count"] = len(edge["contributing_rows"])
        edge["contributing_rows"].sort(key=lambda r: _severity_rank(r.get("muc_do")), reverse=True)

    return list(edges.values())


def build_food_edges(rows: list[dict], ingredient_to_products: dict[str, list[str]]) -> list[dict]:
    return _group_rows(rows, "thuc_pham", ingredient_to_products)


def build_disease_edges(rows: list[dict], ingredient_to_products: dict[str, list[str]]) -> list[dict]:
    return _group_rows(rows, "ten_benh", ingredient_to_products)


def _fd_citation(pair_count: int) -> str:
    return f"Tổng hợp từ {pair_count} hoạt chất tương tác trong CSDL DDInter 2.0."


_FOOD_EDGE_SYSTEM_PROMPT = (
    "Bạn là dược sĩ đang tổng hợp cảnh báo tương tác GIỮA 1 THUỐC và 1 LOẠI THỰC "
    "PHẨM, dựa trên các mô tả tương tác hoạt chất CÓ THẬT giữa thuốc này và thực "
    "phẩm này (dữ liệu CSDL DDInter 2.0) được liệt kê ở tin nhắn tiếp theo — đó là "
    "nguồn duy nhất bạn được dùng, không thêm dữ kiện y khoa nào khác. Hãy TỔNG HỢP "
    "LẠI thành 1 đoạn nói về việc dùng THUỐC này cùng THỰC PHẨM này (xưng tên thuốc "
    "là chính, không cần liệt kê lại từng hoạt chất).\n\n"
    f"Phần {TONE_PATIENT_MARKER}: giọng gần gũi, thân thiện, ngắn gọn dễ hiểu (2-3 "
    "câu).\n\n"
    f"Phần {TONE_PHARMACIST_MARKER}: giọng khoa học, chuyên nghiệp, súc tích (1-2 "
    "câu).\n\n"
    f"{FORMAT_INSTRUCTIONS}\n\n{SAFETY_RULES}"
)

_DISEASE_EDGE_SYSTEM_PROMPT = (
    "Bạn là dược sĩ đang tổng hợp cảnh báo tương tác GIỮA 1 THUỐC và 1 BỆNH NỀN "
    "(tình trạng bệnh lý cần thận trọng khi dùng thuốc này), dựa trên các mô tả "
    "tương tác hoạt chất CÓ THẬT giữa thuốc này và bệnh nền này (dữ liệu CSDL "
    "DDInter 2.0) được liệt kê ở tin nhắn tiếp theo — đó là nguồn duy nhất bạn được "
    "dùng, không thêm dữ kiện y khoa nào khác. Hãy TỔNG HỢP LẠI thành 1 đoạn nói về "
    "việc dùng THUỐC này khi có tiền sử/đang mắc BỆNH NỀN này (xưng tên thuốc là "
    "chính, không cần liệt kê lại từng hoạt chất). TUYỆT ĐỐI KHÔNG khẳng định hay "
    "chẩn đoán người đọc có bệnh này — chỉ nói về việc dùng thuốc NẾU có tiền sử/"
    "đang mắc bệnh đó.\n\n"
    f"Phần {TONE_PATIENT_MARKER}: giọng gần gũi, thân thiện, ngắn gọn dễ hiểu (2-3 "
    "câu).\n\n"
    f"Phần {TONE_PHARMACIST_MARKER}: giọng khoa học, chuyên nghiệp, súc tích (1-2 "
    "câu).\n\n"
    f"{FORMAT_INSTRUCTIONS}\n\n{SAFETY_RULES}"
)

_UNCLASSIFIED_FOOD_EDGE_MESSAGE = (
    "Giữa {a} và {b} có tương tác hoạt chất mà DDInter chưa phân loại mức độ nghiêm "
    "trọng — cần thận trọng, hãy hỏi dược sĩ/bác sĩ trước khi dùng chung."
)

_UNCLASSIFIED_DISEASE_EDGE_MESSAGE = (
    "Giữa {a} và {b} có tương tác hoạt chất mà DDInter chưa phân loại mức độ nghiêm "
    "trọng — cần thận trọng, hãy hỏi dược sĩ/bác sĩ nếu bạn thuộc trường hợp này."
)


def _food_edge_user_prompt(product: str, food: str, muc_do: str, contributing_rows: list[dict]) -> str:
    lines = [f"Thuốc: {product}", f"Thực phẩm: {food}", f"Mức độ nghiêm trọng cao nhất: {muc_do}", ""]
    lines.append("Các mô tả tương tác hoạt chất có thật giữa thuốc này và thực phẩm này (CSDL DDInter 2.0):")
    for row in contributing_rows[:_MAX_CONTRIBUTING_ROWS]:
        lines.append(
            f"- Hoạt chất {row.get('hoat_chat')} (mức {row.get('muc_do')}):\n"
            f"  Mô tả CSDL: {_truncate(row.get('mo_ta'), _MAX_TEXT_CHARS)}\n"
            f"  Xử trí CSDL: {_truncate(row.get('xu_tri'), _MAX_TEXT_CHARS) or '(không có)'}"
        )
    lines.append("")
    lines.append(
        "Hãy viết cả 2 phần theo đúng định dạng đã nêu, bằng tiếng Việt, tổng hợp lại "
        "đúng nội dung ở trên - không thêm dữ kiện nào ngoài đó."
    )
    return "\n".join(lines)


def _disease_edge_user_prompt(product: str, disease: str, muc_do: str, contributing_rows: list[dict]) -> str:
    lines = [f"Thuốc: {product}", f"Bệnh nền: {disease}", f"Mức độ nghiêm trọng cao nhất: {muc_do}", ""]
    lines.append("Các mô tả tương tác hoạt chất có thật giữa thuốc này và bệnh nền này (CSDL DDInter 2.0):")
    for row in contributing_rows[:_MAX_CONTRIBUTING_ROWS]:
        lines.append(
            f"- Hoạt chất {row.get('hoat_chat')} (mức {row.get('muc_do')}):\n"
            f"  Mô tả CSDL: {_truncate(row.get('mo_ta'), _MAX_TEXT_CHARS)}"
        )
    lines.append("")
    lines.append(
        "Hãy viết cả 2 phần theo đúng định dạng đã nêu, bằng tiếng Việt, tổng hợp lại "
        "đúng nội dung ở trên - không thêm dữ kiện nào ngoài đó."
    )
    return "\n".join(lines)


async def _explain_food_edge(edge: dict) -> dict:
    product, food = edge["san_pham"], edge["thuc_pham"]
    muc_do, pair_count = edge["muc_do"], edge["pair_count"]

    if muc_do == "chua_phan_loai":
        message = _UNCLASSIFIED_FOOD_EDGE_MESSAGE.format(a=product, b=food)
        return {
            "san_pham": [product],
            "thuc_pham": food,
            "muc_do": muc_do,
            "giai_thich": message,
            "giai_thich_duoc_si": message,
            "nguon_trich_dan": _fd_citation(pair_count),
            "mo_ta_dich": None,
            "xu_tri_dich": None,
        }

    narrative_response, (mo_ta_dich, xu_tri_dich) = await asyncio.gather(
        ainvoke_llm(
            [
                {"role": "system", "content": _FOOD_EDGE_SYSTEM_PROMPT},
                {"role": "user", "content": _food_edge_user_prompt(product, food, muc_do, edge["contributing_rows"])},
            ]
        ),
        literal_merge_translate(edge["contributing_rows"], include_xu_tri=True),
    )
    patient_text, pharmacist_text = parse_tones(narrative_response.content or "")
    return {
        "san_pham": [product],
        "thuc_pham": food,
        "muc_do": muc_do,
        "giai_thich": filter_banned_language(patient_text),
        "giai_thich_duoc_si": filter_banned_language(pharmacist_text),
        "nguon_trich_dan": _fd_citation(pair_count),
        "mo_ta_dich": mo_ta_dich,
        "xu_tri_dich": xu_tri_dich,
    }


async def _explain_disease_edge(edge: dict) -> dict:
    product, disease = edge["san_pham"], edge["ten_benh"]
    muc_do, pair_count = edge["muc_do"], edge["pair_count"]

    if muc_do == "chua_phan_loai":
        message = _UNCLASSIFIED_DISEASE_EDGE_MESSAGE.format(a=product, b=disease)
        return {
            "san_pham": [product],
            "ten_benh": disease,
            "muc_do": muc_do,
            "giai_thich": message,
            "giai_thich_duoc_si": message,
            "nguon_trich_dan": _fd_citation(pair_count),
            "mo_ta_dich": None,
        }

    narrative_response, (mo_ta_dich, _) = await asyncio.gather(
        ainvoke_llm(
            [
                {"role": "system", "content": _DISEASE_EDGE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _disease_edge_user_prompt(product, disease, muc_do, edge["contributing_rows"]),
                },
            ]
        ),
        literal_merge_translate(edge["contributing_rows"], include_xu_tri=False),
    )
    patient_text, pharmacist_text = parse_tones(narrative_response.content or "")
    return {
        "san_pham": [product],
        "ten_benh": disease,
        "muc_do": muc_do,
        "giai_thich": filter_banned_language(patient_text),
        "giai_thich_duoc_si": filter_banned_language(pharmacist_text),
        "nguon_trich_dan": _fd_citation(pair_count),
        "mo_ta_dich": mo_ta_dich,
    }


async def build_food_interaction_explanations(
    rows: list[dict], ingredient_to_products: dict[str, list[str]]
) -> list[dict]:
    edges = build_food_edges(rows, ingredient_to_products)
    if not edges:
        return []
    return list(await asyncio.gather(*(_explain_food_edge(edge) for edge in edges)))


async def build_disease_interaction_explanations(
    rows: list[dict], ingredient_to_products: dict[str, list[str]]
) -> list[dict]:
    edges = build_disease_edges(rows, ingredient_to_products)
    if not edges:
        return []
    return list(await asyncio.gather(*(_explain_disease_edge(edge) for edge in edges)))


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
