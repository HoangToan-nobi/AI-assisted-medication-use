"""OCR service, image preprocessing and HTTP endpoint tests.

No PaddleOCR model is loaded anywhere in this file.
"""

from __future__ import annotations

import io

import cv2
import numpy as np
import pytest
from PIL import Image

from app.config import settings
from app.services.ocr_service import (
    OCRService,
    OCRUnavailableError,
    filter_ocr_results,
)
from app.utils.image_utils import (
    InvalidImageError,
    enhance_top_band,
    prepare_image,
    rectify_document,
)
from app.services.prescription_resolver import (
    _is_schedule_text,
    classify_document,
    extract_medication_rows,
    extract_package_name,
    extract_package_products,
    extract_prescription_conditions,
)
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


def test_confidence_gate_keeps_a_real_region_seen_clearly_by_paddle():
    item = {
        "text": "ĐƠN THUỐC",
        "confidence": 0.20,
        "paddle_confidence": 0.99,
        "vietocr_confidence": 0.20,
    }

    assert filter_ocr_results([item], 0.50) == [item]


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


def test_enhance_top_band_changes_only_the_configured_top_region():
    image = np.full((100, 120, 3), 180, dtype=np.uint8)
    image[:20, 20:100] = 170

    enhanced = enhance_top_band(image, ratio=0.2)

    assert not np.array_equal(enhanced[:20], image[:20])
    assert np.array_equal(enhanced[20:], image[20:])


def test_rectify_document_warps_a_large_bright_paper_quadrilateral():
    image = np.full((900, 1000, 3), 35, dtype=np.uint8)
    paper = np.array([[180, 210], [825, 95], [900, 690], [120, 785]], dtype=np.int32)
    cv2.fillConvexPoly(image, paper, (235, 235, 235))
    # Interior rules give the synthetic page enough document-like structure;
    # they are not required for detecting its boundary.
    for offset in range(300, 680, 55):
        cv2.line(image, (210, offset), (760, offset - 80), (80, 80, 80), 3)

    rectified = rectify_document(image)

    assert rectified is not None
    assert rectified.shape[1] > rectified.shape[0]
    assert rectified.mean() > image.mean()


def test_rectify_document_leaves_an_image_without_a_paper_boundary_alone():
    assert rectify_document(np.full((600, 800, 3), 180, dtype=np.uint8)) is None


def test_missing_row_digit_as_punctuation_uses_name_strength_and_aligned_unit():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.95,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    items = [
        item("TÊN THUỐC", 150, 30, 330, 55),
        item("1/ Alpha 100mg", 80, 90, 310, 120),
        item("Viên", 650, 90, 710, 120),
        item("2y Beta 60ml", 80, 155, 310, 185),
        item("Chai", 650, 155, 710, 185),
        item("3/ Gamma 150mg", 80, 220, 330, 250),
        item("Viên", 650, 220, 710, 250),
    ]

    rows = extract_medication_rows(items)

    assert [" ".join(row["name_texts"]) for row in rows] == [
        "Alpha 100mg",
        "Beta 60ml",
        "Gamma 150mg",
    ]


def test_dosage_instruction_cannot_become_an_implicit_medication_row():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.95,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    rows = extract_medication_rows([
        item("TÊN THUỐC", 150, 30, 330, 55),
        item("1/ Alpha 100mg", 80, 90, 310, 120),
        item("- Uống 5ml khi sốt", 80, 155, 310, 185),
        item("Chai", 650, 155, 710, 185),
        item("2/ Gamma 150mg", 80, 220, 330, 250),
    ])

    assert [" ".join(row["name_texts"]) for row in rows] == [
        "Alpha 100mg",
        "Gamma 150mg",
    ]


def test_unnumbered_strength_list_and_missing_first_row_are_recovered():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.95,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    unnumbered = extract_medication_rows([
        item("Tên thuốc - Hàm lượng", 180, 30, 430, 55),
        item("Alpha + Beta 40mg + 5mg", 30, 90, 340, 120),
        item("Uống sáng 1 viên", 30, 125, 230, 150),
        item("Gamma 75mg", 30, 170, 220, 200),
        item("Uống tối 1 viên", 30, 205, 220, 230),
    ])
    missing_first = extract_medication_rows([
        item("I. Đơn thuốc", 30, 20, 180, 45),
        item("uros 40mg", 100, 70, 240, 100),
        item("Sáng uống 1.00", 120, 105, 270, 130),
        item("00", 250, 106, 285, 130),
        item("2 (Delta 50mg) Brand", 80, 150, 330, 180),
    ])

    assert [row["name_texts"][0] for row in unnumbered] == [
        "Alpha + Beta 40mg + 5mg",
        "Gamma 75mg",
    ]
    assert [row["name_texts"][0] for row in missing_first] == [
        "uros 40mg",
        "Delta 50mg) Brand",
    ]


def test_duplicate_header_number_and_trailing_footer_are_not_medications():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.95,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    rows = extract_medication_rows([
        item("ĐƠN THUỐC", 250, 20, 430, 50),
        item("1. Khoa Khám Bệnh. CKI. Nguyễn Văn A", 30, 80, 430, 105),
        item("1. Lisinopril 5mg", 40, 120, 280, 150),
        item("2. Calcium 500mg", 40, 180, 280, 210),
        item("PHÁT THU", 250, 270, 390, 300),
        item("Số ngày dùng", 50, 320, 220, 350),
    ])

    assert [row["name_texts"][0] for row in rows] == [
        "Lisinopril 5mg",
        "Calcium 500mg",
    ]


