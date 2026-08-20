"""Khung prompt dùng chung cho mọi cấp (hoạt chất/thuốc/đơn thuốc/thực phẩm/bệnh
nền): quy tắc an toàn bắt buộc, để các nơi gọi LLM sinh giải thích không lặp lại
và không lệch nhau.

Trước đây module này còn giữ FORMAT_INSTRUCTIONS/parse_tones/2 marker để 1 lệnh
gọi LLM sinh CẢ 2 giọng điệu (bệnh nhân + dược sĩ) cùng lúc - đã bỏ vì audience
không dùng tới luôn bị vứt đi ở MỌI luồng trong app (guest không lưu + bị strip
trước khi gửi; patient-check được dược sĩ review vẫn hiện giọng bệnh nhân theo
đúng thiết kế; pharmacist-lookup không patient nào xem được) - tốn gấp đôi token
output vô ích. Giờ mỗi lệnh gọi chỉ sinh 1 giọng khớp audience đã biết trước tại
nơi gọi (xem src/agents/state.py::audience, src/agents/nodes/explain_node.py)."""

SAFETY_RULES = (
    "QUY TẮC BẮT BUỘC:\n"
    "- TUYỆT ĐỐI KHÔNG khuyên ngừng, đổi, kê đơn, hoặc tự ý điều chỉnh liều/thời "
    "điểm dùng bất kỳ thuốc nào - kể cả gợi ý mơ hồ, không nêu con số cụ thể (ví dụ "
    "\"uống cách xa nhau\", \"đừng dùng gần nhau\", \"giãn cách ra\"). Quyết định xử "
    "trí luôn thuộc về bác sĩ/dược sĩ.\n"
    "- TUYỆT ĐỐI KHÔNG chẩn đoán bệnh hay tình trạng sức khỏe của người dùng.\n"
    "- CHỈ diễn giải lại đúng thông tin dữ liệu được cung cấp trong tin nhắn tiếp "
    "theo - không thêm dữ kiện y khoa, tên hoạt chất, cơ chế, hay con số nào không "
    "có trong đó."
)


# Marker cho phần dịch nguyên văn (không qua diễn giải) - dùng ở những nơi cần dịch
# thẳng mô tả/xử trí gốc từ CSDL DDInter (hoạt chất-hoạt chất, hoạt chất-thực phẩm,
# hoạt chất-bệnh nền) song song với đoạn giải thích ở trên, chỉ dược sĩ mới thấy.
TRANSLATION_MARKER = "[BẢN_DỊCH]"


def split_translation_block(raw: str, labels: list[tuple[str, str]]) -> tuple[str, dict[str, str | None]]:
    """Tách phần dịch nguyên văn (bắt đầu bằng TRANSLATION_MARKER) ra khỏi phần còn
    lại của phản hồi LLM.

    labels: danh sách (nhãn dòng viết thường có dấu ':', tên field kết quả), ví dụ
    [("mô tả:", "mo_ta_dich"), ("xử trí:", "xu_tri_dich")] - đúng thứ tự đã yêu cầu
    LLM trả về trong phần hướng dẫn định dạng. Trả về (phần còn lại, dict tên field
    -> giá trị hoặc None nếu thiếu/không có).
    """
    values: dict[str, str | None] = {key: None for _, key in labels}
    if TRANSLATION_MARKER not in raw:
        return raw, values
    rest, block = raw.split(TRANSLATION_MARKER, 1)
    for line in block.strip().splitlines():
        line = line.strip()
        lower = line.lower()
        for label, key in labels:
            if lower.startswith(label):
                values[key] = line.split(":", 1)[1].strip() or None
                break
    return rest, values
