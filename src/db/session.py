"""DB session — dùng lại get_settings() có sẵn trong src/config.py."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.db.models import Base

settings = get_settings()

# connect_args chỉ cần cho SQLite (dev); Postgres (prod) không cần dòng này
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _ensure_column(table: str, column: str, ddl_type: str) -> None:
    """Không có framework migration (chỉ create_all, không ALTER bảng đã tồn tại) -
    thêm cột thủ công 1 lần, idempotent, cho các bảng được tạo trước khi cột này
    xuất hiện trong model.

    Chỉ cần cho SQLite (PRAGMA table_info là cú pháp riêng của SQLite) - Postgres
    không bao giờ có bảng "cũ" thiếu cột này vì create_all() luôn tạo bảng mới đúng
    theo model hiện tại (đã có sẵn các cột này khai báo trong models.py)."""
    if engine.dialect.name != "sqlite":
        return
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]
        if column not in cols:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
            conn.commit()


def init_db() -> None:
    """Tạo bảng nếu chưa tồn tại — gọi 1 lần khi setup (Sprint 0)."""
    Base.metadata.create_all(bind=engine)
    _ensure_column("patient_medications", "prescription_id", "TEXT REFERENCES patient_prescriptions(id)")
    _ensure_column("users", "mo_ta_ngan", "TEXT")
    _ensure_column("users", "noi_cong_tac", "VARCHAR(255)")
    _ensure_column("pharmacist_reviews", "gui_kem_ho_so", "BOOLEAN DEFAULT 0")
    _ensure_column("pharmacist_reviews", "ten_nguoi_duoc_kiem_tra", "TEXT")
    _ensure_column("pharmacist_reviews", "ngay_sinh_nhap_tay", "DATE")
    _ensure_column("pharmacist_reviews", "ghi_chu_nhap_tay", "TEXT")
    _ensure_column("pharmacist_reviews", "thoi_gian_xac_nhan", "DATETIME")
    _ensure_column("pharmacist_reviews", "cau_hoi", "TEXT")
    _ensure_column("pharmacist_reviews", "cau_tra_loi", "TEXT")
    _ensure_column("food_interactions", "thuc_pham_vi", "VARCHAR(255)")
    _ensure_column("disease_interactions", "ten_benh_vi", "VARCHAR(255)")
    _ensure_column("interactions", "mo_ta_dich", "TEXT")
    _ensure_column("interactions", "xu_tri_dich", "TEXT")
    _ensure_column("food_interactions", "mo_ta_dich", "TEXT")
    _ensure_column("food_interactions", "xu_tri_dich", "TEXT")
    _ensure_column("disease_interactions", "mo_ta_dich", "TEXT")


def get_db() -> Session:
    """Dependency cho FastAPI route: `db: Session = Depends(get_db)`."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
