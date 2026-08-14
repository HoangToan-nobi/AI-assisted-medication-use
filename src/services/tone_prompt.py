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
