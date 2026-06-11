"""Adapter di firma per il Portale Cliente (predisposizione provider).

Base normativa/architetturale: la firma applicata internamente dal Portale
Cliente è una **firma elettronica semplice con evidence pack** (CAD D.Lgs.
82/2005, art. 20-21: la firma elettronica semplice ha valore probatorio
liberamente valutabile, rafforzato da un pacchetto di evidenze). NON è una
firma elettronica qualificata: per quella serve un provider esterno qualificato
(eIDAS 910/2014). Questo modulo tiene separate le due cose con un'interfaccia
comune e provider intercambiabili, così la firma qualificata si potrà aggiungere
senza toccare il flusso del portale.

Provider:
- ``InternalGraphicSignatureProvider``  → firma grafica/elettronica + timbro PDF visibile + evidence pack.
- ``ManualUploadSignatureProvider``     → download del documento, firma manuale, riupload del firmato (fallback).
- ``QualifiedSignatureProviderStub``    → segnaposto NON operativo per la firma qualificata remota; non dichiara MAI una firma qualificata completata.

Principi di sicurezza/GDPR applicati qui:
- l'evidence pack non contiene mai l'IP in chiaro (solo hash), né il token in chiaro (solo hash);
- l'evidence pack è pensato per restare lato server (audit), non per essere restituito al cliente;
- nessun contenuto del documento finisce nei log: si trattano solo hash SHA-256;
- il timbro visibile produce SEMPRE una nuova versione: i byte originali non vengono mutati;
- in caso di PDF cifrato o corrotto la firma fallisce in modo sicuro (SignatureProviderError).
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class SignatureType(str, Enum):
    GRAPHIC_INTERNAL = "grafica_interna"
    MANUAL_UPLOAD = "upload_manuale"
    QUALIFIED_REMOTE = "qualificata_remota"


class SignatureProviderError(RuntimeError):
    """Errore controllato di un provider di firma (fail-safe, nessuno stack trace al client)."""


class SignatureProviderNotConfigured(SignatureProviderError):
    """Il provider richiesto non è operativo in questa installazione."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def redact_ip(ip: str) -> str:
    """Ritorna un riferimento non reversibile all'IP (mai l'IP in chiaro)."""

    cleaned = (ip or "").strip()
    if not cleaned:
        return ""
    return "ipv:" + hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:32]


def token_reference(token: str) -> str:
    """Riferimento all'invito tramite hash, mai il token in chiaro."""

    cleaned = (token or "").strip()
    if not cleaned:
        return ""
    return "tok:" + hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class SignatureRequest:
    signature_id: str
    signature_type: SignatureType
    tenant_id: str = ""
    client_id: str = ""
    matter_id: str = ""
    document_id: str = ""


@dataclass(frozen=True)
class SignatureResult:
    provider: str
    signature_type: SignatureType
    status: str
    evidence: dict[str, Any] = field(default_factory=dict)
    signed_pdf: bytes | None = None
    operational: bool = True
    message: str = ""

    @property
    def completed(self) -> bool:
        return self.status == "firmato"

    @property
    def qualified(self) -> bool:
        # Solo un provider qualificato esterno potrà mai impostare questo a True.
        return self.signature_type == SignatureType.QUALIFIED_REMOTE and self.status == "firmato"


