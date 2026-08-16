"""Gộp (rollup) các cặp giải thích cấp hoạt chất lên cấp thuốc/sản phẩm và cấp đơn
thuốc, rồi gọi LLM sinh 1 đoạn giải thích RIÊNG cho từng cấp — chỉ nhắc tên ở đúng
cấp đó (thuốc/đơn thuốc), không lộ tên hoạt chất cụ thể — thay vì lấy nguyên văn
giải thích cấp hoạt chất như trước đây. Sống ngoài LangGraph (gọi từ src/api/routes.py
sau khi agent chạy xong) vì việc nhóm đơn thuốc là khái niệm của request, agent chỉ
biết tên hoạt chất."""

import asyncio

from src.agents.nodes.guardrail_node import filter_banned_language
from src.services.llm import ainvoke_llm
from src.services.tone_prompt import FORMAT_INSTRUCTIONS, SAFETY_RULES, parse_tones

_SEVERITY_RANK = {"nang": 3, "trung_binh": 2, "nhe": 1, "chua_phan_loai": 0}


def _severity_rank(muc_do: str | None) -> int:
    return _SEVERITY_RANK.get(muc_do, -1)


def _truncate(text: str | None, max_chars: int) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (đã rút gọn)"


def _edge_key(a: str, b: str) -> str:
    return "::".join(sorted([a.lower(), b.lower()]))


# ---- Gộp + dịch bám sát nghĩa (dùng chung cho cấp thuốc/thực phẩm/bệnh nền khi 1
# cạnh có NHIỀU cặp hoạt chất góp phần) ----

# Chỉ đưa tối đa từng này cặp vào 1 lượt dịch gộp - tránh phình prompt.
_MAX_LITERAL_MERGE_ITEMS = 5

_LITERAL_MERGE_SYSTEM_PROMPT_WITH_XU_TRI = (
    "Bạn là dược sĩ kiêm biên dịch y khoa. Dưới đây là Mô tả CSDL và Xử trí CSDL "
    "(tiếng Anh) của nhiều cặp tương tác khác nhau, cùng góp phần vào 1 cảnh báo tổng "
    "hợp. Hãy TỔNG HỢP các ý và DỊCH sang tiếng Việt, bám sát ĐÚNG ngữ nghĩa gốc — "
    "KHÔNG diễn giải lại theo văn phong tự nhiên/trò chuyện như một đoạn giải thích, "
    "KHÔNG thêm/bớt thông tin y khoa nào ngoài nội dung đã cho, chỉ gộp các ý trùng "
    "lặp và dịch trung thực, sát nghĩa nhất có thể. Trả lời ĐÚNG theo định dạng, "
    "không thêm chữ nào khác:\n"
    "Mô tả: <tổng hợp + dịch bám sát nghĩa Mô tả CSDL>\n"
    "Xử trí: <tổng hợp + dịch bám sát nghĩa Xử trí CSDL, để trống sau dấu hai chấm nếu không có>"
)

_LITERAL_MERGE_SYSTEM_PROMPT_MO_TA_ONLY = (
    "Bạn là dược sĩ kiêm biên dịch y khoa. Dưới đây là Mô tả CSDL (tiếng Anh) của "
    "nhiều cặp tương tác khác nhau, cùng góp phần vào 1 cảnh báo tổng hợp. Hãy TỔNG "
    "HỢP các ý và DỊCH sang tiếng Việt, bám sát ĐÚNG ngữ nghĩa gốc — KHÔNG diễn giải "
    "lại theo văn phong tự nhiên/trò chuyện như một đoạn giải thích, KHÔNG thêm/bớt "
    "thông tin y khoa nào ngoài nội dung đã cho, chỉ gộp các ý trùng lặp và dịch "
    "trung thực, sát nghĩa nhất có thể. Trả lời ĐÚNG theo định dạng, không thêm chữ "
    "nào khác:\n"
    "Mô tả: <tổng hợp + dịch bám sát nghĩa Mô tả CSDL>"
)


