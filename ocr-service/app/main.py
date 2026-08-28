"""FastAPI application.

Startup loads the PaddleOCR model and the drug database exactly once; requests
reuse those singletons. OCR is CPU-bound, so it runs in the threadpool rather
than on the event loop.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any

import cv2
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.schemas import (
    DrugRecognitionResponse,
    ErrorResponse,
    HealthResponse,
    OCRResponse,
)
from app.services.drug_resolver import DrugResolver
from app.services.ocr_service import (
    OCRService,
    OCRUnavailableError,
    filter_ocr_results,
    recognition_agreement,
)
from app.services.prescription_resolver import (
    classify_document,
    extract_medication_rows,
    extract_package_name,
    extract_package_products,
    extract_prescription_conditions,
)
from app.utils.image_utils import (
    InvalidImageError,
    PreparedImage,
    enhance_top_band,
    prepare_image,
    rectify_document,
)
from app.utils.text_utils import extract_strengths, matching_key, normalize_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Module-level singletons: created here, loaded once in the lifespan below.
ocr_service = OCRService(
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
drug_resolver = DrugResolver()

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Invalid image"},
    413: {"model": ErrorResponse, "description": "File too large"},
    503: {"model": ErrorResponse, "description": "OCR model unavailable"},
}


class UploadTooLargeError(Exception):
    """Raised when an upload exceeds the configured size limit."""


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        drug_resolver.load()
    except Exception:  # noqa: BLE001 - surfaced via /health instead of crashing
        logger.exception("Failed to load drug database")

    if settings.eager_load_ocr:
        # Off the event loop: model init takes seconds.
        await run_in_threadpool(ocr_service.load)
    yield


app = FastAPI(
    title="Vietnamese Drug OCR Service",
    version="1.0.0",
    description=(
        "Reads Vietnamese drug packaging with pretrained PP-OCRv6 and proposes "
        "database candidates. Results always require user confirmation."
    ),
    lifespan=lifespan,
)


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": code, "message": message}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the traceback server-side; never leak it to the client."""
    logger.exception("Unhandled error on %s", request.url.path)
    return error_response("INTERNAL_ERROR", "An internal error occurred.", 500)


# --------------------------------------------------------------------------
# Upload handling
# --------------------------------------------------------------------------


async def read_upload(file: UploadFile) -> bytes:
    """Read at most ``max_file_size_bytes`` + 1 so a huge upload is not buffered.

    The client's filename and Content-Type are ignored entirely; the real format
    check happens when Pillow decodes the bytes.
    """
    limit = settings.max_file_size_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise UploadTooLargeError
        chunks.append(chunk)
    return b"".join(chunks)


