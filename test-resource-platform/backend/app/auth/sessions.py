from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest, new
from json import dumps, loads


def _encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(value + padding)


def issue_session_token(user_id: int, secret_key: str, max_age_seconds: int) -> str:
    expires_at = datetime.now(UTC) + timedelta(seconds=max_age_seconds)
    payload = dumps(
        {"sub": user_id, "exp": int(expires_at.timestamp())},
        separators=(",", ":"),
    ).encode("utf-8")
    encoded_payload = _encode(payload)
    signature = new(secret_key.encode("utf-8"), encoded_payload.encode("ascii"), sha256).digest()
    return f"{encoded_payload}.{_encode(signature)}"


def read_session_user_id(token: str, secret_key: str) -> int | None:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected = new(secret_key.encode("utf-8"), encoded_payload.encode("ascii"), sha256).digest()
        if not compare_digest(_encode(expected), encoded_signature):
            return None
        payload = loads(_decode(encoded_payload))
        if int(payload["exp"]) < int(datetime.now(UTC).timestamp()):
            return None
        return int(payload["sub"])
    except (ValueError, KeyError, TypeError):
        return None
