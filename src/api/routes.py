import asyncio
import logging
import os
import re
import time
from datetime import date, datetime

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.agents.graph import agent
from src.api.deps import get_current_user, require_role
from src.config import get_settings
from src.db.models import (
    Disease,
    InteractionCheck,
    Medication,
    MedicationAlias,
    Notification,
    PatientCondition,
    PatientMedication,
    PatientPrescription,
    PatientProfile,
    PharmacistReview,
    Product,
    ProductIngredient,
    User,
)
from src.db.session import get_db
from src.models.schemas import (
    AddProductRequest,
    ChatRequest,
    ChatResponse,
    CreatePrescriptionRequest,
    DiseaseCandidate,
    DiseaseInfo,
    InteractionCheckSummary,
    MedicationCheckRequest,
    MedicationCheckResponse,
    MedicationItem,
    MedicationSearchResult,
    NotificationItem,
    PatientPrescriptionSummary,
    PatientProfileInfo,
    PharmacistProfileInfo,
    PharmacistReviewRequest,
    PharmacistReviewResponse,
    PharmacistSummary,
    PrescriptionInput,
    ProductCheckRequest,
    ProductSearchResult,
    RenamePrescriptionRequest,
    RequestReviewRequest,
    ReviewRequestSummary,
    ScannedDisease,
    ScannedDrug,
    ScanPrescriptionResponse,
    UpdatePatientConditionsRequest,
    UpdatePatientProfileRequest,
    UpdatePharmacistProfileRequest,
)
from src.services.disease_search import (
    match_diseases_in_phrase,
    normalize_disease_search_text,
    rank_disease_matches,
)
from src.services.food_disease_explain import (
    build_disease_interaction_explanations,
    build_food_disease_warning_line,
    build_food_interaction_explanations,
)
from src.services.food_disease_lookup import lookup_disease_interactions, lookup_food_interactions
from src.services.rollup_explain import (
    build_overview_explanation,
    build_product_edges,
    build_product_explanations,
    filter_cross_prescription_edges,
)

router = APIRouter()

logger = logging.getLogger(__name__)


async def _timed(label: str, coro):
    """Đo + log thời gian chạy 1 coroutine - dùng để so sánh nhánh nào (rollup cấp
    thuốc, tổng quan, thực phẩm, bệnh nền...) đang chiếm nhiều thời gian nhất trong 1
    lần kiểm tra tương tác. Không đổi giá trị trả về, chỉ thêm quan sát."""
    start = time.perf_counter()
    result = await coro
    logger.info("[timing] %s: %.3fs", label, time.perf_counter() - start)
    return result

# Field chỉ dành cho vai trò dược sĩ (GD6 mục 7.2) - không trả cho bệnh nhân.
_PHARMACIST_ONLY_FIELDS = {
    "xu_tri",
    "thay_the_a",
    "thay_the_b",
    "mo_ta",
    "giai_thich_duoc_si",
    # Bản dịch nguyên văn (không qua diễn giải) từ tiếng Anh sang tiếng Việt của
    # mo_ta/xu_tri - cùng mức truy cập với mo_ta/xu_tri gốc.
    "mo_ta_dich",
    "xu_tri_dich",
}


def _strip_pharmacist_fields(items: list[dict]) -> list[dict]:
    return [{k: v for k, v in item.items() if k not in _PHARMACIST_ONLY_FIELDS} for item in items]


def _ensure_can_view_patient(current_user: User, patient_id: str, db: Session) -> None:
    if current_user.id == patient_id:
        return
    # Dược sĩ chỉ được xem dữ liệu cần cho đúng lần tra cứu qua các endpoint
    # /pharmacist/reviews/{check_id}/..., không được dùng patient_id để đọc toàn bộ
    # thuốc, đơn thuốc, bệnh nền hay lịch sử của người dùng. `db` được giữ trong
    # chữ ký để tránh thay đổi hàng loạt call site hiện có.
    raise HTTPException(status_code=403, detail="Không có quyền xem dữ liệu của người dùng này")


