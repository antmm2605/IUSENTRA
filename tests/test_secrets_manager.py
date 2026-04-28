from __future__ import annotations

import pytest

from core.security.secrets_manager import SecretsManager


def test_secret_encrypt_decrypt_and_rotate() -> None:
    old_key = SecretsManager.generate_key()
    new_key = SecretsManager.generate_key()
    old_manager = SecretsManager(old_key)
    token = old_manager.encrypt("smtp-password")

    manager = SecretsManager(new_key, old_keys=[old_key])
    assert manager.decrypt(token) == "smtp-password"
    rotated = manager.rotate(token)
    assert manager.decrypt(rotated) == "smtp-password"


def test_secret_manager_requires_primary_key() -> None:
    with pytest.raises(ValueError):
        SecretsManager("")


def test_secret_manager_rejects_corrupt_secret() -> None:
    manager = SecretsManager(SecretsManager.generate_key())
    with pytest.raises(ValueError):
        manager.decrypt("not-a-token")
