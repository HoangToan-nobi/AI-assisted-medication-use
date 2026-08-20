"""Authentication primitives for passwords, Google identities and sessions."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import AuthActionToken, RefreshSession, User

_PBKDF2_ITERATIONS = 100_000
_password_hasher = PasswordHasher()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def _verify_legacy_password(password: str, hashed: str) -> bool:
    try:
        salt, digest_hex = hashed.split("$", 1)
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected.hex(), digest_hex)


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    if hashed.startswith("$argon2"):
        try:
            return _password_hasher.verify(hashed, password)
        except (VerifyMismatchError, InvalidHashError):
            return False
    return _verify_legacy_password(password, hashed)


def password_needs_rehash(hashed: str | None) -> bool:
    if not hashed or not hashed.startswith("$argon2"):
        return True
    try:
        return _password_hasher.check_needs_rehash(hashed)
    except InvalidHashError:
        return True


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload_b64: str) -> str:
    secret = get_settings().secret_key.encode()
    return _b64encode(hmac.new(secret, payload_b64.encode(), hashlib.sha256).digest())


def create_token(user_id: str, vai_tro: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    ttl = expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    now = int(time.time())
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "vai_tro": vai_tro,
        "type": "access",
        "iat": now,
        "exp": now + ttl * 60,
        "jti": secrets.token_urlsafe(16),
    }
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        payload_b64, signature = token.split(".", 1)
        if not hmac.compare_digest(_sign(payload_b64), signature):
            return None
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    if payload.get("exp", 0) < time.time() or payload.get("type", "access") != "access":
        return None
    return payload


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_action_token(db: Session, user_id: str, purpose: str, ttl_minutes: int) -> str:
    now = datetime.utcnow()
    db.query(AuthActionToken).filter(
        AuthActionToken.user_id == user_id,
        AuthActionToken.purpose == purpose,
        AuthActionToken.used_at.is_(None),
    ).update({"used_at": now})
    raw = secrets.token_urlsafe(32)
    db.add(AuthActionToken(user_id=user_id, purpose=purpose, token_hash=hash_token(raw), expires_at=now + timedelta(minutes=ttl_minutes)))
    db.commit()
    return raw


def consume_action_token(db: Session, raw: str, purpose: str) -> User | None:
    now = datetime.utcnow()
    token = db.query(AuthActionToken).filter_by(token_hash=hash_token(raw), purpose=purpose).first()
    if token is None or token.used_at is not None or token.expires_at <= now:
        return None
    token.used_at = now
    user = db.get(User, token.user_id)
    db.commit()
    return user


def issue_refresh_session(db: Session, user_id: str) -> tuple[str, RefreshSession]:
    raw = secrets.token_urlsafe(48)
    session = RefreshSession(user_id=user_id, token_hash=hash_token(raw), expires_at=datetime.utcnow() + timedelta(days=get_settings().refresh_token_expire_days))
    db.add(session)
    db.commit()
    db.refresh(session)
    return raw, session


def rotate_refresh_session(db: Session, raw: str) -> tuple[str, RefreshSession] | None:
    now = datetime.utcnow()
    old = db.query(RefreshSession).filter_by(token_hash=hash_token(raw)).first()
    if old is None or old.revoked_at is not None or old.expires_at <= now:
        return None
    new_raw, new = issue_refresh_session(db, old.user_id)
    old.revoked_at = now
    old.replaced_by_id = new.id
    db.commit()
    return new_raw, new


def revoke_refresh_session(db: Session, raw: str | None) -> None:
    if not raw:
        return
    session = db.query(RefreshSession).filter_by(token_hash=hash_token(raw)).first()
    if session and session.revoked_at is None:
        session.revoked_at = datetime.utcnow()
        db.commit()


def verify_google_credential(credential: str) -> dict[str, Any]:
    client_id = get_settings().google_client_id
    if not client_id:
        raise ValueError("Google Sign-In chua duoc cau hinh")
    claims = google_id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise ValueError("Google issuer khong hop le")
    if claims.get("aud") != client_id or not claims.get("email_verified"):
        raise ValueError("Tai khoan Google chua duoc xac minh")
    if not claims.get("sub") or not claims.get("email"):
        raise ValueError("Google token thieu thong tin bat buoc")
    return claims


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
