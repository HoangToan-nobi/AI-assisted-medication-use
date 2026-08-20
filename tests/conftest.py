import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, or_, select

from src.db.models import (
    AuthActionToken,
    AuthIdentity,
    InteractionCheck,
    Notification,
    PatientCondition,
    PatientMedication,
    PatientPrescription,
    PatientProfile,
    PharmacistReview,
    RefreshSession,
    User,
)
from src.db.session import SessionLocal
from src.main import app


@pytest.fixture(autouse=True)
def disable_transactional_email(monkeypatch):
    """Keep API tests deterministic and prevent delivery to real recipients."""
    monkeypatch.setattr("src.api.auth_routes.send_verification_email", lambda *args: None)
    monkeypatch.setattr("src.api.auth_routes.send_password_reset_email", lambda *args: None)
    monkeypatch.setattr("src.api.auth_routes.send_pharmacist_decision_email", lambda *args: None)


@pytest.fixture(autouse=True)
def cleanup_generated_users():
    """Remove synthetic @test.local rows from the configured integration DB."""
    yield
    with SessionLocal() as db:
        user_ids = select(User.id).where(User.email_normalized.like("%@test.local"))
        profile_ids = select(PatientProfile.id).where(PatientProfile.user_id.in_(user_ids))
        check_ids = select(InteractionCheck.id).where(InteractionCheck.patient_id.in_(user_ids))
        review_ids = select(PharmacistReview.id).where(
            or_(
                PharmacistReview.pharmacist_id.in_(user_ids),
                PharmacistReview.interaction_check_id.in_(check_ids),
            )
        )
        db.execute(
            delete(Notification).where(
                or_(Notification.patient_id.in_(user_ids), Notification.pharmacist_review_id.in_(review_ids))
            )
        )
        db.execute(delete(PharmacistReview).where(PharmacistReview.id.in_(review_ids)))
        db.execute(delete(PatientCondition).where(PatientCondition.patient_profile_id.in_(profile_ids)))
        db.execute(delete(PatientMedication).where(PatientMedication.patient_id.in_(user_ids)))
        db.execute(delete(PatientPrescription).where(PatientPrescription.patient_id.in_(user_ids)))
        db.execute(delete(InteractionCheck).where(InteractionCheck.id.in_(check_ids)))
        db.execute(delete(PatientProfile).where(PatientProfile.id.in_(profile_ids)))
        db.execute(delete(AuthIdentity).where(AuthIdentity.user_id.in_(user_ids)))
        db.execute(delete(AuthActionToken).where(AuthActionToken.user_id.in_(user_ids)))
        db.execute(delete(RefreshSession).where(RefreshSession.user_id.in_(user_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    # Give every test its own source address so persisted production-style
    # rate-limit events cannot leak between tests or separate pytest runs.
    transport = ASGITransport(app=app, client=(f"pytest-{uuid.uuid4().hex}", 123))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