def test_prepare_image_rejects_pixel_bombs_before_rgb_conversion():
    data = make_image_bytes(size=(20, 20))

    with pytest.raises(InvalidImageError):
        prepare_image(data, 1600, ALLOWED, max_input_pixels=399)


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


def test_health_returns_503_when_required_ocr_is_not_ready(client, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main.ocr_service, "_model", None)
    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "error"


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


def test_bank_transfer_is_not_sent_to_the_drug_resolver():
    items = [
        {"text": "Chi tiết giao dịch"},
        {"text": "Chuyển khoản đến"},
        {"text": "Số tài khoản 2151866884"},
        {"text": "Mã giao dịch FT25160058593509"},
    ]

    assert classify_document(items) == "unknown"


def test_restaurant_receipt_is_not_a_medicine_package():
    # Regression for check2.png: old substring rules counted Ngày->ngay,
    # Xào Tỏi->toi, Tổng/Rồng->ong and the short column heading SL.
    items = [
        {"text": "NHÀ HÀNG TOÀN NGỌC"},
        {"text": "HÓA ĐƠN THANH TOÁN"},
        {"text": "Ngày: 26/07/2020"},
        {"text": "Thu ngân: Phạm Văn Toàn"},
        {"text": "Tên món"},
        {"text": "SL"},
        {"text": "3. Xào Tỏi"},
        {"text": "Tổng thanh toán 1.740.000đ"},
    ]

    assert classify_document(items) == "unknown"


def test_minimal_drug_package_with_a_real_strength_is_recognized():
    items = [{"text": "Panadol 500mg"}, {"text": "GSK"}]

    assert classify_document(items) == "medicine_package"


def test_cropped_numbered_prescription_without_a_heading_is_recognized():
    items = [
        {"text": "1 Diouf 10mg"},
        {"text": "Sáng 1/2 viên; Tối 1/2 viên"},
        {"text": "2 Sulpiride 50mg"},
        {"text": "Sáng 1 viên; Tối 1 viên"},
    ]

    assert classify_document(items) == "prescription"


def test_pharmacy_sales_slip_remains_a_medication_list():
    items = [
        {"text": "1 MOVINAVIR 200"},
        {"text": "40 Viên"},
        {"text": "2 AT ZINC 10MG"},
        {"text": "20 Viên"},
        {"text": "3 NAGAPOLIS"},
        {"text": "1 Chai"},
        {"text": "Tổng tiền: 774,000"},
        {"text": "Quý khách vui lòng kiểm tra thuốc khi nhận"},
    ]

    assert classify_document(items) == "prescription"


def test_no_geometry_fallback_does_not_turn_a_date_into_a_medication():
    rows = extract_medication_rows([
        {"text": "27/07/2020"},
        {"text": "Nguyễn Văn A"},
        {"text": "1. Panadol 500mg"},
    ])

    assert len(rows) == 1
    assert rows[0]["row_number"] == 1
    assert rows[0]["name_texts"] == ["Panadol 500mg"]


def test_standalone_condition_label_is_not_reported_as_a_disease():
    result = extract_prescription_conditions([{"text": "Bệnh kèm theo"}])

    assert result["underlying_conditions"] == []


def test_multiline_diagnosis_collects_all_don26_conditions():
    """The real don26 OCR boxes used to keep only the middle E14/E78 line."""

    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.9,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    items = [
        item("Phòng khám Nội số 2 (Nội TH)", 263, 248, 557, 281),
        item(
            "120 - Cơn đau thất ngực (BC) J20 - Viêm phế quản cấp/"
            "K76 - Bệnh gan khác/E14 - Các",
            267, 276, 1071, 314,
        ),
        item("Chắn đoán", 116, 302, 243, 339),
        item(
            "thể loại đái tháo đường không xác định/ E78 - "
            "Rối loạn chuyển hoá lipoprotein và tình trạng",
            263, 304, 1091, 338,
        ),
        item(
            "tăng lipid máu khác/110 - Bệnh Tang huyết áp vơ cần (nguyên phát)",
            264, 331, 886, 362,
        ),
        item("Thuốc BHYT cấp phát", 120, 396, 364, 431),
        item("1. Trimetazidin 20 mg", 158, 435, 591, 466),
    ]

    result = extract_prescription_conditions(items)

    assert result["underlying_conditions"] == [
        "I20 - Cơn đau thất ngực (BC)",
        "J20 - Viêm phế quản cấp",
        "K76 - Bệnh gan khác",
        "E14 - Các thể loại đái tháo đường không xác định",
        "E78 - Rối loạn chuyển hoá lipoprotein và tình trạng tăng lipid máu khác",
        "I10 - Bệnh Tang huyết áp vơ cần (nguyên phát)",
    ]
    assert result["icd_codes"] == ["I20", "J20", "K76", "E14", "E78", "I10"]
    assert "Phòng khám" not in result["diagnosis"]
    assert "Trimetazidin" not in result["diagnosis"]