def _get_or_create_default_prescription(patient_id: str, db: Session) -> PatientPrescription:
    """Đơn thuốc mặc định để "nhận nuôi" các PatientMedication chưa gắn đơn nào -
    tự tạo lazy ở lần đầu cần đến (list, hoặc add không kèm prescription_id), thay
    vì chạy 1 script backfill riêng. Cùng 1 đường đi cho dữ liệu cũ (tạo trước khi
    có khái niệm đơn thuốc) lẫn bệnh nhân mới đăng ký."""
    existing = (
        db.query(PatientPrescription)
        .filter(PatientPrescription.patient_id == patient_id)
        .order_by(PatientPrescription.ngay_tao)
        .first()
    )
    if existing is not None:
        return existing

    default = PatientPrescription(patient_id=patient_id, label="Đơn thuốc 1")
    db.add(default)
    db.flush()
    (
        db.query(PatientMedication)
        .filter(PatientMedication.patient_id == patient_id, PatientMedication.prescription_id.is_(None))
        .update({"prescription_id": default.id})
    )
    db.commit()
    db.refresh(default)
    return default


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat với AI agent."""
    try:
        result = await agent.ainvoke({"query": request.message})
        return ChatResponse(
            response=result.get("response", ""),
            analysis=result.get("analysis", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def agent_status():
    """Kiểm tra trạng thái agent."""
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}


# ---- Tra cứu / chuẩn hóa thuốc ----


@router.get("/medications/search", response_model=list[MedicationSearchResult])
async def search_medications(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MedicationSearchResult]:
    """Gợi ý tên thuốc - khớp cả tên chuẩn LẪN bảng alias, để nhất quán với
    drug_normalizer_tool (dùng khi POST /patients/{id}/medications thật sự lưu)."""
    like_pattern = f"%{q.strip().lower()}%"

    name_matches = (
        db.query(Medication).filter(func.lower(Medication.ten_chuan_hoa).like(like_pattern)).all()
    )
    alias_matches = (
        db.query(Medication)
        .join(MedicationAlias, MedicationAlias.medication_id == Medication.id)
        .filter(func.lower(MedicationAlias.alias).like(like_pattern))
        .all()
    )

    unique_by_id = {m.id: m for m in [*name_matches, *alias_matches]}
    results = sorted(unique_by_id.values(), key=lambda m: m.ten_chuan_hoa)[:10]
    return [MedicationSearchResult(id=m.id, ten_chuan_hoa=m.ten_chuan_hoa) for m in results]


@router.get("/guest/medications/search", response_model=list[MedicationSearchResult])
async def guest_search_medications(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> list[MedicationSearchResult]:
    """Tra cứu công khai cho khách vãng lai; không yêu cầu tài khoản và không ghi dữ liệu."""
    like_pattern = f"%{q.strip().lower()}%"
    name_matches = db.query(Medication).filter(func.lower(Medication.ten_chuan_hoa).like(like_pattern)).all()
    alias_matches = (
        db.query(Medication)
        .join(MedicationAlias, MedicationAlias.medication_id == Medication.id)
        .filter(func.lower(MedicationAlias.alias).like(like_pattern))
        .all()
    )
    unique_by_id = {m.id: m for m in [*name_matches, *alias_matches]}
    results = sorted(unique_by_id.values(), key=lambda m: m.ten_chuan_hoa)[:10]
    return [MedicationSearchResult(id=m.id, ten_chuan_hoa=m.ten_chuan_hoa) for m in results]


# ---- Tra cứu / kiểm tra tương tác theo tên thuốc (biệt dược) ----


@router.get("/products/search", response_model=list[ProductSearchResult])
async def search_products(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProductSearchResult]:
    like_pattern = f"%{q.strip().lower()}%"
    matches = (
        db.query(Product)
        .filter(func.lower(Product.ten_thuoc).like(like_pattern))
        .order_by(Product.ten_thuoc)
        .limit(10)
        .all()
    )
    return [ProductSearchResult(id=p.id, ten_thuoc=p.ten_thuoc) for p in matches]


@router.get("/guest/products/search", response_model=list[ProductSearchResult])
async def guest_search_products(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> list[ProductSearchResult]:
    like_pattern = f"%{q.strip().lower()}%"
    matches = (
        db.query(Product)
        .filter(func.lower(Product.ten_thuoc).like(like_pattern))
        .order_by(Product.ten_thuoc)
        .limit(10)
        .all()
    )
    return [ProductSearchResult(id=p.id, ten_thuoc=p.ten_thuoc) for p in matches]


def _brand_names(hoat_chat_name: str | None, ingredient_to_products: dict[str, list[str]]) -> list[str]:
    if not hoat_chat_name:
        return []
    brands = ingredient_to_products.get(hoat_chat_name)
    if not brands:
        return []
    return list(dict.fromkeys(brands))


def _brand_label(hoat_chat_name: str | None, unique_brands: list[str]) -> str | None:
    if not hoat_chat_name:
        return hoat_chat_name
    if not unique_brands:
        return hoat_chat_name
    return f"{'/'.join(unique_brands)} (hoạt chất: {hoat_chat_name})"


def _enrich_with_brand_names(items: list[dict], ingredient_to_products: dict[str, list[str]]) -> list[dict]:
    """Gắn tên thương hiệu (san_pham_*) bên cạnh hoạt chất gốc (hoat_chat_*), giữ
    thuoc_a/thuoc_b dạng chuỗi gộp cũ để không phá vỡ UI đang hiển thị trực tiếp.

    san_pham_a/san_pham_b là danh sách tên thuốc (trong lần kiểm tra hiện tại) có
    chứa hoạt chất đó - dùng để gộp (rollup) cạnh ở cấp thuốc trên đồ thị tương tác.
    """
    enriched = []
    for item in items:
        item = dict(item)
        hoat_chat_a = item.get("thuoc_a")
        hoat_chat_b = item.get("thuoc_b")
        brands_a = _brand_names(hoat_chat_a, ingredient_to_products)
        brands_b = _brand_names(hoat_chat_b, ingredient_to_products)
        item["hoat_chat_a"] = hoat_chat_a
        item["hoat_chat_b"] = hoat_chat_b
        item["san_pham_a"] = brands_a
        item["san_pham_b"] = brands_b
        item["thuoc_a"] = _brand_label(hoat_chat_a, brands_a)
        item["thuoc_b"] = _brand_label(hoat_chat_b, brands_b)
        enriched.append(item)
    return enriched


def _resolve_products(
    product_names: list[str], db: Session
) -> tuple[list[str], dict[str, list[str]], list[str], list[str], dict[str, str]]:
    """Quy đổi tên thuốc -> danh sách hoạt chất (dedup, exact-match Product.ten_thuoc) để
    đưa vào agent hiện có (KHÔNG đổi gì trong src/agents/ - agent vẫn nhận tên hoạt chất).

    Trả về (ingredient_names, ingredient_to_products, unknown_products,
    no_interaction_data_products, canonical_by_input). canonical_by_input ánh xạ tên
    thuốc người dùng nhập (viết thường) -> Product.ten_thuoc chuẩn trong CSDL, dùng
    để đối chiếu với san_pham_a/san_pham_b (rollup cấp thuốc/cấp đơn ở routes bên dưới).
    """
    ingredient_names: list[str] = []
    ingredient_to_products: dict[str, list[str]] = {}
    unknown_products: list[str] = []
    no_interaction_data_products: list[str] = []
    canonical_by_input: dict[str, str] = {}
    seen: set[str] = set()

    for name in product_names:
        product = (
            db.query(Product).filter(func.lower(Product.ten_thuoc) == name.strip().lower()).first()
        )
        if product is None:
            unknown_products.append(name)
            continue

        canonical_by_input[name.strip().lower()] = product.ten_thuoc

        ingredient_meds = (
            db.query(Medication)
            .join(ProductIngredient, ProductIngredient.medication_id == Medication.id)
            .filter(ProductIngredient.product_id == product.id)
            .all()
        )
        if not ingredient_meds:
            no_interaction_data_products.append(name)
            continue

        for med in ingredient_meds:
            ingredient_to_products.setdefault(med.ten_chuan_hoa, []).append(product.ten_thuoc)
            key = med.ten_chuan_hoa.lower()
            if key not in seen:
                seen.add(key)
                ingredient_names.append(med.ten_chuan_hoa)

    return (
        ingredient_names,
        ingredient_to_products,
        unknown_products,
        no_interaction_data_products,
        canonical_by_input,
    )


def _flatten_prescriptions(
    prescriptions: list[PrescriptionInput],
) -> tuple[list[str], dict[str, set[int]]]:
    """Gộp tên thuốc từ mọi đơn (dedup, giữ thứ tự xuất hiện) + ghi nhận mỗi tên
    thuốc (viết thường) thuộc chỉ số đơn nào - dùng để tính cạnh cấp đơn thuốc sau
    khi đã có cạnh cấp thuốc."""
    flat: list[str] = []
    seen: set[str] = set()
    origins: dict[str, set[int]] = {}

    for index, prescription in enumerate(prescriptions):
        for name in prescription.products:
            key = name.strip().lower()
            if key not in seen:
                seen.add(key)
                flat.append(name)
            origins.setdefault(key, set()).add(index)

    return flat, origins


async def _run_product_check(
    prescriptions: list[PrescriptionInput],
    db: Session,
    for_pharmacist: bool = False,
    disease_ids: list[int] | None = None,
    disease_interaction_scope: str = "general",
    patient_conditions_snapshot: list[dict] | None = None,
) -> tuple[dict, list[str], list[str]]:
    """Dùng chung cho patient/guest/pharmacist: resolve tên thuốc -> hoạt chất, chạy agent
    hiện có, gắn tên thuốc (biệt dược) vào kết quả, rồi tự tính + sinh giải thích riêng
    cho cấp thuốc. Cả 2 luồng đều sinh overview (tóm tắt tổng quan) - khác nhau ở
    audience truyền vào build_overview_explanation (giọng thân thiện cho bệnh nhân,
    khoa học/chuyên nghiệp cho dược sĩ).
    """
    _t_start = time.perf_counter()
    flat_products, origins_by_input = _flatten_prescriptions(prescriptions)
    _t_resolve = time.perf_counter()
    ingredient_names, ingredient_to_products, unknown, no_data, canonical_by_input = _resolve_products(
        flat_products, db
    )
    logger.info("[timing] resolve_products: %.3fs", time.perf_counter() - _t_resolve)

    audience = "pharmacist" if for_pharmacist else "patient"
    result = dict(
        await _timed(
            "agent_total (normalize+lookup+rank+explain+guardrail)",
            agent.ainvoke({"raw_medications": ingredient_names, "audience": audience}),
        )
    )
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    result["ranked_results"] = _enrich_with_brand_names(
        result.get("ranked_results", []), ingredient_to_products
    )
    result["explanations"] = _enrich_with_brand_names(
        result.get("explanations", []), ingredient_to_products
    )

    product_edges = build_product_edges(result["explanations"])

    product_origins: dict[str, set[int]] = {}
    if len(prescriptions) > 1:
        for input_key, rx_indexes in origins_by_input.items():
            canonical = canonical_by_input.get(input_key)
            if not canonical:
                continue
            product_origins.setdefault(canonical.lower(), set()).update(rx_indexes)

    # So từ 2 đơn trở lên (cả bệnh nhân lẫn dược sĩ): chỉ tính tương tác GIỮA các
    # đơn khác nhau cho cấp thuốc + tóm tắt tổng quan - bỏ tương tác trong cùng 1
    # đơn, vì so nhiều đơn chỉ nhằm phát hiện rủi ro mới phát sinh khi gộp chung,
    # không phải rà lại từng đơn đang dùng riêng lẻ.
    overview_product_edges = (
        filter_cross_prescription_edges(product_edges, product_origins)
        if len(prescriptions) > 1
        else product_edges
    )

    # Tương tác thuốc-thực phẩm/thuốc-bệnh nền chạy NGOÀI agent. Thuốc-bệnh được
    # lọc bằng disease_id khi luồng bệnh nhân có patient_conditions; disease_ids=None
    # giữ hành vi cảnh báo chung cho fallback/guest/dược sĩ.
    valid_medication_ids = [
        med["medication_id"]
        for med in result.get("normalized_medications", [])
        if not med.get("khong_du_du_lieu")
    ]
    _t_food_lookup = time.perf_counter()
    # Chế độ đánh giá (eval/PLAN.md): bỏ nhánh thực phẩm/bệnh nền không liên quan tới
    # case đang chấm - mỗi thuốc kéo theo hàng chục edge/call LLM. Giá trị: "both"/"1"
    # (bỏ cả hai), "food", "disease". Không set -> chạy đầy đủ như thật.
    _eval_skip = os.environ.get("EVAL_SKIP_FOOD_DISEASE", "")
    food_rows = (
        [] if _eval_skip in ("1", "both", "food")
        else lookup_food_interactions(valid_medication_ids, db)
    )
    disease_rows = (
        [] if _eval_skip in ("1", "both", "disease")
        else lookup_disease_interactions(valid_medication_ids, db, disease_ids=disease_ids)
    )
    logger.info("[timing] food_disease_lookup (SQL): %.3fs", time.perf_counter() - _t_food_lookup)

    # 4 nhánh sinh giải thích HOÀN TOÀN không phụ thuộc lẫn nhau - kể cả overview giờ
    # cũng đọc thẳng product_edges (dữ liệu gốc + bản dịch đã cache), không còn đợi
    # product_explanations viết xong như trước (xem build_overview_explanation). Chạy
    # song song bằng asyncio.gather thay vì await nối tiếp từng nhánh, cắt phần lớn
    # thời gian chờ khi 1 lần kiểm tra cần nhiều "đợt" LLM (rollup cấp thuốc, tổng
    # quan, thực phẩm, bệnh nền).
    (
        product_explanations,
        overview,
        food_interactions,
        disease_interactions,
    ) = await asyncio.gather(
        _timed(
            "product_explanations (rollup cấp thuốc)",
            build_product_explanations(overview_product_edges, audience=audience),
        ),
        _timed(
            "overview (tổng quan tóm tắt)",
            build_overview_explanation(
                overview_product_edges,
                audience=audience,
                prescription_count=len(prescriptions),
            ),
        ),
        _timed(
            "food_interactions (thuốc-thực phẩm)",
            build_food_interaction_explanations(food_rows, ingredient_to_products, audience=audience),
        ),
        _timed(
            "disease_interactions (thuốc-bệnh nền)",
            build_disease_interaction_explanations(disease_rows, ingredient_to_products, audience=audience),
        ),
    )
    logger.info("[timing] === product_check total: %.3fs ===", time.perf_counter() - _t_start)

    result["product_explanations"] = product_explanations
    result["overview"] = overview
    result["checked_products"] = flat_products
    result["prescriptions"] = [{"label": p.label, "products": p.products} for p in prescriptions]
    result["food_interactions"] = food_interactions
    result["disease_interactions"] = disease_interactions
    result["has_severe_disease_interaction"] = any(
        item.get("muc_do") == "nang" for item in disease_interactions
    )
    result["disease_interaction_scope"] = disease_interaction_scope
    result["patient_conditions_snapshot"] = patient_conditions_snapshot or []
    result["canh_bao_thuc_pham_benh_nen"] = build_food_disease_warning_line(
        result["food_interactions"], result["disease_interactions"], audience=audience
    )

    return result, unknown, no_data


@router.post("/products/check", response_model=MedicationCheckResponse)
async def check_products(
    request: ProductCheckRequest,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> MedicationCheckResponse:
    if request.personalized:
        disease_ids, disease_scope, condition_snapshot = _patient_disease_context(
            current_user.id, db
        )
    else:
        disease_ids, disease_scope, condition_snapshot = None, "general", []
    result, unknown, no_data = await _run_product_check(
        request.prescriptions,
        db,
        disease_ids=disease_ids,
        disease_interaction_scope=disease_scope,
        patient_conditions_snapshot=condition_snapshot,
    )
    result["is_personalized"] = request.personalized

    check = InteractionCheck(
        patient_id=current_user.id,
        ket_qua_json=result,
        co_canh_bao_nang=bool(
            result.get("has_severe") or result.get("has_severe_disease_interaction")
        ),
        co_chua_phan_loai=bool(result.get("has_unclassified")),
        thuoc_da_kiem_tra=_checked_drug_names(result),
    )
    db.add(check)
    db.commit()
    db.refresh(check)

    return MedicationCheckResponse(
        interaction_check_id=check.id,
        is_personalized=request.personalized,
        ranked_results=_strip_pharmacist_fields(result.get("ranked_results", [])),
        explanations=_strip_pharmacist_fields(result.get("explanations", [])),
        has_severe=result.get("has_severe", False),
        has_severe_disease_interaction=result.get("has_severe_disease_interaction", False),
        has_unclassified=result.get("has_unclassified", False),
        unknown_products=unknown,
        no_interaction_data_products=no_data,
        checked_products=result.get("checked_products", []),
        prescriptions=result.get("prescriptions", []),
        product_explanations=_strip_pharmacist_fields(result.get("product_explanations", [])),
        overview=result.get("overview"),
        food_interactions=_strip_pharmacist_fields(result.get("food_interactions", [])),
        disease_interactions=_strip_pharmacist_fields(result.get("disease_interactions", [])),
        disease_interaction_scope=result.get("disease_interaction_scope", "general"),
        patient_conditions_snapshot=result.get("patient_conditions_snapshot", []),
        canh_bao_thuc_pham_benh_nen=result.get("canh_bao_thuc_pham_benh_nen"),
    )


@router.post("/guest/products/check", response_model=MedicationCheckResponse)
async def guest_check_products(
    request: ProductCheckRequest,
    db: Session = Depends(get_db),
) -> MedicationCheckResponse:
    result, unknown, no_data = await _run_product_check(request.prescriptions, db)
    return MedicationCheckResponse(
        interaction_check_id="guest-check",
        ranked_results=_strip_pharmacist_fields(result.get("ranked_results", [])),
        explanations=_strip_pharmacist_fields(result.get("explanations", [])),
        has_severe=result.get("has_severe", False),
        has_severe_disease_interaction=result.get("has_severe_disease_interaction", False),
        has_unclassified=result.get("has_unclassified", False),
        unknown_products=unknown,
        no_interaction_data_products=no_data,
        checked_products=result.get("checked_products", []),
        prescriptions=result.get("prescriptions", []),
        product_explanations=_strip_pharmacist_fields(result.get("product_explanations", [])),
        overview=result.get("overview"),
        food_interactions=_strip_pharmacist_fields(result.get("food_interactions", [])),
        disease_interactions=_strip_pharmacist_fields(result.get("disease_interactions", [])),
        disease_interaction_scope=result.get("disease_interaction_scope", "general"),
        patient_conditions_snapshot=result.get("patient_conditions_snapshot", []),
        canh_bao_thuc_pham_benh_nen=result.get("canh_bao_thuc_pham_benh_nen"),
    )


@router.post("/pharmacist/products/check", response_model=MedicationCheckResponse)
async def check_products_as_pharmacist(
    request: ProductCheckRequest,
    current_user: User = Depends(require_role("pharmacist")),
    db: Session = Depends(get_db),
) -> MedicationCheckResponse:
    """Công cụ tra cứu độc lập cho dược sĩ - không lưu lịch sử, KHÔNG ẩn xu_tri/thay_the."""
    result, unknown, no_data = await _run_product_check(request.prescriptions, db, for_pharmacist=True)
    return MedicationCheckResponse(
        interaction_check_id="pharmacist-lookup",
        ranked_results=result.get("ranked_results", []),
        explanations=result.get("explanations", []),
        has_severe=result.get("has_severe", False),
        has_severe_disease_interaction=result.get("has_severe_disease_interaction", False),
        has_unclassified=result.get("has_unclassified", False),
        unknown_products=unknown,
        no_interaction_data_products=no_data,
        checked_products=result.get("checked_products", []),
        prescriptions=result.get("prescriptions", []),
        product_explanations=result.get("product_explanations", []),
        overview=result.get("overview"),
        food_interactions=result.get("food_interactions", []),
        disease_interactions=result.get("disease_interactions", []),
        disease_interaction_scope=result.get("disease_interaction_scope", "general"),
        patient_conditions_snapshot=result.get("patient_conditions_snapshot", []),
        canh_bao_thuc_pham_benh_nen=result.get("canh_bao_thuc_pham_benh_nen"),
    )


# ---- Hồ sơ thuốc bệnh nhân ----


def _medication_item(pm: PatientMedication, product: Product) -> MedicationItem:
    return MedicationItem(
        id=pm.id,
        product_id=product.id,
        ten_thuoc=product.ten_thuoc,
        prescription_id=pm.prescription_id,
        ngay_bat_dau=pm.ngay_bat_dau,
        ngay_ket_thuc=pm.ngay_ket_thuc,
    )


@router.get("/patients/{patient_id}/medications", response_model=list[MedicationItem])
async def list_patient_medications(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MedicationItem]:
    _ensure_can_view_patient(current_user, patient_id, db)

    rows = (
        db.query(PatientMedication, Product)
        .join(Product, Product.id == PatientMedication.product_id)
        .filter(PatientMedication.patient_id == patient_id)
        .all()
    )
    return [_medication_item(pm, product) for pm, product in rows]


@router.post(
    "/patients/{patient_id}/medications", response_model=MedicationItem, status_code=201
)
async def add_patient_medication(
    patient_id: str,
    request: AddProductRequest,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> MedicationItem:
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự thêm thuốc cho chính mình")

    product = (
        db.query(Product)
        .filter(func.lower(Product.ten_thuoc) == request.product_name.strip().lower())
        .first()
    )
    if product is None:
        raise HTTPException(
            status_code=422, detail=f"Không tìm thấy thuốc '{request.product_name}' trong CSDL"
        )

    if request.prescription_id:
        prescription = db.get(PatientPrescription, request.prescription_id)
        if prescription is None or prescription.patient_id != patient_id:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn thuốc")
    else:
        prescription = _get_or_create_default_prescription(patient_id, db)

    pm = PatientMedication(
        patient_id=patient_id,
        prescription_id=prescription.id,
        product_id=product.id,
        ngay_bat_dau=date.today(),
    )
    db.add(pm)
    db.commit()
    db.refresh(pm)

    return _medication_item(pm, product)


@router.delete("/patients/{patient_id}/medications/{patient_medication_id}", status_code=204)
async def remove_patient_medication(
    patient_id: str,
    patient_medication_id: str,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> None:
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự xóa thuốc trong hồ sơ của chính mình")

    pm = db.get(PatientMedication, patient_medication_id)
    if pm is None or pm.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy thuốc trong hồ sơ")

    db.delete(pm)
    db.commit()


# ---- Quét đơn thuốc bằng OCR (proxy sang ocr-service, xem ocr-service/README.md) ----

# Backend là phòng chờ duy nhất cho ảnh đơn thuốc: đọc theo chunk để chặn dung
# lượng SỚM (không await image.read() thẳng - ảnh 200MB không được đọc hết vào RAM
# trước khi bị từ chối), chuyển tiếp cho ocr-service qua httpx rồi bỏ bytes ngay -
# không bao giờ ghi xuống đĩa hay lưu DB (ảnh đơn thuốc lộ tên/tuổi/địa chỉ/chẩn đoán
# bệnh nhân). ocr-service không có xác thực/CORS/rate-limit nên KHÔNG được để
# browser gọi thẳng - route này đứng giữa, tái dùng JWT sẵn có của MediCheck.
_MAX_SCAN_IMAGE_BYTES = 10 * 1024 * 1024
_IMAGE_MAGIC_BYTES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "JPEG"),
    (b"\x89PNG\r\n\x1a\n", "PNG"),
)


async def _read_upload_capped(file: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"Ảnh vượt quá dung lượng cho phép ({limit // (1024 * 1024)} MB)",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _looks_like_image(data: bytes) -> bool:
    # Không tin filename/content_type client gửi - quyết định bằng chữ ký byte thật
    # của file. Kiểm định đầy đủ (giải mã pixel) do ocr-service tự làm bằng Pillow;
    # ở đây chỉ cần chặn sớm những request rõ ràng không phải ảnh.
    if any(data.startswith(magic) for magic, _fmt in _IMAGE_MAGIC_BYTES):
        return True
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _scanned_drug_from_medication(item: dict) -> ScannedDrug:
    candidates = item.get("candidates") or []
    # The OCR service returns low-score rows for audit/debug, but the review UI
    # must not present a random 0.72 match as a recommendation (real failures:
    # Thymorosin -> Intaxel, Diapan -> Dexipharm). Apply the same 0.75 boundary
    # already used by ``known`` to every displayed candidate.
    top_candidate = candidates[0] if candidates else None
    top = (
        top_candidate
        if top_candidate and float(top_candidate.get("score") or 0.0) >= 0.75
        else None
    )
    alternatives = [
        candidate["drug_name"]
        for candidate in candidates[1:3]
        if candidate.get("drug_name")
    ] if top else []
    return ScannedDrug(
        row_number=item.get("row_number"),
        ocr_text=item.get("ocr_drug_name") or item.get("ocr_text") or "",
        suggested_name=top.get("drug_name") if top else None,
        alternatives=alternatives,
        known=bool(top and top.get("score", 0.0) >= 0.75),
        score=float(top["score"]) if top and top.get("score") is not None else 0.0,
    )


# Số ứng viên bệnh trả về cho mỗi dòng chẩn đoán (1 đề xuất + phần còn lại là
# lựa chọn thay thế), giống cách xử lý tên thuốc.
_MAX_DISEASE_CANDIDATES = 4

# Tên bệnh in trên đơn thường dài và đủ ngữ cảnh ("Bệnh đái tháo đường không phụ
# thuộc insuline"), trong khi tên trong CSDL ngắn hơn - nên đây chỉ là ngưỡng loại
# bỏ rác, không phải ngưỡng "đúng". Người dùng vẫn phải tự chọn.
_ICD_PATTERN = re.compile(r"^[A-Z]\d{1,3}(?:\.\d+)?$")
_ICD_IN_CONDITION_PATTERN = re.compile(
    r"(?<![A-Z0-9])([A-Z]\d{1,3}(?:\.\d+)?)(?![A-Z0-9])",
    re.IGNORECASE,
)


def _condition_content_key(value: str) -> str:
    """Normalize one OCR condition and remove a leading ICD-like token.

    OCR service deliberately preserves the raw combined diagnosis for audit,
    while also returning its split conditions.  Removing only the leading code
    lets us prove that a split condition is already contained in that raw text,
    even when Paddle read I20 as 120.
    """
    key = normalize_disease_search_text(value)
    return re.sub(r"^(?:[a-z1il]\d{2}(?:\.\d+)?)\s*", "", key).strip()


def _diagnosis_is_summary_of_conditions(diagnosis: str, conditions: list[str]) -> bool:
    """True only when every split condition is represented by diagnosis."""
    if len(conditions) < 2:
        return False
    # OCR boxes may insert/remove whitespace at joins (``heviN40`` versus
    # ``hevi N40``). Whitespace carries no disease identity; compare compact
    # keys so a raw combined diagnosis is not appended as a duplicate UI card.
    diagnosis_key = re.sub(r"\s+", "", normalize_disease_search_text(diagnosis))
    content_keys = [
        re.sub(r"\s+", "", _condition_content_key(condition))
        for condition in conditions
    ]
    return all(len(key) >= 3 and key in diagnosis_key for key in content_keys)


def _scanned_diseases_from_payload(payload: dict, db: Session) -> list[ScannedDisease]:
    """Khớp chẩn đoán in trên đơn với bảng Disease.

    Nguồn dữ liệu là ``underlying_conditions``/``diagnosis`` do ocr-service tách ra
    từ đúng nhãn "Chẩn đoán"/"Bệnh kèm theo" - không suy diễn bệnh từ tên thuốc.
    """
    condition_texts: list[str] = list(payload.get("underlying_conditions") or [])
    diagnosis = (payload.get("diagnosis") or "").strip()
    # A multi-line diagnosis is returned twice on purpose by ocr-service: once
    # as the raw combined string for audit and once as individual conditions for
    # matching. Do not create a seventh duplicate UI card. A genuinely distinct
    # primary diagnosis is still appended when conditions came from a separate
    # "Bệnh kèm theo" field.
    if diagnosis and not _diagnosis_is_summary_of_conditions(diagnosis, condition_texts):
        condition_texts.append(diagnosis)
    if not condition_texts:
        return []

    # Mã ICD đứng riêng một phần tử, không phải tên bệnh để đem đi khớp. Ghép chúng
    # theo thứ tự vào các dòng chữ để hiển thị kèm ("Tăng huyết áp · I10").
    icd_codes = [
        code for code in (payload.get("icd_codes") or []) if _ICD_PATTERN.match(str(code).upper())
    ]
    embedded_codes = []
    for text in condition_texts:
        match = _ICD_IN_CONDITION_PATTERN.search(text)
        embedded_codes.append(match.group(1).upper() if match else None)
    # Positional fallback is safe only when no condition carries its own code
    # and both list lengths agree.  Otherwise one missed OCR code shifts every
    # following disease, as happened with E13/I15 on don1.
    use_positional_codes = (
        not any(embedded_codes) and len(icd_codes) == len(condition_texts)
    )

    all_diseases = db.query(Disease).all()
    results: list[ScannedDisease] = []
    seen: set[str] = set()
    for index, text in enumerate(condition_texts):
        text = " ".join(text.split()).strip(" ;:,-")
        # Bỏ dòng quá ngắn (nhiễu OCR) và dòng trùng nhau giữa diagnosis/kèm theo.
        key = text.casefold()
        if len(text) < 3 or key in seen:
            continue
        seen.add(key)

        ranked = match_diseases_in_phrase(all_diseases, text, _MAX_DISEASE_CANDIDATES)
        candidates = [
            DiseaseCandidate(id=disease.id, ten_benh=disease.ten_benh_vi or disease.ten_benh)
            for disease in ranked
        ]
        results.append(
            ScannedDisease(
                ocr_text=text,
                icd_code=(
                    embedded_codes[index]
                    or (icd_codes[index] if use_positional_codes else None)
                ),
                suggested=candidates[0] if candidates else None,
                alternatives=candidates[1:],
            )
        )
    return results


@router.post("/prescriptions/scan", response_model=ScanPrescriptionResponse)
async def scan_prescription(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScanPrescriptionResponse:
    settings = get_settings()

    data = await _read_upload_capped(image, _MAX_SCAN_IMAGE_BYTES)
    if not data or not _looks_like_image(data):
        raise HTTPException(
            status_code=400, detail="File tải lên không phải ảnh hợp lệ (jpg, png hoặc webp)"
        )

    # Modal-Key/Modal-Secret: bat buoc khi ocr-service chay tren Modal (proxy auth
    # token cua Modal, xem ocr-service/modal_app.py) - rong/khong gui khi chay
    # local qua docker-compose (ocr-service khong kiem tra header nay).
    ocr_headers = {}
    if settings.modal_key_id and settings.modal_key_secret:
        ocr_headers = {"Modal-Key": settings.modal_key_id, "Modal-Secret": settings.modal_key_secret}

    try:
        async with httpx.AsyncClient(timeout=settings.ocr_timeout_seconds) as http_client:
            ocr_response = await http_client.post(
                f"{settings.ocr_service_url}/api/v1/drug/recognize",
                files={"image": (image.filename or "prescription.jpg", data, image.content_type or "application/octet-stream")},
                headers=ocr_headers,
            )
    except httpx.RequestError:
        logger.exception("Không thể kết nối tới ocr-service")
        raise HTTPException(
            status_code=503,
            detail="Không thể kết nối tới dịch vụ quét đơn thuốc. Vui lòng thử lại sau hoặc nhập tên thuốc thủ công.",
        )

    if ocr_response.status_code != 200:
        logger.warning("ocr-service trả lỗi %s: %s", ocr_response.status_code, ocr_response.text[:500])
        raise HTTPException(
            status_code=503,
            detail="Dịch vụ quét đơn thuốc không xử lý được ảnh này. Vui lòng thử lại hoặc nhập tên thuốc thủ công.",
        )

    payload = ocr_response.json()
    medications = payload.get("medications") or []

    return ScanPrescriptionResponse(
        document_type=payload.get("document_type", "unknown"),
        drugs=[_scanned_drug_from_medication(item) for item in medications],
        diseases=_scanned_diseases_from_payload(payload, db),
    )


# ---- Đơn thuốc đã lưu trong hồ sơ (tab "Đơn thuốc của tôi") ----


@router.get("/patients/{patient_id}/prescriptions", response_model=list[PatientPrescriptionSummary])
async def list_patient_prescriptions(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PatientPrescriptionSummary]:
    _ensure_can_view_patient(current_user, patient_id, db)

    prescriptions = (
        db.query(PatientPrescription)
        .filter(PatientPrescription.patient_id == patient_id)
        .order_by(PatientPrescription.ngay_tao)
        .all()
    )
    if not prescriptions:
        # Chỉ tự tạo đơn mặc định + "nhận nuôi" thuốc mồ côi (nếu có) khi thật sự
        # chưa có đơn nào - tránh chạy lại SELECT kiểm tra tồn tại ở mọi lần load
        # trang, vì trong đại đa số trường hợp đơn mặc định đã tồn tại rồi (xem
        # _get_or_create_default_prescription).
        prescriptions = [_get_or_create_default_prescription(patient_id, db)]
    rows = (
        db.query(PatientMedication, Product)
        .join(Product, Product.id == PatientMedication.product_id)
        .filter(PatientMedication.patient_id == patient_id)
        .all()
    )
    meds_by_prescription: dict[str, list[MedicationItem]] = {}
    for pm, product in rows:
        meds_by_prescription.setdefault(pm.prescription_id, []).append(_medication_item(pm, product))

    return [
        PatientPrescriptionSummary(id=p.id, label=p.label, medications=meds_by_prescription.get(p.id, []))
        for p in prescriptions
    ]


@router.post(
    "/patients/{patient_id}/prescriptions",
    response_model=PatientPrescriptionSummary,
    status_code=201,
)
async def create_patient_prescription(
    patient_id: str,
    request: CreatePrescriptionRequest,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> PatientPrescriptionSummary:
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự tạo đơn thuốc cho chính mình")

    prescription = PatientPrescription(patient_id=patient_id, label=request.label.strip())
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return PatientPrescriptionSummary(id=prescription.id, label=prescription.label, medications=[])


@router.patch(
    "/patients/{patient_id}/prescriptions/{prescription_id}",
    response_model=PatientPrescriptionSummary,
)
async def rename_patient_prescription(
    patient_id: str,
    prescription_id: str,
    request: RenamePrescriptionRequest,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> PatientPrescriptionSummary:
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự sửa đơn thuốc của chính mình")

    prescription = db.get(PatientPrescription, prescription_id)
    if prescription is None or prescription.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn thuốc")

    prescription.label = request.label.strip()
    db.commit()
    db.refresh(prescription)

    rows = (
        db.query(PatientMedication, Product)
        .join(Product, Product.id == PatientMedication.product_id)
        .filter(PatientMedication.prescription_id == prescription.id)
        .all()
    )
    return PatientPrescriptionSummary(
        id=prescription.id,
        label=prescription.label,
        medications=[_medication_item(pm, product) for pm, product in rows],
    )


@router.delete("/patients/{patient_id}/prescriptions/{prescription_id}", status_code=204)
async def delete_patient_prescription(
    patient_id: str,
    prescription_id: str,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> None:
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự xóa đơn thuốc của chính mình")

    prescription = db.get(PatientPrescription, prescription_id)
    if prescription is None or prescription.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn thuốc")

    remaining = (
        db.query(PatientPrescription).filter(PatientPrescription.patient_id == patient_id).count()
    )
    if remaining <= 1:
        raise HTTPException(status_code=400, detail="Phải giữ lại ít nhất 1 đơn thuốc trong hồ sơ")

    db.query(PatientMedication).filter(PatientMedication.prescription_id == prescription_id).delete()
    db.delete(prescription)
    db.commit()


# ---- Hồ sơ cá nhân bệnh nhân (ngày sinh, bệnh nền) ----


def _disease_info(disease: Disease) -> DiseaseInfo:
    return DiseaseInfo(
        id=disease.id,
        ten_benh=disease.ten_benh,
        ten_benh_vi=disease.ten_benh_vi,
    )


def _patient_disease_context(
    patient_id: str, db: Session
) -> tuple[list[int] | None, str, list[dict]]:
    """Lấy condition chuẩn hóa cho lần kiểm tra và xác định chế độ fallback.

    Trả ``disease_ids=None`` khi chưa có condition để tầng lookup giữ nguyên
    hành vi cảnh báo tổng quát cũ. Snapshot được lưu cùng kết quả kiểm tra.
    """
    profile = db.query(PatientProfile).filter_by(user_id=patient_id).first()
    if profile is None:
        return None, "general_fallback", []

    diseases = (
        db.query(Disease)
        .join(PatientCondition, PatientCondition.disease_id == Disease.id)
        .filter(PatientCondition.patient_profile_id == profile.id)
        .order_by(func.lower(func.coalesce(Disease.ten_benh_vi, Disease.ten_benh)))
        .all()
    )
    if not diseases:
        return None, "general_fallback", []

    snapshot = [_disease_info(disease).model_dump() for disease in diseases]
    return [disease.id for disease in diseases], "personalized", snapshot


@router.get("/diseases/search", response_model=list[DiseaseInfo])
async def search_diseases(
    q: str = Query(..., min_length=1, max_length=255),
    limit: int = Query(default=20, ge=1, le=50),
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DiseaseInfo]:
    term = q.strip()
    if not term:
        raise HTTPException(status_code=422, detail="Từ khóa tìm kiếm bệnh không được để trống")

    # Danh mục DDInter hiện có quy mô nhỏ. Xếp hạng trong application giúp kết
    # quả nhất quán giữa PostgreSQL/SQLite mà không phụ thuộc unaccent/pg_trgm,
    # đồng thời hỗ trợ tên không dấu, tiền tố, bí danh và typo nhẹ.
    diseases = rank_disease_matches(db.query(Disease).all(), term, limit)
    return [_disease_info(disease) for disease in diseases]


@router.get("/patients/{patient_id}/conditions", response_model=list[DiseaseInfo])
async def get_patient_conditions(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DiseaseInfo]:
    _ensure_can_view_patient(current_user, patient_id, db)

    profile = db.query(PatientProfile).filter_by(user_id=patient_id).first()
    if profile is None:
        return []

    diseases = (
        db.query(Disease)
        .join(PatientCondition, PatientCondition.disease_id == Disease.id)
        .filter(PatientCondition.patient_profile_id == profile.id)
        .order_by(func.lower(func.coalesce(Disease.ten_benh_vi, Disease.ten_benh)))
        .all()
    )
    return [_disease_info(disease) for disease in diseases]


@router.put("/patients/{patient_id}/conditions", response_model=list[DiseaseInfo])
async def update_patient_conditions(
    patient_id: str,
    request: UpdatePatientConditionsRequest,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> list[DiseaseInfo]:
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự sửa bệnh nền của chính mình")

    # Khóa user trong transaction để hai request đồng thời không tạo hai PatientProfile.
    db.query(User).filter(User.id == patient_id).with_for_update().one()
    profile = db.query(PatientProfile).filter_by(user_id=patient_id).first()
    if profile is None:
        profile = PatientProfile(user_id=patient_id)
        db.add(profile)
        db.flush()

    disease_ids = list(dict.fromkeys(request.disease_ids))
    diseases = db.query(Disease).filter(Disease.id.in_(disease_ids)).all() if disease_ids else []
    found_ids = {disease.id for disease in diseases}
    missing_ids = [disease_id for disease_id in disease_ids if disease_id not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=422,
            detail={"message": "Có disease_id không tồn tại", "disease_ids": missing_ids},
        )

    db.query(PatientCondition).filter(
        PatientCondition.patient_profile_id == profile.id
    ).delete(synchronize_session=False)
    db.add_all(
        [
            PatientCondition(patient_profile_id=profile.id, disease_id=disease_id)
            for disease_id in disease_ids
        ]
    )
    db.commit()

    diseases_by_id = {disease.id: disease for disease in diseases}
    return [_disease_info(diseases_by_id[disease_id]) for disease_id in disease_ids]


@router.get("/patients/{patient_id}/profile", response_model=PatientProfileInfo)
async def get_patient_profile(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientProfileInfo:
    # Hồ sơ cá nhân chỉ được đọc trực tiếp bởi chính người dùng. Dược sĩ phải dùng
    # endpoint gắn với một yêu cầu review cụ thể, nơi quyền chia sẻ được kiểm tra
    # theo lựa chọn gui_kem_ho_so của chính yêu cầu đó.
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Người dùng chưa cho phép xem hồ sơ cá nhân")

    # current_user đã được nạp sẵn (cùng patient_id) lúc xác thực token, không cần
    # query lại User.
    user = current_user

    profile = db.query(PatientProfile).filter_by(user_id=patient_id).first()
    if profile is None:
        return PatientProfileInfo(ho_ten=user.ho_ten)

    return PatientProfileInfo(
        ho_ten=user.ho_ten,
        ngay_sinh=profile.ngay_sinh,
        gioi_tinh=profile.gioi_tinh,
        can_nang=profile.can_nang,
        chieu_cao=profile.chieu_cao,
        benh_nen_ghi_chu=profile.benh_nen_ghi_chu,
        di_ung_thuoc=profile.di_ung_thuoc,
        tinh_trang_khac=profile.tinh_trang_khac,
    )


@router.patch("/patients/{patient_id}/profile", response_model=PatientProfileInfo)
async def update_patient_profile(
    patient_id: str,
    request: UpdatePatientProfileRequest,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> PatientProfileInfo:
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự sửa hồ sơ của chính mình")

    # current_user đã được nạp sẵn (cùng patient_id) lúc xác thực token, không cần
    # query lại User.
    user = current_user
    if request.ho_ten:
        user.ho_ten = request.ho_ten

    profile = db.query(PatientProfile).filter_by(user_id=patient_id).first()
    if profile is None:
        profile = PatientProfile(user_id=patient_id)
        db.add(profile)

    profile.ngay_sinh = request.ngay_sinh
    profile.gioi_tinh = request.gioi_tinh
    profile.can_nang = request.can_nang
    profile.chieu_cao = request.chieu_cao
    profile.benh_nen_ghi_chu = request.benh_nen_ghi_chu
    profile.di_ung_thuoc = request.di_ung_thuoc
    profile.tinh_trang_khac = request.tinh_trang_khac

    # Dựng response từ giá trị đã có sẵn trong bộ nhớ trước khi commit - tránh 2
    # round-trip refresh() thừa (sau commit, SQLAlchemy sẽ tự expire object và phải
    # SELECT lại nếu đọc thuộc tính, refresh() tường minh cũng tốn round-trip y hệt).
    response = PatientProfileInfo(
        ho_ten=user.ho_ten,
        ngay_sinh=profile.ngay_sinh,
        gioi_tinh=profile.gioi_tinh,
        can_nang=profile.can_nang,
        chieu_cao=profile.chieu_cao,
        benh_nen_ghi_chu=profile.benh_nen_ghi_chu,
        di_ung_thuoc=profile.di_ung_thuoc,
        tinh_trang_khac=profile.tinh_trang_khac,
    )
    db.commit()
    return response


# ---- Kiểm tra tương tác (chạy agent) ----


@router.post("/medications/check", response_model=MedicationCheckResponse)
async def check_medications(
    request: MedicationCheckRequest,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> MedicationCheckResponse:
    result = dict(await agent.ainvoke({"raw_medications": request.medications, "audience": "patient"}))

    if result.get("error"):
        # guardrail_node chặn (thiếu nguồn trích dẫn) -> KHÔNG trả kết quả cho bệnh nhân.
        raise HTTPException(status_code=422, detail=result["error"])

    check = InteractionCheck(
        patient_id=current_user.id,
        ket_qua_json=result,
        co_canh_bao_nang=bool(result.get("has_severe")),
        co_chua_phan_loai=bool(result.get("has_unclassified")),
        thuoc_da_kiem_tra=_checked_drug_names(result),
    )
    db.add(check)
    db.commit()
    db.refresh(check)

    return MedicationCheckResponse(
        interaction_check_id=check.id,
        ranked_results=_strip_pharmacist_fields(result.get("ranked_results", [])),
        explanations=_strip_pharmacist_fields(result.get("explanations", [])),
        has_severe=result.get("has_severe", False),
        has_severe_disease_interaction=result.get("has_severe_disease_interaction", False),
        has_unclassified=result.get("has_unclassified", False),
    )


@router.post("/guest/medications/check", response_model=MedicationCheckResponse)
async def guest_check_medications(
    request: MedicationCheckRequest,
) -> MedicationCheckResponse:
    """Kiểm tra tương tác cho khách vãng lai; chỉ chạy phân tích, không lưu lịch sử."""
    result = dict(await agent.ainvoke({"raw_medications": request.medications, "audience": "patient"}))
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    return MedicationCheckResponse(
        interaction_check_id="guest-check",
        ranked_results=_strip_pharmacist_fields(result.get("ranked_results", [])),
        explanations=_strip_pharmacist_fields(result.get("explanations", [])),
        has_severe=result.get("has_severe", False),
        has_unclassified=result.get("has_unclassified", False),
    )


def _review_status(db: Session, check_id: str, pharmacist_id: str | None = None) -> str:
    query = db.query(PharmacistReview).filter_by(interaction_check_id=check_id)
    if pharmacist_id is not None:
        query = query.filter_by(pharmacist_id=pharmacist_id)
    review = query.first()
    return review.trang_thai_xac_nhan if review else "chua_xac_nhan"


def _review_note(db: Session, check_id: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Ghi chú + câu hỏi/câu trả lời dược sĩ để lại khi xác nhận (nếu có) + tên dược
    sĩ đó, để hiển thị lại cho bệnh nhân ở trang chi tiết lịch sử (xem
    get_patient_check_detail). Chỉ trả dữ liệu khi đã XÁC NHẬN xong và có ít nhất 1
    trong 2 (ghi chú chung hoặc câu trả lời) - câu hỏi luôn đi kèm câu trả lời, đúng
    yêu cầu gửi về bệnh nhân CÙNG LÚC khi dược sĩ xác nhận xong, không lộ câu hỏi
    một mình trước khi có câu trả lời."""
    review = db.query(PharmacistReview).filter_by(interaction_check_id=check_id).first()
    if not review or review.trang_thai_xac_nhan != "da_xac_nhan":
        return None, None, None, None
    if not review.ghi_chu and not review.cau_tra_loi:
        return None, None, None, None
    pharmacist = db.get(User, review.pharmacist_id) if review.pharmacist_id else None
    return (
        review.ghi_chu or None,
        pharmacist.ho_ten if pharmacist else None,
        review.cau_hoi or None,
        review.cau_tra_loi or None,
    )


