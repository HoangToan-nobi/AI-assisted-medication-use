"""DB session — dùng lại get_settings() có sẵn trong src/config.py."""
from sqlalchemy import create_engine
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


def init_db() -> None:
    """Tạo bảng nếu chưa tồn tại — gọi 1 lần khi setup (Sprint 0)."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Dependency cho FastAPI route: `db: Session = Depends(get_db)`."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
