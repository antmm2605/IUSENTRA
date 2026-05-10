"""Bridge operativo per preventivi e conferimenti nella shell React."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from pct.preventivi import StatoConferimento, StatoPreventivo, TipoVoce, VocePreventivo

_PREVENTIVO_FIELDS = {
    "id_cliente",
    "id_fascicolo",
    "oggetto",
    "data_emissione",
    "data_scadenza",
    "tipo_compenso",
    "tipo_procedimento",
    "valore_controversia",
    "complessita",
    "voci",
    "opzioni_fiscali",
    "note",
    "from_cliente",
    "id_pratica",
    "area_pratica",
    "procedura_operativa_codice",
    "anticipazioni_art15",
    "tariffa_oraria",
    "ore_stimate",
}
_CONFERIMENTO_FIELDS = {
    "id_cliente",
    "id_fascicolo",
    "id_preventivo",
    "oggetto",
    "avvocato_referente",
    "numero_iscrizione_albo",
    "ordine_avvocati",
    "data_incarico",
    "tipo_compenso",
    "tipo_procedimento",
    "compenso_pattuito",
    "informativa_art13_resa",
    "clausola_adr_resa",
    "apri_fascicolo_guidato",
    "note",
    "from_cliente",
    "id_pratica",
    "area_pratica",
    "procedura_operativa_codice",
    "tariffa_oraria",
}
_VOICE_FIELDS = {"descrizione", "tipo", "importo"}
_FISCAL_FIELDS = {"applica_iva", "applica_cassa", "applica_ritenuta"}
_CANONICAL_AMOUNT_FIELDS = {
    "totale",
    "totale_preventivo",
    "totale_documento",
    "iva",
    "cassa",
    "cassa_forense",
    "ritenuta",
    "netto",
    "imponibile",
    "base_iva",
    "dm55",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, *, limit: int | None = None) -> str:
    raw = str(value or "").strip()
    return raw[:limit] if limit else raw


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"EUR {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _date_label(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    try:
        return date.fromisoformat(raw[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return raw[:10]


def _as_date(value: Any, field: str, errors: dict[str, str], *, required: bool) -> str:
    raw = _text(value)
    if not raw:
        if required:
            errors[field] = "Campo obbligatorio."
        return ""
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        errors[field] = "Usa il formato AAAA-MM-GG."
        return ""


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "si", "yes", "on"}


def _as_number(value: Any, field: str, errors: dict[str, str], *, minimum: float, default: float) -> float:
    raw = _text(value)
    if not raw:
        return default
    try:
        parsed = float(raw.replace(",", "."))
    except ValueError:
        errors[field] = "Inserisci un numero valido."
        return default
    if parsed < minimum:
        errors[field] = f"Il valore minimo e' {minimum:g}."
        return default
    return parsed


def _status_tone(status: str) -> str:
    return {
        "BOZZA": "warning",
        "IN_CALCOLO": "info",
        "GENERATO": "primary",
        "VERIFICATO": "info",
        "INVIATO": "primary",
        "APERTO": "warning",
        "ACCETTATO": "success",
        "RIFIUTATO": "danger",
        "SCADUTO": "danger",
        "REVISIONATO": "neutral",
        "CONVERTITO": "success",
        "ATTIVO": "success",
        "DEFINITO": "neutral",
        "REVOCATO": "danger",
    }.get(status.upper(), "neutral")


def _status_label(status: str) -> str:
    return {
        "BOZZA": "Bozza",
        "IN_CALCOLO": "In preparazione",
        "GENERATO": "Generato",
        "VERIFICATO": "Verificato",
        "INVIATO": "Inviato",
        "APERTO": "Aperto",
        "ACCETTATO": "Accettato",
        "RIFIUTATO": "Rifiutato",
        "SCADUTO": "Scaduto",
        "REVISIONATO": "Revisionato",
        "CONVERTITO": "Convertito",
        "ATTIVO": "Attivo",
        "DEFINITO": "Definito",
        "REVOCATO": "Revocato",
    }.get(status.upper(), status or "Non indicato")


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(user and callable(checker) and checker(permission))


def _metric(mid: str, label: str, value: Any, note: str, tone: str) -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _action(aid: str, label: str, href: str, tone: str = "neutral", *, method: str = "GET", enabled: bool = True) -> dict[str, Any]:
    return {"id": aid, "label": label, "href": href, "method": method, "tone": tone, "enabled": enabled}


def _safe_all(loader: Callable[[], Any], method: str, warnings: list[dict[str, str]], label: str) -> list[Any]:
    try:
        manager = loader()
        func = getattr(manager, method, None)
        if callable(func):
            return list(func())
    except Exception as exc:
        warnings.append({"code": f"{label}_non_disponibile", "message": f"Sorgente {label} non disponibile: {type(exc).__name__}."})
    return []


def _get_by_id(loader: Callable[[], Any], item_id: str) -> Any | None:
    if not item_id:
        return None
    try:
        manager = loader()
        getter = getattr(manager, "get", None)
        if callable(getter):
            return getter(item_id)
    except Exception:
        return None
    return None


def _client_label(cliente: Any) -> str:
    return (
        _text(getattr(cliente, "nome_completo", ""))
        or _text(getattr(cliente, "denominazione", ""))
        or _text(getattr(cliente, "nome", ""))
        or "Cliente non indicato"
    )


def _case_label(fascicolo: Any) -> str:
    title = _text(getattr(fascicolo, "titolo", "")) or _text(getattr(fascicolo, "oggetto", ""))
    rg = _text(getattr(fascicolo, "numero_rg", ""))
    if title and rg:
        return f"{title} - RG {rg}"
    return title or rg or "Fascicolo senza titolo"


def _client_option(cliente: Any) -> dict[str, Any]:
    cid = _text(getattr(cliente, "id", ""))
    fiscal = _text(getattr(cliente, "codice_fiscale", "")) or _text(getattr(cliente, "partita_iva", ""))
    return {"id": cid, "value": cid, "label": _client_label(cliente), "description": fiscal}


def _matter_option(fascicolo: Any) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    return {
        "id": fid,
        "value": fid,
        "idCliente": _text(getattr(fascicolo, "id_cliente", "")),
        "label": _case_label(fascicolo),
        "description": _text(getattr(fascicolo, "numero_rg", "")),
    }


def _estimate_option(preventivo: Any, clienti: dict[str, Any]) -> dict[str, Any]:
    pid = _text(getattr(preventivo, "id", ""))
    numero = _text(getattr(preventivo, "numero", "")) or pid
    subject = _text(getattr(preventivo, "oggetto", ""))
    id_cliente = _text(getattr(preventivo, "id_cliente", ""))
    return {
        "id": pid,
        "value": pid,
        "idCliente": id_cliente,
        "label": f"{numero} - {subject}" if subject else numero,
        "description": _client_label(clienti.get(id_cliente)),
        "amountDisplay": _money(getattr(preventivo, "totale", 0)),
        "state": _enum(getattr(preventivo, "stato", "")),
    }


def _preventivo_record(preventivo: Any, clienti: dict[str, Any], fascicoli: dict[str, Any]) -> dict[str, Any]:
    pid = _text(getattr(preventivo, "id", ""))
    status = _enum(getattr(preventivo, "stato", ""))
    id_cliente = _text(getattr(preventivo, "id_cliente", ""))
    id_fascicolo = _text(getattr(preventivo, "id_fascicolo", ""))
    return {
        "id": pid,
        "kind": "preventivo",
        "number": _text(getattr(preventivo, "numero", "")) or pid,
        "subject": _text(getattr(preventivo, "oggetto", "")) or "Oggetto non indicato",
        "customerName": _client_label(clienti.get(id_cliente)),
        "caseTitle": _case_label(fascicoli.get(id_fascicolo)) if id_fascicolo else "",
        "amountDisplay": _money(getattr(preventivo, "totale", 0)),
        "issuedAt": _date_label(getattr(preventivo, "data_emissione", "")),
        "dueAt": _date_label(getattr(preventivo, "data_scadenza", "")),
        "engagementAt": "",
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
        "detailHref": f"/preventivi/p/{pid}" if pid else "",
        "wizardHref": "/preventivi/wizard",
        "legacyHref": "/preventivi?_legacy=1",
    }


def _conferimento_record(conferimento: Any, clienti: dict[str, Any], fascicoli: dict[str, Any]) -> dict[str, Any]:
    cid = _text(getattr(conferimento, "id", ""))
    status = _enum(getattr(conferimento, "stato", ""))
    id_cliente = _text(getattr(conferimento, "id_cliente", ""))
    id_fascicolo = _text(getattr(conferimento, "id_fascicolo", ""))
    return {
        "id": cid,
        "kind": "conferimento",
        "number": _text(getattr(conferimento, "numero", "")) or cid,
        "subject": _text(getattr(conferimento, "oggetto", "")) or "Oggetto non indicato",
        "customerName": _client_label(clienti.get(id_cliente)),
        "caseTitle": _case_label(fascicoli.get(id_fascicolo)) if id_fascicolo else "",
        "amountDisplay": _money(getattr(conferimento, "compenso_pattuito", 0)),
        "issuedAt": "",
        "dueAt": "",
        "engagementAt": _date_label(getattr(conferimento, "data_incarico", "")),
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
        "detailHref": f"/preventivi/conferimento/{cid}" if cid else "",
        "wizardHref": "",
        "legacyHref": "/preventivi?_legacy=1",
    }


def _contracts(route: str) -> dict[str, Any]:
    if route.startswith("/preventivi/conferimento/") and route != "/preventivi/conferimento/nuovo":
        return {
            "mock_fallback": False,
            "writes": "json_api",
            "route_owner": "react_shell",
            "operational": True,
            "document_generation": "backend_legacy",
            "canonical_persistence": "backend",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/preventivi__conferimento__detail.json",
        }
    if route == "/preventivi/nuovo":
        return {
            "mock_fallback": False,
            "writes": "json_api",
            "route_owner": "react_shell",
            "operational": True,
            "canonical_calculation": "backend",
            "dm55_calculation": "backend",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/preventivi__nuovo.json",
        }
    if route == "/preventivi/conferimento/nuovo":
        return {
            "mock_fallback": False,
            "writes": "json_api",
            "route_owner": "react_shell",
            "operational": True,
            "document_generation": "backend_legacy",
            "canonical_persistence": "backend",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/preventivi__conferimento__nuovo.json",
        }
    return {
        "mock_fallback": False,
        "writes": "json_api",
        "route_owner": "react_shell",
        "operational": True,
        "canonical_calculation": "backend",
        "document_generation": "backend_legacy",
        "legacy_contract": "artifacts/react-migration/legacy-contracts/preventivi.json",
    }


def _form_defaults(query: dict[str, Any] | None) -> dict[str, Any]:
    args = query or {}
    today = date.today()
    return {
        "id_cliente": _text(args.get("id_cliente") or args.get("from_cliente")),
        "id_fascicolo": _text(args.get("id_fascicolo")),
        "id_preventivo": _text(args.get("id_preventivo")),
        "oggetto": _text(args.get("oggetto"), limit=240),
        "data_emissione": _text(args.get("data_emissione")) or today.isoformat(),
        "data_scadenza": _text(args.get("data_scadenza")) or (today + timedelta(days=30)).isoformat(),
        "data_incarico": _text(args.get("data_incarico")) or today.isoformat(),
        "tipo_compenso": _text(args.get("tipo_compenso"), limit=120),
        "tipo_procedimento": _text(args.get("tipo_procedimento"), limit=120),
        "valore_controversia": _text(args.get("valore_controversia")),
        "complessita": _text(args.get("complessita"), limit=80),
        "compenso_pattuito": _text(args.get("compenso_pattuito")),
        "avvocato_referente": _text(args.get("avvocato_referente"), limit=160),
        "numero_iscrizione_albo": _text(args.get("numero_iscrizione_albo"), limit=80),
        "ordine_avvocati": _text(args.get("ordine_avvocati"), limit=160),
        "note": _text(args.get("note"), limit=2000),
        "voci": [{"descrizione": _text(args.get("descrizione"), limit=240), "tipo": "ONORARIO", "importo": _text(args.get("importo"))}],
        "opzioni_fiscali": {"applica_iva": True, "applica_cassa": True, "applica_ritenuta": False},
        "hidden": {
            "from_cliente": _text(args.get("from_cliente")),
            "id_pratica": _text(args.get("id_pratica")),
            "area_pratica": _text(args.get("area_pratica")),
            "procedura_operativa_codice": _text(args.get("procedura_operativa_codice")),
        },
    }


def _prefill_conferimento(defaults: dict[str, Any], preventivi: list[Any]) -> dict[str, Any]:
    estimate_id = _text(defaults.get("id_preventivo"))
    if not estimate_id:
        return defaults
    preventivo = next((item for item in preventivi if _text(getattr(item, "id", "")) == estimate_id), None)
    if not preventivo:
        return defaults
    merged = dict(defaults)
    merged.update({
        "id_cliente": _text(getattr(preventivo, "id_cliente", "")) or defaults.get("id_cliente", ""),
        "id_fascicolo": _text(getattr(preventivo, "id_fascicolo", "")) or defaults.get("id_fascicolo", ""),
        "oggetto": defaults.get("oggetto") or _text(getattr(preventivo, "oggetto", "")),
        "tipo_compenso": defaults.get("tipo_compenso") or _text(getattr(preventivo, "tipo_compenso", "")),
        "tipo_procedimento": defaults.get("tipo_procedimento") or _text(getattr(preventivo, "tipo_procedimento", "")),
        "compenso_pattuito": defaults.get("compenso_pattuito") or _text(getattr(preventivo, "totale", "")),
    })
    return merged


def _actions_for(route: str, current_user: Any) -> dict[str, Any]:
    can_read = _can(current_user, "fatturazione.leggi")
    can_write = _can(current_user, "fatturazione.scrivi")
    base = {
        "canCreate": can_write,
        "canUpdateStatus": can_write,
        "canArchive": False,
        "canCancel": False,
        "canDuplicate": False,
        "canCreateConferimento": can_write,
        "canOpenWizard": can_read,
        "canUseFiscalOptions": can_write,
        "canLinkMatter": can_write,
        "canLinkPreventivo": can_write,
        "canOpenMatterAfterSave": False,
    }
    if route == "/preventivi/nuovo":
        return {key: base[key] for key in ("canCreate", "canUseFiscalOptions", "canLinkMatter")}
    if route == "/preventivi/conferimento/nuovo":
        return {key: base[key] for key in ("canCreate", "canLinkPreventivo", "canLinkMatter", "canOpenMatterAfterSave")}
    return base


def build_react_preventivi_payload(
    *,
    get_preventivi: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    current_user: Any = None,
    query: dict[str, Any] | None = None,
    route: str = "/preventivi",
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        {"code": "presidio_calcolo", "message": "La pagina invia dati controllati: importi definitivi, fiscalita', parametri forensi e documenti restano nei controlli operativi."},
        {"code": "percorso_recupero", "message": "I template storici restano disponibili solo come percorso di recupero assistito."},
    ]
    preventivi: list[Any] = []
    conferimenti: list[Any] = []
    try:
        manager = get_preventivi()
        preventivi = list(getattr(manager, "tutti_preventivi", lambda: [])())
        conferimenti = list(getattr(manager, "tutti_conferimenti", lambda: [])())
    except Exception as exc:
        warnings.append({"code": "preventivi_non_disponibili", "message": f"Archivio preventivi non disponibile: {type(exc).__name__}."})

    clienti_list = _safe_all(get_clienti, "tutti", warnings, "clienti")
    fascicoli_list = _safe_all(get_fascicoli, "tutti", warnings, "fascicoli")
    clienti = {_text(getattr(cliente, "id", "")): cliente for cliente in clienti_list}
    fascicoli = {_text(getattr(fascicolo, "id", "")): fascicolo for fascicolo in fascicoli_list}
    preventivo_records = [_preventivo_record(item, clienti, fascicoli) for item in preventivi[:240]]
    conferimento_records = [_conferimento_record(item, clienti, fascicoli) for item in conferimenti[:240]]
    records = preventivo_records + conferimento_records
    defaults = _prefill_conferimento(_form_defaults(query), preventivi) if route == "/preventivi/conferimento/nuovo" else _form_defaults(query)
    statuses = [{"value": item.value, "label": _status_label(item.value), "tone": _status_tone(item.value)} for item in StatoPreventivo]
    actions = _actions_for(route, current_user)
    form = {
        "id": "nuovo_conferimento" if route == "/preventivi/conferimento/nuovo" else "nuovo_preventivo",
        "readHref": f"/api/v1/ui{route}",
        "saveHref": f"/api/v1/ui{route}",
        "enabled": actions.get("canCreate", False),
        "defaults": defaults,
    }
    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(route),
        "metrics": [
            _metric("preventivi_totali", "Preventivi", len(preventivo_records), "Archivio corrente", "primary"),
            _metric("preventivi_aperti", "Preventivi aperti", len([row for row in preventivo_records if row["state"] in {"BOZZA", "GENERATO", "INVIATO", "APERTO"}]), "Stati dall'archivio", "warning"),
            _metric("preventivi_accettati", "Accettati", len([row for row in preventivo_records if row["state"] in {"ACCETTATO", "CONVERTITO"}]), "Valori calcolati", "success"),
            _metric("conferimenti", "Conferimenti", len(conferimento_records), "Incarichi collegati", "info"),
        ],
        "sections": [
            _section("stati_preventivo", "Stati preventivo", "distribution", [_item(item.value.lower(), _status_label(item.value), len([row for row in preventivo_records if row["state"] == item.value]), "Conteggio archivio", _status_tone(item.value)) for item in StatoPreventivo], "Nessun preventivo."),
            _section("stati_conferimento", "Stati conferimento", "distribution", [_item(code.lower(), _status_label(code), len([row for row in conferimento_records if row["state"] == code]), "Conteggio archivio", _status_tone(code)) for code in ("ATTIVO", "DEFINITO", "REVOCATO")], "Nessun conferimento."),
        ],
        "records": records,
        "estimates": [_estimate_option(item, clienti) for item in preventivi if _enum(getattr(item, "stato", "")) in {"ACCETTATO", "CONVERTITO", "INVIATO", "APERTO", "VERIFICATO"}],
        "assignments": conferimento_records,
        "statuses": statuses,
        "clients": [_client_option(item) for item in clienti_list],
        "matters": [_matter_option(item) for item in fascicoli_list],
        "defaults": defaults,
        "form": form,
        "forms": [form],
        "fiscal_options": [
            {"name": "applica_cassa", "label": "Cassa Forense", "default": True, "description": "Dato inviato ai controlli operativi."},
            {"name": "applica_iva", "label": "IVA", "default": True, "description": "Dato inviato ai controlli operativi."},
            {"name": "applica_ritenuta", "label": "Ritenuta", "default": False, "description": "Dato inviato ai controlli operativi."},
        ],
        "compensation_options": [
            {"value": "forfait", "label": "Forfait", "description": "Configurazione testuale, calcolo applicativo."},
            {"value": "tempo", "label": "A tempo", "description": "Ore e tariffa sono input, calcolo applicativo."},
            {"value": "fasi", "label": "Per fasi", "description": "Parametri forensi gestiti dai controlli operativi."},
        ],
        "studio": {
            "avvocato_referente": defaults.get("avvocato_referente", ""),
            "numero_iscrizione_albo": defaults.get("numero_iscrizione_albo", ""),
            "ordine_avvocati": defaults.get("ordine_avvocati", ""),
        },
        "clauses": {"informativa_art13_resa": True, "clausola_adr_resa": True},
        "actions": {
            **actions,
            "links": [
                _action("nuovo_preventivo", "Nuovo preventivo", "/preventivi/nuovo", "primary"),
                _action("nuovo_conferimento", "Nuovo conferimento", "/preventivi/conferimento/nuovo", "primary"),
                _action("percorso_guidato", "Percorso preventivi", "/preventivi/wizard", "neutral"),
                _action("percorso_recupero", "Percorso di recupero", f"{route}?_legacy=1", "warning"),
            ],
        },
        "warnings": warnings,
    }


def build_react_nuovo_preventivo_payload(**kwargs: Any) -> dict[str, Any]:
    kwargs["route"] = "/preventivi/nuovo"
    return build_react_preventivi_payload(**kwargs)


def build_react_nuovo_conferimento_payload(**kwargs: Any) -> dict[str, Any]:
    kwargs["route"] = "/preventivi/conferimento/nuovo"
    return build_react_preventivi_payload(**kwargs)


def build_react_preventivi_error_payload(message: str = "Preventivi non disponibili.", *, route: str = "/preventivi") -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(route),
        "metrics": [],
        "sections": [],
        "records": [],
        "assignments": [],
        "statuses": [],
        "clients": [],
        "matters": [],
        "estimates": [],
        "defaults": {},
        "form": {},
        "forms": [],
        "fiscal_options": [],
        "compensation_options": [],
        "actions": _actions_for(route, None),
        "warnings": [{"code": "preventivi_errore_controllato", "message": message}],
    }


def _unknown_fields(payload: dict[str, Any], allowed: set[str]) -> set[str]:
    return {key for key in payload if key not in allowed}


def _reject_canonical_fields(payload: dict[str, Any], errors: dict[str, str], prefix: str = "") -> None:
    for field in sorted(_CANONICAL_AMOUNT_FIELDS & set(payload.keys())):
        errors[f"{prefix}{field}" if prefix else field] = "Importo o calcolo non accettato dalla pagina."
    for field in payload:
        if field.lower().startswith("dm55"):
            errors[f"{prefix}{field}" if prefix else field] = "Calcolo forense non accettato dalla pagina."


def _voice_type(value: Any, errors: dict[str, str], field: str) -> TipoVoce:
    key = _text(value or "ONORARIO").upper().replace(" ", "_")
    mapping = {
        "ONORARIO": TipoVoce.ONORARIO,
        "SPESE": TipoVoce.SPESA_FORFETTARIA,
        "SPESA_FORFETTARIA": TipoVoce.SPESA_FORFETTARIA,
        "ANTICIPO": TipoVoce.SPESA_VIVA,
        "ANTICIPAZIONE": TipoVoce.SPESA_VIVA,
        "SPESA_VIVA": TipoVoce.SPESA_VIVA,
    }
    if key not in mapping:
        errors[field] = "Tipo voce non consentito."
    return mapping.get(key, TipoVoce.ONORARIO)


def _validate_preventivo_payload(payload: dict[str, Any], *, get_clienti: Callable[[], Any], get_fascicoli: Callable[[], Any]) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}
    unknown = _unknown_fields(payload, _PREVENTIVO_FIELDS)
    if unknown:
        errors["payload"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
    _reject_canonical_fields(payload, errors)
    raw_options = payload.get("opzioni_fiscali") or {}
    if not isinstance(raw_options, dict):
        errors["opzioni_fiscali"] = "Opzioni fiscali non valide."
        raw_options = {}
    option_unknown = _unknown_fields(raw_options, _FISCAL_FIELDS)
    if option_unknown:
        errors["opzioni_fiscali"] = "Campi non consentiti: " + ", ".join(sorted(option_unknown))
    _reject_canonical_fields(raw_options, errors, "opzioni_fiscali.")
    id_cliente = _text(payload.get("id_cliente"))
    id_fascicolo = _text(payload.get("id_fascicolo"))
    if not id_cliente:
        errors["id_cliente"] = "Seleziona un cliente."
    elif not _get_by_id(get_clienti, id_cliente):
        errors["id_cliente"] = "Cliente non trovato."
    fascicolo = _get_by_id(get_fascicoli, id_fascicolo) if id_fascicolo else None
    if id_fascicolo and not fascicolo:
        errors["id_fascicolo"] = "Fascicolo non trovato."
    if fascicolo and _text(getattr(fascicolo, "id_cliente", "")) and _text(getattr(fascicolo, "id_cliente", "")) != id_cliente:
        errors["id_fascicolo"] = "Il fascicolo non appartiene al cliente selezionato."
    subject = _text(payload.get("oggetto"), limit=240)
    if not subject:
        errors["oggetto"] = "Oggetto obbligatorio."
    issued_at = _as_date(payload.get("data_emissione"), "data_emissione", errors, required=True)
    due_at = _as_date(payload.get("data_scadenza"), "data_scadenza", errors, required=True)
    if issued_at and due_at and due_at < issued_at:
        errors["data_scadenza"] = "La scadenza non puo' precedere la data di emissione."
    raw_voices = payload.get("voci")
    if not isinstance(raw_voices, list):
        errors["voci"] = "Aggiungi almeno una voce."
        raw_voices = []
    voices: list[VocePreventivo] = []
    for index, raw_item in enumerate(raw_voices):
        if not isinstance(raw_item, dict):
            errors[f"voci.{index}"] = "Voce non valida."
            continue
        unknown_voice = _unknown_fields(raw_item, _VOICE_FIELDS)
        if unknown_voice:
            errors[f"voci.{index}"] = "Campi non consentiti: " + ", ".join(sorted(unknown_voice))
        _reject_canonical_fields(raw_item, errors, f"voci.{index}.")
        description = _text(raw_item.get("descrizione"), limit=240)
        amount = _as_number(raw_item.get("importo"), f"voci.{index}.importo", errors, minimum=0.0, default=0.0)
        if not description:
            errors[f"voci.{index}.descrizione"] = "Descrizione obbligatoria."
        if description:
            voices.append(VocePreventivo(descrizione=description, importo=amount, tipo=_voice_type(raw_item.get("tipo"), errors, f"voci.{index}.tipo")))
    if not voices and "voci" not in errors:
        errors["voci"] = "Aggiungi almeno una voce valida."
    return {
        "id_cliente": id_cliente,
        "id_fascicolo": id_fascicolo or None,
        "oggetto": subject,
        "data_emissione": issued_at,
        "data_scadenza": due_at,
        "voci": voices,
        "applica_iva": _as_bool(raw_options.get("applica_iva"), True),
        "applica_cassa": _as_bool(raw_options.get("applica_cassa"), True),
        "anticipazioni_art15": _as_number(payload.get("anticipazioni_art15"), "anticipazioni_art15", errors, minimum=0.0, default=0.0),
        "note": _text(payload.get("note"), limit=2000),
        "id_pratica": _text(payload.get("id_pratica"), limit=120),
        "area_pratica": _text(payload.get("area_pratica"), limit=120),
        "procedura_operativa_codice": _text(payload.get("procedura_operativa_codice"), limit=120),
        "tipo_compenso": _text(payload.get("tipo_compenso"), limit=120),
        "tipo_procedimento": _text(payload.get("tipo_procedimento"), limit=120),
        "valore_controversia": _as_number(payload.get("valore_controversia"), "valore_controversia", errors, minimum=0.0, default=0.0),
        "tariffa_oraria": _as_number(payload.get("tariffa_oraria"), "tariffa_oraria", errors, minimum=0.0, default=0.0),
        "ore_stimate": _as_number(payload.get("ore_stimate"), "ore_stimate", errors, minimum=0.0, default=0.0),
        "complessita": _text(payload.get("complessita"), limit=80),
        "from_cliente": _text(payload.get("from_cliente")),
    }, errors


def _validate_conferimento_payload(payload: dict[str, Any], *, get_preventivi: Callable[[], Any], get_clienti: Callable[[], Any], get_fascicoli: Callable[[], Any]) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}
    unknown = _unknown_fields(payload, _CONFERIMENTO_FIELDS)
    if unknown:
        errors["payload"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
    _reject_canonical_fields(payload, errors)
    id_cliente = _text(payload.get("id_cliente"))
    id_fascicolo = _text(payload.get("id_fascicolo"))
    id_preventivo = _text(payload.get("id_preventivo"))
    preventivo = None
    if id_preventivo:
        try:
            preventivo = get_preventivi().get_preventivo(id_preventivo)
        except Exception:
            preventivo = None
        if not preventivo:
            errors["id_preventivo"] = "Preventivo non trovato."
    if not id_cliente and preventivo:
        id_cliente = _text(getattr(preventivo, "id_cliente", ""))
    if not id_fascicolo and preventivo:
        id_fascicolo = _text(getattr(preventivo, "id_fascicolo", ""))
    if not id_cliente:
        errors["id_cliente"] = "Seleziona un cliente."
    elif not _get_by_id(get_clienti, id_cliente):
        errors["id_cliente"] = "Cliente non trovato."
    fascicolo = _get_by_id(get_fascicoli, id_fascicolo) if id_fascicolo else None
    if id_fascicolo and not fascicolo:
        errors["id_fascicolo"] = "Fascicolo non trovato."
    if fascicolo and _text(getattr(fascicolo, "id_cliente", "")) and _text(getattr(fascicolo, "id_cliente", "")) != id_cliente:
        errors["id_fascicolo"] = "Il fascicolo non appartiene al cliente selezionato."
    subject = _text(payload.get("oggetto") or getattr(preventivo, "oggetto", ""), limit=240)
    if not subject:
        errors["oggetto"] = "Oggetto obbligatorio."
    lawyer = _text(payload.get("avvocato_referente"), limit=160)
    if not lawyer:
        errors["avvocato_referente"] = "Avvocato referente obbligatorio."
    return {
        "id_cliente": id_cliente,
        "id_fascicolo": id_fascicolo or None,
        "id_preventivo": id_preventivo or None,
        "oggetto": subject,
        "avvocato_referente": lawyer,
        "data_incarico": _as_date(payload.get("data_incarico"), "data_incarico", errors, required=True),
        "compenso_pattuito": _as_number(payload.get("compenso_pattuito"), "compenso_pattuito", errors, minimum=0.0, default=0.0),
        "note": _text(payload.get("note"), limit=2000),
        "id_pratica": _text(payload.get("id_pratica") or getattr(preventivo, "id_pratica", ""), limit=120),
        "area_pratica": _text(payload.get("area_pratica") or getattr(preventivo, "area_pratica", ""), limit=120),
        "procedura_operativa_codice": _text(payload.get("procedura_operativa_codice") or getattr(preventivo, "procedura_operativa_codice", ""), limit=120),
        "numero_iscrizione_albo": _text(payload.get("numero_iscrizione_albo"), limit=80),
        "ordine_avvocati": _text(payload.get("ordine_avvocati"), limit=160),
        "tipo_compenso": _text(payload.get("tipo_compenso") or getattr(preventivo, "tipo_compenso", ""), limit=120),
        "tipo_procedimento": _text(payload.get("tipo_procedimento") or getattr(preventivo, "tipo_procedimento", ""), limit=120),
        "tariffa_oraria": _as_number(payload.get("tariffa_oraria"), "tariffa_oraria", errors, minimum=0.0, default=0.0),
        "informativa_art13_resa": _as_bool(payload.get("informativa_art13_resa"), True),
        "clausola_adr_resa": _as_bool(payload.get("clausola_adr_resa"), True),
        "from_cliente": _text(payload.get("from_cliente")),
    }, errors


def _audit(get_utenti: Callable[[], Any], current_user: Any, action: str, resource_type: str, resource_id: str, ip_address: str) -> None:
    try:
        registrar = getattr(get_utenti(), "registra_evento", None)
        if not callable(registrar):
            return
        registrar(
            action,
            id_utente=_text(getattr(current_user, "id", "")),
            username=_text(getattr(current_user, "username", "")),
            risorsa_tipo=resource_type,
            risorsa_id=resource_id,
            dettagli="origine=react_operational_full",
            ip=ip_address,
            esito="OK",
        )
    except Exception:
        return


def _created_item(item: Any, kind: str) -> dict[str, Any]:
    status = _enum(getattr(item, "stato", ""))
    return {
        "id": _text(getattr(item, "id", "")),
        "kind": kind,
        "number": _text(getattr(item, "numero", "")),
        "subject": _text(getattr(item, "oggetto", "")),
        "amountDisplay": _money(getattr(item, "totale", getattr(item, "compenso_pattuito", 0))),
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
    }


def create_react_preventivo(
    *,
    get_preventivi: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}, 403
    validated, errors = _validate_preventivo_payload(payload, get_clienti=get_clienti, get_fascicoli=get_fascicoli)
    if errors:
        return {"ok": False, "message": "Controlla i campi evidenziati.", "errors": errors, "item": None}, 400
    try:
        manager = get_preventivi()
        item = manager.crea_preventivo(creato_da=_text(getattr(current_user, "username", "")), **{k: v for k, v in validated.items() if k != "from_cliente"})
    except ValueError as exc:
        return {"ok": False, "message": "Creazione non completata.", "errors": {"payload": _text(exc) or "Dati non validi."}, "item": None}, 400
    _audit(get_utenti, current_user, "preventivi.crea", "preventivo", _text(getattr(item, "id", "")), ip_address)
    redirect_href = f"/clienti/{validated['from_cliente']}" if validated["from_cliente"] else f"/preventivi/p/{_text(getattr(item, 'id', ''))}"
    return {"ok": True, "message": f"Preventivo {_text(getattr(item, 'numero', ''))} creato.", "errors": {}, "item": _created_item(item, "preventivo"), "redirect_href": redirect_href}, 200


def create_react_conferimento(
    *,
    get_preventivi: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}, 403
    validated, errors = _validate_conferimento_payload(payload, get_preventivi=get_preventivi, get_clienti=get_clienti, get_fascicoli=get_fascicoli)
    if errors:
        return {"ok": False, "message": "Controlla i campi evidenziati.", "errors": errors, "item": None}, 400
    try:
        manager = get_preventivi()
        item = manager.crea_conferimento(creato_da=_text(getattr(current_user, "username", "")), **{k: v for k, v in validated.items() if k not in {"from_cliente"}})
        if validated["id_preventivo"]:
            manager.cambia_stato_preventivo(validated["id_preventivo"], StatoPreventivo.CONVERTITO)
    except ValueError as exc:
        return {"ok": False, "message": "Creazione non completata.", "errors": {"payload": _text(exc) or "Dati non validi."}, "item": None}, 400
    _audit(get_utenti, current_user, "preventivi.conferimento.crea", "conferimento", _text(getattr(item, "id", "")), ip_address)
    redirect_href = f"/clienti/{validated['from_cliente']}" if validated["from_cliente"] else f"/preventivi/conferimento/{_text(getattr(item, 'id', ''))}"
    return {"ok": True, "message": f"Conferimento {_text(getattr(item, 'numero', ''))} creato.", "errors": {}, "item": _created_item(item, "conferimento"), "redirect_href": redirect_href}, 200


def build_react_preventivo_detail_payload(
    *,
    get_preventivi: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    id_preventivo: str,
) -> tuple[dict[str, Any], int]:
    try:
        manager = get_preventivi()
        preventivo = manager.get_preventivo(id_preventivo)
    except Exception:
        preventivo = None
    if not preventivo:
        return {"ok": False, "message": "Preventivo non trovato.", "errors": {"id_preventivo": "Identificativo non valido."}, "item": None}, 404
    warnings: list[dict[str, str]] = []
    clienti_list = _safe_all(get_clienti, "tutti", warnings, "clienti")
    fascicoli_list = _safe_all(get_fascicoli, "tutti", warnings, "fascicoli")
    clienti = {_text(getattr(cliente, "id", "")): cliente for cliente in clienti_list}
    fascicoli = {_text(getattr(fascicolo, "id", "")): fascicolo for fascicolo in fascicoli_list}
    item = _preventivo_record(preventivo, clienti, fascicoli)
    item["voci"] = [{"descrizione": _text(getattr(voce, "descrizione", "")), "tipo": _enum(getattr(voce, "tipo", "")), "importoDisplay": _money(getattr(voce, "importo", 0))} for voce in list(getattr(preventivo, "voci", []) or [])]
    return {"ok": True, "source": "repository_reali", "generated_at": _iso_now(), "contracts": _contracts("/preventivi"), "item": item, "warnings": warnings}, 200


def _conferimento_detail_item(conferimento: Any, cliente: Any, fascicolo: Any, preventivo: Any) -> dict[str, Any]:
    item = _conferimento_record(
        conferimento,
        {_text(getattr(cliente, "id", "")): cliente} if cliente else {},
        {_text(getattr(fascicolo, "id", "")): fascicolo} if fascicolo else {},
    )
    preventivo_id = _text(getattr(conferimento, "id_preventivo", ""))
    cliente_id = _text(getattr(conferimento, "id_cliente", ""))
    fascicolo_id = _text(getattr(conferimento, "id_fascicolo", ""))
    signed = bool(getattr(conferimento, "firma_cliente_eseguita", False))
    customer_complete = bool(getattr(cliente, "profilo_completo_per_conferimento", False)) if cliente else False
    missing_customer_fields = [str(row) for row in (getattr(cliente, "campi_mancanti_per_conferimento", []) or [])]
    return {
        **item,
        "lawyer": _text(getattr(conferimento, "avvocato_referente", "")),
        "barNumber": _text(getattr(conferimento, "numero_iscrizione_albo", "")),
        "barCouncil": _text(getattr(conferimento, "ordine_avvocati", "")),
        "compensationType": _text(getattr(conferimento, "tipo_compenso", "")),
        "proceedingType": _text(getattr(conferimento, "tipo_procedimento", "")),
        "createdBy": _text(getattr(conferimento, "creato_da", "")),
        "createdAt": _date_label(getattr(conferimento, "creato_il", "")),
        "notes": _text(getattr(conferimento, "note", "")),
        "preventivoId": preventivo_id,
        "preventivoNumber": _text(getattr(preventivo, "numero", "")),
        "preventivoHref": f"/preventivi/p/{preventivo_id}" if preventivo_id else "",
        "customerId": cliente_id,
        "customerHref": f"/clienti/{cliente_id}" if cliente_id else "",
        "matterId": fascicolo_id,
        "matterHref": f"/fascicoli/{fascicolo_id}" if fascicolo_id else "",
        "newMatterHref": (
            f"/fascicoli/nuovo?id_cliente={cliente_id}&source_conferimento={_text(getattr(conferimento, 'id', ''))}&from_page=conferimento"
            if cliente_id
            else ""
        ),
        "completeCustomerHref": f"/clienti/{cliente_id}/modifica" if cliente_id and not customer_complete else "",
        "pdfHref": f"/preventivi/conferimento/{_text(getattr(conferimento, 'id', ''))}/pdf",
        "signed": signed,
        "signedAt": _date_label(getattr(conferimento, "firma_cliente_il", "")),
        "signatureMethod": _text(getattr(conferimento, "firma_cliente_via", "")) or ("Registrata" if signed else "Da registrare"),
        "customerComplete": customer_complete,
        "missingCustomerFields": missing_customer_fields,
        "clauses": {
            "informativaArt13": bool(getattr(conferimento, "informativa_art13_resa", False)),
            "clausolaAdr": bool(getattr(conferimento, "clausola_adr_resa", False)),
            "controversie": bool(getattr(conferimento, "clausola_controversie_attiva", False)),
            "trattativaIndividuale": bool(getattr(conferimento, "clausola_controversie_trattativa_individuale", False)),
        },
        "workflow": [
            _item("cliente", "Cliente", "Completo" if customer_complete else "Da completare", "Anagrafica necessaria per incarico e fascicolo.", "success" if customer_complete else "warning"),
            _item("firma", "Firma cliente", "Registrata" if signed else "Da registrare", "Stato firma collegato al conferimento.", "success" if signed else "warning"),
            _item("fascicolo", "Fascicolo", "Collegato" if fascicolo_id else "Da aprire", "Collegamento operativo della pratica.", "success" if fascicolo_id else "warning"),
            _item("preventivo", "Preventivo", _text(getattr(preventivo, "numero", "")) or "Non collegato", "Origine economica dell'incarico.", "info" if preventivo_id else "neutral"),
        ],
    }


def build_react_conferimento_detail_payload(
    *,
    get_preventivi: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    id_conferimento: str,
) -> tuple[dict[str, Any], int]:
    try:
        manager = get_preventivi()
        conferimento = manager.get_conferimento(id_conferimento)
    except Exception:
        conferimento = None
    if not conferimento:
        return {"ok": False, "message": "Conferimento non trovato.", "errors": {"id_conferimento": "Identificativo non valido."}, "item": None}, 404

    warnings: list[dict[str, str]] = []
    cliente = None
    fascicolo = None
    preventivo = None
    try:
        cliente = get_clienti().get(getattr(conferimento, "id_cliente", ""))
    except Exception as exc:
        warnings.append({"code": "cliente_non_disponibile", "message": f"Cliente non disponibile: {type(exc).__name__}."})
    try:
        id_fascicolo = _text(getattr(conferimento, "id_fascicolo", ""))
        fascicolo = get_fascicoli().get(id_fascicolo) if id_fascicolo else None
    except Exception as exc:
        warnings.append({"code": "fascicolo_non_disponibile", "message": f"Fascicolo non disponibile: {type(exc).__name__}."})
    try:
        id_preventivo = _text(getattr(conferimento, "id_preventivo", ""))
        preventivo = manager.get_preventivo(id_preventivo) if id_preventivo else None
    except Exception as exc:
        warnings.append({"code": "preventivo_non_disponibile", "message": f"Preventivo collegato non disponibile: {type(exc).__name__}."})

    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(f"/preventivi/conferimento/{id_conferimento}"),
        "item": _conferimento_detail_item(conferimento, cliente, fascicolo, preventivo),
        "statuses": [
            {"value": item.value, "label": _status_label(item.value), "tone": _status_tone(item.value)}
            for item in StatoConferimento
        ],
        "warnings": warnings,
    }, 200


def update_react_preventivo_status(
    *,
    get_preventivi: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_preventivo: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}, 403
    unknown = _unknown_fields(payload, {"stato", "note"})
    errors: dict[str, str] = {}
    if unknown:
        errors["payload"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
    requested = _text(payload.get("stato")).upper()
    try:
        status = StatoPreventivo(requested)
    except ValueError:
        errors["stato"] = "Stato preventivo non valido."
        status = StatoPreventivo.BOZZA
    if errors:
        return {"ok": False, "message": "Controlla i campi evidenziati.", "errors": errors, "item": None}, 400
    try:
        manager = get_preventivi()
        manager.cambia_stato_preventivo(id_preventivo, status)
        item = manager.get_preventivo(id_preventivo)
    except KeyError:
        return {"ok": False, "message": "Preventivo non trovato.", "errors": {"id_preventivo": "Identificativo non valido."}, "item": None}, 404
    _audit(get_utenti, current_user, "preventivi.stato", "preventivo", id_preventivo, ip_address)
    return {"ok": True, "message": "Stato preventivo aggiornato.", "errors": {}, "item": _created_item(item, "preventivo")}, 200


def update_react_conferimento_status(
    *,
    get_preventivi: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_conferimento: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}, 403
    unknown = _unknown_fields(payload, {"stato", "note"})
    errors: dict[str, str] = {}
    if unknown:
        errors["payload"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
    requested = _text(payload.get("stato")).upper()
    try:
        status = StatoConferimento(requested)
    except ValueError:
        errors["stato"] = "Stato conferimento non valido."
        status = StatoConferimento.ATTIVO
    if errors:
        return {"ok": False, "message": "Controlla i campi evidenziati.", "errors": errors, "item": None}, 400
    try:
        manager = get_preventivi()
        manager.cambia_stato_conferimento(id_conferimento, status)
        item = manager.get_conferimento(id_conferimento)
    except KeyError:
        return {"ok": False, "message": "Conferimento non trovato.", "errors": {"id_conferimento": "Identificativo non valido."}, "item": None}, 404
    _audit(get_utenti, current_user, "preventivi.conferimento.stato", "conferimento", id_conferimento, ip_address)
    return {"ok": True, "message": "Stato conferimento aggiornato.", "errors": {}, "item": _created_item(item, "conferimento")}, 200
