#!/usr/bin/env python3
"""One-time migration NGƯỢC lại với migrate_sqlite_to_postgres.py: copy toàn bộ dữ
liệu từ Postgres (Neon) hiện tại trong DATABASE_URL (.env) về 1 file SQLite local
mới, để chạy app hoàn toàn local khi Neon không truy cập được (VD hết quota).

Tự động sao lưu file SQLite đích nếu đã tồn tại (đổi tên kèm timestamp) trước khi
ghi đè - không xóa mất dữ liệu local cũ.

Usage (chạy từ thư mục gốc dự án, .env đã có DATABASE_URL trỏ tới Neon):
  python scripts/migrate_postgres_to_sqlite.py [duong_dan_file_sqlite_dich]

Mặc định file đích: data/app.db
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine

from src.config import get_settings
from src.db.models import Base

_CHUNK_SIZE = 2000


def main() -> None:
    settings = get_settings()
    postgres_url = settings.database_url
    if not postgres_url.startswith("postgresql"):
        print(
            f"Loi: DATABASE_URL trong .env dang la '{postgres_url}', khong phai Postgres/Neon. "
            "Script nay dung de keo du lieu TU Neon VE SQLite - kiem tra lai .env.",
            file=sys.stderr,
        )
        sys.exit(1)

    dest_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/app.db")

    print(f"Ket noi Neon: {postgres_url.split('@')[-1]}")
    src_engine = create_engine(postgres_url)

    # QUAN TRONG: kiem tra ket noi Neon truoc, truoc khi dung toi file dich - neu
    # khong se sao luu/ghi de file SQLite cu roi moi phat hien Neon khong ket noi
    # duoc, khien nguoi dung mat ca file cu lan file moi (da tung xay ra khi test).
    print("Kiem tra ket noi Neon...")
    try:
        with src_engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as e:
        print(f"Khong ket noi duoc Neon: {e}", file=sys.stderr)
        print("Neon co the dang bi chan (het quota) - thu lai sau hoac nang cap goi.", file=sys.stderr)
        sys.exit(1)

    if dest_path.exists():
        backup_path = dest_path.with_name(
            f"{dest_path.stem}.bak-{datetime.now():%Y%m%d-%H%M%S}{dest_path.suffix}"
        )
        shutil.move(str(dest_path), str(backup_path))
        print(f"Da sao luu file cu: {dest_path} -> {backup_path}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite_url = f"sqlite:///{dest_path.as_posix()}"
    dst_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

    print("Tao bang tren SQLite (theo dung models.py hien tai)...")
    Base.metadata.create_all(bind=dst_engine)

    with src_engine.connect() as src_conn, dst_engine.begin() as dst_conn:
        for table in Base.metadata.sorted_tables:
            rows = [dict(row._mapping) for row in src_conn.execute(table.select())]
            if not rows:
                print(f"  {table.name}: 0 dong, bo qua")
                continue
            for i in range(0, len(rows), _CHUNK_SIZE):
                dst_conn.execute(table.insert(), rows[i : i + _CHUNK_SIZE])
            print(f"  {table.name}: da copy {len(rows)} dong")

    print(f"\nXong. File SQLite moi: {dest_path}")
    print("De chay app voi file nay, sua DATABASE_URL trong .env thanh:")
    print(f"  DATABASE_URL=sqlite:///./{dest_path.as_posix()}")


if __name__ == "__main__":
    main()
