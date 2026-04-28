from __future__ import annotations

from dataclasses import replace

import pytest

from core.security.audit_log import build_audit_event, verify_event


def test_audit_event_signature_is_valid() -> None:
    event = build_audit_event(key="super-secret-key", action="upload", entity_type="documento", entity_id="42")
    assert event.signature
    assert verify_event("super-secret-key", event)


def test_audit_event_tampering_is_detected() -> None:
    event = build_audit_event(key="super-secret-key", action="delete", result="ok")
    altered = replace(event, result="ok-altered")
    assert not verify_event("super-secret-key", altered)


def test_audit_requires_hmac_key() -> None:
    with pytest.raises(ValueError):
        build_audit_event(key="", action="login")