def _checked_drug_names(result: dict | None) -> list[str]:
    """Return the drug names stored with a check, including older check formats."""
    payload = result or {}
    names = payload.get("checked_products", [])
    if not names:
        names = [
            product
            for prescription in payload.get("prescriptions", [])
            if isinstance(prescription, dict)
            for product in prescription.get("products", [])
        ]
    if not names:
        names = [
            medication.get("ten_chuan") or medication.get("ten_goc")
            for medication in payload.get("normalized_medications", [])
            if isinstance(medication, dict)
        ]
    return list(dict.fromkeys(
        name.strip() for name in names if isinstance(name, str) and name.strip()
    ))


@router.get("/patients/{patient_id}/checks", response_model=list[InteractionCheckSummary])
async def list_patient_checks(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InteractionCheckSummary]:
    """Lịch sử kiểm tra tương tác của bệnh nhân (FR-09) — bệnh nhân hoặc dược sĩ
    được phân công đều xem được danh sách tóm tắt này."""
    _ensure_can_view_patient(current_user, patient_id, db)

    # CHỈ select các cột nhẹ cần cho danh sách tóm tắt - KHÔNG động tới ket_qua_json
    # (thực đo trung bình ~260KB/dòng, có thể tới hàng chục MB cho cả danh sách).
    # thuoc_da_kiem_tra được lưu sẵn lúc TẠO check (xem check_products/check_medications)
    # thay vì trích lại từ ket_qua_json ở đây mỗi lần load trang Lịch sử/Trang chủ.
    checks = (
        db.query(
            InteractionCheck.id,
            InteractionCheck.thoi_gian_kiem_tra,
            InteractionCheck.co_canh_bao_nang,
            InteractionCheck.co_chua_phan_loai,
            InteractionCheck.thuoc_da_kiem_tra,
        )
        .filter_by(patient_id=patient_id)
        .order_by(InteractionCheck.thoi_gian_kiem_tra.desc())
        .all()
    )

    # Trước đây gọi _review_status() (1 SELECT riêng) cho MỖI check trong vòng lặp
    # bên dưới - N+1 query. Gộp lại thành 1 SELECT duy nhất lấy hết review liên
    # quan tới các check này, dựng map tra cứu O(1) thay vì round-trip DB riêng.
    check_ids = [c.id for c in checks]
    review_status_by_check: dict[str, str] = {}
    if check_ids:
        for review in (
            db.query(PharmacistReview)
            .filter(PharmacistReview.interaction_check_id.in_(check_ids))
            .all()
        ):
            review_status_by_check.setdefault(
                review.interaction_check_id, review.trang_thai_xac_nhan
            )

    return [
        InteractionCheckSummary(
            id=check.id,
            thoi_gian_kiem_tra=check.thoi_gian_kiem_tra,
            co_canh_bao_nang=check.co_canh_bao_nang,
            co_chua_phan_loai=check.co_chua_phan_loai,
            trang_thai_xac_nhan=review_status_by_check.get(check.id, "chua_xac_nhan"),
            # Rơi về [] cho các check tạo trước khi có cột này (chưa backfill) -
            # xem scripts/backfill_checked_drug_names.py.
            thuoc_da_kiem_tra=check.thuoc_da_kiem_tra or [],
        )
        for check in checks
    ]


