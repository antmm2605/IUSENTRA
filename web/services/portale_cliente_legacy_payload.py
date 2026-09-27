"""Payload JSON del portale con link personale per la pagina React.

Solo campi in lista: niente impronte del token, indirizzi IP, user agent,
note riservate o dati di altri clienti. Date e importi arrivano già nel
formato italiano delle pagine storiche (stessi filtri: `fmt_*`, `euro`).
"""

from __future__ import annotations

from typing import Any

from flask import url_for

from pct.formatting import format_date_it, format_euro_it
from web.services.portale_cliente_legacy_contesto import ContestoPortale, permesso, studio_nome
from web.services.ui_localization import format_date, format_date_long, format_month_short, format_time_only

PERMESSI_ESPOSTI = (
    "vedi_anagrafica", "modifica_anagrafica", "vedi_fascicoli", "vedi_economici", "accetta_preventivi",
    "firma_conferimenti", "vedi_appuntamenti", "vedi_scadenze", "carica_documenti", "firma_privacy",
)
PERMESSI_PREDEFINITI_VERI = {"accetta_preventivi", "firma_conferimenti"}


def _testo(valore: Any) -> str:
    return "" if valore is None else str(valore)


def _stato(valore: Any) -> str:
    return _testo(getattr(valore, "value", valore))


def intestazione(contesto: ContestoPortale) -> dict[str, Any]:
    """Dati comuni a ogni sezione: studio, cliente, permessi e stato privacy."""
    portale = contesto.portale
    permessi = {
        nome: permesso(contesto, nome, nome in PERMESSI_PREDEFINITI_VERI) for nome in PERMESSI_ESPOSTI
    }
    permessi["max_upload_mb"] = int(getattr(portale.permessi, "max_upload_mb", 10) or 10)
    return {
        "studio_nome": studio_nome(),
        "cliente": {"nome_completo": _testo(contesto.cliente.nome_completo)},
        "permessi": permessi,
        "privacy": {
            "firmata": bool(portale.privacy_firmata),
            "data_firma": format_date_it(portale.data_firma_privacy) if portale.data_firma_privacy else "",
        },
    }


def _fascicolo(f: Any, tracker: dict[str, Any] | None) -> dict[str, Any]:
    payload = {
        "id": _testo(f.id),
        "titolo": _testo(f.titolo),
        "stato": _stato(f.stato),
        "tipo": _stato(f.tipo),
        "numero_rg": _testo(getattr(f, "numero_rg", "")),
        "tribunale": _testo(getattr(f, "tribunale", "")),
        "tracker": None,
    }
    if tracker:
        payload["tracker"] = {
            "current_label": _testo(tracker.get("current_label")),
            "percent": max(0, min(100, int(tracker.get("percent") or 0))),
            "steps": [
                {"label": _testo(step.get("label")), "complete": bool(step.get("complete"))}
                for step in tracker.get("steps") or []
                if isinstance(step, dict)
            ],
            "last_event": _testo(tracker.get("last_event")),
            "next_event": _testo(tracker.get("next_event")),
        }
    return payload


def _appuntamento(a: Any) -> dict[str, Any]:
    quando = a.data_ora_dt
    return {
        "titolo": _testo(a.titolo),
        "giorno": f"{quando.day:02d}",
        "mese": format_month_short(quando),
        "ora": format_time_only(quando),
        "luogo": _testo(getattr(a, "luogo", "")),
        "data_ora": _testo(a.data_ora),
    }


def _scadenza(s: Any) -> dict[str, Any]:
    return {
        "titolo": _testo(s.titolo),
        "data": format_date(getattr(s, "data_scadenza", "")),
        "priorita": _stato(getattr(s, "priorita", "")),
        "perentorio": bool(getattr(s, "perentorio", False)),
    }


def _riepilogo_calcolo(calc: Any) -> dict[str, Any] | None:
    if not isinstance(calc, dict) or not calc:
        return None
    audit = calc.get("audit_tariffario") if isinstance(calc.get("audit_tariffario"), dict) else {}
    payload = {
        "pratica_label": _testo(calc.get("pratica_label")),
        "regola": _testo(calc.get("regola_tariffaria_label") or calc.get("regola_tariffaria")),
        "grado_sede": _testo(calc.get("grado_sede")),
        "compliance_label": _testo(audit.get("compliance_label")),
        "compliance_tone": _testo(audit.get("compliance_badge") or "secondary"),
        "table_code": _testo(audit.get("table_code")),
    }
    return payload if any(payload[k] for k in ("pratica_label", "regola", "grado_sede", "compliance_label")) else None


def _riepilogo_workflow(summary: Any) -> dict[str, Any] | None:
    if not isinstance(summary, dict) or not summary:
        return None
    riferimenti = [
        _testo(r.get("title")) for r in (summary.get("riferimenti_normativi") or [])[:2] if isinstance(r, dict)
    ]
    return {
        "channel_label": _testo(summary.get("channel_label")),
        "next_step_label": _testo(summary.get("next_step_label")),
        "riferimenti": [r for r in riferimenti if r],
    }


def _url_pdf(kind: str, token: str, id_doc: str) -> str:
    if kind == "preventivo":
        return url_for("portale.pdf_preventivo", token=token, id_preventivo=id_doc)
    if kind == "conferimento":
        return url_for("portale.pdf_conferimento", token=token, id_conferimento=id_doc)
    return url_for("portale.pdf_parcella", token=token, id_parcella=id_doc)


