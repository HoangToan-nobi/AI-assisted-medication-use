"""Khung prompt dùng chung cho mọi cấp (hoạt chất/thuốc/đơn thuốc): định dạng đầu ra
2 giọng điệu (bệnh nhân/dược sĩ) + các quy tắc an toàn bắt buộc, để 3 nơi gọi LLM
(explain_node cấp hoạt chất, rollup_explain cấp thuốc và cấp đơn) không lặp lại và
không lệch nhau."""

TONE_PATIENT_MARKER = "[BỆNH_NHÂN]"
TONE_PHARMACIST_MARKER = "[DƯỢC_SĨ]"

FORMAT_INSTRUCTIONS = (
    "Trả lời theo ĐÚNG định dạng sau, không thêm chữ nào khác ngoài 2 phần này:\n"
    f"{TONE_PATIENT_MARKER}\n"
    "<đoạn văn dành cho bệnh nhân>\n"
    f"{TONE_PHARMACIST_MARKER}\n"
    "<đoạn văn dành cho dược sĩ>"
)

SAFETY_RULES = (
    "QUY TẮC BẮT BUỘC (áp dụng cho CẢ HAI phần bên trên):\n"
    "- TUYỆT ĐỐI KHÔNG khuyên ngừng, đổi, kê đơn, hoặc tự ý điều chỉnh liều/thời "
    "điểm dùng bất kỳ thuốc nào - kể cả gợi ý mơ hồ, không nêu con số cụ thể (ví dụ "
    "\"uống cách xa nhau\", \"đừng dùng gần nhau\", \"giãn cách ra\"). Quyết định xử "
    "trí luôn thuộc về bác sĩ/dược sĩ.\n"
    "- TUYỆT ĐỐI KHÔNG chẩn đoán bệnh hay tình trạng sức khỏe của người dùng.\n"
    "- CHỈ diễn giải lại đúng thông tin dữ liệu được cung cấp trong tin nhắn tiếp "
    "theo - không thêm dữ kiện y khoa, tên hoạt chất, cơ chế, hay con số nào không "
    "có trong đó.\n"
    "- Luôn khép mỗi phần bằng việc nhắc trao đổi với dược sĩ/bác sĩ nếu cần biết cụ "
    "thể hơn, diễn đạt tự nhiên, không phải khẩu hiệu dán cứng."
)


def parse_tones(raw: str) -> tuple[str, str]:
    """Tách phản hồi LLM thành (bản bệnh nhân, bản dược sĩ). Nếu LLM không theo đúng
    định dạng 2 marker, dùng nguyên văn cho cả hai để không mất nội dung."""
    text = (raw or "").strip()
    if TONE_PATIENT_MARKER in text and TONE_PHARMACIST_MARKER in text:
        _, rest = text.split(TONE_PATIENT_MARKER, 1)
        patient_part, pharmacist_part = rest.split(TONE_PHARMACIST_MARKER, 1)
        patient_part = patient_part.strip()
        pharmacist_part = pharmacist_part.strip()
        if patient_part and pharmacist_part:
            return patient_part, pharmacist_part
    return text, text


# Marker cho phần thứ 3 (bản dịch nguyên văn không qua diễn giải) - dùng ở những nơi
# cần dịch thẳng mô tả/xử trí gốc từ CSDL DDInter (hoạt chất-hoạt chất, hoạt chất-thực
# phẩm, hoạt chất-bệnh nền) song song với 2 giọng điệu ở trên, chỉ dược sĩ mới thấy.
TRANSLATION_MARKER = "[BẢN_DỊCH]"


def split_translation_block(raw: str, labels: list[tuple[str, str]]) -> tuple[str, dict[str, str | None]]:
    """Tách phần dịch nguyên văn (bắt đầu bằng TRANSLATION_MARKER, LLM luôn đặt SAU
    2 phần giọng điệu) ra khỏi phần còn lại TRƯỚC khi gọi parse_tones - nếu không tách
    trước, parse_tones sẽ dính luôn đoạn dịch vào cuối bản dược sĩ vì nó chỉ biết dừng
    ở hết chuỗi.

    labels: danh sách (nhãn dòng viết thường có dấu ':', tên field kết quả), ví dụ
    [("mô tả:", "mo_ta_dich"), ("xử trí:", "xu_tri_dich")] - đúng thứ tự đã yêu cầu
    LLM trả về trong phần hướng dẫn định dạng. Trả về (phần còn lại để đưa cho
    parse_tones, dict tên field -> giá trị hoặc None nếu thiếu/không có).
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
