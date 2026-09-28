"""Guardrail locali; la firma XML reale è provata dal job periodico."""

from datetime import datetime, timedelta, timezone
import hashlib

import pytest

import scripts.check_eidas_tl as monitor
from scripts.check_eidas_tl import _metadata


class _Cert:
    def __init__(self, der: bytes):
        self.der = der

    def dump(self) -> bytes:
        return self.der


def test_tl5_tl6_are_checked_as_rotation_evidence_not_trust_anchors(monkeypatch):
    certs = [_Cert(b"quinta chiave"), _Cert(b"sesta chiave")]
    monkeypatch.setattr(monitor, "AGID_TL_2026_SHA256", {
        "TL5": hashlib.sha256(certs[0].dump()).hexdigest(),
        "TL6": hashlib.sha256(certs[1].dump()).hexdigest(),
    })
    assert monitor._certificati_2026_nella_lotl(certs) == {"TL5": True, "TL6": True}
    assert monitor._certificati_2026_nella_lotl(certs[:1]) == {"TL5": True, "TL6": False}


def _tl(*, sequence: str = "224", next_update: str) -> str:
    return (
        '<TrustServiceStatusList xmlns="http://uri.etsi.org/02231/v2#">'
        '<SchemeInformation>'
        f'<TSLSequenceNumber>{sequence}</TSLSequenceNumber>'
        f'<NextUpdate><dateTime>{next_update}</dateTime></NextUpdate>'
        '</SchemeInformation></TrustServiceStatusList>'
    )


def test_tl_metadata_has_future_expiry_and_sequence():
    expiry = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert _metadata(_tl(next_update=expiry)) == {
        "sequence": 224,
        "next_update": expiry,
    }


def test_expired_tl_is_rejected():
    expiry = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="scaduta"):
        _metadata(_tl(next_update=expiry))


def test_missing_tl_metadata_is_rejected():
    with pytest.raises(ValueError, match="obbligatori"):
        _metadata('<TrustServiceStatusList xmlns="http://uri.etsi.org/02231/v2#"/>')