def build_signature_evidence_pack(
    *,
    signature_id: str,
    signature_type: SignatureType,
    provider: str,
    tenant_id: str = "",
    client_id: str = "",
    matter_id: str = "",
    document_id: str = "",
    consent_text: str = "",
    consent_version: str = "1",
    declaration: str = "",
    original_sha256: str = "",
    signed_sha256: str = "",
    signature_coordinates: dict[str, Any] | None = None,
    ip: str = "",
    user_agent: str = "",
    token: str = "",
    when: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Costruisce il pacchetto di evidenze probatorie (server-side).

    Non include mai IP o token in chiaro; aggiunge un checksum del payload per
    rilevare manomissioni. Pensato per essere salvato lato studio, non inviato
    al cliente.
    """

    payload: dict[str, Any] = {
        "signatureId": signature_id,
        "signatureType": signature_type.value,
        "provider": provider,
        "tenantId": tenant_id,
        "clientId": client_id,
        "matterId": matter_id,
        "documentId": document_id,
        "consentText": consent_text,
        "consentVersion": consent_version,
        "declaration": declaration,
        "originalSha256": original_sha256,
        "signedSha256": signed_sha256,
        "signatureCoordinates": signature_coordinates or {},
        "ipHash": redact_ip(ip),
        "userAgent": (user_agent or "")[:400],
        "tokenRef": token_reference(token),
        "completedAt": when or _utc_now_iso(),
    }
    if extra:
        # I campi extra (es. esito provider OTP) non devono reintrodurre PII grezza.
        for key, value in extra.items():
            if key in {"ip", "token", "ipHash", "tokenRef"}:
                continue
            payload.setdefault(key, value)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["payloadSha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def apply_visible_signature_stamp(
    pdf_bytes: bytes,
    *,
    signer_name: str,
    when_label: str = "",
    reference: str = "",
    page_index: int = -1,
    x_mm: float = 110.0,
    y_mm: float = 12.0,
    width_mm: float = 85.0,
    height_mm: float = 26.0,
) -> bytes:
    """Applica un timbro di firma visibile su una nuova copia del PDF.

    - Non muta i byte originali (input trattato come immutabile).
    - Produce una nuova versione con riquadro firma su una pagina (default ultima).
    - Fallisce in modo sicuro su PDF cifrato/corrotto/non valido.
    """

    if not pdf_bytes:
        raise SignatureProviderError("Documento PDF mancante.")
    try:
        from pypdf import PdfReader, PdfWriter
    except Exception as exc:  # pragma: no cover - dipende dall'ambiente
        raise SignatureProviderError("Libreria PDF non disponibile per la firma.") from exc

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if getattr(reader, "is_encrypted", False):
            raise SignatureProviderError("PDF protetto da password: impossibile applicare la firma.")
        pages = reader.pages
        if not pages:
            raise SignatureProviderError("PDF senza pagine.")
    except SignatureProviderError:
        raise
    except Exception as exc:
        raise SignatureProviderError("PDF non valido o illeggibile.") from exc

    target = page_index if (0 <= page_index < len(pages)) else len(pages) - 1
    media = pages[target].mediabox
    page_w = float(media.width)
    page_h = float(media.height)

    try:
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except Exception as exc:  # pragma: no cover - dipende dall'ambiente
        raise SignatureProviderError("Libreria di rendering non disponibile per la firma.") from exc

    overlay_buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(overlay_buffer, pagesize=(page_w, page_h))
    x = x_mm * mm
    y = y_mm * mm
    w = width_mm * mm
    h = height_mm * mm
    pdf_canvas.setLineWidth(0.8)
    pdf_canvas.rect(x, y, w, h, stroke=1, fill=0)
    pdf_canvas.setFont("Helvetica-Bold", 8)
    pdf_canvas.drawString(x + 4, y + h - 11, "Firma elettronica del cliente")
    pdf_canvas.setFont("Helvetica", 7)
    pdf_canvas.drawString(x + 4, y + h - 21, (signer_name or "")[:60])
    if when_label:
        pdf_canvas.drawString(x + 4, y + 12, when_label[:60])
    if reference:
        pdf_canvas.drawString(x + 4, y + 4, ("Rif. " + reference)[:60])
    pdf_canvas.showPage()
    pdf_canvas.save()
    overlay_buffer.seek(0)

    try:
        overlay_reader = PdfReader(overlay_buffer)
        writer = PdfWriter()
        # Le pagine vanno prima collegate al writer, poi si fa il merge su quelle
        # del writer: fare merge su pagine "staccate" è deprecato in pypdf e poco
        # affidabile (replace_contents). Così il timbro è stabile e senza warning.
        writer.append(reader)
        writer.pages[target].merge_page(overlay_reader.pages[0])
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception as exc:
        raise SignatureProviderError("Impossibile comporre il PDF firmato.") from exc


@runtime_checkable
class SignatureProvider(Protocol):
    name: str
    signature_type: SignatureType

    def create_signature_request(self, request: SignatureRequest, **kwargs: Any) -> SignatureResult: ...
    def get_signature_status(self, signature_id: str, **kwargs: Any) -> SignatureResult: ...
    def download_signed_document(self, signature_id: str, **kwargs: Any) -> bytes: ...
    def cancel_signature_request(self, signature_id: str, **kwargs: Any) -> SignatureResult: ...


class InternalGraphicSignatureProvider:
    """Firma elettronica semplice con timbro grafico applicato al PDF + evidence pack."""

    name = "internal_graphic"
    signature_type = SignatureType.GRAPHIC_INTERNAL

    def create_signature_request(
        self,
        request: SignatureRequest,
        *,
        pdf_bytes: bytes = b"",
        signer_name: str = "",
        when_label: str = "",
        reference: str = "",
        consent_text: str = "",
        consent_version: str = "1",
        declaration: str = "",
        ip: str = "",
        user_agent: str = "",
        token: str = "",
        signature_coordinates: dict[str, Any] | None = None,
        **_: Any,
    ) -> SignatureResult:
        original_sha = sha256_hex(pdf_bytes) if pdf_bytes else ""
        signed_pdf = None
        signed_sha = ""
        if pdf_bytes:
            signed_pdf = apply_visible_signature_stamp(
                pdf_bytes,
                signer_name=signer_name or "Cliente",
                when_label=when_label,
                reference=reference,
            )
            signed_sha = sha256_hex(signed_pdf)
        evidence = build_signature_evidence_pack(
            signature_id=request.signature_id,
            signature_type=self.signature_type,
            provider=self.name,
            tenant_id=request.tenant_id,
            client_id=request.client_id,
            matter_id=request.matter_id,
            document_id=request.document_id,
            consent_text=consent_text,
            consent_version=consent_version,
            declaration=declaration,
            original_sha256=original_sha,
            signed_sha256=signed_sha,
            signature_coordinates=signature_coordinates,
            ip=ip,
            user_agent=user_agent,
            token=token,
        )
        return SignatureResult(
            provider=self.name,
            signature_type=self.signature_type,
            status="firmato",
            evidence=evidence,
            signed_pdf=signed_pdf,
            message="Firma elettronica applicata.",
        )

    def get_signature_status(self, signature_id: str, **_: Any) -> SignatureResult:
        return SignatureResult(self.name, self.signature_type, "firmato")

    def download_signed_document(self, signature_id: str, **_: Any) -> bytes:
        raise SignatureProviderError("Recupero documento firmato non gestito da questo provider in-memory.")

    def cancel_signature_request(self, signature_id: str, **_: Any) -> SignatureResult:
        return SignatureResult(self.name, self.signature_type, "annullato")


class ManualUploadSignatureProvider:
    """Fallback: il cliente scarica, firma a mano e ricarica il documento firmato."""

    name = "manual_upload"
    signature_type = SignatureType.MANUAL_UPLOAD

    def create_signature_request(
        self,
        request: SignatureRequest,
        *,
        original_pdf_bytes: bytes = b"",
        signed_pdf_bytes: bytes = b"",
        consent_text: str = "",
        consent_version: str = "1",
        declaration: str = "",
        ip: str = "",
        user_agent: str = "",
        token: str = "",
        **_: Any,
    ) -> SignatureResult:
        if not signed_pdf_bytes:
            raise SignatureProviderError("Documento firmato mancante: ricarica il file firmato.")
        original_sha = sha256_hex(original_pdf_bytes) if original_pdf_bytes else ""
        signed_sha = sha256_hex(signed_pdf_bytes)
        evidence = build_signature_evidence_pack(
            signature_id=request.signature_id,
            signature_type=self.signature_type,
            provider=self.name,
            tenant_id=request.tenant_id,
            client_id=request.client_id,
            matter_id=request.matter_id,
            document_id=request.document_id,
            consent_text=consent_text,
            consent_version=consent_version,
            declaration=declaration,
            original_sha256=original_sha,
            signed_sha256=signed_sha,
            ip=ip,
            user_agent=user_agent,
            token=token,
        )
        return SignatureResult(
            provider=self.name,
            signature_type=self.signature_type,
            status="firmato",
            evidence=evidence,
            signed_pdf=signed_pdf_bytes,
            message="Documento firmato ricevuto.",
        )

    def get_signature_status(self, signature_id: str, **_: Any) -> SignatureResult:
        return SignatureResult(self.name, self.signature_type, "firmato")

    def download_signed_document(self, signature_id: str, **_: Any) -> bytes:
        raise SignatureProviderError("Il documento firmato è gestito dallo storage del portale.")

    def cancel_signature_request(self, signature_id: str, **_: Any) -> SignatureResult:
        return SignatureResult(self.name, self.signature_type, "annullato")


class QualifiedSignatureProviderStub:
    """Segnaposto NON operativo per la firma qualificata remota (eIDAS).

    Non integra alcun provider reale e non dichiara MAI una firma qualificata
    completata: serve solo a tenere pronta l'interfaccia per un'integrazione
    futura con un prestatore di servizi fiduciari qualificato.
    """

    name = "qualified_stub"
    signature_type = SignatureType.QUALIFIED_REMOTE

    def create_signature_request(self, request: SignatureRequest, **_: Any) -> SignatureResult:
        raise SignatureProviderNotConfigured(
            "Firma qualificata non configurata: richiede un provider esterno qualificato."
        )

    def get_signature_status(self, signature_id: str, **_: Any) -> SignatureResult:
        return SignatureResult(
            provider=self.name,
            signature_type=self.signature_type,
            status="non_configurato",
            operational=False,
            message="Provider di firma qualificata non configurato.",
        )

    def download_signed_document(self, signature_id: str, **_: Any) -> bytes:
        raise SignatureProviderNotConfigured("Firma qualificata non configurata.")

    def cancel_signature_request(self, signature_id: str, **_: Any) -> SignatureResult:
        return SignatureResult(
            provider=self.name,
            signature_type=self.signature_type,
            status="non_configurato",
            operational=False,
        )


_PROVIDERS: dict[str, type] = {
    InternalGraphicSignatureProvider.name: InternalGraphicSignatureProvider,
    ManualUploadSignatureProvider.name: ManualUploadSignatureProvider,
    QualifiedSignatureProviderStub.name: QualifiedSignatureProviderStub,
}


def get_signature_provider(name: str) -> SignatureProvider:
    provider_cls = _PROVIDERS.get((name or "").strip())
    if provider_cls is None:
        raise SignatureProviderNotConfigured(f"Provider di firma sconosciuto: {name!r}.")
    return provider_cls()


def available_signature_providers() -> list[str]:
    return sorted(_PROVIDERS)


__all__ = [
    "SignatureType",
    "SignatureProvider",
    "SignatureRequest",
    "SignatureResult",
    "SignatureProviderError",
    "SignatureProviderNotConfigured",
    "InternalGraphicSignatureProvider",
    "ManualUploadSignatureProvider",
    "QualifiedSignatureProviderStub",
    "build_signature_evidence_pack",
    "apply_visible_signature_stamp",
    "redact_ip",
    "token_reference",
    "sha256_hex",
    "get_signature_provider",
    "available_signature_providers",
]
