"""Payload React per il workflow notifiche legali e comunicazioni cliente."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from pct.notifiche_legali import (
    DOCUMENT_ORIGIN_LABELS,
    LEGAL_NOTIFICATION_SUBJECT,
    LEGAL_RECIPIENT_ROLES,
    PUBLIC_PEC_REGISTERS,
    available_template_fields,
    client_communication_templates_version,
    list_client_communication_templates,
    list_notification_templates,
    legal_notification_automation_payload,
    normalise_custom_template,
    normalise_document_origin,
    notification_directive_matrix,
    office_notification_evidence_from_pec,
    template_preview_text,
    template_catalog_version,
)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _display_text(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    cleaned = re.sub(r"\b(demo|sample|repository)\b", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"[-–—]\s*$", "", cleaned).strip()
    return cleaned or raw


def _config_object(config_manager_or_config: Any) -> Any:
    return getattr(config_manager_or_config, "config", config_manager_or_config)


def _enum_value(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _first_attr(obj: Any, *names: str) -> str:
    for name in names:
        value = _text(getattr(obj, name, ""))
        if value:
            return value
    return ""


def _safe_call(label: str, callback: Any, fallback: Any) -> Any:
    try:
        return callback() if callable(callback) else fallback
    except Exception:
        return fallback


def _repo_from_getter(getter: Any) -> Any:
    if callable(getter):
        return _safe_call("repo", getter, None)
    return getter


def _infer_public_register(soggetto: Any, ruolo: str = "") -> str:
    tipo = _enum_value(getattr(soggetto, "tipo", "")).upper()
    qualifica = _text(getattr(soggetto, "qualifica", "")).lower()
    ruolo = ruolo.upper()
    if "DIFENSORE" in ruolo or "avv" in qualifica or "avvocato" in qualifica:
        return "reginde"
    if tipo == "PUBBLICA_AMMINISTRAZIONE":
        return "registro_ppaa"
    if tipo in {"PERSONA_GIURIDICA", "ENTE", "CONDOMINIO", "ASSOCIAZIONE"}:
        return "ini_pec"
    if tipo == "PROFESSIONISTA":
        return "ini_pec"
    return "inad"


def _infer_recipient_role(soggetto: Any, ruolo: str = "") -> str:
    tipo = _enum_value(getattr(soggetto, "tipo", "")).upper()
    ruolo = ruolo.upper()
    if "DIFENSORE" in ruolo:
        return "difensore"
    if tipo == "PUBBLICA_AMMINISTRAZIONE":
        return "pa"
    if tipo == "PROFESSIONISTA":
        return "professionista"
    if tipo in {"PERSONA_GIURIDICA", "ENTE", "CONDOMINIO", "ASSOCIAZIONE"}:
        return "impresa"
    if "CONTROPARTE" in ruolo or "DEBITORE" in ruolo or "CREDITORE" in ruolo:
        return "controparte"
    return "terzo"


def _recipient_from_subject(soggetto: Any, *, ruolo: str = "", note: str = "", fascicolo: Any = None) -> dict[str, Any]:
    pec = _text(getattr(getattr(soggetto, "recapiti", None), "pec", ""))
    role = _infer_recipient_role(soggetto, ruolo)
    source = _infer_public_register(soggetto, ruolo)
    represented = ""
    if role == "difensore":
        represented = _text(note) or _text(getattr(fascicolo, "controparte", ""))
    return {
        "id": _text(getattr(soggetto, "id", "")),
        "label": _display_text(getattr(soggetto, "nome_completo", "")) or _display_text(getattr(soggetto, "ragione_sociale", "")),
        "nome": _text(getattr(soggetto, "nome_completo", "")) or _text(getattr(soggetto, "ragione_sociale", "")),
        "codiceFiscalePiva": _text(getattr(soggetto, "identificativo", "")),
        "pec": pec,
        "ruolo": role,
        "ruoloPratica": ruolo,
        "fontePecSuggerita": source,
        "parteRappresentata": represented,
        "verificaRichiesta": bool(pec),
    }


def _infer_document_origin(documento: Any) -> str:
    fonte = _text(getattr(documento, "fonte_documento", "")).upper()
    tags = " ".join(_text(item).lower() for item in (getattr(documento, "tags", []) or []))
    if "cancelleria" in fonte.lower() or "comunicazione_cancelleria" in tags:
        return "comunicazione_cancelleria"
    if fonte in {"PORTALE_TELEMATICO", "PST", "PDP", "PAT", "PTT"}:
        return "copia_fascicolo_informatico"
    if _text(getattr(documento, "id_documento_portale", "")) or _text(getattr(documento, "nome_portale", "")):
        return "copia_fascicolo_informatico"
    if "scansione" in tags or "analogico" in tags:
        return "scansione_analogico"
    return "originale_informatico"


def _document_label(documento: Any) -> str:
    name = _first_attr(documento, "nome_originale", "nome_portale", "nome", "percorso")
    description = _first_attr(documento, "tipo_atto_portale", "classificazione_portale", "note")
    return _display_text(" - ".join(part for part in (name, description) if part))


def _portal_acquisition_href(fascicolo: Any, *, portale: str = "pst") -> str:
    params = {
        "id_fasc": _text(getattr(fascicolo, "id", "")),
        "numero": _text(getattr(fascicolo, "numero_rg", "")),
        "anno": _text(getattr(fascicolo, "anno_rg", "")),
        "ufficio": _text(getattr(fascicolo, "tribunale", "")),
        "focus": "documenti",
        "mode": "update_existing",
    }
    query = urlencode({key: value for key, value in params.items() if value})
    return f"/portali/{portale}/acquisizione{f'?{query}' if query else ''}"


def _normalise_document_match(value: Any) -> str:
    raw = _text(value).lower()
    if raw.endswith(".pdf.p7m"):
        raw = raw[:-4]
    elif raw.endswith(".p7m") and ".pdf" not in raw:
        raw = raw[:-4]
    return re.sub(r"[^a-z0-9]+", "", raw)


def _office_pec_messages() -> list[Any]:
    try:
        from web.helpers import get_email_pec

        return list(get_email_pec().tutte())[:500]
    except Exception:
        return []


def _document_notification_required(documento: Any, *, origin: str) -> bool:
    haystack = " ".join(
        _text(value).lower()
        for value in (
            getattr(documento, "tipo_atto_portale", ""),
            getattr(documento, "classificazione_portale", ""),
            getattr(documento, "note", ""),
            getattr(documento, "nome_originale", ""),
            getattr(documento, "nome_portale", ""),
            getattr(documento, "nome", ""),
            " ".join(str(item) for item in (getattr(documento, "tags", []) or [])),
        )
    )
    if bool(getattr(documento, "notifica_richiesta", False)) or bool(getattr(documento, "notificaRichiesta", False)):
        return True
    return origin == "comunicazione_cancelleria" and any(
        token in haystack for token in ("notifica", "notificare", "relata", "termine breve", "sentenza", "ordinanza", "decreto", "provvedimento")
    )


def _document_from_fascicolo(
    documento: Any,
    *,
    office_names: set[str] | None = None,
    office_hashes: set[str] | None = None,
) -> dict[str, Any]:
    origin = normalise_document_origin(_infer_document_origin(documento))
    name = _first_attr(documento, "nome_originale", "nome_portale", "nome", "percorso")
    description = _first_attr(documento, "tipo_atto_portale", "classificazione_portale", "note") or name
    portal_ref = _first_attr(documento, "id_documento_portale", "id_portale", "codice_portale", "riferimento_portale")
    source_name = _text(getattr(documento, "fonte_documento", ""))
    portal_service = _first_attr(documento, "servizio_portale", "nome_portale")
    acquired_from_portal = bool(
        portal_ref
        or source_name.upper() in {"PORTALE_TELEMATICO", "PST", "POLISWEB", "PDP", "PAT", "PTT", "SIGIT"}
        or portal_service.upper() in {"PST", "POLISWEB", "PDP", "PAT", "PTT", "SIGIT"}
    )
    name_key = _normalise_document_match(name)
    sha_key = _text(getattr(documento, "hash_sha256", "")).lower()
    pec_evidence = bool((name_key and name_key in (office_names or set())) or (sha_key and sha_key in (office_hashes or set())))
    notification_required = pec_evidence or _document_notification_required(documento, origin=origin)
    office_document = (
        pec_evidence
        or bool(getattr(documento, "documento_ufficio", False))
        or bool(getattr(documento, "notifica_richiesta", False))
        or origin == "comunicazione_cancelleria"
    )
    return {
        "id": _text(getattr(documento, "id", "")) or name,
        "label": _document_label(documento) or _display_text(name),
        "nomeFile": name,
        "descrizione": _display_text(description),
        "origine": origin,
        "hashSha256": _text(getattr(documento, "hash_sha256", "")),
        "dataDocumento": _text(getattr(documento, "data_documento", "")) or _text(getattr(documento, "data_deposito_portale", "")),
        "fonte": source_name,
        "riferimentoPortale": _text(portal_ref),
        "servizioPortale": portal_service,
        "documentoUfficio": office_document,
        "acquisitoDaPortale": acquired_from_portal,
        "notificaRichiesta": notification_required,
        "dataRilascioPortale": _text(getattr(documento, "data_deposito_portale", "")) or _text(getattr(documento, "data_documento", "")),
        "necessitaAttestazione": origin in {"copia_fascicolo_informatico", "comunicazione_cancelleria", "scansione_analogico"},
    }


def _cliente_option(cliente: Any) -> dict[str, Any]:
    return {
        "id": _text(getattr(cliente, "id", "")),
        "nome": _display_text(getattr(cliente, "nome_completo", "")),
        "codiceFiscalePiva": _text(getattr(cliente, "identificativo_fiscale", "")),
        "pec": _text(getattr(getattr(cliente, "recapiti", None), "pec", "")),
    }


def _fascicolo_option(fascicolo: Any, *, cliente: Any = None, soggetti_repo: Any = None, pec_emails: list[Any] | None = None) -> dict[str, Any]:
    proceeding_present = bool(
        _text(getattr(fascicolo, "tribunale", ""))
        or _text(getattr(fascicolo, "numero_rg", ""))
        or _text(getattr(fascicolo, "anno_rg", ""))
    )
    recipients: list[dict[str, Any]] = []
    if soggetti_repo is not None:
        parti = _safe_call(
            "parti_fascicolo",
            lambda: soggetti_repo.parti_fascicolo(_text(getattr(fascicolo, "id", ""))),
            [],
        )
        for parte, soggetto in parti:
            ruolo = _enum_value(getattr(parte, "ruolo", ""))
            if ruolo == "ASSISTITO":
                continue
            recipient = _recipient_from_subject(
                soggetto,
                ruolo=ruolo,
                note=_text(getattr(parte, "note", "")),
                fascicolo=fascicolo,
            )
            if recipient["nome"] or recipient["pec"]:
                recipients.append(recipient)
    pec_evidence = office_notification_evidence_from_pec(fascicolo, pec_emails or [])
    office_names = {
        _normalise_document_match(item.get("nome"))
        for item in pec_evidence
        if item.get("acquisito")
    }
    office_hashes = {
        _text(item.get("hashSha256")).lower()
        for item in pec_evidence
        if item.get("acquisito") and _text(item.get("hashSha256"))
    }
    documents = [
        _document_from_fascicolo(documento, office_names=office_names, office_hashes=office_hashes)
        for documento in (getattr(fascicolo, "documenti", []) or [])[:60]
    ]
    office_documents = [
        documento
        for documento in documents
        if documento["documentoUfficio"] or documento["notificaRichiesta"]
    ]
    acquired_office_documents = [documento for documento in office_documents if documento["notificaRichiesta"] or documento["documentoUfficio"]]
    pending_releases = [item for item in pec_evidence if not item.get("acquisito")]
    monitor_status = (
        "da_acquisire"
        if pending_releases
        else "acquisito"
        if acquired_office_documents
        else "da_verificare"
        if proceeding_present
        else "non_rilevato"
    )
    client_name = _text(getattr(cliente, "nome_completo", "")) or _text(getattr(fascicolo, "nome_cliente", ""))
    client_cf = _text(getattr(cliente, "identificativo_fiscale", ""))
    label = _display_text(" - ".join(part for part in (_text(getattr(fascicolo, "numero", "")), _text(getattr(fascicolo, "titolo", ""))) if part))
    return {
        "id": _text(getattr(fascicolo, "id", "")),
        "label": label,
        "numero": _text(getattr(fascicolo, "numero", "")),
        "titolo": _display_text(getattr(fascicolo, "titolo", "")),
        "assistitoNome": client_name,
        "assistitoCf": client_cf,
        "clienteId": _text(getattr(fascicolo, "id_cliente", "")),
        "controparte": _text(getattr(fascicolo, "controparte", "")),
        "controparteCf": _text(getattr(fascicolo, "cf_controparte", "")),
        "procedimento": {
            "presente": proceeding_present,
            "ufficio": _text(getattr(fascicolo, "tribunale", "")),
            "sezione": _text(getattr(fascicolo, "sezione", "")),
            "numeroRg": _text(getattr(fascicolo, "numero_rg", "")),
            "annoRg": _text(getattr(fascicolo, "anno_rg", "")),
            "giudice": _text(getattr(fascicolo, "giudice", "")),
            "tipoProcedimento": _text(getattr(fascicolo, "tipo_procedimento", "")),
        },
        "destinatari": recipients[:40],
        "documenti": documents,
        "portaleAcquisizioneHref": _portal_acquisition_href(fascicolo),
        "documentoUfficioMonitor": {
            "stato": monitor_status,
            "rilascioRilevato": bool(office_documents or pending_releases),
            "documentiAcquisiti": len(acquired_office_documents),
            "documentiDaAcquisire": len(pending_releases),
            "documentiDaNotificare": len([documento for documento in office_documents if documento["notificaRichiesta"]]),
            "documentiRilevati": pec_evidence[:20],
            "documentiRilasciati": pending_releases[:20],
            "messaggio": (
                "PEC dell'ufficio ricevuta: scarica dal portale solo il provvedimento indicato e collegalo ai Documenti e atti prima della relata."
                if pending_releases
                else "Documento comunicato dall'ufficio già presente nei Documenti e atti."
                if acquired_office_documents
                else "Nessuna PEC dell'ufficio richiede oggi una relata su provvedimento da notificare."
                if proceeding_present
                else "Nessun procedimento telematico da controllare."
            ),
        },
        "modelloSuggerito": "relata_pec_in_corso_di_causa" if proceeding_present else "relata_pec_base_l53",
    }


def _build_prefill_payload(*, get_clienti: Any = None, get_fascicoli: Any = None, get_soggetti: Any = None) -> dict[str, Any]:
    clienti_repo = _repo_from_getter(get_clienti)
    fascicoli_repo = _repo_from_getter(get_fascicoli)
    soggetti_repo = _repo_from_getter(get_soggetti)
    clienti_by_id = {}
    if clienti_repo is not None:
        clienti_recenti = _safe_call("clienti", lambda: clienti_repo.tutti(), [])[:250]
        clienti_by_id = {
            _text(getattr(cliente, "id", "")): cliente
            for cliente in clienti_recenti
        }
    fascicoli = []
    if fascicoli_repo is not None:
        fascicoli = _safe_call("fascicoli", lambda: fascicoli_repo.tutti(archiviati=False), [])
    pec_emails = _office_pec_messages()
    pratiche = [
        _fascicolo_option(
            fascicolo,
            cliente=clienti_by_id.get(_text(getattr(fascicolo, "id_cliente", ""))),
            soggetti_repo=soggetti_repo,
            pec_emails=pec_emails,
        )
        for fascicolo in fascicoli[:80]
    ]
    destinatari = []
    if soggetti_repo is not None:
        for soggetto in _safe_call("soggetti", lambda: soggetti_repo.tutti(), [])[:250]:
            recipient = _recipient_from_subject(soggetto)
            if recipient["pec"]:
                destinatari.append(recipient)
    return {
        "pratiche": [item for item in pratiche if item["id"]],
        "clienti": [_cliente_option(cliente) for cliente in clienti_by_id.values()],
        "destinatari": destinatari[:120],
        "note": [
            "I dati di pratica, assistito, procedimento e documenti sono proposti dai fascicoli IUSENTRA.",
            "La fonte PEC viene suggerita in base al ruolo e al tipo di soggetto; la verifica sul pubblico elenco resta da confermare.",
            "La data di verifica PEC non viene inventata: va registrata quando l'elenco pubblico viene controllato.",
        ],
    }


def build_react_notifiche_legali_payload(
    *,
    config_studio: Any = None,
    get_clienti: Any = None,
    get_fascicoli: Any = None,
    get_soggetti: Any = None,
    custom_templates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cfg = _config_object(config_studio)
    studio = getattr(cfg, "studio", None)
    pec = getattr(cfg, "pec", None)

    avvocato_nome = _text(getattr(studio, "avvocato", ""))
    studio_nome = _text(getattr(studio, "nome", "")) or "IUSENTRA"
    city = _text(getattr(studio, "city", ""))
    province = _text(getattr(studio, "province", ""))
    return {
        "source": "configurazione_studio",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "contracts": {
            "separateLegalNotification": True,
            "clientCommunicationWithoutRelata": True,
            "depositProofWithOriginalReceipts": True,
            "parametricTemplateEngine": True,
            "officeDocumentPortalAcquisition": True,
            "officeDocumentPecEvidence": True,
            "recipientCaseMatrix": True,
        },
        "templateCatalogVersion": template_catalog_version(),
        "mandatorySubject": LEGAL_NOTIFICATION_SUBJECT,
        "defaults": {
            "studioNome": studio_nome,
            "avvocatoNome": avvocato_nome,
            "avvocatoCf": _text(getattr(studio, "codice_fiscale_avvocato", "")) or _text(getattr(studio, "cf", "")),
            "avvocatoForo": _text(getattr(studio, "ordine_avvocati", "")),
            "studioIndirizzo": _text(getattr(studio, "indirizzo", "")),
            "studioCitta": " ".join(part for part in (city, province) if part),
            "mittentePec": _text(getattr(pec, "indirizzo", "")),
            "fontePecMittente": "ReGIndE",
        },
        "registriPec": [
            {"value": key, "label": label}
            for key, label in PUBLIC_PEC_REGISTERS.items()
        ],
        "matriceNotifica": notification_directive_matrix(),
        "ruoliDestinatario": [
            {"value": role, "label": _recipient_role_label(role)}
            for role in sorted(LEGAL_RECIPIENT_ROLES)
        ],
        "originiDocumento": [
            {"value": key, "label": label, "needsAttestazione": key in {"copia_fascicolo_informatico", "comunicazione_cancelleria", "scansione_analogico"}}
            for key, label in DOCUMENT_ORIGIN_LABELS.items()
        ],
        "modelliRelata": [
            _template_option(template)
            for template in (
                list_notification_templates(kind="relata")
                + [normalise_custom_template(item) for item in (custom_templates or [])]
            )
        ],
        "modelliControllo": [
            _template_option(template)
            for template in list_notification_templates()
            if template.get("kind") in {"control_document", "audit_document", "workflow"}
        ],
        "modelliComunicazioneCliente": [
            _client_template_option(template)
            for template in list_client_communication_templates()
        ],
        "clientCommunicationTemplateVersion": client_communication_templates_version(),
        "precompilazione": _build_prefill_payload(
            get_clienti=get_clienti,
            get_fascicoli=get_fascicoli,
            get_soggetti=get_soggetti,
        ),
        "campiDisponibili": available_template_fields(),
        "automazioneGuidata": legal_notification_automation_payload(),
        "portaleServizi": {
            "defaultPortal": "pst",
            "label": "Portale Servizi Telematici",
            "acquisizioneHref": "/portali/pst/acquisizione?focus=documenti",
            "assistantStartApi": "/api/portali/pst/assistant/start",
            "downloadWatchApi": "/api/portali/pst/assistant/{session_id}/watch-downloads",
            "collectApi": "/api/portali/pst/assistant/{session_id}/collect",
            "localSignerRequired": True,
        },
        "azioni": {
            "notifica": "/api/v1/ui/notifiche-legali/notifica",
            "anteprimaRelata": "/api/v1/ui/notifiche-legali/anteprima-relata",
            "bozzaRelata": "/api/v1/ui/notifiche-legali/bozze-relata",
            "comunicazioneCliente": "/api/v1/ui/notifiche-legali/comunicazione-cliente",
            "provaDeposito": "/api/v1/ui/notifiche-legali/prova-deposito",
            "areaWebPst": "/api/v1/ui/notifiche-legali/area-web-pst",
            "pecCompose": "/email/scrivi?tipo=notifica_l53",
            "clientCompose": "/email-ordinaria/scrivi?tipo=comunicazione_cliente",
            "fascicoli": "/fascicoli",
            "depositoChecklist": "/deposito/checklist",
        },
        "fontiOperative": [
            "Portale Servizi Telematici: notificazioni via PEC degli avvocati, L. 53/1994.",
            "Art. 16-ter D.L. 179/2012: pubblici elenchi rilevanti per notificazioni e comunicazioni.",
            "Specifiche tecniche deposito: ricevute RAC/RdAC in originale digitale e indicizzazione in DatiAtto.xml.",
        ],
    }


def _recipient_role_label(value: str) -> str:
    return {
        "controparte": "Controparte",
        "difensore": "Difensore avversario",
        "impresa": "Impresa",
        "pa": "Pubblica amministrazione",
        "professionista": "Professionista",
        "terzo": "Terzo destinatario",
    }.get(value, value.replace("_", " ").title())


def _template_option(template: dict[str, Any]) -> dict[str, Any]:
    return {
        "value": _text(template.get("id")),
        "code": _text(template.get("code")),
        "label": _text(template.get("label")),
        "description": _text(template.get("description")),
        "requiresProceeding": bool(template.get("requires_proceeding")),
        "privacyDescription": bool(template.get("privacy_description")),
        "custom": bool(template.get("custom")),
        "previewText": template_preview_text(template),
        "fields": [
            {
                "name": _text(field.get("name")),
                "label": _text(field.get("label")),
            }
            for field in (template.get("fields") or [])
            if isinstance(field, dict) and _text(field.get("name"))
        ],
    }


def _client_template_option(template: dict[str, Any]) -> dict[str, Any]:
    body = "\n".join(str(line) for line in (template.get("body_lines") or []))
    return {
        "value": _text(template.get("id")),
        "label": _text(template.get("label")),
        "description": _text(template.get("description")),
        "subjectPreview": _text(template.get("subject")),
        "bodyPreview": body.strip(),
    }
