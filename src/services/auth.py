"""Auth don gian: bam mat khau (PBKDF2) + token tu ky bang HMAC.

Khong dung thu vien ngoai (bcrypt/python-jose...) de giu nguyen tech stack da
chot (GD6) - chi dung stdlib. Du cho MVP: 2 vai tro (patient/pharmacist),
khong co refresh token/revoke list.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

from src.config import get_settings

_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, digest_hex = hashed.split("$", 1)
    except ValueError:
        return False
    expected = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(expected.hex(), digest_hex)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)


def _sign(payload_b64: str) -> str:
    settings = get_settings()
    sig = hmac.new(
        settings.secret_key.encode(), payload_b64.encode(), hashlib.sha256
    ).digest()
    return _b64encode(sig)


def create_token(user_id: str, vai_tro: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    ttl = expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    payload = {"user_id": user_id, "vai_tro": vai_tro, "exp": time.time() + ttl * 60}
    payload_b64 = _b64encode(json.dumps(payload).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def decode_token(token: str) -> dict | None:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(payload_b64), signature):
        return None
    try:
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload
