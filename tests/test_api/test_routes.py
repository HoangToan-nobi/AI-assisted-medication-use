import uuid

import pytest

from src.db.session import SessionLocal


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    response = await client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_agent_status(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@test.local"


async def _register(client, ho_ten: str, vai_tro: str) -> dict:
    email = _unique_email(vai_tro)
    response = await client.post(
        "/api/v1/auth/register",
        json={"ho_ten": ho_ten, "email": email, "mat_khau": "matkhau123", "vai_tro": vai_tro},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# TC-A01: đăng ký + đăng nhập theo vai trò (FR-01).
@pytest.mark.asyncio
async def test_register_and_login(client):
    email = _unique_email("patient")
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "ho_ten": "Co Lan",
            "email": email,
            "mat_khau": "matkhau123",
            "vai_tro": "patient",
        },
    )
    assert register_resp.status_code == 201
    assert register_resp.json()["vai_tro"] == "patient"

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "mat_khau": "matkhau123"}
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["access_token"]

    wrong_pw_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "mat_khau": "sai_mat_khau"}
    )
    assert wrong_pw_resp.status_code == 401


# TC-A02: gọi endpoint cần auth mà không có token -> 401.
@pytest.mark.asyncio
async def test_medications_check_requires_auth(client):
    response = await client.post("/api/v1/medications/check", json={"medications": []})
    assert response.status_code in (401, 422)  # 422 nếu Header thiếu bị FastAPI validate trước


