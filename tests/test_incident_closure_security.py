import pytest

from backend.app.services.incident_service import close_incident


def test_close_incident_requires_verification_token():
    with pytest.raises(
        PermissionError,
        match="successful resolution verification",
    ):
        close_incident(
            db=None,
            incident_id=123,
        )


def test_close_incident_rejects_fake_verification_token():
    with pytest.raises(
        PermissionError,
        match="successful resolution verification",
    ):
        close_incident(
            db=None,
            incident_id=123,
            verification_token=True,
        )
