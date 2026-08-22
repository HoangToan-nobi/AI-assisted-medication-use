"""OCR service, image preprocessing and HTTP endpoint tests.

No PaddleOCR model is loaded anywhere in this file.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from app.config import settings
from app.services.ocr_service import OCRService, OCRUnavailableError
from app.utils.image_utils import InvalidImageError, prepare_image
from app.services.prescription_resolver import classify_document, extract_medication_rows, extract_package_name
from tests.conftest import FakePaddleOCR2, FakePaddleOCR3, FakeVietOCR, make_image_bytes

ALLOWED = settings.allowed_image_formats


# --------------------------------------------------------------------------
# OCRService
# --------------------------------------------------------------------------


def test_parses_paddleocr_3x_result(hapacol_lines):
    service = OCRService(model=FakePaddleOCR3(hapacol_lines), vietocr_enabled=False)
    results = service.recognize(np.zeros((10, 10, 3), dtype=np.uint8))

    assert [r["text"] for r in results] == [text for text, _ in hapacol_lines]
    assert results[0]["confidence"] == pytest.approx(0.96)


def test_parses_paddleocr_2x_result(hapacol_lines):
    service = OCRService(model=FakePaddleOCR2(hapacol_lines), vietocr_enabled=False)
    results = service.recognize(np.zeros((10, 10, 3), dtype=np.uint8))

    assert [r["text"] for r in results] == [text for text, _ in hapacol_lines]
    assert results[1]["confidence"] == pytest.approx(0.91)


def test_model_is_loaded_once_not_per_request(hapacol_lines):
    fake = FakePaddleOCR3(hapacol_lines)
    service = OCRService(model=fake, vietocr_enabled=False)

    for _ in range(3):
        service.recognize(np.zeros((10, 10, 3), dtype=np.uint8))

    assert fake.calls == 3  # three predictions...
    assert service.loaded  # ...against one model instance


def test_recognize_reports_unavailable_model(monkeypatch):
    service = OCRService(vietocr_enabled=False)
    monkeypatch.setattr(service, "_build_model", lambda: (_ for _ in ()).throw(RuntimeError("no model")))

    with pytest.raises(OCRUnavailableError):
        service.recognize(np.zeros((10, 10, 3), dtype=np.uint8))
    assert "no model" in (service.load_error or "")


# --------------------------------------------------------------------------
# Recognizer arbitration
#
# The premise of every test below: PaddleOCR's latin dictionary contains no
# codepoint in U+1EA0-U+1EF9, so a reading containing one can only have come
# from VietOCR, and Paddle's competing reading is missing characters by
# construction rather than by chance.
# --------------------------------------------------------------------------


def test_diacritics_always_win_over_paddle():
    """Even a far more confident Paddle reading cannot supply the missing marks."""
    text, confidence, recognizer = OCRService._arbitrate("Thuc kê đơn", 0.99, "Thuốc kê đơn", 0.61)

    assert text == "Thuốc kê đơn"
    assert recognizer == "vietocr"
    assert confidence == pytest.approx(0.61)


def test_case_is_taken_from_paddle_and_letters_from_vietocr():
    """VietOCR's decoder normalizes case; Paddle reads glyph shapes and does not."""
    text, _, _ = OCRService._arbitrate(
        "H tên bnh nhân: Nguyn Th Hnh", 0.90, "họ tên bệnh nhân: nguyễn thị hạnh", 0.93
    )
    assert text == "Họ tên bệnh nhân: Nguyễn Thị Hạnh"


def test_case_restoration_ignores_stretches_the_two_disagree_on():
    """A Paddle misread must not leak capitals into words it got wrong."""
    # Paddle dropped characters mid-word; only the matching runs may be recased.
    assert OCRService._restore_case("thuốc bổ phế", "THUC B PH") == "THUốC Bổ PHế"
    # No agreement at all leaves VietOCR's reading untouched.
    assert OCRService._restore_case("thuốc bổ", "xyzw") == "thuốc bổ"


def test_case_restoration_never_changes_letters():
    """It is a capitalization pass, not a second arbitration."""
    restored = OCRService._restore_case("viên nén", "VIEN NEN")
    assert restored.lower() == "viên nén"


