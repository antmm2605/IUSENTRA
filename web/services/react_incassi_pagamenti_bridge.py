"""Bridge read-only per la dashboard React incassi e pagamenti."""

from __future__ import annotations

from datetime import date, datetime, timezone
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
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        try:
            return date.fromisoformat(raw[:10]).strftime("%d/%m/%Y")
        except ValueError:
            return raw[:16]


def _tone(status: str) -> str:
    return {
        "PAGATO": "success",
        "ATTESO": "warning",
        "SCADUTO": "danger",
        "FALLITO": "danger",
        "ANNULLATO": "neutral",
    }.get(status.upper(), "neutral")


def _label(status: str) -> str:
    return {
        "PAGATO": "Pagato",
        "ATTESO": "Atteso",
        "SCADUTO": "Scaduto",
        "FALLITO": "Fallito",
        "ANNULLATO": "Annullato",
    }.get(status.upper(), status or "Non indicato")


def _metric(mid: str, label: str, value: Any, note: str, tone: str) -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _action(aid: str, label: str, href: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": aid, "label": label, "href": href, "method": "GET", "tone": tone}


def _client_label(cliente: Any) -> str:
    return (
        _text(getattr(cliente, "nome_completo", ""))
        or _text(getattr(cliente, "denominazione", ""))
        or _text(getattr(cliente, "nome", ""))
        or "Cliente non indicato"
    )


def _provider_state(config: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, label in (
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("satispay", "Satispay"),
        ("sumup", "SumUp"),
        ("bonifico", "Bonifico"),
    ):
        section = getattr(config, code, None)
        enabled = bool(getattr(section, "abilitato", False))
        mode = _text(getattr(section, "modo", ""))
        note = f"Modalita {mode}" if mode else "Stato configurazione senza dettagli riservati"
        rows.append(_item(code, label, "abilitato" if enabled else "non abilitato", note, "success" if enabled else "neutral"))
    return rows


def _invoice_lookup(parcelle: list[Any]) -> dict[str, Any]:
    return {_text(getattr(item, "id", "")): item for item in parcelle}


def _payment_record(row: Any, parcelle: dict[str, Any], clienti: dict[str, Any]) -> dict[str, Any]:
    row_id = _text(getattr(row, "id", ""))
    id_parcella = _text(getattr(row, "id_parcella", ""))
    id_cliente = _text(getattr(row, "id_cliente", ""))
    parcella = parcelle.get(id_parcella)
    customer = clienti.get(id_cliente)
    state = _enum(getattr(row, "stato", ""))
    return {
        "id": row_id,
        "invoiceId": id_parcella,
        "invoiceNumber": _text(getattr(parcella, "numero", "")) or id_parcella,
        "customerName": _client_label(customer),
        "amountDisplay": _money(getattr(row, "importo", 0)),
        "state": state,
        "stateLabel": _label(state),
        "stateTone": _tone(state),
        "providerLabel": _text(getattr(row, "provider_usato", "")) or "non indicato",
        "createdAt": _date_label(getattr(row, "creato_il", "")),
        "dueAt": _date_label(getattr(row, "scade_il", "")),
        "paidAt": _date_label(getattr(row, "pagato_il", "")),
        "invoiceHref": f"/fatturazione/{id_parcella}?_legacy=1" if id_parcella else "",
    }


def build_react_incassi_pagamenti_payload(
    *,
    get_fatturazione: Callable[[], Any],
    get_pagamenti: Callable[[], Any],
    get_clienti: Callable[[], Any],
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        {
            "code": "provider_legacy",
            "message": "Configurazione provider, webhook e credenziali restano nel pannello legacy pagamenti.",
        },
        {
            "code": "scritture_legacy",
            "message": "Creazione link, avvio incasso e aggiornamenti di stato restano sulle route Flask esistenti.",
        },
    ]
    anno = date.today().year
    fatt_stats: dict[str, Any] = {}
    parcelle: list[Any] = []
    try:
        fatturazione = get_fatturazione()
        fatt_stats = fatturazione.statistiche(anno) if callable(getattr(fatturazione, "statistiche", None)) else {}
        parcelle = list(fatturazione.tutte()) if callable(getattr(fatturazione, "tutte", None)) else []
    except Exception as exc:
        warnings.append({
            "code": "fatturazione_non_disponibile",
            "message": f"Archivio fatturazione non disponibile: {type(exc).__name__}.",
        })

    pay_stats: dict[str, Any] = {}
    payment_rows: list[Any] = []
    provider_items: list[dict[str, Any]] = []
    try:
        payments = get_pagamenti()
        pay_stats = payments.statistiche() if callable(getattr(payments, "statistiche", None)) else {}
        payment_rows = list(payments.tutti_link()) if callable(getattr(payments, "tutti_link", None)) else []
        provider_items = _provider_state(getattr(payments, "config", None))
    except Exception as exc:
        warnings.append({
            "code": "pagamenti_non_disponibili",
            "message": f"Archivio pagamenti non disponibile: {type(exc).__name__}.",
        })

    try:
        clienti = {_text(getattr(cliente, "id", "")): cliente for cliente in get_clienti().tutti()}
    except Exception as exc:
        warnings.append({
            "code": "clienti_non_disponibili",
            "message": f"Anagrafica clienti non disponibile: {type(exc).__name__}.",
        })
        clienti = {}

    parcelle_map = _invoice_lookup(parcelle)
    records = [_payment_record(row, parcelle_map, clienti) for row in payment_rows[:80]]

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/incassi-pagamenti.json",
        },
        "metrics": [
            _metric("incassato", "Incassato anno", _money(fatt_stats.get("incassato", 0)), f"Anno {fatt_stats.get('anno', anno)}", "success"),
            _metric("da_incassare", "Da incassare", _money(fatt_stats.get("da_incassare", 0)), "Parcelle emesse non saldate", "warning"),
            _metric("scaduto", "Scaduto", _money(fatt_stats.get("scaduto", 0)), "Parcelle gia' marcate scadute dal backend", "danger" if fatt_stats.get("scaduto", 0) else "neutral"),
            _metric("link_attesi", "Link attesi", pay_stats.get("attesi", 0), "Collegamenti di pagamento aperti", "primary"),
        ],
        "sections": [
            _section("provider", "Stato provider", "safe-status", provider_items, "Nessun provider abilitato."),
            _section(
                "link",
                "Riepilogo link pagamento",
                "distribution",
                [
                    _item("totale", "Totale link", pay_stats.get("totale_link", 0), "Archivio collegamenti", "primary"),
                    _item("pagati", "Pagati", pay_stats.get("pagati", 0), _money(pay_stats.get("importo_pagato", 0)), "success"),
                    _item("attesi", "Attesi", pay_stats.get("attesi", 0), _money(pay_stats.get("importo_atteso", 0)), "warning"),
                    _item("falliti", "Falliti", pay_stats.get("falliti", 0), "Da verificare in legacy", "danger" if pay_stats.get("falliti", 0) else "neutral"),
                ],
                "Nessun collegamento pagamento disponibile.",
            ),
        ],
        "records": records,
        "actions": [
            _action("fatturazione", "Apri fatturazione", "/fatturazione", "primary"),
            _action("nuova", "Nuova parcella", "/fatturazione/nuova", "neutral"),
            _action("config", "Configura provider legacy", "/impostazioni/pagamenti?_legacy=1", "warning"),
        ],
        "forms": [],
        "warnings": warnings,
    }


def build_react_incassi_pagamenti_error_payload(message: str = "Incassi e pagamenti non disponibili.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/incassi-pagamenti.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [_action("config", "Configura provider legacy", "/impostazioni/pagamenti?_legacy=1", "warning")],
        "forms": [],
        "warnings": [{"code": "incassi_pagamenti_errore_controllato", "message": message}],
    }
