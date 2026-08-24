"""DB session — dùng lại get_settings() có sẵn trong src/config.py."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.db.models import Base

settings = get_settings()

# connect_args chỉ cần cho SQLite (dev); Postgres (prod) không cần dòng này
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

# pool_pre_ping: kiểm tra connection còn sống trước khi dùng - bắt buộc với Neon vì
# nó tự ngắt connection khi idle (auto-suspend), nếu không sẽ lấy phải connection
# chết từ pool và phải đợi timeout mới phát hiện ra.
# pool_recycle: chủ động bỏ connection cũ trước khi hạ tầng Neon tự cắt ngầm.
engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DB "facts" (interactions/food_interactions/disease_interactions) - xem
# PLAN_migration_cockroach.md. Khi database_url_facts để trống (dev/test), dùng lại
# engine chính thay vì mở thêm 1 connection pool trỏ tới cùng 1 DB.
FACTS_TABLE_NAMES = {"interactions", "food_interactions", "disease_interactions"}
if settings.database_url_facts:
    _facts_connect_args = (
        {"check_same_thread": False} if settings.database_url_facts.startswith("sqlite") else {}
    )
    engine_facts = create_engine(
        settings.database_url_facts,
        connect_args=_facts_connect_args,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    SessionLocalFacts = sessionmaker(autocommit=False, autoflush=False, bind=engine_facts)
else:
    engine_facts = engine
    SessionLocalFacts = SessionLocal


def _ensure_column(table: str, column: str, ddl_type: str, *, engine=engine) -> None:
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


def _ensure_column_any_dialect(
    table: str, column: str, sqlite_ddl_type: str, pg_ddl_type: str, *, engine=engine
) -> None:
    """Giống _ensure_column nhưng chạy trên CẢ Postgres lẫn SQLite - _ensure_column
    bỏ qua Postgres với giả định create_all() sẽ tự thêm cột mới cho bảng cũ, nhưng
    thực ra create_all() KHÔNG BAO GIỜ ALTER bảng đã tồn tại sẵn ở bất kỳ dialect
    nào (giả định đó sai với 1 DB Postgres đã có data từ trước, như Neon hiện tại).
    Postgres hỗ trợ sẵn ADD COLUMN IF NOT EXISTS nên không cần tự kiểm tra tồn tại
    trước như nhánh SQLite."""
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]
            if column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sqlite_ddl_type}"))
                conn.commit()
        else:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {pg_ddl_type}"))
            conn.commit()


def _ensure_index(table: str, column: str, index_name: str, *, engine=engine) -> None:
    """Giống _ensure_column nhưng cho index - create_all() KHÔNG retroactively thêm
    index vào bảng đã tồn tại sẵn (khác cột, đây đúng cho cả SQLite lẫn Postgres),
    nên phải tự chạy CREATE INDEX IF NOT EXISTS 1 lần cho bảng cũ. Thiếu các index
    này từng khiến các query lọc theo patient_id/user_id chậy hẳn trên Neon (seq
    scan) sau khi chuyển từ SQLite (dataset nhỏ, không thấy rõ) sang Postgres."""
    with engine.connect() as conn:
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})"))
        conn.commit()


def init_db() -> None:
    """Tạo bảng nếu chưa tồn tại — gọi 1 lần khi setup (Sprint 0).

    interactions/food_interactions/disease_interactions tạo trên engine_facts
    (CockroachDB) - các bảng còn lại tạo trên engine chính (Supabase). Xem
    PLAN_migration_cockroach.md."""
    main_tables = [t for name, t in Base.metadata.tables.items() if name not in FACTS_TABLE_NAMES]
    facts_tables = [Base.metadata.tables[name] for name in FACTS_TABLE_NAMES]
    Base.metadata.create_all(bind=engine, tables=main_tables)
    Base.metadata.create_all(bind=engine_facts, tables=facts_tables)

    _ensure_column("patient_medications", "prescription_id", "TEXT REFERENCES patient_prescriptions(id)")
    _ensure_column("users", "mo_ta_ngan", "TEXT")
    _ensure_column("users", "noi_cong_tac", "VARCHAR(255)")
    _ensure_column("users", "email_normalized", "VARCHAR(255)")
    _ensure_column("users", "email_verified_at", "DATETIME")
    _ensure_column("users", "account_status", "VARCHAR(30) DEFAULT 'locked'")
    _ensure_column("users", "lock_source", "VARCHAR(30)")
    _ensure_column("users", "so_chung_chi_hanh_nghe", "VARCHAR(100)")
    _ensure_column("users", "ly_do_tu_choi", "TEXT")
    _ensure_column("pharmacist_reviews", "gui_kem_ho_so", "BOOLEAN DEFAULT 0")
    _ensure_column("pharmacist_reviews", "ten_nguoi_duoc_kiem_tra", "TEXT")
    _ensure_column("pharmacist_reviews", "ngay_sinh_nhap_tay", "DATE")
    _ensure_column("pharmacist_reviews", "ghi_chu_nhap_tay", "TEXT")
    _ensure_column("pharmacist_reviews", "thoi_gian_xac_nhan", "DATETIME")
    _ensure_column("pharmacist_reviews", "cau_hoi", "TEXT")
    _ensure_column("pharmacist_reviews", "cau_tra_loi", "TEXT")
    _ensure_column("food_interactions", "thuc_pham_vi", "VARCHAR(255)", engine=engine_facts)
    _ensure_column("disease_interactions", "ten_benh_vi", "VARCHAR(255)", engine=engine_facts)
    _ensure_column("interactions", "mo_ta_dich", "TEXT", engine=engine_facts)
    _ensure_column("interactions", "xu_tri_dich", "TEXT", engine=engine_facts)
    _ensure_column("food_interactions", "mo_ta_dich", "TEXT", engine=engine_facts)
    _ensure_column("food_interactions", "xu_tri_dich", "TEXT", engine=engine_facts)
    _ensure_column("disease_interactions", "mo_ta_dich", "TEXT", engine=engine_facts)

    _ensure_column_any_dialect("interaction_checks", "thuoc_da_kiem_tra", "TEXT", "JSON")
    _ensure_column_any_dialect("food_disease_explanation_cache", "nguon_trich_dan_chi_tiet", "TEXT", "TEXT")

    _ensure_index("patient_profiles", "user_id", "idx_patient_profiles_user_id")
    _ensure_index("patient_prescriptions", "patient_id", "idx_patient_prescriptions_patient_id")
    _ensure_index("patient_medications", "patient_id", "idx_patient_medications_patient_id")
    _ensure_index("interaction_checks", "patient_id", "idx_interaction_checks_patient_id")
    _ensure_index("pharmacist_reviews", "interaction_check_id", "idx_pharmacist_reviews_check_id")
    _ensure_index("pharmacist_reviews", "pharmacist_id", "idx_pharmacist_reviews_pharmacist_id")
    _ensure_index("notifications", "patient_id", "idx_notifications_patient_id")


def assert_auth_schema_ready() -> None:
    """Fail with an actionable message instead of serving partially migrated auth."""
    columns = {column["name"]: column for column in inspect(engine).get_columns("users")}
    required = {"email_normalized", "email_verified_at", "account_status", "lock_source", "so_chung_chi_hanh_nghe", "ly_do_tu_choi"}
    if missing := required - columns.keys():
        raise RuntimeError(f"Auth schema chua migrate ({sorted(missing)}); chay python scripts/migrate_auth.py")
    if not columns["mat_khau_hash"]["nullable"]:
        raise RuntimeError("Auth schema cu van bat buoc mat_khau_hash; chay python scripts/migrate_auth.py")
    with engine.connect() as conn:
        unclassified_locks = conn.execute(text(
            "SELECT count(*) FROM users WHERE account_status = 'locked' AND lock_source IS NULL"
        )).scalar_one()
    if unclassified_locks:
        raise RuntimeError(
            f"Co {unclassified_locks} tai khoan khoa chua co nguon khoa; "
            "chay python scripts/migrate_auth.py"
        )


def get_db() -> Session:
    """Dependency cho FastAPI route: `db: Session = Depends(get_db)`."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_facts() -> Session:
    """Dependency cho FastAPI route: `db_facts: Session = Depends(get_db_facts)`.

    Trỏ tới CockroachDB (interactions/food_interactions/disease_interactions) -
    xem PLAN_migration_cockroach.md."""
    db = SessionLocalFacts()
    try:
        yield db
    finally:
        db.close()
