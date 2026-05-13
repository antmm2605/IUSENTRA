"""Signature providers for audit envelopes.

JWS is implemented locally with cryptography and requires a configured private
key. CAdES/PKCS#7 mode is accepted only when an external signer is configured;
the module never falls back to generated or repository keys.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from .canonical import canonicalize
from .exceptions import AuditConfigError, AuditSignatureError
from .hashing import sha256_bytes


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    raw = value.encode("ascii")
    raw += b"=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class SignatureMetadata:
    format: str
    alg: str
    kid: str
    cert_fingerprint: str
    signature_b64: str
    signed_at_utc: str
    digest_signed: str
    event_format_version: str
    chain_metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "format": self.format,
            "alg": self.alg,
            "kid": self.kid,
            "cert_fingerprint": self.cert_fingerprint,
            "signature_b64": self.signature_b64,
            "signed_at_utc": self.signed_at_utc,
            "digest_signed": self.digest_signed,
            "event_format_version": self.event_format_version,
        }
        if self.chain_metadata:
            payload["chain_metadata"] = self.chain_metadata
        return payload


class AuditSigner:
    def sign(self, payload: dict[str, Any], *, event_format_version: str) -> SignatureMetadata:
        raise NotImplementedError

    def verify(self, payload: dict[str, Any], signature: dict[str, Any]) -> bool:
        raise NotImplementedError

    def public_key_pem(self) -> str:
        return ""


class JwsAuditSigner(AuditSigner):
    def __init__(
        self,
        *,
        private_key_pem: bytes | None = None,
        public_key_pem: bytes | None = None,
        private_key_path: str | Path | None = None,
        public_key_path: str | Path | None = None,
        private_key_password: bytes | None = None,
        kid: str,
        alg: str = "RS256",
        cert_fingerprint: str = "",
    ) -> None:
        if not kid.strip():
            raise AuditConfigError("AUDIT_SIGNING_KID obbligatorio.")
        self.kid = kid.strip()
        self.alg = alg.strip().upper() or "RS256"
        self.cert_fingerprint = cert_fingerprint.strip().lower()
        if self.alg not in {"RS256", "ES256"}:
            raise AuditConfigError("Algoritmo JWS audit non supportato.")
        if private_key_path:
            private_key_pem = Path(private_key_path).read_bytes()
        if public_key_path:
            public_key_pem = Path(public_key_path).read_bytes()
        self._private_key = None
        if private_key_pem:
            self._private_key = serialization.load_pem_private_key(private_key_pem, password=private_key_password)
        if public_key_pem:
            self._public_key = serialization.load_pem_public_key(public_key_pem)
        elif self._private_key is not None:
            self._public_key = self._private_key.public_key()
        else:
            raise AuditConfigError("Chiave pubblica o privata audit JWS mancante.")

    def _signing_input(self, payload: dict[str, Any]) -> tuple[bytes, str, str]:
        protected = {"alg": self.alg, "kid": self.kid, "typ": "iusentra-audit+jcs"}
        protected_b64 = _b64url(json.dumps(protected, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        payload_bytes = canonicalize(payload)
        payload_b64 = _b64url(payload_bytes)
        return f"{protected_b64}.{payload_b64}".encode("ascii"), protected_b64, payload_b64

    def sign(self, payload: dict[str, Any], *, event_format_version: str) -> SignatureMetadata:
        if self._private_key is None:
            raise AuditSignatureError("Chiave privata audit non disponibile per firmare.")
        signing_input, protected_b64, payload_b64 = self._signing_input(payload)
        if self.alg == "RS256":
            signature = self._private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        else:
            signature = self._private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        compact = f"{protected_b64}.{payload_b64}.{_b64url(signature)}"
        return SignatureMetadata(
            format="JWS",
            alg=self.alg,
            kid=self.kid,
            cert_fingerprint=self.cert_fingerprint,
            signature_b64=compact,
            signed_at_utc=_now(),
            digest_signed=sha256_bytes(canonicalize(payload)),
            event_format_version=event_format_version,
        )

    def verify(self, payload: dict[str, Any], signature: dict[str, Any]) -> bool:
        compact = str(signature.get("signature_b64") or "")
        parts = compact.split(".")
        if len(parts) != 3:
            return False
        try:
            protected = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
            if protected.get("kid") != self.kid or str(protected.get("alg", "")).upper() != self.alg:
                return False
            expected_payload = _b64url(canonicalize(payload))
            if parts[1] != expected_payload:
                return False
            signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
            raw_signature = _b64url_decode(parts[2])
            if self.alg == "RS256":
                self._public_key.verify(raw_signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
            else:
                self._public_key.verify(raw_signature, signing_input, ec.ECDSA(hashes.SHA256()))
            return True
        except (InvalidSignature, ValueError, json.JSONDecodeError):
            return False

    def public_key_pem(self) -> str:
        return self._public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")


class ExternalCadesSigner(AuditSigner):
    def __init__(self, *, endpoint_url: str = "", verify_url: str = "", kid: str = "", timeout_seconds: int = 15) -> None:
        self.endpoint_url = endpoint_url.strip().rstrip("/")
        self.verify_url = verify_url.strip().rstrip("/")
        self.kid = kid.strip()
        self.timeout_seconds = int(timeout_seconds)
        if not self.endpoint_url or not self.verify_url or not self.kid:
            raise AuditConfigError("CAdES richiede AUDIT_CADES_LOCAL_SIGNER_URL, AUDIT_CADES_VERIFY_URL e AUDIT_SIGNING_KID.")

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            import requests
        except Exception as exc:  # pragma: no cover
            raise AuditConfigError("requests non disponibile: richiesto per HACS Local Signer CAdES.") from exc
        try:
            response = requests.post(url, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise AuditSignatureError("Chiamata al signer CAdES non riuscita.") from exc
        if not isinstance(data, dict):
            raise AuditSignatureError("Risposta CAdES non valida.")
        return data

    def sign(self, payload: dict[str, Any], *, event_format_version: str) -> SignatureMetadata:
        payload_bytes = canonicalize(payload)
        digest = sha256_bytes(payload_bytes)
        result = self._post(
            self.endpoint_url,
            {
                "format": "iusentra-audit-signing-payload-v1",
                "kid": self.kid,
                "payload_b64": base64.b64encode(payload_bytes).decode("ascii"),
                "digest_sha256": digest,
                "event_format_version": event_format_version,
                "signature_format": "CAdES",
            },
        )
        signature_b64 = str(result.get("signature_b64") or "").strip()
        if not signature_b64:
            raise AuditSignatureError("Signer CAdES senza firma.")
        signed_digest = str(result.get("digest_signed") or digest).lower()
        if signed_digest != digest:
            raise AuditSignatureError("Signer CAdES ha firmato un digest inatteso.")
        return SignatureMetadata(
            format=str(result.get("format") or "CAdES"),
            alg=str(result.get("alg") or "CAdES-SHA256"),
            kid=str(result.get("kid") or self.kid),
            cert_fingerprint=str(result.get("cert_fingerprint") or "").lower(),
            signature_b64=signature_b64,
            signed_at_utc=str(result.get("signed_at_utc") or _now()),
            digest_signed=digest,
            event_format_version=event_format_version,
            chain_metadata=result.get("chain_metadata") if isinstance(result.get("chain_metadata"), dict) else None,
        )

    def verify(self, payload: dict[str, Any], signature: dict[str, Any]) -> bool:
        if str(signature.get("format") or "").upper() not in {"CADES", "PKCS7", "PKCS#7"}:
            return False
        payload_bytes = canonicalize(payload)
        digest = sha256_bytes(payload_bytes)
        result = self._post(
            self.verify_url,
            {
                "format": "iusentra-audit-verify-payload-v1",
                "kid": self.kid,
                "payload_b64": base64.b64encode(payload_bytes).decode("ascii"),
                "digest_sha256": digest,
                "signature": signature,
            },
        )
        return bool(result.get("ok") is True and str(result.get("digest_verified") or digest).lower() == digest)


def build_signing_payload(*, signed_event: dict[str, Any], event_hash: str) -> dict[str, Any]:
    return {
        "format": "audit-signing-payload-v1",
        "signed_event": signed_event,
        "event_hash": event_hash,
    }


def signer_from_config(config: dict[str, Any] | None = None) -> AuditSigner:
    cfg = dict(config or {})
    env = str(cfg.get("AUDIT_ENV") or os.getenv("AUDIT_ENV") or "development").strip().lower()
    mode = str(cfg.get("AUDIT_SIGNING_MODE") or os.getenv("AUDIT_SIGNING_MODE") or "JWS").strip().upper()
    kid = str(cfg.get("AUDIT_SIGNING_KID") or os.getenv("AUDIT_SIGNING_KID") or "").strip()
    if not kid:
        raise AuditConfigError("AUDIT_SIGNING_KID obbligatorio per firmare gli eventi audit.")
    if mode in {"CADES", "PKCS7", "PKCS#7"}:
        return ExternalCadesSigner(
            endpoint_url=str(cfg.get("AUDIT_CADES_LOCAL_SIGNER_URL") or os.getenv("AUDIT_CADES_LOCAL_SIGNER_URL") or ""),
            verify_url=str(cfg.get("AUDIT_CADES_VERIFY_URL") or os.getenv("AUDIT_CADES_VERIFY_URL") or ""),
            kid=kid,
            timeout_seconds=int(cfg.get("AUDIT_CADES_TIMEOUT_SECONDS") or os.getenv("AUDIT_CADES_TIMEOUT_SECONDS") or 15),
        )
    if mode != "JWS":
        raise AuditConfigError(f"AUDIT_SIGNING_MODE non supportato: {mode}.")
    private_key_path = str(cfg.get("AUDIT_SIGNING_PRIVATE_KEY_FILE") or os.getenv("AUDIT_SIGNING_PRIVATE_KEY_FILE") or "")
    public_key_path = str(cfg.get("AUDIT_SIGNING_PUBLIC_KEY_FILE") or os.getenv("AUDIT_SIGNING_PUBLIC_KEY_FILE") or "")
    key_source = str(cfg.get("AUDIT_SIGNING_KEY_SOURCE") or os.getenv("AUDIT_SIGNING_KEY_SOURCE") or "").strip().upper()
    sealed = str(cfg.get("AUDIT_SIGNING_KEY_SEALED") or os.getenv("AUDIT_SIGNING_KEY_SEALED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if env == "production":
        if not key_source:
            raise AuditConfigError("In produzione AUDIT_SIGNING_KEY_SOURCE deve indicare HSM, PKCS11 o KEY_VAULT_FILE.")
        if key_source == "KEY_VAULT_FILE" and not sealed:
            raise AuditConfigError("In produzione la chiave JWS da key vault file deve essere marcata sigillata.")
        if not private_key_path and key_source not in {"HSM", "PKCS11"}:
            raise AuditConfigError("Chiave privata JWS mancante per produzione.")
    if key_source in {"HSM", "PKCS11"}:
        raise AuditConfigError("Provider JWS HSM/PKCS11 non configurato: usare CAdES o adapter HSM esplicito.")
    password = str(cfg.get("AUDIT_SIGNING_PRIVATE_KEY_PASSWORD") or os.getenv("AUDIT_SIGNING_PRIVATE_KEY_PASSWORD") or "")
    return JwsAuditSigner(
        private_key_path=private_key_path or None,
        public_key_path=public_key_path or None,
        private_key_password=password.encode("utf-8") if password else None,
        kid=kid,
        alg=str(cfg.get("AUDIT_SIGNING_ALG") or os.getenv("AUDIT_SIGNING_ALG") or "RS256"),
        cert_fingerprint=str(
            cfg.get("AUDIT_SIGNING_CERT_FINGERPRINT") or os.getenv("AUDIT_SIGNING_CERT_FINGERPRINT") or ""
        ),
    )