def _literal_merge_parse(raw: str) -> tuple[str | None, str | None]:
    mo_ta_dich, xu_tri_dich = None, None
    for line in (raw or "").strip().splitlines():
        line = line.strip()
        lower = line.lower()
        if lower.startswith("mô tả:") or lower.startswith("mo ta:"):
            mo_ta_dich = line.split(":", 1)[1].strip() or None
        elif lower.startswith("xử trí:") or lower.startswith("xu tri:"):
            xu_tri_dich = line.split(":", 1)[1].strip() or None
    return mo_ta_dich, xu_tri_dich


async def literal_merge_translate(
    items: list[dict], include_xu_tri: bool, max_items: int = _MAX_LITERAL_MERGE_ITEMS
) -> tuple[str | None, str | None]:
    """Gộp Mô tả/Xử trí CSDL (tiếng Anh, từ nhiều cặp góp phần đã sort severity-desc)
    thành 1 bản dịch DUY NHẤT, bám sát nghĩa gốc - KHÔNG đổi giọng điệu/cách viết tự
    nhiên như phần giai_thich (văn xuôi, đa dạng cách nói giữa các lần). Dùng chung
    cho cả 3 cấp (thuốc-thuốc/thực phẩm/bệnh nền) khi 1 cạnh có nhiều cặp góp phần
    cần gộp thành 1 thẻ - thay cho cách cũ chỉ lấy nguyên bản dịch của 1 cặp đại diện."""
    usable = [item for item in items[:max_items] if item.get("mo_ta")]
    if not usable:
        return None, None

    lines = []
    for i, item in enumerate(usable, start=1):
        block = f"Cặp {i}:\nMô tả CSDL: {_truncate(item.get('mo_ta'), 800)}"
        if include_xu_tri:
            block += f"\nXử trí CSDL: {_truncate(item.get('xu_tri'), 800) or '(không có)'}"
        lines.append(block)

    system_prompt = (
        _LITERAL_MERGE_SYSTEM_PROMPT_WITH_XU_TRI if include_xu_tri else _LITERAL_MERGE_SYSTEM_PROMPT_MO_TA_ONLY
    )
    response = await ainvoke_llm(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n\n".join(lines)},
        ]
    )
    return _literal_merge_parse(response.content or "")


def build_product_edges(explanations: list[dict]) -> list[dict]:
    """Port của buildProductGraph (frontend/lib/interactionGraph.ts): gộp các cặp
    hoạt chất (đã enrich san_pham_a/san_pham_b) thành cạnh cấp thuốc — mỗi cạnh giữ
    mức độ nặng nhất và danh sách các giải thích cấp hoạt chất góp phần (dùng làm
    dữ liệu gốc để sinh giải thích cấp thuốc - xem _explain_product_edge)."""
    edges: dict[str, dict] = {}
    for exp in explanations:
        muc_do = exp.get("muc_do")
        if not muc_do:
            continue
        prods_a = exp.get("san_pham_a") or ([exp["thuoc_a"]] if exp.get("thuoc_a") else [])
        prods_b = exp.get("san_pham_b") or ([exp["thuoc_b"]] if exp.get("thuoc_b") else [])
        incomplete = muc_do == "chua_phan_loai"

        for product_a in prods_a:
            for product_b in prods_b:
                if product_a.lower() == product_b.lower():
                    continue
                key = _edge_key(product_a, product_b)
                edge = edges.get(key)
                if edge is None:
                    edges[key] = {
                        "product_a": product_a,
                        "product_b": product_b,
                        "muc_do": muc_do,
                        "has_incomplete_pair": incomplete,
                        "contributing_pairs": [exp],
                    }
                    continue
                edge["contributing_pairs"].append(exp)
                edge["has_incomplete_pair"] = edge["has_incomplete_pair"] or incomplete
                if _severity_rank(muc_do) > _severity_rank(edge["muc_do"]):
                    edge["muc_do"] = muc_do

    for edge in edges.values():
        edge["pair_count"] = len(edge["contributing_pairs"])
        edge["contributing_pairs"].sort(key=lambda e: _severity_rank(e.get("muc_do")), reverse=True)

    return list(edges.values())


