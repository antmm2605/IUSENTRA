"""Workflow professionale del Portale Cliente: preventivo, conferimento, firma.

Governato dal feature flag default-off `routes.appV2.clientPortal.signingWorkflow`.
Tutto è risolto lato server dal token d'invito (tenant, cliente, pratica):
nessun endpoint accetta tenant_id/studio_id/path. La firma applicata qui è una
firma elettronica semplice con pacchetto di evidenze (CAD artt. 20-21), MAI
dichiarata come firma qualificata. Base normativa preventivi/conferimento:
art. 13 L. 247/2012, D.M. 55/2014 (compensi), art. 23 CAD (copie).
"""

from __future__ import annotations

import base64
import binascii
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import current_app, request

from pct.client_portal import (
    CLIENT_PORTAL_DOCUMENT_FINAL_STATUS,
    ClientPortalError,
    ClientPortalRepository,
    json_dumps,
    json_loads,
    new_id,
    utc_now,
)
from pct.client_portal_access import constant_time_match, generate_otp, hash_secret
from pct.preventivi import StatoConferimento, StatoPreventivo
from web.services.client_portal_signing_texts import (
    CONFERIMENTO_CONSENT_KEY,
    CONFERIMENTO_CONSENT_TEXT,
    CONSENT_VERSION,
    IDENTITY_CONSENT_KEY,
    MANUAL_UPLOAD_DECLARATION,
    PREVENTIVO_CONSENT_KEY,
    PREVENTIVO_CONSENT_TEXT,
    SIGNING_CONSENT_KEYS,
    SIGNING_CONSENTS,
    consent_texts_payload,
)
from web.services.client_signature_providers import (
    InternalGraphicSignatureProvider,
    ManualUploadSignatureProvider,
    SignatureProviderError,
    SignatureRequest,
    SignatureType,
    build_signature_evidence_pack,
    is_jpeg_bytes,
    token_reference,
)
from web.services.feature_flags import is_feature_enabled
from web.services.react_client_portal_bridge import (
    _core_runtime_func,
    _current_client_token,
    _document_bytes,
    _invalid_invite_payload,
    _invite_and_repo,
    _iso_to_rome_label,
    _persist_client_upload,
    _public_row,
    _text,
    tenant_locator_from_token,
)


SIGNING_FEATURE_FLAG = "routes.appV2.clientPortal.signingWorkflow"

# request_id sentinella per i documenti generati/gestiti dal workflow.
REQUEST_IDENTITY_DOCUMENT = "documento-identita"
REQUEST_SIGNED_DOCUMENT = "documento-firmato"
REQUEST_RECEIPT_DOCUMENT = "ricevuta-firma"


def _request_preventivo_pdf(preventivo_id: str) -> str:
    return f"preventivo-pdf:{preventivo_id}"


def _request_conferimento_pdf(conferimento_id: str) -> str:
    return f"conferimento-pdf:{conferimento_id}"


PREVENTIVO_STATI_PORTALE = {
    StatoPreventivo.INVIATO,
    StatoPreventivo.APERTO,
    StatoPreventivo.ACCETTATO,
    StatoPreventivo.CONVERTITO,
}
PREVENTIVO_STATI_ACCETTABILI = {StatoPreventivo.INVIATO, StatoPreventivo.APERTO}
PREVENTIVO_STATI_ACCETTATI = {StatoPreventivo.ACCETTATO, StatoPreventivo.CONVERTITO}

SIGNATURE_IMAGE_MAX_BYTES = 300 * 1024
DECLINE_REASON_MAX_CHARS = 500
SIGNED_UPLOAD_MAX_BYTES = 25 * 1024 * 1024

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_GRANT_CONSENT_KEY = "__otp_firma__"

# Campi minimi che il cliente deve aver compilato prima del conferimento.
MINIMAL_CLIENT_FIELDS = ("display_name", "email", "fiscal_code")
MINIMAL_CLIENT_FIELD_LABELS = {
    "display_name": "nome e cognome",
    "email": "email",
    "fiscal_code": "codice fiscale",
}


def _signing_disabled_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "code": "feature_disabled",
        "message": "Workflow di conferimento incarico non attivo per questo studio.",
    }


def _signing_enabled() -> bool:
    return is_feature_enabled(SIGNING_FEATURE_FLAG, current_app.config)


def _validation_error(message: str) -> dict[str, Any]:
    return {"ok": False, "code": "validation_error", "message": message}


def _stato_value(entity: Any) -> str:
    stato = getattr(entity, "stato", "")
    return _text(getattr(stato, "value", stato))


def _tenant_paths_for_token(token: str) -> dict[str, str] | None:
    """Percorsi dati del tenant risolto dal token; None = usare il runtime corrente.

    In multi-tenant il gestore preventivi/clienti NON può dipendere dalla
    sessione della richiesta pubblica: il tenant è quello firmato nel token.
    """

    locator = tenant_locator_from_token(token)
    if locator == "single-studio" or not current_app.config.get("MULTI_TENANT"):
        return None
    registry = _text(current_app.config.get("TENANTS_REGISTRY"))
    if not registry:
        raise ClientPortalError("Studio non disponibile per l'invito.")
    from pct.tenant import GestioneTenant

    tenant_manager = GestioneTenant(registry_path=registry)
    if tenant_manager.get(locator) is None:
        raise ClientPortalError("Studio non disponibile per l'invito.")
    return tenant_manager.percorsi_dati(locator, reconcile_aliases=False)


def _gestione_preventivi_for_token(token: str):
    paths = _tenant_paths_for_token(token)
    if paths is None:
        getter = _core_runtime_func("get_preventivi")
        if callable(getter):
            return getter()
        from web.helpers import get_preventivi

        return get_preventivi()
    from pct.preventivi import GestionePreventivi
    from web.services.storage_runtime import get_request_studio_db

    return GestionePreventivi(
        db_path=paths["PREVENTIVI_DB"],
        studio_db=get_request_studio_db(paths["PREVENTIVI_DB"]),
    )


def _cliente_for_token(token: str, client_id: str):
    paths = _tenant_paths_for_token(token)
    if paths is None:
        getter = _core_runtime_func("get_clienti")
        manager = getter() if callable(getter) else None
    else:
        from pct.clienti import GestioneClienti
        from web.services.storage_runtime import get_request_studio_db

        manager = GestioneClienti(
            db_path=paths["CLIENTI_DB"],
            studio_db=get_request_studio_db(paths["CLIENTI_DB"]),
        )
    return manager.get(client_id) if manager is not None and client_id else None


def _fascicolo_for_token(token: str, fascicolo_id: str):
    if not fascicolo_id:
        return None
    paths = _tenant_paths_for_token(token)
    if paths is None:
        getter = _core_runtime_func("get_fascicoli")
        manager = getter() if callable(getter) else None
    else:
        from pct.fascicoli import GestioneFascicoli
        from web.services.storage_runtime import get_request_studio_db

        manager = GestioneFascicoli(
            db_path=paths["FASCICOLI_DB"],
            documents_dir=paths["FASCICOLI_DOCS"],
            archive_dir=paths["FASCICOLI_ARCH"],
            studio_db=get_request_studio_db(paths["FASCICOLI_DB"]),
        )
    return manager.get(fascicolo_id) if manager is not None else None