def test_don1_pairs_parallel_icd_codes_and_stops_before_medication_table():
    """Do not repeat the summary or swallow ``II.THÔNG TIN ĐƠN THUỐC``."""

    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.9,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    items = [
        # Adjacent OCR boxes overlap vertically by three pixels in the real
        # response; the next label must still stop the diagnosis block.
        item("Chấn đoán: ZS", 117, 493, 280, 515),
        item(
            "Bệnh kèm theo: , E13;115: , Bệnh đái tháo đường sau ghép, "
            "Tăng huyết áp thứ phát",
            117,
            512,
            920,
            529,
        ),
        item("II.THÔNG TIN ĐƠN THUỐC", 116, 531, 430, 550),
        item("Stt", 116, 553, 150, 570),
        item("Tên thuốc", 180, 554, 290, 571),
        item("1", 116, 642, 130, 660),
        item("Methyl prednisolon(Medrol 4mg)", 150, 642, 500, 660),
    ]

    result = extract_prescription_conditions(items)

    assert result["diagnosis"] == ""
    assert result["underlying_conditions"] == [
        "E13 - Bệnh đái tháo đường sau ghép",
        "I15 - Tăng huyết áp thứ phát",
    ]
    assert result["icd_codes"] == ["E13", "I15"]
    assert all("THÔNG TIN ĐƠN THUỐC" not in text for text in result["underlying_conditions"])


def test_don2_blank_diagnosis_does_not_swallow_vitals_or_medication_table():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.9,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    items = [
        item("Nhịp thờ: 20,0 lần/ph;", 346, 637, 480, 657),
        item("Chẩn đoán: -", 43, 658, 130, 675),
        item("ILTHÔNG TIN ĐƠN THUỐC", 43, 678, 242, 695),
        item(
            "Sitagliptin (dưới dạng Sitagliptin phosphate monohydrate); Metformin",
            66,
            701,
            521,
            722,
        ),
        item("1.", 49, 712, 68, 730),
        item("Hydrochloride(Janumet 50mg/1000mg)", 64, 717, 334, 740),
    ]

    conditions = extract_prescription_conditions(items)
    rows = extract_medication_rows(items)

    assert conditions == {"diagnosis": "", "underlying_conditions": [], "icd_codes": []}
    assert rows[0]["name_texts"] == [
        "Sitagliptin (dưới dạng Sitagliptin phosphate monohydrate); Metformin",
        "Hydrochloride(Janumet 50mg/1000mg)",
    ]


def test_don3_ignores_overlapping_vital_but_keeps_hypertension_disease():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.9,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    items = [
        item("Nhịp thờ: 20,0 lần/ph;", 323, 706, 460, 726),
        item("Chấn đoán: sau zhép", 62, 723, 226, 747),
        item("nz", 640, 730, 657, 743),
        item(
            "huyết áp vô căn (uguyên phát);Bệnh đái tháo đường không phụ 1.mộc insuline",
            64,
            743,
            562,
            760,
        ),
        item("Kết quả CLS:", 64, 760, 157, 777),
        item("ILTHÔNG TIN ĐƠN THUỐC", 63, 777, 263, 798),
    ]

    result = extract_prescription_conditions(items)

    assert result["diagnosis"] == (
        "sau zhép huyết áp vô căn (uguyên phát);"
        "Bệnh đái tháo đường không phụ 1.mộc insuline"
    )
    assert result["underlying_conditions"] == [
        "sau zhép huyết áp vô căn (uguyên phát)",
        "Bệnh đái tháo đường không phụ 1.mộc insuline",
    ]
    assert all("Nhịp thờ" not in text for text in result["underlying_conditions"])


def test_drug_ingredient_line_is_not_fuzzy_footer():
    from app.services.prescription_resolver import is_table_footer

    assert not is_table_footer(
        "Sitagliptin (dưới dạng Sitagliptin phosphate monohydrate); Metformin"
    )
    assert is_table_footer("Lời dặn của bác sĩ: uống thuốc theo đơn")
    assert is_table_footer("chi chú:")


@pytest.mark.parametrize(
    "text",
    [
        "NGƯỜI M",
        "dùng, khám lại sau 3 tuần Hà Nội",
        "Tiếp tục nhỏ mũi, rửa mũi tại nhà",
        "Hà Nội, Ngày",
        "Ghiche",
        "Ghicholi",
    ],
)
def test_new_real_prescription_footers_are_not_medication_rows(text):
    from app.services.prescription_resolver import is_table_footer

    assert is_table_footer(text)


def test_cropped_schedule_fragments_are_not_drug_names():
    from app.services.prescription_resolver import _is_schedule_text

    assert _is_schedule_text("áng 1.00")
    assert _is_schedule_text("ng: 1.00")
    assert _is_schedule_text("2 Trưa:")


def test_don7_condition_block_excludes_vitals_background_and_drug_heading():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.9,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    items = [
        item("Mạch làmp", 177, 348, 338, 392),
        item(
            "N40 Tang sân tuyến tiến heviN40, Nhiễm trùng hó hấp trên",
            168, 360, 761, 426,
        ),
        item("Chân đoán", 25, 397, 155, 436),
        item(
            "vị trì không xÁc đình J06) HỘI CHỨNG THẬN HƯ",
            170, 392, 666, 453,
        ),
        item("19,Phường", 700, 415, 820, 450),
        item("Thuốc", 23, 443, 116, 491),
        item("1. Spetcefy 200mg", 30, 480, 260, 520),
    ]

    result = extract_prescription_conditions(items)

    assert result["underlying_conditions"] == [
        "Tang sân tuyến tiến hevi N40",
        "Nhiễm trùng hó hấp trên vị trì không xÁc đình J06",
        "HỘI CHỨNG THẬN HƯ",
    ]
    assert result["icd_codes"] == ["N40", "J06"]
    assert "Mạch" not in result["diagnosis"]
    assert "Phường" not in result["diagnosis"]
    assert "Thuốc" not in result["diagnosis"]