def filter_cross_prescription_edges(
    product_edges: list[dict], product_origins: dict[str, set[int]]
) -> list[dict]:
    """Chỉ giữ lại cạnh cấp thuốc có ÍT NHẤT 1 cặp chỉ số đơn khác nhau chứa 2 đầu
    cạnh - bỏ cạnh mà 2 thuốc chỉ CÙNG xuất hiện trong đúng 1 đơn (tương tác trong
    cùng 1 đơn). Dùng cho luồng bệnh nhân khi so từ 2 đơn trở lên: chỉ tính tương
    tác GIỮA các đơn khác nhau cho cấp thuốc + tóm tắt tổng quan."""
    filtered = []
    for edge in product_edges:
        set_a = product_origins.get(edge["product_a"].lower())
        set_b = product_origins.get(edge["product_b"].lower())
        if not set_a or not set_b:
            continue
        if any(rx_a != rx_b for rx_a in set_a for rx_b in set_b):
            filtered.append(edge)
    return filtered


def severity_counts(edges: list[dict]) -> dict[str, int]:
    """Đếm số cạnh theo từng mức độ - dùng cho thống kê tóm tắt (build_overview_explanation)."""
    counts = {"nang": 0, "trung_binh": 0, "nhe": 0, "chua_phan_loai": 0}
    for edge in edges:
        muc_do = edge.get("muc_do")
        if muc_do in counts:
            counts[muc_do] += 1
    return counts


def build_prescription_edges(
    product_edges: list[dict], product_origins: dict[str, set[int]]
) -> list[dict]:
    """Port của buildPrescriptionGraph: gộp cạnh cấp thuốc lên cấp đơn thuốc, dùng
    product_origins (tên thuốc viết thường -> tập chỉ số đơn chứa thuốc đó, theo
    đúng thứ tự prescriptions trong request) do routes.py truyền vào."""
    edges: dict[tuple[int, int], dict] = {}
    counted_products: dict[tuple[int, int], set[str]] = {}

    for pe in product_edges:
        set_a = product_origins.get(pe["product_a"].lower())
        set_b = product_origins.get(pe["product_b"].lower())
        if not set_a or not set_b:
            continue
        pe_key = _edge_key(pe["product_a"], pe["product_b"])

        for rx_a in set_a:
            for rx_b in set_b:
                if rx_a == rx_b:
                    continue
                i, j = (rx_a, rx_b) if rx_a < rx_b else (rx_b, rx_a)
                key = (i, j)
                seen_products = counted_products.setdefault(key, set())
                edge = edges.get(key)

                if pe_key in seen_products:
                    # Đã tính cạnh thuốc này cho đúng cặp đơn (i, j) rồi (2 thuốc
                    # cùng thuộc cả 2 đơn) - không cộng dồn pair_count 2 lần.
                    if edge is not None and _severity_rank(pe["muc_do"]) > _severity_rank(edge["muc_do"]):
                        edge["muc_do"] = pe["muc_do"]
                    continue

                seen_products.add(pe_key)
                if edge is None:
                    edges[key] = {
                        "rx_a_index": i,
                        "rx_b_index": j,
                        "muc_do": pe["muc_do"],
                        "has_incomplete_pair": pe["has_incomplete_pair"],
                        "pair_count": 1,
                    }
                else:
                    edge["pair_count"] += 1
                    edge["has_incomplete_pair"] = edge["has_incomplete_pair"] or pe["has_incomplete_pair"]
                    if _severity_rank(pe["muc_do"]) > _severity_rank(edge["muc_do"]):
                        edge["muc_do"] = pe["muc_do"]

    return list(edges.values())


# ---- Cấp thuốc (sản phẩm) ----