def _documento(kind: str, doc: Any, token: str) -> dict[str, Any]:
    data = doc.data_incarico if kind == "conferimento" else doc.data_emissione
    totale = (doc.compenso_pattuito or 0) if kind == "conferimento" else doc.totale
    descrizione = (doc.note or "Parcella professionale emessa dallo studio.") if kind == "parcella" else _testo(doc.oggetto)
    return {
        "kind": kind,
        "id": _testo(doc.id),
        "numero": _testo(doc.numero),
        "stato": _stato(doc.stato),
        "data": format_date_it(data),
        "scadenza": format_date_it(getattr(doc, "data_scadenza", "")) if getattr(doc, "data_scadenza", "") else "",
        "totale": format_euro_it(totale),
        "descrizione": descrizione,
        "calcolo": _riepilogo_calcolo(getattr(doc, "calc_summary", None)),
        "workflow": _riepilogo_workflow(getattr(doc, "workflow_summary", None)),
        "can_accept": bool(getattr(doc, "can_accept", False)) if kind == "preventivo" else False,
        "can_sign": bool(getattr(doc, "can_sign", False)) if kind == "conferimento" else False,
        "pdf_url": _url_pdf(kind, token, _testo(doc.id)),
    }


def _azione(azione: dict[str, Any]) -> dict[str, Any]:
    return {k: _testo(azione.get(k)) for k in ("kind", "id", "title", "subtitle", "button_label")}


def _voce_cronologia(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": _testo(item.get("kind")),
        "numero": _testo(item.get("numero")),
        "titolo": _testo(item.get("titolo")),
        "data": format_date_it(item.get("data")),
        "fascicolo_label": _testo(item.get("fascicolo_label")),
        "totale": format_euro_it(item.get("totale")),
    }


def payload_home(contesto: ContestoPortale, token: str, dati: dict[str, Any]) -> dict[str, Any]:
    tracker_map = dati.get("tracker_map") or {}
    economici = dati["economici"]
    return {
        "ok": True,
        "sezione": "home",
        **intestazione(contesto),
        "oggi": format_date_long(dati["oggi"]),
        "azioni_richieste": [_azione(a) for a in dati["azioni_richieste"][:2]],
        "fascicoli": [_fascicolo(f, tracker_map.get(f.id)) for f in dati["fascicoli"]],
        "appuntamenti": [_appuntamento(a) for a in dati["appuntamenti"]],
        "scadenze": [_scadenza(s) for s in dati["scadenze"]],
        "economici": {
            "stats": dict(economici["stats"]),
            "cronologia": [_voce_cronologia(item) for item in economici["timeline"][:3]],
        },
    }


def payload_privacy(contesto: ContestoPortale) -> dict[str, Any]:
    return {"ok": True, "sezione": "privacy", **intestazione(contesto)}


def payload_documenti(contesto: ContestoPortale, fascicoli: list[Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "sezione": "documenti",
        **intestazione(contesto),
        "fascicoli": [
            {"id": _testo(f.id), "titolo": _testo(f.titolo), "numero_rg": _testo(getattr(f, "numero_rg", ""))}
            for f in fascicoli
        ],
    }


def payload_economici(contesto: ContestoPortale, token: str, dati: dict[str, Any], azioni: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ok": True,
        "sezione": "economici",
        **intestazione(contesto),
        "stats": dict(dati["stats"]),
        "azioni_richieste": [_azione(a) for a in azioni[:3]],
        "preventivi": [_documento("preventivo", d, token) for d in dati["preventivi"]],
        "conferimenti": [_documento("conferimento", d, token) for d in dati["conferimenti"]],
        "parcelle": [_documento("parcella", d, token) for d in dati["parcelle"]],
    }


def _indirizzo(cliente: Any) -> str:
    from pct.clienti import TipoCliente

    campo = "indirizzo_sede_legale" if cliente.tipo == TipoCliente.PERSONA_GIURIDICA else "indirizzo_residenza"
    return _testo(getattr(cliente, campo, "") or "").strip()


def payload_anagrafica(contesto: ContestoPortale) -> dict[str, Any]:
    from pct.clienti import TipoCliente

    cliente = contesto.cliente
    persona_fisica = cliente.tipo != TipoCliente.PERSONA_GIURIDICA
    recapiti = cliente.recapiti
    return {
        "ok": True,
        "sezione": "anagrafica",
        **intestazione(contesto),
        "anagrafica": {
            "nome_completo": _testo(cliente.nome_completo),
            "tipo": "PF" if persona_fisica else "PG",
            "data_nascita": format_date_it(cliente.data_nascita) if persona_fisica and cliente.data_nascita else "",
            "codice_fiscale": _testo(cliente.codice_fiscale) if persona_fisica else "",
            "partita_iva": "" if persona_fisica else _testo(cliente.partita_iva),
            "indirizzo": _indirizzo(cliente),
        },
        "recapiti": {
            "cellulare": _testo(getattr(recapiti, "cellulare", "")),
            "telefono": _testo(getattr(recapiti, "telefono", "")),
            "email": _testo(getattr(recapiti, "email", "")),
        },
    }


__all__ = [
    "intestazione",
    "payload_anagrafica",
    "payload_documenti",
    "payload_economici",
    "payload_home",
    "payload_privacy",
]
