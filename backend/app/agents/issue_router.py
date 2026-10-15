"""Choose a safe initial workflow for customer support issues."""

ACCOUNT_WORKFLOW_CATEGORIES = {"account_access"}


def route_issue(classification: dict) -> dict:
    category = classification.get("category", "unknown")
    needs_clarification = classification.get(
        "needs_clarification", False
    )

    if needs_clarification or category in {
        "unknown",
        "multiple_issues",
    }:
        return {
            "workflow": "clarify",
            "category": category,
            "needs_clarification": True,
        }

    if category in ACCOUNT_WORKFLOW_CATEGORIES:
        return {
            "workflow": "account_investigation",
            "category": category,
            "needs_clarification": False,
        }

    if category == "billing":
        return {
            "workflow": "billing_investigation",
            "category": category,
            "needs_clarification": False,
        }

    if category in {
        "technical",
        "service_request",
        "general_support",
    }:
        return {
            "workflow": "incident_support",
            "category": category,
            "needs_clarification": False,
        }

    return {
        "workflow": "clarify",
        "category": category,
        "needs_clarification": True,
    }
