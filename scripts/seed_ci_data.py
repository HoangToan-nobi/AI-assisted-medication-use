#!/usr/bin/env python3
"""Create the small deterministic dataset required by CI integration tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.models import Base, Interaction, Medication, MedicationAlias, Product
from src.db.session import SessionLocal, engine

MEDICATIONS = {
    "DDInter14": "Acetaminophen",
    "DDInter20": "Acetylsalicylic acid",
    "DDInter83": "Amoxicillin",
    "DDInter690": "Ethanol",
    "DDInter771": "Folic acid",
    "DDInter900": "Ibuprofen",
    "DDInter1951": "Warfarin",
}

ALIASES = {
    "asp": "DDInter20",
    "aspirin": "DDInter20",
    "paracetamol": "DDInter14",
    "warfarin": "DDInter1951",
    "ibuprofen": "DDInter900",
}


def main() -> None:
    Path("data").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for medication_id, name in MEDICATIONS.items():
            if db.get(Medication, medication_id) is None:
                db.add(Medication(id=medication_id, ten_chuan_hoa=name, nguon_du_lieu="CI fixture"))
        db.flush()

        for alias, medication_id in ALIASES.items():
            if db.query(MedicationAlias).filter_by(alias=alias).first() is None:
                db.add(MedicationAlias(alias=alias, medication_id=medication_id))

        interactions = (
            (
                "ci-warfarin-aspirin",
                "DDInter1951",
                "DDInter20",
                "nang",
                "Tang nguy co chay mau.",
            ),
            (
                "ci-ibuprofen-folic",
                "DDInter771",
                "DDInter900",
                "chua_phan_loai",
                "Chua du thong tin phan loai.",
            ),
        )
        for row_id, medication_a_id, medication_b_id, severity, description in interactions:
            if db.get(Interaction, row_id) is None:
                db.add(
                    Interaction(
                        id=row_id,
                        medication_a_id=medication_a_id,
                        medication_b_id=medication_b_id,
                        muc_do=severity,
                        mo_ta=description,
                        xu_tri="Theo doi va tham khao duoc si.",
                        nguon_trich_dan="DDInter CI fixture",
                    )
                )

        for product_id, name in (
            ("ci-product-ibuprofen", "Ibuprofen"),
            ("ci-product-paracetamol", "Paracetamol"),
        ):
            if db.get(Product, product_id) is None:
                db.add(Product(id=product_id, ten_thuoc=name, nguon_du_lieu="CI fixture"))
        db.commit()


if __name__ == "__main__":
    main()
