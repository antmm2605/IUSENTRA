"""Bridge dati per la pagina React Centro Servizi Telematici."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from flask import url_for

from web.services.telematico_control_tower import build_telematico_control_tower

PORTALS = ("pst", "pdp", "pat", "ptt")
ASSISTED_OFFICIAL_PORTALS = {"pdp", "pat", "ptt"}
SERVICE_MAP = {
    "pst": "polisweb_consultazione",
    "pdp": "pdp_penale",
    "pat": "pat_siga",
    "ptt": "ptt_sigit",
}
PORTAL_LABELS = {
    "pst": "PST / PolisWeb",
    "pdp": "PDP Penale",
    "pat": "PAT / SIGA",
    "ptt": "PTT / SIGIT",
}
PORTAL_TITLES = {
    "pst": "PST / PolisWeb",
    "pdp": "PDP Penale",
    "pat": "PAT Amministrativo",
    "ptt": "PTT Tributario",
}
PORTAL_DESCRIPTIONS = {
    "pst": "Consultazione civile e import autorizzato dei fascicoli già scaricati.",
    "pdp": "Percorso penale, esiti, documenti collegati e controllo dell'avvocato.",
    "pat": "Portale avvocato, fascicolo amministrativo e import guidato documenti.",
    "ptt": "Telecontenzioso, SIGIT, fascicoli tributari e ricevute importate.",
}
PORTAL_TONES = {"pst": "primary", "pdp": "danger", "pat": "success", "ptt": "warning"}
PORTAL_HOME_ENDPOINTS = {"pst": "polisWeb_home", "pdp": "pdp_home", "pat": "pat_home", "ptt": "sigit_home"}
PORTAL_HOME_FALLBACKS = {"pst": "/polisWeb", "pdp": "/pdp", "pat": "/pat", "ptt": "/sigit"}
PORTAL_SURFACE_IDS = {"pst": "polisweb", "pdp": "pdp", "pat": "pat", "ptt": "ptt"}
SURFACE_CANONICAL_HREFS = {
    "polisweb": "/polisWeb",
    "pdp": "/pdp",
    "pat": "/pat",
    "ptt": "/sigit",
    "tribunali": "/tribunali",
    "checklist": "/deposito/checklist",
    "firma": "/guida/firma-digitale",
    "telematico": "/telematico",
}
PORTAL_IMPORT_FALLBACKS = {
    "pst": "/portali/pst/acquisizione",
    "pdp": "/portali/pdp/acquisizione",
    "pat": "/portali/pat/acquisizione",
    "ptt": "/portali/ptt/acquisizione",
}
PORTAL_IMPORT_LABELS = {
    "pst": "Importa pratica da PST",
    "pdp": "Importa pratica da PDP",
    "pat": "Importa pratica da PAT",
    "ptt": "Importa pratica da PTT",
}
PORTAL_IMPORT_DESCRIPTIONS = {
    "pst": (
        "Avvia il percorso operativo per acquisire nel fascicolo interno i dati e i file "
        "ottenuti dal Portale Servizi Telematici o da PolisWeb, senza accessi non autorizzati "
        "e senza credenziali salvate fuori dallo studio."
    ),
    "pdp": "Avvia il percorso operativo per acquisire nel fascicolo penale file, cataloghi ed esiti ottenuti dal PDP.",
    "pat": "Avvia il percorso operativo per acquisire documenti, provvedimenti ed esiti dal Portale Avvocato / SIGA.",
    "ptt": "Avvia il percorso operativo per acquisire fascicoli, ricevute e provvedimenti tributari da SIGIT.",
}
PORTAL_OFFICIAL_URLS = {
    "pst": "https://pst.giustizia.it/PST/it/services.page",
    "pdp": "https://servizipst.giustizia.it/PST/authentication/it/pst_ar.wp",
    "pat": "https://www.giustizia-amministrativa.it/portale-avvocato",
    "ptt": "https://sigit.giustiziatributaria.gov.it/Sigit/index.do",
}
SURFACE_ALIASES = {
    "polisweb": "polisweb",
    "polisweb-pst": "polisweb",
    "pst": "polisweb",
    "sigp": "polisweb",
    "pdp": "pdp",
    "pat": "pat",
    "ptt": "ptt",
    "sigit": "ptt",
    "tributario": "ptt",
    "tribunali": "tribunali",
    "tribunali-pec": "tribunali",
    "checklist": "checklist",
    "deposito-checklist": "checklist",
    "firma": "firma",
    "firma-digitale": "firma",
}
SURFACE_SPECS = {
    "polisweb": {
        "id": "polisweb",
        "portal": "pst",
        "title": "PolisWeb / PST",
        "eyebrow": "Consultazione civile",
        "subtitle": (
            "Ricerca fascicoli, acquisizione guidata e import autorizzato dal Portale "
            "Servizi Telematici, senza accessi non autorizzati e senza credenziali salvate fuori dallo studio."
        ),
        "tone": "primary",
    },
    "pdp": {
        "id": "pdp",
        "portal": "pdp",
        "title": "PDP Penale",
        "eyebrow": "Deposito e fascicolo penale",
        "subtitle": (
            "Percorso penale con accesso guidato, import fascicolo, ricevute, "
            "attivita operative e collegamento alla cabina fascicolo."
        ),
        "tone": "danger",
    },
    "pat": {
        "id": "pat",
        "portal": "pat",
        "title": "PAT Amministrativo",
        "eyebrow": "Portale Avvocato / SIGA",
        "subtitle": (
            "Presidio del fascicolo amministrativo, import dei file gia scaricati e "
            "controllo di ricevute, provvedimenti ed esiti."
        ),
        "tone": "success",
    },
    "ptt": {
        "id": "ptt",
        "portal": "ptt",
        "title": "PTT Tributario",
        "eyebrow": "SIGIT e Telecontenzioso",
        "subtitle": (
            "Preparazione del fascicolo tributario interno, acquisizione guidata da "
            "SIGIT e presidio di ricevute, NIR, provvedimenti e scadenze."
        ),
        "tone": "warning",
    },
    "checklist": {
        "id": "checklist",
        "portal": "",
        "title": "Controlli Atti",
        "eyebrow": "Controlli prima dell'invio",
        "subtitle": (
            "Checklist operativa token-based per PCT, PDP, PAT e PTT con stato locale "
            "salvato nel browser e collegamenti alle superfici operative."
        ),
        "tone": "purple",
    },
    "firma": {
        "id": "firma",
        "portal": "",
        "title": "Guida firma digitale",
        "eyebrow": "Local Signer, token e certificati",
        "subtitle": (
            "Percorso guidato per usare Local Signer, token USB, P12/PEM e pacchetti "
            "installabili senza confondere token locale e ambiente dello studio."
        ),
        "tone": "info",
    },
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(label: str, func: Callable[[], Any], fallback: Any, logger: Any | None = None) -> Any:
    try:
        return func()
    except Exception as exc:  # pragma: no cover - guardrail operativo
        if logger:
            logger.exception("Bridge React telematico: sorgente non disponibile (%s): %s", label, exc)
        return fallback


def _safe_url(endpoint: str, fallback: str, **values: Any) -> str:
    try:
        return url_for(endpoint, **values)
    except Exception:
        return fallback


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _text(value: Any, fallback: str = "") -> str:
    return str(value or fallback).strip()


def _display_text(value: Any, fallback: str = "") -> str:
    text = _text(value, fallback)
    text = re.sub(r"\bdemo\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip(" -")
    return text or fallback


def _portal_from_service(value: Any) -> str:
    raw = _text(value).lower()
    if raw in PORTALS:
        return raw
    for portal, code in SERVICE_MAP.items():
        if raw == code or portal in raw:
            return portal
    if "polis" in raw:
        return "pst"
    if "penale" in raw:
        return "pdp"
    if "siga" in raw or "amministr" in raw:
        return "pat"
    if "sigit" in raw or "tribut" in raw:
        return "ptt"
    return "altro"


def _tone_for_status(status: str, portal: str = "") -> str:
    raw = _text(status).lower()
    if any(marker in raw for marker in ("rifiut", "errore", "blocked", "blocc")):
        return "danger"
    if any(marker in raw for marker in ("warning", "manual", "incomplet", "attesa", "pending")):
        return "warning"
    if any(marker in raw for marker in ("import", "sincron", "accepted", "complet")):
        return "success"
    return PORTAL_TONES.get(portal, "neutral")


def _channel_badges(payload: dict[str, Any]) -> list[str]:
    badges: list[str] = []
    if payload.get("pkcs11_mode"):
        badges.append("Local Signer")
    if payload.get("browser_channel_required"):
        badges.append("Accesso guidato")
    if payload.get("demo_mode"):
        badges.append("Assistita")
    if not badges:
        badges.append("Operativo")
    return badges


def _surface_href(surface_id: str, fragment: str = "") -> str:
    clean_id = _surface_id(surface_id)
    return f"{SURFACE_CANONICAL_HREFS.get(clean_id, f'/{clean_id}')}{fragment}"


def _portal_surface_href(portal: str, fragment: str = "") -> str:
    surface_id = PORTAL_SURFACE_IDS.get(portal, portal)
    return _surface_href(surface_id, fragment)


def _surface_id(value: str) -> str:
    raw = _text(value).strip().lower().replace("_", "-").replace("/", "-")
    return SURFACE_ALIASES.get(raw, raw)


def _build_channel(portal: str, stats: dict[str, Any], access_payload: dict[str, Any]) -> dict[str, Any]:
    spec = dict(access_payload.get("spec") or {})
    service_stats = dict((stats.get("per_service") or {}).get(SERVICE_MAP[portal]) or {})
    home_href = _portal_surface_href(portal)
    import_href = PORTAL_IMPORT_FALLBACKS.get(portal, _portal_surface_href(portal, "#acquisizione-portale"))
    status_text = _text(access_payload.get("status_text"), "Da configurare")
    attention_needed = _int(service_stats.get("attention_needed"))
    tone = "warning" if attention_needed else PORTAL_TONES[portal]
    if access_payload.get("demo_mode"):
        tone = "warning"
    return {
        "id": portal,
        "label": spec.get("label") or PORTAL_LABELS[portal],
        "title": spec.get("title") or PORTAL_TITLES[portal],
        "description": spec.get("subtitle") or PORTAL_DESCRIPTIONS[portal],
        "tone": tone,
        "statusText": status_text,
        "environmentLabel": access_payload.get("environment_label") or "",
        "cases": _int(service_stats.get("totale")),
        "importCompleted": _int(service_stats.get("import_completed")),
        "attentionNeeded": attention_needed,
        "lastSyncAt": access_payload.get("last_sync_at") or "",
        "homeHref": home_href,
        "importHref": import_href,
        "presideHref": f"/telematico?focus={portal}",
        "browserChannelRequired": bool(access_payload.get("browser_channel_required")),
        "demoMode": bool(access_payload.get("demo_mode")),
        "pkcs11Mode": bool(access_payload.get("pkcs11_mode")),
        "badges": _channel_badges(access_payload),
        "quickActions": [
            {"label": PORTAL_IMPORT_LABELS.get(portal, "Importa da portale"), "href": import_href, "tone": "primary"},
            {"label": "Apri pagina", "href": home_href, "tone": PORTAL_TONES[portal]},
            {"label": "Checklist", "href": f"{home_href}#checklist-operativa", "tone": "warning"},
        ],
    }


def _practice_href(row: dict[str, Any], fascicoli_index: dict[str, Any]) -> str:
    practice_id = _text(row.get("practice_id") or row.get("id_fascicolo"))
    if practice_id and practice_id in fascicoli_index:
        return _safe_url("dettaglio_fascicolo", f"/fascicoli/{practice_id}", id_fasc=practice_id)
    return "/telematico"


def _case_row(row: dict[str, Any], index: int, fascicoli_index: dict[str, Any]) -> dict[str, Any]:
    portal = _portal_from_service(row.get("service_code") or row.get("portale"))
    practice_id = _text(row.get("practice_id") or row.get("id_fascicolo"))
    fasc = fascicoli_index.get(practice_id)
    title = (
        _display_text(row.get("title"))
        or _display_text(row.get("practice_title"))
        or _display_text(getattr(fasc, "titolo", ""))
        or _display_text(row.get("registry_number"))
        or "Pratica telematica"
    )
    rg = _display_text(row.get("registry_number") or row.get("numero_rg") or getattr(fasc, "rg_completo", "") or getattr(fasc, "numero", ""))
    court = _display_text(row.get("office_name") or row.get("ufficio") or getattr(fasc, "tribunale", ""))
    status = _display_text(row.get("internal_status") or row.get("status") or row.get("status_text"), "Da verificare")
    return {
        "id": _text(row.get("id") or practice_id, f"case-{index}"),
        "portal": portal,
        "portalLabel": PORTAL_LABELS.get(portal, "Telematico"),
        "title": title,
        "subtitle": " · ".join(part for part in [court, rg] if part) or "Fascicolo telematico importato",
        "subject": _display_text(row.get("subject") or row.get("oggetto") or getattr(fasc, "oggetto", "")),
        "statusText": status.replace("_", " ").title(),
        "documentsCount": _int(row.get("documents_count") or row.get("documents") or row.get("document_count")),
        "openTasks": _int(row.get("open_tasks") or row.get("task_aperti") or row.get("tasks")),
        "syncedAt": _text(row.get("updated_at") or row.get("last_sync_at") or row.get("synced_at")),
        "href": _practice_href(row, fascicoli_index),
        "tone": _tone_for_status(status, portal),
        "badges": [PORTAL_LABELS.get(portal, "TEL")],
    }


def _event_row(row: dict[str, Any], index: int, fascicoli_index: dict[str, Any]) -> dict[str, Any]:
    portal = _portal_from_service(row.get("service_code") or row.get("portale"))
    title = _text(row.get("title") or row.get("event_type") or row.get("tipo"), "Attività telematica")
    status = _text(row.get("status") or row.get("outcome") or row.get("badge"))
    return {
        "id": _text(row.get("id"), f"event-{index}"),
        "portal": portal,
        "title": title,
        "subtitle": _text(row.get("description") or row.get("message") or row.get("practice_title")),
        "timestamp": _text(row.get("created_at") or row.get("timestamp") or row.get("time")),
        "href": _practice_href(row, fascicoli_index),
        "tone": _tone_for_status(status, portal),
        "badge": status,
    }


def _control_item(value: Any, index: int, badge: str, fallback_tone: str, fascicoli_index: dict[str, Any]) -> dict[str, Any]:
    row = dict(value or {}) if isinstance(value, dict) else {}
    portal = _portal_from_service(row.get("service_code") or row.get("portale") or row.get("portal"))
    status = _text(row.get("status") or row.get("badge"), badge)
    return {
        "id": _text(row.get("id") or row.get("practice_id"), f"{badge}-{index}"),
        "portal": portal,
        "title": _text(row.get("title") or row.get("practice_title") or row.get("subject"), "Elemento telematico da presidiare"),
        "subtitle": _text(row.get("subtitle") or row.get("description") or row.get("office_name") or row.get("message")),
        "href": _practice_href(row, fascicoli_index),
        "tone": _tone_for_status(status, portal) if status else fallback_tone,
        "badge": status,
    }


def _control_tower_payload(control_tower: dict[str, Any], fascicoli_index: dict[str, Any]) -> dict[str, Any]:
    return {
        "pendingOutcomes": [
            _control_item(item, index, "esito", "warning", fascicoli_index)
            for index, item in enumerate(list(control_tower.get("pending_outcomes") or []))
        ],
        "incompleteImports": [
            _control_item(item, index, "import", "warning", fascicoli_index)
            for index, item in enumerate(list(control_tower.get("incomplete_imports") or []))
        ],
        "warnings": [
            _control_item(item, index, "warning", "warning", fascicoli_index)
            for index, item in enumerate(list(control_tower.get("warning_cases") or []))
        ],
        "blockedCases": [
            _control_item(item, index, "bloccato", "danger", fascicoli_index)
            for index, item in enumerate(list(control_tower.get("blocked_cases") or []))
        ],
        "predeposito": [
            _control_item(item, index, "predeposito", "primary", fascicoli_index)
            for index, item in enumerate(list(control_tower.get("predeposito") or []))
        ],
    }


def _lex_suggestions(summary: dict[str, int], channels: list[dict[str, Any]]) -> list[str]:
    suggestions: list[str] = []
    if summary.get("blocked"):
        suggestions.append("Prima del deposito risolvi i fascicoli bloccati nei controlli predeposito.")
    if summary.get("pendingOutcomes"):
        suggestions.append("Controlla gli esiti in attesa e collega ricevute o comunicazioni al fascicolo corretto.")
    if summary.get("incompleteImports"):
        suggestions.append("Completa gli import parziali prima di chiudere il presidio telematico giornaliero.")
    if any(channel.get("demoMode") or channel.get("browserChannelRequired") for channel in channels):
        suggestions.append("Per i canali con browser guidato apri il portale ufficiale e importa solo dati o file autorizzati.")
    return suggestions[:4]


def _surface_action(
    action_id: str,
    label: str,
    href: str,
    *,
    tone: str = "primary",
    method: str = "GET",
    external: bool = False,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "href": href,
        "tone": tone,
        "method": method,
        "external": external,
    }


def _surface_card(
    card_id: str,
    title: str,
    body: str,
    *,
    tone: str = "primary",
    icon: str = "workflow",
    actions: list[dict[str, Any]] | None = None,
    metrics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": card_id,
        "title": title,
        "body": body,
        "tone": tone,
        "icon": icon,
        "actions": actions or [],
        "metrics": metrics or [],
    }


def _portal_operation_cards(surface_id: str, portal: str, channel: dict[str, Any] | None) -> list[dict[str, Any]]:
    channel = dict(channel or {})
    tone = PORTAL_TONES.get(portal, "primary")
    home_href = channel.get("homeHref") or _portal_surface_href(portal)
    import_href = channel.get("importHref") or PORTAL_IMPORT_FALLBACKS.get(portal, "/portali/pst/acquisizione")
    official_href = PORTAL_OFFICIAL_URLS.get(portal, "")
    import_label = PORTAL_IMPORT_LABELS.get(portal, "Importa pratica da portale")
    import_body = PORTAL_IMPORT_DESCRIPTIONS.get(
        portal,
        "Avvia il percorso operativo per acquisire nel fascicolo interno dati, file o cataloghi ottenuti da canali autorizzati.",
    )
    assisted_action = _surface_action(
        "assisted-session",
        "Sessione assistita IUSENTRA",
        f"{import_href}#wizard-acquisizione",
        tone=tone,
    )
    official_action = (
        assisted_action
        if portal in ASSISTED_OFFICIAL_PORTALS
        else _surface_action("official", "Portale ufficiale", official_href, tone=tone, external=True)
    )
    return [
        _surface_card(
            "importa-pratica",
            import_label,
            import_body,
            tone="primary",
            icon="download",
            actions=[
                _surface_action("import", import_label, import_href, tone="primary"),
                _surface_action("fascicoli", "Fascicoli collegati", "/fascicoli", tone="secondary"),
            ],
        ),
        _surface_card(
            "workspace",
            f"Cabina {PORTAL_LABELS.get(portal, 'del canale')}",
            "Controlla stato canale, casi collegati, blocchi e prossima azione senza uscire dalla superficie telematica.",
            tone=tone,
            icon="monitor",
            actions=[
                _surface_action("open-react", "Apri pagina", _surface_href(surface_id), tone=tone),
                _surface_action("open-center", "Centro telematico", "/telematico", tone="secondary"),
            ],
            metrics=[
                {"label": "Pratiche", "value": channel.get("cases", 0)},
                {"label": "Import completi", "value": channel.get("importCompleted", 0)},
                {"label": "Da presidiare", "value": channel.get("attentionNeeded", 0)},
            ],
        ),
        _surface_card(
            "presidio-react",
            "Presidio operativo",
            (
                "Lavora su checklist, stato canale e sessione assistita IUSENTRA senza uscire dalla pagina."
                if portal in ASSISTED_OFFICIAL_PORTALS
                else "Lavora su checklist, stato canale e portale ufficiale senza uscire dalla pagina."
            ),
            tone="neutral",
            icon="external",
            actions=[
                _surface_action("surface", "Apri pagina", home_href, tone="neutral"),
                official_action,
            ],
        ),
        _surface_card(
            "controlli",
            "Controlli e qualita",
            "Verifica connessioni, Local Signer, PEC, esiti in attesa e blocchi predeposito.",
            tone="warning",
            icon="shield",
            actions=[
                _surface_action("status", "Stato connessioni", "/api/telematico/connection-status", tone="warning"),
                _surface_action("checklist", "Checklist deposito", "/deposito/checklist", tone="purple"),
            ],
        ),
    ]


def _portal_checklist_groups(portal: str) -> list[dict[str, Any]]:
    common = [
        {
            "id": "identita",
            "title": "Identita e accesso",
            "items": [
                {"id": "certificato", "label": "Certificato o Local Signer verificato", "description": "Il controllo reale del token USB avviene sul PC locale, non in cloud.", "critical": True},
                {"id": "ufficio", "label": "Ufficio e registro coerenti", "description": "Codice ufficio, RG, anno e rito devono corrispondere al fascicolo reale.", "critical": True},
                {"id": "parti", "label": "Parti e anagrafiche riallineate", "description": "Nessun soggetto essenziale deve restare incompleto prima dell'import o deposito.", "critical": False},
            ],
        },
        {
            "id": "documenti",
            "title": "Documenti e ricevute",
            "items": [
                {"id": "catalogo", "label": "Catalogo documenti acquisito", "description": "Le buste devono mantenere id deposito, tipo atto, data e mittente.", "critical": True},
                {"id": "ricevute", "label": "Ricevute ed esiti collegati", "description": "Accettazione, consegna, controlli ed esiti vanno archiviati nel fascicolo.", "critical": False},
                {"id": "naming", "label": "Nomi file leggibili", "description": "File e allegati devono restare riconoscibili nella cabina fascicolo.", "critical": False},
            ],
        },
    ]
    if portal == "ptt":
        common.append(
            {
                "id": "ptt",
                "title": "Passaggi tributari",
                "items": [
                    {"id": "nir", "label": "NIR e allegati controllati", "description": "La nota iscrizione a ruolo e i file scaricati da SIGIT devono essere importati in modo tracciabile.", "critical": True},
                    {"id": "telecontenzioso", "label": "Telecontenzioso presidiato", "description": "Consultazione e download restano sul portale ufficiale, con import successivo nel gestionale.", "critical": False},
                ],
            }
        )
    if portal == "pdp":
        common.append(
            {
                "id": "pdp",
                "title": "Passaggi penali",
                "items": [
                    {"id": "registro", "label": "Registro penale corretto", "description": "RGNR, GIP/GUP o dibattimento devono essere selezionati senza ambiguita.", "critical": True},
                    {"id": "review", "label": "Manual review completata", "description": "Ogni richiesta di accesso o deposito deve restare validata dall'avvocato.", "critical": True},
                ],
            }
        )
    return common


def _deposit_checklist_groups() -> list[dict[str, Any]]:
    return [
        {
            "id": "kit-base",
            "title": "Kit base",
            "items": [
                {"id": "firma", "label": "Firma digitale attiva", "description": "Certificato valido, PIN disponibile e Local Signer o software di firma funzionante.", "critical": True},
                {"id": "pec", "label": "PEC operativa", "description": "Casella capiente e canale di invio coerente con la configurazione dello studio o Local Signer.", "critical": True},
                {"id": "pdf", "label": "PDF e allegati verificati", "description": "Documenti leggibili, non corrotti e collegati al fascicolo corretto.", "critical": True},
                {"id": "ricevute", "label": "Ricevute da controllare dopo invio", "description": "Accettazione, consegna, controlli automatici ed esito ufficio.", "critical": False},
            ],
        },
        {
            "id": "pct",
            "title": "PCT civile",
            "items": [
                {"id": "atto-principale", "label": "Atto principale selezionato", "description": "L'atto principale deve essere quello effettivo da inserire in busta.", "critical": True},
                {"id": "ufficio-pct", "label": "Ufficio abilitato verificato", "description": "Controlla codice ufficio e PEC destinataria prima dell'invio.", "critical": True},
                {"id": "busta", "label": "Busta e allegati coerenti", "description": "Informazioni, registro, RG, anno, oggetto e allegati devono combaciare.", "critical": True},
            ],
        },
        {
            "id": "pdp-pat-ptt",
            "title": "PDP, PAT e PTT",
            "items": [
                {"id": "canale", "label": "Canale corretto per il rito", "description": "Penale su PDP, amministrativo su PAT/SIGA, tributario su PTT/SIGIT.", "critical": True},
                {"id": "portale", "label": "Sessione o canale ufficiale presidiato", "description": "La consultazione avviene dalla procedura IUSENTRA con Local Signer quando richiesto.", "critical": True},
                {"id": "import", "label": "File importati nel fascicolo", "description": "Ricevute, provvedimenti ed esiti vanno collegati al fascicolo interno.", "critical": False},
            ],
        },
    ]


def _firma_checklist_groups() -> list[dict[str, Any]]:
    return [
        {
            "id": "local-signer",
            "title": "Local Signer",
            "items": [
                {"id": "installato", "label": "Local Signer installato sul PC", "description": "Il servizio deve rispondere su http://127.0.0.1:27272 dal browser dell'avvocato.", "critical": True},
                {"id": "origine", "label": "Origine HTTPS autorizzata", "description": "L'origine app.iusentra.it deve poter dialogare con il loopback locale.", "critical": True},
                {"id": "pacchetto", "label": "Pacchetto aggiornato scaricato", "description": "Su Windows il pacchetto utente resta un eseguibile .exe versionato.", "critical": False},
            ],
        },
        {
            "id": "certificato",
            "title": "Certificato e token",
            "items": [
                {"id": "token", "label": "Token USB controllato localmente", "description": "Se il controllo avviene dal PC, eventuali avvisi del cloud non bloccano la firma locale.", "critical": True},
                {"id": "p12", "label": "P12/PEM solo dove previsto", "description": "Usare file certificato gestiti dallo studio solo per installazioni che lo prevedono.", "critical": False},
                {"id": "scadenza", "label": "Scadenza certificato presidiata", "description": "Il certificato va verificato prima di firma e deposito.", "critical": True},
            ],
        },
    ]


def _surface_checklist(surface_id: str, portal: str = "") -> list[dict[str, Any]]:
    if surface_id == "checklist":
        return _deposit_checklist_groups()
    if surface_id == "firma":
        return _firma_checklist_groups()
    if portal:
        return _portal_checklist_groups(portal)
    return []


def _filter_by_portal(items: list[dict[str, Any]], portal: str) -> list[dict[str, Any]]:
    if not portal:
        return items
    return [item for item in items if item.get("portal") == portal]


def _surface_controls(base_control: dict[str, Any], portal: str) -> dict[str, Any]:
    return {
        "pendingOutcomes": _filter_by_portal(list(base_control.get("pendingOutcomes") or []), portal),
        "incompleteImports": _filter_by_portal(list(base_control.get("incompleteImports") or []), portal),
        "warnings": _filter_by_portal(list(base_control.get("warnings") or []), portal),
        "blockedCases": _filter_by_portal(list(base_control.get("blockedCases") or []), portal),
        "predeposito": _filter_by_portal(list(base_control.get("predeposito") or []), portal),
    }


def _surface_links(surface_id: str, portal: str = "") -> list[dict[str, Any]]:
    links = [
        {"label": "Centro Servizi Telematici", "href": "/telematico", "kind": "react"},
        {"label": "Checklist deposito", "href": "/deposito/checklist", "kind": "react"},
        {"label": "Guida firma digitale", "href": "/guida/firma-digitale", "kind": "react"},
        {"label": "Tribunali / PEC", "href": "/tribunali", "kind": "react"},
    ]
    if portal:
        links.insert(1, {"label": PORTAL_IMPORT_LABELS[portal], "href": PORTAL_IMPORT_FALLBACKS[portal], "kind": "operativo"})
        if portal in ASSISTED_OFFICIAL_PORTALS:
            links.append({"label": "Sessione assistita IUSENTRA", "href": f"{PORTAL_IMPORT_FALLBACKS[portal]}#wizard-acquisizione", "kind": "operativo"})
        else:
            links.append({"label": "Portale ufficiale", "href": PORTAL_OFFICIAL_URLS[portal], "kind": "esterno"})
    if surface_id == "firma":
        links.extend(
            [
                {"label": "Installer Windows EXE", "href": "/polisWeb/local-signer/setup/windows", "kind": "download"},
                {"label": "Installer macOS", "href": "/polisWeb/local-signer/setup/macos", "kind": "download"},
                {"label": "Installer Linux", "href": "/polisWeb/local-signer/setup/linux", "kind": "download"},
                {"label": "Impostazioni firma", "href": "/impostazioni?tab=firma", "kind": "operativo"},
            ]
        )
    return links


def build_react_telematico_surface_payload(
    *,
    surface: str,
    get_telematico: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    build_access_status_payload: Callable[[str], dict[str, Any]],
    logger: Any | None = None,
) -> dict[str, Any]:
    """Payload per le superfici React di secondo livello dei servizi telematici."""

    surface_id = _surface_id(surface)
    if surface_id not in SURFACE_SPECS:
        surface_id = "polisweb"
    spec = dict(SURFACE_SPECS[surface_id])
    portal = str(spec.get("portal") or "")
    base = build_react_telematico_payload(
        get_telematico=get_telematico,
        get_fascicoli=get_fascicoli,
        build_access_status_payload=build_access_status_payload,
        logger=logger,
    )
    channel = next((item for item in base["channels"] if item.get("id") == portal), None) if portal else None
    controls = _surface_controls(dict(base.get("controlTower") or {}), portal)
    recent_cases = _filter_by_portal(list(base.get("recentCases") or []), portal) if portal else list(base.get("recentCases") or [])
    recent_events = _filter_by_portal(list(base.get("recentEvents") or []), portal) if portal else list(base.get("recentEvents") or [])
    attention = sum(len(list(controls.get(key) or [])) for key in controls)
    operation_cards = (
        _portal_operation_cards(surface_id, portal, channel)
        if portal
        else [
            _surface_card(
                "centro",
                "Centro Servizi Telematici",
                "Torna alla cabina che aggrega PST, PDP, PAT, PTT, esiti e import.",
                tone="primary",
                icon="monitor",
                actions=[_surface_action("centro", "Apri centro", "/telematico", tone="primary")],
            ),
            _surface_card(
                "fascicoli",
                "Fascicoli collegati",
                "Usa i fascicoli collegati per preparare atti, documenti, scadenze e depositi.",
                tone="success",
                icon="folder",
                actions=[_surface_action("fascicoli", "Apri fascicoli", "/fascicoli", tone="success")],
            ),
        ]
    )
    if surface_id == "checklist":
        operation_cards.extend(
            [
                _surface_card(
                    "firma",
                    "Firma digitale",
                    "Controlla Local Signer, token e certificato prima di proseguire.",
                    tone="info",
                    icon="shield",
                    actions=[_surface_action("firma", "Apri guida", "/guida/firma-digitale", tone="info")],
                ),
                _surface_card(
                    "pec",
                    "PEC ed esiti",
                    "Leggi ricevute e comunicazioni collegate al deposito.",
                    tone="warning",
                    icon="mail",
                    actions=[_surface_action("pec", "Apri PEC", "/email/", tone="warning")],
                ),
            ]
        )
    if surface_id == "firma":
        operation_cards = [
            _surface_card(
                "windows",
                "Pacchetto Windows",
                "Scarica l'installer EXE versionato per avviare Local Signer sul PC dell'avvocato.",
                tone="primary",
                icon="download",
                actions=[_surface_action("windows", "Scarica installer Windows", "/polisWeb/local-signer/setup/windows", tone="primary")],
            ),
            _surface_card(
                "monitor",
                "Verifica Local Signer",
                "Il browser controlla il servizio locale sul PC in uso, senza interrogare il token dal cloud.",
                tone="success",
                icon="shield",
                actions=[_surface_action("settings", "Impostazioni firma", "/impostazioni?tab=firma", tone="success")],
            ),
            _surface_card(
                "pacchetti",
                "Pacchetti macOS e Linux",
                "Restano disponibili per postazioni non Windows, con installatori eseguibili dedicati.",
                tone="neutral",
                icon="download",
                actions=[
                    _surface_action("macos", "macOS", "/polisWeb/local-signer/setup/macos", tone="neutral"),
                    _surface_action("linux", "Linux", "/polisWeb/local-signer/setup/linux", tone="neutral"),
                ],
            ),
        ]
    summary = {
        "total": int(channel.get("cases") or 0) if channel else int((base.get("summary") or {}).get("total") or 0),
        "imports": int(channel.get("importCompleted") or 0) if channel else int((base.get("summary") or {}).get("incompleteImports") or 0),
        "attention": int(channel.get("attentionNeeded") or 0) + attention if channel else attention,
        "blocked": len(list(controls.get("blockedCases") or [])),
        "warnings": len(list(controls.get("warnings") or [])),
    }
    offices, office_summary = _portal_office_rows(portal) if portal else ([], {})
    local_signer_release = _local_signer_release_payload()
    return {
        "source": "repository_reali",
        "generatedAt": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "read_only": True,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "surface": {
            **spec,
            "portal": portal,
            "appHref": _surface_href(surface_id),
            "legacyHref": PORTAL_HOME_FALLBACKS.get(portal, ""),
            "officialHref": PORTAL_OFFICIAL_URLS.get(portal, ""),
        },
        "summary": summary,
        "channel": channel,
        "operationCards": operation_cards,
        "checklistGroups": _surface_checklist(surface_id, portal),
        "controlTower": controls,
        "recentCases": recent_cases,
        "recentEvents": recent_events,
        "links": _surface_links(surface_id, portal),
        "notices": list(base.get("notices") or []),
        "lexSuggestions": list(base.get("lexSuggestions") or []),
        "offices": offices,
        "officeSummary": office_summary,
        "localSigner": local_signer_release,
    }


def _local_signer_release_payload() -> dict[str, str]:
    try:
        from web.services.local_signer_release import latest_local_signer_release

        release = latest_local_signer_release()
    except Exception:
        release = {}
    return {
        "browserUrl": _text(release.get("browser_url") or "http://127.0.0.1:27272"),
        "latestVersion": _text(release.get("version")),
        "downloadPage": _text(release.get("download_page") or "/impostazioni?tab=firma"),
        "windowsUrl": "/polisWeb/local-signer/setup/windows",
        "macosUrl": "/polisWeb/local-signer/setup/macos",
        "linuxUrl": "/polisWeb/local-signer/setup/linux",
    }


def _office_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _office_row_payload(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": _office_text(row, "codice", "codice_ministero") or f"ufficio-{index}",
        "codice": _office_text(row, "codice"),
        "codiceMinistero": _office_text(row, "codice_ministero"),
        "nome": _office_text(row, "nome", "descrizione_ministero", "denominazione"),
        "descrizione": _office_text(row, "descrizione_ministero", "denominazione"),
        "tipo": _office_text(row, "tipo", "tipo_ministero_descrizione"),
        "distretto": _office_text(row, "distretto", "distretto_ministero"),
        "pec": _office_text(row, "pec", "email_pec", "pec_ministero"),
        "regione": _office_text(row, "regione_ministero", "regione"),
        "provincia": _office_text(row, "provincia_ministero", "provincia"),
        "comune": _office_text(row, "comune_ministero", "comune"),
        "servizioPst": _office_text(row, "servizio_pst_predefinito"),
        "servizi": list(row.get("servizi_ministero") or []),
    }


def _portal_office_rows(portal: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Uffici reali disponibili nel wizard di acquisizione del portale."""

    from collections import Counter

    from pct.uffici_giudiziari import get_gestore

    portal = (portal or "").strip().lower()
    gestore = get_gestore()
    uffici = list(gestore.carica())
    stato = gestore.stato()
    tipi_per_portale = {
        "pst": {"TRIBUNALE", "CORTE_APPELLO", "CORTE_CASSAZIONE", "TM", "GDP"},
        "pdp": {"PROCURA", "PROCURA_GENERALE", "TRIBUNALE", "SORVEGLIANZA", "CORTE_ASSISE"},
        "pat": {"TAR", "CDS", "CGARS"},
        "ptt": {"CGT", "CPT"},
    }
    ammessi = tipi_per_portale.get(portal, set())

    def _supports_portal(row: dict[str, Any]) -> bool:
        tipo = str(row.get("tipo") or "").strip().upper()
        if not ammessi:
            return True
        if tipo not in ammessi:
            return False
        if portal == "pst":
            servizi = {str(servizio or "").upper() for servizio in (row.get("servizi_ministero") or [])}
            return bool(row.get("codice_ministero") and any(servizio.startswith("JPW_") for servizio in servizi))
        return True

    filtrati = [row for row in uffici if _supports_portal(row)]
    per_tipo = Counter(str(row.get("tipo") or "ALTRO") for row in filtrati)
    offices = [_office_row_payload(row, index) for index, row in enumerate(filtrati)]
    offices.sort(key=lambda item: (item.get("nome", "").lower(), item.get("distretto", "").lower()))
    return offices, {
        "source": stato.get("sorgente", "bundle"),
        "updatedAt": stato.get("aggiornato_il", ""),
        "cachePath": stato.get("cache_path", ""),
        "expired": bool(stato.get("scaduta")),
        "perType": dict(sorted(per_tipo.items())),
    }


