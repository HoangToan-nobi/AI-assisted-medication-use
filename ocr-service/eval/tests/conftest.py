"""Shared fixtures.

PaddleOCR and VietOCR are always mocked here: the unit suite must not download
or load a model. Only the fakes' output shapes matter, and they mirror the real
PaddleOCR 2.x/3.x result formats that ``OCRService._parse`` handles, plus
``vietocr.tool.predictor.Predictor.predict_batch``.

Tests that are not about recognition pass ``vietocr_enabled=False`` so that
``OCRService.recognize`` never reaches for the real 150 MB checkpoint.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

# Make `app` importable when pytest is invoked from anywhere.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("EAGER_LOAD_OCR", "false")

SAMPLE_CSV = ROOT / "app" / "data" / "drugs.csv"
# Keep endpoint tests fast and deterministic; production defaults to the
# temporary 43,970-row registry CSV through app.config.
os.environ.setdefault("DRUGS_CSV_PATH", str(SAMPLE_CSV))


class FakePaddleOCR3:
    """Mimics PaddleOCR 3.x: `.predict()` -> list of dict-like pages.

    ``polys`` is optional. Left out, the page carries no geometry, so
    ``_rectify`` produces no crops and VietOCR is never consulted -- which is
    what the tests that only care about parsing want.
    """

    def __init__(self, lines: list[tuple[str, float]], polys: list | None = None) -> None:
        self.lines = lines
        self.polys = polys
        self.calls = 0

    def predict(self, _image):
        self.calls += 1
        page = {
            "rec_texts": [text for text, _ in self.lines],
            "rec_scores": [score for _, score in self.lines],
        }
        if self.polys is not None:
            page["rec_polys"] = self.polys
        return [page]


class FakeVietOCR:
    """Mimics `vietocr.tool.predictor.Predictor.predict_batch`.

    Returns queued `(text, prob)` pairs in call order, so a test states the
    recognizer's readings without any tensor work.
    """

    def __init__(self, readings: list[tuple[str, float]]) -> None:
        self.readings = list(readings)
        self.batches: list[int] = []

    def predict_batch(self, imgs, return_prob=False):
        self.batches.append(len(imgs))
        taken, self.readings = self.readings[: len(imgs)], self.readings[len(imgs) :]
        # Guard against a test queueing fewer readings than there are crops.
        assert len(taken) == len(imgs), "FakeVietOCR ran out of queued readings"
        sentences = [text for text, _ in taken]
        return (sentences, [prob for _, prob in taken]) if return_prob else sentences


class FakePaddleOCR2:
    """Mimics PaddleOCR 2.x: `.ocr()` -> [[[box, (text, score)], ...]]."""

    def __init__(self, lines: list[tuple[str, float]]) -> None:
        self.lines = lines

    def ocr(self, _image, cls=True):
        box = [[0, 0], [1, 0], [1, 1], [0, 1]]
        return [[[box, (text, score)] for text, score in self.lines]]


def make_image_bytes(
    size: tuple[int, int] = (240, 160),
    image_format: str = "PNG",
    color: str = "white",
) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", size, color)
    # Some texture so the blur score is not identically zero.
    for x in range(0, size[0], 8):
        for y in range(0, size[1], 8):
            image.putpixel((x, y), (0, 0, 0))
    image.save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.fixture
def sample_csv() -> Path:
    return SAMPLE_CSV


@pytest.fixture
def hapacol_lines() -> list[tuple[str, float]]:
    """A realistic misread of a Hapacol 650 box."""
    return [("HAPAC0L", 0.96), ("65O", 0.91), ("Paracetamol 650mg", 0.93), ("noise", 0.2)]


@pytest.fixture
def client(hapacol_lines):
    """TestClient with the OCR model replaced by a fake and the DB loaded."""
    from fastapi.testclient import TestClient

    import app.main as main

    main.ocr_service._model = FakePaddleOCR3(hapacol_lines)
    main.ocr_service._load_error = None
    # A non-None predictor short-circuits _load_vietocr, so the endpoint tests
    # never touch the real checkpoint. The fake page carries no geometry, so no
    # crop is ever handed to it.
    main.ocr_service._vietocr_predictor = FakeVietOCR([])
    with TestClient(main.app) as test_client:
        yield test_client
