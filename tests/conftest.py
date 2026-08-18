import sys
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.db.session as db_session
from src.db.models import Base, Interaction, Medication, MedicationAlias, Product
from src.db.session import get_db
from src.main import app


def _seed_reference_data(session_factory) -> None:
    """Dữ liệu tối thiểu nhiều test trong test_routes.py cần sẵn có (Warfarin +
    Acetylsalicylic acid mức "nang", 2 sản phẩm tra theo tên) - trước đây các test
    này ngầm dựa vào dữ liệu DDInter thật đã có sẵn trong Neon, giờ DB test biệt
    lập rỗng nên phải tự seed lại đúng phần cần dùng."""
    db = session_factory()
    try:
        warfarin = Medication(ten_chuan_hoa="Warfarin")
        acid = Medication(ten_chuan_hoa="Acetylsalicylic acid")
        db.add_all([warfarin, acid])
        db.flush()

        db.add_all(
            [
                MedicationAlias(alias="asp", medication_id=acid.id),
                MedicationAlias(alias="aspirin", medication_id=acid.id),
            ]
        )

        id_a, id_b = sorted([warfarin.id, acid.id])
        db.add(
            Interaction(
                medication_a_id=id_a,
                medication_b_id=id_b,
                muc_do="nang",
                mo_ta="Test: tang nguy co chay mau khi dung dong thoi.",
                xu_tri="Test: theo doi INR chat che, can nhac dieu chinh boi bac si.",
                nguon_trich_dan="DDInter 2.0 (du lieu test)",
            )
        )

        db.add_all(
            [
                Product(ten_thuoc="Ibuprofen", loai="khong_ke_don"),
                Product(ten_thuoc="Paracetamol", loai="khong_ke_don"),
            ]
        )
        db.commit()
    finally:
        db.close()


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints.

    Dùng SQLite in-memory biệt lập cho từng test (không đọc/ghi DATABASE_URL thật)
    - trước đây fixture này gọi thẳng vào Neon DB thật và không dọn dẹp, để lại
    user/đơn thuốc/review rác sau mỗi lần chạy test suite.

    Override get_db lo được mọi route qua Depends, nhưng vài chỗ (2 tool của agent
    trong src/agents/tools/, và chính test_routes.py khi tự tạo dữ liệu setup) làm
    `from src.db.session import SessionLocal` - import theo GIÁ TRỊ nên không đi qua
    Depends, không bị override ở trên chạm tới. Quét sys.modules, patch lại
    SessionLocal ở TẤT CẢ module đã import nó theo cách này (thay vì liệt kê tay
    từng module, dễ sót nếu sau này có thêm chỗ dùng SessionLocal trực tiếp).
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    _seed_reference_data(testing_session)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    original_session_local = db_session.SessionLocal
    patched_modules = [
        mod
        for mod in list(sys.modules.values())
        if mod is not None and getattr(mod, "SessionLocal", None) is original_session_local
    ]
    for mod in patched_modules:
        mod.SessionLocal = testing_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)
        for mod in patched_modules:
            mod.SessionLocal = original_session_local
        engine.dispose()


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
