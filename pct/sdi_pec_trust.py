"""Fiducia PEC fiscale: CA AgID governata, radice nativa e revoche firmate.

Nessun certificato o URL fornito dalla UI è una radice di fiducia.
Fonte: docs/specs/SDI_PEC_PROVENANCE_20260908.md.
"""
from __future__ import annotations

import hashlib
import ssl
from datetime import datetime
from pathlib import Path
from threading import Lock
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from cryptography import x509
from cryptography.hazmat.primitives import serialization

CA_PEM_SHA256 = "6ce848b03f6d506fd38824ed41e07e14f28010e888a372c50f5f88fb8348c092"
ROOT_SHA256 = "55926084ec963a64b96e2abe01ce0ba86a64fbfebcc7aab5afc155b37fd76066"
CA_FILE = Path(__file__).resolve().parents[1] / "docs/specs/ministero/fonti_ufficiali/2026-09-08/AgID_CA1_20250220.pem"
CRL_URLS = ("http://ca1.agid.gov.it/CRL", "http://crl07.actalis.it/Repository/AUTH-ROOT/getLastCRL")
_CRL_CACHE: dict[str, tuple[bytes, datetime]] = {}
_LOCK = Lock()


class PecTrustError(ValueError):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code, self.retryable = code, retryable


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PecTrustError("revocation_redirect", "Il canale ufficiale delle revoche ha cambiato indirizzo.", retryable=True)


def trust_certificates() -> tuple[bytes, bytes]:
    ca_pem = CA_FILE.read_bytes()
    if hashlib.sha256(ca_pem).hexdigest() != CA_PEM_SHA256:
        raise PecTrustError("trust_bundle_changed", "Il certificato di fiducia PEC richiede una verifica di integrità.")
    for der in ssl.create_default_context().get_ca_certs(binary_form=True):
        if hashlib.sha256(der).hexdigest() == ROOT_SHA256:
            root = x509.load_der_x509_certificate(der)
            return ca_pem, root.public_bytes(serialization.Encoding.PEM)
    raise PecTrustError("native_root_missing", "La radice di fiducia PEC manca dal sistema: aggiornare i certificati del servizio.", retryable=True)


def _validated_crl(data: bytes, issuer: x509.Certificate, now: datetime) -> x509.CertificateRevocationList:
    crl = x509.load_der_x509_crl(data)
    if crl.issuer != issuer.subject or not crl.is_signature_valid(issuer.public_key()):
        raise PecTrustError("revocation_signature_invalid", "La lista di revoca PEC non supera il controllo della firma.")
    if crl.next_update_utc is None or not crl.last_update_utc <= now < crl.next_update_utc:
        raise PecTrustError("revocation_outdated", "La lista delle revoche PEC non è aggiornata: ripetere il controllo.", retryable=True)
    return crl


def revocation_bundle(ca_pem: bytes, root_pem: bytes, now: datetime) -> tuple[bytes, list[dict[str, str]]]:
    """Recupera solo CRL pubbliche fisse; contenuto autenticato prima dell'uso.

    Cache esclusivamente tecnica di processo, massimo un'ora e mai oltre
    nextUpdate. Nessun dato del messaggio lascia lo studio.
    """
    out, evidence = [], []
    for url, issuer_pem in zip(CRL_URLS, (ca_pem, root_pem)):
        issuer = x509.load_pem_x509_certificate(issuer_pem)
        with _LOCK:
            cached = _CRL_CACHE.get(url)
        data = cached[0] if cached and (now - cached[1]).total_seconds() < 3600 else b""
        if data:
            try:
                _validated_crl(data, issuer, now)
            except PecTrustError:
                data = b""
        if not data:
            opener = build_opener(ProxyHandler({}), _NoRedirect())
            try:
                with opener.open(Request(url, headers={"User-Agent": "IUSENTRA-PEC-Provenance/1"}), timeout=6) as response:
                    data = response.read(4 * 1024 * 1024 + 1)
                if len(data) > 4 * 1024 * 1024:
                    raise PecTrustError("revocation_too_large", "La lista di revoca richiede una verifica tecnica.")
                _validated_crl(data, issuer, now)
            except PecTrustError:
                raise
            except Exception as exc:
                raise PecTrustError("revocation_unavailable", "Il controllo pubblico delle revoche non è disponibile: riprovare la verifica.", retryable=True) from exc
            with _LOCK:
                _CRL_CACHE[url] = data, now
        crl = _validated_crl(data, issuer, now)
        out.append(crl.public_bytes(serialization.Encoding.PEM))
        evidence.append({"url": url, "sha256": hashlib.sha256(data).hexdigest(),
                         "this_update": crl.last_update_utc.isoformat(), "next_update": crl.next_update_utc.isoformat()})
    return b"".join(out), evidence
