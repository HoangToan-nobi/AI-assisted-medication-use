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
    ngay_bat_dau: date | None = None
    ngay_ket_thuc: date | None = None


class AddMedicationRequest(BaseModel):
    medication_name: str = Field(..., min_length=1, max_length=255)


class MedicationSearchResult(BaseModel):
    id: str
    ten_chuan_hoa: str


# ---- Thuốc theo tên biệt dược (Product) ----


class ProductSearchResult(BaseModel):
    id: str
    ten_thuoc: str


class ProductCheckRequest(BaseModel):
    products: list[str] = Field(..., min_length=1)


class AddProductRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=500)


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


class ReviewRequestSummary(BaseModel):
    check_id: str
    patient_id: str
    patient_name: str
    thoi_gian_kiem_tra: datetime
    co_canh_bao_nang: bool
    trang_thai_xac_nhan: str


class PharmacistReviewRequest(BaseModel):
    interaction_check_id: str = Field(..., min_length=1)
    ghi_chu: str = Field(default="", max_length=2000)


class PharmacistReviewResponse(BaseModel):
    id: str
    interaction_check_id: str
    trang_thai_xac_nhan: str
    ghi_chu: str


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
