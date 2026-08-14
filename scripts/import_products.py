#!/usr/bin/env python3
"""ETL: nap CSDL ten thuoc (biet duoc) -> hoat chat vao Product/ProductIngredient.

Doc data/raw/thuoc_final_project.csv (moi dong = 1 thuoc; cot Hoat_chat_list la JSON
list [{"ten": ..., "ddinter_id": "DDInterXXX" | null}, ...] da duoc pre-match san
ddinter_id) -> voi moi thuoc, tao 1 Product + N ProductIngredient (1 phan tu JSON = 1
hoat chat). ProductIngredient.medication_id duoc gan truc tiep bang ddinter_id neu id
do da co trong bang medications (nap tu import_ddinter.py), nguoc lai de NULL - van luu
ten hoat chat de hien thi thanh phan, nhung khong dung de tra tuong tac (cung nguyen tac
"khong suy doan ngoai CSDL" nhu drug_normalizer_tool.py).

Thay the du lieu cu (thuoc_hoat_chat_clean.csv): sau khi nap xong, xoa het Product nao
co ten_thuoc KHONG con xuat hien trong file CSV moi, de dung nghia "thay the" thay vi
"cong don". Product nao ten_thuoc trung voi du lieu cu se giu nguyen id (upsert), nen
khong lam vo cac PatientMedication.product_id da tro toi no.

PHAI chay sau scripts/import_ddinter.py (can bang medications day du truoc khi so khop).

Usage:
  python scripts/import_products.py
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.models import Medication, Product, ProductIngredient
from src.db.session import SessionLocal, init_db

RAW_CSV = Path(__file__).resolve().parent.parent / "data" / "raw" / "thuoc_final_project.csv"


def load_rows() -> list[dict]:
    if not RAW_CSV.exists():
        raise FileNotFoundError(
            f"Khong tim thay {RAW_CSV}. Copy thuoc_final_project.csv vao data/raw/ truoc khi chay script nay."
        )
    rows = []
    with open(RAW_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ten_thuoc = (row.get("Ten_thuoc") or "").strip()
            if not ten_thuoc:
                continue
            rows.append(row)
    return rows


def build_medication_id_set(db) -> set[str]:
    return {m.id for m in db.query(Medication.id).all()}


def get_or_create_product(db, ten_thuoc: str, is_duoc_lieu: bool) -> Product:
    product = db.query(Product).filter_by(ten_thuoc=ten_thuoc).first()
    if product is None:
        product = Product(
            ten_thuoc=ten_thuoc,
            is_duoc_lieu=is_duoc_lieu,
            nguon_du_lieu="VMEC12 crawl",
        )
        db.add(product)
        db.flush()
    else:
        product.is_duoc_lieu = is_duoc_lieu
    return product


def sync_ingredients(
    db, product: Product, ingredients: list[dict], medication_ids: set[str]
) -> tuple[int, int]:
    """Ghi de toan bo ProductIngredient cua 1 Product theo CSV hien tai (idempotent)."""
    db.query(ProductIngredient).filter_by(product_id=product.id).delete()

    matched, unmatched = 0, 0
    seen: set[str] = set()
    for ing in ingredients:
        ten = (ing.get("ten") or "").strip()
        if not ten or ten.lower() in seen:
            continue
        seen.add(ten.lower())

        ddinter_id = ing.get("ddinter_id")
        medication_id = ddinter_id if ddinter_id in medication_ids else None
        if medication_id:
            matched += 1
        else:
            unmatched += 1

        db.add(
            ProductIngredient(
                product_id=product.id,
                ten_hoat_chat_raw=ten,
                ten_hoat_chat_clean=ten,
                medication_id=medication_id,
            )
        )
    return matched, unmatched


_SQL_BATCH = 500


def delete_stale_products(db, current_names: set[str]) -> int:
    """Xoa Product (+ ProductIngredient con) khong con trong file CSV moi.

    Tinh phan bu o phia Python (khong dung IN/NOT IN voi ~44k gia tri - vuot gioi han
    so bien cua SQLite), roi xoa theo id thanh tung batch nho.
    """
    existing = db.query(Product.id, Product.ten_thuoc).all()
    stale_ids = [pid for pid, ten_thuoc in existing if ten_thuoc not in current_names]
    if not stale_ids:
        return 0

    for i in range(0, len(stale_ids), _SQL_BATCH):
        batch = stale_ids[i : i + _SQL_BATCH]
        db.query(ProductIngredient).filter(ProductIngredient.product_id.in_(batch)).delete(
            synchronize_session=False
        )
        db.query(Product).filter(Product.id.in_(batch)).delete(synchronize_session=False)
    return len(stale_ids)


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        print("Doc CSV...")
        rows = load_rows()
        print(f"  -> {len(rows)} thuoc")

        print("Nap medication id set de so khop...")
        medication_ids = build_medication_id_set(db)
        print(f"  -> {len(medication_ids)} hoat chat trong CSDL")

        print("Nap products + ingredients...")
        total_matched, total_unmatched = 0, 0
        products_with_data = 0
        current_names: set[str] = set()
        for i, row in enumerate(rows, start=1):
            ten_thuoc = row["Ten_thuoc"].strip()
            current_names.add(ten_thuoc)
            is_duoc_lieu = (row.get("Is_Duoc_Lieu") or "").strip() == "True"
            try:
                ingredients = json.loads(row.get("Hoat_chat_list") or "[]")
            except json.JSONDecodeError:
                ingredients = []

            product = get_or_create_product(db, ten_thuoc, is_duoc_lieu)
            matched, unmatched = sync_ingredients(db, product, ingredients, medication_ids)
            total_matched += matched
            total_unmatched += unmatched
            if matched > 0:
                products_with_data += 1
            if i % 2000 == 0:
                db.commit()
                print(f"  ... {i}/{len(rows)}")

        db.commit()

        print("Xoa product cu khong con trong file moi...")
        deleted = delete_stale_products(db, current_names)
        db.commit()
        print(f"  -> da xoa {deleted} product cu")

        print(
            f"=== Tong: {len(rows)} thuoc ({products_with_data} co >=1 hoat chat "
            f"khop DDInter), {total_matched} dong hoat chat khop, {total_unmatched} khong khop ==="
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
