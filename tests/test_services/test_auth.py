from types import SimpleNamespace

import pytest

from src.services import auth


def test_argon2_and_legacy_password_verification():
    encoded = auth.hash_password("correct-horse-battery")
    assert encoded.startswith("$argon2")
    assert auth.verify_password("correct-horse-battery", encoded)
    assert not auth.verify_password("wrong", encoded)

    # Known legacy PBKDF2 shape remains readable and is marked for rehash.
    import hashlib
    salt = "00" * 16
    digest = hashlib.pbkdf2_hmac("sha256", b"legacy-password", bytes.fromhex(salt), 100_000).hex()
    legacy = f"{salt}${digest}"
    assert auth.verify_password("legacy-password", legacy)
    assert auth.password_needs_rehash(legacy)


def test_google_claim_validation(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(google_client_id="client-123"))
    valid = {"sub": "subject", "email": "user@gmail.com", "email_verified": True, "aud": "client-123", "iss": "https://accounts.google.com"}
    monkeypatch.setattr(auth.google_id_token, "verify_oauth2_token", lambda *_: valid.copy())
    assert auth.verify_google_credential("credential")["sub"] == "subject"

    for changed in (
        {"aud": "wrong"},
        {"iss": "https://attacker.invalid"},
        {"email_verified": False},
        {"sub": None},
    ):
        claims = valid | changed
        monkeypatch.setattr(auth.google_id_token, "verify_oauth2_token", lambda *_, claims=claims: claims)
        with pytest.raises(ValueError):
            auth.verify_google_credential("credential")

    monkeypatch.setattr(auth.google_id_token, "verify_oauth2_token", lambda *_: (_ for _ in ()).throw(ValueError("expired or bad signature")))
    with pytest.raises(ValueError):
        auth.verify_google_credential("credential")