# Chỉ đưa tối đa từng này cặp hoạt chất (đã sắp nặng nhất trước) vào prompt cấp
# thuốc, để tránh phình prompt khi 2 thuốc phối hợp có nhiều hoạt chất - vẫn đủ
# đại diện vì các cặp còn lại thường nhẹ hơn cặp đã đưa vào.
_MAX_CONTRIBUTING_PAIRS = 5

_PRODUCT_SYSTEM_PROMPT = (
    "Bạn là dược sĩ đang tổng hợp cảnh báo tương tác GIỮA HAI THUỐC (cấp thuốc), "
    "dựa trên các giải thích tương tác hoạt chất CÓ THẬT giữa 2 thuốc này được liệt "
    "kê ở tin nhắn tiếp theo — đó là nguồn duy nhất bạn được dùng, không thêm dữ "
    "kiện y khoa nào khác. Hãy TỔNG HỢP LẠI thành 1 đoạn nói về việc dùng chung "
    "THUỐC A và THUỐC B (xưng tên thuốc là chính, không cần liệt kê lại từng hoạt "
    "chất), không chỉ đơn thuần dịch nguyên văn 1 cặp.\n\n"
    "Phần bệnh nhân: giọng gần gũi, thân thiện, ngắn gọn dễ hiểu (2-4 câu), nêu "
    "ngay việc dùng chung 2 thuốc này cần lưu ý và mức độ ra sao, tóm lược đúng "
    "bản chất rủi ro từ các giải thích được cung cấp.\n\n"
    "Phần dược sĩ: giọng khoa học, chuyên nghiệp, súc tích (2-3 câu), có thể nhắc "
    "ngắn gọn cơ chế/hoạt chất liên quan nếu dữ liệu cung cấp có đề cập, phù hợp để "
    "tra cứu nhanh.\n\n"
    f"{FORMAT_INSTRUCTIONS}\n\n{SAFETY_RULES}"
)

_UNCLASSIFIED_PRODUCT_MESSAGE = (
    "Giữa {a} và {b} có tương tác hoạt chất mà DDInter chưa phân loại mức độ "
    "nghiêm trọng — cần thận trọng, hãy hỏi dược sĩ/bác sĩ trước khi dùng chung."
)


def _product_citation(pair_count: int) -> str:
    return f"Tổng hợp từ {pair_count} cặp hoạt chất tương tác trong CSDL DDInter 2.0."


def _product_user_prompt(product_a: str, product_b: str, muc_do: str, contributing_pairs: list[dict]) -> str:
    lines = [f"Cặp thuốc: {product_a} + {product_b}", f"Mức độ nghiêm trọng cao nhất: {muc_do}", ""]
    lines.append("Các giải thích tương tác hoạt chất có thật giữa 2 thuốc này:")
    for pair in contributing_pairs[:_MAX_CONTRIBUTING_PAIRS]:
        lines.append(
            f"- Hoạt chất {pair.get('thuoc_a')} + {pair.get('thuoc_b')} (mức {pair.get('muc_do')}):\n"
            f"  Bản bệnh nhân: {pair.get('giai_thich', '')}\n"
            f"  Bản dược sĩ: {pair.get('giai_thich_duoc_si', '')}"
        )
    lines.append("")
    lines.append(
        "Hãy viết cả 2 phần theo đúng định dạng đã nêu, bằng tiếng Việt, tổng hợp lại "
        "đúng nội dung ở trên - không thêm dữ kiện nào ngoài đó."
    )
    return "\n".join(lines)