# TC-A03: bệnh nhân kiểm tra tương tác - cặp thật mức "nang", response KHÔNG có xu_tri (pharmacist-only).
@pytest.mark.asyncio
async def test_check_medications_severe_pair_hides_pharmacist_fields(client, monkeypatch, mock_llm):
    # Mức "nang" (khác chua_phan_loai) đi qua nhánh gọi LLM thật trong explain_node -
    # mock lại để test không phụ thuộc DEEPSEEK_API_KEY thật.
    monkeypatch.setattr("src.agents.nodes.explain_node.ainvoke_llm", mock_llm.ainvoke)

    patient = await _register(client, "Benh nhan A", "patient")
    headers = _auth_headers(patient["access_token"])

    response = await client.post(
        "/api/v1/medications/check",
        json={"medications": ["warfarin", "asp"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["has_severe"] is True
    assert data["interaction_check_id"]
    for explanation in data["explanations"]:
        assert "xu_tri" not in explanation
        assert "thay_the_a" not in explanation
        assert "thay_the_b" not in explanation


# TC-A04: bệnh nhân thêm thuốc hợp lệ vào hồ sơ, xem lại đúng danh sách; thuốc không tồn tại -> 422.
@pytest.mark.asyncio
async def test_add_and_list_patient_medications(client):
    patient = await _register(client, "Benh nhan B", "patient")
    headers = _auth_headers(patient["access_token"])
    patient_id = patient["user_id"]

    add_resp = await client.post(
        f"/api/v1/patients/{patient_id}/medications",
        json={"product_name": "ibuprofen"},
        headers=headers,
    )
    assert add_resp.status_code == 201, add_resp.text
    assert add_resp.json()["ten_thuoc"] == "Ibuprofen"

    invalid_resp = await client.post(
        f"/api/v1/patients/{patient_id}/medications",
        json={"product_name": "thuocxyzkhonghople"},
        headers=headers,
    )
    assert invalid_resp.status_code == 422

    list_resp = await client.get(
        f"/api/v1/patients/{patient_id}/medications", headers=headers
    )
    assert list_resp.status_code == 200
    items = list_resp.json()
    names = [m["ten_thuoc"] for m in items]
    assert "Ibuprofen" in names

    # Xóa thuốc vừa thêm -> biến mất khỏi danh sách.
    patient_medication_id = next(m["id"] for m in items if m["ten_thuoc"] == "Ibuprofen")
    delete_resp = await client.delete(
        f"/api/v1/patients/{patient_id}/medications/{patient_medication_id}", headers=headers
    )
    assert delete_resp.status_code == 204

    after_delete_resp = await client.get(
        f"/api/v1/patients/{patient_id}/medications", headers=headers
    )
    assert "Ibuprofen" not in [m["ten_chuan_hoa"] for m in after_delete_resp.json()]

    # Bệnh nhân khác không được xóa thuốc không phải của mình.
    other_patient = await _register(client, "Benh nhan khac", "patient")
    forbidden_resp = await client.delete(
        f"/api/v1/patients/{patient_id}/medications/{patient_medication_id}",
        headers=_auth_headers(other_patient["access_token"]),
    )
    assert forbidden_resp.status_code == 403


# TC-A05: đơn thuốc đã lưu trong hồ sơ (tab "Đơn thuốc của tôi") - tạo/đổi tên/xóa
# đơn, thêm thuốc theo đúng đơn được chọn, không cho xóa đơn cuối cùng.
@pytest.mark.asyncio
async def test_patient_prescriptions_grouping(client):
    patient = await _register(client, "Benh nhan C", "patient")
    headers = _auth_headers(patient["access_token"])
    patient_id = patient["user_id"]

    # Chưa có đơn nào - GET tự tạo đơn mặc định "Đơn thuốc 1".
    list_resp = await client.get(f"/api/v1/patients/{patient_id}/prescriptions", headers=headers)
    assert list_resp.status_code == 200
    prescriptions = list_resp.json()
    assert len(prescriptions) == 1
    assert prescriptions[0]["label"] == "Đơn thuốc 1"
    default_id = prescriptions[0]["id"]

    # Thêm thuốc không kèm prescription_id -> rơi vào đơn mặc định (tương thích ngược).
    add_default_resp = await client.post(
        f"/api/v1/patients/{patient_id}/medications",
        json={"product_name": "ibuprofen"},
        headers=headers,
    )
    assert add_default_resp.status_code == 201, add_default_resp.text
    assert add_default_resp.json()["prescription_id"] == default_id

    # Tạo đơn thứ 2, đổi tên, thêm thuốc đúng vào đơn này.
    create_resp = await client.post(
        f"/api/v1/patients/{patient_id}/prescriptions",
        json={"label": "Đơn thuốc 2"},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    second_id = create_resp.json()["id"]

    rename_resp = await client.patch(
        f"/api/v1/patients/{patient_id}/prescriptions/{second_id}",
        json={"label": "Đơn tiểu đường"},
        headers=headers,
    )
    assert rename_resp.status_code == 200
    assert rename_resp.json()["label"] == "Đơn tiểu đường"

    add_second_resp = await client.post(
        f"/api/v1/patients/{patient_id}/medications",
        json={"product_name": "paracetamol", "prescription_id": second_id},
        headers=headers,
    )
    assert add_second_resp.status_code == 201, add_second_resp.text
    assert add_second_resp.json()["prescription_id"] == second_id

    grouped_resp = await client.get(f"/api/v1/patients/{patient_id}/prescriptions", headers=headers)
    grouped = {p["id"]: p for p in grouped_resp.json()}
    assert len(grouped) == 2
    assert [m["ten_thuoc"] for m in grouped[default_id]["medications"]] == ["Ibuprofen"]
    assert [m["ten_thuoc"] for m in grouped[second_id]["medications"]] == ["Paracetamol"]

    # Xóa đơn thứ 2 -> kéo theo thuốc của nó; xóa đơn mặc định (đơn cuối cùng còn lại) -> 400.
    delete_second_resp = await client.delete(
        f"/api/v1/patients/{patient_id}/prescriptions/{second_id}", headers=headers
    )
    assert delete_second_resp.status_code == 204

    delete_last_resp = await client.delete(
        f"/api/v1/patients/{patient_id}/prescriptions/{default_id}", headers=headers
    )
    assert delete_last_resp.status_code == 400

    after_delete_resp = await client.get(f"/api/v1/patients/{patient_id}/prescriptions", headers=headers)
    remaining = after_delete_resp.json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == default_id


# TC-A06: /medications/search phải khớp cả alias (VD "aspirin" -> Acetylsalicylic acid),
# nhất quán với drug_normalizer_tool dùng khi thêm thuốc thật (bug người dùng báo cáo).
@pytest.mark.asyncio
async def test_search_medications_matches_alias(client):
    patient = await _register(client, "Benh nhan E", "patient")
    headers = _auth_headers(patient["access_token"])

    resp = await client.get("/api/v1/medications/search?q=aspirin", headers=headers)
    assert resp.status_code == 200
    names = [m["ten_chuan_hoa"] for m in resp.json()]
    assert "Acetylsalicylic acid" in names


@pytest.mark.asyncio
async def test_pharmacist_receives_review_request_and_can_review(monkeypatch, mock_llm):
    monkeypatch.setattr("src.agents.nodes.explain_node.ainvoke_llm", mock_llm.ainvoke)

    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        patient = await _register(client, "Benh nhan C", "patient")
        pharmacist = await _register(client, "Duoc si D", "pharmacist")
        patient_headers = _auth_headers(patient["access_token"])
        pharmacist_headers = _auth_headers(pharmacist["access_token"])

        # Bệnh nhân tự kiểm tra một cặp thuốc thật mức "nang".
        check_resp = await client.post(
            "/api/v1/medications/check",
            json={"medications": ["warfarin", "asp"]},
            headers=patient_headers,
        )
        assert check_resp.status_code == 200
        check_id = check_resp.json()["interaction_check_id"]

        # Dược sĩ chưa nhận được request nào.
        before_resp = await client.get("/api/v1/pharmacist/requests", headers=pharmacist_headers)
        assert before_resp.status_code == 200
        assert len(before_resp.json()) == 0

        # Bệnh nhân gửi yêu cầu review - lần này chọn TỰ NHẬP thông tin (trường hợp
        # tra cứu hộ người khác), không gửi kèm hồ sơ cá nhân của chính mình.
        req_resp = await client.post(
            f"/api/v1/checks/{check_id}/pharmacists/{pharmacist['user_id']}/request_review",
            json={
                "gui_kem_ho_so": False,
                "ten_nguoi_duoc_kiem_tra": "Nguoi than cua benh nhan",
                "ngay_sinh_nhap_tay": "1990-01-01",
                "ghi_chu_nhap_tay": "Di ung penicillin",
            },
            headers=patient_headers,
        )
        assert req_resp.status_code == 201

        # Dược sĩ thấy request, kèm đúng ngữ cảnh tự nhập ở trên.
        after_resp = await client.get("/api/v1/pharmacist/requests", headers=pharmacist_headers)
        after = after_resp.json()
        assert len(after) == 1
        assert after[0]["check_id"] == check_id
        assert after[0]["trang_thai_xac_nhan"] == "cho_xac_nhan"
        assert after[0]["gui_kem_ho_so"] is False
        assert after[0]["ten_nguoi_duoc_kiem_tra"] == "Nguoi than cua benh nhan"
        assert after[0]["ghi_chu_nhap_tay"] == "Di ung penicillin"

        # Dược sĩ khác không xem được chi tiết.
        other_pharmacist = await _register(client, "Duoc si khac", "pharmacist")
        forbidden_resp = await client.get(
            f"/api/v1/pharmacist/reviews/{check_id}",
            headers=_auth_headers(other_pharmacist["access_token"]),
        )
        assert forbidden_resp.status_code == 403

        # Dược sĩ được yêu cầu xem chi tiết đầy đủ - CÓ xu_tri (pharmacist-only).
        detail_resp = await client.get(
            f"/api/v1/pharmacist/reviews/{check_id}", headers=pharmacist_headers
        )
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert any("xu_tri" in e for e in detail["explanations"])

        # Xác nhận review -> trạng thái "đã xác nhận".
        review_resp = await client.post(
            "/api/v1/pharmacist/reviews",
            json={"interaction_check_id": check_id, "ghi_chu": "Da tu van benh nhan"},
            headers=pharmacist_headers,
        )
        assert review_resp.status_code == 200
        assert review_resp.json()["trang_thai_xac_nhan"] == "da_xac_nhan"

        final_resp = await client.get("/api/v1/pharmacist/requests", headers=pharmacist_headers)
        assert final_resp.json()[0]["trang_thai_xac_nhan"] == "da_xac_nhan"

        # Xác nhận xong -> bệnh nhân có 1 thông báo mới, chưa đọc, nhắc tên dược sĩ.
        notif_resp = await client.get(
            f"/api/v1/patients/{patient['user_id']}/notifications", headers=patient_headers
        )
        assert notif_resp.status_code == 200
        notifications = notif_resp.json()
        assert len(notifications) == 1
        assert notifications[0]["da_doc"] is False
        assert "Duoc si D" in notifications[0]["noi_dung"]
        assert notifications[0]["interaction_check_id"] == check_id

        # Đánh dấu đã đọc -> phản ánh đúng ở lần gọi lại.
        mark_resp = await client.post(
            f"/api/v1/patients/{patient['user_id']}/notifications/{notifications[0]['id']}/read",
            headers=patient_headers,
        )
        assert mark_resp.status_code == 204
        notif_resp2 = await client.get(
            f"/api/v1/patients/{patient['user_id']}/notifications", headers=patient_headers
        )
        assert notif_resp2.json()[0]["da_doc"] is True

        # Bệnh nhân khác không xem được thông báo của người khác.
        other_patient = await _register(client, "Benh nhan khac 2", "patient")
        forbidden_notif_resp = await client.get(
            f"/api/v1/patients/{patient['user_id']}/notifications",
            headers=_auth_headers(other_patient["access_token"]),
        )
        assert forbidden_notif_resp.status_code == 403


# TC-A07: hồ sơ cá nhân dược sĩ - tự sửa được, người khác không sửa được.
@pytest.mark.asyncio
async def test_pharmacist_profile_self_update_only(client):
    pharmacist = await _register(client, "Duoc si Ho So", "pharmacist")
    other_pharmacist = await _register(client, "Duoc si Khac 2", "pharmacist")
    headers = _auth_headers(pharmacist["access_token"])

    get_resp = await client.get(
        f"/api/v1/pharmacists/{pharmacist['user_id']}/profile", headers=headers
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["mo_ta_ngan"] is None

    update_resp = await client.patch(
        f"/api/v1/pharmacists/{pharmacist['user_id']}/profile",
        json={"noi_cong_tac": "Benh vien Cho Ray", "mo_ta_ngan": "10 nam kinh nghiem lam sang"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["mo_ta_ngan"] == "10 nam kinh nghiem lam sang"

    forbidden_resp = await client.patch(
        f"/api/v1/pharmacists/{pharmacist['user_id']}/profile",
        json={"mo_ta_ngan": "Hack"},
        headers=_auth_headers(other_pharmacist["access_token"]),
    )
    assert forbidden_resp.status_code == 403


# TC-A08: get_patient_check_detail phải trả đủ overview/product_explanations đã
# lưu trong ket_qua_json (bug cũ chỉ trả ranked_results/explanations/has_severe).
@pytest.mark.asyncio
async def test_patient_check_detail_includes_overview_and_product_explanations(client):
    patient = await _register(client, "Benh nhan F", "patient")
    headers = _auth_headers(patient["access_token"])

    db = SessionLocal()
    try:
        from src.db.models import InteractionCheck

        check = InteractionCheck(
            patient_id=patient["user_id"],
            ket_qua_json={
                "ranked_results": [],
                "explanations": [],
                "has_severe": False,
                "has_unclassified": False,
                "product_explanations": [{"thuoc_a": "A", "thuoc_b": "B", "giai_thich": "..."}],
                "overview": {"giai_thich": "Tom tat tong quan"},
            },
            co_canh_bao_nang=False,
            co_chua_phan_loai=False,
        )
        db.add(check)
        db.commit()
        db.refresh(check)
        check_id = check.id
    finally:
        db.close()

    detail_resp = await client.get(
        f"/api/v1/patients/{patient['user_id']}/checks/{check_id}", headers=headers
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["overview"] == {"giai_thich": "Tom tat tong quan"}
    assert detail["product_explanations"] == [{"thuoc_a": "A", "thuoc_b": "B", "giai_thich": "..."}]
