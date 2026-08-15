from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="Tin nhắn từ user")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Phản hồi từ agent")
    analysis: str = Field(default="", description="Phân tích nội bộ")


# ---- Auth ----


class RegisterRequest(BaseModel):
    ho_ten: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=3, max_length=255)
    mat_khau: str = Field(..., min_length=6, max_length=255)
    vai_tro: Literal["patient", "pharmacist"]


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    mat_khau: str = Field(..., min_length=1, max_length=255)


class AuthResponse(BaseModel):
    access_token: str
    vai_tro: str
    user_id: str
    ho_ten: str


# ---- Medications (hồ sơ thuốc bệnh nhân) ----


class MedicationItem(BaseModel):
    id: str  # id của bản ghi patient_medications - dùng để xóa
    product_id: str
    ten_thuoc: str
    prescription_id: str
    ngay_bat_dau: date | None = None
    ngay_ket_thuc: date | None = None


class AddMedicationRequest(BaseModel):
    medication_name: str = Field(..., min_length=1, max_length=255)


# ---- Đơn thuốc đã lưu trong hồ sơ (tab "Đơn thuốc của tôi") ----


class PatientPrescriptionSummary(BaseModel):
    id: str
    label: str
    medications: list[MedicationItem]


class CreatePrescriptionRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)


class RenamePrescriptionRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)


class MedicationSearchResult(BaseModel):
    id: str
    ten_chuan_hoa: str


# ---- Thuốc theo tên biệt dược (Product) ----


class ProductSearchResult(BaseModel):
    id: str
    ten_thuoc: str


class PrescriptionInput(BaseModel):
    """1 đơn thuốc gửi lên từ frontend - "đơn thuốc" chỉ là khái niệm ở phía người
    dùng nhập liệu, backend dùng label + danh sách thuốc này để tự tính cạnh cấp
    thuốc/cấp đơn thuốc và sinh giải thích tương ứng (rollup_explain.py)."""

    label: str = Field(..., min_length=1, max_length=100)
    products: list[str] = Field(..., min_length=1)


class ProductCheckRequest(BaseModel):
    prescriptions: list[PrescriptionInput] = Field(..., min_length=1)


class AddProductRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=500)
    # Tùy chọn - nếu bỏ trống, route tự gán vào đơn mặc định của bệnh nhân (tạo mới
    # nếu chưa có đơn nào), giữ tương thích ngược với các client cũ chưa biết khái
    # niệm "đơn thuốc" (VD test_add_and_list_patient_medications không gửi field này).
    prescription_id: str | None = None


# ---- Kiểm tra tương tác ----


class MedicationCheckRequest(BaseModel):
    medications: list[str] = Field(..., min_length=1)


