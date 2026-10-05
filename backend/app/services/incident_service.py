from sqlalchemy.orm import Session

from backend.app.models.database import Customer, Incident


def create_incident(
    db: Session,
    customer_id: int,
    issue: str,
) -> Incident:
    """
    Create a new customer incident.
    """

    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id)
        .first()
    )

    if not customer:
        raise ValueError("Customer not found.")

    incident = Incident(
        customer_id=customer_id,
        issue=issue,
        status="open",
    )

    db.add(incident)
    db.commit()
    db.refresh(incident)

    return incident


def update_diagnosis(
    db: Session,
    incident_id: int,
    diagnosis: str,
) -> Incident:
    """
    Store the agent's diagnosis for an incident.
    """

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if not incident:
        raise ValueError("Incident not found.")

    incident.diagnosis = diagnosis
    incident.status = "diagnosed"

    db.commit()
    db.refresh(incident)

    return incident


def close_incident(
    db: Session,
    incident_id: int,
) -> Incident:
    """
    Mark an incident as resolved.
    """

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if not incident:
        raise ValueError("Incident not found.")

    incident.status = "resolved"

    db.commit()
    db.refresh(incident)

    return incident
