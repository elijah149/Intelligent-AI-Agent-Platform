from sqlalchemy.orm import Session

from backend.app.models.database import LoginAuditLog


def log_login_event(
    db: Session,
    username: str,
    event: str,
    success: bool,
) -> None:

    audit_log = LoginAuditLog(
        username=username,
        event=event,
        success=success,
    )

    db.add(audit_log)
    db.commit()
