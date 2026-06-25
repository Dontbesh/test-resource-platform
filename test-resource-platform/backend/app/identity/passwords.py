from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from secrets import token_bytes

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
SALT_BYTES = 16


def _encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = token_bytes(SALT_BYTES)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"{ALGORITHM}${ITERATIONS}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
        if algorithm != ALGORITHM:
            return False
        digest = pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _decode(salt),
            int(iterations),
        )
        return compare_digest(_encode(digest), expected)
    except (ValueError, TypeError):
        return False