def _run_ocr(data: bytes) -> tuple[PreparedImage, list[dict[str, Any]]]:
    """Preprocess + OCR. Runs in a worker thread."""
    prepared = prepare_image(
        data,
        settings.max_image_dimension,
        settings.allowed_image_formats,
        settings.ocr_min_dimension,
        settings.max_input_pixels,
    )
    results = filter_ocr_results(
        ocr_service.recognize(prepared.array), settings.ocr_confidence_threshold
    )
    # A photographed sheet can be a strongly rotated trapezoid inside a much
    # larger phone image. Axis-aligned OCR boxes then overlap vertically and a
    # fixed page-x gate loses later row numbers. Rectify only a confidently
    # detected bright document, OCR it as a second pass, and accept it only when
    # the prescription structure contains more credible medication rows.
    if classify_document(results) == "prescription":
        rectified = rectify_document(prepared.array)
        if rectified is not None:
            longest = max(rectified.shape[:2])
            if longest < settings.ocr_min_dimension:
                scale = settings.ocr_min_dimension / longest
                rectified = cv2.resize(
                    rectified,
                    (
                        max(1, round(rectified.shape[1] * scale)),
                        max(1, round(rectified.shape[0] * scale)),
                    ),
                    interpolation=cv2.INTER_LANCZOS4,
                )
            rectified_results = filter_ocr_results(
                ocr_service.recognize(rectified), settings.ocr_confidence_threshold
            )

            def extraction_quality(entries: list[dict[str, Any]]) -> tuple[int, int]:
                if classify_document(entries) != "prescription":
                    return (0, 0)
                rows = extract_medication_rows(entries)
                credible = sum(
                    bool(row.get("name_texts"))
                    and (
                        bool(extract_strengths(" ".join(row.get("resolver_texts") or [])))
                        or "(" in " ".join(row.get("resolver_texts") or [])
                    )
                    for row in rows
                )
                return credible, len(rows)

            if extraction_quality(rectified_results) > extraction_quality(results):
                results = rectified_results
                prepared = replace(
                    prepared,
                    array=rectified,
                    blur_score=round(float(cv2.Laplacian(cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()), 2),
                    width=rectified.shape[1],
                    height=rectified.shape[0],
                )
    # A diagnosis printed flush against a crop's top edge can be much fainter
    # than the bold drug rows (eval don14). Retry only that narrow band when a
    # prescription was recognized but no condition survived the normal pass.
    # This keeps normal-request latency unchanged and never invents a disease:
    # the fallback is accepted only if it reads an explicit diagnosis label.
    if classify_document(results) == "prescription":
        conditions = extract_prescription_conditions(results)
        has_condition = bool(
            conditions.get("diagnosis") or conditions.get("underlying_conditions")
        )
        if not has_condition:
            fallback = filter_ocr_results(
                ocr_service.recognize(enhance_top_band(prepared.array)),
                settings.ocr_confidence_threshold,
            )
            fallback_conditions = extract_prescription_conditions(fallback)
            if fallback_conditions.get("diagnosis") or fallback_conditions.get("underlying_conditions"):
                results = fallback
    return prepared, results


async def _ocr_or_error(
    file: UploadFile,
) -> tuple[PreparedImage, list[dict[str, Any]], None] | tuple[None, None, JSONResponse]:
    """Shared upload -> OCR path for both endpoints."""
    try:
        data = await read_upload(file)
    except UploadTooLargeError:
        megabytes = settings.max_file_size_bytes / (1024 * 1024)
        return None, None, error_response(
            "FILE_TOO_LARGE", f"Uploaded file exceeds the {megabytes:.0f} MB limit.", 413
        )

    try:
        prepared, results = await run_in_threadpool(_run_ocr, data)
    except InvalidImageError:
        return None, None, error_response(
            "INVALID_IMAGE", "Uploaded file is not a valid image.", 400
        )
    except OCRUnavailableError:
        return None, None, error_response(
            "OCR_UNAVAILABLE", "OCR model is not available.", 503
        )
    return prepared, results, None


def _image_metadata(prepared: PreparedImage) -> dict[str, Any]:
    return {
        "blur_score": prepared.blur_score,
        "width": prepared.width,
        "height": prepared.height,
        "original_width": prepared.original_width,
        "original_height": prepared.original_height,
        "image_format": prepared.image_format,
    }


def _ocr_drug_names(results: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Extract display-only OCR names without consulting the drug database."""
    document_type = classify_document(results)
    if document_type == "prescription":
        rows = extract_medication_rows(results)
        names = []
        for row in rows:
            name_items = row.get("name_items") or row.get("items", [])
            name_texts = row.get("name_texts") or row.get("texts", [])
            confidences = [item["confidence"] for item in name_items if item.get("confidence") is not None]
            names.append({
                "row_number": row["row_number"],
                "ocr_drug_name": " ".join(name_texts),
                "confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
            })
        return "", names

    selected = extract_package_name(results)
    names = " ".join(item["text"] for item in selected)
    confidence = round(sum(item["confidence"] for item in selected) / len(selected), 4) if selected else None
    return names, ([{"row_number": None, "ocr_drug_name": names, "confidence": confidence}] if names else [])


def _raw_ocr_text(results: list[dict[str, Any]]) -> str:
    """The recognizers' output, exactly as read, never repaired by the resolver.

    This used to prefer ``paddle_text`` as the "auditable" transcription, from
    when VietOCR was an experimental override of a trusted baseline. That
    premise is now inverted: PaddleOCR's dictionary cannot encode Vietnamese
    diacritics, so preferring it made ``raw_text`` and ``normalized_text``
    systematically wrong on every accented line. Arbitration is part of
    recognition, not a post-hoc repair -- the arbitrated text *is* the raw OCR.
    """
    return "\n".join(str(item["text"]) for item in results)


def _unreadable_reason(results: list[dict[str, Any]]) -> str | None:
    """Why this page cannot be parsed, or ``None`` if it can.

    Three refusals, in the order they can be established. Returning nothing at
    all is the safe answer for a drug-interaction tool: a wrong medicine the
    user cannot tell is wrong is more dangerous than an honest "unreadable".
    """
    if not results:
        return "no_text_detected"
    agreement = recognition_agreement(results)
    floor = settings.ocr_min_agreement
    if floor > 0 and agreement is not None and agreement < floor:
        # Both recognizers read the page, and they disagree about what it says.
        # Handwriting and photos too degraded to read both land here.
        return "illegible_or_handwritten"
    if classify_document(results) == "unknown":
        return "not_a_medical_document"
    return None


def _resolve_document(results: list[dict[str, Any]]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """Resolve a package as one drug or a prescription as independent rows."""
    document_type = classify_document(results)
    if document_type == "prescription":
        rows = extract_medication_rows(results)
        conditions = extract_prescription_conditions(results)
        medications: list[dict[str, Any]] = []
        for row in rows:
            # Resolve only the OCR text from the medicine-name column. Dosage
            # instructions and warehouse text are retained for display but do
            # not participate in drug-name matching.
            name_texts = row.get("name_texts") or row["texts"]
            # Match against the original medicine-name column, not the
            # display-cleaned text. This preserves strengths and aliases
            # such as "Prograf 1mg" and "Janumet 50mg/1000mg".
            resolver_texts = row.get("resolver_texts") or name_texts
            resolution = drug_resolver.resolve(resolver_texts)
            name_items = row.get("name_items") or row.get("items", [])
            name_confidences = [item["confidence"] for item in name_items if item.get("confidence") is not None]
            medications.append({
                "row_number": row["row_number"],
                "ocr_text": " ".join(row["texts"]),
                "ocr_drug_name": " ".join(name_texts),
                "ocr_name": " ".join(name_texts),
                "ocr_drug_name_refined": " ".join(name_texts),
                "ocr_drug_confidence": round(sum(name_confidences) / len(name_confidences), 4) if name_confidences else None,
                "detected_information": {
                    "strengths": resolution["strengths"],
                    "possible_ingredients": resolution["possible_ingredients"],
                },
                "candidates": resolution["candidates"],
                "database_matches": (
                    resolution["candidates"]
                    if resolution["candidates"]
                    and resolution["candidates"][0].get("score", 0) >= 0.75
                    else []
                ),
                "requires_confirmation": True,
            })
        strengths = [strength for medication in medications for strength in medication["detected_information"]["strengths"]]
        ingredients = [ingredient for medication in medications for ingredient in medication["detected_information"]["possible_ingredients"]]
        row_scores = [medication["candidates"][0]["score"] for medication in medications if medication["candidates"]]
        return document_type, {
            "strengths": list(dict.fromkeys(strengths)),
            "possible_ingredients": list(dict.fromkeys(ingredients)),
            # A prescription is only as certain as its least-certain row.
            "status": drug_resolver.status_for(min(row_scores)) if row_scores else "uncertain",
            "candidates": [],
            "diagnosis": conditions["diagnosis"],
            "underlying_conditions": conditions["underlying_conditions"],
            "icd_codes": conditions["icd_codes"],
        }, medications

    if document_type == "unknown":
        # Ảnh không phải giấy tờ thuốc: không đề xuất gì, để tầng trên báo cho
        # người dùng chụp lại. Cố khớp bừa ở đây nguy hiểm hơn là trả về rỗng.
        return document_type, {
            "candidates": [],
            "status": "uncertain",
            "strengths": [],
            "possible_ingredients": [],
        }, []

    # One photo can show several blisters. Resolve each printed object on its
    # own; joining them produces a single confident-looking answer that hides
    # every other medicine in the frame.
    products = extract_package_products(results)
    if len(products) >= 2:
        multi = _resolve_package_products(products, results)
        if len(multi) >= 2:
            information = drug_resolver.resolve([item["text"] for item in results])
            scores = [m["candidates"][0]["score"] for m in multi if m["candidates"]]
            return document_type, {
                "candidates": [],
                # As with a prescription, the photo is only as certain as its
                # least certain product.
                "status": drug_resolver.status_for(min(scores)) if scores else "uncertain",
                "strengths": information["strengths"],
                "possible_ingredients": information["possible_ingredients"],
            }, multi

    package_name_items = extract_package_name(results)
    package_name_texts = [item["text"] for item in package_name_items]
    name_resolution = drug_resolver.resolve(package_name_texts or [item["text"] for item in results])
    information_resolution = drug_resolver.resolve([item["text"] for item in results])
    resolution = {
        "candidates": name_resolution["candidates"],
        "status": name_resolution["status"],
        "strengths": information_resolution["strengths"],
        "possible_ingredients": information_resolution["possible_ingredients"],
    }
    medication = {
        "row_number": None,
        "ocr_text": "\n".join(item["text"] for item in results),
        "ocr_drug_name": " ".join(package_name_texts) or "\n".join(item["text"] for item in results),
        "ocr_drug_confidence": round(sum(item["confidence"] for item in package_name_items) / len(package_name_items), 4) if package_name_items else None,
        "detected_information": {
            "strengths": resolution["strengths"],
            "possible_ingredients": resolution["possible_ingredients"],
        },
        "diagnosis": "",
        "underlying_conditions": [],
        "icd_codes": [],
        "candidates": resolution["candidates"],
        "requires_confirmation": True,
    }
    return document_type, resolution, [medication]


def _resolve_package_products(
    products: list[dict[str, Any]], results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """One medication per distinct product shown in a packaging photo.

    A cluster becomes a product only with independent evidence that it is a
    medicine: a printed strength on the object, or a catalogue match. Without
    that gate a marketing headline or a manufacturer stamp becomes a "drug".
    The OCR text is still reported for a product that carries a strength but
    matches nothing, so a medicine missing from the catalogue stays visible
    instead of disappearing.
    """
    medications: list[dict[str, Any]] = []
    seen: set[str] = set()
    for product in products:
        texts = product["texts"]
        if not texts:
            continue
        resolution = drug_resolver.resolve(texts)
        candidates = resolution["candidates"]
        top = candidates[0] if candidates else None
        # Evidence gate. A manufacturer logo also finds a catalogue neighbour:
        # ``GLOMED`` resolves to ``Glomelid`` (Nalidixic acid) at 0.680, while
        # every genuine product measured on real packaging scored 0.807-1.000.
        # 0.75 sits in that gap and is already this project's suggestion
        # threshold. A cluster that matches nothing is still admitted when the
        # object carries a printed strength, so a medicine missing from the
        # catalogue stays visible instead of vanishing.
        if top is not None:
            if float(top.get("score") or 0.0) < settings.drug_medium_confidence:
                continue
        elif not product["has_strength"]:
            continue
        # One product can be printed twice on the same sheet -- a leaflet shows
        # its brand in the header and the ingredient on the pack shot. Those
        # resolve to different rows of the catalogue but the same active
        # ingredient, so identity is the ingredient when there is one.
        identity = matching_key(" ".join(texts))
        if top is not None:
            identity = matching_key(top.get("active_ingredient") or "") or top["drug_id"]
        if identity in seen:
            continue
        seen.add(identity)
        name_items = product["name_items"]
        confidences = [i["confidence"] for i in name_items if i.get("confidence") is not None]
        joined = " ".join(texts)
        medications.append({
            "row_number": len(medications) + 1,
            "ocr_text": joined,
            "ocr_drug_name": joined,
            "ocr_name": joined,
            "ocr_drug_name_refined": joined,
            "ocr_drug_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
            "detected_information": {
                "strengths": resolution["strengths"],
                "possible_ingredients": resolution["possible_ingredients"],
            },
            "diagnosis": "",
            "underlying_conditions": [],
            "icd_codes": [],
            "candidates": candidates,
            "database_matches": (
                candidates if candidates and candidates[0].get("score", 0) >= 0.75 else []
            ),
            "requires_confirmation": True,
        })
    return medications


def _build_recognition_response(
    prepared: PreparedImage,
    results: list[dict[str, Any]],
    started: float,
    ocr_finished: float,
) -> dict[str, Any]:
    """Build one recognition payload; shared by single and batch endpoints."""
    raw_text = _raw_ocr_text(results)
    reason = _unreadable_reason(results)
    if reason is not None:
        document_type, resolution, medications = "unknown", {
            "candidates": [], "status": "uncertain",
            "strengths": [], "possible_ingredients": [],
        }, []
    else:
        document_type, resolution, medications = _resolve_document(results)
    finished = time.perf_counter()
    return {
        "success": True,
        "raw_text": raw_text,
        "normalized_text": normalize_text(raw_text),
        "document_type": document_type,
        "unreadable_reason": reason,
        "ocr_results": results,
        "detected_information": {
            "strengths": resolution["strengths"],
            "possible_ingredients": resolution["possible_ingredients"],
        },
        "diagnosis": resolution.get("diagnosis", ""),
        "underlying_conditions": resolution.get("underlying_conditions", []),
        "icd_codes": resolution.get("icd_codes", []),
        "candidates": resolution["candidates"],
        "medications": medications,
        "diagnosis": resolution.get("diagnosis", ""),
        "underlying_conditions": resolution.get("underlying_conditions", []),
        "icd_codes": resolution.get("icd_codes", []),
        "status": resolution["status"],
        "requires_confirmation": True,
        "metadata": {
            **_image_metadata(prepared),
            "ocr_time_ms": round((ocr_finished - started) * 1000, 2),
            "resolver_time_ms": round((finished - ocr_finished) * 1000, 2),
            "total_time_ms": round((finished - started) * 1000, 2),
        },
    }


def _json_error_payload(response: JSONResponse) -> dict[str, Any]:
    """Convert a shared JSONResponse error into a nested batch result."""
    import json

    return {"status_code": response.status_code, **json.loads(response.body)}


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> Any:
    vietocr_ready = not ocr_service.vietocr_enabled or ocr_service.vietocr_loaded
    ready = ocr_service.loaded and drug_resolver.loaded and vietocr_ready
    payload = {
        "status": "ok" if ready else "error",
        "ocr_model_loaded": ocr_service.loaded,
        "drug_database_loaded": drug_resolver.loaded,
        "drug_count": len(drug_resolver.drugs),
        "ocr_error": ocr_service.load_error,
        # Surfaced separately: the service still answers requests without
        # VietOCR, but every Vietnamese diacritic in the output will be wrong,
        # which is not something that should fail silently.
        "vietocr_loaded": ocr_service.vietocr_loaded,
        "vietocr_error": ocr_service.vietocr_error,
    }
    if not ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.post(
    "/api/v1/ocr",
    response_model=OCRResponse,
    responses=ERROR_RESPONSES,
    tags=["ocr"],
    summary="Read text from a drug image",
)
async def ocr_endpoint(image: UploadFile = File(...)) -> Any:
    started = time.perf_counter()
    prepared, results, failure = await _ocr_or_error(image)
    if failure is not None:
        return failure

    raw_text = _raw_ocr_text(results)
    document_type = classify_document(results)
    ocr_drug_name, ocr_drug_names = _ocr_drug_names(results)
    return {
        "success": True,
        "raw_text": raw_text,
        "normalized_text": normalize_text(raw_text),
        "document_type": document_type,
        "ocr_drug_name": ocr_drug_name,
        "ocr_drug_names": ocr_drug_names,
        "ocr_results": results,
        "metadata": {
            **_image_metadata(prepared),
            "processing_time_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    }


@app.post(
    "/api/v1/ocr/batch",
    responses=ERROR_RESPONSES,
    tags=["ocr"],
    summary="Read text from up to five drug images",
)
async def ocr_batch_endpoint(images: list[UploadFile] = File(...)) -> Any:
    if not images:
        return error_response("NO_IMAGES", "At least one image is required.", 400)
    if len(images) > settings.max_batch_images:
        return error_response(
            "TOO_MANY_IMAGES",
            f"A batch may contain at most {settings.max_batch_images} images.",
            400,
        )

    batch_started = time.perf_counter()
    results: list[dict[str, Any]] = []
    for index, image in enumerate(images, 1):
        started = time.perf_counter()
        prepared, ocr_results, failure = await _ocr_or_error(image)
        item: dict[str, Any] = {
            "index": index,
            "filename": image.filename or f"image-{index}",
        }
        if failure is not None:
            item["result"] = _json_error_payload(failure)
        else:
            raw_text = "\n".join(entry["text"] for entry in ocr_results)
            document_type = classify_document(ocr_results)
            ocr_drug_name, ocr_drug_names = _ocr_drug_names(ocr_results)
            item["result"] = {
                "success": True,
                "raw_text": raw_text,
                "normalized_text": normalize_text(raw_text),
                "document_type": document_type,
                "ocr_drug_name": ocr_drug_name,
                "ocr_drug_names": ocr_drug_names,
                "ocr_results": ocr_results,
                "metadata": {
                    **_image_metadata(prepared),
                    "processing_time_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            }
        results.append(item)

    return {
        "success": True,
        "total_images": len(results),
        "results": results,
        "processing_time_ms": round((time.perf_counter() - batch_started) * 1000, 2),
    }


@app.post(
    "/api/v1/drug/recognize",
    response_model=DrugRecognitionResponse,
    responses=ERROR_RESPONSES,
    tags=["drug"],
    summary="Read a drug image and propose database candidates",
)
async def recognize_drug(image: UploadFile = File(...)) -> Any:
    started = time.perf_counter()
    prepared, results, failure = await _ocr_or_error(image)
    if failure is not None:
        return failure

    ocr_finished = time.perf_counter()
    return await run_in_threadpool(
        _build_recognition_response, prepared, results, started, ocr_finished
    )


@app.post(
    "/api/v1/drug/recognize/batch",
    responses=ERROR_RESPONSES,
    tags=["drug"],
    summary="Recognize up to five drug packages or prescriptions",
)
async def recognize_drug_batch(images: list[UploadFile] = File(...)) -> Any:
    if not images:
        return error_response("NO_IMAGES", "At least one image is required.", 400)
    if len(images) > settings.max_batch_images:
        return error_response(
            "TOO_MANY_IMAGES",
            f"A batch may contain at most {settings.max_batch_images} images.",
            400,
        )

    batch_started = time.perf_counter()
    results: list[dict[str, Any]] = []
    for index, image in enumerate(images, 1):
        started = time.perf_counter()
        prepared, ocr_results, failure = await _ocr_or_error(image)
        item: dict[str, Any] = {
            "index": index,
            "filename": image.filename or f"image-{index}",
        }
        if failure is not None:
            item["result"] = _json_error_payload(failure)
        else:
            ocr_finished = time.perf_counter()
            item["result"] = await run_in_threadpool(
                _build_recognition_response,
                prepared,
                ocr_results,
                started,
                ocr_finished,
            )
        results.append(item)

    return {
        "success": True,
        "total_images": len(results),
        "results": results,
        "processing_time_ms": round((time.perf_counter() - batch_started) * 1000, 2),
    }