def test_numeric_region_stays_with_paddle():
    """VietOCR's language model invents words from bare figures; Paddle does not."""
    for figures in ("650mg", "10 x 10", "125 mg/5 ml", "1.5%"):
        text, _, recognizer = OCRService._arbitrate(figures, 0.95, "sáu trăm", 0.93)
        assert (text, recognizer) == (figures, "paddleocr"), figures


def test_alphanumeric_code_is_not_treated_as_numeric():
    """A registration number has letters, so it goes through the normal path."""
    assert not OCRService._is_numeric_region("VD-12345-17")
    assert OCRService._is_numeric_region("10x10")


def test_paddle_keeps_region_when_vietocr_drops_a_bracket():
    """Prescription aliases live in parentheses; losing one corrupts the field."""
    text, _, recognizer = OCRService._arbitrate(
        "Medrol (Methylprednisolon)", 0.94, "Medrol Methylprednisolon)", 0.95
    )
    assert (text, recognizer) == ("Medrol (Methylprednisolon)", "paddleocr")


def test_bracket_rule_never_costs_diacritics():
    """Correct words beat correct punctuation: the resolver folds tone marks anyway."""
    text, _, recognizer = OCRService._arbitrate("Thuc ho (B ph)", 0.94, "Thuốc ho Bổ phế", 0.90)
    assert (text, recognizer) == ("Thuốc ho Bổ phế", "vietocr")


def test_vietocr_keeps_close_calls_but_yields_to_a_clear_paddle_win():
    """Scores are not calibrated across recognizers, so ties must not decide."""
    _, _, close = OCRService._arbitrate("Augmentin", 0.90, "Augmentin", 0.85)
    _, _, clear = OCRService._arbitrate("Augmentin", 0.99, "Augmentn", 0.60)
    assert (close, clear) == ("vietocr", "paddleocr")


def test_empty_reading_falls_back_to_the_other_recognizer():
    assert OCRService._arbitrate("Hapacol", 0.9, "", 0.0)[2] == "paddleocr"
    assert OCRService._arbitrate("", 0.0, "Hapacol", 0.9)[2] == "vietocr"


def test_recognize_replaces_paddle_text_using_detected_polygons():
    """End-to-end through recognize(): detection geometry -> crop -> arbitration."""
    polys = [
        [[10, 10], [200, 10], [200, 50], [10, 50]],
        [[10, 60], [200, 60], [200, 100], [10, 100]],
    ]
    paddle = FakePaddleOCR3([("Thuc k don", 0.88), ("650mg", 0.97)], polys=polys)
    vietocr = FakeVietOCR([("Thuốc kê đơn", 0.93), ("sáu năm không", 0.80)])
    service = OCRService(model=paddle, vietocr_predictor=vietocr)

    results = service.recognize(np.zeros((200, 300, 3), dtype=np.uint8))

    assert [r["text"] for r in results] == ["Thuốc kê đơn", "650mg"]
    assert [r["recognizer"] for r in results] == ["vietocr", "paddleocr"]
    # Both readings survive for the eval harness; OCRItem drops them on the way out.
    assert results[1]["vietocr_text"] == "sáu năm không"
    # Internal geometry must not leak into the API payload.
    assert "_poly" not in results[0]


def test_recognition_batches_respect_the_configured_cap():
    """predict_batch has no internal bound; a dense page must not build one tensor."""
    polys = [[[0, i * 20], [50, i * 20], [50, i * 20 + 15], [0, i * 20 + 15]] for i in range(5)]
    paddle = FakePaddleOCR3([(f"line{i}", 0.9) for i in range(5)], polys=polys)
    vietocr = FakeVietOCR([(f"dòng{i}", 0.95) for i in range(5)])
    service = OCRService(model=paddle, vietocr_predictor=vietocr, vietocr_batch_size=2)

    service.recognize(np.zeros((200, 100, 3), dtype=np.uint8))

    assert vietocr.batches == [2, 2, 1]


