"""Gestione secrets cifrati con Fernet e rotazione chiavi."""

from __future__ import annotations

from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


@dataclass(frozen=True)
class SecretRecord:
    name: str
    value: str


class SecretsManager:
    def __init__(self, primary_key: str, old_keys: list[str] | None = None) -> None:
        if not primary_key:
            raise ValueError("FERNET_PRIMARY_KEY mancante")
        self.primary_key = primary_key.encode()
        self.old_keys = [item.encode() for item in list(old_keys or []) if item]
        self._primary = Fernet(self.primary_key)
        self._readers = [self._primary, *[Fernet(key) for key in self.old_keys]]

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()

    def encrypt(self, value: str) -> str:
        return self._primary.encrypt(str(value).encode()).decode()

    def decrypt(self, token: str) -> str:
        last_error: Exception | None = None
        for reader in self._readers:
            try:
                return reader.decrypt(str(token).encode()).decode()
            except InvalidToken as exc:
                last_error = exc
        raise ValueError("Secret non decifrabile") from last_error

    def rotate(self, token: str) -> str:
        return self.encrypt(self.decrypt(token))
