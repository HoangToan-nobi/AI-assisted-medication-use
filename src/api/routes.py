from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.agents.graph import agent
from src.api.deps import get_current_user, require_role
from src.db.models import (
    InteractionCheck,
    Medication,
    MedicationAlias,
    Notification,
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
    AddMedicationRequest,
    AddProductRequest,
    AuthResponse,
    ChatRequest,
    ChatResponse,
    CreatePrescriptionRequest,
    InteractionCheckSummary,
    LoginRequest,
    MedicationCheckRequest,
    MedicationCheckResponse,
    MedicationItem,
    MedicationSearchResult,
    NotificationItem,
    PatientPrescriptionSummary,
    PatientProfileInfo,
    PharmacistProfileInfo,
    PrescriptionInput,
    RenamePrescriptionRequest,
    RequestReviewRequest,
    ReviewRequestSummary,
    PharmacistSummary,
    PharmacistReviewRequest,
    PharmacistReviewResponse,
    ProductCheckRequest,
    ProductSearchResult,
    RegisterRequest,
    UpdatePatientProfileRequest,
    UpdatePharmacistProfileRequest,
)
from src.services.auth import create_token, hash_password, verify_password
from src.services.rollup_explain import (
    build_overview_explanation,
    build_prescription_edges,
    build_prescription_explanations,
    build_product_edges,
    build_product_explanations,
    filter_cross_prescription_edges,
)

router = APIRouter()

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
    if current_user.vai_tro == "pharmacist":
        review = (
            db.query(PharmacistReview)
            .join(InteractionCheck, PharmacistReview.interaction_check_id == InteractionCheck.id)
            .filter(
                PharmacistReview.pharmacist_id == current_user.id,
                InteractionCheck.patient_id == patient_id
            )
            .first()
        )
        if review is not None:
            return
    raise HTTPException(status_code=403, detail="Không có quyền xem thuốc của bệnh nhân này")


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


