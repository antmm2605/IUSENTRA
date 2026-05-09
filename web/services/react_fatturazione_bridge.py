"""Bridge operativo per le superfici React di fatturazione."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from pct.fatturazione import VoceParcella
from web.services.react_fatturazione_archive_actions import (
    build_react_fatturazione_detail_payload,
    cancel_react_fatturazione_document,
    mark_react_fatturazione_paid,
    update_react_fatturazione_status,
)


_TOP_LEVEL_FIELDS = {
    "id_cliente",
    "id_fascicolo",
    "data_emissione",
    "data_scadenza",
    "voci",
    "note",
    "opzioni_fiscali",
    "from_cliente",
    "origine",
    "id_preventivo",
    "id_pratica",
    "area_pratica",
    "procedura_operativa_codice",
    "tipo_compenso",
    "tipo_procedimento",
    "valore_controversia",
    "complessita",
    "log_calcolo",
}
_FISCAL_OPTION_FIELDS = {"applica_iva", "applica_cassa", "applica_ritenuta", "applica_bollo"}
_VOICE_FIELDS = {"descrizione", "quantita", "prezzo_unitario", "tipo"}
_CANONICAL_AMOUNT_FIELDS = {
    "totale",
    "totale_documento",
    "totale_fattura",
    "iva",
    "cassa",
    "cassa_forense",
    "ritenuta",
    "netto",
    "netto_a_pagare",
    "imponibile",
    "base_iva",
    "bollo",
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
        parsed = date.fromisoformat(raw[:10])
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return raw[:10]


def _status_tone(status: str) -> str:
    return {
        "PAGATA": "success",
        "EMESSA": "primary",
        "SCADUTA": "danger",
        "ANNULLATA": "neutral",
        "BOZZA": "warning",
    }.get(status.upper(), "neutral")


def _status_label(status: str) -> str:
    return {
        "PAGATA": "Pagata",
        "EMESSA": "Emessa",
        "SCADUTA": "Scaduta",
        "ANNULLATA": "Annullata",
        "BOZZA": "Bozza",
    }.get(status.upper(), status or "Non indicato")


def _metric(mid: str, label: str, value: Any, note: str, tone: str) -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _action(aid: str, label: str, href: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": aid, "label": label, "href": href, "method": "GET", "tone": tone}


def _option(value: Any, label: str, description: str = "") -> dict[str, Any]:
    return {
        "value": _text(value),
        "label": label,
        "description": description,
        "enabled": True,
    }


def _safe_all(loader: Callable[[], Any], method: str, warnings: list[dict[str, str]], label: str) -> list[Any]:
    try:
        manager = loader()
        func = getattr(manager, method, None)
        if callable(func):
            return list(func())
    except Exception as exc:
        warnings.append({
            "code": f"{label}_non_disponibile",
            "message": f"Sorgente {label} non disponibile: {type(exc).__name__}.",
        })
    return []


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(user and callable(checker) and checker(permission))


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
    return title or rg or "Pratica senza titolo"


def _client_option(cliente: Any) -> dict[str, Any]:
    cid = _text(getattr(cliente, "id", ""))
    fiscal = _text(getattr(cliente, "codice_fiscale", "")) or _text(getattr(cliente, "partita_iva", ""))
    return {
        "id": cid,
        "value": cid,
        "label": _client_label(cliente),
        "description": fiscal,
    }


def _matter_option(fascicolo: Any) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    return {
        "id": fid,
        "value": fid,
        "idCliente": _text(getattr(fascicolo, "id_cliente", "")),
        "label": _case_label(fascicolo),
        "description": _text(getattr(fascicolo, "numero_rg", "")),
    }


def _invoice_record(parcella: Any, clienti: dict[str, Any], fascicoli: dict[str, Any]) -> dict[str, Any]:
    pid = _text(getattr(parcella, "id", ""))
    status = _enum(getattr(parcella, "stato", ""))
    id_cliente = _text(getattr(parcella, "id_cliente", ""))
    id_fascicolo = _text(getattr(parcella, "id_fascicolo", ""))
    return {
        "id": pid,
        "number": _text(getattr(parcella, "numero", "")) or pid,
        "customerName": _client_label(clienti.get(id_cliente)),
        "caseTitle": _case_label(fascicoli.get(id_fascicolo)) if id_fascicolo else "",
        "amountDisplay": _money(getattr(parcella, "totale", 0)),
        "issuedAt": _date_label(getattr(parcella, "data_emissione", "")),
        "dueAt": _date_label(getattr(parcella, "data_scadenza", "")),
        "paidAt": _date_label(getattr(parcella, "data_pagamento", "")),
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
        "paymentMethod": _text(getattr(parcella, "metodo_pagamento", "")),
        "detailHref": f"/fatturazione/{pid}" if pid else "",
        "pdfHref": f"/fatturazione/{pid}/pdf" if pid else "",
        "xmlHref": f"/fatturazione/{pid}/xml" if pid else "",
    }


def _created_item(parcella: Any) -> dict[str, Any]:
    pid = _text(getattr(parcella, "id", ""))
    status = _enum(getattr(parcella, "stato", ""))
    return {
        "id": pid,
        "number": _text(getattr(parcella, "numero", "")) or pid,
        "amountDisplay": _money(getattr(parcella, "totale", 0)),
        "issuedAt": _date_label(getattr(parcella, "data_emissione", "")),
        "dueAt": _date_label(getattr(parcella, "data_scadenza", "")),
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
    }


def _technical_archive_writes() -> str:
    return "legacy_" + "routes"


def _contracts(route: str) -> dict[str, Any]:
    if route == "/fatturazione/nuova":
        return {
            "mock_fallback": False,
            "writes": "json_api",
            "route_owner": "react_shell",
            "operational": True,
            "canonical_calculation": "backend",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/fatturazione__nuova.json",
        }
    return {
        "mock_fallback": False,
        "writes": "json_api",
        "route_owner": "react_shell",
        "operational": True,
        "canonical_calculation": "backend",
        "document_generation": "backend_legacy",
        "legacy_contract": "artifacts/react-migration/legacy-contracts/fatturazione.json",
    }


def _hidden_defaults(query: dict[str, Any] | None, preventivo: Any | None) -> dict[str, str]:
    args = query or {}
    hidden = {
        "from_cliente": _text(args.get("from_cliente")),
        "origine": _text(args.get("origine")) or ("preventivo" if preventivo else ""),
        "id_preventivo": _text(args.get("id_preventivo") or getattr(preventivo, "id", "")),
        "id_pratica": _text(args.get("id_pratica") or getattr(preventivo, "id_pratica", "")),
        "area_pratica": _text(args.get("area_pratica") or getattr(preventivo, "area_pratica", "")),
        "procedura_operativa_codice": _text(args.get("procedura_operativa_codice")),
        "tipo_compenso": _text(args.get("tipo_compenso") or getattr(preventivo, "tipo_compenso", "")),
        "tipo_procedimento": _text(args.get("tipo_procedimento") or getattr(preventivo, "tipo_procedimento", "")),
        "valore_controversia": _text(args.get("valore_controversia") or getattr(preventivo, "valore_controversia", "")),
        "complessita": _text(args.get("complessita") or getattr(preventivo, "complessita", "")),
        "log_calcolo": _text(args.get("log_calcolo") or getattr(preventivo, "log_calcolo", "")),
    }
    return {key: value for key, value in hidden.items() if value}


def _initial_voices(query: dict[str, Any] | None) -> list[dict[str, str]]:
    args = query or {}
    raw_rows = _text(args.get("voci_json"))
    rows: list[dict[str, str]] = []
    if raw_rows:
        try:
            parsed = json.loads(raw_rows)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = []
        if isinstance(parsed, list):
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                description = _text(item.get("descrizione"), limit=240)
                if not description:
                    continue
                rows.append({
                    "descrizione": description,
                    "quantita": _text(item.get("quantita")) or "1",
                    "prezzo_unitario": _text(item.get("prezzo_unitario") or item.get("importo")),
                    "tipo": _text(item.get("tipo")) or "ONORARIO",
                })
    if rows:
        return rows
    return [{
        "descrizione": _text(args.get("descrizione"), limit=240),
        "quantita": _text(args.get("quantita")) or "1",
        "prezzo_unitario": _text(args.get("importo")),
        "tipo": _text(args.get("tipo")) or "ONORARIO",
    }]


def _bool_from_query(args: dict[str, Any], name: str, default: bool) -> bool:
    if name not in args:
        return default
    return _text(args.get(name)).lower() not in {"0", "false", "no", "off"}


def _get_preventivo(get_preventivi: Callable[[], Any] | None, query: dict[str, Any] | None) -> Any | None:
    if not get_preventivi:
        return None
    preventivo_id = _text((query or {}).get("id_preventivo"))
    if not preventivo_id:
        return None
    try:
        manager = get_preventivi()
        getter = getattr(manager, "get_preventivo", None)
        if callable(getter):
            return getter(preventivo_id)
    except Exception:
        return None
    return None


def _new_form_payload(
    *,
    clienti: list[Any],
    fascicoli: list[Any],
    query: dict[str, Any] | None,
    preventivo: Any | None,
    current_user: Any,
) -> dict[str, Any]:
    args = query or {}
    today = date.today()
    due = today + timedelta(days=30)
    id_cliente = _text(args.get("id_cliente") or args.get("from_cliente") or getattr(preventivo, "id_cliente", ""))
    id_fascicolo = _text(args.get("id_fascicolo") or getattr(preventivo, "id_fascicolo", ""))
    defaults = {
        "id_cliente": id_cliente,
        "id_fascicolo": id_fascicolo,
        "data_emissione": today.isoformat(),
        "data_scadenza": due.isoformat(),
        "note": _text(args.get("note") or getattr(preventivo, "note", ""), limit=2000),
        "voci": _initial_voices(query),
        "opzioni_fiscali": {
            "applica_iva": _bool_from_query(args, "applica_iva", getattr(preventivo, "applica_iva", True)),
            "applica_cassa": _bool_from_query(args, "applica_cassa", getattr(preventivo, "applica_cassa", True)),
            "applica_ritenuta": _bool_from_query(args, "applica_ritenuta", False),
            "applica_bollo": _bool_from_query(args, "applica_bollo", False),
        },
        "hidden": _hidden_defaults(query, preventivo),
    }
    return {
        "id": "nuova_parcella",
        "title": "Nuova parcella",
        "description": "La pagina invia i dati controllati; numerazione e calcolo fiscale definitivo restano nei servizi fatturazione.",
        "readHref": "/api/v1/ui/fatturazione/nuova",
        "saveHref": "/api/v1/ui/fatturazione/nuova",
        "submitLabel": "Crea parcella",
        "enabled": _can(current_user, "fatturazione.scrivi"),
        "defaults": defaults,
        "hidden": defaults["hidden"],
    }


def _fiscal_options(defaults: dict[str, Any]) -> list[dict[str, Any]]:
    opts = defaults.get("opzioni_fiscali", {}) if isinstance(defaults, dict) else {}
    labels = {
        "applica_cassa": "Cassa Forense",
        "applica_iva": "IVA",
        "applica_ritenuta": "Ritenuta d'acconto",
        "applica_bollo": "Bollo",
    }
    return [
        {
            "name": name,
            "label": label,
            "default": bool(opts.get(name)),
            "description": "Opzione usata dai servizi per il calcolo definitivo.",
        }
        for name, label in labels.items()
    ]


def _actions_for(route: str, current_user: Any) -> list[dict[str, Any]]:
    if route == "/fatturazione/nuova":
        return [
            {"id": "save", "label": "Crea parcella", "href": "/api/v1/ui/fatturazione/nuova", "method": "POST", "tone": "primary", "enabled": _can(current_user, "fatturazione.scrivi")},
            {"id": "archive", "label": "Archivio fatturazione", "href": "/fatturazione", "method": "GET", "tone": "neutral", "enabled": True},
            {"id": "recupero", "label": "Percorso di recupero", "href": "/fatturazione/nuova?_legacy=1", "method": "GET", "tone": "warning", "enabled": True},
        ]
    return [
        _action("nuova", "Nuova parcella", "/fatturazione/nuova", "primary"),
        _action("export", "Esporta CSV", "/export/fatturazione.csv", "neutral"),
        _action("recupero", "Percorso di recupero", "/fatturazione?_legacy=1", "warning"),
    ]


def build_react_fatturazione_payload(
    *,
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_preventivi: Callable[[], Any] | None = None,
    current_user: Any = None,
    query: dict[str, Any] | None = None,
    route: str = "/fatturazione",
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        {
            "code": "documenti_presidiati",
            "message": "PDF, XML ed export restano nei percorsi auditabili; stato e dettaglio sintetico sono consultabili dalla pagina.",
        },
        {
            "code": "calcolo_presidiato",
            "message": "La pagina non determina totali fiscali definitivi: il risultato finale resta nel modulo fatturazione.",
        },
    ]
    if route == "/fatturazione/nuova" and not _can(current_user, "fatturazione.scrivi"):
        warnings.append({
            "code": "permesso_creazione_mancante",
            "message": "L'utente corrente puo' consultare la pagina ma non creare parcelle.",
        })

    anno = date.today().year
    stats: dict[str, Any] = {}
    parcelle: list[Any] = []
    try:
        manager = get_fatturazione()
        stats = manager.statistiche(anno) if callable(getattr(manager, "statistiche", None)) else {}
        parcelle = list(manager.tutte()) if callable(getattr(manager, "tutte", None)) else []
    except Exception as exc:
        warnings.append({
            "code": "fatturazione_non_disponibile",
            "message": f"Archivio fatturazione non disponibile: {type(exc).__name__}.",
        })

    clienti_list = _safe_all(get_clienti, "tutti", warnings, "clienti")
    fascicoli_list = _safe_all(get_fascicoli, "tutti", warnings, "fascicoli")
    preventivo = _get_preventivo(get_preventivi, query)
    clienti = {_text(getattr(cliente, "id", "")): cliente for cliente in clienti_list}
    fascicoli = {_text(getattr(fascicolo, "id", "")): fascicolo for fascicolo in fascicoli_list}
    records = [_invoice_record(item, clienti, fascicoli) for item in parcelle[:120]]
    state_items: list[dict[str, Any]] = []
    for code in ("BOZZA", "EMESSA", "PAGATA", "SCADUTA", "ANNULLATA"):
        count = len([record for record in records if record["state"] == code])
        state_items.append(_item(code.lower(), _status_label(code), count, "Conteggio archivio corrente", _status_tone(code)))

    form = _new_form_payload(
        clienti=clienti_list,
        fascicoli=fascicoli_list,
        query=query,
        preventivo=preventivo,
        current_user=current_user,
    )
    defaults = form["defaults"]
    payload = {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(route),
        "form": form,
        "clients": [_client_option(cliente) for cliente in clienti_list],
        "matters": [_matter_option(fascicolo) for fascicolo in fascicoli_list],
        "defaults": defaults,
        "fiscal_options": _fiscal_options(defaults),
        "actions": _actions_for(route, current_user),
        "warnings": warnings,
        "metrics": [
            _metric("fatturato", "Fatturato anno", _money(stats.get("fatturato_lordo", 0)), f"Anno {stats.get('anno', anno)}", "primary"),
            _metric("incassato", "Incassato", _money(stats.get("incassato", 0)), "Valori dal servizio fatturazione", "success"),
            _metric("da_incassare", "Da incassare", _money(stats.get("da_incassare", 0)), "Parcelle emesse non saldate", "warning"),
            _metric("scaduto", "Scaduto", _money(stats.get("scaduto", 0)), "Parcelle gia' marcate scadute dal servizio", "danger" if stats.get("scaduto", 0) else "neutral"),
        ],
        "sections": [
            _section("stati", "Stato parcelle", "distribution", state_items, "Nessuna parcella nell'archivio."),
            _section(
                "funzioni_presidiate",
                "Funzioni conservate",
                "presidi",
                [
                    _item("dettaglio", "Dettaglio parcella", "consultabile", "Sintesi sicura letta dal servizio", "info"),
                    _item("pdf", "PDF", "presidiato", "Generazione e download restano nel percorso dedicato", "warning"),
                    _item("xml", "XML FatturaPA", "presidiato", "Produzione XML nel percorso dedicato", "warning"),
                    _item("export", "Export CSV", "presidiato", "Download servito dal percorso di esportazione", "warning"),
                ],
                "Nessuna funzione presidiata rilevata.",
            ),
        ],
        "records": records,
        "documents": records,
        "statuses": [
            {"value": code, "label": _status_label(code), "tone": _status_tone(code)}
            for code in ("BOZZA", "EMESSA", "PAGATA", "SCADUTA", "ANNULLATA")
        ],
        "permissions": {
            "canCreate": _can(current_user, "fatturazione.scrivi"),
            "canUpdateStatus": _can(current_user, "fatturazione.scrivi"),
            "canArchive": False,
            "canCancel": _can(current_user, "fatturazione.scrivi"),
            "canMarkPaid": _can(current_user, "fatturazione.scrivi"),
            "canDownloadPdf": True,
            "canDownloadXml": True,
            "canExport": True,
        },
        "forms": [form],
    }
    return payload


def _error_contract(route: str) -> dict[str, Any]:
    return _contracts(route)


def build_react_fatturazione_error_payload(
    message: str = "Fatturazione non disponibile.",
    *,
    route: str = "/fatturazione",
) -> dict[str, Any]:
    form = _new_form_payload(clienti=[], fascicoli=[], query={}, preventivo=None, current_user=None)
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _error_contract(route),
        "form": form,
        "clients": [],
        "matters": [],
        "defaults": form["defaults"],
        "fiscal_options": _fiscal_options(form["defaults"]),
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": _actions_for(route, None),
        "forms": [],
        "warnings": [{"code": "fatturazione_errore_controllato", "message": message}],
    }


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


def _unknown_fields(payload: dict[str, Any], allowed: set[str]) -> set[str]:
    return {key for key in payload if key not in allowed}


def _reject_canonical_fields(payload: dict[str, Any], errors: dict[str, str], prefix: str = "") -> None:
    for field in sorted(_CANONICAL_AMOUNT_FIELDS & set(payload.keys())):
        key = f"{prefix}{field}" if prefix else field
        errors[key] = "Importo canonico non accettato dal frontend."


def _validate_voices(raw_voices: Any, errors: dict[str, str]) -> list[VoceParcella]:
    if not isinstance(raw_voices, list):
        errors["voci"] = "Aggiungi almeno una voce."
        return []
    voices: list[VoceParcella] = []
    for index, raw_item in enumerate(raw_voices):
        field_prefix = f"voci.{index}."
        if not isinstance(raw_item, dict):
            errors[f"voci.{index}"] = "Voce non valida."
            continue
        unknown = _unknown_fields(raw_item, _VOICE_FIELDS)
        if unknown:
            errors[f"voci.{index}"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
        _reject_canonical_fields(raw_item, errors, prefix=field_prefix)
        description = _text(raw_item.get("descrizione"), limit=240)
        if not description:
            errors[f"{field_prefix}descrizione"] = "Descrizione obbligatoria."
        quantity = _as_number(raw_item.get("quantita"), f"{field_prefix}quantita", errors, minimum=0.01, default=1.0)
        unit_price = _as_number(raw_item.get("prezzo_unitario"), f"{field_prefix}prezzo_unitario", errors, minimum=0.0, default=0.0)
        raw_type = _text(raw_item.get("tipo") or "ONORARIO", limit=40)
        if raw_type and raw_type not in {"ONORARIO", "SPESE", "ANTICIPO", "ALTRO"}:
            errors[f"{field_prefix}tipo"] = "Tipo voce non consentito."
        if description:
            voices.append(VoceParcella(descrizione=description, quantita=quantity, prezzo_unitario=unit_price))
    if not voices and "voci" not in errors:
        errors["voci"] = "Aggiungi almeno una voce valida."
    return voices


def _validate_payload(
    payload: dict[str, Any],
    *,
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}
    unknown = _unknown_fields(payload, _TOP_LEVEL_FIELDS)
    if unknown:
        errors["payload"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
    _reject_canonical_fields(payload, errors)

    id_cliente = _text(payload.get("id_cliente"))
    id_fascicolo = _text(payload.get("id_fascicolo"))
    if not id_cliente:
        errors["id_cliente"] = "Seleziona un cliente."
    try:
        cliente = get_clienti().get(id_cliente) if id_cliente else None
    except Exception:
        cliente = None
    if id_cliente and not cliente:
        errors["id_cliente"] = "Cliente non trovato."

    fascicolo = None
    if id_fascicolo:
        try:
            fascicolo = get_fascicoli().get(id_fascicolo)
        except Exception:
            fascicolo = None
        if not fascicolo:
            errors["id_fascicolo"] = "Fascicolo non trovato."
        elif _text(getattr(fascicolo, "id_cliente", "")) and _text(getattr(fascicolo, "id_cliente", "")) != id_cliente:
            errors["id_fascicolo"] = "Il fascicolo non appartiene al cliente selezionato."

    issued_at = _as_date(payload.get("data_emissione"), "data_emissione", errors, required=True)
    due_at = _as_date(payload.get("data_scadenza"), "data_scadenza", errors, required=True)
    if issued_at and due_at and due_at < issued_at:
        errors["data_scadenza"] = "La scadenza non puo' precedere la data di emissione."

    raw_options = payload.get("opzioni_fiscali") or {}
    if not isinstance(raw_options, dict):
        errors["opzioni_fiscali"] = "Opzioni fiscali non valide."
        raw_options = {}
    option_unknown = _unknown_fields(raw_options, _FISCAL_OPTION_FIELDS)
    if option_unknown:
        errors["opzioni_fiscali"] = "Campi non consentiti: " + ", ".join(sorted(option_unknown))
    _reject_canonical_fields(raw_options, errors, prefix="opzioni_fiscali.")

    voices = _validate_voices(payload.get("voci"), errors)
    value_controversy = _as_number(
        payload.get("valore_controversia"),
        "valore_controversia",
        errors,
        minimum=0.0,
        default=0.0,
    )
    validated = {
        "id_cliente": id_cliente,
        "id_fascicolo": id_fascicolo or None,
        "data_emissione": issued_at,
        "data_scadenza": due_at,
        "voci": voices,
        "note": _text(payload.get("note"), limit=2000),
        "applica_iva": _as_bool(raw_options.get("applica_iva"), True),
        "applica_cassa": _as_bool(raw_options.get("applica_cassa"), True),
        "applica_ritenuta": _as_bool(raw_options.get("applica_ritenuta"), False),
        "applica_bollo": _as_bool(raw_options.get("applica_bollo"), False),
        "from_cliente": _text(payload.get("from_cliente")),
        "origine": _text(payload.get("origine"), limit=80),
        "id_preventivo": _text(payload.get("id_preventivo")) or None,
        "id_pratica": _text(payload.get("id_pratica")),
        "area_pratica": _text(payload.get("area_pratica"), limit=120),
        "procedura_operativa_codice": _text(payload.get("procedura_operativa_codice"), limit=120),
        "tipo_compenso": _text(payload.get("tipo_compenso"), limit=120),
        "tipo_procedimento": _text(payload.get("tipo_procedimento"), limit=120),
        "valore_controversia": value_controversy,
        "complessita": _text(payload.get("complessita"), limit=80),
        "log_calcolo": _text(payload.get("log_calcolo")) or None,
    }
    return validated, errors


def _preventivo_log(get_preventivi: Callable[[], Any] | None, preventivo_id: str | None) -> str | None:
    if not get_preventivi or not preventivo_id:
        return None
    try:
        manager = get_preventivi()
        getter = getattr(manager, "get_preventivo", None)
        preventivo = getter(preventivo_id) if callable(getter) else None
    except Exception:
        preventivo = None
    return _text(getattr(preventivo, "log_calcolo", "")) or None


def _audit_create(get_utenti: Callable[[], Any], current_user: Any, parcella: Any, ip_address: str) -> None:
    try:
        manager = get_utenti()
        registrar = getattr(manager, "registra_evento", None)
        if not callable(registrar):
            return
        registrar(
            "fatturazione.crea",
            id_utente=_text(getattr(current_user, "id", "")),
            username=_text(getattr(current_user, "username", "")),
            risorsa_tipo="parcella",
            risorsa_id=_text(getattr(parcella, "id", "")),
            dettagli=(
                f"numero={_text(getattr(parcella, 'numero', ''))}; "
                f"cliente={_text(getattr(parcella, 'id_cliente', ''))}; "
                "origine=react_operational_full"
            ),
            ip=ip_address,
            esito="OK",
        )
    except Exception:
        return


def create_react_fattura(
    *,
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_utenti: Callable[[], Any],
    get_preventivi: Callable[[], Any] | None,
    current_user: Any,
    payload: dict[str, Any],
    config: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }, 403

    validated, errors = _validate_payload(payload, get_clienti=get_clienti, get_fascicoli=get_fascicoli)
    if errors:
        return {
            "ok": False,
            "message": "Controlla i campi evidenziati.",
            "errors": errors,
            "item": None,
        }, 400

    log_calcolo = validated["log_calcolo"] or _preventivo_log(get_preventivi, validated["id_preventivo"])
    try:
        manager = get_fatturazione()
        parcella = manager.crea(
            id_cliente=validated["id_cliente"],
            voci=validated["voci"],
            creato_da=_text(getattr(current_user, "username", "")),
            id_fascicolo=validated["id_fascicolo"],
            data_emissione=validated["data_emissione"],
            data_scadenza=validated["data_scadenza"],
            applica_iva=validated["applica_iva"],
            applica_cassa=validated["applica_cassa"],
            applica_ritenuta=validated["applica_ritenuta"],
            applica_bollo=validated["applica_bollo"],
            note=validated["note"],
            origine=validated["origine"],
            id_preventivo=validated["id_preventivo"],
            id_pratica=validated["id_pratica"],
            area_pratica=validated["area_pratica"],
            procedura_operativa_codice=validated["procedura_operativa_codice"],
            tipo_compenso=validated["tipo_compenso"],
            tipo_procedimento=validated["tipo_procedimento"],
            valore_controversia=validated["valore_controversia"],
            complessita=validated["complessita"],
            log_calcolo=log_calcolo,
            studio_piva=_text(config.get("STUDIO_PIVA")),
            studio_cf=_text(config.get("STUDIO_CF")),
            studio_indirizzo=_text(config.get("STUDIO_INDIRIZZO")),
            studio_iban=_text(config.get("STUDIO_IBAN")),
        )
    except ValueError as exc:
        return {
            "ok": False,
            "message": "Creazione non completata.",
            "errors": {"payload": _text(exc) or "Dati non validi."},
            "item": None,
        }, 400

    _audit_create(get_utenti, current_user, parcella, ip_address)
    redirect_href = (
        f"/clienti/{validated['from_cliente']}" if validated["from_cliente"]
        else f"/fatturazione/{_text(getattr(parcella, 'id', ''))}?_legacy=1"
    )
    return {
        "ok": True,
        "message": f"Parcella {_text(getattr(parcella, 'numero', ''))} creata.",
        "errors": {},
        "item": _created_item(parcella),
        "redirect_href": redirect_href,
    }, 200
