import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.database import (
    Account,
    AgentAction,
    Base,
    Customer,
    Incident,
)
from backend.app.agents.incident_agent import run_account_recovery_agent


ALL_RECOVERY_PERMISSIONS = {
    "incident.create",
    "incident.diagnose",
    "account.unlock",
    "incident.verify",
    "incident.resolve",
}


@pytest.fixture
def db():
    """Create an isolated in-memory SQLite database for each test."""
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

    try:
        customer = Customer(
            name="Integration Test Customer",
            email="integration@example.test",
        )
        session.add(customer)
        session.flush()

        session.add_all([
            Account(
                customer_id=customer.id,
                username="target_user",
                status="locked",
                failed_login_attempts=5,
                is_locked=True,
            ),
            Account(
                customer_id=customer.id,
                username="other_user",
                status="active",
                failed_login_attempts=0,
                is_locked=False,
            ),
        ])

        session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_recovery_workflow_completes_with_explicit_permissions(db):
    customer = db.query(Customer).filter_by(
        email="integration@example.test"
    ).one()

    result = run_account_recovery_agent(
        db=db,
        customer_id=customer.id,
        username="target_user",
        issue="Cannot log in because the account is locked.",
        authorized=True,
        permissions=ALL_RECOVERY_PERMISSIONS,
        performed_by="support_agent",
    )

    target = db.query(Account).filter_by(
        username="target_user"
    ).one()
    other = db.query(Account).filter_by(
        username="other_user"
    ).one()
    incident = db.query(Incident).filter_by(
        id=result["incident_id"]
    ).one()
    actions = db.query(AgentAction).filter_by(
        incident_id=incident.id
    ).all()

    assert result["success"] is True
    assert result["stage"] == "resolved"
    assert result["status"] == "resolved"

    assert target.is_locked is False
    assert target.status == "active"
    assert target.failed_login_attempts == 0

    assert other.is_locked is False
    assert other.status == "active"
    assert other.failed_login_attempts == 0

    assert incident.customer_id == customer.id
    assert incident.status == "resolved"
    assert incident.diagnosis is not None

    assert any(
        action.action == "unlock_account" and action.success
        for action in actions
    )


@pytest.mark.parametrize("authorized", [True, False])
def test_legacy_authorized_boolean_alone_cannot_unlock(db, authorized):
    customer = db.query(Customer).filter_by(
        email="integration@example.test"
    ).one()

    result = run_account_recovery_agent(
        db=db,
        customer_id=customer.id,
        username="target_user",
        issue="Cannot log in because the account is locked.",
        authorized=authorized,
    )

    target = db.query(Account).filter_by(
        username="target_user"
    ).one()

    assert result["success"] is False
    assert result["stage"] == "authorization"
    assert "incident_id" not in result

    assert target.is_locked is True
    assert target.status == "locked"
    assert target.failed_login_attempts == 5

    # Without incident.create permission, no incident should be created.
    assert db.query(Incident).count() == 0
    assert db.query(AgentAction).count() == 0


def test_missing_unlock_permission_does_not_unlock_account(db):
    customer = db.query(Customer).filter_by(
        email="integration@example.test"
    ).one()
    permissions = ALL_RECOVERY_PERMISSIONS - {"account.unlock"}

    result = run_account_recovery_agent(
        db=db,
        customer_id=customer.id,
        username="target_user",
        issue="Cannot log in because the account is locked.",
        permissions=permissions,
    )

    target = db.query(Account).filter_by(
        username="target_user"
    ).one()

    assert result["success"] is False
    assert result["stage"] == "authorization"
    assert target.is_locked is True
    assert target.status == "locked"
    assert target.failed_login_attempts == 5

    incident = db.query(Incident).filter_by(
        id=result["incident_id"]
    ).one()
    assert incident.status != "resolved"

    assert not db.query(AgentAction).filter_by(
        incident_id=incident.id,
        action="unlock_account",
        success=True,
    ).first()