def test_suffix_icd_codes_split_conditions_without_separators():
    result = extract_prescription_conditions([
        {
            "text": (
                "Chẩn đoán: thoái hóa khớp M19 suy van tĩnh mạch I83 "
                "Rối loạn Lipid Máu E78 tăng men gan K76 gout M10 suy thận mạn N19"
            )
        }
    ])

    assert result["underlying_conditions"] == [
        "thoái hóa khớp M19",
        "suy van tĩnh mạch I83",
        "Rối loạn Lipid Máu E78",
        "tăng men gan K76",
        "gout M10",
        "suy thận mạn N19",
    ]
    assert result["icd_codes"] == ["M19", "I83", "E78", "K76", "M10", "N19"]


def test_condition_split_keeps_spinal_level_l4_l5_together():
    result = extract_prescription_conditions([
        {"text": "Chẩn đoán: thoát vị đĩa đệm cột sống L4/L5 chèn ép rễ"}
    ])

    assert result["underlying_conditions"] == [
        "thoát vị đĩa đệm cột sống L4/L5 chèn ép rễ"
    ]
    assert result["icd_codes"] == []


def test_condition_split_does_not_turn_blood_pressure_into_i20():
    result = extract_prescription_conditions([
        {"text": "Chẩn đoán: theo dõi huyết áp 120/80 mmHg"}
    ])

    assert result["underlying_conditions"] == ["theo dõi huyết áp 120/80 mmHg"]
    assert result["icd_codes"] == []


def test_comma_splits_two_explicit_diseases_but_keeps_a_complication_suffix():
    split = extract_prescription_conditions([
        {
            "text": (
                "Chẩn đoán: E11: Bệnh tăng huyết áp vô căn (nguyên phát), "
                "Bệnh đái tháo đường không phụ thuộc"
            )
        }
    ])
    preserved = extract_prescription_conditions([
        {
            "text": (
                "Chẩn đoán: Bệnh đái tháo đường không phụ thuộc insulin, "
                "biến chứng mắt"
            )
        }
    ])

    assert split["underlying_conditions"] == [
        "E11: Bệnh tăng huyết áp vô căn (nguyên phát)",
        "Bệnh đái tháo đường không phụ thuộc",
    ]
    assert preserved["underlying_conditions"] == [
        "Bệnh đái tháo đường không phụ thuộc insulin, biến chứng mắt"
    ]


def test_wrapped_diagnosis_and_secondary_diagnosis_are_both_preserved():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.9,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    result = extract_prescription_conditions([
        item("Chẩn đoán - CAO HUYẾT ÁP VÔ CĂN (I10)/ BỆNH TIM", 30, 50, 760, 80),
        item("THIẾU MÁU CỤC BỘ", 35, 84, 330, 114),
        item("Chẩn đoán kèm theo: Bất thường của nhịp tim", 30, 120, 590, 150),
        item("Tên thuốc - Hàm lượng", 180, 180, 430, 210),
    ])

    assert result["underlying_conditions"] == [
        "CAO HUYẾT ÁP VÔ CĂN (I10)",
        "BỆNH TIM THIẾU MÁU CỤC BỘ",
        "Bất thường của nhịp tim",
    ]


def test_cropped_icd_diagnosis_before_table_is_recovered_without_label():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.9,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    result = extract_prescription_conditions([
        item("vỡn đom 110 - Bệnh lý tăng huyết áp/Sa sút trí tuệ/Nhồi máu não", 0, 0, 800, 35),
        item("Tên thuốc - Hàm lượng", 200, 90, 450, 120),
        item("Telmisartan 40mg", 20, 150, 260, 180),
    ])

    assert result["diagnosis"] == "I10 - Bệnh lý tăng huyết áp/Sa sút trí tuệ/Nhồi máu não"
    assert result["underlying_conditions"] == [
        "I10 - Bệnh lý tăng huyết áp",
        "Sa sút trí tuệ",
        "Nhồi máu não",
    ]


def test_same_diagnosis_with_i10_and_ocr_110_is_returned_once():
    result = extract_prescription_conditions([
        {"text": "Chẩn đoán: I10 - Cao huyết áp vô căn (nguyên phát)"},
        {"text": "Bệnh kèm theo: Bất thường của nhịp tim"},
        {"text": "Bệnh kèm theo: 110 - Cao huyết áp vô căn (nguyên phát)"},
    ])

    assert result["underlying_conditions"] == [
        "I10 - Cao huyết áp vô căn (nguyên phát)",
        "Bất thường của nhịp tim",
    ]
    assert result["icd_codes"] == ["I10"]


def test_standalone_diagnosis_label_uses_disease_below_not_patient_above():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.9,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    result = extract_prescription_conditions([
        item("Tên bệnh nhân", 20, 20, 145, 40),
        item("Nguyễn Văn An", 165, 20, 310, 40),
        item("Chẩn đoán:", 20, 60, 140, 80),
        item("VIÊM DẠ DÀY (K29)", 20, 82, 260, 104),
        item("Tên thuốc - Hàm lượng", 20, 130, 280, 150),
    ])

    assert result["underlying_conditions"] == ["VIÊM DẠ DÀY (K29)"]


def test_administrative_bhyt_suffix_is_not_a_second_condition():
    result = extract_prescription_conditions([{
        "text": "Chẩn đoán: VIÊM DẠ DÀY / HP(+) BHYT",
    }])

    assert result["underlying_conditions"] == ["VIÊM DẠ DÀY", "HP(+)"]


def test_fuzzy_diagnosis_label_keeps_the_printed_condition_suffix():
    result = extract_prescription_conditions([{
        "text": "Chín đoàn Rồi loạn tiêu hóa",
    }])

    assert result["underlying_conditions"] == ["Rồi loạn tiêu hóa"]


