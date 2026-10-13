from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.app.auth.security import (
    create_access_token,
    verify_password,
)
from backend.app.models.database import User
from backend.app.services.login_audit_service import log_login_event


MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User | None:

    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if user is None:
        log_login_event(
            db=db,
            username=username,
            event="LOGIN_FAILED",
            success=False,
        )
        return None

    if not user.is_active:
        log_login_event(
            db=db,
            username=username,
            event="LOGIN_FAILED",
            success=False,
        )
        return None

    now = datetime.now()

    # Check temporary account lock.
    if user.locked_until is not None:

        if user.locked_until > now:
            log_login_event(
                db=db,
                username=username,
                event="LOGIN_FAILED",
                success=False,
            )
            return None

        # Lockout has expired.
        user.locked_until = None
        user.failed_login_attempts = 0
        db.commit()

    # Verify password.
    if not verify_password(
        password,
        user.password_hash,
    ):
        user.failed_login_attempts += 1

        log_login_event(
            db=db,
            username=username,
            event="LOGIN_FAILED",
            success=False,
        )

        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = (
                datetime.now()
                + timedelta(minutes=LOCKOUT_MINUTES)
            )

            log_login_event(
                db=db,
                username=username,
                event="ACCOUNT_LOCKED",
                success=False,
            )
        else:
            db.commit()

        return None

    # Successful login.
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    log_login_event(
        db=db,
        username=username,
        event="LOGIN_SUCCESS",
        success=True,
    )

    return user


def create_user_token(user: User) -> str:

    return create_access_token(
        {
            "sub": user.username,
            "role": user.role,
            "user_id": user.id,
        }
    )
