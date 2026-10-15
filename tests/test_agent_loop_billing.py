import asyncio
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.agents.agent_loop import AgentLoop
from backend.app.models.database import Base, Customer, Account, Invoice


def make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    customer = Customer(
        name="Billing Test Customer",
        email="billing-test@example.com",
    )
    db.add(customer)
    db.flush()

    account = Account(
        customer_id=customer.id,
        username="billing_test_user",
        status="active",
    )
    db.add(account)
    db.flush()

    invoice = Invoice(
        customer_id=customer.id,
        invoice_number="INV-DEMO-001",
        amount_cents=150000,
        currency="TZS",
        invoice_status="unpaid",
        payment_status="paid",
    )
    db.add(invoice)
    db.commit()

    return engine, db


def test_agent_loop_returns_billing_discrepancy():
    engine, db = make_db()

    try:
        with (
            patch(
                "backend.app.agents.agent_loop.llm_agent.decide",
                new_callable=AsyncMock,
                return_value={
                    "success": True,
                    "decision": {
                        "intent": "Investigate invoice",
                        "tool": "none",
                    },
                },
            ),
        ):
            result = asyncio.run(
                AgentLoop().run(
                    db=db,
                    customer_message="Please check invoice INV-DEMO-001",
                    username="billing_test_user",
                    permissions={"billing.view"},
                )
            )

        assert result["success"] is True
        assert result["status"] == "completed"
        assert result["tool"] == "lookup_invoice"
        assert result["invoice"]["invoice_number"] == "INV-DEMO-001"
        assert result["invoice"]["payment_status"] == "paid"
        assert result["invoice"]["invoice_status"] == "unpaid"
        assert result["invoice"]["paid_but_unpaid_invoice"] is True
        assert "billing discrepancy" in result["message"]

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_agent_loop_denies_billing_without_permission():
    engine, db = make_db()

    try:
        with (
            patch(
                "backend.app.agents.agent_loop.llm_agent.decide",
                new_callable=AsyncMock,
                return_value={
                    "success": True,
                    "decision": {
                        "intent": "Investigate invoice",
                        "tool": "none",
                    },
                },
            ),
        ):
            result = asyncio.run(
                AgentLoop().run(
                    db=db,
                    customer_message="Please check invoice INV-DEMO-001",
                    username="billing_test_user",
                    permissions={"account.view"},
                )
            )

        assert result["success"] is True
        assert result["status"] == "policy_blocked"
        assert result["tool"] == "lookup_invoice"
        assert "invoice" not in result

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