# ---- Auth ----


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
async def register(request: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    """Đăng ký tài khoản theo vai trò (FR-01). Không có trong bảng API gốc GD2 nhưng
    bắt buộc phải có để /auth/login hoạt động được."""
    existing = db.query(User).filter_by(email=request.email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email đã được sử dụng")

    user = User(
        ho_ten=request.ho_ten,
        email=request.email,
        mat_khau_hash=hash_password(request.mat_khau),
        vai_tro=request.vai_tro,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id, user.vai_tro)
    return AuthResponse(access_token=token, vai_tro=user.vai_tro, user_id=user.id, ho_ten=user.ho_ten)


@router.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(User).filter_by(email=request.email).first()
    if user is None or not verify_password(request.mat_khau, user.mat_khau_hash):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")

    token = create_token(user.id, user.vai_tro)
    return AuthResponse(access_token=token, vai_tro=user.vai_tro, user_id=user.id, ho_ten=user.ho_ten)


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
    prescriptions: list[PrescriptionInput], db: Session, for_pharmacist: bool = False
) -> tuple[dict, list[str], list[str]]:
    """Dùng chung cho patient/guest/pharmacist: resolve tên thuốc -> hoạt chất, chạy agent
    hiện có, gắn tên thuốc (biệt dược) vào kết quả, rồi tự tính + sinh giải thích riêng
    cho cấp thuốc. Cả 2 luồng đều sinh overview (tóm tắt tổng quan) - khác nhau ở
    audience truyền vào build_overview_explanation (giọng thân thiện cho bệnh nhân,
    khoa học/chuyên nghiệp cho dược sĩ).

    for_pharmacist=True (công cụ tra cứu độc lập của dược sĩ, vẫn giữ drill-down đầy
    đủ): sinh thêm prescription_explanations (cấp đơn) khi có từ 2 đơn trở lên.
    for_pharmacist=False (luồng bệnh nhân): KHÔNG sinh prescription_explanations
    (không còn UI nào dùng tới, tránh tốn LLM call vô ích).
    """
    flat_products, origins_by_input = _flatten_prescriptions(prescriptions)
    ingredient_names, ingredient_to_products, unknown, no_data, canonical_by_input = _resolve_products(
        flat_products, db
    )

    result = dict(await agent.ainvoke({"raw_medications": ingredient_names}))
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
    result["product_explanations"] = await build_product_explanations(overview_product_edges)

    if for_pharmacist and len(prescriptions) > 1:
        labels = [p.label for p in prescriptions]
        prescription_edges = build_prescription_edges(product_edges, product_origins)
        result["prescription_explanations"] = await build_prescription_explanations(
            prescription_edges, labels
        )
    else:
        result["prescription_explanations"] = []

    result["overview"] = await build_overview_explanation(
        overview_product_edges,
        result["product_explanations"],
        audience="pharmacist" if for_pharmacist else "patient",
    )

    return result, unknown, no_data


@router.post("/products/check", response_model=MedicationCheckResponse)
async def check_products(
    request: ProductCheckRequest,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> MedicationCheckResponse:
    result, unknown, no_data = await _run_product_check(request.prescriptions, db)

    check = InteractionCheck(
        patient_id=current_user.id,
        ket_qua_json=result,
        co_canh_bao_nang=bool(result.get("has_severe")),
        co_chua_phan_loai=bool(result.get("has_unclassified")),
    )
    db.add(check)
    db.commit()
    db.refresh(check)

    return MedicationCheckResponse(
        interaction_check_id=check.id,
        ranked_results=_strip_pharmacist_fields(result.get("ranked_results", [])),
        explanations=_strip_pharmacist_fields(result.get("explanations", [])),
        has_severe=result.get("has_severe", False),
        has_unclassified=result.get("has_unclassified", False),
        unknown_products=unknown,
        no_interaction_data_products=no_data,
        product_explanations=_strip_pharmacist_fields(result.get("product_explanations", [])),
        prescription_explanations=_strip_pharmacist_fields(result.get("prescription_explanations", [])),
        overview=result.get("overview"),
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
        has_unclassified=result.get("has_unclassified", False),
        unknown_products=unknown,
        no_interaction_data_products=no_data,
        product_explanations=_strip_pharmacist_fields(result.get("product_explanations", [])),
        prescription_explanations=_strip_pharmacist_fields(result.get("prescription_explanations", [])),
        overview=result.get("overview"),
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
        has_unclassified=result.get("has_unclassified", False),
        unknown_products=unknown,
        no_interaction_data_products=no_data,
        product_explanations=result.get("product_explanations", []),
        prescription_explanations=result.get("prescription_explanations", []),
        overview=result.get("overview"),
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


# ---- Đơn thuốc đã lưu trong hồ sơ (tab "Đơn thuốc của tôi") ----


@router.get("/patients/{patient_id}/prescriptions", response_model=list[PatientPrescriptionSummary])
async def list_patient_prescriptions(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PatientPrescriptionSummary]:
    _ensure_can_view_patient(current_user, patient_id, db)

    # Tự tạo đơn mặc định + "nhận nuôi" thuốc mồ côi (nếu có) ở lần load đầu tiên -
    # xem _get_or_create_default_prescription.
    _get_or_create_default_prescription(patient_id, db)

    prescriptions = (
        db.query(PatientPrescription)
        .filter(PatientPrescription.patient_id == patient_id)
        .order_by(PatientPrescription.ngay_tao)
        .all()
    )
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


@router.get("/patients/{patient_id}/profile", response_model=PatientProfileInfo)
async def get_patient_profile(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientProfileInfo:
    _ensure_can_view_patient(current_user, patient_id, db)

    user = db.query(User).filter_by(id=patient_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
        
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

    user = db.query(User).filter_by(id=patient_id).first()
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
    
    db.commit()
    db.refresh(profile)
    db.refresh(user)

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


# ---- Kiểm tra tương tác (chạy agent) ----


@router.post("/medications/check", response_model=MedicationCheckResponse)
async def check_medications(
    request: MedicationCheckRequest,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> MedicationCheckResponse:
    result = dict(await agent.ainvoke({"raw_medications": request.medications}))

    if result.get("error"):
        # guardrail_node chặn (thiếu nguồn trích dẫn) -> KHÔNG trả kết quả cho bệnh nhân.
        raise HTTPException(status_code=422, detail=result["error"])

    check = InteractionCheck(
        patient_id=current_user.id,
        ket_qua_json=result,
        co_canh_bao_nang=bool(result.get("has_severe")),
        co_chua_phan_loai=bool(result.get("has_unclassified")),
    )
    db.add(check)
    db.commit()
    db.refresh(check)

    return MedicationCheckResponse(
        interaction_check_id=check.id,
        ranked_results=_strip_pharmacist_fields(result.get("ranked_results", [])),
        explanations=_strip_pharmacist_fields(result.get("explanations", [])),
        has_severe=result.get("has_severe", False),
        has_unclassified=result.get("has_unclassified", False),
    )


@router.post("/guest/medications/check", response_model=MedicationCheckResponse)
async def guest_check_medications(
    request: MedicationCheckRequest,
) -> MedicationCheckResponse:
    """Kiểm tra tương tác cho khách vãng lai; chỉ chạy phân tích, không lưu lịch sử."""
    result = dict(await agent.ainvoke({"raw_medications": request.medications}))
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


def _review_note(db: Session, check_id: str) -> tuple[str | None, str | None]:
    """Ghi chú dược sĩ để lại khi xác nhận (nếu có) + tên dược sĩ đó, để hiển thị lại
    cho bệnh nhân ở trang chi tiết lịch sử (xem get_patient_check_detail)."""
    review = db.query(PharmacistReview).filter_by(interaction_check_id=check_id).first()
    if not review or not review.ghi_chu:
        return None, None
    pharmacist = db.get(User, review.pharmacist_id) if review.pharmacist_id else None
    return review.ghi_chu, pharmacist.ho_ten if pharmacist else None


@router.get("/patients/{patient_id}/checks", response_model=list[InteractionCheckSummary])
async def list_patient_checks(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InteractionCheckSummary]:
    """Lịch sử kiểm tra tương tác của bệnh nhân (FR-09) — bệnh nhân hoặc dược sĩ
    được phân công đều xem được danh sách tóm tắt này."""
    _ensure_can_view_patient(current_user, patient_id, db)

    checks = (
        db.query(InteractionCheck)
        .filter_by(patient_id=patient_id)
        .order_by(InteractionCheck.thoi_gian_kiem_tra.desc())
        .all()
    )
    return [
        InteractionCheckSummary(
            id=check.id,
            thoi_gian_kiem_tra=check.thoi_gian_kiem_tra,
            co_canh_bao_nang=check.co_canh_bao_nang,
            co_chua_phan_loai=check.co_chua_phan_loai,
            trang_thai_xac_nhan=_review_status(db, check.id),
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
    ghi_chu_duoc_si, ten_duoc_si_xac_nhan = _review_note(db, check_id)
    return MedicationCheckResponse(
        interaction_check_id=check.id,
        ranked_results=_strip_pharmacist_fields(result.get("ranked_results", [])),
        explanations=_strip_pharmacist_fields(result.get("explanations", [])),
        has_severe=result.get("has_severe", False),
        has_unclassified=result.get("has_unclassified", False),
        unknown_products=result.get("unknown_products", []),
        no_interaction_data_products=result.get("no_interaction_data_products", []),
        product_explanations=_strip_pharmacist_fields(result.get("product_explanations", [])),
        prescription_explanations=_strip_pharmacist_fields(result.get("prescription_explanations", [])),
        overview=result.get("overview"),
        ghi_chu_duoc_si=ghi_chu_duoc_si,
        ten_duoc_si_xac_nhan=ten_duoc_si_xac_nhan,
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
    pharmacists = db.query(User).filter_by(vai_tro="pharmacist").all()
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
    if pharmacist is None or pharmacist.vai_tro != "pharmacist":
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
                patient_name=patient.ho_ten,
                thoi_gian_kiem_tra=check.thoi_gian_kiem_tra,
                co_canh_bao_nang=check.co_canh_bao_nang,
                trang_thai_xac_nhan=review.trang_thai_xac_nhan,
                gui_kem_ho_so=review.gui_kem_ho_so or False,
                ten_nguoi_duoc_kiem_tra=review.ten_nguoi_duoc_kiem_tra,
                ngay_sinh_nhap_tay=review.ngay_sinh_nhap_tay,
                ghi_chu_nhap_tay=review.ghi_chu_nhap_tay,
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
    result = dict(await agent.ainvoke({"raw_medications": request.medications}))
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    return MedicationCheckResponse(
        interaction_check_id="pharmacist-lookup",
        ranked_results=result.get("ranked_results", []),
        explanations=result.get("explanations", []),
        has_severe=result.get("has_severe", False),
        has_unclassified=result.get("has_unclassified", False),
    )
