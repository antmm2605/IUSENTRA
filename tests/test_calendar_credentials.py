from pct.calendar_bindings import CalendarSyncRepository
from pct.calendar_credentials import CalendarCredentialVault


def test_calendar_credentials_are_encrypted_on_disk(tmp_path):
    secret = "google-access-token-secret"
    vault = CalendarCredentialVault(master_key="calendar-test-key")
    encrypted = vault.encrypt({"access_token": secret, "refresh_token": "refresh-secret"})

    repo_path = tmp_path / "calendar_sync_engine.json"
    repo = CalendarSyncRepository(repo_path)
    account = repo.upsert_account(
        {
            "tenant_id": "tenant-test",
            "provider": "google",
            "display_name": "Google Calendar",
            "email": "studio@example.test",
            "auth_type": "oauth",
            "encrypted_credentials": encrypted,
            "scopes": ["calendar.events"],
        }
    )

    raw = repo_path.read_text(encoding="utf-8")
    assert secret not in raw
    assert "refresh-secret" not in raw
    assert "fernet:v1:" in account["encrypted_credentials"]
    assert vault.decrypt(account["encrypted_credentials"])["access_token"] == secret