class MedicationCheckResponse(BaseModel):
    interaction_check_id: str
    ranked_results: list[dict]
    explanations: list[dict]
    has_severe: bool
    has_unclassified: bool
    # Chỉ có ở luồng kiểm tra theo tên thuốc (products/check) - tên thuốc không tìm thấy
    # trong CSDL, hoặc tìm thấy nhưng chưa có hoạt chất nào khớp DDInter để tra tương tác.
    unknown_products: list[str] = Field(default_factory=list)
    no_interaction_data_products: list[str] = Field(default_factory=list)
    # Toàn bộ tên thuốc đã nhập ở lần kiểm tra này (kể cả thuốc không có tương tác
    # với thuốc nào khác) - dùng để vẽ đủ node trên đồ thị khi xem lại lịch sử/dược
    # sĩ review, thay vì suy ra danh sách thuốc từ các cặp trong explanations (sẽ
    # thiếu thuốc không có cặp tương tác nào).
    checked_products: list[str] = Field(default_factory=list)
    # Đúng cấu trúc đơn thuốc gốc đã gửi lên (label + danh sách thuốc mỗi đơn), theo
    # đúng thứ tự khớp với don_a_index/don_b_index của prescription_explanations -
    # để xem lại lịch sử/dược sĩ review vẫn dựng được đúng "bàn cân" nhiều đơn như
    # lúc kiểm tra, thay vì gộp hết thuốc vào 1 đơn ảo duy nhất (mất khả năng lọc
    # tương tác GIỮA các đơn). Rỗng ở dữ liệu lịch sử cũ lưu trước khi field này tồn tại.
    prescriptions: list[PrescriptionInput] = Field(default_factory=list)
    # Giải thích riêng cấp thuốc (thuốc-với-thuốc) và cấp đơn thuốc (đơn-với-đơn),
    # chỉ nhắc tên ở đúng cấp đó - KHÔNG lấy nguyên văn giải thích cấp hoạt chất
    # trong `explanations` như trước. prescription_explanations chỉ khác rỗng ở
    # luồng dược sĩ (pharmacist/products/check) khi request có từ 2 đơn trở lên.
    product_explanations: list[dict] = Field(default_factory=list)
    prescription_explanations: list[dict] = Field(default_factory=list)
    # Tóm tắt tổng quan toàn bộ lần phân tích - sinh cho cả luồng bệnh nhân và dược
    # sĩ, khác nhau ở giọng điệu (xem build_overview_explanation).
    overview: dict | None = None
    # Tương tác thuốc-thực phẩm/thuốc-bệnh nền (DDInter 2.0 DFI/DDSI) - thông tin
    # CHUNG theo từng hoạt chất đang kiểm tra, không lọc theo hồ sơ bệnh nền cá nhân
    # (xem food_disease_explain.py). mo_ta_dich/xu_tri_dich chỉ dược sĩ mới thấy.
    food_interactions: list[dict] = Field(default_factory=list)
    disease_interactions: list[dict] = Field(default_factory=list)
    # Câu liệt kê cố định (không qua LLM) tên thực phẩm/bệnh nền cần lưu ý, ghép thêm
    # vào bảng tóm tắt tổng quan sau đoạn overview.giai_thich do LLM sinh.
    canh_bao_thuc_pham_benh_nen: str | None = None
    # Ghi chú dược sĩ để lại khi xác nhận lần kiểm tra này (PharmacistReview.ghi_chu)
    # - chỉ có ở GET /patients/{id}/checks/{check_id} khi đã có dược sĩ xác nhận,
    # None ở mọi trường hợp khác (lần kiểm tra mới chạy, guest, chưa ai xác nhận).
    ghi_chu_duoc_si: str | None = None
    ten_duoc_si_xac_nhan: str | None = None
    # Câu hỏi bệnh nhân đã gửi kèm yêu cầu xét duyệt (nếu có) và câu trả lời tương
    # ứng của dược sĩ - cùng điều kiện hiển thị với ghi_chu_duoc_si ở trên (chỉ có
    # ở getPatientCheckDetail khi đã có dược sĩ xác nhận).
    cau_hoi_benh_nhan: str | None = None
    cau_tra_loi_duoc_si: str | None = None


class InteractionCheckSummary(BaseModel):
    id: str
    thoi_gian_kiem_tra: datetime
    co_canh_bao_nang: bool
    co_chua_phan_loai: bool
    trang_thai_xac_nhan: str


# ---- Dược sĩ ----


class PharmacistSummary(BaseModel):
    id: str
    ho_ten: str
    noi_cong_tac: str | None = None
    mo_ta_ngan: str | None = None


