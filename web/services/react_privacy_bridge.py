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
    if _bool(getattr(item, "trasferimento_extra_ue", False)):
        flags.append({
            "code": "extra_ue",
            "label": "Extra UE",
            "tone": "warning",
            "message": "Verificare paese, garanzie e base del trasferimento.",
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
        "retention": _text(getattr(item, "termine_conservazione", "")),
        "securityMeasures": _text(getattr(item, "misure_sicurezza", "")),
        "processor": _text(getattr(item, "responsabile", "")),
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
            "warnings": warnings,
        },
        "treatments": treatments,
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
            "legacy_fallback": "_legacy=1 tecnico",
        },
    }
