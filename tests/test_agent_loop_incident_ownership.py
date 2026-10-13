import asyncio
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.agents.agent_loop import AgentLoop
from backend.app.models.database import Base, Customer, Incident


def test_agent_loop_rejects_incident_owned_by_another_customer():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    try:
        customer_a = Customer(
            name="Customer A",
            email="a@example.com",
        )
        customer_b = Customer(
            name="Customer B",
            email="b@example.com",
        )
        db.add_all([customer_a, customer_b])
        db.flush()

        incident_b = Incident(
            customer_id=customer_b.id,
            issue="Private issue for Customer B",
            status="open",
        )
        db.add(incident_b)
        db.commit()

        account_result = {
            "success": True,
            "result": {
                "found": True,
                "customer": {"id": customer_a.id},
                "account": {"username": "customer_a"},
            },
            "message": "Account found",
        }

        with (
            patch(
                "backend.app.agents.agent_loop.llm_agent.decide",
                new_callable=AsyncMock,
                return_value={
                    "success": True,
                    "decision": {
                        "intent": "Investigate account",
                        "tool": "get_customer_account",
                    },
                },
            ),
            patch(
                "backend.app.agents.agent_loop.execute_tool",
                new_callable=AsyncMock,
                return_value=account_result,
            ) as mocked_execute,
        ):
            result = asyncio.run(
                AgentLoop().run(
                    db=db,
                    customer_message="Investigate my issue",
                    username="customer_a",
                    incident_id=incident_b.id,
                    permissions={"account.view"},
                )
            )

        assert result["success"] is False
        assert result["status"] == "incident_customer_mismatch"

        executed_tools = [
            call.kwargs.get("tool_name")
            for call in mocked_execute.await_args_list
        ]
        assert "diagnose_incident" not in executed_tools
        assert "unlock_account" not in executed_tools

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
