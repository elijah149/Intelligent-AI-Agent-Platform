from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.core.dependencies import get_db
from backend.app.main import app
from backend.app.models.database import Base, Customer, User


client = TestClient(app)


def fake_user(role: str) -> User:
    return User(
        id=1,
        username=f"test_{role}",
        password_hash="not-a-real-password-hash",
        role=role,
        is_active=True,
    )


def override_user(role: str):
    app.dependency_overrides[get_current_user] = (
        lambda: fake_user(role)
    )


def setup_test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()

    customer = Customer(
        name="Test Customer",
        email="test-customer@example.com",
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    return engine, db, customer


def test_customer_cannot_create_incident():
    override_user("customer")

    try:
        response = client.post(
            "/incidents",
            json={
                "customer_id": 1,
                "issue": "Unable to log in",
            },
        )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_customer_cannot_view_incident():
    override_user("customer")

    try:
        response = client.get("/incidents/123")

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_incident_view_requires_authentication():
    app.dependency_overrides.clear()

    response = client.get("/incidents/123")

    assert response.status_code == 401


def test_support_agent_gets_404_for_missing_incident():
    engine, db, _customer = setup_test_db()
    override_user("support_agent")
    app.dependency_overrides[get_db] = lambda: db

    try:
        response = client.get("/incidents/999999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Incident not found."
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_support_agent_can_create_incident_for_existing_customer():
    engine, db, customer = setup_test_db()
    override_user("support_agent")
    app.dependency_overrides[get_db] = lambda: db

    try:
        response = client.post(
            "/incidents",
            json={
                "customer_id": customer.id,
                "issue": "Unable to log in",
            },
        )

        assert response.status_code == 201

        data = response.json()
        assert data["customer_id"] == customer.id
        assert data["issue"] == "Unable to log in"
        assert data["status"] == "open"
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
