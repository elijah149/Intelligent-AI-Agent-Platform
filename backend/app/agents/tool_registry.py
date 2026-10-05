from backend.app.tools.account_tools import (
    get_customer_account,
    unlock_account,
)
from backend.app.services.incident_service import (
    create_incident,
    update_diagnosis,
    close_incident,
)
from backend.app.services.diagnosis_service import (
    diagnose_incident,
)
from backend.app.services.verification_service import (
    verify_incident_resolution,
)
from backend.app.services.resolution_service import (
    resolve_incident,
)


TOOL_REGISTRY = {
    "get_customer_account": {
        "function": get_customer_account,
        "description": (
            "Retrieve customer and account information "
            "including account status, failed login attempts, "
            "and lock state."
        ),
        "read_only": True,
        "requires_authorization": False,
    },

    "create_incident": {
        "function": create_incident,
        "description": (
            "Create a new customer support incident "
            "for tracking and investigation."
        ),
        "read_only": False,
        "requires_authorization": False,
    },

    "diagnose_incident": {
        "function": diagnose_incident,
        "description": (
            "Investigate an incident using the customer's "
            "actual account state and generate a diagnosis."
        ),
        "read_only": True,
        "requires_authorization": False,
    },

    "unlock_account": {
        "function": unlock_account,
        "description": (
            "Unlock a locked customer account and reset "
            "failed login attempts."
        ),
        "read_only": False,
        "requires_authorization": True,
    },

    "verify_incident_resolution": {
        "function": verify_incident_resolution,
        "description": (
            "Verify whether the customer's account is "
            "actually in the expected state after a corrective action."
        ),
        "read_only": True,
        "requires_authorization": False,
    },

    "resolve_incident": {
        "function": resolve_incident,
        "description": (
            "Resolve an incident after successful verification "
            "that the underlying problem has been fixed."
        ),
        "read_only": False,
        "requires_authorization": False,
    },

    "update_diagnosis": {
        "function": update_diagnosis,
        "description": (
            "Store or update the diagnosis associated with an incident."
        ),
        "read_only": False,
        "requires_authorization": False,
    },

    "close_incident": {
        "function": close_incident,
        "description": (
            "Mark an incident as resolved."
        ),
        "read_only": False,
        "requires_authorization": False,
    },
}


def get_tool(name: str):
    """
    Retrieve a registered tool by name.
    """

    tool = TOOL_REGISTRY.get(name)

    if not tool:
        raise ValueError(
            f"Tool '{name}' is not registered."
        )

    return tool


def list_tools() -> list[dict]:
    """
    Return tool information that can later be provided
    to the AI agent.
    """

    return [
        {
            "name": name,
            "description": tool["description"],
            "read_only": tool["read_only"],
            "requires_authorization": tool["requires_authorization"],
        }
        for name, tool in TOOL_REGISTRY.items()
    ]