@router.get("/patients/{patient_id}/checks/{check_id}", response_model=MedicationCheckResponse)
async def get_patient_check_detail(
    patient_id: str,
    check_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MedicationCheckResponse:
    """Xem lại 1 lần kiểm tra cũ - LUÔN ẩn xu_tri/thay_the (dùng /pharmacist/reviews/{id}
    cho vai trò dược sĩ cần xem đầy đủ)."""
    _ensure_can_view_patient(current_user, patient_id, db)

    check = db.get(InteractionCheck, check_id)
    if check is None or check.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy interaction_check")

    result = check.ket_qua_json or {}
    ghi_chu_duoc_si, ten_duoc_si_xac_nhan, cau_hoi_benh_nhan, cau_tra_loi_duoc_si = _review_note(db, check_id)
    return MedicationCheckResponse(
        interaction_check_id=check.id,
        is_personalized=result.get("is_personalized", False),
        ranked_results=_strip_pharmacist_fields(result.get("ranked_results", [])),
        explanations=_strip_pharmacist_fields(result.get("explanations", [])),
        has_severe=result.get("has_severe", False),
        has_severe_disease_interaction=result.get("has_severe_disease_interaction", False),
        has_unclassified=result.get("has_unclassified", False),
        unknown_products=result.get("unknown_products", []),
        no_interaction_data_products=result.get("no_interaction_data_products", []),
        checked_products=result.get("checked_products", []),
        prescriptions=result.get("prescriptions", []),
        product_explanations=_strip_pharmacist_fields(result.get("product_explanations", [])),
        overview=result.get("overview"),
        food_interactions=_strip_pharmacist_fields(result.get("food_interactions", [])),
        disease_interactions=_strip_pharmacist_fields(result.get("disease_interactions", [])),
        disease_interaction_scope=result.get(
            "disease_interaction_scope",
            "general_fallback" if "disease_interactions" in result else "general",
        ),
        patient_conditions_snapshot=result.get("patient_conditions_snapshot", []),
        canh_bao_thuc_pham_benh_nen=result.get("canh_bao_thuc_pham_benh_nen"),
        ghi_chu_duoc_si=ghi_chu_duoc_si,
        ten_duoc_si_xac_nhan=ten_duoc_si_xac_nhan,
        cau_hoi_benh_nhan=cau_hoi_benh_nhan,
        cau_tra_loi_duoc_si=cau_tra_loi_duoc_si,
    )

@router.delete("/patients/{patient_id}/checks", status_code=204)
async def delete_all_patient_checks(
    patient_id: str,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> None:
    """Xóa tất cả lịch sử tra cứu của bệnh nhân."""
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự xóa lịch sử của chính mình")

    # Xóa các PharmacistReview liên quan trước để tránh lỗi khóa ngoại
    checks = db.query(InteractionCheck).filter_by(patient_id=patient_id).all()
    check_ids = [c.id for c in checks]
    if check_ids:
        db.query(PharmacistReview).filter(PharmacistReview.interaction_check_id.in_(check_ids)).delete(synchronize_session=False)
        db.query(InteractionCheck).filter_by(patient_id=patient_id).delete(synchronize_session=False)
        db.commit()


@router.delete("/patients/{patient_id}/checks/{check_id}", status_code=204)
async def delete_patient_check(
    patient_id: str,
    check_id: str,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> None:
    """Xóa 1 lịch sử tra cứu cụ thể."""
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự xóa lịch sử của chính mình")

    check = db.get(InteractionCheck, check_id)
    if check is None or check.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy lịch sử tra cứu")

    # Xóa PharmacistReview liên quan trước
    db.query(PharmacistReview).filter_by(interaction_check_id=check_id).delete(synchronize_session=False)
    db.delete(check)
    db.commit()


# ---- Dược sĩ ----


@router.get("/pharmacists", response_model=list[PharmacistSummary])
async def list_pharmacists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PharmacistSummary]:
    pharmacists = db.query(User).filter_by(vai_tro="pharmacist", account_status="active").all()
    return [
        PharmacistSummary(
            id=p.id,
            ho_ten=p.ho_ten,
            noi_cong_tac=p.noi_cong_tac,
            mo_ta_ngan=p.mo_ta_ngan,
        )
        for p in pharmacists
    ]


@router.post("/checks/{check_id}/pharmacists/{pharmacist_id}/request_review", status_code=201)
async def request_review(
    check_id: str,
    pharmacist_id: str,
    request: RequestReviewRequest = RequestReviewRequest(),
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
):
    check = db.get(InteractionCheck, check_id)
    if check is None or check.patient_id != current_user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy lịch sử tra cứu của bạn")

    pharmacist = db.get(User, pharmacist_id)
    if pharmacist is None or pharmacist.vai_tro != "pharmacist" or pharmacist.account_status != "active":
        raise HTTPException(status_code=404, detail="Không tìm thấy dược sĩ")

    review = db.query(PharmacistReview).filter_by(
        interaction_check_id=check_id, pharmacist_id=pharmacist_id
    ).first()

    if not review:
        review = PharmacistReview(
            interaction_check_id=check_id,
            pharmacist_id=pharmacist_id,
            trang_thai_xac_nhan="cho_xac_nhan",
            gui_kem_ho_so=request.gui_kem_ho_so,
            ten_nguoi_duoc_kiem_tra=request.ten_nguoi_duoc_kiem_tra,
            ngay_sinh_nhap_tay=request.ngay_sinh_nhap_tay,
            ghi_chu_nhap_tay=request.ghi_chu_nhap_tay,
            cau_hoi=request.cau_hoi,
        )
        db.add(review)
        db.commit()
    return {"message": "Đã gửi yêu cầu xét duyệt thành công"}


@router.get("/pharmacist/requests", response_model=list[ReviewRequestSummary])
async def list_pharmacist_requests(
    current_user: User = Depends(require_role("pharmacist")),
    db: Session = Depends(get_db),
) -> list[ReviewRequestSummary]:
    reviews = (
        db.query(PharmacistReview, InteractionCheck, User)
        .join(InteractionCheck, PharmacistReview.interaction_check_id == InteractionCheck.id)
        .join(User, InteractionCheck.patient_id == User.id)
        .filter(PharmacistReview.pharmacist_id == current_user.id)
        .all()
    )

    results = []
    for review, check, patient in reviews:
        results.append(
            ReviewRequestSummary(
                check_id=check.id,
                patient_id=patient.id,
                # Không để tên tài khoản vô tình trở thành một phần bắt buộc của
                # kết quả tra tương tác. Chỉ hiện danh tính khi người dùng đồng ý
                # chia sẻ hồ sơ (hoặc đã chủ động nhập tên theo API cũ).
                patient_name=(
                    patient.ho_ten
                    if review.gui_kem_ho_so
                    else review.ten_nguoi_duoc_kiem_tra or "Người dùng ẩn danh"
                ),
                thoi_gian_kiem_tra=check.thoi_gian_kiem_tra,
                co_canh_bao_nang=check.co_canh_bao_nang,
                trang_thai_xac_nhan=review.trang_thai_xac_nhan,
                gui_kem_ho_so=review.gui_kem_ho_so or False,
                ten_nguoi_duoc_kiem_tra=review.ten_nguoi_duoc_kiem_tra,
                ngay_sinh_nhap_tay=review.ngay_sinh_nhap_tay,
                ghi_chu_nhap_tay=review.ghi_chu_nhap_tay,
                ghi_chu=review.ghi_chu,
                thoi_gian_xac_nhan=review.thoi_gian_xac_nhan,
                cau_hoi=review.cau_hoi,
                cau_tra_loi=review.cau_tra_loi,
            )
        )

    # Sort: pending severe -> pending -> resolved
    def _sort_key(req: ReviewRequestSummary):
        score = 0
        if req.trang_thai_xac_nhan != "da_xac_nhan":
            score += 10
        if req.co_canh_bao_nang:
            score += 5
        return (score, req.thoi_gian_kiem_tra.timestamp())

    results.sort(key=_sort_key, reverse=True)
    return results


@router.get(
    "/pharmacist/reviews/{check_id}/patient-profile",
    response_model=PatientProfileInfo,
)
async def get_shared_patient_profile(
    check_id: str,
    current_user: User = Depends(require_role("pharmacist")),
    db: Session = Depends(get_db),
) -> PatientProfileInfo:
    """Trả hồ sơ chỉ khi yêu cầu review cụ thể có sự đồng ý chia sẻ."""

    review = (
        db.query(PharmacistReview)
        .filter_by(interaction_check_id=check_id, pharmacist_id=current_user.id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=403, detail="Bạn không được yêu cầu xem xét lần kiểm tra này")
    if not review.gui_kem_ho_so:
        raise HTTPException(status_code=403, detail="Người dùng không chia sẻ hồ sơ cá nhân")

    check = db.get(InteractionCheck, check_id)
    if check is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần kiểm tra")

    patient = db.get(User, check.patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    profile = db.query(PatientProfile).filter_by(user_id=patient.id).first()
    if profile is None:
        return PatientProfileInfo(ho_ten=patient.ho_ten)

    return PatientProfileInfo(
        ho_ten=patient.ho_ten,
        ngay_sinh=profile.ngay_sinh,
        gioi_tinh=profile.gioi_tinh,
        can_nang=profile.can_nang,
        chieu_cao=profile.chieu_cao,
        benh_nen_ghi_chu=profile.benh_nen_ghi_chu,
        di_ung_thuoc=profile.di_ung_thuoc,
        tinh_trang_khac=profile.tinh_trang_khac,
    )


def _ensure_pharmacist_can_review(current_user: User, check: InteractionCheck, db: Session) -> None:
    review = (
        db.query(PharmacistReview)
        .filter_by(interaction_check_id=check.id, pharmacist_id=current_user.id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=403, detail="Bạn không được yêu cầu xem xét lần kiểm tra này")


@router.get("/pharmacist/reviews/{interaction_check_id}")
async def get_interaction_check_detail(
    interaction_check_id: str,
    current_user: User = Depends(require_role("pharmacist")),
    db: Session = Depends(get_db),
) -> dict:
    """Chi tiết đầy đủ 1 lần kiểm tra (bao gồm xu_tri/thay_the - chỉ dược sĩ xem)."""
    check = db.get(InteractionCheck, interaction_check_id)
    if check is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy interaction_check")

    _ensure_pharmacist_can_review(current_user, check, db)
    return check.ket_qua_json


@router.post("/pharmacist/reviews", response_model=PharmacistReviewResponse)
async def submit_pharmacist_review(
    request: PharmacistReviewRequest,
    current_user: User = Depends(require_role("pharmacist")),
    db: Session = Depends(get_db),
) -> PharmacistReviewResponse:
    check = db.get(InteractionCheck, request.interaction_check_id)
    if check is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy interaction_check")

    review = (
        db.query(PharmacistReview)
        .filter_by(interaction_check_id=check.id, pharmacist_id=current_user.id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=403, detail="Bạn không được yêu cầu xem xét lần kiểm tra này")

    review.ghi_chu = request.ghi_chu
    review.cau_tra_loi = request.cau_tra_loi
    review.trang_thai_xac_nhan = "da_xac_nhan"
    review.thoi_gian_xac_nhan = datetime.utcnow()
    db.add(Notification(
        patient_id=check.patient_id,
        pharmacist_review_id=review.id,
        noi_dung=(
            f"Dược sĩ {current_user.ho_ten} đã xác nhận yêu cầu tra cứu ngày "
            f"{check.thoi_gian_kiem_tra:%d/%m/%Y}."
        ),
    ))
    db.commit()
    db.refresh(review)

    return PharmacistReviewResponse(
        id=review.id,
        interaction_check_id=review.interaction_check_id,
        trang_thai_xac_nhan=review.trang_thai_xac_nhan,
        ghi_chu=review.ghi_chu or "",
        cau_tra_loi=review.cau_tra_loi,
    )


# ---- Hồ sơ cá nhân dược sĩ ----


@router.get("/pharmacists/{pharmacist_id}/profile", response_model=PharmacistProfileInfo)
async def get_pharmacist_profile(
    pharmacist_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PharmacistProfileInfo:
    pharmacist = db.get(User, pharmacist_id)
    if pharmacist is None or pharmacist.vai_tro != "pharmacist":
        raise HTTPException(status_code=404, detail="Không tìm thấy dược sĩ")
    return PharmacistProfileInfo(
        ho_ten=pharmacist.ho_ten,
        noi_cong_tac=pharmacist.noi_cong_tac,
        mo_ta_ngan=pharmacist.mo_ta_ngan,
    )


@router.patch("/pharmacists/{pharmacist_id}/profile", response_model=PharmacistProfileInfo)
async def update_pharmacist_profile(
    pharmacist_id: str,
    request: UpdatePharmacistProfileRequest,
    current_user: User = Depends(require_role("pharmacist")),
    db: Session = Depends(get_db),
) -> PharmacistProfileInfo:
    if current_user.id != pharmacist_id:
        raise HTTPException(status_code=403, detail="Chỉ tự sửa hồ sơ của chính mình")

    if request.ho_ten:
        current_user.ho_ten = request.ho_ten
    current_user.noi_cong_tac = request.noi_cong_tac
    current_user.mo_ta_ngan = request.mo_ta_ngan
    db.commit()
    db.refresh(current_user)

    return PharmacistProfileInfo(
        ho_ten=current_user.ho_ten,
        noi_cong_tac=current_user.noi_cong_tac,
        mo_ta_ngan=current_user.mo_ta_ngan,
    )


# ---- Thông báo ----


@router.get("/patients/{patient_id}/notifications", response_model=list[NotificationItem])
async def list_patient_notifications(
    patient_id: str,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> list[NotificationItem]:
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự xem thông báo của chính mình")

    rows = (
        db.query(Notification, PharmacistReview)
        .outerjoin(PharmacistReview, Notification.pharmacist_review_id == PharmacistReview.id)
        .filter(Notification.patient_id == patient_id)
        .order_by(Notification.thoi_gian_tao.desc())
        .all()
    )
    return [
        NotificationItem(
            id=n.id,
            noi_dung=n.noi_dung,
            da_doc=n.da_doc,
            thoi_gian_tao=n.thoi_gian_tao,
            interaction_check_id=review.interaction_check_id if review else None,
        )
        for n, review in rows
    ]


@router.post("/patients/{patient_id}/notifications/{notification_id}/read", status_code=204)
async def mark_notification_read(
    patient_id: str,
    notification_id: str,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> None:
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự cập nhật thông báo của chính mình")

    notification = db.get(Notification, notification_id)
    if notification is None or notification.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo")

    notification.da_doc = True
    db.commit()


@router.post("/pharmacist/medications/check", response_model=MedicationCheckResponse)
async def check_medications_as_pharmacist(
    request: MedicationCheckRequest,
    current_user: User = Depends(require_role("pharmacist")),
) -> MedicationCheckResponse:
    """Công cụ tra cứu tương tác độc lập cho dược sĩ - không gắn bệnh nhân nào,
    không lưu lịch sử, và KHÔNG ẩn xu_tri/thay_the (dược sĩ được xem đầy đủ)."""
    result = dict(await agent.ainvoke({"raw_medications": request.medications, "audience": "pharmacist"}))
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    return MedicationCheckResponse(
        interaction_check_id="pharmacist-lookup",
        ranked_results=result.get("ranked_results", []),
        explanations=result.get("explanations", []),
        has_severe=result.get("has_severe", False),
        has_unclassified=result.get("has_unclassified", False),
    )