def test_rectify_uprights_a_slanted_detection_box():
    """A photographed prescription is never axis-aligned."""
    image = np.zeros((300, 300, 3), dtype=np.uint8)
    slanted = [[20, 40], [220, 60], [216, 100], [16, 80]]

    crop = OCRService._rectify(image, slanted)

    assert crop is not None
    # ~201 px along the top edge, ~40 px tall, plus the tone-mark padding.
    assert 200 <= crop.width <= 215
    assert 45 <= crop.height <= 60


def test_rectify_rejects_degenerate_geometry():
    image = np.zeros((50, 50, 3), dtype=np.uint8)
    assert OCRService._rectify(image, [[5, 5], [5, 5], [5, 5], [5, 5]]) is None
    assert OCRService._rectify(image, None) is None


def test_vietocr_failure_does_not_fail_the_page():
    """Without VietOCR the text is wrong, but the request must still answer."""

    class ExplodingVietOCR:
        def predict_batch(self, imgs, return_prob=False):
            raise RuntimeError("checkpoint corrupt")

    polys = [[[10, 10], [200, 10], [200, 50], [10, 50]]]
    service = OCRService(
        model=FakePaddleOCR3([("Thuc", 0.9)], polys=polys),
        vietocr_predictor=ExplodingVietOCR(),
    )
    results = service.recognize(np.zeros((100, 300, 3), dtype=np.uint8))

    assert [r["text"] for r in results] == ["Thuc"]


# --------------------------------------------------------------------------
# Image preprocessing
# --------------------------------------------------------------------------


def test_prepare_image_returns_bgr_array_and_blur_score():
    prepared = prepare_image(make_image_bytes(), settings.max_image_dimension, ALLOWED)

    assert prepared.array.ndim == 3 and prepared.array.shape[2] == 3
    assert prepared.image_format == "PNG"
    assert prepared.blur_score > 0


def test_large_image_is_resized_keeping_aspect_ratio():
    data = make_image_bytes(size=(3200, 1600))
    prepared = prepare_image(data, 1600, ALLOWED)

    assert max(prepared.width, prepared.height) == 1600
    assert prepared.original_width == 3200
    # 2:1 in, 2:1 out.
    assert prepared.width / prepared.height == pytest.approx(2.0, abs=0.01)


def test_small_image_is_not_upscaled():
    prepared = prepare_image(make_image_bytes(size=(200, 100)), 1600, ALLOWED)
    assert (prepared.width, prepared.height) == (200, 100)


def test_flat_image_scores_lower_than_textured_image():
    """Laplacian variance must separate detail-free images from detailed ones."""
    textured = prepare_image(make_image_bytes(), settings.max_image_dimension, ALLOWED)

    buffer = io.BytesIO()
    Image.new("RGB", (240, 160), "gray").save(buffer, format="PNG")
    flat = prepare_image(buffer.getvalue(), settings.max_image_dimension, ALLOWED)

    assert flat.blur_score == pytest.approx(0.0, abs=1e-6)
    assert textured.blur_score > flat.blur_score


def test_exif_orientation_is_applied():
    """A phone photo tagged Orientation=6 must be uprighted before OCR."""
    image = Image.new("RGB", (200, 100), "white")
    exif = image.getexif()
    exif[274] = 6  # rotate 90 CW on display
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes())

    prepared = prepare_image(buffer.getvalue(), settings.max_image_dimension, ALLOWED)
    assert (prepared.width, prepared.height) == (100, 200)


def test_image_without_exif_is_left_alone():
    buffer = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(buffer, format="JPEG")

    prepared = prepare_image(buffer.getvalue(), settings.max_image_dimension, ALLOWED)
    assert (prepared.width, prepared.height) == (200, 100)


def test_non_image_bytes_are_rejected():
    with pytest.raises(InvalidImageError):
        prepare_image(b"this is definitely not an image", 1600, ALLOWED)


def test_disallowed_image_format_is_rejected():
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format="BMP")
    with pytest.raises(InvalidImageError):
        prepare_image(buffer.getvalue(), 1600, ALLOWED)


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "WEBP"])
def test_allowed_formats_decode(image_format):
    prepared = prepare_image(make_image_bytes(image_format=image_format), 1600, ALLOWED)
    assert prepared.image_format == image_format


# --------------------------------------------------------------------------
# HTTP endpoints
# --------------------------------------------------------------------------


