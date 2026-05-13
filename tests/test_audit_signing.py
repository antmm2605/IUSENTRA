from __future__ import annotations

from audit.signing import ExternalCadesSigner, JwsAuditSigner, build_signing_payload

from tests.audit_test_utils import make_key_pair


def test_jws_signature_roundtrip() -> None:
    private_pem, public_pem = make_key_pair()
    signer = JwsAuditSigner(private_key_pem=private_pem, kid="kid-1")
    verifier = JwsAuditSigner(public_key_pem=public_pem, kid="kid-1")
    payload = build_signing_payload(signed_event={"event_id": "e1"}, event_hash="a" * 64)
    signature = signer.sign(payload, event_format_version="audit-event-v1").to_dict()
    assert verifier.verify(payload, signature)


def test_jws_signature_detects_tampering() -> None:
    private_pem, public_pem = make_key_pair()
    signer = JwsAuditSigner(private_key_pem=private_pem, kid="kid-1")
    verifier = JwsAuditSigner(public_key_pem=public_pem, kid="kid-1")
    payload = build_signing_payload(signed_event={"event_id": "e1"}, event_hash="a" * 64)
    signature = signer.sign(payload, event_format_version="audit-event-v1").to_dict()
    altered = build_signing_payload(signed_event={"event_id": "e2"}, event_hash="a" * 64)
    assert not verifier.verify(altered, signature)


def test_cades_signer_uses_configured_external_endpoints(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    class _Response:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self.payload

    def _post(url: str, json: dict, timeout: int):
        calls.append((url, json))
        if url.endswith("/sign"):
            return _Response(
                {
                    "format": "CAdES",
                    "alg": "CAdES-SHA256",
                    "kid": "kid-cades",
                    "signature_b64": "ZmlybWE=",
                    "digest_signed": json["digest_sha256"],
                    "cert_fingerprint": "ab" * 32,
                    "chain_metadata": {"subject": "CN=Signer"},
                }
            )
        return _Response({"ok": True, "digest_verified": json["digest_sha256"]})

    monkeypatch.setattr("requests.post", _post)

    signer = ExternalCadesSigner(endpoint_url="https://signer.local/sign", verify_url="https://signer.local/verify", kid="kid-cades")
    payload = build_signing_payload(signed_event={"event_id": "e1"}, event_hash="a" * 64)
    signature = signer.sign(payload, event_format_version="audit-event-v1").to_dict()

    assert signature["format"] == "CAdES"
    assert signature["chain_metadata"]["subject"] == "CN=Signer"
    assert signer.verify(payload, signature)
    assert [call[0] for call in calls] == ["https://signer.local/sign", "https://signer.local/verify"]