def _client_ip() -> str:
    return _text(request.remote_addr)


def _client_user_agent() -> str:
    return _text(request.user_agent.string if request.user_agent else "")


def _invite_preventivo_id(invite: dict[str, Any]) -> str:
    metadata = json_loads(invite.get("metadata_json"), {})
    if not isinstance(metadata, dict):
        return ""
    return _text(metadata.get("preventivoId"))


def _preventivi_for_invite(invite: dict[str, Any], gp: Any) -> list[Any]:
    client_id = _text(invite.get("client_id"))
    if not client_id:
        return []
    result = [
        p
        for p in gp.preventivi_per_cliente(client_id)
        if p.stato in PREVENTIVO_STATI_PORTALE
    ]
    highlighted = _invite_preventivo_id(invite)
    if highlighted:
        result.sort(key=lambda p: 0 if _text(p.id) == highlighted else 1)
    return result


def _preventivo_of_invite_or_none(invite: dict[str, Any], gp: Any, preventivo_id: str):
    preventivo = gp.get_preventivo(_text(preventivo_id))
    if preventivo is None:
        return None
    if _text(preventivo.id_cliente) != _text(invite.get("client_id")):
        return None
    return preventivo


def _materialize_pdf(
    repo: ClientPortalRepository,
    invite: dict[str, Any],
    *,
    request_id: str,
    filename: str,
    pdf_factory,
) -> dict[str, Any]:
    """Genera una sola volta il PDF e lo persiste come documento del portale.

    L'hash del documento resta così stabile fra visualizzazione e accettazione
    (i generatori ReportLab non sono deterministici tra invocazioni).
    """

    tenant_id = _text(invite.get("tenant_id"))
    matter_id = _text(invite.get("matter_id"))
    existing = repo.find_documents_by_request(tenant_id, matter_id=matter_id, request_id=request_id)
    if existing:
        return existing[0]
    buffer = pdf_factory()
    data = buffer.getvalue() if isinstance(buffer, io.BytesIO) else bytes(buffer)
    if not data:
        raise ClientPortalError("Documento non disponibile.")
    return _persist_client_upload(
        repo,
        invite,
        data=data,
        original_name=filename,
        content_type="application/pdf",
        request_id=request_id,
        status="generato",
    )


def _preventivo_document(repo: ClientPortalRepository, invite: dict[str, Any], token: str, gp: Any, preventivo: Any) -> dict[str, Any]:
    cliente = _cliente_for_token(token, _text(invite.get("client_id")))
    fascicolo = _fascicolo_for_token(token, _text(getattr(preventivo, "id_fascicolo", "")))
    from web.blueprints.preventivi import _genera_pdf_preventivo

    return _materialize_pdf(
        repo,
        invite,
        request_id=_request_preventivo_pdf(_text(preventivo.id)),
        filename=f"preventivo_{_text(preventivo.numero).replace('/', '-')}.pdf",
        pdf_factory=lambda: _genera_pdf_preventivo(preventivo, cliente, fascicolo, current_app.config),
    )


def _conferimento_document(repo: ClientPortalRepository, invite: dict[str, Any], token: str, gp: Any, conferimento: Any) -> dict[str, Any]:
    cliente = _cliente_for_token(token, _text(invite.get("client_id")))
    fascicolo = _fascicolo_for_token(token, _text(getattr(conferimento, "id_fascicolo", "")))
    preventivo = gp.get_preventivo(conferimento.id_preventivo) if getattr(conferimento, "id_preventivo", "") else None
    from web.blueprints.preventivi import _genera_pdf_conferimento

    return _materialize_pdf(
        repo,
        invite,
        request_id=_request_conferimento_pdf(_text(conferimento.id)),
        filename=f"conferimento_{_text(conferimento.numero).replace('/', '-')}.pdf",
        pdf_factory=lambda: _genera_pdf_conferimento(conferimento, cliente, fascicolo, preventivo, current_app.config),
    )


def _missing_client_data(repo: ClientPortalRepository, invite: dict[str, Any]) -> list[str]:
    profile = repo.get_profile(_text(invite.get("tenant_id")), _text(invite.get("client_id"))) or {}
    missing = [
        MINIMAL_CLIENT_FIELD_LABELS[field]
        for field in MINIMAL_CLIENT_FIELDS
        if not _text(profile.get(field))
    ]
    return missing


def _conferimento_for_invite(invite: dict[str, Any], gp: Any, preventivi: list[Any]):
    """Il conferimento del workflow: quello del preventivo accettato dell'invito."""

    for preventivo in preventivi:
        if preventivo.stato not in PREVENTIVO_STATI_ACCETTATI:
            continue
        conferimento = gp.get_conferimento_principale_preventivo(_text(preventivo.id))
        if conferimento is not None and conferimento.stato != StatoConferimento.REVOCATO:
            return preventivo, conferimento
    return None, None


def _identity_state(repo: ClientPortalRepository, invite: dict[str, Any]) -> dict[str, Any]:
    tenant_id = _text(invite.get("tenant_id"))
    matter_id = _text(invite.get("matter_id"))
    client_id = _text(invite.get("client_id"))
    consent = repo._fetchone(  # noqa: SLF001 - lookup interno consapevole
        "SELECT * FROM client_portal_consents WHERE tenant_id = ? AND client_id = ? AND matter_id = ? AND consent_key = ? AND version = ?",
        (tenant_id, client_id, matter_id, IDENTITY_CONSENT_KEY, CONSENT_VERSION),
    )
    documents = [
        row
        for row in repo.find_documents_by_request(tenant_id, matter_id=matter_id, request_id=REQUEST_IDENTITY_DOCUMENT)
        if _text(row.get("status")) != "sostituito"
    ]
    current = documents[0] if documents else None
    return {
        "consentAccepted": bool(int(consent.get("accepted") or 0)) if consent else False,
        "document": _public_row(current) if current else None,
    }


def _signature_state(repo: ClientPortalRepository, invite: dict[str, Any], conferimento: Any) -> dict[str, Any]:
    tenant_id = _text(invite.get("tenant_id"))
    matter_id = _text(invite.get("matter_id"))
    signed_docs = repo.find_documents_by_request(
        tenant_id, matter_id=matter_id, request_id=REQUEST_SIGNED_DOCUMENT
    )
    signed = signed_docs[0] if signed_docs else None
    return {
        "firmaEseguita": bool(getattr(conferimento, "firma_cliente_eseguita", False)) if conferimento else False,
        "firmaVia": _text(getattr(conferimento, "firma_cliente_via", "")) if conferimento else "",
        "signedDocument": _public_row(signed) if signed else None,
    }


