"""Read-only tools for investigating demo billing records."""

from sqlalchemy.orm import Session
from backend.app.models.database import Account, Invoice


def lookup_invoice(
    db: Session,
    username: str,
    invoice_number: str,
) -> dict:
    """Look up an invoice belonging to the customer's account."""

    account = (
        db.query(Account)
        .filter(Account.username == username)
        .first()
    )

    if account is None:
        return {"found": False, "message": "Account or invoice not found."}

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.invoice_number == invoice_number,
            Invoice.customer_id == account.customer_id,
        )
        .first()
    )

    if invoice is None:
        return {"found": False, "message": "Account or invoice not found."}

    mismatch = (
        invoice.payment_status.lower() == "paid"
        and invoice.invoice_status.lower() == "unpaid"
    )

    return {
        "found": True,
        "invoice_number": invoice.invoice_number,
        "amount_cents": invoice.amount_cents,
        "currency": invoice.currency,
        "invoice_status": invoice.invoice_status,
        "payment_status": invoice.payment_status,
        "paid_but_unpaid_invoice": mismatch,
        "evidence": (
            "Payment is marked paid but invoice is marked unpaid."
            if mismatch
            else "No paid-but-unpaid mismatch was detected."
        ),
    }
