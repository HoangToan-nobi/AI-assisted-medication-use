"""POST /api/v1/prescriptions/scan - proxy sang ocr-service.

Không cần ocr-service chạy thật: mock httpx.AsyncClient ở mức module
src.api.routes (nơi nó được import và dùng) cho mọi ca gọi ra ngoài.
"""

import httpx
import pytest

from tests.test_api.test_routes import _auth_headers, _register

_JPEG_MAGIC = b"\xff\xd8\xff"


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None):
        self.status_code = status_code
        self._json_body = json_body or {}
        self.text = str(self._json_body)

    def json(self) -> dict:
        return self._json_body


class _FakeAsyncClient:
    """Thay cho httpx.AsyncClient thật - trả về response/lỗi đã định sẵn."""

    def __init__(self, response: _FakeResponse | None = None, raise_error: bool = False, **_kwargs):
        self._response = response
        self._raise_error = raise_error

    def __call__(self, *_args, **_kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def post(self, *_args, **_kwargs):
        if self._raise_error:
            raise httpx.ConnectError("boom", request=None)
        return self._response


def _mock_ocr(monkeypatch, *, response: _FakeResponse | None = None, raise_error: bool = False):
    monkeypatch.setattr(
        "src.api.routes.httpx.AsyncClient",
        _FakeAsyncClient(response=response, raise_error=raise_error),
    )


async def _patient_token(client) -> str:
    data = await _register(client, "Benh nhan Scan", "patient")
    return data["access_token"]


@pytest.mark.asyncio
async def test_scan_prescription_requires_auth(client):
    files = {"image": ("don.jpg", _JPEG_MAGIC + b"\x00" * 50, "image/jpeg")}
    response = await client.post("/api/v1/prescriptions/scan", files=files)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scan_prescription_file_too_large(client, monkeypatch):
    token = await _patient_token(client)
    oversized = _JPEG_MAGIC + b"0" * (10 * 1024 * 1024 + 1)
    files = {"image": ("don.jpg", oversized, "image/jpeg")}
    response = await client.post(
        "/api/v1/prescriptions/scan", files=files, headers=_auth_headers(token)
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_scan_prescription_rejects_non_image(client, monkeypatch):
    token = await _patient_token(client)
    files = {"image": ("don.txt", b"day khong phai anh", "text/plain")}
    response = await client.post(
        "/api/v1/prescriptions/scan", files=files, headers=_auth_headers(token)
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_scan_prescription_ocr_service_unreachable(client, monkeypatch):
    token = await _patient_token(client)
    _mock_ocr(monkeypatch, raise_error=True)
    files = {"image": ("don.jpg", _JPEG_MAGIC + b"\x00" * 50, "image/jpeg")}
    response = await client.post(
        "/api/v1/prescriptions/scan", files=files, headers=_auth_headers(token)
    )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_scan_prescription_ocr_service_error_status(client, monkeypatch):
    token = await _patient_token(client)
    _mock_ocr(monkeypatch, response=_FakeResponse(500, {"success": False}))
    files = {"image": ("don.jpg", _JPEG_MAGIC + b"\x00" * 50, "image/jpeg")}
    response = await client.post(
        "/api/v1/prescriptions/scan", files=files, headers=_auth_headers(token)
    )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_scan_prescription_maps_ocr_response(client, monkeypatch):
    token = await _patient_token(client)
    ocr_payload = {
        "success": True,
        "document_type": "prescription",
        "medications": [
            {
                "row_number": 1,
                "ocr_drug_name": "Đại tần giao",
                "candidates": [
                    {"drug_name": "Tần giao", "score": 0.87},
                    {"drug_name": "Đại Tần Giao", "score": 0.81},
                    {"drug_name": "Tam that", "score": 0.4},
                ],
            },
            {
                "row_number": 2,
                "ocr_drug_name": "Panadol Extra",
                "candidates": [{"drug_name": "Panadol Extra", "score": 0.97}],
            },
            {
                "row_number": 3,
                "ocr_drug_name": "Thuoc la khong ro",
                "candidates": [],
            },
        ],
    }
    _mock_ocr(monkeypatch, response=_FakeResponse(200, ocr_payload))
    files = {"image": ("don.jpg", _JPEG_MAGIC + b"\x00" * 50, "image/jpeg")}
    response = await client.post(
        "/api/v1/prescriptions/scan", files=files, headers=_auth_headers(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_type"] == "prescription"
    assert body["requires_confirmation"] is True
    assert len(body["drugs"]) == 3

    row1 = body["drugs"][0]
    assert row1["ocr_text"] == "Đại tần giao"
    assert row1["suggested_name"] == "Tần giao"
    # Ứng viên đúng ("Đại Tần Giao") phải vẫn xuất hiện trong alternatives dù xếp
    # hạng 2 - đây là đúng ca lệch điểm mô tả trong yêu cầu tích hợp, phần duyệt ở
    # frontend PHẢI hiển thị alternatives để người dùng tự sửa.
    assert row1["alternatives"] == ["Đại Tần Giao", "Tam that"]
    assert row1["known"] is True  # score 0.87 >= 0.75, dù là đề xuất sai

    row2 = body["drugs"][1]
    assert row2["suggested_name"] == "Panadol Extra"
    assert row2["known"] is True
    assert row2["alternatives"] == []

    row3 = body["drugs"][2]
    assert row3["suggested_name"] is None
    assert row3["known"] is False
    assert row3["score"] == 0.0
