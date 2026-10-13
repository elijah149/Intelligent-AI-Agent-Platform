from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.database import Base, Customer, Incident


def test_incident_belongs_to_expected_customer():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    try:
        customer_a = Customer(
            name="Customer A",
            email="customer-a@example.com",
        )
        customer_b = Customer(
            name="Customer B",
            email="customer-b@example.com",
        )
        db.add_all([customer_a, customer_b])
        db.flush()

        incident_a = Incident(
            customer_id=customer_a.id,
            issue="Cannot log in",
            status="open",
        )
        incident_b = Incident(
            customer_id=customer_b.id,
            issue="Account locked",
            status="open",
        )
        db.add_all([incident_a, incident_b])
        db.commit()

        from backend.app.agents.agent_loop import (
            incident_belongs_to_customer,
        )

        assert incident_belongs_to_customer(
            db, incident_a.id, customer_a.id
        ) is True

        assert incident_belongs_to_customer(
            db, incident_b.id, customer_a.id
        ) is False

        assert incident_belongs_to_customer(
            db, 999999, customer_a.id
        ) is False
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
