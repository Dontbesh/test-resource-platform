from cryptography.fernet import Fernet, InvalidToken


class CredentialEncryptionKeyError(Exception):
    pass


class CredentialDecryptionError(Exception):
    pass


class CredentialCipher:
    def __init__(self, key: str | None) -> None:
        if not key:
            raise CredentialEncryptionKeyError
        try:
            self._fernet = Fernet(key.encode())
        except ValueError as exc:
            raise CredentialEncryptionKeyError from exc

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise CredentialDecryptionError from exc
