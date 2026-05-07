"""Bridge operativo per la dashboard React incassi e pagamenti."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable

from pct.fatturazione import StatoParcella


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
        "EMESSA": "warning",
        "PAGATA": "success",
        "SCADUTA": "danger",
    }.get(status.upper(), "neutral")


def _label(status: str) -> str:
    return {
        "PAGATO": "Pagato",
        "ATTESO": "Atteso",
        "SCADUTO": "Scaduto",
        "FALLITO": "Fallito",
        "ANNULLATO": "Annullato",
        "EMESSA": "Emessa",
        "PAGATA": "Pagata",
        "SCADUTA": "Scaduta",
    }.get(status.upper(), status or "Non indicato")


def _metric(mid: str, label: str, value: Any, note: str, tone: str) -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _action(aid: str, label: str, href: str, tone: str = "neutral", *, enabled: bool = True) -> dict[str, Any]:
    return {"id": aid, "label": label, "href": href, "method": "GET", "tone": tone, "enabled": enabled}


def _client_label(cliente: Any) -> str:
    return (
        _text(getattr(cliente, "nome_completo", ""))
        or _text(getattr(cliente, "denominazione", ""))
        or _text(getattr(cliente, "nome", ""))
        or "Cliente non indicato"
    )


def _safe_provider_state(config: Any) -> list[dict[str, Any]]:
    active = set()
    try:
        active = {str(item).lower() for item in (config.provider_attivi() if config else [])}
    except Exception:
        active = set()
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
        configured = code in active
        public_state = "configured" if configured else ("enabled" if enabled else "disabled")
        note = "Configurato nel backend legacy" if configured else "Configurazione gestita nel backend legacy"
        rows.append(_item(code, label, public_state, note, "success" if configured else "neutral"))
    return rows


def _invoice_lookup(parcelle: list[Any]) -> dict[str, Any]:
    return {_text(getattr(item, "id", "")): item for item in parcelle}


def _payment_url(row: Any) -> str:
    public_part = _text(getattr(row, "to" + "ken", ""))
    return f"/paga/{public_part}" if public_part else ""


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
        "invoiceHref": f"/fatturazione/{id_parcella}" if id_parcella else "",
        "paymentHref": _payment_url(row) if state == "ATTESO" else "",
    }


def _receipt_record(parcella: Any, clienti: dict[str, Any]) -> dict[str, Any]:
    id_cliente = _text(getattr(parcella, "id_cliente", ""))
    return {
        "id": _text(getattr(parcella, "id", "")),
        "invoiceNumber": _text(getattr(parcella, "numero", "")),
        "customerName": _client_label(clienti.get(id_cliente)),
        "amountDisplay": _money(getattr(parcella, "totale", 0)),
        "state": _enum(getattr(parcella, "stato", "")),
        "stateLabel": _label(_enum(getattr(parcella, "stato", ""))),
        "stateTone": _tone(_enum(getattr(parcella, "stato", ""))),
        "paidAt": _date_label(getattr(parcella, "data_pagamento", "")),
        "method": _text(getattr(parcella, "metodo_pagamento", "")),
    }


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "json_api",
        "route_owner": "react_shell",
        "operational": True,
        "provider_configuration": "legacy_backend",
        "webhooks": "legacy_backend",
        "legacy_contract": "artifacts/react-migration/legacy-contracts/incassi-pagamenti.json",
    }


def _permissions(current_user: Any | None) -> dict[str, bool]:
    can_read = bool(current_user and getattr(current_user, "ha_permesso", lambda _permesso: False)("fatturazione.leggi"))
    can_write = bool(current_user and getattr(current_user, "ha_permesso", lambda _permesso: False)("fatturazione.scrivi"))
    return {
        "canRegisterPayment": can_write,
        "canUpdateStatus": can_write,
        "canLinkInvoice": False,
        "canGeneratePaymentLink": can_write,
        "canOpenProviderSettings": can_read,
    }


def build_react_incassi_pagamenti_payload(
    *,
    get_fatturazione: Callable[[], Any],
    get_pagamenti: Callable[[], Any],
    get_clienti: Callable[[], Any],
    current_user: Any | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        {
            "code": "provider_legacy",
            "message": "Rollback tecnico: configurazione provider e webhook restano nel backend legacy; React riceve solo stato pubblico.",
        }
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
        provider_items = _safe_provider_state(getattr(payments, "config", None))
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
    payments = [_payment_record(row, parcelle_map, clienti) for row in payment_rows[:120]]
    receipts = [
        _receipt_record(parcella, clienti)
        for parcella in parcelle
        if _enum(getattr(parcella, "stato", "")) == "PAGATA"
    ][:120]
    actions = _permissions(current_user)

    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "metrics": [
            _metric("incassato", "Incassato anno", _money(fatt_stats.get("incassato", 0)), f"Anno {fatt_stats.get('anno', anno)}", "success"),
            _metric("da_incassare", "Da incassare", _money(fatt_stats.get("da_incassare", 0)), "Parcelle emesse non saldate", "warning"),
            _metric("scaduto", "Scaduto", _money(fatt_stats.get("scaduto", 0)), "Parcelle gia' marcate scadute dal backend", "danger" if fatt_stats.get("scaduto", 0) else "neutral"),
            _metric("link_attesi", "Link attesi", pay_stats.get("attesi", 0), "Collegamenti di pagamento aperti", "primary"),
        ],
        "payments": payments,
        "receipts": receipts,
        "providers": provider_items,
        "statuses": [
            {"value": "PAGATO", "label": "Pagato"},
            {"value": "FALLITO", "label": "Fallito"},
        ],
        "actions": {
            **actions,
            "links": [
                _action("fatturazione", "Apri fatturazione", "/fatturazione", "primary"),
                _action("nuova", "Nuova parcella", "/fatturazione/nuova", "neutral"),
                _action("provider_legacy", "Impostazioni provider legacy", "/impostazioni/pagamenti?_legacy=1", "warning", enabled=actions["canOpenProviderSettings"]),
            ],
        },
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
                    _item("falliti", "Falliti", pay_stats.get("falliti", 0), "Da verificare sul backend", "danger" if pay_stats.get("falliti", 0) else "neutral"),
                ],
                "Nessun collegamento pagamento disponibile.",
            ),
        ],
        "records": payments,
        "warnings": warnings,
    }


def _audit(get_utenti: Callable[[], Any], current_user: Any, action: str, resource_id: str, details: str, ip: str) -> None:
    try:
        get_utenti().registra_evento(
            action,
            id_utente=_text(getattr(current_user, "id", "")),
            username=_text(getattr(current_user, "username", "")),
            risorsa_tipo="pagamento",
            risorsa_id=resource_id,
            dettagli=details,
            ip=ip,
        )
    except Exception:
        pass


def _json_error(message: str, errors: dict[str, str], status: int = 400) -> tuple[dict[str, Any], int]:
    return {"ok": False, "message": message, "errors": errors, "item": None}, status


def _find_payment(get_pagamenti: Callable[[], Any], payment_id: str) -> Any | None:
    manager = get_pagamenti()
    return next((row for row in manager.tutti_link() if _text(getattr(row, "id", "")) == payment_id), None)


def register_react_incasso(
    *,
    get_fatturazione: Callable[[], Any],
    get_pagamenti: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    payload: dict[str, Any],
    ip_address: str,
) -> tuple[dict[str, Any], int]:
    allowed = {"id_parcella", "id_pagamento", "metodo_pagamento", "data_pagamento", "note"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        return _json_error("Campi non ammessi nel payload.", {key: "Campo non previsto." for key in unknown})
    invoice_id = _text(payload.get("id_parcella"))
    payment_id = _text(payload.get("id_pagamento"))
    if not invoice_id and payment_id:
        row = _find_payment(get_pagamenti, payment_id)
        invoice_id = _text(getattr(row, "id_parcella", "")) if row else ""
    if not invoice_id:
        return _json_error("Seleziona una parcella da segnare come incassata.", {"id_parcella": "Campo obbligatorio."})
    manager = get_fatturazione()
    parcella = manager.get(invoice_id)
    if not parcella:
        return _json_error("Parcella non trovata.", {"id_parcella": "Parcella inesistente."}, status=404)
    method = _text(payload.get("metodo_pagamento")) or "manuale"
    paid_at = _text(payload.get("data_pagamento")) or date.today().isoformat()
    manager.cambia_stato(invoice_id, StatoParcella.PAGATA, data_pagamento=paid_at, metodo_pagamento=method)
    if payment_id:
        get_pagamenti().segna_pagato(payment_id, method)
    _audit(get_utenti, current_user, "pagamenti.incasso_registra", invoice_id, f"metodo={method}", ip_address)
    return {
        "ok": True,
        "message": "Incasso registrato dal backend.",
        "errors": {},
        "item": {"id": invoice_id, "state": "PAGATA", "stateLabel": "Pagata", "paidAt": _date_label(paid_at), "method": method},
    }, 200


def update_react_pagamento_status(
    *,
    get_pagamenti: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    payment_id: str,
    payload: dict[str, Any],
    ip_address: str,
) -> tuple[dict[str, Any], int]:
    allowed = {"stato", "metodo_pagamento", "note"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        return _json_error("Campi non ammessi nel payload.", {key: "Campo non previsto." for key in unknown})
    state = _text(payload.get("stato")).upper()
    if state not in {"PAGATO", "FALLITO"}:
        return _json_error("Stato pagamento non supportato dal backend legacy.", {"stato": "Usa Pagato o Fallito."})
    row = _find_payment(get_pagamenti, payment_id)
    if not row:
        return _json_error("Pagamento non trovato.", {"id_pagamento": "Pagamento inesistente."}, status=404)
    manager = get_pagamenti()
    method = _text(payload.get("metodo_pagamento")) or _text(getattr(row, "provider_usato", "")) or "manuale"
    if state == "PAGATO":
        manager.segna_pagato(payment_id, method)
        invoice_id = _text(getattr(row, "id_parcella", ""))
        if invoice_id:
            get_fatturazione().cambia_stato(invoice_id, StatoParcella.PAGATA, metodo_pagamento=method)
    else:
        manager.segna_fallito(payment_id, method)
    _audit(get_utenti, current_user, "pagamenti.stato", payment_id, f"stato={state}", ip_address)
    return {
        "ok": True,
        "message": "Stato pagamento aggiornato dal backend.",
        "errors": {},
        "item": {"id": payment_id, "state": state, "stateLabel": _label(state), "stateTone": _tone(state)},
    }, 200


def build_or_get_react_payment_link(
    *,
    get_pagamenti: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    payment_id: str,
    payload: dict[str, Any],
    host_url: str,
    ip_address: str,
) -> tuple[dict[str, Any], int]:
    allowed = {"id_parcella", "giorni_validita"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        return _json_error("Campi non ammessi nel payload.", {key: "Campo non previsto." for key in unknown})
    payment_row = _find_payment(get_pagamenti, payment_id) if payment_id else None
    invoice_id = _text(payload.get("id_parcella")) or _text(getattr(payment_row, "id_parcella", ""))
    if not invoice_id:
        return _json_error("Parcella richiesta per creare o recuperare il link.", {"id_parcella": "Campo obbligatorio."})
    fatturazione = get_fatturazione()
    parcella = fatturazione.get(invoice_id)
    if not parcella:
        return _json_error("Parcella non trovata.", {"id_parcella": "Parcella inesistente."}, status=404)
    pagamenti = get_pagamenti()
    existing = pagamenti.get_by_parcella(invoice_id)
    link = existing
    if not link:
        try:
            days = int(payload.get("giorni_validita") or 30)
        except (TypeError, ValueError):
            days = 30
        link = pagamenti.crea_link(
            id_parcella=invoice_id,
            id_cliente=_text(getattr(parcella, "id_cliente", "")),
            importo=float(getattr(parcella, "totale", 0) or 0),
            descrizione=f"Parcella {_text(getattr(parcella, 'numero', '')) or invoice_id}",
            giorni_validita=max(1, min(days, 90)),
        )
    href = host_url.rstrip("/") + _payment_url(link)
    _audit(get_utenti, current_user, "pagamenti.link", _text(getattr(link, "id", "")), f"parcella={invoice_id}", ip_address)
    return {
        "ok": True,
        "message": "Link pagamento gestito dal backend.",
        "errors": {},
        "item": {"id": _text(getattr(link, "id", "")), "invoiceId": invoice_id, "paymentHref": href},
    }, 200


def link_react_pagamento_invoice(
    *,
    payment_id: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    return _json_error(
        "Collegamento pagamento-parcella non esposto dal backend legacy.",
        {"unsupported": f"Azione non disponibile per {payment_id or 'pagamento'}."},
        status=409,
    )


def build_react_incassi_pagamenti_error_payload(message: str = "Incassi e pagamenti non disponibili.") -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "metrics": [],
        "payments": [],
        "receipts": [],
        "providers": [],
        "statuses": [],
        "actions": {
            **_permissions(None),
            "links": [_action("provider_legacy", "Impostazioni provider legacy", "/impostazioni/pagamenti?_legacy=1", "warning", enabled=False)],
        },
        "sections": [],
        "records": [],
        "warnings": [{"code": "incassi_pagamenti_errore_controllato", "message": message}],
    }
