"""Bridge React per il registro GDPR.

Il bridge espone alla UI dati gia' governati dal repository privacy esistente.
Le scritture restano sulle route Flask operative, cosi permessi, audit e
tenant continuano a vivere nel backend.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


BASE_GIURIDICA_OPTIONS = (
    "Contratto (art. 6.1.b GDPR)",
    "Obbligo legale (art. 6.1.c GDPR)",
    "Interesse legittimo (art. 6.1.f GDPR)",
    "Consenso (art. 6.1.a GDPR)",
    "Interesse vitale (art. 6.1.d GDPR)",
)

GDPR_OFFICIAL_SOURCES = (
    {
        "id": "garante_registro_trattamenti",
        "authority": "Garante per la protezione dei dati personali",
        "label": "Registro delle attività di trattamento",
        "url": "https://www.garanteprivacy.it/registro-delle-attivita-di-trattamento",
        "localPath": "docs/specs/ministero/fonti_ufficiali/2026-06-02/garante-registro-attivita-trattamento.html",
    },
    {
        "id": "garante_gdpr_art30",
        "authority": "Garante per la protezione dei dati personali",
        "label": "Regolamento UE 2016/679 - testo e guida",
        "url": "https://www.garanteprivacy.it/regolamentoue",
        "localPath": "docs/specs/ministero/fonti_ufficiali/2026-06-02/garante-gdpr-regolamento-2016-679.html",
    },
    {
        "id": "garante_regolamento_arricchito_pdf",
        "authority": "Garante per la protezione dei dati personali",
        "label": "Regolamento UE 2016/679 arricchito",
        "url": "https://www.garanteprivacy.it/documents/10160/0/Regolamento+UE+2016+679.+Arricchito+con+riferimenti+ai+Considerando.pdf",
        "localPath": "docs/specs/ministero/fonti_ufficiali/2026-06-02/garante-regolamento-ue-2016-679-arricchito.pdf",
    },
)

GDPR_REGISTER_CHECKLIST = (
    {
        "id": "finalita_base",
        "label": "Finalità e base giuridica",
        "message": "Ogni trattamento deve indicare finalità e presupposto di liceità.",
    },
    {
        "id": "categorie_interessati_dati",
        "label": "Categorie di interessati e dati",
        "message": "La scheda deve indicare soggetti interessati e categorie di dati trattati.",
    },
    {
        "id": "destinatari_conservazione",
        "label": "Destinatari e conservazione",
        "message": "Destinatari e termini di cancellazione/conservazione devono essere espliciti.",
    },
    {
        "id": "misure_sicurezza",
        "label": "Misure tecniche e organizzative",
        "message": "Le misure di sicurezza devono essere aggiornate e proporzionate al rischio.",
    },
    {
        "id": "trasferimenti_responsabili",
        "label": "Trasferimenti e responsabili",
        "message": "Trasferimenti extra UE e responsabili esterni richiedono garanzie e riferimenti tracciati.",
    },
)

GDPR_GOVERNANCE = {
    "title": "Presidio GDPR per studio legale",
    "message": (
        "Il registro deve riflettere i trattamenti reali dello studio ed essere aggiornato. "
        "Per attività legali con dati giudiziari, sanitari o con personale/collaboratori, "
        "il software evidenzia il registro come presidio operativo da mantenere."
    ),
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return bool(value is True or value == 1 or str(value).strip().lower() in {"1", "true", "si", "yes", "on"})


def _date_label(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return "n.d."
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return raw


def _risk_flags(item: Any) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if not _text(getattr(item, "finalita", "")):
        flags.append({
            "code": "finalita_mancante",
            "label": "Finalità",
            "tone": "danger",
            "message": "Indicare la finalità del trattamento.",
        })
    if not _text(getattr(item, "categoria_dati", "")):
        flags.append({
            "code": "categorie_dati_mancanti",
            "label": "Categorie dati",
            "tone": "danger",
            "message": "Indicare le categorie di dati personali trattati.",
        })
    if not _text(getattr(item, "soggetti_interessati", "")):
        flags.append({
            "code": "interessati_mancanti",
            "label": "Interessati",
            "tone": "warning",
            "message": "Indicare le categorie di interessati.",
        })
    if not _text(getattr(item, "destinatari", "")):
        flags.append({
            "code": "destinatari_mancanti",
            "label": "Destinatari",
            "tone": "warning",
            "message": "Indicare destinatari interni, esterni o autorità.",
        })
    if _bool(getattr(item, "trasferimento_extra_ue", False)):
        flags.append({
            "code": "extra_ue",
            "label": "Extra UE",
            "tone": "warning",
            "message": "Verificare paese, garanzie e base del trasferimento.",
        })
        if not _text(getattr(item, "paese_destinazione", "")):
            flags.append({
                "code": "paese_extra_ue_mancante",
                "label": "Paese extra UE",
                "tone": "danger",
                "message": "Indicare il paese di destinazione del trasferimento.",
            })
        if not _text(getattr(item, "garanzie_trasferimento_extra_ue", "")):
            flags.append({
                "code": "garanzie_extra_ue_mancanti",
                "label": "Garanzie extra UE",
                "tone": "danger",
                "message": "Indicare garanzie, decisione di adeguatezza o clausole applicabili.",
            })
    if not _text(getattr(item, "termine_conservazione", "")):
        flags.append({
            "code": "conservazione_mancante",
            "label": "Conservazione",
            "tone": "danger",
            "message": "Indicare il termine di conservazione.",
        })
    if not _text(getattr(item, "misure_sicurezza", "")):
        flags.append({
            "code": "sicurezza_mancante",
            "label": "Sicurezza",
            "tone": "danger",
            "message": "Indicare le misure tecniche e organizzative.",
        })
    if not _text(getattr(item, "base_giuridica", "")):
        flags.append({
            "code": "base_giuridica_mancante",
            "label": "Base giuridica",
            "tone": "warning",
            "message": "Completare la base giuridica del trattamento.",
        })
    if _text(getattr(item, "responsabile", "")) and not _text(getattr(item, "registro_responsabile", "")):
        flags.append({
            "code": "registro_responsabile_mancante",
            "label": "Responsabile",
            "tone": "warning",
            "message": "Indicare il riferimento al registro o all'accordo del responsabile esterno.",
        })
    return flags


def _treatment_payload(item: Any) -> dict[str, Any]:
    item_id = _text(getattr(item, "id", ""))
    flags = _risk_flags(item)
    return {
        "id": item_id,
        "name": _text(getattr(item, "nome", "")),
        "purpose": _text(getattr(item, "finalita", "")),
        "dataCategory": _text(getattr(item, "categoria_dati", "")),
        "legalBasis": _text(getattr(item, "base_giuridica", "")),
        "subjects": _text(getattr(item, "soggetti_interessati", "")),
        "recipients": _text(getattr(item, "destinatari", "")),
        "extraEuTransfer": _bool(getattr(item, "trasferimento_extra_ue", False)),
        "destinationCountry": _text(getattr(item, "paese_destinazione", "")),
        "transferSafeguards": _text(getattr(item, "garanzie_trasferimento_extra_ue", "")),
        "retention": _text(getattr(item, "termine_conservazione", "")),
        "securityMeasures": _text(getattr(item, "misure_sicurezza", "")),
        "processor": _text(getattr(item, "responsabile", "")),
        "processorRegister": _text(getattr(item, "registro_responsabile", "")),
        "sourceReference": _text(getattr(item, "fonte_normativa", "")) or "GDPR art. 30; Garante registro attività di trattamento",
        "active": _bool(getattr(item, "attivo", True)),
        "notes": _text(getattr(item, "note", "")),
        "createdAt": _text(getattr(item, "creato_il", "")),
        "createdLabel": _date_label(getattr(item, "creato_il", "")),
        "updatedAt": _text(getattr(item, "modificato_il", "")),
        "updatedLabel": _date_label(getattr(item, "modificato_il", "")),
        "riskFlags": flags,
        "deleteAction": f"/privacy/registro/{item_id}/elimina" if item_id else "",
    }


def build_react_privacy_registro_payload(
    get_trattamenti: Callable[[], Any],
    *,
    path: str = "/privacy/registro",
) -> dict[str, Any]:
    """Costruisce il contratto dati per la pagina React del registro GDPR."""

    treatments = [_treatment_payload(item) for item in get_trattamenti().tutti()]
    active = [item for item in treatments if item["active"]]
    extra_eu = [item for item in treatments if item["extraEuTransfer"]]
    missing_security = [item for item in treatments if not item["securityMeasures"]]
    missing_retention = [item for item in treatments if not item["retention"]]
    missing_legal_basis = [item for item in treatments if not item["legalBasis"]]
    missing_recipients = [item for item in treatments if not item["recipients"]]
    missing_subjects = [item for item in treatments if not item["subjects"]]
    missing_categories = [item for item in treatments if not item["dataCategory"]]
    missing_transfer_safeguards = [
        item for item in treatments
        if item["extraEuTransfer"] and not item["transferSafeguards"]
    ]
    warnings = sum(len(item["riskFlags"]) for item in treatments)

    return {
        "source": "repository_reali",
        "generatedAt": _iso_now(),
        "page": {
            "title": "Registro dei trattamenti",
            "subtitle": "Registro GDPR Art. 30 con trattamenti, basi giuridiche, conservazione, misure e audit operativo.",
            "path": path,
            "formOpenByDefault": path.rstrip("/").lower() == "/privacy/registro/nuovo",
        },
        "summary": {
            "total": len(treatments),
            "active": len(active),
            "inactive": len(treatments) - len(active),
            "extraEu": len(extra_eu),
            "missingSecurity": len(missing_security),
            "missingRetention": len(missing_retention),
            "missingLegalBasis": len(missing_legal_basis),
            "missingRecipients": len(missing_recipients),
            "missingSubjects": len(missing_subjects),
            "missingCategories": len(missing_categories),
            "missingTransferSafeguards": len(missing_transfer_safeguards),
            "warnings": warnings,
        },
        "treatments": treatments,
        "officialSources": list(GDPR_OFFICIAL_SOURCES),
        "registerChecklist": list(GDPR_REGISTER_CHECKLIST),
        "governance": GDPR_GOVERNANCE,
        "facets": {
            "legalBasis": [
                {"value": option, "label": option}
                for option in BASE_GIURIDICA_OPTIONS
            ],
            "status": [
                {"value": "tutti", "label": "Tutti"},
                {"value": "attivi", "label": "Attivi"},
                {"value": "inattivi", "label": "Inattivi"},
                {"value": "extra_ue", "label": "Trasferimenti extra UE"},
                {"value": "da_completare", "label": "Da completare"},
            ],
        },
        "actions": {
            "create": "/privacy/registro/nuovo",
            "list": "/privacy/registro",
            "audit": "/audit",
            "exportAuditCsv": "/audit/esporta.csv",
            "clienti": "/clienti",
            "settings": "/impostazioni",
            "lex": "#lex",
        },
        "contracts": {
            "mock_fallback": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
            "legacy_fallback": "Percorso di recupero",
        },
    }
