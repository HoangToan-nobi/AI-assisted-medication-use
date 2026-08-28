"""Đánh giá trích xuất tên thuốc và bệnh trực tiếp từ OCR, không dùng resolver.

Mỗi ảnh ``eval/end2end/<tên>.<đuôi>`` đi cùng:

* ``<tên>.txt``: một thuốc in trên đơn mỗi dòng;
* ``<tên>.benh.txt``: một bệnh/chẩn đoán mỗi dòng (không bắt buộc).

Script chạy OCR, phân loại và tách dòng giống API nhưng dừng trước
``DrugResolver``. Vì nhãn thuốc hiện có thể chứa cả hoạt chất, biệt dược và hàm
lượng trong khi OCR tách thành nhiều vùng, kết quả báo cả khớp nghiêm ngặt và
khớp mềm. Khớp mềm chỉ là chỉ số trích xuất sơ bộ; CER/exact mới phản ánh mức
độ giống văn bản.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from app.config import settings
from app.services.ocr_service import OCRService, filter_ocr_results
from app.services.prescription_resolver import (
    classify_document,
    extract_medication_rows,
    extract_prescription_conditions,
)
from app.utils.image_utils import prepare_image
from app.utils.text_utils import matching_key

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
FUZZY_THRESHOLD = 80.0


def load_labels(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [
        line
        for raw in path.read_text(encoding="utf-8").splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    ]


def strict_key(text: str) -> str:
    """Chỉ chuẩn hóa trình bày; giữ nguyên dấu và ký tự OCR đã đọc."""
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def cer(expected: str, produced: str) -> float:
    expected_key = strict_key(expected)
    produced_key = strict_key(produced)
    if not expected_key:
        return 0.0 if not produced_key else 1.0
    return Levenshtein.distance(expected_key, produced_key) / len(expected_key)


def row_variants(texts: list[str]) -> list[str]:
    cleaned = [text.strip() for text in texts if text and text.strip()]
    if len(cleaned) > 1:
        cleaned.append(" ".join(cleaned))
    return list(dict.fromkeys(cleaned))


def fuzzy_score(expected: str, variants: list[str]) -> float:
    """Độ giống tên trước resolver; không tra cứu hay chuẩn hóa theo CSDL."""
    expected_key = matching_key(expected)
    best = 0.0
    for variant in variants:
        produced_key = matching_key(variant)
        if len(produced_key) < 4:
            # Tên biệt dược dạng viết tắt như ``JEX`` vẫn là kết quả OCR hợp lệ.
            # Chỉ cho điểm khi chuỗi ba chữ khớp NGUYÊN TỪ trong nhãn; tuyệt đối
            # không fuzzy chuỗi ngắn vì ``Số``, ``SL``... rất dễ trùng ngẫu nhiên.
            if (
                re.fullmatch(r"[a-z]{3}", produced_key)
                and re.search(
                    rf"(?<![a-z0-9]){re.escape(produced_key)}(?![a-z0-9])",
                    expected_key,
                )
            ):
                best = max(best, 100.0)
            continue
        best = max(
            best,
            fuzz.token_set_ratio(expected_key, produced_key),
            fuzz.partial_ratio(expected_key, produced_key),
        )
    return best


def exact_match(expected: str, variants: list[str]) -> bool:
    expected_key = strict_key(expected)
    return any(strict_key(variant) == expected_key for variant in variants)


def best_cer(expected: str, variants: list[str]) -> float:
    return min((cer(expected, variant) for variant in variants), default=1.0)


def match_one_to_one(expected: list[str], produced: list[list[str]]) -> dict:
    used: set[int] = set()
    fuzzy_hits: list[tuple[str, str, float]] = []
    exact_hits = 0
    misses: list[str] = []
    cer_sum = 0.0

    for label in expected:
        available = [
            (fuzzy_score(label, variants), index, variants)
            for index, variants in enumerate(produced)
            if index not in used
        ]
        if not available:
            misses.append(label)
            cer_sum += 1.0
            continue

        score, index, variants = max(available, key=lambda item: item[0])
        cer_sum += best_cer(label, variants)
        if score < FUZZY_THRESHOLD:
            misses.append(label)
            continue

        used.add(index)
        exact_hits += int(exact_match(label, variants))
        displayed = max(variants, key=lambda text: fuzzy_score(label, [text]))
        fuzzy_hits.append((label, displayed, score))

    return {
        "fuzzy_hits": fuzzy_hits,
        "exact_hits": exact_hits,
        "misses": misses,
        "spurious": [variants for index, variants in enumerate(produced) if index not in used],
        "cer_sum": cer_sum,
    }


def build_ocr() -> OCRService:
    service = OCRService(
        lang=settings.ocr_lang,
        device=settings.ocr_device,
        enable_mkldnn=settings.ocr_enable_mkldnn,
        ocr_version=settings.ocr_version,
        det_model=settings.ocr_det_model,
        rec_model=settings.ocr_rec_model,
        vietocr_enabled=settings.ocr_vietocr_enabled,
        vietocr_model=settings.ocr_vietocr_model,
        vietocr_weights=settings.ocr_vietocr_weights,
        vietocr_batch_size=settings.ocr_vietocr_batch_size,
        torch_threads=settings.ocr_torch_threads,
    )
    service.load()
    if not service.loaded:
        raise SystemExit(f"PaddleOCR không tải được: {service.load_error}")
    if settings.ocr_vietocr_enabled and not service.vietocr_loaded:
        raise SystemExit(f"VietOCR không tải được: {service.vietocr_error}")
    return service


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "eval" / "end2end",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    def natural_key(path: Path):
        return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", path.stem)]

    images = sorted(
        (path for path in args.dataset.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES),
        key=natural_key,
    )
    if not images:
        raise SystemExit(f"Không tìm thấy ảnh trong {args.dataset}")

    ocr = build_ocr()
    drug_expected = drug_fuzzy = drug_exact = drug_spurious = 0
    disease_expected = disease_fuzzy = disease_exact = disease_spurious = 0
    drug_cer_sum = disease_cer_sum = 0.0
    document_types: dict[str, int] = {}

    for image in images:
        expected_drugs = load_labels(image.with_suffix(".txt"))
        expected_diseases = load_labels(image.parent / f"{image.stem}.benh.txt")
        if not expected_drugs:
            print(f"BỎ QUA {image.name}: thiếu hoặc rỗng {image.stem}.txt")
            continue

        prepared = prepare_image(
            image.read_bytes(),
            max_dimension=settings.max_image_dimension,
            allowed_formats=settings.allowed_image_formats,
            min_dimension=settings.ocr_min_dimension,
            max_input_pixels=settings.max_input_pixels,
        )
        items = filter_ocr_results(
            ocr.recognize(prepared.array), settings.ocr_confidence_threshold
        )
        document_type = classify_document(items)
        document_types[document_type] = document_types.get(document_type, 0) + 1

        rows = extract_medication_rows(items) if document_type == "prescription" else []
        produced_drugs = [
            row_variants(list(row.get("name_texts") or []))
            for row in rows
            if row.get("name_texts")
        ]
        drug_report = match_one_to_one(expected_drugs, produced_drugs)

        conditions = (
            extract_prescription_conditions(items)
            if document_type == "prescription"
            else {"diagnosis": "", "underlying_conditions": []}
        )
        condition_texts = list(conditions.get("underlying_conditions") or [])
        diagnosis = str(conditions.get("diagnosis") or "").strip()
        # The raw combined diagnosis is audit evidence, not a seventh disease.
        # Use it only when the parser could not produce individual conditions.
        if not condition_texts and diagnosis:
            condition_texts.append(diagnosis)
        produced_diseases = [[text] for text in condition_texts if text.strip()]
        disease_report = match_one_to_one(expected_diseases, produced_diseases)

        drug_expected += len(expected_drugs)
        drug_fuzzy += len(drug_report["fuzzy_hits"])
        drug_exact += drug_report["exact_hits"]
        drug_spurious += len(drug_report["spurious"])
        drug_cer_sum += drug_report["cer_sum"]
        disease_expected += len(expected_diseases)
        disease_fuzzy += len(disease_report["fuzzy_hits"])
        disease_exact += disease_report["exact_hits"]
        disease_spurious += len(disease_report["spurious"])
        disease_cer_sum += disease_report["cer_sum"]

        print(
            f"{image.name:12s} thuốc {len(drug_report['fuzzy_hits'])}/{len(expected_drugs)}"
            f" (exact {drug_report['exact_hits']}, +{len(drug_report['spurious'])} thừa)"
            + (
                f" | bệnh {len(disease_report['fuzzy_hits'])}/{len(expected_diseases)}"
                f" (exact {disease_report['exact_hits']})"
                if expected_diseases
                else ""
            )
        )
        if args.verbose:
            for label in drug_report["misses"]:
                print(f"    TRƯỢT thuốc: {label}")
            for variants in drug_report["spurious"]:
                print(f"    THỪA dòng:   {' | '.join(variants)}")
            for label in disease_report["misses"]:
                print(f"    TRƯỢT bệnh:  {label}")

    def percentage(value: int, total: int) -> float:
        return value / total * 100 if total else 0.0

    print("\nKẾT QUẢ TRÍCH XUẤT TRƯỚC RESOLVER")
    print("THUỐC")
    print(
        f"  fuzzy recall (>= {FUZZY_THRESHOLD:.0f}): "
        f"{drug_fuzzy}/{drug_expected} = {percentage(drug_fuzzy, drug_expected):.1f}%"
    )
    print(
        f"  exact-normalized recall: {drug_exact}/{drug_expected} = "
        f"{percentage(drug_exact, drug_expected):.1f}%"
    )
    print(
        f"  fuzzy precision: {drug_fuzzy}/{drug_fuzzy + drug_spurious} = "
        f"{percentage(drug_fuzzy, drug_fuzzy + drug_spurious):.1f}%"
    )
    print(f"  CER trung bình theo nhãn: {drug_cer_sum / drug_expected:.1%}" if drug_expected else "")

    print("BỆNH")
    print(
        f"  fuzzy recall (>= {FUZZY_THRESHOLD:.0f}): "
        f"{disease_fuzzy}/{disease_expected} = {percentage(disease_fuzzy, disease_expected):.1f}%"
    )
    print(
        f"  exact-normalized recall: {disease_exact}/{disease_expected} = "
        f"{percentage(disease_exact, disease_expected):.1f}%"
    )
    print(
        f"  fuzzy precision: {disease_fuzzy}/{disease_fuzzy + disease_spurious} = "
        f"{percentage(disease_fuzzy, disease_fuzzy + disease_spurious):.1f}%"
    )
    print(
        f"  CER trung bình theo nhãn: {disease_cer_sum / disease_expected:.1%}"
        if disease_expected
        else ""
    )
    print("PHÂN LOẠI:", ", ".join(f"{key}={value}" for key, value in sorted(document_types.items())))
    print("\nKhông chỉ số nào ở trên gọi DrugResolver hoặc tra tên thuốc trong CSDL.")


if __name__ == "__main__":
    main()
