"""Verifica autonoma delle sole buste PEC che contengono ricevute SdI.

Non usa le euristiche PEC né altera la firma di deposito/Local Signer.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from defusedxml import ElementTree
from pct.sdi_pec_trust import PecTrustError, revocation_bundle, trust_certificates


def _one_address(values: list[str]) -> str:
    addresses = [address.strip().lower() for _, address in getaddresses(values) if address.strip()]
    return addresses[0] if len(addresses) == 1 else ""


def _receipt_payloads(message):
    # Non attraversare messaggi inoltrati allegati: il loro mittente non è SdI.
    if message.get_content_type() == "message/rfc822":
        return
    if message.is_multipart():
        for part in message.iter_parts():
            yield from _receipt_payloads(part)
    else:
        raw = message.get_payload(decode=True) or b""
        if len(raw) <= 2 * 1024 * 1024 and raw.lstrip().startswith(b"<"):
            yield raw


def _attested_content(content: bytes, expected_recipient: str) -> dict[str, Any]:
    message = BytesParser(policy=policy.default).parsebytes(content)
    parts = list(message.iter_parts()) if message.is_multipart() else []
    certificates = [part for part in parts if str(part.get_filename() or "").lower() == "daticert.xml"]
    originals = [part for part in parts if str(part.get_filename() or "").lower() == "postacert.eml" and part.get_content_type() == "message/rfc822"]
    if len(certificates) != 1 or len(originals) != 1:
        raise PecTrustError("certified_envelope_required", "La ricevuta richiede la busta PEC originale con dati di certificazione.")
    daticert = certificates[0].get_payload(decode=True) or b""
    if len(daticert) > 128 * 1024:
        raise PecTrustError("invalid_certification_data", "I dati di certificazione PEC non sono riconoscibili.")
    root = ElementTree.fromstring(daticert, forbid_dtd=True)
    if root.tag != "postacert" or root.get("tipo") != "posta-certificata" or root.get("errore", "nessuno") != "nessuno":
        raise PecTrustError("certified_transport_required", "Il messaggio non è una busta di trasporto PEC senza errori.")
    senders = root.findall("./intestazione/mittente")
    sender = _one_address([str(node.text or "") for node in senders])
    if not re.fullmatch(r"sdi[0-9]+@pec\.fatturapa\.it", sender):
        raise PecTrustError("sdi_sender_mismatch", "Il mittente attestato dalla PEC non corrisponde al canale SdI.")
    recipients = {address.lower() for _, address in getaddresses([
        str(node.text or "") for node in root.findall("./intestazione/destinatari")
        if node.get("tipo", "certificato") == "certificato"])}
    if expected_recipient.strip().lower() not in recipients:
        raise PecTrustError("sdi_recipient_mismatch", "La ricevuta PEC non è indirizzata alla casella configurata dello studio.")
    original_parts = originals[0].get_payload()
    if not isinstance(original_parts, list) or len(original_parts) != 1:
        raise PecTrustError("original_message_ambiguous", "Il messaggio originale PEC non è univoco.")
    original = original_parts[0]
    if _one_address(original.get_all("From", [])) != sender:
        raise PecTrustError("sdi_sender_mismatch", "Il mittente originale e la certificazione PEC non coincidono.")
    original_id = str(original.get("Message-ID") or "").strip().strip("<>")
    # RFC 6109 §§3.1.1 e 4.4: il gestore sostituisce il Message-ID del
    # client; identificativo contiene quello PEC, msgid quello precedente.
    # Il confronto resta sul contenuto coperto dalla firma della busta.
    attested_id = str(root.findtext("./dati/identificativo") or "").strip().strip("<>")
    if not original_id or original_id != attested_id:
        raise PecTrustError("original_message_mismatch", "Il messaggio originale non coincide con i dati certificati.")
    return {"sender": sender, "original_message_id": original_id,
            "receipt_hashes": [hashlib.sha256(raw).hexdigest() for raw in _receipt_payloads(original)],
            "certification_sha256": hashlib.sha256(daticert).hexdigest(),
            "certified_message_id": str(root.findtext("./dati/identificativo") or "")}


def verify_sdi_pec_provenance(raw_mime: bytes, *, expected_recipient: str) -> dict[str, Any]:
    """Promuove soltanto dopo firma, catena PEC, revoche e corrispondenza dati.

    Il primo comando verifica l'integrità CMS; il secondo verifica la catena
    completa con le revoche. Il suo output non è mai una conferma della UI.
    """
    try:
        if not expected_recipient:
            raise PecTrustError("pec_address_missing", "Configurare la casella PEC dello studio per verificare la ricevuta.", retryable=True)
        if not raw_mime or len(raw_mime) > 32 * 1024 * 1024:
            raise PecTrustError("original_envelope_unavailable", "La busta PEC originale non è disponibile per la verifica.")
        executable = shutil.which("openssl")
        if not executable:
            raise PecTrustError("verifier_unavailable", "Il servizio di verifica PEC richiede il ripristino del verificatore di sistema.", retryable=True)
        ca_pem, root_pem = trust_certificates()
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory(prefix="iusentra-sdi-verify-") as directory:
            folder = Path(directory)
            paths = {name: folder / name for name in ("message.eml", "content.mime", "signer.pem", "ca.pem", "root.pem", "revocations.pem")}
            paths["message.eml"].write_bytes(raw_mime)
            paths["ca.pem"].write_bytes(ca_pem)
            paths["root.pem"].write_bytes(root_pem)
            result = subprocess.run([executable, "cms", "-verify", "-verify_retcode", "-inform", "SMIME",
                "-in", str(paths["message.eml"]), "-noverify", "-out", str(paths["content.mime"]),
                "-signer", str(paths["signer.pem"])], capture_output=True, timeout=12, check=False)
            if result.returncode != 0:
                raise PecTrustError("envelope_signature_invalid", "La firma della busta PEC non supera la verifica di integrità.")
            signers = x509.load_pem_x509_certificates(paths["signer.pem"].read_bytes())
            if len(signers) != 1:
                raise PecTrustError("signer_ambiguous", "Il firmatario della busta PEC non è univoco.")
            signer = signers[0]
            ca = x509.load_pem_x509_certificate(ca_pem)
            try:
                signer.verify_directly_issued_by(ca)
            except Exception as exc:
                raise PecTrustError("pec_issuer_unrecognized", "Il certificato della busta richiede la verifica del gestore PEC.") from exc
            if not signer.not_valid_before_utc <= now <= signer.not_valid_after_utc:
                raise PecTrustError("historical_certificate_review", "Certificato storico: acquisire la prova della catena e delle revoche alla data della firma.")
            attested = _attested_content(paths["content.mime"].read_bytes(), expected_recipient)
            crls, revocations = revocation_bundle(ca_pem, root_pem, now)
            paths["revocations.pem"].write_bytes(crls)
            chain = subprocess.run([executable, "verify", "-purpose", "smimesign", "-no-CApath", "-no-CAstore",
                "-CAfile", str(paths["root.pem"]), "-untrusted", str(paths["ca.pem"]),
                "-CRLfile", str(paths["revocations.pem"]), "-crl_check_all", str(paths["signer.pem"])],
                capture_output=True, timeout=12, check=False)
            if chain.returncode != 0:
                raise PecTrustError("certificate_chain_invalid", "La catena del gestore PEC o il controllo delle revoche non sono validi.")
            return {"verified": True, "code": "verified_pec_sdi", "retryable": False,
                "message": "Ricevuta verificata sulla busta PEC originale, sulla catena del gestore e sulle revoche.",
                "checked_at": now.isoformat(), "envelope_sha256": hashlib.sha256(raw_mime).hexdigest(),
                "signer_sha256": signer.fingerprint(hashes.SHA256()).hex(), "revocations": revocations,
                "method": "agid_ca1_native_root_smime_crl_v1", **attested}
    except PecTrustError as exc:
        return {"verified": False, "code": exc.code, "message": str(exc), "retryable": exc.retryable}
    except Exception:
        return {"verified": False, "code": "provenance_verification_failed", "message": "Verifica della provenienza PEC non riuscita: controllare la busta originale.", "retryable": True}

