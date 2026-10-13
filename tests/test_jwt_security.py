from jose import JWTError

from backend.app.auth.security import (
    create_access_token,
    decode_access_token,
)


def test_valid_token_can_be_decoded():
    token = create_access_token(
        {"sub": "test_user", "role": "support_agent"}
    )

    payload = decode_access_token(token)

    assert payload["sub"] == "test_user"
    assert payload["role"] == "support_agent"
    assert "exp" in payload


def test_expired_token_is_rejected():
    token = create_access_token(
        {"sub": "test_user"},
        expires_minutes=-1,
    )

    try:
        decode_access_token(token)
    except JWTError:
        pass
    else:
        raise AssertionError("An expired token was accepted.")
