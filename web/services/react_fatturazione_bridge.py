"""Bridge read-only per le superfici React di fatturazione."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


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
        "detailHref": f"/fatturazione/{pid}?_legacy=1" if pid else "",
        "pdfHref": f"/fatturazione/{pid}/pdf?_legacy=1" if pid else "",
        "xmlHref": f"/fatturazione/{pid}/xml?_legacy=1" if pid else "",
    }


def _form_payload(clienti: list[Any], fascicoli: list[Any], query: dict[str, Any] | None) -> dict[str, Any]:
    args = query or {}
    today = date.today()
    due = today + timedelta(days=30)
    customer_options = [_option("", "Seleziona cliente")]
    customer_options.extend(_option(getattr(cliente, "id", ""), _client_label(cliente)) for cliente in clienti)
    case_options = [_option("", "Nessuna pratica")]
    case_options.extend(_option(getattr(fascicolo, "id", ""), _case_label(fascicolo)) for fascicolo in fascicoli)

    hidden_fields = [
        "from_cliente",
        "origine",
        "id_preventivo",
        "id_pratica",
        "area_pratica",
        "tipo_compenso",
        "tipo_procedimento",
        "valore_controversia",
        "complessita",
        "log_calcolo",
    ]

    fields: list[dict[str, Any]] = [
        {
            "name": "id_cliente",
            "label": "Cliente",
            "type": "select",
            "required": True,
            "value": _text(args.get("id_cliente") or args.get("from_cliente")),
            "options": customer_options,
        },
        {
            "name": "id_fascicolo",
            "label": "Pratica",
            "type": "select",
            "required": False,
            "value": _text(args.get("id_fascicolo")),
            "options": case_options,
        },
    ]
    fields.extend({
        "name": name,
        "label": name,
        "type": "hidden",
        "value": _text(args.get(name)),
    } for name in hidden_fields)

    amount_prefill = _text(args.get("importo"))
    return {
        "id": "nuova_parcella",
        "title": "Nuova parcella",
        "description": "Il form invia al POST legacy: importi finali, imposte, PDF e XML restano calcolati dal backend.",
        "action": "/fatturazione/nuova",
        "method": "POST",
        "submitLabel": "Crea parcella",
        "enabled": True,
        "fields": fields,
        "defaults": {
            "issuedAt": today.isoformat(),
            "dueAt": due.isoformat(),
            "description": _text(args.get("descrizione")),
            "quantity": _text(args.get("quantita")) or "1",
            "unitAmount": amount_prefill,
            "notes": _text(args.get("note")),
            "withFund": _text(args.get("applica_cassa") or "1") != "0",
            "withVat": _text(args.get("applica_iva") or "1") != "0",
            "withWithholding": _text(args.get("applica_ritenuta")) == "1",
            "withStamp": _text(args.get("applica_bollo")) == "1",
        },
    }


def build_react_fatturazione_payload(
    *,
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    query: dict[str, Any] | None = None,
    route: str = "/fatturazione",
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        {
            "code": "documenti_legacy",
            "message": "PDF, XML, export, dettagli avanzati e variazioni di stato restano sulle route legacy auditabili.",
        },
        {
            "code": "calcolo_backend",
            "message": "La shell React non calcola importi fiscali: il risultato canonico resta nel modulo Flask.",
        },
    ]
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
    clienti = {_text(getattr(cliente, "id", "")): cliente for cliente in clienti_list}
    fascicoli = {_text(getattr(fascicolo, "id", "")): fascicolo for fascicolo in fascicoli_list}
    records = [_invoice_record(item, clienti, fascicoli) for item in parcelle[:120]]
    state_items: list[dict[str, Any]] = []
    for code in ("BOZZA", "EMESSA", "PAGATA", "SCADUTA", "ANNULLATA"):
        count = len([record for record in records if record["state"] == code])
        state_items.append(_item(code.lower(), _status_label(code), count, "Conteggio archivio corrente", _status_tone(code)))

    payload = {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/fatturazione.json",
        },
        "metrics": [
            _metric("fatturato", "Fatturato anno", _money(stats.get("fatturato_lordo", 0)), f"Anno {stats.get('anno', anno)}", "primary"),
            _metric("incassato", "Incassato", _money(stats.get("incassato", 0)), "Valori dal servizio fatturazione", "success"),
            _metric("da_incassare", "Da incassare", _money(stats.get("da_incassare", 0)), "Parcelle emesse non saldate", "warning"),
            _metric("scaduto", "Scaduto", _money(stats.get("scaduto", 0)), "Parcelle gia' marcate scadute dal backend", "danger" if stats.get("scaduto", 0) else "neutral"),
        ],
        "sections": [
            _section("stati", "Stato parcelle", "distribution", state_items, "Nessuna parcella nell'archivio."),
            _section(
                "funzioni_legacy",
                "Funzioni conservate",
                "legacy-routes",
                [
                    _item("dettaglio", "Dettaglio parcella", "legacy", "Aperto con parametro tecnico di bypass React", "warning"),
                    _item("pdf", "PDF", "legacy", "Generazione e download restano Flask", "warning"),
                    _item("xml", "XML FatturaPA", "legacy", "Produzione XML fuori dalla shell React", "warning"),
                    _item("export", "Export CSV", "legacy", "Download servito dal blueprint export esistente", "warning"),
                ],
                "Nessuna funzione legacy rilevata.",
            ),
        ],
        "records": records,
        "actions": [
            _action("nuova", "Nuova parcella", "/fatturazione/nuova", "primary"),
            _action("export", "Export CSV legacy", "/export/fatturazione.csv?_legacy=1", "neutral"),
            _action("legacy", "Archivio legacy", "/fatturazione?_legacy=1", "warning"),
        ],
        "forms": [_form_payload(clienti_list, fascicoli_list, query)],
        "warnings": warnings,
    }
    if route == "/fatturazione/nuova":
        payload["contracts"]["legacy_contract"] = "artifacts/react-migration/legacy-contracts/fatturazione__nuova.json"
    return payload


def build_react_fatturazione_error_payload(message: str = "Fatturazione non disponibile.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/fatturazione.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [_action("legacy", "Archivio legacy", "/fatturazione?_legacy=1", "warning")],
        "forms": [],
        "warnings": [{"code": "fatturazione_errore_controllato", "message": message}],
    }