async def _explain_product_edge(edge: dict) -> dict:
    product_a, product_b = edge["product_a"], edge["product_b"]
    muc_do, pair_count = edge["muc_do"], edge["pair_count"]

    if muc_do == "chua_phan_loai":
        message = _UNCLASSIFIED_PRODUCT_MESSAGE.format(a=product_a, b=product_b)
        return {
            "thuoc_a": product_a,
            "thuoc_b": product_b,
            "muc_do": muc_do,
            "giai_thich": message,
            "giai_thich_duoc_si": message,
            "nguon_trich_dan": _product_citation(pair_count),
            "mo_ta_dich": None,
            "xu_tri_dich": None,
        }

    # 2 lượt gọi LLM ĐỘC LẬP chạy song song: 1 viết giải thích (giọng điệu tự nhiên,
    # đa dạng cách nói), 1 gộp + dịch bám sát nghĩa gốc (không đổi giọng điệu) - xem
    # literal_merge_translate.
    narrative_response, (mo_ta_dich, xu_tri_dich) = await asyncio.gather(
        ainvoke_llm(
            [
                {"role": "system", "content": _PRODUCT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _product_user_prompt(product_a, product_b, muc_do, edge["contributing_pairs"]),
                },
            ]
        ),
        literal_merge_translate(edge["contributing_pairs"], include_xu_tri=True),
    )
    patient_text, pharmacist_text = parse_tones(narrative_response.content)
    return {
        "thuoc_a": product_a,
        "thuoc_b": product_b,
        "muc_do": muc_do,
        "giai_thich": filter_banned_language(patient_text),
        "giai_thich_duoc_si": filter_banned_language(pharmacist_text),
        "nguon_trich_dan": _product_citation(pair_count),
        "mo_ta_dich": mo_ta_dich,
        "xu_tri_dich": xu_tri_dich,
    }


async def build_product_explanations(product_edges: list[dict]) -> list[dict]:
    if not product_edges:
        return []
    return list(await asyncio.gather(*(_explain_product_edge(edge) for edge in product_edges)))


# ---- Cấp đơn thuốc ----

_PRESCRIPTION_SYSTEM_PROMPT = (
    "Bạn là dược sĩ đang tổng hợp cảnh báo tương tác GIỮA HAI ĐƠN THUỐC (cấp đơn, "
    "KHÔNG phải cấp thuốc hay hoạt chất). Bạn CHỈ được cung cấp nhãn của 2 đơn "
    "thuốc, mức độ nghiêm trọng cao nhất ghi nhận được, và số cặp thuốc tương tác "
    "góp phần — hoàn toàn KHÔNG biết tên thuốc hay hoạt chất cụ thể nào bên trong "
    "từng đơn. Vì vậy TUYỆT ĐỐI KHÔNG được nêu, bịa, hay suy đoán tên thuốc/hoạt "
    "chất cụ thể — chỉ nói ở mức tổng quan cấp đơn thuốc, và gợi ý xem chi tiết cấp "
    "thuốc hoặc hỏi dược sĩ nếu cần biết cụ thể hơn.\n\n"
    "Phần bệnh nhân: giọng gần gũi, thân thiện, ngắn gọn dễ hiểu (2-3 câu).\n\n"
    "Phần dược sĩ: giọng khoa học, chuyên nghiệp, súc tích (1-2 câu).\n\n"
    f"{FORMAT_INSTRUCTIONS}\n\n{SAFETY_RULES}"
)

_UNCLASSIFIED_PRESCRIPTION_MESSAGE = (
    "Giữa {a} và {b} có tương tác thuốc mà DDInter chưa phân loại mức độ nghiêm "
    "trọng — cần thận trọng, hãy hỏi dược sĩ/bác sĩ trước khi dùng chung."
)


def _prescription_citation(pair_count: int) -> str:
    return (
        f"Tổng hợp từ {pair_count} cặp thuốc tương tác trong CSDL DDInter 2.0 — "
        "xem chi tiết ở cấp thuốc."
    )


def _prescription_user_prompt(label_a: str, label_b: str, muc_do: str, pair_count: int) -> str:
    return (
        f"Cặp đơn thuốc: {label_a} + {label_b}\n"
        f"Mức độ nghiêm trọng cao nhất: {muc_do}\n"
        f"Số cặp thuốc tương tác ghi nhận giữa 2 đơn này: {pair_count}\n\n"
        "Hãy viết cả 2 phần theo đúng định dạng đã nêu, bằng tiếng Việt."
    )