def test_same_diagnosis_with_i10_and_ocr_110_is_returned_once():
    result = extract_prescription_conditions([
        {"text": "Chẩn đoán: I10 - Cao huyết áp vô căn (nguyên phát)"},
        {"text": "Bệnh kèm theo: Bất thường của nhịp tim"},
        {"text": "Bệnh kèm theo: 110 - Cao huyết áp vô căn (nguyên phát)"},
    ])

    assert result["underlying_conditions"] == [
        "I10 - Cao huyết áp vô căn (nguyên phát)",
        "Bất thường của nhịp tim",
    ]
    assert result["icd_codes"] == ["I10"]


def test_colon_comma_and_trailing_icd_note_split_only_real_conditions():
    result = extract_prescription_conditions([{
        "text": (
            "Chẩn đoán: Cao huyết áp vô căn (nguyên phát): "
            "Bệnh đái tháo đường không phụ thuộc insulin, biến chứng mắt; "
            "Rối loạn chuyển hóa lipoprotein và tình trạng tăng lipid máu khác, "
            "Suy thận mạn; E11: E78; N18:) Jighi chú"
        )
    }])

    assert result["underlying_conditions"] == [
        "Cao huyết áp vô căn (nguyên phát)",
        "Bệnh đái tháo đường không phụ thuộc insulin, biến chứng mắt",
        "Rối loạn chuyển hóa lipoprotein và tình trạng tăng lipid máu khác",
        "Suy thận mạn",
    ]
    assert "Jighi chú" not in result["diagnosis"]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            "Chẩn đoán: Tổn thương nông ở đầu Hạn sử dụng: Chỉ định dùng thuốc x3 ngày",
            ["Tổn thương nông ở đầu"],
        ),
        ("Chẩn đoán chính Số lượng Viên", []),
        ("Chần đoán. Viêm hạch sau tai 2 bên Bệnh kóm theo", ["Viêm hạch sau tai 2 bên"]),
        (
            "Bệnh chính, Viêm tai giữa cấp ứ dịch Phải/Viêm mũi họng - V.A đợt cấp.",
            ["Viêm tai giữa cấp ứ dịch Phải", "Viêm mũi họng", "V.A đợt cấp"],
        ),
    ],
)
def test_condition_labels_are_cleaned_and_stop_before_table_text(line, expected):
    result = extract_prescription_conditions([{"text": line}])

    assert result["underlying_conditions"] == expected


def test_missing_middle_row_number_is_recovered_from_name_and_unit_geometry():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.9,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    items = [
        item("Tên thuốc", 180, 440, 390, 470),
        item("Đơn vị", 500, 440, 590, 470),
        item("2", 70, 552, 93, 583),
        item("Mekocetin 0.5mg", 106, 545, 282, 581),
        item("(Dexamethasone 0.5mg)", 104, 563, 337, 611),
        item("Chai", 486, 576, 575, 619),
        item("Atussin SR 60ml (hết hàng)", 106, 591, 375, 637),
        item("(Dextromethorphan, chlorpheniramin)", 108, 613, 450, 667),
        item("1", 73, 667, 95, 690),
        item("Acemuc 100mg", 109, 656, 267, 692),
        item("Tiếp tục nhỏ mũi, rửa mũi tại nhà", 264, 716, 593, 782),
    ]

    rows = extract_medication_rows(items)

    assert [row["name_texts"][0] for row in rows] == [
        "Mekocetin 0.5mg",
        "Atussin SR 60ml (hết hàng)",
        "Acemuc 100mg",
    ]
    assert [row["row_number"] for row in rows] == [1, 2, 3]


