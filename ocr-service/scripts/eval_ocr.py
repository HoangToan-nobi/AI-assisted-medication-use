"""Measure OCR accuracy against ground truth, per recognizer.

Without numbers there is no way to tell an improvement from a rearrangement.
This scores the three configurations that matter:

    paddle   detection + PaddleOCR recognition (what the service used to do)
    vietocr  detection + VietOCR recognition on every region
    hybrid   detection + the arbitration in OCRService (what it does now)

Usage:
    python scripts/eval_ocr.py eval/            # every image in the directory
    python scripts/eval_ocr.py eval/ --config hybrid

Layout: for each image ``eval/<name>.<ext>`` a ``eval/<name>.txt`` holds the
expected text, one detected line per row, order-insensitive. Lines are matched
greedily to predictions by similarity before scoring, because detection order
is not something the recognizer controls.
"""

from __future__ import annotations

import argparse
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.ocr_service import OCRService  # noqa: E402
from app.utils.image_utils import prepare_image  # noqa: E402

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
CONFIGS = ("paddle", "vietocr", "hybrid")


def has_diacritics(text: str) -> bool:
    """True when the line contains a mark PaddleOCR's dictionary cannot encode."""
    return any("Ạ" <= char <= "ỹ" for char in text)


def cer(expected: str, actual: str) -> float:
    """Character error rate, NFC-normalized so composed/decomposed forms agree."""
    expected = unicodedata.normalize("NFC", expected)
    actual = unicodedata.normalize("NFC", actual)
    if not expected:
        return 0.0 if not actual else 1.0
    return Levenshtein.distance(expected, actual) / len(expected)


def align(expected: list[str], predicted: list[str]) -> list[tuple[str, str]]:
    """Pair each expected line with its best unused prediction.

    Detection order varies with layout, so scoring by index would report noise.
    Unmatched expected lines pair with "" and score as a full miss, which is
    what a dropped region deserves.
    """
    remaining = list(predicted)
    pairs = []
    for line in expected:
        if not remaining:
            pairs.append((line, ""))
            continue
        best = min(remaining, key=lambda candidate: cer(line, candidate))
        # A prediction that shares almost nothing is a miss, not a match; taking
        # it would also consume a candidate a later line may genuinely need.
        if cer(line, best) >= 0.9:
            pairs.append((line, ""))
            continue
        remaining.remove(best)
        pairs.append((line, best))
    return pairs


def build_service(config: str) -> OCRService:
    return OCRService(
        lang=settings.ocr_lang,
        device=settings.ocr_device,
        enable_mkldnn=settings.ocr_enable_mkldnn,
        ocr_version=settings.ocr_version,
        det_model=settings.ocr_det_model,
        rec_model=settings.ocr_rec_model,
        vietocr_enabled=config != "paddle",
        vietocr_model=settings.ocr_vietocr_model,
        vietocr_weights=settings.ocr_vietocr_weights,
        vietocr_batch_size=settings.ocr_vietocr_batch_size,
        torch_threads=settings.ocr_torch_threads,
    )


def read_lines(service: OCRService, image_path: Path, config: str) -> tuple[list[str], float]:
    prepared = prepare_image(
        image_path.read_bytes(),
        settings.max_image_dimension,
        settings.allowed_image_formats,
        settings.ocr_min_dimension,
    )
    started = time.perf_counter()
    items = service.recognize(prepared.array)
    elapsed = time.perf_counter() - started

    kept = [i for i in items if i["confidence"] >= settings.ocr_confidence_threshold]
    if config == "vietocr":
        # Bypass arbitration: score VietOCR's raw reading wherever it produced
        # one, so the hybrid column can be judged against its own inputs.
        return [str(i.get("vietocr_text") or i["text"]) for i in kept], elapsed
    return [str(i["text"]) for i in kept], elapsed


def evaluate(config: str, pairs: list[tuple[Path, Path]]) -> dict:
    service = build_service(config)
    service.load()
    if config != "paddle" and not service.vietocr_loaded:
        raise SystemExit(f"VietOCR failed to load, cannot score '{config}': {service.vietocr_error}")

    totals = {"chars": 0, "errors": 0, "lines": 0, "exact": 0, "seconds": 0.0}
    accented = {"chars": 0, "errors": 0, "lines": 0, "exact": 0}
    for image_path, truth_path in pairs:
        expected = [l.strip() for l in truth_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        predicted, elapsed = read_lines(service, image_path, config)
        totals["seconds"] += elapsed
        for line, prediction in align(expected, predicted):
            errors = Levenshtein.distance(
                unicodedata.normalize("NFC", line), unicodedata.normalize("NFC", prediction)
            )
            bucket = accented if has_diacritics(line) else None
            totals["chars"] += len(line)
            totals["errors"] += errors
            totals["lines"] += 1
            totals["exact"] += int(errors == 0)
            if bucket is not None:
                bucket["chars"] += len(line)
                bucket["errors"] += errors
                bucket["lines"] += 1
                bucket["exact"] += int(errors == 0)
    return {"config": config, "all": totals, "accented": accented, "images": len(pairs)}


def rate(bucket: dict) -> tuple[float, float]:
    cer_value = bucket["errors"] / bucket["chars"] if bucket["chars"] else 0.0
    exact = bucket["exact"] / bucket["lines"] if bucket["lines"] else 0.0
    return cer_value, exact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory of images + .txt ground truth")
    parser.add_argument("--config", choices=CONFIGS, action="append", help="Repeatable; default all")
    args = parser.parse_args()

    pairs = []
    for image_path in sorted(args.directory.iterdir()):
        if image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        truth_path = image_path.with_suffix(".txt")
        if truth_path.is_file():
            pairs.append((image_path, truth_path))
    if not pairs:
        raise SystemExit(
            f"No image/.txt pairs in {args.directory}. Each foo.png needs a foo.txt "
            "holding the expected text, one line per detected region."
        )

    print(f"{len(pairs)} image(s), device={settings.ocr_device}\n")
    header = f"{'config':<9}{'CER':>8}{'line acc':>10}{'CER (dấu)':>12}{'acc (dấu)':>11}{'s/ảnh':>9}"
    print(header)
    print("-" * len(header))
    for config in args.config or CONFIGS:
        result = evaluate(config, pairs)
        overall_cer, overall_exact = rate(result["all"])
        accent_cer, accent_exact = rate(result["accented"])
        seconds = result["all"]["seconds"] / result["images"]
        print(
            f"{config:<9}{overall_cer:>7.1%}{overall_exact:>10.1%}"
            f"{accent_cer:>11.1%}{accent_exact:>11.1%}{seconds:>9.2f}"
        )
    print(
        "\nCER lower is better. The 'dấu' columns cover only lines containing "
        "U+1EA0-U+1EF9 -- the characters PaddleOCR cannot represent."
    )


if __name__ == "__main__":
    main()