def _preventivo_summary(repo: ClientPortalRepository, invite: dict[str, Any], token: str, gp: Any, preventivo: Any) -> dict[str, Any]:
    document: dict[str, Any] | None = None
    try:
        document = _preventivo_document(repo, invite, token, gp, preventivo)
    except ClientPortalError:
        document = None
    return {
        "id": _text(preventivo.id),
        "numero": _text(preventivo.numero),
        "oggetto": _text(preventivo.oggetto),
        "stato": _stato_value(preventivo),
        "versione": int(getattr(preventivo, "versione", 1) or 1),
        "totale": round(float(getattr(preventivo, "totale", 0.0) or 0.0), 2),
        "dataEmissione": _text(getattr(preventivo, "data_emissione", "")),
        "dataScadenza": _text(getattr(preventivo, "data_scadenza", "")),
        "documentId": _text(document.get("id")) if document else "",
        "pdfSha256": _text(document.get("sha256")) if document else "",
        "highlighted": _text(preventivo.id) == _invite_preventivo_id(invite),
        "accettatoIl": _text(getattr(preventivo, "accettato_il", "")),
    }


def _otp_step_up_required(repo: ClientPortalRepository, tenant_id: str) -> bool:
    settings = repo.get_settings(tenant_id)
    signatures = settings.get("signatures") if isinstance(settings.get("signatures"), dict) else {}
    return bool(signatures.get("otpStepUp"))


def _overview_payload(invite: dict[str, Any], repo: ClientPortalRepository, token: str) -> dict[str, Any]:
    tenant_id = _text(invite.get("tenant_id"))
    gp = _gestione_preventivi_for_token(token)
    preventivi = _preventivi_for_invite(invite, gp)

    # Prima visualizzazione dal portale: INVIATO → APERTO (traccia dominio).
    for preventivo in preventivi:
        if preventivo.stato == StatoPreventivo.INVIATO:
            preventivo.portale_aperto_il = datetime.now(timezone.utc).isoformat()
            gp.cambia_stato_preventivo(_text(preventivo.id), StatoPreventivo.APERTO)

    accepted_preventivo, conferimento = _conferimento_for_invite(invite, gp, preventivi)
    missing = _missing_client_data(repo, invite)
    conferimento_state: dict[str, Any] = {
        "available": False,
        "id": "",
        "numero": "",
        "oggetto": "",
        "stato": "",
        "documentId": "",
        "pdfSha256": "",
        "missingClientData": missing,
        "requisiti": [],
    }
    if not any(p.stato in PREVENTIVO_STATI_ACCETTATI for p in preventivi):
        conferimento_state["requisiti"].append("Accettare prima il preventivo.")
    if missing:
        conferimento_state["requisiti"].append(
            "Completare l'anagrafica: " + ", ".join(missing) + "."
        )
    if conferimento is not None and not conferimento_state["requisiti"]:
        document: dict[str, Any] | None = None
        try:
            document = _conferimento_document(repo, invite, token, gp, conferimento)
        except ClientPortalError:
            document = None
        conferimento_state.update(
            {
                "available": True,
                "id": _text(conferimento.id),
                "numero": _text(conferimento.numero),
                "oggetto": _text(conferimento.oggetto),
                "stato": _stato_value(conferimento),
                "documentId": _text(document.get("id")) if document else "",
                "pdfSha256": _text(document.get("sha256")) if document else "",
                "preventivoId": _text(getattr(conferimento, "id_preventivo", "") or ""),
            }
        )

    signature = _signature_state(repo, invite, conferimento)
    identity = _identity_state(repo, invite)

    preventivo_done = any(p.stato in PREVENTIVO_STATI_ACCETTATI for p in preventivi)
    preventivo_rejected = bool(preventivi) and all(
        p.stato == StatoPreventivo.RIFIUTATO for p in preventivi
    )
    steps = [
        {"key": "benvenuto", "title": "Benvenuto e verifica accesso", "status": "completato"},
        {
            "key": "dati",
            "title": "Dati cliente",
            "status": "completato" if not missing else "da_fare",
        },
        {
            "key": "identita",
            "title": "Documento d'identità",
            "status": (
                "in_revisione"
                if identity["document"] and _text(identity["document"].get("status")) == "in_revisione"
                else "completato"
                if identity["document"]
                else "da_fare"
            ),
        },
        {
            "key": "preventivo",
            "title": "Preventivo",
            "status": (
                "completato"
                if preventivo_done
                else "rifiutato"
                if preventivo_rejected
                else "da_fare"
                if preventivi
                else "in_attesa"
            ),
        },
        {
            "key": "conferimento",
            "title": "Conferimento incarico",
            "status": "completato" if conferimento_state["available"] else "in_attesa",
        },
        {
            "key": "firma",
            "title": "Firma documenti",
            "status": "completato" if signature["firmaEseguita"] else (
                "da_fare" if conferimento_state["available"] else "in_attesa"
            ),
        },
        {
            "key": "riepilogo",
            "title": "Riepilogo e ricevuta",
            "status": "completato" if signature["firmaEseguita"] else "in_attesa",
        },
    ]

    return {
        "ok": True,
        "surface": "signing",
        "steps": steps,
        "preventivi": [
            _preventivo_summary(repo, invite, token, gp, preventivo) for preventivo in preventivi
        ],
        "conferimento": conferimento_state,
        "signature": signature,
        "identity": identity,
        "consents": consent_texts_payload(),
        "otpStepUp": _otp_step_up_required(repo, tenant_id),
        "qualifiedSignature": {
            "available": False,
            "note": (
                "La firma qualificata remota non è disponibile: questo flusso "
                "produce una firma elettronica semplice con pacchetto di evidenze."
            ),
        },
    }


def client_signing_overview() -> dict[str, Any]:
    if not _signing_enabled():
        return _signing_disabled_payload()
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        return _overview_payload(invite, repo, token)
    except ClientPortalError:
        return _invalid_invite_payload()


# ---------------------------------------------------------------- preventivo


