import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.database import (
    Base,
    Customer,
    Account,
    Incident,
    AgentAction,
)
from backend.app.tools.account_tools import unlock_account


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

    customer = Customer(
        name="Test Customer",
        email="unlock-test@example.com",
    )
    session.add(customer)
    session.flush()

    account = Account(
        customer_id=customer.id,
        username="unlock_test_user",
        status="locked",
        failed_login_attempts=5,
        is_locked=True,
    )
    session.add(account)
    session.flush()

    incident = Incident(
        customer_id=customer.id,
        issue="Customer cannot log in.",
        status="open",
    )
    session.add(incident)
    session.commit()

    try:
        yield session, incident.id
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_unlock_is_denied_without_authorization(db):
    session, incident_id = db

    result = unlock_account(
        db=session,
        username="unlock_test_user",
        incident_id=incident_id,
        authorized=False,
        performed_by="support_test",
    )

    account = session.query(Account).filter_by(
        username="unlock_test_user"
    ).one()

    assert result["success"] is False
    assert account.is_locked is True
    assert account.failed_login_attempts == 5

    successful_actions = session.query(AgentAction).filter_by(
        incident_id=incident_id,
        action="unlock_account",
        success=True,
    ).count()

    assert successful_actions == 0


def test_authorized_unlock_is_audited(db):
    session, incident_id = db

    result = unlock_account(
        db=session,
        username="unlock_test_user",
        incident_id=incident_id,
        authorized=True,
        performed_by="support_test",
    )

    account = session.query(Account).filter_by(
        username="unlock_test_user"
    ).one()

    action = session.query(AgentAction).filter_by(
        incident_id=incident_id,
        action="unlock_account",
    ).one()

    assert result["success"] is True
    assert account.is_locked is False
    assert account.status == "active"
    assert account.failed_login_attempts == 0
    assert action.performed_by == "support_test"
    assert action.success is True


def test_unlock_rejects_missing_incident(db):
    session, _ = db

    result = unlock_account(
        db=session,
        username="unlock_test_user",
        incident_id=999999,
        authorized=True,
        performed_by="support_test",
    )

    account = session.query(Account).filter_by(
        username="unlock_test_user"
    ).one()

    assert result["success"] is False
    assert account.is_locked is True


def test_unlock_rejects_incident_from_another_customer(db):
    session, incident_id = db

    other_customer = Customer(
        name="Other Test Customer",
        email="other-unlock-test@example.com",
    )
    session.add(other_customer)
    session.flush()

    other_account = Account(
        customer_id=other_customer.id,
        username="other_unlock_test_user",
        status="locked",
        failed_login_attempts=4,
        is_locked=True,
    )
    session.add(other_account)
    session.commit()

    result = unlock_account(
        db=session,
        username="other_unlock_test_user",
        incident_id=incident_id,
        authorized=True,
        performed_by="support_test",
    )

    session.refresh(other_account)

    assert result["success"] is False
    assert "does not belong" in result["message"]
    assert other_account.is_locked is True
    assert other_account.status == "locked"
    assert other_account.failed_login_attempts == 4

    successful_actions = session.query(AgentAction).filter_by(
        incident_id=incident_id,
        action="unlock_account",
        success=True,
    ).count()

    assert successful_actions == 0
