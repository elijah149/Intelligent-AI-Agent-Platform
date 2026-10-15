from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.database import (
    Base,
    Customer,
    Account,
    Incident,
    User,
    LoginAuditLog,
)
from backend.app.services.diagnosis_service import diagnose_incident


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    session = TestingSession()

    customer = Customer(
        name="Diagnosis Test Customer",
        email="diagnosis-test@example.com",
    )
    session.add(customer)
    session.flush()

    account = Account(
        customer_id=customer.id,
        username="diagnosis_test_user",
        status="active",
        failed_login_attempts=0,
        is_locked=False,
    )
    incident = Incident(
        customer_id=customer.id,
        issue="Customer cannot log in.",
        status="open",
    )
    session.add_all([account, incident])
    session.commit()

    try:
        yield session, customer, account, incident
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_missing_incident_is_rejected(db):
    session, _, _, _ = db

    result = diagnose_incident(
        db=session,
        incident_id=999999,
        username="diagnosis_test_user",
    )

    assert result["success"] is False
    assert result["message"] == "Incident not found."


def test_account_from_another_customer_is_rejected(db):
    session, _, _, incident = db
    other_customer = Customer(
        name="Other Diagnosis Customer",
        email="other-diagnosis@example.com",
    )
    session.add(other_customer)
    session.flush()
    other_account = Account(
        customer_id=other_customer.id,
        username="other_diagnosis_user",
        status="locked",
        failed_login_attempts=5,
        is_locked=True,
    )
    session.add(other_account)
    session.commit()

    result = diagnose_incident(
        db=session,
        incident_id=incident.id,
        username=other_account.username,
    )

    assert result["success"] is False
    assert "does not belong" in result["message"]
    assert other_account.is_locked is True


def test_active_account_with_old_failures_is_not_reported_locked(db):
    session, _, account, incident = db
    session.add(
        LoginAuditLog(
            username=account.username,
            event="LOGIN_FAILED",
            success=False,
            created_at=datetime.now() - timedelta(days=1),
        )
    )
    session.commit()

    result = diagnose_incident(
        db=session,
        incident_id=incident.id,
        username=account.username,
    )

    assert result["success"] is True
    assert result["root_cause"] == "No current account-level cause was confirmed."
    assert result["recommended_action"] == "further_investigation"
    assert account.is_locked is False
    assert account.status == "active"
    assert any("historical" in item.lower() for item in result["evidence"])
    assert incident.status == "diagnosed"


def test_current_account_lock_is_detected_without_unlocking(db):
    session, _, account, incident = db
    account.status = "locked"
    account.is_locked = True
    account.failed_login_attempts = 5
    session.commit()

    result = diagnose_incident(
        db=session,
        incident_id=incident.id,
        username=account.username,
    )

    assert result["success"] is True
    assert result["recommended_action"] == "unlock_account"
    assert account.is_locked is True
    assert account.status == "locked"
    assert account.failed_login_attempts == 5


def test_current_user_lock_is_detected_without_changing_user(db):
    session, _, account, incident = db
    user = User(
        username=account.username,
        password_hash="test-hash",
        role="customer",
        is_active=True,
        failed_login_attempts=5,
        locked_until=datetime.now() + timedelta(minutes=10),
    )
    session.add(user)
    session.commit()
    original_lock_time = user.locked_until

    result = diagnose_incident(
        db=session,
        incident_id=incident.id,
        username=account.username,
    )

    assert result["success"] is True
    assert result["user_locked"] is True
    assert result["recommended_action"] == "review_account_unlock"
    assert user.locked_until == original_lock_time
    assert user.failed_login_attempts == 5
    assert account.is_locked is False
