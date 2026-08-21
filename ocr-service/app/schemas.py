"""Pydantic response models. These define the contract the main app codes against."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DrugStatus = Literal["high_confidence", "medium_confidence", "uncertain"]


class OCRItem(BaseModel):
    """One text region: detected by PaddleOCR, read by VietOCR or PaddleOCR."""

    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: list[list[float]] | None = None
    recognizer: Literal["vietocr", "paddleocr"] | None = Field(
        default=None, description="Which recognizer's reading won this region."
    )


class HealthResponse(BaseModel):
    status: str = "ok"
    ocr_model_loaded: bool
    drug_database_loaded: bool
    drug_count: int = 0
    ocr_error: str | None = None
    # False means Vietnamese diacritics cannot be read at all -- PaddleOCR's
    # recognizer has no codepoints for them.
    vietocr_loaded: bool = False
    vietocr_error: str | None = None


class ImageMetadata(BaseModel):
    blur_score: float = Field(description="Laplacian variance; higher is sharper.")
    width: int
    height: int
    original_width: int
    original_height: int
    image_format: str


class OCRMetadata(ImageMetadata):
    processing_time_ms: float


class OCRResponse(BaseModel):
    success: bool = True
    raw_text: str = Field(description="OCR output exactly as returned, never repaired.")
    normalized_text: str = Field(description="Unicode/whitespace-normalized copy.")
    document_type: Literal["medicine_package", "prescription", "unknown"] = "unknown"
    ocr_drug_name: str = ""
    ocr_drug_names: list[dict] = Field(default_factory=list)
    ocr_results: list[OCRItem]
    metadata: OCRMetadata


class DetectedInformation(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    possible_ingredients: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    name_score: float
    strength_score: float
    ingredient_score: float


class DrugCandidate(BaseModel):
    drug_id: str
    drug_name: str
    active_ingredient: str = ""
    strength: str = ""
    dosage_form: str = ""
    manufacturer: str = ""
    registration_number: str = ""
    score: float
    score_breakdown: ScoreBreakdown


class RecognizeMetadata(ImageMetadata):
    ocr_time_ms: float
    resolver_time_ms: float
    total_time_ms: float


class MedicationRecognition(BaseModel):
    row_number: int | None = None
    ocr_text: str
    ocr_drug_name: str = ""
    # Keep OCR output separate from database suggestions.  The resolver must
    # never overwrite what was read from the image.
    ocr_name: str = ""
    ocr_drug_name_refined: str = ""
    ocr_drug_confidence: float | None = None
    detected_information: DetectedInformation
    candidates: list[DrugCandidate]
    database_matches: list[DrugCandidate] = Field(default_factory=list)
    requires_confirmation: Literal[True] = True


class DrugRecognitionResponse(BaseModel):
    success: bool = True
    raw_text: str
    normalized_text: str
    document_type: Literal["medicine_package", "prescription", "unknown"] = "unknown"
    ocr_results: list[OCRItem]
    detected_information: DetectedInformation
    candidates: list[DrugCandidate]
    medications: list[MedicationRecognition] = Field(default_factory=list)
    diagnosis: str = ""
    underlying_conditions: list[str] = Field(default_factory=list)
    icd_codes: list[str] = Field(default_factory=list)
    status: DrugStatus
    # Invariant: the service never picks the final drug on the user's behalf.
    requires_confirmation: Literal[True] = True
    metadata: RecognizeMetadata
class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
