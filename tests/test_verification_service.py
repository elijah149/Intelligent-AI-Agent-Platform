import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.database import Base, Customer, Account, Incident
from backend.app.services.verification_service import verify_incident_resolution


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    customer = Customer(
        name="Verification Customer",
        email="verification@example.com",
    )
    session.add(customer)
    session.flush()

    account = Account(
        customer_id=customer.id,
        username="verification_user",
        status="active",
        failed_login_attempts=0,
        is_locked=False,
    )
    incident = Incident(
        customer_id=customer.id,
        issue="Cannot log in",
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


def test_verification_checks_the_requested_account(db):
    session, customer, account, incident = db

    # The customer has a second, still-locked account.
    other_account = Account(
        customer_id=customer.id,
        username="verification_other_user",
        status="locked",
        failed_login_attempts=5,
        is_locked=True,
    )
    session.add(other_account)
    session.commit()

    result = verify_incident_resolution(
        session, incident.id, username=account.username
    )

    assert result["success"] is True
    assert result["verified"] is True
    assert result["account"]["username"] == "verification_user"


def test_verification_rejects_account_from_another_customer(db):
    session, _, _, incident = db

    other_customer = Customer(
        name="Another Customer",
        email="verification-other@example.com",
    )
    session.add(other_customer)
    session.flush()

    other_account = Account(
        customer_id=other_customer.id,
        username="foreign_verification_user",
        status="active",
        failed_login_attempts=0,
        is_locked=False,
    )
    session.add(other_account)
    session.commit()

    result = verify_incident_resolution(
        session,
        incident.id,
        username=other_account.username,
    )

    assert result["success"] is False
    assert result["verified"] is False
    assert "does not belong" in result["message"]


def test_verification_fails_if_requested_account_is_still_locked(db):
    session, _, account, incident = db

    account.status = "locked"
    account.failed_login_attempts = 5
    account.is_locked = True
    session.commit()

    result = verify_incident_resolution(
        session, incident.id, username=account.username
    )

    assert result["success"] is True
    assert result["verified"] is False


def test_verification_rejects_missing_incident(db):
    session, _, account, _ = db

    result = verify_incident_resolution(
        session, 999999, username=account.username
    )

    assert result["success"] is False
    assert result["verified"] is False
    assert result["message"] == "Incident not found."
