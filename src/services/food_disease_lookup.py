"""Tra cứu tương tác thuốc-thực phẩm/thuốc-bệnh nền qua CSDL SQL (DDInter 2.0 DFI/DDSI).

Khác interaction_lookup_tool.py (tương tác thuốc-thuốc, chạy TRONG LangGraph agent):
2 hàm này là SQL thuần, gọi TRỰC TIẾP từ src/api/routes.py SAU khi agent chạy xong -
vì đây là tra cứu đơn giản theo 1 hoạt chất (không cần rank/guardrail) và cần
ingredient_to_products (map hoạt chất -> tên biệt dược) vốn chỉ có ở tầng request,
giống hệt cách product_explanations/overview được tính ở rollup_explain.py."""

from sqlalchemy.orm import Session

from src.db.models import DiseaseInteraction, FoodInteraction, Medication


def lookup_food_interactions(medication_ids: list[str], db: Session) -> list[dict]:
    if not medication_ids:
        return []
    rows = (
        db.query(FoodInteraction, Medication.ten_chuan_hoa)
        .join(Medication, FoodInteraction.medication_id == Medication.id)
        .filter(FoodInteraction.medication_id.in_(medication_ids))
        .all()
    )
    return [
        {
            "hoat_chat": ten_chuan_hoa,
            "medication_id": food.medication_id,
            # Ưu tiên bản dịch tiếng Việt đã cache sẵn (scripts/translate_food_disease_names.py)
            # - rơi về tên gốc tiếng Anh nếu vì lý do gì đó chưa dịch (script chưa chạy qua dòng này).
            "thuc_pham": food.thuc_pham_vi or food.thuc_pham,
            "muc_do": food.muc_do,
            "mo_ta": food.mo_ta,
            "xu_tri": food.xu_tri,
            "nguon_trich_dan": food.nguon_trich_dan,
        }
        for food, ten_chuan_hoa in rows
    ]


def lookup_disease_interactions(medication_ids: list[str], db: Session) -> list[dict]:
    if not medication_ids:
        return []
    rows = (
        db.query(DiseaseInteraction, Medication.ten_chuan_hoa)
        .join(Medication, DiseaseInteraction.medication_id == Medication.id)
        .filter(DiseaseInteraction.medication_id.in_(medication_ids))
        .all()
    )
    return [
        {
            "hoat_chat": ten_chuan_hoa,
            "medication_id": disease.medication_id,
            "ten_benh": disease.ten_benh_vi or disease.ten_benh,
            "muc_do": disease.muc_do,
            "mo_ta": disease.mo_ta,
            "nguon_trich_dan": disease.nguon_trich_dan,
        }
        for disease, ten_chuan_hoa in rows
    ]
