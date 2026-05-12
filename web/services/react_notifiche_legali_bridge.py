"""Payload React per il workflow notifiche legali e comunicazioni cliente."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pct.notifiche_legali import (
    DOCUMENT_ORIGIN_LABELS,
    LEGAL_NOTIFICATION_SUBJECT,
    LEGAL_RECIPIENT_ROLES,
    PUBLIC_PEC_REGISTERS,
    list_notification_templates,
    normalise_document_origin,
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


def _document_from_fascicolo(documento: Any) -> dict[str, Any]:
    origin = normalise_document_origin(_infer_document_origin(documento))
    name = _first_attr(documento, "nome_originale", "nome_portale", "nome", "percorso")
    description = _first_attr(documento, "tipo_atto_portale", "classificazione_portale", "note") or name
    return {
        "id": _text(getattr(documento, "id", "")) or name,
        "label": _document_label(documento) or _display_text(name),
        "nomeFile": name,
        "descrizione": _display_text(description),
        "origine": origin,
        "hashSha256": _text(getattr(documento, "hash_sha256", "")),
        "dataDocumento": _text(getattr(documento, "data_documento", "")) or _text(getattr(documento, "data_deposito_portale", "")),
        "fonte": _text(getattr(documento, "fonte_documento", "")),
        "necessitaAttestazione": origin in {"copia_fascicolo_informatico", "comunicazione_cancelleria", "scansione_analogico"},
    }


def _cliente_option(cliente: Any) -> dict[str, Any]:
    return {
        "id": _text(getattr(cliente, "id", "")),
        "nome": _display_text(getattr(cliente, "nome_completo", "")),
        "codiceFiscalePiva": _text(getattr(cliente, "identificativo_fiscale", "")),
        "pec": _text(getattr(getattr(cliente, "recapiti", None), "pec", "")),
    }


def _fascicolo_option(fascicolo: Any, *, cliente: Any = None, soggetti_repo: Any = None) -> dict[str, Any]:
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
    documents = [
        _document_from_fascicolo(documento)
        for documento in (getattr(fascicolo, "documenti", []) or [])[:60]
    ]
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
    pratiche = [
        _fascicolo_option(
            fascicolo,
            cliente=clienti_by_id.get(_text(getattr(fascicolo, "id_cliente", ""))),
            soggetti_repo=soggetti_repo,
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
            for template in list_notification_templates(kind="relata")
        ],
        "modelliControllo": [
            _template_option(template)
            for template in list_notification_templates()
            if template.get("kind") in {"control_document", "audit_document", "workflow", "communication"}
        ],
        "precompilazione": _build_prefill_payload(
            get_clienti=get_clienti,
            get_fascicoli=get_fascicoli,
            get_soggetti=get_soggetti,
        ),
        "azioni": {
            "notifica": "/api/v1/ui/notifiche-legali/notifica",
            "comunicazioneCliente": "/api/v1/ui/notifiche-legali/comunicazione-cliente",
            "provaDeposito": "/api/v1/ui/notifiche-legali/prova-deposito",
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
        "fields": [
            {
                "name": _text(field.get("name")),
                "label": _text(field.get("label")),
            }
            for field in (template.get("fields") or [])
            if isinstance(field, dict) and _text(field.get("name"))
        ],
    }
