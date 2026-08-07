import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.agents.graph import agent
from src.agents.tools.drug_normalizer_tool import drug_normalizer
from src.api.deps import get_current_user, require_role
from src.db.models import (
    InteractionCheck,
    Medication,
    MedicationAlias,
    PatientMedication,
    PharmacistAssignment,
    PharmacistReview,
    User,
)
from src.db.session import get_db
from src.models.schemas import (
    AddMedicationRequest,
    AuthResponse,
    ChatRequest,
    ChatResponse,
    InteractionCheckSummary,
    LoginRequest,
    MedicationCheckRequest,
    MedicationCheckResponse,
    MedicationItem,
    MedicationSearchResult,
    PatientSummary,
    PharmacistReviewRequest,
    PharmacistReviewResponse,
    RegisterRequest,
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
        assignment = (
            db.query(PharmacistAssignment)
            .filter_by(pharmacist_id=current_user.id, patient_id=patient_id)
            .first()
        )
        if assignment is not None:
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


# ---- Hồ sơ thuốc bệnh nhân ----


@router.get("/patients/{patient_id}/medications", response_model=list[MedicationItem])
async def list_patient_medications(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MedicationItem]:
    _ensure_can_view_patient(current_user, patient_id, db)

    rows = (
        db.query(PatientMedication, Medication)
        .join(Medication, Medication.id == PatientMedication.medication_id)
        .filter(PatientMedication.patient_id == patient_id)
        .all()
    )
    return [
        MedicationItem(
            id=pm.id,
            medication_id=med.id,
            ten_chuan_hoa=med.ten_chuan_hoa,
            ngay_bat_dau=pm.ngay_bat_dau,
            ngay_ket_thuc=pm.ngay_ket_thuc,
        )
        for pm, med in rows
    ]


@router.post(
    "/patients/{patient_id}/medications", response_model=MedicationItem, status_code=201
)
async def add_patient_medication(
    patient_id: str,
    request: AddMedicationRequest,
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> MedicationItem:
    if current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Chỉ tự thêm thuốc cho chính mình")

    normalized_json = await drug_normalizer.ainvoke(
        {"medication_names": [request.medication_name]}
    )
    med_info = json.loads(normalized_json)[0]
    if med_info["khong_du_du_lieu"]:
        raise HTTPException(
            status_code=422, detail=f"Không tìm thấy thuốc '{request.medication_name}' trong CSDL"
        )

    pm = PatientMedication(
        patient_id=patient_id,
        medication_id=med_info["medication_id"],
        ngay_bat_dau=date.today(),
    )
    db.add(pm)
    db.commit()
    db.refresh(pm)

    return MedicationItem(
        id=pm.id,
        medication_id=med_info["medication_id"],
        ten_chuan_hoa=med_info["ten_chuan"],
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


def _find_review(
    db: Session, check_id: str, pharmacist_id: str | None = None
) -> PharmacistReview | None:
    query = db.query(PharmacistReview).filter_by(interaction_check_id=check_id)
    if pharmacist_id is not None:
        query = query.filter_by(pharmacist_id=pharmacist_id)
    return query.first()


def _review_status(db: Session, check_id: str, pharmacist_id: str | None = None) -> str:
    review = _find_review(db, check_id, pharmacist_id)
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
    review = _find_review(db, check.id)
    return MedicationCheckResponse(
        interaction_check_id=check.id,
        ranked_results=_strip_pharmacist_fields(result.get("ranked_results", [])),
        explanations=_strip_pharmacist_fields(result.get("explanations", [])),
        has_severe=result.get("has_severe", False),
        has_unclassified=result.get("has_unclassified", False),
        ghi_chu=review.ghi_chu if review else None,
    )


# ---- Dược sĩ ----


@router.get("/pharmacist/{pharmacist_id}/patients", response_model=list[PatientSummary])
async def list_pharmacist_patients(
    pharmacist_id: str,
    current_user: User = Depends(require_role("pharmacist")),
    db: Session = Depends(get_db),
) -> list[PatientSummary]:
    if current_user.id != pharmacist_id:
        raise HTTPException(status_code=403, detail="Không được xem danh sách của dược sĩ khác")

    assignments = db.query(PharmacistAssignment).filter_by(pharmacist_id=pharmacist_id).all()

    results = []
    for assignment in assignments:
        patient = db.get(User, assignment.patient_id)
        if patient is None:
            continue
        unresolved_severe = (
            db.query(InteractionCheck)
            .outerjoin(
                PharmacistReview,
                PharmacistReview.interaction_check_id == InteractionCheck.id,
            )
            .filter(
                InteractionCheck.patient_id == patient.id,
                InteractionCheck.co_canh_bao_nang.is_(True),
                PharmacistReview.id.is_(None),
            )
            .count()
            > 0
        )
        results.append(
            PatientSummary(
                id=patient.id, ho_ten=patient.ho_ten, co_canh_bao_nang_chua_xu_ly=unresolved_severe
            )
        )

    # Escalate: bệnh nhân có cảnh báo nặng chưa xử lý nổi lên đầu danh sách.
    results.sort(key=lambda p: p.co_canh_bao_nang_chua_xu_ly, reverse=True)
    return results


def _ensure_pharmacist_assigned(current_user: User, patient_id: str, db: Session) -> None:
    assignment = (
        db.query(PharmacistAssignment)
        .filter_by(pharmacist_id=current_user.id, patient_id=patient_id)
        .first()
    )
    if assignment is None:
        raise HTTPException(status_code=403, detail="Bạn không được phân công bệnh nhân này")


@router.get(
    "/pharmacist/patients/{patient_id}/checks", response_model=list[InteractionCheckSummary]
)
async def list_patient_checks_for_pharmacist(
    patient_id: str,
    current_user: User = Depends(require_role("pharmacist")),
    db: Session = Depends(get_db),
) -> list[InteractionCheckSummary]:
    """Danh sách lần kiểm tra của 1 bệnh nhân - để dược sĩ chọn ra check cần xem
    chi tiết/xác nhận (GET /pharmacist/reviews/{id}, POST /pharmacist/reviews)."""
    _ensure_pharmacist_assigned(current_user, patient_id, db)

    checks = (
        db.query(InteractionCheck)
        .filter_by(patient_id=patient_id)
        .order_by(InteractionCheck.co_canh_bao_nang.desc(), InteractionCheck.thoi_gian_kiem_tra.desc())
        .all()
    )
    return [
        InteractionCheckSummary(
            id=check.id,
            thoi_gian_kiem_tra=check.thoi_gian_kiem_tra,
            co_canh_bao_nang=check.co_canh_bao_nang,
            co_chua_phan_loai=check.co_chua_phan_loai,
            trang_thai_xac_nhan=_review_status(db, check.id, current_user.id),
        )
        for check in checks
    ]


@router.get("/pharmacist/reviews/{interaction_check_id}")
async def get_interaction_check_detail(
    interaction_check_id: str,
    current_user: User = Depends(require_role("pharmacist")),
    db: Session = Depends(get_db),
) -> dict:
    """Chi tiết đầy đủ 1 lần kiểm tra (bao gồm xu_tri/thay_the - chỉ dược sĩ xem),
    kèm ghi_chu/trang_thai_xac_nhan của CHÍNH dược sĩ đang xem (nếu đã từng xác nhận)."""
    check = db.get(InteractionCheck, interaction_check_id)
    if check is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy interaction_check")

    _ensure_pharmacist_assigned(current_user, check.patient_id, db)

    review = _find_review(db, check.id, current_user.id)
    result = dict(check.ket_qua_json or {})
    result["ghi_chu"] = review.ghi_chu if review else None
    result["trang_thai_xac_nhan"] = review.trang_thai_xac_nhan if review else "chua_xac_nhan"
    return result


@router.post("/pharmacist/reviews", response_model=PharmacistReviewResponse)
async def submit_pharmacist_review(
    request: PharmacistReviewRequest,
    current_user: User = Depends(require_role("pharmacist")),
    db: Session = Depends(get_db),
) -> PharmacistReviewResponse:
    check = db.get(InteractionCheck, request.interaction_check_id)
    if check is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy interaction_check")

    _ensure_pharmacist_assigned(current_user, check.patient_id, db)

    review = (
        db.query(PharmacistReview)
        .filter_by(interaction_check_id=check.id, pharmacist_id=current_user.id)
        .first()
    )
    if review is None:
        review = PharmacistReview(
            interaction_check_id=check.id, pharmacist_id=current_user.id
        )
        db.add(review)

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
