"""
Shared pytest fixtures.

`db_session` gives each test a session inside a transaction that is rolled back
afterwards, so tests can write to the real Supabase database without leaving
any rows behind. Tests that need it are skipped when DATABASE_URL is not set.
"""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.database import check_database_connection, engine


@pytest.fixture(scope="session")
def database_available() -> bool:
    connected, message = check_database_connection()
    if not connected:
        pytest.skip(f"Database not available: {message}")
    return True


TEST_PASSWORD = "Passw0rd-test"


@pytest.fixture
def make_user(db_session):
    """Create an HR account inside the rolled-back test transaction."""
    from app.services.user_service import create_user

    def _make(role: str = "hr", email: str | None = None, password: str = TEST_PASSWORD, name: str = "Test Recruiter"):
        return create_user(db_session, name, email or f"hr-{uuid.uuid4().hex[:10]}@example.com", password, role)

    return _make


@pytest.fixture
def hr_user(make_user):
    return make_user()


@pytest.fixture
def db_session(database_available):
    connection = engine.connect()
    outer_transaction = connection.begin()
    # "create_savepoint": session.commit()/rollback() inside a test only affect a
    # SAVEPOINT; the outer transaction is always rolled back at the end.
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()