def build_react_tribunali_payload() -> dict[str, Any]:
    """Payload React per Tribunali / PEC, usando la cache uffici reale."""

    from collections import Counter

    from pct.uffici_giudiziari import get_gestore, indirizzi_telematici_ufficio

    gestore = get_gestore()
    uffici = list(gestore.carica())
    stato = gestore.stato()
    per_tipo = Counter(str(row.get("tipo") or "ALTRO") for row in uffici)
    offices = []
    for index, row in enumerate(uffici):
        office = _office_row_payload(row, index)
        office["indirizziTelematici"] = indirizzi_telematici_ufficio(
            row,
            data_rilevazione=str(stato.get("aggiornato_il") or ""),
        )
        offices.append(office)
    pec_count = sum(1 for item in offices if item["pec"])
    return {
        "source": "repository_reali",
        "generatedAt": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "read_only": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "surface": {
            "id": "tribunali",
            "portal": "",
            "title": "Tribunali / PEC",
            "eyebrow": "Uffici giudiziari e indirizzi",
            "subtitle": "Ricerca uffici, PEC, codici e stato dell'elenco collegato a ReGINdE/PST.",
            "tone": "primary",
            "appHref": "/tribunali",
            "legacyHref": "/tribunali",
            "officialHref": "https://pst.giustizia.it/PST/it/services.page",
        },
        "summary": {
            "total": len(offices),
            "imports": pec_count,
            "attention": 1 if stato.get("scaduta") else 0,
            "blocked": 0,
            "warnings": 1 if stato.get("scaduta") else 0,
        },
        "channel": None,
        "operationCards": [
            _surface_card(
                "ricerca",
                "Ricerca uffici",
                "Filtra per denominazione, distretto, tipo, codice o indirizzo PEC.",
                tone="primary",
                icon="search",
                metrics=[
                    {"label": "Uffici", "value": len(offices)},
                    {"label": "PEC censite", "value": pec_count},
                ],
            ),
            _surface_card(
                "aggiorna",
                "Aggiorna elenco",
                "Aggiorna l'elenco uffici quando devi verificare variazioni o nuovi indirizzi.",
                tone="warning",
                icon="refresh",
                actions=[_surface_action("aggiorna", "Aggiorna", "/api/uffici/aggiorna", tone="warning", method="POST")],
            ),
            _surface_card(
                "variazioni",
                "Verifica variazioni",
                "Consulta o avvia il report di variazione uffici senza lasciare la pagina.",
                tone="success",
                icon="shield",
                actions=[
                    _surface_action("report", "Report", "/api/uffici/variazioni", tone="success"),
                    _surface_action("esegui", "Esegui verifica", "/api/uffici/variazioni/esegui", tone="warning", method="POST"),
                ],
            ),
            _surface_card(
                "centro-react",
                "Centro telematico",
                "Rientra nella cabina che coordina PST, PDP, PAT, PTT, controlli e firma digitale.",
                tone="neutral",
                icon="external",
                actions=[_surface_action("centro", "Apri centro", "/telematico", tone="neutral")],
            ),
        ],
        "checklistGroups": [],
        "controlTower": {
            "pendingOutcomes": [],
            "incompleteImports": [],
            "warnings": [],
            "blockedCases": [],
            "predeposito": [],
        },
        "recentCases": [],
        "recentEvents": [],
        "links": [
            {"label": "Ricerca uffici", "href": "/api/uffici", "kind": "azione"},
            {"label": "Stato elenco", "href": "/api/uffici/stato", "kind": "azione"},
            {"label": "Centro telematico", "href": "/telematico", "kind": "react"},
            {"label": "Checklist deposito", "href": "/deposito/checklist", "kind": "react"},
        ],
        "notices": [
            {
                "tone": "warning" if stato.get("scaduta") else "success",
                "title": "Stato elenco uffici",
                "body": f"Sorgente: {stato.get('sorgente', 'bundle')} - aggiornato il {stato.get('aggiornato_il', '')}.",
            }
        ],
        "lexSuggestions": [
            "Prima del deposito verifica sempre codice ufficio e PEC destinataria.",
            "Se l'elenco risulta da aggiornare, avvia l'aggiornamento o controlla il report variazioni.",
        ],
        "offices": offices,
        "officeSummary": {
            "source": stato.get("sorgente", "bundle"),
            "updatedAt": stato.get("aggiornato_il", ""),
            "cachePath": stato.get("cache_path", ""),
            "expired": bool(stato.get("scaduta")),
            "perType": dict(sorted(per_tipo.items())),
            "sources": stato.get("fonti_uffici", []),
            "policy": stato.get("policy_pec", ""),
        },
    }


