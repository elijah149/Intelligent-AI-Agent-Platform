from types import SimpleNamespace
from unittest.mock import Mock

from backend.app.agents import incident_agent


ALL_RECOVERY_PERMISSIONS = {
    "incident.create",
    "incident.diagnose",
    "account.unlock",
    "incident.verify",
    "incident.resolve",
}


def test_recovery_agent_does_not_unlock_without_authorization(monkeypatch):
    unlock_account = Mock()
    monkeypatch.setattr(incident_agent, "unlock_account", unlock_account)

    result = incident_agent.run_account_recovery_agent(
        db=Mock(),
        customer_id=1,
        username="test_user",
        issue="Cannot log in",
        authorized=True,
    )

    assert result["success"] is False
    assert result["stage"] == "authorization"
    unlock_account.assert_not_called()


def test_recovery_agent_requires_explicit_approval_even_with_unlock_permission(
    monkeypatch,
):
    monkeypatch.setattr(
        incident_agent,
        "create_incident",
        Mock(return_value=SimpleNamespace(id=123)),
    )
    monkeypatch.setattr(
        incident_agent,
        "diagnose_incident",
        Mock(
            return_value={
                "success": True,
                "diagnosis": "Account is locked.",
                "account": {"is_locked": True},
            }
        ),
    )

    unlock_account = Mock(
        return_value={"success": True, "message": "Account unlocked."}
    )
    monkeypatch.setattr(incident_agent, "unlock_account", unlock_account)

    result = incident_agent.run_account_recovery_agent(
        db=Mock(),
        customer_id=1,
        username="test_user",
        issue="Cannot log in",
        authorized=False,
        permissions=ALL_RECOVERY_PERMISSIONS,
        performed_by="support_agent",
    )

    assert result["success"] is True
    assert result["stage"] == "authorization"
    assert result["status"] == "awaiting_authorization"
    assert result["incident_id"] == 123
    unlock_account.assert_not_called()


def test_recovery_agent_stops_when_user_is_locked_but_account_is_active(
    monkeypatch,
):
    monkeypatch.setattr(
        incident_agent,
        "create_incident",
        Mock(return_value=SimpleNamespace(id=456)),
    )
    monkeypatch.setattr(
        incident_agent,
        "diagnose_incident",
        Mock(return_value={
            "success": True,
            "diagnosis": "User is locked; Account is active.",
            "account": {"is_locked": False, "status": "active"},
            "user_locked": True,
            "user_active": True,
        }),
    )
    unlock = Mock()
    monkeypatch.setattr(incident_agent, "unlock_account", unlock)

    result = incident_agent.run_account_recovery_agent(
        db=Mock(),
        customer_id=1,
        username="test_user",
        issue="Cannot log in",
        authorized=True,
        permissions=ALL_RECOVERY_PERMISSIONS,
        performed_by="support_agent",
    )

    assert result["success"] is False
    assert result["stage"] == "diagnosis"
    assert result["incident_id"] == 456
    assert "User record is locked or inactive" in result["message"]
    unlock.assert_not_called()


def test_recovery_agent_stops_when_user_is_inactive(
    monkeypatch,
):
    monkeypatch.setattr(
        incident_agent,
        "create_incident",
        Mock(return_value=SimpleNamespace(id=457)),
    )
    monkeypatch.setattr(
        incident_agent,
        "diagnose_incident",
        Mock(return_value={
            "success": True,
            "diagnosis": "User is inactive.",
            "account": {"is_locked": True, "status": "locked"},
            "user_locked": False,
            "user_active": False,
        }),
    )
    unlock = Mock()
    monkeypatch.setattr(incident_agent, "unlock_account", unlock)

    result = incident_agent.run_account_recovery_agent(
        db=Mock(),
        customer_id=1,
        username="test_user",
        issue="Cannot log in",
        authorized=True,
        permissions=ALL_RECOVERY_PERMISSIONS,
        performed_by="support_agent",
    )

    assert result["success"] is False
    assert result["stage"] == "diagnosis"
    unlock.assert_not_called()
