from unittest.mock import Mock

from backend.app.services import resolution_service


def test_resolution_does_not_close_incident_if_verification_fails(monkeypatch):
    verification = {
        "success": False,
        "verified": False,
        "message": "The specified account does not belong to this incident.",
    }
    verify_mock = Mock(return_value=verification)
    close_mock = Mock()

    monkeypatch.setattr(
        resolution_service,
        "verify_incident_resolution",
        verify_mock,
    )
    monkeypatch.setattr(
        resolution_service,
        "close_incident",
        close_mock,
    )

    result = resolution_service.resolve_incident(
        db=Mock(),
        incident_id=123,
        username="wrong_customer_user",
    )

    assert result["success"] is False
    assert result["resolved"] is False
    assert "does not belong" in result["message"]
    verify_mock.assert_called_once_with(
        db=verify_mock.call_args.kwargs["db"],
        incident_id=123,
        username="wrong_customer_user",
    )
    close_mock.assert_not_called()