class ReviewRequestSummary(BaseModel):
    check_id: str
    patient_id: str
    patient_name: str
    thoi_gian_kiem_tra: datetime
    co_canh_bao_nang: bool
    trang_thai_xac_nhan: str
    # Ngữ cảnh bệnh nhân gửi kèm lúc nhờ xác nhận (xem RequestReviewRequest) - đưa
    # thẳng vào đây để trang review dược sĩ lấy được luôn từ listPharmacistRequests,
    # khỏi cần gọi thêm endpoint riêng.
    gui_kem_ho_so: bool = False
    ten_nguoi_duoc_kiem_tra: str | None = None
    ngay_sinh_nhap_tay: date | None = None
    ghi_chu_nhap_tay: str | None = None
    # Nội dung và thời điểm dược sĩ đã xác nhận, để có thể mở lại hồ sơ đã xử lý
    # ở chế độ chỉ xem mà không cần tạo một lượt xác nhận mới.
    ghi_chu: str | None = None
    thoi_gian_xac_nhan: datetime | None = None
    # Câu hỏi bệnh nhân gửi kèm (không bắt buộc) và câu trả lời tương ứng của dược
    # sĩ - tách riêng khỏi ghi_chu (nhận xét chung).
    cau_hoi: str | None = None
    cau_tra_loi: str | None = None


class RequestReviewRequest(BaseModel):
    """Ngữ cảnh bệnh nhân chọn gửi kèm khi nhờ dược sĩ xác nhận 1 lần tra cứu - gửi
    hồ sơ cá nhân CỦA CHÍNH MÌNH (gui_kem_ho_so=True), hoặc tự nhập thông tin cho
    trường hợp tra cứu hộ người khác (3 field dưới), hoặc không gửi gì cả."""

    gui_kem_ho_so: bool = False
    ten_nguoi_duoc_kiem_tra: str | None = Field(default=None, max_length=255)
    ngay_sinh_nhap_tay: date | None = None
    ghi_chu_nhap_tay: str | None = Field(default=None, max_length=2000)
    # Câu hỏi muốn hỏi dược sĩ về lần kiểm tra này - không bắt buộc.
    cau_hoi: str | None = Field(default=None, max_length=2000)


class PharmacistReviewRequest(BaseModel):
    interaction_check_id: str = Field(..., min_length=1)
    ghi_chu: str = Field(default="", max_length=2000)
    # Câu trả lời cho cau_hoi bệnh nhân đã gửi (nếu có) - không bắt buộc, vì bệnh
    # nhân có thể không hỏi gì cả lúc gửi yêu cầu.
    cau_tra_loi: str | None = Field(default=None, max_length=2000)


class PharmacistReviewResponse(BaseModel):
    id: str
    interaction_check_id: str
    trang_thai_xac_nhan: str
    ghi_chu: str
    cau_tra_loi: str | None = None


# ---- Hồ sơ cá nhân dược sĩ ----


class PharmacistProfileInfo(BaseModel):
    ho_ten: str | None = None
    noi_cong_tac: str | None = None
    mo_ta_ngan: str | None = None


class UpdatePharmacistProfileRequest(BaseModel):
    ho_ten: str | None = Field(default=None, max_length=255)
    noi_cong_tac: str | None = Field(default=None, max_length=255)
    mo_ta_ngan: str | None = Field(default=None, max_length=2000)


# ---- Thông báo ----


class NotificationItem(BaseModel):
    id: str
    noi_dung: str
    da_doc: bool
    thoi_gian_tao: datetime
    interaction_check_id: str | None = None


# ---- Hồ sơ cá nhân bệnh nhân ----


class PatientProfileInfo(BaseModel):
    ho_ten: str | None = None
    ngay_sinh: date | None = None
    gioi_tinh: str | None = None
    can_nang: float | None = None
    chieu_cao: float | None = None
    benh_nen_ghi_chu: str | None = None
    di_ung_thuoc: str | None = None
    tinh_trang_khac: str | None = None


class UpdatePatientProfileRequest(BaseModel):
    ho_ten: str | None = Field(default=None, max_length=255)
    ngay_sinh: date | None = None
    gioi_tinh: str | None = Field(default=None, max_length=20)
    can_nang: float | None = None
    chieu_cao: float | None = None
    benh_nen_ghi_chu: str | None = Field(default=None, max_length=2000)
    di_ung_thuoc: str | None = Field(default=None, max_length=2000)
    tinh_trang_khac: str | None = Field(default=None, max_length=2000)
