from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.db.models import Base, Disease, DiseaseInteraction, Medication
from src.services.food_disease_lookup import lookup_disease_interactions


def test_lookup_disease_interactions_filters_by_disease_ids_and_keeps_fallback():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        medication = Medication(id="med-1", ten_chuan_hoa="Example drug")
        hypertension = Disease(id=1, ten_benh="Hypertension", ten_benh_vi="Tăng huyết áp")
        diabetes = Disease(id=2, ten_benh="Diabetes", ten_benh_vi="Đái tháo đường")
        db.add_all(
            [
                medication,
                hypertension,
                diabetes,
                DiseaseInteraction(
                    id="di-hypertension",
                    medication_id=medication.id,
                    disease_id=hypertension.id,
                    ten_benh=hypertension.ten_benh,
                    ten_benh_vi=hypertension.ten_benh_vi,
                    muc_do="nang",
                ),
                DiseaseInteraction(
                    id="di-diabetes",
                    medication_id=medication.id,
                    disease_id=diabetes.id,
                    ten_benh=diabetes.ten_benh,
                    ten_benh_vi=diabetes.ten_benh_vi,
                    muc_do="trung_binh",
                ),
            ]
        )
        db.commit()

        fallback = lookup_disease_interactions([medication.id], db)
        assert {item["ten_benh"] for item in fallback} == {"Tăng huyết áp", "Đái tháo đường"}

        personalized = lookup_disease_interactions(
            [medication.id], db, disease_ids=[hypertension.id]
        )
        assert [item["ten_benh"] for item in personalized] == ["Tăng huyết áp"]

        assert lookup_disease_interactions([medication.id], db, disease_ids=[]) == []

    engine.dispose()