async def _explain_prescription_edge(edge: dict, labels: list[str]) -> dict:
    i, j = edge["rx_a_index"], edge["rx_b_index"]
    label_a = labels[i] if i < len(labels) else f"Đơn thuốc {i + 1}"
    label_b = labels[j] if j < len(labels) else f"Đơn thuốc {j + 1}"
    muc_do, pair_count = edge["muc_do"], edge["pair_count"]

    if muc_do == "chua_phan_loai":
        message = _UNCLASSIFIED_PRESCRIPTION_MESSAGE.format(a=label_a, b=label_b)
        return {
            "don_a": label_a,
            "don_b": label_b,
            "don_a_index": i,
            "don_b_index": j,
            "muc_do": muc_do,
            "giai_thich": message,
            "giai_thich_duoc_si": message,
            "nguon_trich_dan": _prescription_citation(pair_count),
        }

    response = await ainvoke_llm(
        [
            {"role": "system", "content": _PRESCRIPTION_SYSTEM_PROMPT},
            {"role": "user", "content": _prescription_user_prompt(label_a, label_b, muc_do, pair_count)},
        ]
    )
    patient_text, pharmacist_text = parse_tones(response.content)
    return {
        "don_a": label_a,
        "don_b": label_b,
        "don_a_index": i,
        "don_b_index": j,
        "muc_do": muc_do,
        "giai_thich": filter_banned_language(patient_text),
        "giai_thich_duoc_si": filter_banned_language(pharmacist_text),
        "nguon_trich_dan": _prescription_citation(pair_count),
    }


async def build_prescription_explanations(prescription_edges: list[dict], labels: list[str]) -> list[dict]:
    if not prescription_edges:
        return []
    return list(
        await asyncio.gather(*(_explain_prescription_edge(edge, labels) for edge in prescription_edges))
    )


# ---- Tóm tắt tổng quan (luồng bệnh nhân + luồng dược sĩ, 2 giọng điệu riêng) ----

# Chỉ đưa tối đa từng này cặp thuốc-thuốc (nặng nhất trước) vào prompt tóm tắt, để
# tránh phình prompt khi lần phân tích có rất nhiều thuốc/cặp tương tác.
_MAX_OVERVIEW_PAIRS = 8

_OVERVIEW_SYSTEM_PROMPT_PATIENT = (
    "Bạn là một dược sĩ đang tóm tắt TOÀN BỘ kết quả phân tích tương tác thuốc cho "
    "bệnh nhân, dựa trên thống kê và danh sách giải thích từng cặp thuốc-thuốc CÓ "
    "THẬT được liệt kê ở tin nhắn tiếp theo — đó là nguồn duy nhất bạn được dùng, "
    "không thêm dữ kiện y khoa nào khác.\n\n"
    "Viết 1 đoạn tổng quan bằng tiếng Việt (4-6 câu), giọng gần gũi, thân thiện, dễ "
    "hiểu, xưng \"mình\", gọi người đọc là \"bạn\":\n"
    "- Câu đầu nêu ngay bức tranh chung: có bao nhiêu cặp tương tác thuốc-thuốc "
    "được tìm thấy, chia theo mức độ (nghiêm trọng/trung bình/nhẹ/chưa phân loại) "
    "dựa đúng số liệu được cung cấp.\n"
    "- Các câu sau khái quát lại nội dung chính của những cặp đáng chú ý nhất (ưu "
    "tiên các cặp mức nghiêm trọng nếu có), không cần liệt kê hết từng cặp một.\n\n"
    "QUY TẮC BẮT BUỘC:\n"
    "- TUYỆT ĐỐI KHÔNG khuyên ngừng, đổi, kê đơn, hoặc tự ý điều chỉnh liều/thời "
    "điểm dùng bất kỳ thuốc nào — kể cả gợi ý mơ hồ.\n"
    "- TUYỆT ĐỐI KHÔNG chẩn đoán bệnh hay tình trạng sức khỏe của người dùng.\n"
    "- CHỈ dựa trên đúng thống kê và giải thích được cung cấp — không thêm dữ kiện "
    "y khoa nào khác.\n"
    "- Khép lại bằng việc nhắc trao đổi với dược sĩ/bác sĩ nếu cần biết cụ thể hơn, "
    "diễn đạt tự nhiên, không phải khẩu hiệu dán cứng."
)

