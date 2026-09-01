"""Image validation and OCR-oriented preprocessing.

Preprocessing stays deliberately gentle: hard binarization or aggressive
denoising tends to erase the small print (strengths, ingredient lists). We fix
orientation, resize small photos for recognition, apply local contrast, and
use a light unsharp mask.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

# Pillow only warns at MAX_IMAGE_PIXELS and rejects at twice that value. Keep its
# global guard, then enforce the exact configured limit ourselves before convert()
# allocates the full RGB image.
Image.MAX_IMAGE_PIXELS = 40_000_000


class InvalidImageError(ValueError):
    """Raised when the upload is not a decodable image in an allowed format."""


@dataclass(frozen=True)
class PreparedImage:
    """A BGR ndarray ready for PaddleOCR, plus quality metadata."""

    array: np.ndarray  # BGR, what PaddleOCR expects
    blur_score: float
    width: int
    height: int
    original_width: int
    original_height: int
    image_format: str


def _laplacian_variance(bgr: np.ndarray) -> float:
    """Blur score. Higher is sharper; roughly <100 reads as blurry in practice."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _contrast(bgr: np.ndarray) -> float:
    """Return grayscale contrast used to choose a gentle OCR preprocessing path."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(gray.std())


def _order_document_quad(points: np.ndarray) -> np.ndarray:
    """Return a convex document quadrilateral as TL, TR, BR, BL.

    Sum/difference ordering duplicates a corner on strongly rotated perspective
    photos. Sorting around the centroid is stable for every convex quad; the
    lower-y neighbour of the top-left corner identifies the printed top edge.
    """
    points = np.asarray(points, dtype=np.float32).reshape(4, 2)
    centre = points.mean(axis=0)
    cycle = points[
        np.argsort(np.arctan2(points[:, 1] - centre[1], points[:, 0] - centre[0]))
    ]
    start = int(np.argmin(cycle.sum(axis=1)))
    cycle = np.roll(cycle, -start, axis=0)
    if cycle[1, 1] > cycle[-1, 1]:
        cycle = cycle[[0, 3, 2, 1]]
    return cycle


def rectify_document(bgr: np.ndarray) -> np.ndarray | None:
    """Perspective-warp a confidently detected bright paper document.

    This is deliberately a guarded fallback, not unconditional preprocessing.
    It requires a large convex quadrilateral, good rectangularity and a paper
    interior measurably brighter than its surroundings. The caller compares the
    OCR structure before/after rectification and keeps the warp only when it
    extracts more credible medication rows.
    """
    if bgr.ndim != 3 or min(bgr.shape[:2]) < 240:
        return None

    height, width = bgr.shape[:2]
    page_area = float(height * width)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 120)
    kernel_size = max(5, round(min(height, width) * 0.007))
    if kernel_size % 2 == 0:
        kernel_size += 1
    edges = cv2.morphologyEx(
        edges,
        cv2.MORPH_CLOSE,
        np.ones((kernel_size, kernel_size), dtype=np.uint8),
        iterations=2,
    )

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[float, np.ndarray]] = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:30]:
        area = float(cv2.contourArea(contour))
        area_ratio = area / page_area
        if not 0.12 <= area_ratio <= 0.92:
            continue
        perimeter = cv2.arcLength(contour, True)
        quad = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(quad) != 4 or not cv2.isContourConvex(quad):
            continue

        points = quad.reshape(4, 2)
        rectangle = cv2.minAreaRect(points.astype(np.float32))
        rectangle_area = float(rectangle[1][0] * rectangle[1][1])
        rectangularity = area / rectangle_area if rectangle_area else 0.0
        if rectangularity < 0.72:
            continue

        ordered = _order_document_quad(points)
        side_lengths = [
            float(np.linalg.norm(ordered[index] - ordered[(index + 1) % 4]))
            for index in range(4)
        ]
        if min(side_lengths) < min(height, width) * 0.20:
            continue

        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.fillConvexPoly(mask, points.astype(np.int32), 255)
        inside = gray[mask > 0]
        outside = gray[mask == 0]
        if not len(inside) or not len(outside):
            continue
        brightness_gap = float(inside.mean() - outside.mean())
        if inside.mean() < 100.0 or brightness_gap < 12.0:
            continue
        candidates.append((area_ratio * rectangularity * brightness_gap, ordered))

    if not candidates:
        return None

    _score, source = max(candidates, key=lambda candidate: candidate[0])
    target_width = round(max(np.linalg.norm(source[0] - source[1]), np.linalg.norm(source[3] - source[2])))
    target_height = round(max(np.linalg.norm(source[0] - source[3]), np.linalg.norm(source[1] - source[2])))
    if target_width < 120 or target_height < 120:
        return None
    destination = np.float32(
        [[0, 0], [target_width - 1, 0], [target_width - 1, target_height - 1], [0, target_height - 1]]
    )
    return cv2.warpPerspective(
        bgr,
        cv2.getPerspectiveTransform(source, destination),
        (target_width, target_height),
        borderMode=cv2.BORDER_REPLICATE,
    )


def enhance_top_band(bgr: np.ndarray, ratio: float = 0.18) -> np.ndarray:
    """Strengthen faint text touching the top edge without binarizing the page.

    Cropped prescriptions can leave the diagnosis in a thin, regular-weight
    line at the very top while medicine names below are bold. A second local
    CLAHE pass makes that line detectable and leaves the rest of the page
    unchanged. The caller uses this only as a fallback when the normal pass
    found a prescription but no diagnosis.
    """
    enhanced = bgr.copy()
    band_height = max(1, min(enhanced.shape[0], round(enhanced.shape[0] * ratio)))
    band = enhanced[:band_height]
    lab = cv2.cvtColor(band, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    l_channel = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 4)).apply(l_channel)
    enhanced[:band_height] = cv2.cvtColor(
        cv2.merge((l_channel, a_channel, b_channel)), cv2.COLOR_LAB2BGR
    )
    return enhanced


# Ảnh nhỏ hơn mức này coi như icon/thumbnail, phóng to lên chỉ tốn thời gian.
# Ngưỡng cũ 400 loại nhầm cả ảnh đơn thuốc chụp nhỏ: eval/end2end/don40.jpg chỉ
# 349x336 nên không được phóng to, dẫn tới cột tên thuốc rộng vỏn vẹn 119px và
# chính dòng thuốc bị xem là "ngoài cột".
_MIN_UPSCALE_SOURCE = 300


def prepare_image(
    data: bytes,
    max_dimension: int,
    allowed_formats: frozenset[str],
    min_dimension: int = 0,
    max_input_pixels: int = 40_000_000,
) -> PreparedImage:
    """Decode, validate, orient and resize an uploaded image.

    The format is taken from the decoded bytes, never from the client-supplied
    filename or Content-Type.
    """
    if not data:
        raise InvalidImageError("Uploaded file is empty.")

    try:
        with Image.open(io.BytesIO(data)) as source:
            image_format = (source.format or "").upper()
            if image_format not in allowed_formats:
                raise InvalidImageError(
                    f"Unsupported image format: {image_format or 'unknown'}."
                )
            source_width, source_height = source.size
            if (
                source_width <= 0
                or source_height <= 0
                or source_width * source_height > max_input_pixels
            ):
                raise InvalidImageError(
                    f"Decoded image exceeds the {max_input_pixels:,}-pixel limit."
                )
            # EXIF rotation must be applied before anything reads pixel order.
            oriented = ImageOps.exif_transpose(source)
            rgb_image = oriented.convert("RGB")
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise InvalidImageError("Uploaded file is not a valid image.") from exc

    original_width, original_height = rgb_image.size
    longest = max(original_width, original_height)
    target_scale = 1.0
    if longest > max_dimension:
        target_scale = max_dimension / longest
    elif min_dimension and longest >= _MIN_UPSCALE_SOURCE and longest < min_dimension:
        # Phone screenshots and cropped prescriptions often contain very small
        # characters. Upscale those images before recognition, but do not
        # enlarge tiny test icons or thumbnails.
        target_scale = min_dimension / longest

    if target_scale != 1.0:
        rgb_image = rgb_image.resize(
            (
                max(1, round(original_width * target_scale)),
                max(1, round(original_height * target_scale)),
            ),
            Image.Resampling.LANCZOS,
        )

    bgr = cv2.cvtColor(np.asarray(rgb_image), cv2.COLOR_RGB2BGR)
    # Do not enhance every image: CLAHE/unsharp can damage Vietnamese
    # diacritics on already-clean scans.  Use the original pixels for clear
    # documents and enhance only low-contrast captures.  The mode remains
    # configurable for A/B testing: auto (default), always, or never.
    mode = os.getenv("OCR_PREPROCESSING", "auto").strip().lower()
    should_enhance = mode == "always" or (mode == "auto" and _contrast(bgr) < 42.0)
    if should_enhance and mode != "never":
        # CLAHE improves faint black/gray print on photographed prescriptions
        # without destroying colored medicine packaging.
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        l_channel = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(l_channel)
        enhanced = cv2.cvtColor(cv2.merge((l_channel, a_channel, b_channel)), cv2.COLOR_LAB2BGR)
        blurred = cv2.GaussianBlur(enhanced, (0, 0), 1.0)
        bgr = cv2.addWeighted(enhanced, 1.15, blurred, -0.15, 0)
    height, width = bgr.shape[:2]

    return PreparedImage(
        array=bgr,
        blur_score=round(_laplacian_variance(bgr), 2),
        width=width,
        height=height,
        original_width=original_width,
        original_height=original_height,
        image_format=image_format,
    )
