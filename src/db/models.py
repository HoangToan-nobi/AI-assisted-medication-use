"""SQLAlchemy models — khớp Data Model đã thiết kế ở Giai đoạn 2 (mục 5)."""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    ho_ten = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    mat_khau_hash = Column(String(255), nullable=False)
    vai_tro = Column(String(20), nullable=False)  # patient | pharmacist
    ngay_tao = Column(DateTime, default=datetime.utcnow)


class PatientProfile(Base):
    __tablename__ = "patient_profiles"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    ngay_sinh = Column(Date)
    benh_nen_ghi_chu = Column(Text)


class PharmacistAssignment(Base):
    __tablename__ = "pharmacist_assignments"
    id = Column(String, primary_key=True, default=_uuid)
    pharmacist_id = Column(String, ForeignKey("users.id"))
    patient_id = Column(String, ForeignKey("users.id"))


class Medication(Base):
    __tablename__ = "medications"
    id = Column(String, primary_key=True, default=_uuid)
    ten_chuan_hoa = Column(String(255), nullable=False)
    ten_biet_duoc = Column(String(255))
    hoat_chat = Column(String(255))
    nguon_du_lieu = Column(String(100))
    mo_ta = Column(Text)  # DDInter Description


class MedicationAlias(Base):
    """Bảng alias/viết tắt thủ công — DDInter không có cột alias riêng.

    Trỏ thẳng vào medication_id thật thay vì tên tự do, để drug_normalizer_tool
    không phải suy đoán ngoài CSDL.
    """

    __tablename__ = "medication_aliases"
    id = Column(String, primary_key=True, default=_uuid)
    alias = Column(String(255), unique=True, nullable=False)
    medication_id = Column(String, ForeignKey("medications.id"), nullable=False)


class PatientMedication(Base):
    __tablename__ = "patient_medications"
    id = Column(String, primary_key=True, default=_uuid)
    patient_id = Column(String, ForeignKey("users.id"))
    medication_id = Column(String, ForeignKey("medications.id"))
    ngay_bat_dau = Column(Date)
    ngay_ket_thuc = Column(Date)


class Interaction(Base):
    __tablename__ = "interactions"
    __table_args__ = (
        UniqueConstraint("medication_a_id", "medication_b_id", name="uq_interaction_pair"),
    )
    id = Column(String, primary_key=True, default=_uuid)
    # Quy ước bắt buộc khi ghi/đọc: medication_a_id < medication_b_id (so sánh chuỗi)
    # để mỗi cặp thuốc chỉ có đúng 1 bản ghi, tránh phải OR 2 chiều khi tra cứu.
    medication_a_id = Column(String, ForeignKey("medications.id"), nullable=False)
    medication_b_id = Column(String, ForeignKey("medications.id"), nullable=False)
    muc_do = Column(String(20))  # nhe | trung_binh | nang | chua_phan_loai
    mo_ta = Column(Text)
    xu_tri = Column(Text)  # DDInter Management — CHỈ hiển thị cho vai trò dược sĩ
    nguon_trich_dan = Column(Text)
    thay_the_a = Column(Text)  # DDInter Alt_for_A — tham khảo cho dược sĩ, KHÔNG dùng để agent tự đề xuất đổi thuốc
    thay_the_b = Column(Text)  # DDInter Alt_for_B


class InteractionCheck(Base):
    __tablename__ = "interaction_checks"
    id = Column(String, primary_key=True, default=_uuid)
    patient_id = Column(String, ForeignKey("users.id"))
    ket_qua_json = Column(JSON)
    # Cờ trích từ ket_qua_json (has_severe/has_unclassified) — cột riêng để
    # truy vấn/lọc hàng đợi ưu tiên dược sĩ mà không cần parse JSON mỗi lần.
    co_canh_bao_nang = Column(Boolean, default=False)
    co_chua_phan_loai = Column(Boolean, default=False)
    thoi_gian_kiem_tra = Column(DateTime, default=datetime.utcnow)


class PharmacistReview(Base):
    __tablename__ = "pharmacist_reviews"
    id = Column(String, primary_key=True, default=_uuid)
    interaction_check_id = Column(String, ForeignKey("interaction_checks.id"))
    pharmacist_id = Column(String, ForeignKey("users.id"))
    ghi_chu = Column(Text)
    trang_thai_xac_nhan = Column(String(20), default="chua_xac_nhan")
