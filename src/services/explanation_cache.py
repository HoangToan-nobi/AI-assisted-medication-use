"""Cache đọc/ghi dùng chung cho giải thích cấp thuốc (rollup_explain.py) và cấp
thuốc-thực phẩm/thuốc-bệnh nền (food_disease_explain.py) - dữ liệu DDInter đứng sau
các cạnh này gần như tĩnh nên nhiều user tra trùng 1 cạnh sẽ dùng lại đúng 1 bản ghi
thay vì gọi LLM lại từ đầu.

Mỗi hàm tự mở/đóng 1 SessionLocal() NGẮN HẠN riêng cho lần đọc/ghi của nó, KHÔNG
nhận Session truyền từ ngoài - vì các cạnh chạy đồng thời qua asyncio.gather, có
await LLM xen giữa lúc đọc cache và lúc ghi cache; nếu dùng chung 1 Session giữa
nhiều coroutine bị xen kẽ như vậy, Session (vốn không an toàn với kiểu dùng xen kẽ
này) có thể dính state lẫn lộn giữa các coroutine."""

from sqlalchemy.exc import IntegrityError

from src.db.session import SessionLocal


def lookup_cached(model_cls: type, **filters) -> dict | None:
    """Trả về dict các field của bản ghi khớp filters, hoặc None nếu cache miss."""
    with SessionLocal() as db:
        row = db.query(model_cls).filter_by(**filters).first()
        if row is None:
            return None
        return {
            "giai_thich": row.giai_thich,
            "giai_thich_duoc_si": row.giai_thich_duoc_si,
            "nguon_trich_dan": row.nguon_trich_dan,
            "mo_ta_dich": row.mo_ta_dich,
            "xu_tri_dich": row.xu_tri_dich,
        }


def save_cached(model_cls: type, **fields) -> None:
    """Ghi 1 bản ghi cache mới. Nếu coroutine khác đã ghi trước (race giữa các cạnh
    chạy song song) thì UniqueConstraint chặn lại bằng IntegrityError - bỏ qua, không
    coi là lỗi, vì nội dung ghi trước đó đã đủ dùng cho lần tra sau."""
    with SessionLocal() as db:
        db.add(model_cls(**fields))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