def build_react_telematico_payload(
    *,
    get_telematico: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    build_access_status_payload: Callable[[str], dict[str, Any]],
    logger: Any | None = None,
) -> dict[str, Any]:
    """Costruisce il payload reale per ``/api/v1/ui/telematico``."""

    repo = _safe("telematico_repo", get_telematico, None, logger)
    stats = _safe("case_stats", lambda: repo.case_stats() if repo else {}, {"totale": 0, "per_service": {}}, logger)
    recent_cases = _safe("list_cases", lambda: repo.list_cases(limit=18) if repo else [], [], logger)
    recent_events = _safe("list_recent_events", lambda: repo.list_recent_events(limit=12) if repo else [], [], logger)
    fascicoli = _safe("fascicoli", lambda: get_fascicoli().tutti(), [], logger)
    fascicoli_index = {str(getattr(fascicolo, "id", "")): fascicolo for fascicolo in fascicoli}
    control_tower = _safe(
        "control_tower",
        lambda: build_telematico_control_tower(get_telematico=get_telematico, get_fascicoli=get_fascicoli),
        {
            "summary": {"pending_outcomes": 0, "imports_incomplete": 0, "warnings": 0, "blocked": 0},
            "pending_outcomes": [],
            "incomplete_imports": [],
            "warning_cases": [],
            "blocked_cases": [],
            "predeposito": [],
            "recent_events": [],
        },
        logger,
    )
    access_payloads = {
        portal: _safe("access_status", lambda portal=portal: build_access_status_payload(portal), {}, logger)
        for portal in PORTALS
    }
    channels = [_build_channel(portal, stats, access_payloads[portal]) for portal in PORTALS]
    control_payload = _control_tower_payload(control_tower, fascicoli_index)
    summary_raw = dict(control_tower.get("summary") or {})
    summary = {
        "total": _int(stats.get("totale")) or sum(_int(channel.get("cases")) for channel in channels),
        "pst": _int(channels[0].get("cases")),
        "pdp": _int(channels[1].get("cases")),
        "pat": _int(channels[2].get("cases")),
        "ptt": _int(channels[3].get("cases")),
        "pendingOutcomes": _int(summary_raw.get("pending_outcomes") or len(control_payload["pendingOutcomes"])),
        "incompleteImports": _int(summary_raw.get("imports_incomplete") or len(control_payload["incompleteImports"])),
        "warnings": _int(summary_raw.get("warnings") or len(control_payload["warnings"])),
        "blocked": _int(summary_raw.get("blocked") or len(control_payload["blockedCases"])),
        "attentionNeeded": sum(_int(channel.get("attentionNeeded")) for channel in channels),
    }
    notices = []
    if summary["blocked"] or summary["warnings"]:
        notices.append(
            {
                "tone": "warning",
                "title": "Regia telematica da presidiare",
                "body": f"Sono presenti {summary['warnings']} warning e {summary['blocked']} blocchi nei controlli telematici.",
            }
        )
    if any(channel.get("demoMode") for channel in channels):
        notices.append(
            {
                "tone": "warning",
                "title": "Canale assistito",
                "body": "Almeno un portale richiede apertura guidata o import manuale autorizzato: non usare scraping HTML.",
            }
        )
    return {
        "source": "repository_reali",
        "generatedAt": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "read_only": True,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "summary": summary,
        "channels": channels,
        "recentCases": [_case_row(dict(row or {}), index, fascicoli_index) for index, row in enumerate(recent_cases)],
        "recentEvents": [_event_row(dict(row or {}), index, fascicoli_index) for index, row in enumerate(list(recent_events) + list(control_tower.get("recent_events") or []))][:14],
        "controlTower": control_payload,
        "notices": notices,
        "actions": {
            "checklistHref": _safe_url("checklist_deposito", "/deposito/checklist"),
            "firmaDigitaleHref": "/guida/firma-digitale",
            "localSignerHref": "/local-signer",
            "connectionStatusHref": "/api/telematico/connection-status",
            "lexHref": "#lex",
            "emailHref": "/email/",
        },
        "lexSuggestions": _lex_suggestions(summary, channels),
    }
