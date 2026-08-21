"""Runtime configuration.

Every value is overridable through environment variables so the same image can
run on CPU today and on GPU later without touching application code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DEFAULT_DRUGS_CSV = APP_DIR / "data" / "thuoc_final_project.csv"


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # --- Upload / security -------------------------------------------------
    max_file_size_bytes: int = field(
        default_factory=lambda: _env_int("MAX_FILE_SIZE_BYTES", 10 * 1024 * 1024)
    )
    max_batch_images: int = field(
        default_factory=lambda: _env_int("MAX_BATCH_IMAGES", 5)
    )
    # Formats are validated from the decoded image itself, never the filename.
    allowed_image_formats: frozenset[str] = frozenset({"JPEG", "PNG", "WEBP"})

    # --- Image preprocessing ----------------------------------------------
    max_image_dimension: int = field(
        default_factory=lambda: _env_int("MAX_IMAGE_DIMENSION", 1600)
    )
    ocr_min_dimension: int = field(
        default_factory=lambda: _env_int("OCR_MIN_DIMENSION", 1200)
    )

    # --- OCR ---------------------------------------------------------------
    # PaddleOCR is used for *detection*. Its recognizer cannot read Vietnamese:
    # every ``lang`` in its latin group shares an 836-character dictionary that
    # omits the entire U+1EA0-U+1EF9 block, so ``Thuốc`` can only ever come back
    # as ``Thuc``. VietOCR below owns recognition -- see ocr_service.py.
    ocr_lang: str = field(default_factory=lambda: os.getenv("OCR_LANG", "vi"))
    ocr_device: str = field(default_factory=lambda: os.getenv("OCR_DEVICE", "cpu"))
    ocr_confidence_threshold: float = field(
        default_factory=lambda: _env_float("OCR_CONFIDENCE_THRESHOLD", 0.5)
    )
    # oneDNN gives roughly a 4x CPU speedup and is the difference between a
    # 12 s and a 3 s response on a busy drug box. It requires paddlepaddle
    # 3.2.x -- see the pin and the comment in requirements.txt.
    ocr_enable_mkldnn: bool = field(
        default_factory=lambda: _env_bool("OCR_ENABLE_MKLDNN", True)
    )
    # PP-OCRv6 Medium is the accuracy/speed default in PaddleOCR 3.7.
    # Set OCR_VERSION=PP-OCRv5 only when an older checkpoint is required.
    ocr_version: str = field(
        default_factory=lambda: os.getenv("OCR_VERSION", "PP-OCRv6").strip()
    )
    # Legacy override for machines that cannot load the v6 checkpoint.
    ocr_model_tier: str = field(
        default_factory=lambda: os.getenv("OCR_MODEL_TIER", "server").strip().lower()
    )
    # Detection is now the only job PaddleOCR does that affects Vietnamese text.
    # The mobile checkpoint was expected to trade recall for speed on hard
    # images; measured on a real 45-region photographed prescription it did not:
    # both tiers found all six medications, at 6.2 s against 11.2 s end to end.
    # On the clean eval/ renders both also scored identically (1.9 s vs 4.2 s).
    # Set OCR_DET_MODEL=PP-OCRv5_server_det to spend the extra time anyway.
    ocr_det_model: str = field(
        default_factory=lambda: os.getenv("OCR_DET_MODEL", "PP-OCRv5_mobile_det")
    )
    # Paddle recognition is now only the second opinion on numeric regions, so
    # the cheapest latin checkpoint (8 MB) is preferred over PP-OCRv6_medium_rec
    # (76 MB) -- neither can read Vietnamese, and this one is far faster.
    ocr_rec_model: str = field(
        default_factory=lambda: os.getenv("OCR_REC_MODEL", "latin_PP-OCRv5_mobile_rec")
    )
    # The only component that can produce Vietnamese diacritics. Turning this
    # off does not degrade results gracefully -- it makes every accented word
    # wrong. It exists as an escape hatch for latin-only deployments.
    ocr_vietocr_enabled: bool = field(
        default_factory=lambda: _env_bool("OCR_VIETOCR_ENABLED", True)
    )
    ocr_vietocr_model: str = field(
        default_factory=lambda: os.getenv("OCR_VIETOCR_MODEL", "vgg_transformer")
    )
    # vietocr's own downloader caches into /tmp, which a container loses on
    # every restart. Point at a file baked into the image instead.
    ocr_vietocr_weights: str = field(
        default_factory=lambda: os.getenv(
            "OCR_VIETOCR_WEIGHTS", str(APP_DIR.parent / "models" / "vgg_transformer.pth")
        )
    )
    # predict_batch buckets by width but sets no upper bound; this caps how many
    # crops become one tensor on a dense prescription.
    ocr_vietocr_batch_size: int = field(
        default_factory=lambda: _env_int("OCR_VIETOCR_BATCH_SIZE", 32)
    )
    # Paddle's oneDNN already spreads across every core. Letting torch do the
    # same makes the two contend and is a net loss on a busy box.
    ocr_torch_threads: int = field(
        default_factory=lambda: _env_int("OCR_TORCH_THREADS", min(8, os.cpu_count() or 4))
    )

    # --- Drug resolver -----------------------------------------------------
    drugs_csv_path: Path = field(
        default_factory=lambda: Path(os.getenv("DRUGS_CSV_PATH", str(DEFAULT_DRUGS_CSV)))
    )
    max_candidates: int = field(default_factory=lambda: _env_int("MAX_CANDIDATES", 3))
    # How many drugs survive the cheap name-similarity pass and get fully rescored.
    shortlist_size: int = field(default_factory=lambda: _env_int("SHORTLIST_SIZE", 200))
    # Longest run of consecutive OCR lines glued together into one candidate.
    max_line_window: int = field(default_factory=lambda: _env_int("MAX_LINE_WINDOW", 3))

    weight_name: float = field(default_factory=lambda: _env_float("WEIGHT_NAME", 0.75))
    weight_strength: float = field(
        default_factory=lambda: _env_float("WEIGHT_STRENGTH", 0.15)
    )
    weight_ingredient: float = field(
        default_factory=lambda: _env_float("WEIGHT_INGREDIENT", 0.10)
    )

    drug_high_confidence: float = field(
        default_factory=lambda: _env_float("DRUG_HIGH_CONFIDENCE", 0.90)
    )
    drug_medium_confidence: float = field(
        default_factory=lambda: _env_float("DRUG_MEDIUM_CONFIDENCE", 0.75)
    )

    # --- Startup behaviour -------------------------------------------------
    # Off by default so `pytest` and `--reload` do not pay the model-load cost.
    eager_load_ocr: bool = field(default_factory=lambda: _env_bool("EAGER_LOAD_OCR", True))

    def strength_neutral_score(self) -> float:
        """Score used when the image shows no strength at all.

        Neither evidence for nor against a row, so it must not out-rank a real
        strength match nor punish rows as hard as a contradicted strength.
        """
        return 0.25


settings = Settings()