def test_health_endpoint(client):
    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["ocr_model_loaded"] is True
    assert body["drug_database_loaded"] is True
    assert body["drug_count"] > 0
    # Reported separately from ocr_model_loaded: the service answers without
    # VietOCR, but no Vietnamese diacritic can be read while it is down.
    assert body["vietocr_loaded"] is True
    assert body["vietocr_error"] is None


def test_ocr_endpoint_response_schema(client):
    response = client.post(
        "/api/v1/ocr", files={"image": ("box.png", make_image_bytes(), "image/png")}
    )
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["raw_text"].startswith("HAPAC0L")
    assert body["normalized_text"]
    assert {"text", "confidence"} <= set(body["ocr_results"][0])
    assert body["metadata"]["blur_score"] > 0
    assert body["metadata"]["processing_time_ms"] >= 0


def test_low_confidence_regions_are_dropped(client):
    body = client.post(
        "/api/v1/ocr", files={"image": ("box.png", make_image_bytes(), "image/png")}
    ).json()

    # The "noise" region scores 0.2, below OCR_CONFIDENCE_THRESHOLD.
    assert all(item["confidence"] >= settings.ocr_confidence_threshold for item in body["ocr_results"])
    assert "noise" not in body["raw_text"]


def test_raw_text_carries_the_arbitrated_reading_not_paddles(client, hapacol_lines):
    """raw_text must never fall back to a transcription that has no diacritics.

    Regression guard: raw_text used to prefer the `paddle_text` debug field,
    which is missing every U+1EA0-U+1EF9 character by construction.
    """
    import app.main as main

    polys = [[[10, 10 + i * 40], [300, 10 + i * 40], [300, 40 + i * 40], [10, 40 + i * 40]]
             for i in range(2)]
    main.ocr_service._model = FakePaddleOCR3([("Thuc", 0.9), ("Hot cht", 0.9)], polys=polys)
    main.ocr_service._vietocr_predictor = FakeVietOCR([("Thuốc", 0.95), ("Hoạt chất", 0.95)])

    for endpoint in ("/api/v1/ocr", "/api/v1/drug/recognize"):
        main.ocr_service._model = FakePaddleOCR3(
            [("Thuc", 0.9), ("Hot cht", 0.9)], polys=polys
        )
        main.ocr_service._vietocr_predictor = FakeVietOCR(
            [("Thuốc", 0.95), ("Hoạt chất", 0.95)]
        )
        body = client.post(
            endpoint, files={"image": ("box.png", make_image_bytes(), "image/png")}
        ).json()
        assert body["raw_text"] == "Thuốc\nHoạt chất", endpoint
        assert "Hot cht" not in body["normalized_text"], endpoint


def test_invalid_file_returns_structured_error(client):
    response = client.post(
        "/api/v1/ocr", files={"image": ("payload.txt", b"not an image", "text/plain")}
    )
    body = response.json()

    assert response.status_code == 400
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_IMAGE"
    assert "traceback" not in response.text.lower()


