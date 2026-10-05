from sqlalchemy.orm import Session

from backend.app.models.database import Customer, Account, AgentAction


def get_customer_account(
    db: Session,
    username: str,
) -> dict:
    """
    Retrieve a customer's account information from the database.
    """

    account = (
        db.query(Account)
        .filter(Account.username == username)
        .first()
    )

    if not account:
        return {
            "found": False,
            "message": "Account not found.",
        }

    customer = (
        db.query(Customer)
        .filter(Customer.id == account.customer_id)
        .first()
    )

    if not customer:
        return {
            "found": False,
            "message": "Customer associated with this account was not found.",
        }

    return {
        "found": True,
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
        },
        "account": {
            "id": account.id,
            "username": account.username,
            "status": account.status,
            "failed_login_attempts": account.failed_login_attempts,
            "is_locked": account.is_locked,
        },
    }


def unlock_account(
    db: Session,
    username: str,
    incident_id: int,
    authorized: bool = False,
) -> dict:
    """
    Unlock a customer account.

    The action is only performed when explicitly authorized.
    Every successful action is recorded in agent_actions.
    """

    if not authorized:
        return {
            "success": False,
            "message": "Account unlock was not authorized.",
        }

    account = (
        db.query(Account)
        .filter(Account.username == username)
        .first()
    )

    if not account:
        return {
            "success": False,
            "message": "Account not found.",
        }

    if not account.is_locked:
        return {
            "success": False,
            "message": "Account is already unlocked.",
        }

    account.is_locked = False
    account.status = "active"
    account.failed_login_attempts = 0

    action = AgentAction(
        incident_id=incident_id,
        action="unlock_account",
        result=f"Account '{username}' was successfully unlocked.",
        success=True,
    )

    db.add(action)
    db.commit()

    return {
        "success": True,
        "message": f"Account '{username}' was successfully unlocked.",
    }