def test_pharmacy_receipt_extracts_product_lines_not_quantity_price_or_unit_cells():
    def item(text, x1, y1, x2, y2):
        return {
            "text": text,
            "confidence": 0.95,
            "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        }

    items = [
        item("S.L", 476, 637, 517, 661),
        item("DVT", 536, 635, 590, 661),
        item("Đ.Giá", 692, 634, 756, 660),
        item("T.Tiền", 853, 632, 927, 659),
        item("MOVINAVIR 200", 441, 696, 601, 722),
        item("40", 485, 732, 517, 756),
        item("Viên", 535, 731, 589, 757),
        item("12,500", 687, 731, 757, 757),
        item("500,000", 842, 728, 928, 756),
        item("ENERVON", 442, 767, 542, 791),
        item("20", 484, 801, 540, 827),
        item("Viên", 535, 801, 589, 826),
        item("AT ZINC 10MG", 441, 838, 585, 862),
        item("20", 485, 874, 516, 898),
        item("Viên", 538, 874, 588, 897),
        item("MASAK DAVI", 440, 908, 568, 935),
        item("20", 480, 942, 591, 973),
        item("ORESOL PLUZ", 438, 981, 584, 1008),
        item("1", 491, 1019, 545, 1045),
        item("Tube", 532, 1017, 591, 1045),
        item("NAGAPOLIS", 435, 1056, 559, 1083),
        item("1", 493, 1096, 511, 1116),
        item("Chai", 539, 1095, 588, 1118),
        item("EFFE 500", 436, 1128, 532, 1155),
        item("4", 492, 1167, 510, 1187),
        item("Viên", 538, 1164, 588, 1190),
        item("Tổng tiền:", 430, 1295, 551, 1331),
        item("774,000", 832, 1284, 927, 1317),
    ]

    rows = extract_medication_rows(items)

    assert [row["name_texts"][0] for row in rows] == [
        "MOVINAVIR 200",
        "ENERVON",
        "AT ZINC 10MG",
        "MASAK DAVI",
        "ORESOL PLUZ",
        "NAGAPOLIS",
        "EFFE 500",
    ]


def test_second_prescriber_group_restarting_at_one_is_a_new_medication_row():
    def item(text, x, y, width=180):
        return {
            "text": text,
            "confidence": 0.99,
            "bbox": [[x, y], [x + width, y], [x + width, y + 18], [x, y + 18]],
        }

    items = [
        item("II.THÔNG TIN ĐƠN THUỐC", 20, 100, 260),
        item("Tên thuốc", 60, 125, 90),
        item("6", 20, 300, 12),
        item("Metoprolol(Carmotop 25 mg)", 60, 300, 240),
        # More than 100 px below the section header, so this is the footer
        # boundary used by the real don1 layout.
        item("Bác sĩ kê đơn: LƯU THỊ THẢO", 20, 340, 240),
        item("Lời dặn của bác sĩ: dùng thuốc theo đơn", 20, 360, 330),
        # A second prescribing group restarts its own STT sequence at 1.
        item("1", 20, 390, 12),
        item("Sitagliptin, Metformin (Janumet 50mg/1000mg)", 60, 390, 350),
        item("Tổng 7 khoản", 20, 430, 120),
    ]

    rows = extract_medication_rows(items)

    assert [row["row_number"] for row in rows] == [1, 2]
    assert "Carmotop" in " ".join(rows[0]["name_texts"])
    assert "Janumet" in " ".join(rows[1]["name_texts"])


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


def test_two_strength_rows_separated_by_schedule_are_not_merged():
    def item(text, x, y, width=260):
        return {
            "text": text,
            "confidence": 0.99,
            "bbox": [[x, y], [x + width, y], [x + width, y + 20], [x, y + 20]],
        }

    rows = extract_medication_rows([
        item("TOA THUỐC", 20, 40),
        item("1. TINIDAZOL 500mg", 20, 100),
        item("Ngày uống 2 lần", 80, 150),
        item("TETRACYCLIN SOOMG", 80, 205),
        item("Ngày uống 4 lần", 80, 240),
        item("3. BISMUTH 300mg", 20, 320),
    ])

    assert [" ".join(row["name_texts"]) for row in rows] == [
        "TINIDAZOL 500mg",
        "TETRACYCLIN SOOMG",
        "BISMUTH 300mg",
    ]


def test_damaged_unnumbered_alias_row_between_numbered_rows_is_recovered():
    def item(text, x, y, width=320):
        return {
            "text": text,
            "confidence": 0.99,
            "bbox": [[x, y], [x + width, y], [x + width, y + 20], [x, y + 20]],
        }

    rows = extract_medication_rows([
        item("Chỉ định dùng thuốc", 20, 40),
        item("1 BUSCOPAN 20mg (Hyoscine)", 20, 80),
        item("2 RIFLOX 500mg (Levofloxacin)", 20, 140),
        item("Sáng: 1.00", 80, 180),
        item("- NO-SPA Uống Viên (Drotaverin)", 20, 240),
        item("Tối: 1.00", 80, 280),
        item("4 BISCAN-G Uống Viên (Bacillus)", 20, 340),
    ])

    assert len(rows) == 4
    assert "NO-SPA" in " ".join(rows[2]["name_texts"])


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


@pytest.mark.parametrize("text", ["NAGAPOLIS", "Ngọc linh", "Angioten 10mg"])
def test_drug_names_are_not_schedule_text_just_because_of_their_prefix(text):
    from app.services.prescription_resolver import _is_schedule_text

    assert _is_schedule_text(text) is False


def test_row_number_is_stripped_from_the_drug_name():
    """A name reaching the resolver as "4, PAPAZE" cannot match the database."""
    from app.services.prescription_resolver import _clean_medication_name

    assert _clean_medication_name("4, PAPAZE (magnesi").startswith("PAPAZE")
    assert _clean_medication_name("(2. SUCRATE GEL").startswith("SUCRATE GEL")


def test_inline_row_number_is_not_sent_to_the_resolver():
    def item(text, x, y, width=300):
        return {
            "text": text,
            "confidence": 0.99,
            "bbox": [[x, y], [x + width, y], [x + width, y + 20], [x, y + 20]],
        }

    rows = extract_medication_rows([
        item("TOA THUỐC", 20, 80),
        item("1. Spetcely 200mg (Cetpodoxime)", 20, 150),
    ])

    assert rows[0]["resolver_texts"] == ["Spetcely 200mg (Cetpodoxime)"]


def test_inline_number_stays_when_no_ingredient_can_verify_the_brand():
    def item(text, x, y, width=250):
        return {
            "text": text,
            "confidence": 0.99,
            "bbox": [[x, y], [x + width, y], [x + width, y + 20], [x, y + 20]],
        }

    rows = extract_medication_rows([
        item("TOA THUỐC", 20, 80),
        item("1. Spetcely 200mg (Cetpodoxime)", 20, 120),
        item("2. Amlozaar 50/5 mg", 20, 150),
    ])

    assert rows[1]["resolver_texts"] == ["2. Amlozaar 50/5 mg"]


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


# --------------------------------------------------------------------------
# One photo, several products
# --------------------------------------------------------------------------


def _box(text, x, y, w, h, confidence=0.95):
    return {
        "text": text,
        "confidence": confidence,
        "bbox": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
    }


def _resolve(items):
    from app import main

    main.drug_resolver.load()
    return main._resolve_document(items)


def test_three_blisters_in_one_photo_become_three_medications():
    """The single-product path joined every prominent region into one string.

    A table of blisters then returned one medicine and silently dropped the
    rest -- the worst failure for an interaction checker, because nothing on
    screen says anything is missing.
    """
    items = [
        _box("Medrol 16", 60, 60, 200, 40),
        _box("Methylprednisolone 16 mg", 60, 110, 240, 22),
        _box("Omeprazol 20", 900, 60, 200, 40),
        _box("Omeprazole 20 mg", 900, 110, 210, 22),
        _box("Augmentin 625", 60, 900, 220, 40),
        _box("Amoxicillin 500 mg", 60, 950, 220, 22),
    ]

    document_type, _resolution, medications = _resolve(items)

    assert document_type == "medicine_package"
    assert len(medications) == 3
    assert [m["row_number"] for m in medications] == [1, 2, 3]
    # Each blister is reported separately. Which catalogue row wins for a given
    # blister is the resolver's business -- what this pins is that all three
    # objects survive instead of being merged into one answer.
    reported = " ".join(m["ocr_drug_name"] for m in medications)
    assert "Medrol" in reported
    assert "Omeprazol" in reported
    assert "Augmentin" in reported
    assert all(m["requires_confirmation"] is True for m in medications)


def test_one_product_printed_twice_is_not_reported_twice():
    """A leaflet prints its brand in the header and its ingredient on the pack
    shot. Those are far enough apart to cluster separately and resolve to
    different catalogue rows, but they share an active ingredient."""
    items = [
        _box("Zinnat 500", 300, 200, 500, 110),
        _box("Cefuroxime 500 mg", 320, 500, 380, 40),
        _box("Zinnat 500", 340, 1100, 160, 30),
        _box("Cefuroxime 500 mg", 340, 1150, 150, 20),
    ]

    _document_type, _resolution, medications = _resolve(items)

    assert len(medications) == 1


def test_a_weak_match_without_a_strength_is_not_a_product():
    """A manufacturer logo also finds a catalogue neighbour. Measured on real
    packaging the only false cluster scored 0.680 while every genuine product
    scored 0.807 or better, so the suggestion threshold separates them."""
    items = [
        _box("Medrol 16", 60, 60, 200, 40),
        _box("Methylprednisolone 16 mg", 60, 110, 240, 22),
        _box("Omeprazol 20", 900, 60, 200, 40),
        _box("Omeprazole 20 mg", 900, 110, 210, 22),
        # A logo far from either blister, with no strength of its own.
        _box("Amlor", 500, 1400, 90, 24),
    ]

    _document_type, _resolution, medications = _resolve(items)

    joined = " ".join(m["ocr_drug_name"] for m in medications)
    assert "Amlor" not in joined


def test_package_name_ranks_by_glyph_height_not_rectangle_area():
    """Area rewards a long line of small print: on a real leaflet a 50-character
    citation outweighed the brand set in display type."""
    items = [
        _box("ACTIXIM", 300, 300, 200, 120),          # tall, narrow
        _box("Cong bo tieu chuan chat luong", 40, 800, 700, 18),  # wide, tiny
    ]

    selected = [item["text"] for item in extract_package_name(items)]

    assert selected[0] == "ACTIXIM"


def test_package_name_does_not_promote_a_thin_diagonal_watermark():
    """A rotated watermark has a huge axis-aligned y-span but short glyphs.

    Name ranking must use the oriented OCR quadrilateral, otherwise background
    copy outranks the horizontal brand and strength printed on the box.
    """
    items = [
        {
            "text": "BACKGROUND-MARK",
            "confidence": 0.99,
            "bbox": [[20, 30], [500, 300], [490, 318], [10, 48]],
        },
        _box("PRODUCT BRAND", 200, 100, 300, 60),
        _box("Product 160 mg", 205, 175, 220, 30),
        _box("Product 80 mg", 205, 360, 210, 28),
    ]

    selected = [item["text"] for item in extract_package_name(items)]

    assert "BACKGROUND-MARK" not in selected
    assert "PRODUCT BRAND" in selected


def test_package_name_prefers_strength_evidence_over_large_background_copy():
    items = [
        _box("BACKGROUND COMPANY", 20, 20, 300, 100),
        _box("BACKGROUND COMPANY", 700, 350, 300, 105),
        _box("MEDICINE LABEL", 200, 150, 320, 70),
        _box("Medicine 160 mg", 210, 220, 220, 28),
    ]

    selected = [item["text"] for item in extract_package_name(items)]

    assert "Medicine 160 mg" in selected
    assert "MEDICINE LABEL" in selected


def test_ingredient_line_is_not_discarded_as_packaging_copy():
    """``paracetamol``/``caffeine`` used to sit in the packaging stopword list,
    so the very line that identifies a Glotadol blister was thrown away."""
    items = [
        _box("Glotadol 500", 60, 60, 200, 40),
        _box("500mg Paracetamol", 60, 110, 220, 26),
    ]

    kept = {item["text"] for item in extract_package_name(items)}

    assert "500mg Paracetamol" in kept


def test_signatory_name_is_not_a_dosage_line():
    """``tra`` was a bare three-letter prefix for ``Trưa``; it matched the
    signatory ``TRANG CẨM TÚ`` printed under a leaflet."""
    assert _is_schedule_text("TRANG CẨM TÚ") is False
    assert _is_schedule_text("Trua: 1.00") is True


def test_clustering_keeps_a_single_object_together():
    items = [
        _box("Medrol 16", 60, 60, 200, 40),
        _box("Methylprednisolone 16 mg", 60, 110, 240, 22),
        _box("16 mg", 60, 145, 80, 20),
    ]

    products = extract_package_products(items)

    assert len(products) == 1
    assert products[0]["has_strength"] is True


# --------------------------------------------------------------------------
# Refusing a page instead of guessing
# --------------------------------------------------------------------------


def test_empty_page_reports_no_text():
    from app import main

    assert main._unreadable_reason([]) == "no_text_detected"


def test_restaurant_receipt_reports_a_non_medical_reason():
    from app import main

    items = [
        {"text": "NHÀ HÀNG TOÀN NGỌC"},
        {"text": "HÓA ĐƠN THANH TOÁN"},
        {"text": "Thu ngân: Phạm Văn Toàn"},
        {"text": "Tổng thanh toán 1.740.000đ"},
    ]

    assert main._unreadable_reason(items) == "not_a_medical_document"


def test_disagreeing_recognizers_mark_the_page_illegible():
    """Both recognizers read the page and produced different text.

    Handwriting and photos too degraded to read both land here: the models are
    independent, so on print they converge and on noise they do not.
    """
    from app import main

    items = [
        {
            "text": f"line {index}",
            "confidence": 0.9,
            "paddle_text": f"Chan doan {index}",
            "vietocr_text": f"qwrtyup {index}",
        }
        for index in range(12)
    ]

    assert main._unreadable_reason(items) == "illegible_or_handwritten"


def test_agreeing_recognizers_leave_the_page_readable():
    from app.services.ocr_service import recognition_agreement

    items = [
        {"paddle_text": "Thuoc dieu tri", "vietocr_text": "Thuốc điều trị"}
        for _ in range(12)
    ]

    assert recognition_agreement(items) == 1.0


def test_too_few_regions_do_not_decide_legibility():
    """A three-word crop must not be judged on the median of three ratios."""
    from app.services.ocr_service import recognition_agreement

    items = [{"paddle_text": "abc", "vietocr_text": "xyz"} for _ in range(3)]

    assert recognition_agreement(items) is None


def test_quantity_cells_are_not_medicines():
    """``04 Lọ`` and ``60 Viên`` are the SL/Đơn vị columns.

    A number bound to a dosage form is a count, never a drug. On a real
    two-medicine prescription those two cells were proposed as medications #2
    and #4, and the name column of a third row held only the word ``Viên``.
    """
    items = [
        _box("STT", 205, 116, 42, 24),
        _box("Tên thuốc - Hàm lượng", 388, 116, 300, 26),
        _box("SL", 835, 116, 32, 24),
        _box("Đơn vị", 932, 116, 70, 24),
        _box("INSUNOVA - N (NPH) - 1000UI/10ml", 262, 148, 380, 26),
        _box("1", 220, 176, 14, 24),
        _box("04", 836, 172, 30, 24),
        _box("Lọ", 948, 172, 30, 24),
        _box("SaViDopril Plus - Perindopril", 262, 236, 400, 26),
        _box("2", 220, 264, 14, 24),
        _box("60", 836, 260, 30, 24),
        _box("Viên", 940, 260, 46, 24),
    ]

    rows = extract_medication_rows(items)

    reported = [" ".join(row["name_texts"]) for row in rows]
    assert not any(text.strip() in {"Lọ", "Viên", "04 Lọ", "60 Viên"} for text in reported)
    # Numbering the user sees stays contiguous after the artefacts are dropped.
    assert [row["row_number"] for row in rows] == list(range(1, len(rows) + 1))


def test_name_printed_above_a_centred_stt_digit_is_kept():
    """A tall table cell centres its STT digit over three printed lines.

    The digit then sits BELOW the medicine name, not beside it. Two rules used
    to fail together here: the digit was rejected as a row marker (a page
    margin and a second sheet visible at the photo's edge both distort the
    fraction-of-page tests), and the row window started 12px above the digit,
    which is under the name. The result was the brand name dropped entirely and
    the ingredient line below the digit reported as the medicine.
    """
    items = [
        _box("STT", 205, 116, 42, 24),
        _box("Tên thuốc - Hàm lượng", 388, 116, 300, 26),
        _box("INSUNOVA - N (NPH) - 1000UI/10ml", 262, 148, 380, 26),
        _box("1", 220, 176, 14, 24),
        _box("Insulin người tác dụng trung bình, trung gian", 262, 176, 350, 24),
        _box("04", 836, 172, 30, 24),
        _box("Lọ", 948, 172, 30, 24),
        _box("Tiêm dưới da - sáng 28 đv chiều 26 đv", 262, 202, 310, 24),
        _box("SaViDopril Plus - Perindopril erbumin + Indapamid", 262, 236, 530, 26),
        _box("2", 220, 264, 14, 24),
        _box("Perindopril erbumin + Indapamid", 262, 264, 300, 24),
        _box("60", 836, 260, 30, 24),
        _box("Viên", 940, 260, 46, 24),
        _box("Uống - Ngày 1 viên - sáng", 262, 290, 240, 24),
        # A second sheet at the edge of the photo, which inflates page_right
        # and carries a row number of its own.
        _box("Chẩn", 1255, 8, 60, 22),
        _box("STT", 1258, 100, 42, 22),
        _box("1", 1290, 145, 12, 20),
    ]

    rows = extract_medication_rows(items)

    assert len(rows) == 2
    joined = [" ".join(row["name_texts"]) for row in rows]
    assert joined[0].startswith("INSUNOVA")
    assert "SaViDopril Plus" in joined[1]
