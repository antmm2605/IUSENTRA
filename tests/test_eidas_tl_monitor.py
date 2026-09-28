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


def _tl_with_takeover(*, extra: str = "") -> str:
    return (
        '<TrustServiceStatusList xmlns="http://uri.etsi.org/02231/v2#" '
        'xmlns:a="http://uri.etsi.org/02231/v2/additionaltypes#">'
        '<ServiceInformationExtensions><Extension Critical="true">'
        '<a:TakenOverBy><a:URI>https://agid.gov.it/cessionario</a:URI>'
        '<a:TSPName><Name>Nuovo prestatore</Name></a:TSPName>'
        '<SchemeOperatorName><Name>AgID</Name></SchemeOperatorName>'
        '<SchemeTerritory>IT</SchemeTerritory>'
        f'{extra}</a:TakenOverBy></Extension></ServiceInformationExtensions>'
        '</TrustServiceStatusList>'
    )


def test_takeover_is_projected_only_after_signed_tl_validation(monkeypatch):
    calls = []
    monkeypatch.setattr(monitor, "trust_list_to_registry", lambda xml, certs: (
        calls.append("signed") or object(), [ValueError(
            "Cannot process a critical extension in service named 'sample'.\nContent: TakenOverBy(...)"
        )]
    ))

    def parse_projection(xml):
        calls.append("projection")
        assert "TakenOverBy" not in xml
        return object(), []

    monkeypatch.setattr(monitor, "trust_list_to_registry_unsafe", parse_projection)
    _, recovered, count = monitor._registro_con_cessioni(_tl_with_takeover(), [object()])
    assert recovered == 1
    assert count == 1
    assert calls == ["signed", "projection"]


def test_takeover_does_not_bypass_invalid_tl_signature(monkeypatch):
    monkeypatch.setattr(monitor, "trust_list_to_registry", lambda xml, certs: (
        (_ for _ in ()).throw(ValueError("firma XML non valida"))
    ))
    with pytest.raises(ValueError, match="firma XML non valida"):
        monitor._registro_con_cessioni(_tl_with_takeover(), [])


def test_unknown_critical_takeover_content_fails_closed(monkeypatch):
    monkeypatch.setattr(monitor, "trust_list_to_registry", lambda xml, certs: (
        object(), [ValueError(
            "Cannot process a critical extension in service named 'sample'.\nContent: TakenOverBy(...)"
        )]
    ))
    with pytest.raises(ValueError, match="non riconosciut"):
        monitor._registro_con_cessioni(_tl_with_takeover(extra="<a:FutureRule/>"), [])


def test_takeover_service_identifier_is_interpreted_but_unknown_content_fails(monkeypatch):
    monkeypatch.setattr(monitor, "trust_list_to_registry", lambda xml, certs: (
        object(), [ValueError(
            "Cannot process a critical extension in service named 'sample'.\nContent: TakenOverBy(...)"
        )]
    ))
    monkeypatch.setattr(monitor, "trust_list_to_registry_unsafe", lambda xml: (object(), []))
    known = (
        '<a:OtherQualifier><TLServiceIdentifier '
        'xmlns="http://ep.nbu.gov.sk/kca/tsl/x509types#">TLICZ-86'
        '</TLServiceIdentifier></a:OtherQualifier>'
    )
    _, errors, count = monitor._registro_con_cessioni(_tl_with_takeover(extra=known), [])
    assert (errors, count) == (1, 1)
    with pytest.raises(ValueError, match="non riconosciuto"):
        monitor._registro_con_cessioni(_tl_with_takeover(extra=known.replace("TLICZ-86", "invalid")), [])


def test_other_service_error_cannot_be_hidden_by_projection(monkeypatch):
    monkeypatch.setattr(monitor, "trust_list_to_registry", lambda xml, certs: (
        object(), [ValueError("Other parsing error")]
    ))
    with pytest.raises(ValueError, match="errori diversi"):
        monitor._registro_con_cessioni(_tl_with_takeover(), [])


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
