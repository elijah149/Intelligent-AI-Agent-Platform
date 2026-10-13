import pytest

from backend.app.agents.authorization import AuthorizationPolicy
from backend.app.agents.tool_registry import get_tool


@pytest.fixture
def policy():
    return AuthorizationPolicy()


def test_account_investigation_requires_account_view_permission(policy):
    assert policy.can_execute(
        "get_customer_account", permissions=set()
    ) is False
    assert policy.can_execute(
        "get_customer_account", permissions={"account.view"}
    ) is True


def test_unlock_account_requires_specific_permission(policy):
    assert policy.can_execute(
        "unlock_account",
        permissions=set(),
    ) is False

    assert policy.can_execute(
        "unlock_account",
        permissions={"account.unlock"},
    ) is True


def test_legacy_authorized_boolean_grants_no_permissions(policy):
    assert policy.can_execute(
        "unlock_account",
        authorized=True,
        permissions=set(),
    ) is False

    assert policy.can_execute(
        "resolve_incident",
        authorized=True,
        permissions=set(),
    ) is False

    assert policy.can_execute(
        "update_diagnosis",
        authorized=True,
        permissions=set(),
    ) is False

    assert policy.can_execute(
        "call_rest_api",
        authorized=True,
        permissions=set(),
    ) is False


@pytest.mark.parametrize(
    ("tool_name", "permission"),
    [
        ("diagnose_incident", "incident.diagnose"),
        ("update_diagnosis", "incident.diagnose"),
        ("verify_incident_resolution", "incident.verify"),
        ("resolve_incident", "incident.resolve"),
        ("call_rest_api", "integration.call_api"),
    ],
)
def test_each_protected_tool_requires_its_own_permission(
    policy,
    tool_name,
    permission,
):
    assert policy.can_execute(
        tool_name,
        permissions=set(),
    ) is False

    assert policy.can_execute(
        tool_name,
        permissions={permission},
    ) is True


def test_permission_for_one_action_does_not_authorize_another(policy):
    assert policy.can_execute(
        "resolve_incident",
        permissions={"account.unlock"},
    ) is False

    assert policy.can_execute(
        "unlock_account",
        permissions={"incident.resolve"},
    ) is False

    assert policy.can_execute(
        "verify_incident_resolution",
        permissions={"incident.resolve"},
    ) is False


def test_close_incident_is_not_registered_as_an_ai_tool():
    with pytest.raises(ValueError, match="not registered"):
        get_tool("close_incident")


def test_create_incident_requires_incident_create_permission(policy):
    assert policy.can_execute(
        "create_incident", permissions=set()
    ) is False
    assert policy.can_execute(
        "create_incident", permissions={"incident.create"}
    ) is True
