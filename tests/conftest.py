import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from saas_core.db.base import Base
from saas_core.db.session import get_db
from saas_core.config.settings import SaasSettings, get_saas_settings

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_settings():
    return SaasSettings(
        DATABASE_URL=TEST_DATABASE_URL,
        TRIAL_HASH_SECRET="test-secret-key-12345",
        TRIAL_ENABLED=True,
        TRIAL_CREDITS=10,
        TRIAL_DURATION_DAYS=3,
        BILLING_ENABLED=True,
        EMAIL_ENABLED=True,
        TURNSTILE_ENABLED=False
    )


from sqlalchemy.pool import StaticPool

@pytest.fixture(scope="function")
def db_session(test_settings):
    engine = create_engine(
        test_settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
