"""Chấm điểm toàn trình: từ ảnh đơn thuốc ra danh sách thuốc.

`eval_ocr.py` chấm khâu đọc chữ, `eval_match.py` chấm khâu khớp danh mục. Bộ này
chấm cả đường đi một lượt: đưa vào tấm ảnh, so danh sách thuốc trả về với danh
sách thuốc thật sự in trên tờ đơn.

Nó không thay hai bộ kia mà bù cho chúng. Một con số toàn trình che mất khâu nào
đang hỏng, nhưng nó là con số duy nhất phản ánh thứ người dùng thật sự nhận được,
và cũng là bộ dữ liệu dễ gán nhãn nhất - chỉ cần nhìn tờ đơn rồi liệt kê thuốc,
không cần biết gì về bên trong hệ thống.

Cách dùng:
    python scripts/eval_end2end.py                    # eval/end2end/
    python scripts/eval_end2end.py --top 3            # tính đúng nếu nằm trong 3 đề xuất
    python scripts/eval_end2end.py --verbose          # in từng dòng lệch

Bố cục: mỗi ảnh ``eval/end2end/<tên>.<đuôi>`` đi kèm ``eval/end2end/<tên>.txt``
chứa các thuốc thật trên đơn, mỗi dòng một thuốc, chép theo tên IN TRÊN ĐƠN.
Dòng trống và dòng bắt đầu bằng ``#`` bị bỏ qua.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rapidfuzz import fuzz

from app.config import settings
from app.services.drug_resolver import DrugResolver
from app.services.ocr_service import OCRService, filter_ocr_results
from app.services.prescription_resolver import (
    classify_document,
    extract_medication_rows,
    extract_package_name,
    extract_prescription_conditions,
)
from app.utils.image_utils import prepare_image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

# Nhãn chép tay từ tờ đơn không bao giờ trùng từng ký tự với chuỗi hệ thống trả
# về: người gõ "Medrol 4mg", hệ thống trả "Methylprednisolone 4 mg". Ngưỡng này
# quyết định hai chuỗi có được coi là cùng một thuốc hay không. Đặt cao để một
# thuốc khác tên gần giống không bị tính là đúng.
SIMILARITY_THRESHOLD = 80.0


def load_expected(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def same_drug(expected: str, produced: str) -> bool:
    """Hai chuỗi có cùng chỉ một thuốc không.

    Nhãn chép nguyên dòng in trên đơn - thường gồm CẢ hoạt chất lẫn biệt dược
    (``Insulin glargine (Lantus SoloStar 3ml 100UI/ml)``) - trong khi CSDL chỉ giữ
    tên biệt dược (``Lantus``). Tức tên đúng hay là CHUỖI CON của nhãn.

    ``token_set_ratio`` phạt rất nặng quan hệ đó: cặp trên chỉ được 23 điểm dù là
    cùng một thuốc, còn ``Prograf 1mg`` / ``Tacrolimus(Prograf 1mg)`` được 65.
    ``partial_ratio`` đo đúng quan hệ chuỗi con nên cả hai đạt 100, trong khi cặp
    sai thật (``Aspirin Stada`` với ``Aspirin-Agimexpharm``) vẫn chỉ 61 và
    ``SAXAGLIPTIN`` với ``SAVI PROLOL`` chỉ 43 - ngưỡng 80 tách sạch hai nhóm.

    Vẫn giữ token_set_ratio cho chiều ngược lại (nhãn ngắn, tên CSDL dài), và chặn
    chuỗi quá ngắn vì ``partial_ratio`` của vài ký tự khớp được vào bất kỳ đâu.
    """
    if not expected or len(produced.strip()) < 4:
        return False
    a, b = expected.casefold().strip(), produced.casefold().strip()
    score = fuzz.token_set_ratio(a, b)
    # partial_ratio chỉ hợp lệ theo đúng chiều "tên CSDL nằm trong nhãn". Dùng cả
    # chiều ngược lại sẽ tính ``Prednisolon 5mg`` khớp ``Methylprednisolone 4 mg``
    # - hai thuốc khác nhau mà tên lồng nhau.
    if len(b) < len(a):
        score = max(score, fuzz.partial_ratio(a, b))
    return score >= SIMILARITY_THRESHOLD


def evaluate_image(
    image_path: Path,
    expected: list[str],
    expected_diseases: list[str],
    ocr: OCRService,
    resolver: DrugResolver,
    top: int,
) -> dict:
    prepared = prepare_image(
        image_path.read_bytes(),
        max_dimension=settings.max_image_dimension,
        allowed_formats=settings.allowed_image_formats,
        min_dimension=settings.ocr_min_dimension,
    )
    items = filter_ocr_results(
        ocr.recognize(prepared.array), settings.ocr_confidence_threshold
    )
    document_type = classify_document(items)
    rows = extract_medication_rows(items) if document_type == "prescription" else []

    produced: list[list[str]] = []
    scores: list[float] = []
    for row in rows:
        texts = row.get("resolver_texts") or row.get("name_texts") or []
        if not texts:
            continue
        result = resolver.resolve(texts, limit=top)
        cands = result["candidates"][:top]
        names = [c["drug_name"] for c in cands]
        if names:
            produced.append(names)
            scores.append(float(cands[0].get("score") or 0.0))

    # Mirror app/main.py: a package is resolved once from its prominent name
    # regions; an unknown document is never sent to the drug resolver.
    if document_type == "medicine_package":
        selected = extract_package_name(items)
        texts = [item["text"] for item in selected] or [item["text"] for item in items]
        result = resolver.resolve(texts, limit=top)
        cands = result["candidates"][:top]
        if cands:
            produced.append([candidate["drug_name"] for candidate in cands])
            scores.append(float(cands[0].get("score") or 0.0))

    # Ghép mỗi thuốc mong đợi với nhiều nhất một dòng hệ thống trả về, để một dòng
    # trúng nhiều nhãn không bị tính thành nhiều lần đúng.
    used: set[int] = set()
    hits: list[tuple[str, str]] = []
    misses: list[str] = []
    for want in expected:
        matched = None
        for index, names in enumerate(produced):
            if index in used:
                continue
            for name in names:
                if same_drug(want, name):
                    matched = (index, name)
                    break
            if matched:
                break
        if matched:
            used.add(matched[0])
            hits.append((want, matched[1]))
        else:
            misses.append(want)

    spurious = [names[0] for index, names in enumerate(produced) if index not in used]
    spurious_scores = [scores[i] for i in range(len(produced)) if i not in used]
    hit_scores = [scores[i] for i in sorted(used)]

    # Chẩn đoán: chấm ở mức "đọc đúng chữ trên đơn" thôi. Việc khớp tên bệnh với
    # bảng Disease diễn ra ở backend MediCheck (match_diseases_in_phrase), không ở
    # service này - nên ở đây chưa đo được khâu đó.
    conditions = (
        extract_prescription_conditions(items)
        if document_type == "prescription"
        else {"diagnosis": "", "underlying_conditions": [], "icd_codes": []}
    )
    produced_conditions = list(conditions.get("underlying_conditions") or [])
    diagnosis = (conditions.get("diagnosis") or "").strip()
    # The raw combined diagnosis is audit evidence, not a duplicate condition.
    # Fall back to it only when no split condition was recovered.
    if not produced_conditions and diagnosis:
        produced_conditions.append(diagnosis)

    used_c: set[int] = set()
    disease_hits: list[tuple[str, str]] = []
    disease_misses: list[str] = []
    for want in expected_diseases:
        matched = None
        for index, text in enumerate(produced_conditions):
            if index in used_c:
                continue
            if same_drug(want, text):
                matched = (index, text)
                break
        if matched:
            used_c.add(matched[0])
            disease_hits.append((want, matched[1]))
        else:
            disease_misses.append(want)

    return {
        "document_type": document_type,
        "rows": len(produced),
        "expected": len(expected),
        "hits": hits,
        "misses": misses,
        "spurious": spurious,
        "expected_diseases": len(expected_diseases),
        "disease_hits": disease_hits,
        "disease_misses": disease_misses,
        "icd_codes": list(conditions.get("icd_codes") or []),
        "hit_scores": hit_scores,
        "spurious_scores": spurious_scores,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "eval" / "end2end")
    parser.add_argument("--top", type=int, default=1, help="tính đúng nếu thuốc nằm trong N đề xuất đầu")
    parser.add_argument("--verbose", action="store_true", help="in từng thuốc trượt")
    args = parser.parse_args()

    def natural_key(path: Path):
        return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', path.stem)]

    images = sorted(
        (p for p in args.dataset.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES),
        key=natural_key,
    )
    if not images:
        raise SystemExit(f"Không tìm thấy ảnh nào trong {args.dataset}")

    # Giữ đúng cách app/main.py dựng service, để bộ đo chạy trên cùng cấu hình
    # với lúc phục vụ thật.
    ocr = OCRService(
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
    resolver = DrugResolver()
    resolver.load()

    total_expected = total_hits = total_spurious = 0
    total_dis_expected = total_dis_hits = 0
    all_hit_scores: list[float] = []
    all_sp_scores: list[float] = []
    skipped: list[str] = []
    document_types: dict[str, int] = {}

    for image in images:
        label_file = image.with_suffix(".txt")
        if not label_file.exists():
            skipped.append(f"{image.name} (thiếu {label_file.name})")
            continue
        expected = load_expected(label_file)
        if not expected:
            skipped.append(f"{image.name} (nhãn rỗng)")
            continue
        disease_file = image.parent / f"{image.stem}.benh.txt"
        expected_diseases = load_expected(disease_file) if disease_file.exists() else []

        report = evaluate_image(image, expected, expected_diseases, ocr, resolver, args.top)
        document_type = str(report["document_type"])
        document_types[document_type] = document_types.get(document_type, 0) + 1
        hit, want = len(report["hits"]), report["expected"]
        dhit, dwant = len(report["disease_hits"]), report["expected_diseases"]
        total_expected += want
        total_hits += hit
        total_spurious += len(report["spurious"])
        total_dis_expected += dwant
        total_dis_hits += dhit
        all_hit_scores += report['hit_scores']
        all_sp_scores += report['spurious_scores']

        perfect = hit == want and not report["spurious"] and dhit == dwant
        line = f"{'OK  ' if perfect else '    '}{image.name:12s} {hit}/{want} thuốc"
        if report["spurious"]:
            line += f"  +{len(report['spurious'])} thừa"
        if dwant:
            line += f"   |  {dhit}/{dwant} bệnh"
        if report["icd_codes"]:
            line += f"   ICD: {','.join(report['icd_codes'])}"
        print(line)
        if args.verbose:
            for want_name in report["misses"]:
                print(f"       TRƯỢT thuốc  {want_name[:58]}")
            for name in report["spurious"]:
                print(f"       THỪA  thuốc  {name[:58]}")
            for want_name in report["disease_misses"]:
                print(f"       TRƯỢT bệnh   {want_name[:58]}")

    print()
    if skipped:
        print("Bỏ qua (chưa gán nhãn):")
        for item in skipped:
            print(f"   {item}")
        print()

    if total_expected:
        recall = total_hits / total_expected * 100
        print(f"THUỐC  Top-{args.top}: {total_hits}/{total_expected} = {recall:.1f}% (recall)")
        if total_spurious:
            precision = total_hits / (total_hits + total_spurious) * 100
            print(f"       {total_spurious} dòng thừa -> precision {precision:.1f}%")
        if total_dis_expected:
            drec = total_dis_hits / total_dis_expected * 100
            print(f"BỆNH   đọc đúng chẩn đoán: {total_dis_hits}/{total_dis_expected} = {drec:.1f}%")
            print("       (chỉ đo khâu đọc chữ; việc khớp tên bệnh với CSDL nằm ở backend)")
        if all_hit_scores or all_sp_scores:
            import statistics as st
            print()
            print("PHÂN BỐ ĐIỂM  (để chọn ngưỡng từ chối)")
            for label, xs in (("đúng ", all_hit_scores), ("thừa ", all_sp_scores)):
                if not xs:
                    continue
                xs = sorted(xs)
                q = lambda f: xs[min(len(xs) - 1, int(len(xs) * f))]
                print(f"  {label} n={len(xs):3d}  min={xs[0]:.2f}  p10={q(.10):.2f}  p25={q(.25):.2f}"
                      f"  trung vị={st.median(xs):.2f}  p75={q(.75):.2f}  max={xs[-1]:.2f}")
            for t in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70):
                lost = sum(1 for x in all_hit_scores if x < t)
                cut = sum(1 for x in all_sp_scores if x < t)
                print(f"  ngưỡng {t:.2f}: bỏ được {cut:2d}/{len(all_sp_scores)} dòng thừa,"
                      f" mất {lost:2d}/{len(all_hit_scores)} dòng đúng")
        if document_types:
            summary = ", ".join(f"{key}={value}" for key, value in sorted(document_types.items()))
            print(f"PHÂN LOẠI TÀI LIỆU: {summary}")
    else:
        print("Chưa có nhãn nào để chấm. Điền các file .txt trong eval/end2end/ trước.")


if __name__ == "__main__":
    main()
