"""Sezioni tipizzate delle pagine del pannello di piattaforma (React).

Ogni pagina del superamministratore si descrive con poche forme che un solo
componente React (`PiattaformaApp`) sa mostrare:

- `metrics`: indicatori (etichetta, valore, nota, tono);
- `status`: elenco di voci con esito (ok, attenzione, blocco, informazione);
- `table`: tabella con colonne dichiarate, righe con collegamento e azioni;
- `facts`: coppie etichetta/valore;
- `notes`: avvisi in testo;
- `shortcuts`: collegamenti alle sezioni del pannello;
- `actions`: pulsanti di azione;
- `form`: modulo che invia un'azione.

Le azioni (`azione`) portano la chiave che il server esegue, i parametri fissi,
gli eventuali campi da compilare in una finestra e la frase di conferma per le
operazioni che modificano dati o richiedono tempo.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

TONI = {"ok": "success", "success": "success", "block": "danger", "danger": "danger", "errore": "danger", "error": "danger", "warning": "warning", "warn": "warning", "info": "info"}
TONI_AZIONE = {"neutral", "primary", "danger", "warning", "success"}
TIPI_CAMPO = {"text", "textarea", "number", "select", "checkbox", "password", "email"}


def _t(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "sì" if value else "no"
    return str(value).strip()


def data_ora(value: Any) -> str:
    """Data e ora in formato italiano (gg/mm/aaaa hh:mm) da un valore ISO."""
    testo = _t(value)
    if not testo:
        return ""
    try:
        momento = datetime.fromisoformat(testo.replace("Z", "+00:00"))
    except ValueError:
        return testo
    if momento.tzinfo is not None:
        from zoneinfo import ZoneInfo

        momento = momento.astimezone(ZoneInfo("Europe/Rome"))
    return momento.strftime("%d/%m/%Y %H:%M")


def _tono(stato: Any) -> str:
    return TONI.get(_t(stato).lower(), "neutral")


def _elenco(valori: Iterable[Any] | None, separatore: str = ", ") -> str:
    return separatore.join(_t(v) for v in valori or [] if _t(v))


# ------------------------------------------------------------------ azioni


def campo(
    name: str,
    label: str,
    kind: str = "text",
    *,
    value: Any = "",
    options: Iterable[tuple[Any, Any]] | None = None,
    required: bool = False,
    help: str = "",
    placeholder: str = "",
) -> dict[str, Any]:
    tipo = kind if kind in TIPI_CAMPO else "text"
    valore: Any = bool(value) if tipo == "checkbox" else _t(value)
    return {
        "name": name,
        "label": label,
        "kind": tipo,
        "value": valore,
        "options": [{"value": _t(v), "label": _t(etichetta)} for v, etichetta in options or []],
        "required": bool(required),
        "help": help,
        "placeholder": placeholder,
    }


def azione(
    key: str,
    label: str,
    *,
    tone: str = "neutral",
    confirm: str = "",
    params: dict[str, Any] | None = None,
    fields: list[dict[str, Any]] | None = None,
    detail: str = "",
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "tone": tone if tone in TONI_AZIONE else "neutral",
        "confirm": confirm,
        "params": {k: _t(v) for k, v in (params or {}).items()},
        "fields": list(fields or []),
        "detail": detail,
    }


def actions(title: str, items: list[dict[str, Any]], *, subtitle: str = "") -> dict[str, Any]:
    return {"kind": "actions", "title": title, "subtitle": subtitle, "items": list(items)}


def form(
    title: str,
    action_key: str,
    fields: list[dict[str, Any]],
    *,
    submit_label: str = "Salva",
    subtitle: str = "",
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": "form",
        "title": title,
        "subtitle": subtitle,
        "action": azione(action_key, submit_label, tone="primary", params=params),
        "fields": list(fields),
    }


# ------------------------------------------------------------------ sezioni


def metrics(items: list[dict[str, Any]], title: str = "") -> dict[str, Any]:
    return {"kind": "metrics", "title": title, "items": [{"label": _t(i.get("label")), "value": _t(i.get("value")), "note": _t(i.get("note")), "tone": i.get("tone") or "neutral"} for i in items]}


def status(title: str, items: list[dict[str, Any]], subtitle: str = "") -> dict[str, Any]:
    return {
        "kind": "status",
        "title": title,
        "subtitle": subtitle,
        "items": [
            {"title": _t(i.get("title")), "summary": _t(i.get("summary")), "detail": _t(i.get("detail")), "tone": _tono(i.get("status")), "statusLabel": _t(i.get("statusLabel") or i.get("status")).upper()}
            for i in items
        ],
    }


def table(title: str, columns: list[tuple[str, str]], rows: list[dict[str, Any]], *, subtitle: str = "", empty: str = "Nessun dato.") -> dict[str, Any]:
    return {
        "kind": "table",
        "title": title,
        "subtitle": subtitle,
        "empty": empty,
        "columns": [{"key": k, "label": label} for k, label in columns],
        "rows": [
            {
                "cells": {k: _t(r.get(k)) for k, _ in columns},
                "href": _t(r.get("_href")),
                "external": bool(r.get("_external")),
                "tone": r.get("_tone") or "",
                "actions": list(r.get("_actions") or []),
            }
            for r in rows
        ],
    }


def facts(title: str, items: list[tuple[str, Any]]) -> dict[str, Any]:
    return {"kind": "facts", "title": title, "items": [{"label": label, "value": _t(value)} for label, value in items if _t(value)]}


def notes(title: str, items: list[Any], tone: str = "warning") -> dict[str, Any]:
    testi = [_t(i) for i in items if _t(i)]
    return {"kind": "notes", "title": title, "tone": tone, "items": testi}


def shortcuts(title: str, items: list[tuple[str, str, str]]) -> dict[str, Any]:
    """Collegamenti alle sezioni del pannello (etichetta, descrizione, indirizzo)."""
    return {"kind": "shortcuts", "title": title, "items": [{"label": label, "detail": detail, "href": href} for label, detail, href in items]}


def link(label: str, href: str, *, tone: str = "neutral", external: bool = False) -> dict[str, Any]:
    return {"label": label, "href": href, "tone": tone, "external": external}


def esito(ok: bool, message: str, *, tone: str = "", sections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Risposta di un'azione: esito, messaggio in italiano ed eventuali sezioni di risultato."""
    return {"ok": bool(ok), "message": message, "tone": tone or ("success" if ok else "danger"), "sections": list(sections or [])}


def sezione_visibile(sezione: dict[str, Any]) -> bool:
    """Le sezioni vuote non si mostrano; tabelle e moduli restano (dicono «nessun dato» o chiedono dati)."""
    return bool(sezione.get("items") or sezione.get("rows") or sezione.get("kind") in {"table", "form"})


__all__ = [
    "_elenco",
    "_t",
    "_tono",
    "actions",
    "azione",
    "campo",
    "data_ora",
    "esito",
    "facts",
    "form",
    "link",
    "metrics",
    "notes",
    "sezione_visibile",
    "shortcuts",
    "status",
    "table",
]