def test_client_filename_is_not_trusted(client):
    """A .png name on non-image bytes must still be rejected."""
    response = client.post(
        "/api/v1/ocr", files={"image": ("innocent.png", b"MZ\x90\x00 not a png", "image/png")}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


def test_oversized_file_is_rejected(client):
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (settings.max_file_size_bytes + 1024)
    response = client.post(
        "/api/v1/ocr", files={"image": ("big.png", oversized, "image/png")}
    )
    body = response.json()

    assert response.status_code == 413
    assert body["error"]["code"] == "FILE_TOO_LARGE"


def test_recognize_endpoint_returns_candidates_and_requires_confirmation(client):
    response = client.post(
        "/api/v1/drug/recognize",
        files={"image": ("box.png", make_image_bytes(), "image/png")},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["requires_confirmation"] is True


def test_prescription_is_classified_and_split_into_rows():
    items = [
        {"text": "ĐƠN THUỐC", "confidence": 0.99},
        {"text": "THÔNG TIN BỆNH NHÂN", "confidence": 0.99},
        {"text": "CÁCH DÙNG", "confidence": 0.99},
        {"text": "1", "confidence": 0.99},
        {"text": "Medrol 4mg", "confidence": 0.99},
        {"text": "2", "confidence": 0.99},
        {"text": "Prograf 1mg", "confidence": 0.99},
    ]
    assert classify_document(items) == "prescription"
    rows = extract_medication_rows(items)
    assert [row["row_number"] for row in rows] == [1, 2]
    assert rows[0]["texts"] == ["1", "Medrol 4mg"]


def test_prescription_geometry_groups_cells_in_one_row():
    def item(text, x, y):
        return {"text": text, "confidence": 0.99, "bbox": [[x, y], [x + 30, y], [x + 30, y + 20], [x, y + 20]]}

    items = [
        {"text": "ĐƠN THUỐC", "confidence": 0.99},
        item("1", 10, 200), item("Tacrolimus", 60, 200), item("Prograf 1mg", 180, 200),
        item("2", 10, 300), item("Exforge 5mg + 80mg", 60, 300),
    ]
    rows = extract_medication_rows(items)
    assert len(rows) == 2
    assert rows[0]["texts"] == ["1", "Tacrolimus", "Prograf 1mg"]


def test_package_name_is_separated_from_packaging_copy():
    def item(text, x, y, w, h):
        return {"text": text, "confidence": 0.99, "bbox": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]}

    items = [
        item("Health Supplement", 10, 10, 100, 10),
        item("VITAMIN", 10, 50, 450, 100),
        item("6B", 20, 140, 210, 140),
        item("DK", 230, 160, 130, 80),
        item("Box of 10 blisters", 10, 500, 300, 20),
    ]
    selected = extract_package_name(items)
    assert [item["text"] for item in selected] == ["VITAMIN", "6B", "DK"]


def test_recognize_never_auto_confirms(client):
    """`requires_confirmation` is structurally pinned to True."""
    body = client.post(
        "/api/v1/drug/recognize",
        files={"image": ("box.png", make_image_bytes(), "image/png")},
    ).json()
    assert body["requires_confirmation"] is True


# --------------------------------------------------------------------------
# Prescription row parsing
#
# Cases taken from a real Bệnh viện Bình Dân prescription where 3 of 6
# medications were dropped.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1. YESOM 40 40mg (Esomeprazol 40mg)", 1),
        # OCR read this row's "4." as "4," on the real image, which used to
        # disqualify the row entirely and left "4," inside the drug name.
        ("4, PAPAZE (magnesi aluminometasilicate ,na", 4),
        # A pen stroke in the margin is detected as its own glyph and glued to
        # the front of the row.
        ("(2. SUCRATE GEL (Sucralfate 1g (goi))", 2),
        ("6. DIGLUMISAN (L-Arginine Hydrocloride 1000mg)", 6),
    ],
)
def test_row_numbers_survive_ocr_separator_variants(text, expected):
    from app.services.prescription_resolver import _row_number

    assert _row_number(text, x1=100.0, page_right=1000.0) == expected


@pytest.mark.parametrize(
    "text",
    [
        "12:46",          # header clock; ':' must never separate a row number
        "Tuổi : 49",
        "Cộng khoản:6",
        "Ngày uống 3 lần, mỗi lần 1 Viên",
    ],
)
def test_non_rows_are_not_promoted_to_medications(text):
    from app.services.prescription_resolver import _is_schedule_text, _row_number

    assert _row_number(text, x1=100.0, page_right=1000.0) is None or _is_schedule_text(text)


def test_row_number_is_stripped_from_the_drug_name():
    """A name reaching the resolver as "4, PAPAZE" cannot match the database."""
    from app.services.prescription_resolver import _clean_medication_name

    assert _clean_medication_name("4, PAPAZE (magnesi").startswith("PAPAZE")
    assert _clean_medication_name("(2. SUCRATE GEL").startswith("SUCRATE GEL")


