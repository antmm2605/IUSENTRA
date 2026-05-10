"""Azioni JSON sicure per l'archivio fatturazione React."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable

from pct.fatturazione import StatoParcella

_ALLOWED_STATUS_FIELDS = {"stato", "data_pagamento", "metodo_pagamento", "note"}
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
        return date.fromisoformat(raw[:10]).strftime("%d/%m/%Y")
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


def _safe_all(loader: Callable[[], Any], method: str) -> list[Any]:
    try:
        func = getattr(loader(), method, None)
        if callable(func):
            return list(func())
    except Exception:
        return []
    return []


def _record(parcella: Any, clienti: dict[str, Any], fascicoli: dict[str, Any]) -> dict[str, Any]:
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


def _audit(get_utenti: Callable[[], Any], current_user: Any, action: str, resource_id: str, ip_address: str) -> None:
    try:
        registrar = getattr(get_utenti(), "registra_evento", None)
        if not callable(registrar):
            return
        registrar(
            action,
            id_utente=_text(getattr(current_user, "id", "")),
            username=_text(getattr(current_user, "username", "")),
            risorsa_tipo="parcella",
            risorsa_id=resource_id,
            dettagli="origine=react_operational_full",
            ip=ip_address,
            esito="OK",
        )
    except Exception:
        return


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(user and callable(checker) and checker(permission))


def _safe_payload_fields(payload: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    unknown = {key for key in payload if key not in _ALLOWED_STATUS_FIELDS}
    if unknown:
        errors["payload"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
    for field in sorted(_CANONICAL_AMOUNT_FIELDS & set(payload.keys())):
        errors[field] = "Importo calcolato non accettato dalla pagina."
    return errors


def _status_result(item: Any) -> dict[str, Any]:
    status = _enum(getattr(item, "stato", ""))
    return {
        "id": _text(getattr(item, "id", "")),
        "number": _text(getattr(item, "numero", "")),
        "amountDisplay": _money(getattr(item, "totale", 0)),
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
        "paidAt": _date_label(getattr(item, "data_pagamento", "")),
        "paymentMethod": _text(getattr(item, "metodo_pagamento", "")),
    }


def build_react_fatturazione_detail_payload(
    *,
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    id_documento: str,
) -> tuple[dict[str, Any], int]:
    try:
        parcella = get_fatturazione().get(id_documento)
    except Exception:
        parcella = None
    if not parcella:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}, "item": None}, 404
    clienti = {_text(getattr(item, "id", "")): item for item in _safe_all(get_clienti, "tutti")}
    fascicoli = {_text(getattr(item, "id", "")): item for item in _safe_all(get_fascicoli, "tutti")}
    item = _record(parcella, clienti, fascicoli)
    item["voci"] = [
        {
            "descrizione": _text(getattr(voce, "descrizione", "")),
            "quantita": _text(getattr(voce, "quantita", "")),
            "prezzoDisplay": _money(getattr(voce, "prezzo_unitario", 0)),
        }
        for voce in list(getattr(parcella, "voci", []) or [])
    ]
    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {"mock_fallback": False, "writes": "json_api", "route_owner": "react_shell", "operational": True},
        "item": item,
        "warnings": [],
    }, 200


def update_react_fatturazione_status(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}, 403
    errors = _safe_payload_fields(payload)
    try:
        status = StatoParcella(_text(payload.get("stato")).upper())
    except ValueError:
        errors["stato"] = "Stato documento non valido."
        status = StatoParcella.BOZZA
    if errors:
        return {"ok": False, "message": "Controlla i campi evidenziati.", "errors": errors, "item": None}, 400
    try:
        manager = get_fatturazione()
        if not manager.get(id_documento):
            raise KeyError(id_documento)
        manager.cambia_stato(
            id_documento,
            status,
            data_pagamento=_text(payload.get("data_pagamento")) or None,
            metodo_pagamento=_text(payload.get("metodo_pagamento")) or None,
        )
        item = manager.get(id_documento)
    except KeyError:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}, "item": None}, 404
    _audit(get_utenti, current_user, "fatturazione.stato", id_documento, ip_address)
    return {"ok": True, "message": "Stato documento aggiornato.", "errors": {}, "item": _status_result(item)}, 200


def cancel_react_fatturazione_document(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    payload = dict(payload)
    payload["stato"] = StatoParcella.ANNULLATA.value
    return update_react_fatturazione_status(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=current_user,
        id_documento=id_documento,
        payload=payload,
        ip_address=ip_address,
    )


def mark_react_fatturazione_paid(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    payload = dict(payload)
    payload["stato"] = StatoParcella.PAGATA.value
    return update_react_fatturazione_status(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=current_user,
        id_documento=id_documento,
        payload=payload,
        ip_address=ip_address,
    )