_OVERVIEW_SYSTEM_PROMPT_PHARMACIST = (
    "Bạn là dược sĩ lâm sàng đang tóm tắt TOÀN BỘ kết quả phân tích tương tác thuốc "
    "để trình bày cho một dược sĩ khác đang tra cứu, dựa trên thống kê và danh sách "
    "giải thích từng cặp thuốc-thuốc CÓ THẬT được liệt kê ở tin nhắn tiếp theo — đó "
    "là nguồn duy nhất bạn được dùng, không thêm dữ kiện y khoa nào khác.\n\n"
    "Viết 1 đoạn tổng quan bằng tiếng Việt (4-6 câu), văn phong khoa học, chuyên "
    "nghiệp, học thuật và lịch sự, phù hợp trao đổi giữa các dược sĩ - hạn chế xưng "
    "hô trực tiếp, có thể dùng thuật ngữ dược lý/dược động học khi dữ liệu có đề cập "
    "(cơ chế, enzym, thụ thể, nồng độ huyết tương...):\n"
    "- Câu đầu nêu ngay số liệu tổng quan: tổng số cặp tương tác thuốc-thuốc ghi "
    "nhận được, chia theo mức độ (nghiêm trọng/trung bình/nhẹ/chưa phân loại) dựa "
    "đúng số liệu được cung cấp.\n"
    "- Các câu sau khái quát bản chất và cơ chế của những cặp đáng chú ý nhất (ưu "
    "tiên các cặp mức nghiêm trọng nếu có), không cần liệt kê hết từng cặp một.\n\n"
    "QUY TẮC BẮT BUỘC:\n"
    "- TUYỆT ĐỐI KHÔNG khuyên ngừng, đổi, kê đơn, hoặc tự ý điều chỉnh liều/thời "
    "điểm dùng bất kỳ thuốc nào — kể cả gợi ý mơ hồ.\n"
    "- CHỈ dựa trên đúng thống kê và giải thích được cung cấp — không thêm dữ kiện "
    "y khoa nào khác.\n"
    "- Khép lại bằng việc nhắc xem chi tiết từng cặp thuốc để có đầy đủ căn cứ trước "
    "khi ra quyết định lâm sàng, diễn đạt tự nhiên, không phải khẩu hiệu dán cứng."
)

_NO_INTERACTION_OVERVIEW_MESSAGE_PATIENT = (
    "Mình không tìm thấy tương tác nào giữa các thuốc bạn đã chọn trong CSDL "
    "DDInter 2.0 lần này. Nếu có thêm thuốc mới hoặc thay đổi liều, hãy kiểm tra "
    "lại hoặc hỏi dược sĩ/bác sĩ để chắc chắn nhé."
)

_NO_INTERACTION_OVERVIEW_MESSAGE_PHARMACIST = (
    "Không ghi nhận tương tác nào giữa các thuốc đã chọn trong cơ sở dữ liệu "
    "DDInter 2.0 ở lần phân tích này. Khi danh mục thuốc thay đổi, khuyến nghị thực "
    "hiện tra cứu lại để đảm bảo dữ liệu được cập nhật đầy đủ."
)


_MAX_OVERVIEW_EDGE_SUMMARY_CHARS = 500


