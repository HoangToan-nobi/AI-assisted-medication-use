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

# Guard against decompression-bomb style uploads before we allocate pixels.
Image.MAX_IMAGE_PIXELS = 80_000_000


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


def prepare_image(
    data: bytes,
    max_dimension: int,
    allowed_formats: frozenset[str],
    min_dimension: int = 0,
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
            # EXIF rotation must be applied before anything reads pixel order.
            oriented = ImageOps.exif_transpose(source)
            rgb_image = oriented.convert("RGB")
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageError("Uploaded file is not a valid image.") from exc

    original_width, original_height = rgb_image.size
    longest = max(original_width, original_height)
    target_scale = 1.0
    if longest > max_dimension:
        target_scale = max_dimension / longest
    elif min_dimension and longest >= 400 and longest < min_dimension:
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
