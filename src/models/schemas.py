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
    medication_id: str
    ten_chuan_hoa: str
    ngay_bat_dau: date | None = None
    ngay_ket_thuc: date | None = None


class AddMedicationRequest(BaseModel):
    medication_name: str = Field(..., min_length=1, max_length=255)


class MedicationSearchResult(BaseModel):
    id: str
    ten_chuan_hoa: str


# ---- Kiểm tra tương tác ----


class MedicationCheckRequest(BaseModel):
    medications: list[str] = Field(..., min_length=1)


class MedicationCheckResponse(BaseModel):
    interaction_check_id: str
    ranked_results: list[dict]
    explanations: list[dict]
    has_severe: bool
    has_unclassified: bool
    # Ghi chú của dược sĩ (nếu đã xác nhận) - None nếu chưa ai xác nhận lần kiểm tra này.
    ghi_chu: str | None = None


class InteractionCheckSummary(BaseModel):
    id: str
    thoi_gian_kiem_tra: datetime
    co_canh_bao_nang: bool
    co_chua_phan_loai: bool
    trang_thai_xac_nhan: str


# ---- Dược sĩ ----


class PatientSummary(BaseModel):
    id: str
    ho_ten: str
    co_canh_bao_nang_chua_xu_ly: bool


class PharmacistReviewRequest(BaseModel):
    interaction_check_id: str = Field(..., min_length=1)
    ghi_chu: str = Field(default="", max_length=2000)


class PharmacistReviewResponse(BaseModel):
    id: str
    interaction_check_id: str
    trang_thai_xac_nhan: str
    ghi_chu: str
