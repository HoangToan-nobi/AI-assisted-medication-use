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
    monkeypatch.setattr("src.agents.nodes.explain_node.get_llm", lambda: mock_llm)

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
    monkeypatch.setattr("src.agents.nodes.explain_node.get_llm", lambda: mock_llm)

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

        # Bệnh nhân gửi yêu cầu review.
        req_resp = await client.post(
            f"/api/v1/checks/{check_id}/pharmacists/{pharmacist['user_id']}/request_review",
            headers=patient_headers,
        )
        assert req_resp.status_code == 201

        # Dược sĩ thấy request.
        after_resp = await client.get("/api/v1/pharmacist/requests", headers=pharmacist_headers)
        after = after_resp.json()
        assert len(after) == 1
        assert after[0]["check_id"] == check_id
        assert after[0]["trang_thai_xac_nhan"] == "cho_xac_nhan"

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
