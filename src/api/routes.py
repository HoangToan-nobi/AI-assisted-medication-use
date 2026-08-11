from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.agents.graph import agent
from src.api.deps import get_current_user, require_role
from src.db.models import (
    InteractionCheck,
    Medication,
    MedicationAlias,
    PatientMedication,
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
    InteractionCheckSummary,
    LoginRequest,
    MedicationCheckRequest,
    MedicationCheckResponse,
    MedicationItem,
    MedicationSearchResult,
    PatientProfileInfo,
    ReviewRequestSummary,
    PharmacistSummary,
    PharmacistReviewRequest,
    PharmacistReviewResponse,
    ProductCheckRequest,
    ProductSearchResult,
    RegisterRequest,
    UpdatePatientProfileRequest,
)
from src.services.auth import create_token, hash_password, verify_password

router = APIRouter()

# Field chỉ dành cho vai trò dược sĩ (GD6 mục 7.2) - không trả cho bệnh nhân.
_PHARMACIST_ONLY_FIELDS = {"xu_tri", "thay_the_a", "thay_the_b"}


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


def _brand_label(hoat_chat_name: str | None, ingredient_to_products: dict[str, list[str]]) -> str | None:
    if not hoat_chat_name:
        return hoat_chat_name
    brands = ingredient_to_products.get(hoat_chat_name)
    if not brands:
        return hoat_chat_name
    unique_brands = list(dict.fromkeys(brands))
    return f"{'/'.join(unique_brands)} (hoạt chất: {hoat_chat_name})"


def _enrich_with_brand_names(items: list[dict], ingredient_to_products: dict[str, list[str]]) -> list[dict]:
    enriched = []
    for item in items:
        item = dict(item)
        item["thuoc_a"] = _brand_label(item.get("thuoc_a"), ingredient_to_products)
        item["thuoc_b"] = _brand_label(item.get("thuoc_b"), ingredient_to_products)
        enriched.append(item)
    return enriched


def _resolve_products(
    product_names: list[str], db: Session
) -> tuple[list[str], dict[str, list[str]], list[str], list[str]]:
    """Quy đổi tên thuốc -> danh sách hoạt chất (dedup, exact-match Product.ten_thuoc) để
    đưa vào agent hiện có (KHÔNG đổi gì trong src/agents/ - agent vẫn nhận tên hoạt chất).

    Trả về (ingredient_names, ingredient_to_products, unknown_products, no_interaction_data_products).
    """
    ingredient_names: list[str] = []
    ingredient_to_products: dict[str, list[str]] = {}
    unknown_products: list[str] = []
    no_interaction_data_products: list[str] = []
    seen: set[str] = set()

    for name in product_names:
        product = (
            db.query(Product).filter(func.lower(Product.ten_thuoc) == name.strip().lower()).first()
        )
        if product is None:
            unknown_products.append(name)
            continue

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

    return ingredient_names, ingredient_to_products, unknown_products, no_interaction_data_products


async def _run_product_check(products: list[str], db: Session) -> tuple[dict, list[str], list[str]]:
    """Dùng chung cho patient/guest/pharmacist: resolve tên thuốc -> hoạt chất, chạy agent
    hiện có, rồi gắn tên thuốc (biệt dược) vào kết quả để hiển thị."""
    ingredient_names, ingredient_to_products, unknown, no_data = _resolve_products(products, db)

    result = dict(await agent.ainvoke({"raw_medications": ingredient_names}))
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    result["ranked_results"] = _enrich_with_brand_names(
        result.get("ranked_results", []), ingredient_to_products
    )
    result["explanations"] = _enrich_with_brand_names(
        result.get("explanations", []), ingredient_to_products
    )
    return result, unknown, no_data


@router.post("/products/check", response_model=MedicationCheckResponse)
async def check_products(
    request: ProductCheckRequest,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> MedicationCheckResponse:
    result, unknown, no_data = await _run_product_check(request.products, db)

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
    )


@router.post("/guest/products/check", response_model=MedicationCheckResponse)
async def guest_check_products(
    request: ProductCheckRequest,
    db: Session = Depends(get_db),
) -> MedicationCheckResponse:
    result, unknown, no_data = await _run_product_check(request.products, db)
    return MedicationCheckResponse(
        interaction_check_id="guest-check",
        ranked_results=_strip_pharmacist_fields(result.get("ranked_results", [])),
        explanations=_strip_pharmacist_fields(result.get("explanations", [])),
        has_severe=result.get("has_severe", False),
        has_unclassified=result.get("has_unclassified", False),
        unknown_products=unknown,
        no_interaction_data_products=no_data,
    )


@router.post("/pharmacist/products/check", response_model=MedicationCheckResponse)
async def check_products_as_pharmacist(
    request: ProductCheckRequest,
    current_user: User = Depends(require_role("pharmacist")),
    db: Session = Depends(get_db),
) -> MedicationCheckResponse:
    """Công cụ tra cứu độc lập cho dược sĩ - không lưu lịch sử, KHÔNG ẩn xu_tri/thay_the."""
    result, unknown, no_data = await _run_product_check(request.products, db)
    return MedicationCheckResponse(
        interaction_check_id="pharmacist-lookup",
        ranked_results=result.get("ranked_results", []),
        explanations=result.get("explanations", []),
        has_severe=result.get("has_severe", False),
        has_unclassified=result.get("has_unclassified", False),
        unknown_products=unknown,
        no_interaction_data_products=no_data,
    )


# ---- Hồ sơ thuốc bệnh nhân ----


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
    return [
        MedicationItem(
            id=pm.id,
            product_id=product.id,
            ten_thuoc=product.ten_thuoc,
            ngay_bat_dau=pm.ngay_bat_dau,
            ngay_ket_thuc=pm.ngay_ket_thuc,
        )
        for pm, product in rows
    ]


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

    pm = PatientMedication(
        patient_id=patient_id,
        product_id=product.id,
        ngay_bat_dau=date.today(),
    )
    db.add(pm)
    db.commit()
    db.refresh(pm)

    return MedicationItem(
        id=pm.id,
        product_id=product.id,
        ten_thuoc=product.ten_thuoc,
        ngay_bat_dau=pm.ngay_bat_dau,
        ngay_ket_thuc=None,
    )


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
    return MedicationCheckResponse(
        interaction_check_id=check.id,
        ranked_results=_strip_pharmacist_fields(result.get("ranked_results", [])),
        explanations=_strip_pharmacist_fields(result.get("explanations", [])),
        has_severe=result.get("has_severe", False),
        has_unclassified=result.get("has_unclassified", False),
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
        )
        for p in pharmacists
    ]


@router.post("/checks/{check_id}/pharmacists/{pharmacist_id}/request_review", status_code=201)
async def request_review(
    check_id: str,
    pharmacist_id: str,
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
            trang_thai_xac_nhan="cho_xac_nhan"
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
                trang_thai_xac_nhan=review.trang_thai_xac_nhan
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
    db.commit()
    db.refresh(review)

    return PharmacistReviewResponse(
        id=review.id,
        interaction_check_id=review.interaction_check_id,
        trang_thai_xac_nhan=review.trang_thai_xac_nhan,
        ghi_chu=review.ghi_chu or "",
    )


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