def _preventivo_evidence(
    invite: dict[str, Any],
    token: str,
    *,
    action: str,
    preventivo: Any,
    document: dict[str, Any] | None,
    consent_text: str,
    declaration: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_signature_evidence_pack(
        signature_id=f"{action}:{_text(preventivo.id)}",
        signature_type=SignatureType.GRAPHIC_INTERNAL,
        provider="portale_cliente_workflow",
        tenant_id=_text(invite.get("tenant_id")),
        client_id=_text(invite.get("client_id")),
        matter_id=_text(invite.get("matter_id")),
        document_id=_text(document.get("id")) if document else "",
        consent_text=consent_text,
        consent_version=CONSENT_VERSION,
        declaration=declaration,
        original_sha256=_text(document.get("sha256")) if document else "",
        ip=_client_ip(),
        user_agent=_client_user_agent(),
        token=token,
        extra={"azione": action, "documentVersion": int(getattr(preventivo, "versione", 1) or 1), **(extra or {})},
    )


def client_accept_preventivo(preventivo_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not _signing_enabled():
        return _signing_disabled_payload()
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        tenant_id = _text(invite.get("tenant_id"))
        gp = _gestione_preventivi_for_token(token)
        preventivo = _preventivo_of_invite_or_none(invite, gp, preventivo_id)
        if preventivo is None:
            return _validation_error("Preventivo non disponibile.")
        if preventivo.stato in PREVENTIVO_STATI_ACCETTATI:
            return _validation_error("Preventivo già accettato.")
        if preventivo.stato not in PREVENTIVO_STATI_ACCETTABILI:
            return _validation_error("Questo preventivo non è più accettabile dal portale.")
        if not bool(payload.get("accepted")):
            return _validation_error("Conferma espressamente l'accettazione del preventivo.")
        document = _preventivo_document(repo, invite, token, gp, preventivo)
        expected_sha = _text(payload.get("pdfSha256"))
        if expected_sha and expected_sha != _text(document.get("sha256")):
            return _validation_error("Il documento è cambiato: ricarica la pagina e rileggi il preventivo.")

        client_profile = repo.get_profile(tenant_id, _text(invite.get("client_id"))) or {}
        gp.registra_accettazione_preventivo(
            _text(preventivo.id),
            workflow_channel="ONLINE",
            via="PORTALE_CLIENTE_APP",
            ip=_client_ip(),
            user_agent=_client_user_agent(),
            avvocato_referente=_text(getattr(preventivo, "creato_da", "")),
            auto_crea_conferimento=True,
            studio_piva=_text(current_app.config.get("STUDIO_PIVA")),
            studio_cf=_text(current_app.config.get("STUDIO_CF")),
            studio_indirizzo=_text(current_app.config.get("STUDIO_INDIRIZZO")),
        )
        declaration = _text(payload.get("declaration")) or PREVENTIVO_CONSENT_TEXT
        evidence = _preventivo_evidence(
            invite,
            token,
            action="accettazione_preventivo",
            preventivo=preventivo,
            document=document,
            consent_text=PREVENTIVO_CONSENT_TEXT,
            declaration=declaration,
            extra={"clienteDisplay": _text(client_profile.get("display_name"))},
        )
        repo.set_consent(
            tenant_id,
            client_id=_text(invite.get("client_id")),
            matter_id=_text(invite.get("matter_id")),
            consent_key=PREVENTIVO_CONSENT_KEY,
            version=CONSENT_VERSION,
            accepted=True,
            payload=evidence,
        )
        repo.record_audit(
            tenant_id,
            "cliente",
            _text(invite.get("client_id")),
            "client_portal.preventivo.accettato",
            "preventivo",
            _text(preventivo.id),
            {"sha256": _text(document.get("sha256")), "ipHash": evidence.get("ipHash"), "versione": evidence.get("documentVersion")},
        )
        _notify_studio(
            repo,
            invite,
            title="Preventivo accettato dal cliente",
            body=f"Il preventivo {preventivo.numero} è stato accettato dal Portale Cliente.",
        )
        return {
            "ok": True,
            "message": "Preventivo accettato.",
            "overview": _overview_payload(invite, repo, token),
        }
    except ClientPortalError:
        return _invalid_invite_payload()


def client_decline_preventivo(preventivo_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not _signing_enabled():
        return _signing_disabled_payload()
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        tenant_id = _text(invite.get("tenant_id"))
        gp = _gestione_preventivi_for_token(token)
        preventivo = _preventivo_of_invite_or_none(invite, gp, preventivo_id)
        if preventivo is None:
            return _validation_error("Preventivo non disponibile.")
        if preventivo.stato not in PREVENTIVO_STATI_ACCETTABILI:
            return _validation_error("Questo preventivo non è rifiutabile dal portale.")
        reason = _text(payload.get("reason"))[:DECLINE_REASON_MAX_CHARS]
        gp.cambia_stato_preventivo(_text(preventivo.id), StatoPreventivo.RIFIUTATO)
        document: dict[str, Any] | None = None
        try:
            document = _preventivo_document(repo, invite, token, gp, preventivo)
        except ClientPortalError:
            document = None
        evidence = _preventivo_evidence(
            invite,
            token,
            action="rifiuto_preventivo",
            preventivo=preventivo,
            document=document,
            consent_text=PREVENTIVO_CONSENT_TEXT,
            declaration=reason or "Preventivo rifiutato dal cliente.",
            extra={"motivo": reason},
        )
        repo.set_consent(
            tenant_id,
            client_id=_text(invite.get("client_id")),
            matter_id=_text(invite.get("matter_id")),
            consent_key=PREVENTIVO_CONSENT_KEY,
            version=CONSENT_VERSION,
            accepted=False,
            payload=evidence,
        )
        repo.record_audit(
            tenant_id,
            "cliente",
            _text(invite.get("client_id")),
            "client_portal.preventivo.rifiutato",
            "preventivo",
            _text(preventivo.id),
            {"motivo": reason, "ipHash": evidence.get("ipHash")},
        )
        _notify_studio(
            repo,
            invite,
            title="Preventivo rifiutato dal cliente",
            body=f"Il preventivo {preventivo.numero} è stato rifiutato." + (f" Motivo: {reason}" if reason else ""),
        )
        return {
            "ok": True,
            "message": "Rifiuto registrato. Lo studio è stato informato.",
            "overview": _overview_payload(invite, repo, token),
        }
    except ClientPortalError:
        return _invalid_invite_payload()


# ---------------------------------------------------------------- OTP step-up
# Riusa le primitive hash/anti-bruteforce di pct.client_portal_access: codice
# salvato SOLO come hash con pepper, TTL, tentativi limitati, mai nei log.


def _otp_pepper() -> str:
    return _text(current_app.secret_key or current_app.config.get("SECRET_KEY") or "iusentra-otp")


def _otp_grant_row(repo: ClientPortalRepository, invite: dict[str, Any]) -> dict[str, Any]:
    return repo._fetchone(  # noqa: SLF001 - accesso interno consapevole
        "SELECT * FROM client_portal_consents WHERE tenant_id = ? AND client_id = ? AND matter_id = ? AND consent_key = ? AND version = ?",
        (
            _text(invite.get("tenant_id")),
            _text(invite.get("client_id")),
            _text(invite.get("matter_id")),
            OTP_GRANT_CONSENT_KEY,
            "1",
        ),
    )


def _otp_grant_save(repo: ClientPortalRepository, invite: dict[str, Any], grant: dict[str, Any]) -> None:
    existing = _otp_grant_row(repo, invite)
    values = {"payload_json": json_dumps(grant), "accepted": 0, "accepted_at": ""}
    if existing:
        repo._update("client_portal_consents", values, "id = ?", (existing["id"],))  # noqa: SLF001
    else:
        repo._insert(  # noqa: SLF001
            "client_portal_consents",
            {
                "id": new_id("cpc"),
                "tenant_id": _text(invite.get("tenant_id")),
                "client_id": _text(invite.get("client_id")),
                "matter_id": _text(invite.get("matter_id")),
                "consent_key": OTP_GRANT_CONSENT_KEY,
                "version": "1",
                **values,
            },
        )


def _otp_grant_load(repo: ClientPortalRepository, invite: dict[str, Any]) -> dict[str, Any]:
    row = _otp_grant_row(repo, invite)
    grant = json_loads(row.get("payload_json"), {}) if row else {}
    return grant if isinstance(grant, dict) else {}


def _otp_send_email(invite: dict[str, Any], repo: ClientPortalRepository, code: str) -> tuple[bool, str]:
    """Invia il codice via email del profilo cliente. Fail-closed: (ok, motivo)."""

    profile = repo.get_profile(_text(invite.get("tenant_id")), _text(invite.get("client_id"))) or {}
    email = _text(profile.get("email"))
    if not email:
        return False, "Nessuna email registrata nel profilo cliente."
    getter = _core_runtime_func("get_messaggi")
    if not callable(getter):
        return False, "Canale email dello studio non disponibile."
    try:
        messaggi = getter()
        esito = messaggi.invia_email(
            destinatario=email,
            oggetto="Codice di verifica firma — Portale Cliente",
            corpo_testo=(
                "Il tuo codice di verifica per confermare la firma sul Portale Cliente è: "
                f"{code}\n\nIl codice scade tra {OTP_TTL_MINUTES} minuti. "
                "Se non hai richiesto tu questa operazione, contatta lo studio."
            ),
            id_cliente=_text(invite.get("client_id")),
            tipo_automazione="portale_cliente_otp",
        )
        stato = _text(getattr(getattr(esito, "stato", ""), "value", getattr(esito, "stato", ""))).lower()
        if stato and stato not in {"inviato"}:
            return False, "Invio email non riuscito."
        return True, ""
    except Exception:
        current_app.logger.exception("Invio OTP portale cliente non riuscito")
        return False, "Invio email non riuscito."


def client_signing_otp_start() -> dict[str, Any]:
    if not _signing_enabled():
        return _signing_disabled_payload()
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        tenant_id = _text(invite.get("tenant_id"))
        if not _otp_step_up_required(repo, tenant_id):
            return _validation_error("La verifica con codice non è richiesta da questo studio.")
        code = generate_otp()
        now = datetime.now(timezone.utc)
        grant = {
            "otp_hash": hash_secret(code, pepper=_otp_pepper()),
            "expires_at": (now + timedelta(minutes=OTP_TTL_MINUTES)).isoformat(),
            "attempts": 0,
            "status": "inviato",
            "verified_at": "",
        }
        sent, reason = _otp_send_email(invite, repo, code)
        if not sent:
            return _validation_error(
                "Impossibile inviare il codice di verifica. " + reason + " Contatta lo studio."
            )
        _otp_grant_save(repo, invite, grant)
        repo.record_audit(tenant_id, "cliente", _text(invite.get("client_id")), "client_portal.firma.otp_inviato", "otp", "firma", {})
        return {"ok": True, "message": "Codice inviato via email.", "expiresMinutes": OTP_TTL_MINUTES}
    except ClientPortalError:
        return _invalid_invite_payload()


def client_signing_otp_verify(payload: dict[str, Any]) -> dict[str, Any]:
    if not _signing_enabled():
        return _signing_disabled_payload()
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        tenant_id = _text(invite.get("tenant_id"))
        grant = _otp_grant_load(repo, invite)
        if not grant or grant.get("status") not in {"inviato"}:
            return _validation_error("Richiedi prima un codice di verifica.")
        if int(grant.get("attempts") or 0) >= OTP_MAX_ATTEMPTS:
            return _validation_error("Troppi tentativi: richiedi un nuovo codice.")
        try:
            expired = datetime.fromisoformat(str(grant.get("expires_at"))) < datetime.now(timezone.utc)
        except (TypeError, ValueError):
            expired = True
        if expired:
            return _validation_error("Codice scaduto: richiedine uno nuovo.")
        code = _text(payload.get("code"))
        if not constant_time_match(code, str(grant.get("otp_hash") or ""), pepper=_otp_pepper()):
            grant["attempts"] = int(grant.get("attempts") or 0) + 1
            if grant["attempts"] >= OTP_MAX_ATTEMPTS:
                grant["status"] = "bloccato"
            _otp_grant_save(repo, invite, grant)
            if grant["status"] == "bloccato":
                return _validation_error("Troppi tentativi: richiedi un nuovo codice.")
            return _validation_error("Codice non corretto.")
        grant["status"] = "verificato"
        grant["verified_at"] = datetime.now(timezone.utc).isoformat()
        _otp_grant_save(repo, invite, grant)
        repo.record_audit(tenant_id, "cliente", _text(invite.get("client_id")), "client_portal.firma.otp_verificato", "otp", "firma", {})
        return {"ok": True, "message": "Codice verificato: puoi procedere con la firma."}
    except ClientPortalError:
        return _invalid_invite_payload()


def _otp_grant_verified(repo: ClientPortalRepository, invite: dict[str, Any]) -> bool:
    grant = _otp_grant_load(repo, invite)
    if grant.get("status") != "verificato":
        return False
    try:
        verified_at = datetime.fromisoformat(str(grant.get("verified_at")))
    except (TypeError, ValueError):
        return False
    return datetime.now(timezone.utc) - verified_at <= timedelta(minutes=OTP_TTL_MINUTES)


def _otp_grant_consume(repo: ClientPortalRepository, invite: dict[str, Any]) -> None:
    grant = _otp_grant_load(repo, invite)
    if grant:
        grant["status"] = "usato"
        _otp_grant_save(repo, invite, grant)


# ---------------------------------------------------------------- firma conferimento


def _decode_signature_image(data_url: str) -> bytes:
    """Decodifica il data URL JPEG del tratto firma (mai loggato né persistito in chiaro)."""

    text = _text(data_url)
    if not text:
        return b""
    prefix = "data:image/jpeg;base64,"
    if not text.startswith(prefix):
        raise ClientPortalError("L'immagine della firma deve essere un JPEG.")
    try:
        raw = base64.b64decode(text[len(prefix):], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ClientPortalError("Immagine firma non leggibile.") from exc
    if len(raw) > SIGNATURE_IMAGE_MAX_BYTES:
        raise ClientPortalError("L'immagine della firma supera i 300 KB: riduci la qualità e riprova.")
    if not is_jpeg_bytes(raw):
        raise ClientPortalError("L'immagine della firma deve essere un JPEG.")
    return raw


def _validate_signing_consents(payload: dict[str, Any]) -> dict[str, bool]:
    consents = payload.get("consents")
    consents = consents if isinstance(consents, dict) else {}
    missing = [key for key in SIGNING_CONSENT_KEYS if not bool(consents.get(key))]
    if missing:
        raise ClientPortalError("Tutti i consensi sono obbligatori per firmare il documento.")
    return {key: True for key in SIGNING_CONSENT_KEYS}


def _clamped_position(payload: dict[str, Any]) -> dict[str, Any]:
    position = payload.get("position")
    position = position if isinstance(position, dict) else {}

    def _num(key: str, default: float, low: float, high: float) -> float:
        try:
            value = float(position.get(key, default))
        except (TypeError, ValueError):
            value = default
        return max(low, min(value, high))

    try:
        page_index = int(position.get("pageIndex", -1))
    except (TypeError, ValueError):
        page_index = -1
    return {
        "pageIndex": max(-1, min(page_index, 500)),
        "xMm": _num("xMm", 110.0, 0.0, 500.0),
        "yMm": _num("yMm", 12.0, 0.0, 500.0),
        "widthMm": _num("widthMm", 85.0, 20.0, 200.0),
        "heightMm": _num("heightMm", 26.0, 12.0, 120.0),
    }


def _conferimento_of_invite_or_none(invite: dict[str, Any], gp: Any, conferimento_id: str):
    conferimento = gp.get_conferimento(_text(conferimento_id))
    if conferimento is None:
        return None
    if _text(conferimento.id_cliente) != _text(invite.get("client_id")):
        return None
    if conferimento.stato == StatoConferimento.REVOCATO:
        return None
    return conferimento


def _conferimento_ready(invite: dict[str, Any], repo: ClientPortalRepository, gp: Any, conferimento: Any) -> str:
    """Ritorna il motivo del blocco (stringa vuota = firmabile)."""

    preventivo = gp.get_preventivo(conferimento.id_preventivo) if getattr(conferimento, "id_preventivo", "") else None
    if preventivo is None or preventivo.stato not in PREVENTIVO_STATI_ACCETTATI:
        return "Il conferimento è disponibile solo dopo l'accettazione del preventivo."
    missing = _missing_client_data(repo, invite)
    if missing:
        return "Completa prima l'anagrafica: " + ", ".join(missing) + "."
    if bool(getattr(conferimento, "firma_cliente_eseguita", False)):
        return "Il documento risulta già firmato."
    return ""


def _rfc3161_best_effort(repo: ClientPortalRepository, invite: dict[str, Any], signed_pdf: bytes, signed_sha256: str) -> dict[str, Any]:
    """Marca temporale RFC 3161 sul PDF firmato (data certa di terza parte). Mai bloccante."""

    if current_app.config.get("TESTING") or not current_app.config.get("CLIENT_PORTAL_TSA_ENABLED", True):
        return {"tsaStatus": "disattivata"}
    try:
        from pct.rfc3161 import richiedi_timestamp, salva_token

        esito = richiedi_timestamp(signed_pdf)
        if not esito.get("ok"):
            return {"tsaStatus": "non_disponibile"}
        token_dir = repo.db_path.parent / "tsa"
        token_dir.mkdir(parents=True, exist_ok=True)
        path = salva_token(esito.get("token") or b"", str(token_dir / f"firma_{signed_sha256[:16]}"))
        return {"tsaStatus": "ok", "tsaUrl": _text(esito.get("tsa_url")), "tsaTokenName": Path(path).name}
    except Exception:
        current_app.logger.info("Marca temporale RFC 3161 non disponibile per la firma portale.")
        return {"tsaStatus": "non_disponibile"}


def _worm_audit_best_effort(invite: dict[str, Any], gp: Any, conferimento: Any, *, signature_id: str, evidence: dict[str, Any]) -> str:
    """Emette gli hash della firma sul WORM audit forense se configurato. Mai bloccante.

    Il fascicolo di riferimento è quello del conferimento (o dell'invito):
    senza fascicolo il WORM non viene coinvolto. Nel WORM finiscono solo hash.
    """

    fascicolo_id = _text(getattr(conferimento, "id_fascicolo", "")) or ""
    if not fascicolo_id:
        matter = evidence.get("matterId")
        fascicolo_id = _text(matter)
    try:
        from audit.integrations import emit_client_signature_acquired

        result = emit_client_signature_acquired(
            fascicolo_id=fascicolo_id,
            signature_id=signature_id,
            conferimento_id=_text(getattr(conferimento, "id", "")),
            original_sha256=_text(evidence.get("originalSha256")),
            signed_sha256=_text(evidence.get("signedSha256")),
            evidence_sha256=_text(evidence.get("payloadSha256")),
            tenant_id=_text(invite.get("tenant_id")),
        )
        return _text(getattr(result, "event_hash", ""))
    except Exception:
        return ""


def client_sign_conferimento(conferimento_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not _signing_enabled():
        return _signing_disabled_payload()
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        tenant_id = _text(invite.get("tenant_id"))
        client_id = _text(invite.get("client_id"))
        matter_id = _text(invite.get("matter_id"))
        gp = _gestione_preventivi_for_token(token)
        conferimento = _conferimento_of_invite_or_none(invite, gp, conferimento_id)
        if conferimento is None:
            return _validation_error("Conferimento non disponibile.")
        blocked = _conferimento_ready(invite, repo, gp, conferimento)
        if blocked:
            return _validation_error(blocked)
        try:
            _validate_signing_consents(payload)
            signature_image = _decode_signature_image(_text(payload.get("signatureImage")))
        except ClientPortalError as exc:
            return _validation_error(str(exc))
        if _otp_step_up_required(repo, tenant_id) and not _otp_grant_verified(repo, invite):
            return _validation_error("Verifica prima la tua identità con il codice ricevuto via email.")

        document = _conferimento_document(repo, invite, token, gp, conferimento)
        original_bytes = _document_bytes(repo, document)
        expected_sha = _text(payload.get("pdfSha256"))
        if expected_sha and expected_sha != _text(document.get("sha256")):
            return _validation_error("Il documento è cambiato: ricarica la pagina e rileggilo prima di firmare.")

        profile = repo.get_profile(tenant_id, client_id) or {}
        signer_name = _text(payload.get("typedName")) or _text(profile.get("display_name")) or "Cliente"
        position = _clamped_position(payload)
        consent_text = "\n".join(SIGNING_CONSENTS[key] for key in SIGNING_CONSENT_KEYS)
        declaration = _text(payload.get("declaration")) or "Firma elettronica applicata dal Portale Cliente."
        provider = InternalGraphicSignatureProvider()
        try:
            result = provider.create_signature_request(
                SignatureRequest(
                    signature_id=new_id("cpsr"),
                    signature_type=SignatureType.GRAPHIC_INTERNAL,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    matter_id=matter_id,
                    document_id=_text(document.get("id")),
                ),
                pdf_bytes=original_bytes,
                signer_name=signer_name,
                when_label=_iso_to_rome_label(utc_now()),
                reference=f"Conferimento {conferimento.numero}",
                consent_text=consent_text,
                consent_version=CONSENT_VERSION,
                declaration=declaration,
                ip=_client_ip(),
                user_agent=_client_user_agent(),
                token=token,
                signature_coordinates=position,
                signature_image=signature_image,
            )
        except SignatureProviderError as exc:
            return _validation_error(str(exc))

        signed_document = _persist_client_upload(
            repo,
            invite,
            data=result.signed_pdf or b"",
            original_name=f"conferimento_{_text(conferimento.numero).replace('/', '-')}_firmato.pdf",
            content_type="application/pdf",
            request_id=REQUEST_SIGNED_DOCUMENT,
            status=CLIENT_PORTAL_DOCUMENT_FINAL_STATUS,
        )
        evidence = dict(result.evidence)
        evidence["signedDocumentId"] = _text(signed_document.get("id"))
        evidence["conferimentoId"] = _text(conferimento.id)
        evidence.update(
            _rfc3161_best_effort(repo, invite, result.signed_pdf or b"", _text(signed_document.get("sha256")))
        )

        signature_row = repo.add_signature_request(
            tenant_id,
            matter_id=matter_id,
            title=f"Conferimento incarico {conferimento.numero}",
            description="Firma elettronica applicata dal workflow del Portale Cliente.",
            document_id=_text(document.get("id")),
        )
        worm_ref = _worm_audit_best_effort(
            invite, gp, conferimento, signature_id=_text(signature_row.get("id")), evidence=evidence
        )
        if worm_ref:
            evidence["wormAuditRef"] = worm_ref
        repo.complete_signature(tenant_id, _text(signature_row.get("id")), client_id=client_id, evidence=evidence)
        # Consenso di accettazione del conferimento: distinto da quello del preventivo.
        repo.set_consent(
            tenant_id,
            client_id=client_id,
            matter_id=matter_id,
            consent_key=CONFERIMENTO_CONSENT_KEY,
            version=CONSENT_VERSION,
            accepted=True,
            payload={
                "conferimentoId": _text(conferimento.id),
                "consentText": CONFERIMENTO_CONSENT_TEXT,
                "tokenRef": token_reference(token),
            },
        )
        for key in SIGNING_CONSENT_KEYS:
            repo.set_consent(
                tenant_id,
                client_id=client_id,
                matter_id=matter_id,
                consent_key=key,
                version=CONSENT_VERSION,
                accepted=True,
                payload={"conferimentoId": _text(conferimento.id), "tokenRef": token_reference(token)},
            )
        gp.registra_firma_conferimento(
            _text(conferimento.id),
            via="PORTALE_CLIENTE_APP",
            workflow_channel="ONLINE",
            ip=_client_ip(),
            user_agent=_client_user_agent(),
        )
        if _otp_step_up_required(repo, tenant_id):
            _otp_grant_consume(repo, invite)
        repo.record_audit(
            tenant_id,
            "cliente",
            client_id,
            "client_portal.conferimento.firmato",
            "conferimento",
            _text(conferimento.id),
            {
                "originalSha256": _text(document.get("sha256")),
                "signedSha256": _text(signed_document.get("sha256")),
                "ipHash": evidence.get("ipHash"),
            },
        )
        _notify_studio(
            repo,
            invite,
            title="Conferimento firmato dal cliente",
            body=f"Il conferimento {conferimento.numero} è stato firmato dal Portale Cliente.",
        )
        return {
            "ok": True,
            "message": "Incarico firmato e inviato allo studio.",
            "signedDocumentId": _text(signed_document.get("id")),
            "overview": _overview_payload(invite, repo, token),
        }
    except ClientPortalError:
        return _invalid_invite_payload()


def client_upload_signed_conferimento(conferimento_id: str, file: Any, form: dict[str, Any]) -> dict[str, Any]:
    """Fallback: il cliente scarica il conferimento, lo firma a mano e lo ricarica."""

    if not _signing_enabled():
        return _signing_disabled_payload()
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        tenant_id = _text(invite.get("tenant_id"))
        client_id = _text(invite.get("client_id"))
        matter_id = _text(invite.get("matter_id"))
        gp = _gestione_preventivi_for_token(token)
        conferimento = _conferimento_of_invite_or_none(invite, gp, conferimento_id)
        if conferimento is None:
            return _validation_error("Conferimento non disponibile.")
        blocked = _conferimento_ready(invite, repo, gp, conferimento)
        if blocked:
            return _validation_error(blocked)
        try:
            _validate_signing_consents(form)
        except ClientPortalError as exc:
            return _validation_error(str(exc))
        if file is None or not _text(getattr(file, "filename", "")):
            return _validation_error("Carica il PDF firmato.")
        content_type = _text(getattr(file, "mimetype", ""))
        if content_type != "application/pdf":
            return _validation_error("Il documento firmato deve essere un PDF.")
        data = file.read()
        if not data:
            return _validation_error("Il file caricato è vuoto.")
        if len(data) > SIGNED_UPLOAD_MAX_BYTES:
            return _validation_error("Il PDF firmato supera i 25 MB.")

        document = _conferimento_document(repo, invite, token, gp, conferimento)
        original_bytes = _document_bytes(repo, document)
        declaration = _text(form.get("declaration")) or MANUAL_UPLOAD_DECLARATION
        provider = ManualUploadSignatureProvider()
        result = provider.create_signature_request(
            SignatureRequest(
                signature_id=new_id("cpsr"),
                signature_type=SignatureType.MANUAL_UPLOAD,
                tenant_id=tenant_id,
                client_id=client_id,
                matter_id=matter_id,
                document_id=_text(document.get("id")),
            ),
            original_pdf_bytes=original_bytes,
            signed_pdf_bytes=data,
            consent_text="\n".join(SIGNING_CONSENTS[key] for key in SIGNING_CONSENT_KEYS),
            consent_version=CONSENT_VERSION,
            declaration=declaration,
            ip=_client_ip(),
            user_agent=_client_user_agent(),
            token=token,
        )
        # L'upload manuale va in revisione: lo studio verifica la firma autografa.
        signed_document = _persist_client_upload(
            repo,
            invite,
            data=data,
            original_name=f"conferimento_{_text(conferimento.numero).replace('/', '-')}_firmato.pdf",
            content_type="application/pdf",
            request_id=REQUEST_SIGNED_DOCUMENT,
            status="in_revisione",
        )
        evidence = dict(result.evidence)
        evidence["signedDocumentId"] = _text(signed_document.get("id"))
        evidence["conferimentoId"] = _text(conferimento.id)
        signature_row = repo.add_signature_request(
            tenant_id,
            matter_id=matter_id,
            title=f"Conferimento incarico {conferimento.numero} (upload firmato)",
            description="Documento firmato a mano e ricaricato dal cliente.",
            document_id=_text(document.get("id")),
        )
        repo.complete_signature(tenant_id, _text(signature_row.get("id")), client_id=client_id, evidence=evidence)
        repo.set_consent(
            tenant_id,
            client_id=client_id,
            matter_id=matter_id,
            consent_key=CONFERIMENTO_CONSENT_KEY,
            version=CONSENT_VERSION,
            accepted=True,
            payload={
                "conferimentoId": _text(conferimento.id),
                "consentText": CONFERIMENTO_CONSENT_TEXT,
                "tokenRef": token_reference(token),
                "via": "upload_manuale",
            },
        )
        for key in SIGNING_CONSENT_KEYS:
            repo.set_consent(
                tenant_id,
                client_id=client_id,
                matter_id=matter_id,
                consent_key=key,
                version=CONSENT_VERSION,
                accepted=True,
                payload={"conferimentoId": _text(conferimento.id), "tokenRef": token_reference(token), "via": "upload_manuale"},
            )
        gp.registra_firma_conferimento(
            _text(conferimento.id),
            via="PORTALE_CLIENTE_UPLOAD",
            workflow_channel="ONLINE",
            ip=_client_ip(),
            user_agent=_client_user_agent(),
        )
        repo.record_audit(
            tenant_id,
            "cliente",
            client_id,
            "client_portal.conferimento.upload_firmato",
            "conferimento",
            _text(conferimento.id),
            {
                "originalSha256": _text(document.get("sha256")),
                "signedSha256": _text(signed_document.get("sha256")),
                "ipHash": evidence.get("ipHash"),
            },
        )
        _notify_studio(
            repo,
            invite,
            title="Conferimento firmato caricato dal cliente",
            body=f"Il conferimento {conferimento.numero} firmato a mano è in revisione.",
        )
        return {
            "ok": True,
            "message": "Documento firmato ricevuto: lo studio lo verificherà a breve.",
            "signedDocumentId": _text(signed_document.get("id")),
            "overview": _overview_payload(invite, repo, token),
        }
    except ClientPortalError:
        return _invalid_invite_payload()


# ---------------------------------------------------------------- documento identità


IDENTITY_ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png"}
IDENTITY_MAX_BYTES = 20 * 1024 * 1024


def client_upload_identity_document(file: Any) -> dict[str, Any]:
    if not _signing_enabled():
        return _signing_disabled_payload()
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        tenant_id = _text(invite.get("tenant_id"))
        matter_id = _text(invite.get("matter_id"))
        client_id = _text(invite.get("client_id"))
        identity = _identity_state(repo, invite)
        if not identity["consentAccepted"]:
            return _validation_error(
                "Serve prima il consenso esplicito all'acquisizione del documento d'identità."
            )
        if file is None or not _text(getattr(file, "filename", "")):
            return _validation_error("Seleziona o scatta il documento da inviare.")
        content_type = _text(getattr(file, "mimetype", ""))
        if content_type not in IDENTITY_ALLOWED_TYPES:
            return _validation_error("Formato non consentito: usa PDF, JPG o PNG.")
        data = file.read()
        if not data:
            return _validation_error("Il file caricato è vuoto.")
        if len(data) > IDENTITY_MAX_BYTES:
            return _validation_error("Il documento supera i 20 MB: riduci la risoluzione e riprova.")

        previous = repo.find_documents_by_request(tenant_id, matter_id=matter_id, request_id=REQUEST_IDENTITY_DOCUMENT)
        for row in previous:
            if _text(row.get("status")) not in {"sostituito", CLIENT_PORTAL_DOCUMENT_FINAL_STATUS}:
                repo.update_document_status(
                    tenant_id,
                    _text(row.get("id")),
                    status="sostituito",
                    actor_id=client_id,
                    actor_type="cliente",
                )
        original_name = _text(getattr(file, "filename", "")) or "documento_identita"
        document = _persist_client_upload(
            repo,
            invite,
            data=data,
            original_name=original_name,
            content_type=content_type,
            request_id=REQUEST_IDENTITY_DOCUMENT,
            status="in_revisione",
        )
        repo.record_audit(
            tenant_id,
            "cliente",
            client_id,
            "client_portal.identita.caricata",
            "document",
            _text(document.get("id")),
            {"sha256": _text(document.get("sha256")), "sostituiti": len(previous)},
        )
        _notify_studio(
            repo,
            invite,
            title="Documento d'identità ricevuto",
            body="Il cliente ha inviato il documento d'identità: è in revisione.",
        )
        return {
            "ok": True,
            "message": "Documento inviato: è in revisione presso lo studio.",
            "item": _public_row(document),
            "overview": _overview_payload(invite, repo, token),
        }
    except ClientPortalError:
        return _invalid_invite_payload()


def studio_review_document(document_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Revisione studio di un documento del portale (identità o firmato manuale)."""

    from flask import g

    if not _signing_enabled():
        return _signing_disabled_payload()
    user = g.get("utente_corrente")
    if not (user and getattr(user, "ha_permesso", lambda _p: False)("clienti.scrivi")):
        return {"ok": False, "code": "forbidden", "message": "Permesso clienti.scrivi richiesto."}
    from web.services.react_client_portal_bridge import _actor_id, repository_for_current_request, _current_tenant_id

    repo = repository_for_current_request()
    tenant_id = _current_tenant_id()
    decision = _text(payload.get("decision"))
    if decision not in {"approvato", "respinto"}:
        return _validation_error("Decisione non valida: usare 'approvato' o 'respinto'.")
    try:
        row = repo.update_document_status(
            tenant_id,
            _text(document_id),
            status=decision,
            reviewed_at=utc_now(),
            review_note=_text(payload.get("note")),
            actor_id=_actor_id(),
        )
    except ClientPortalError as exc:
        return _validation_error(str(exc))
    return {"ok": True, "message": "Revisione registrata.", "item": _public_row(row, include_private=True)}


# ---------------------------------------------------------------- ricevuta


def client_signing_receipt() -> dict[str, Any]:
    if not _signing_enabled():
        return _signing_disabled_payload()
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        overview = _overview_payload(invite, repo, token)
        preventivo_accettato = next(
            (p for p in overview["preventivi"] if p["stato"] in {"ACCETTATO", "CONVERTITO"}),
            None,
        )
        signature = overview["signature"]
        signed = signature.get("signedDocument") or {}
        receipt = {
            "generatoIl": _iso_to_rome_label(utc_now()),
            "preventivo": (
                {
                    "numero": preventivo_accettato["numero"],
                    "stato": preventivo_accettato["stato"],
                    "impronta": (preventivo_accettato.get("pdfSha256") or "")[:16],
                }
                if preventivo_accettato
                else None
            ),
            "conferimento": (
                {
                    "numero": overview["conferimento"].get("numero", ""),
                    "stato": overview["conferimento"].get("stato", ""),
                    "impronta": (overview["conferimento"].get("pdfSha256") or "")[:16],
                }
                if overview["conferimento"].get("id")
                else None
            ),
            "firma": {
                "eseguita": signature.get("firmaEseguita", False),
                "via": signature.get("firmaVia", ""),
                "documentoFirmatoId": _text(signed.get("id")),
                "improntaFirmato": (_text(signed.get("sha256")) or "")[:16],
                "tipo": "Firma elettronica semplice con pacchetto di evidenze (artt. 20-21 CAD)",
            },
            "identita": {
                "inviata": bool(overview["identity"].get("document")),
                "stato": _text((overview["identity"].get("document") or {}).get("status")),
            },
        }
        return {"ok": True, "receipt": receipt, "steps": overview["steps"]}
    except ClientPortalError:
        return _invalid_invite_payload()


def _notify_studio(repo: ClientPortalRepository, invite: dict[str, Any], *, title: str, body: str) -> None:
    tenant_id = _text(invite.get("tenant_id"))
    matter_id = _text(invite.get("matter_id"))
    client_id = _text(invite.get("client_id"))
    try:
        repo.add_message(
            tenant_id,
            matter_id=matter_id,
            sender_type="cliente",
            sender_id=client_id,
            body=f"{title}: {body}",
        )
    except ClientPortalError:
        pass
    repo.add_notification(
        tenant_id,
        client_id=client_id,
        matter_id=matter_id,
        title=title,
        body=body,
        kind="workflow",
        href="/app/portale-clienti",
    )