def test_real_prescription_yields_every_medication_row():
    """All six rows of a real Bình Dân prescription, from its actual OCR output.

    Detection and recognition were never the problem on this image: all six
    medication lines were found and read correctly. Three were lost in row
    parsing alone, because OCR rendered `4.` `5.` `6.` as `4,` `5,` `6,` and a
    pen stroke in the margin prefixed row 2 with `(`.
    """
    import json
    from pathlib import Path

    from app.services.prescription_resolver import classify_document

    fixture = Path(__file__).parent / "data" / "binhdan_ocr.json"
    items = [
        {"text": t, "confidence": c, "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]}
        for t, c, x1, y1, x2, y2 in json.loads(fixture.read_text(encoding="utf-8"))
    ]

    assert classify_document(items) == "prescription"
    rows = extract_medication_rows(items)
    assert [row["row_number"] for row in rows] == [1, 2, 3, 4, 5, 6]

    names = {row["row_number"]: " ".join(row["name_texts"]) for row in rows}
    assert names[1].startswith("YESOM 40")
    assert names[2].startswith("SUCRATE GEL")
    assert names[4].startswith("PAPAZE")     # not "4, PAPAZE"
    assert names[5].startswith("BIOCID MH")
    assert names[6].startswith("DIGLUMISAN")


def test_figures_are_taken_from_paddle_not_vietocr():
    """VietOCR decodes digits through a language model and gets them wrong.

    Both cases are from a real prescription: it read `tháng 09` as `tháng 00`
    and `3.5+2g` as `3.5%2g`.
    """
    assert OCRService._restore_case(
        "Ngày khám Ngày 25 tháng 00 năm 2014", "Ngày khám Ngày 25 tháng 09 nām 2014"
    ) == "Ngày khám Ngày 25 tháng 09 năm 2014"
    assert OCRService._restore_case(
        "5, BIOCID MH 3.5%2g", "5. BIOCID MH 3.5+2g"
    ) == "5. BIOCID MH 3.5+2g"


def test_figure_transfer_never_crosses_into_a_word():
    """Only all-figure runs of equal length may be substituted."""
    # Paddle's "DAN" must not overwrite VietOCR's "CÂN": those are letters.
    assert OCRService._restore_case("BỆNH VIỆN BÌNH CÂN", "BENH VIEN BINH DAN") == "BỆNH VIỆN BÌNH CÂN"


def test_nothing_is_copied_between_readings_that_disagree():
    """Coincidental short matches used to produce "nguyễN Thị hạNh"."""
    # Two different regions' text: no transfer at all, VietOCR survives intact.
    assert (
        OCRService._restore_case("họ tên: nguyễn thị hạnh", "H tên: TRÀN TRUNG")
        == "họ tên: nguyễn thị hạnh"
    )
    # The same region, read by both: case is restored.
    assert (
        OCRService._restore_case("họ tên: nguyễn thị hạnh", "H tên: Nguyn Thj Hnh")
        == "Họ tên: Nguyễn Thị Hạnh"
    )


def test_row_number_read_as_a_letter_is_taken_from_paddle():
    """VietOCR read `1.` as `T.` and `4.` as `A.` on a real prescription.

    Each cost a whole medication: the row never parsed. Paddle spaces the
    separator differently ("1 ." against "T."), so the runs differ in length.
    """
    assert OCRService._restore_case(
        "T. Spetcely 200mg (Cetpodoxime)", "1 . Speteefy 200 mg (Cefpodoxime)"
    ).startswith("1.")
    assert OCRService._restore_case("A.Furosin 5020mg", "4 . Furosin 50/20 mg").startswith("4.")


def test_only_a_leading_initial_may_become_a_digit():
    """Anywhere else, a letter is a letter: Paddle cannot rewrite words."""
    # Paddle misread the 'T' of a word; VietOCR's reading must survive intact.
    assert OCRService._restore_case("Thuốc bổ phế", "7huoc bo phe") == "Thuốc bổ phế"
    # 'L' is mid-string, not the row-number position.
    assert OCRService._restore_case("Trưa: L.00", "Trua: 1.00") == "Trưa: L.00"


def test_separator_lost_from_inside_a_number_is_recovered():
    """`50/20 mg` came back as `5020mg`, which destroys strength extraction."""
    assert "50/20" in OCRService._restore_case("A.Furosin 5020mg", "4 . Furosin 50/20 mg")
    # Paddle's stray spaces are not pulled in with it.
    assert "Furosin 50/20mg" in OCRService._restore_case("A.Furosin 5020mg", "4 . Furosin 50/20 mg")
