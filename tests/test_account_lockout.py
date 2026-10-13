from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.database import Base, User, LoginAuditLog
from backend.app.auth.security import hash_password
from backend.app.services.auth_service import authenticate_user


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    session = TestingSession()

    user = User(
        username="lockout_test_user",
        password_hash=hash_password("CorrectPassword123!"),
        role="support_agent",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
    )
    session.add(user)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_five_failed_logins_lock_account(db):
    for _ in range(5):
        result = authenticate_user(
            db=db,
            username="lockout_test_user",
            password="WrongPassword!",
        )
        assert result is None

    user = db.query(User).filter_by(
        username="lockout_test_user"
    ).first()

    assert user.failed_login_attempts == 5
    assert user.locked_until is not None
    assert user.locked_until > datetime.now()

    lock_event = db.query(LoginAuditLog).filter_by(
        username="lockout_test_user",
        event="ACCOUNT_LOCKED",
    ).first()
    assert lock_event is not None


def test_locked_account_rejects_correct_password(db):
    user = db.query(User).filter_by(
        username="lockout_test_user"
    ).first()
    user.failed_login_attempts = 5
    user.locked_until = datetime.now() + timedelta(minutes=15)
    db.commit()

    result = authenticate_user(
        db=db,
        username="lockout_test_user",
        password="CorrectPassword123!",
    )

    assert result is None


def test_expired_lockout_allows_correct_password(db):
    user = db.query(User).filter_by(
        username="lockout_test_user"
    ).first()
    user.failed_login_attempts = 5
    user.locked_until = datetime.now() - timedelta(seconds=1)
    db.commit()

    result = authenticate_user(
        db=db,
        username="lockout_test_user",
        password="CorrectPassword123!",
    )

    assert result is not None
    assert result.username == "lockout_test_user"
    assert result.failed_login_attempts == 0
    assert result.locked_until is None


def test_successful_login_resets_failed_attempts(db):
    user = db.query(User).filter_by(
        username="lockout_test_user"
    ).first()
    user.failed_login_attempts = 3
    db.commit()

    result = authenticate_user(
        db=db,
        username="lockout_test_user",
        password="CorrectPassword123!",
    )

    assert result is not None
    assert result.failed_login_attempts == 0
    assert result.locked_until is None