def _overview_edge_summary(edge: dict) -> str:
    """Tóm tắt ngắn 1 dòng cho 1 cạnh cấp thuốc, đọc THẲNG dữ liệu gốc (mô tả CSDL
    của cặp hoạt chất góp phần nặng nhất - contributing_pairs đã sort severity-desc)
    - KHÔNG đọc lại đoạn văn product_explanations đã viết, để overview không phải đợi
    build_product_explanations chạy xong (xem build_overview_explanation).

    Đang dùng thẳng mo_ta gốc tiếng Anh (KHÔNG ưu tiên mo_ta_dich đã cache) theo yêu
    cầu test - bỏ qua phụ thuộc vào batch dịch cache còn đang dở dang."""
    if edge.get("muc_do") == "chua_phan_loai":
        return "DDInter chưa phân loại mức độ nghiêm trọng cho tương tác này."
    representative = edge["contributing_pairs"][0] if edge["contributing_pairs"] else {}
    text = representative.get("mo_ta") or ""
    return _truncate(text, _MAX_OVERVIEW_EDGE_SUMMARY_CHARS)


def _overview_user_prompt(counts: dict[str, int], product_edges: list[dict]) -> str:
    total = sum(counts.values())
    lines = [
        f"Tổng số cặp thuốc-thuốc có tương tác: {total}",
        f"- Mức nghiêm trọng: {counts['nang']}",
        f"- Mức trung bình: {counts['trung_binh']}",
        f"- Mức nhẹ: {counts['nhe']}",
        f"- Chưa phân loại: {counts['chua_phan_loai']}",
        "",
        "Danh sách dữ liệu gốc (CSDL DDInter 2.0) từng cặp thuốc-thuốc, đã sắp nặng nhất trước:",
    ]
    sorted_edges = sorted(product_edges, key=lambda e: _severity_rank(e.get("muc_do")), reverse=True)
    for edge in sorted_edges[:_MAX_OVERVIEW_PAIRS]:
        lines.append(
            f"- {edge.get('product_a')} + {edge.get('product_b')} (mức {edge.get('muc_do')}): "
            f"{_overview_edge_summary(edge)}"
        )
    lines.append("")
    lines.append("Hãy viết đoạn tổng quan theo đúng hướng dẫn ở trên, bằng tiếng Việt.")
    return "\n".join(lines)


async def build_overview_explanation(product_edges: list[dict], audience: str = "patient") -> dict:
    """Sinh 1 đoạn tóm tắt tổng quan toàn bộ lần phân tích - thống kê số cặp
    thuốc-thuốc theo mức độ + tổng hợp TRỰC TIẾP từ dữ liệu gốc trong product_edges
    (contributing_pairs, đã có bản dịch cache sẵn) - KHÔNG còn đọc product_explanations
    (đoạn văn rollup cấp thuốc do LLM khác viết) làm nguyên liệu như trước, để overview
    không phải đợi build_product_explanations chạy xong mà chạy SONG SONG được với nó
    (xem routes.py::_run_product_check). audience="patient"|"pharmacist" chỉ còn ảnh
    hưởng tới giọng điệu system prompt, không ảnh hưởng dữ liệu nguồn đưa vào."""
    counts = severity_counts(product_edges)
    total = sum(counts.values())
    is_pharmacist = audience == "pharmacist"

    if total == 0:
        giai_thich = (
            _NO_INTERACTION_OVERVIEW_MESSAGE_PHARMACIST if is_pharmacist else _NO_INTERACTION_OVERVIEW_MESSAGE_PATIENT
        )
    else:
        system_prompt = _OVERVIEW_SYSTEM_PROMPT_PHARMACIST if is_pharmacist else _OVERVIEW_SYSTEM_PROMPT_PATIENT
        response = await ainvoke_llm(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _overview_user_prompt(counts, product_edges)},
            ]
        )
        giai_thich = filter_banned_language((response.content or "").strip())

    return {
        "giai_thich": giai_thich,
        "so_cap_nang": counts["nang"],
        "so_cap_trung_binh": counts["trung_binh"],
        "so_cap_nhe": counts["nhe"],
        "so_cap_chua_phan_loai": counts["chua_phan_loai"],
        "tong_so_cap": total,
    }
