"""Shared helpers for fascicolo document bootstrap routes."""

from __future__ import annotations

from typing import Any

from flask import request

from pct.fascicoli import TipoDocumento


def estrai_pdf_da_raw(data: bytes) -> bytes | None:
    idx = data.find(b"%PDF")
    if idx < 0:
        return None
    eof_idx = data.rfind(b"%%EOF")
    if eof_idx > idx:
        return data[idx : eof_idx + 5]
    return data[idx:]


def wants_json_response() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def preview_unavailable_html(nome_documento: str, scarica_url: str) -> tuple[str, int, dict[str, str]]:
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">'
        '</head><body class="bg-light d-flex align-items-center justify-content-center" style="min-height:100vh">'
        '<div class="text-center p-4">'
        '<i class="bi bi-file-earmark-lock2 text-secondary" style="font-size:3rem"></i>'
        f'<h6 class="mt-3 mb-2">{nome_documento}</h6>'
        '<p class="text-muted small mb-3">Anteprima non disponibile per questo formato.<br>'
        "Scarica il file per visualizzarlo con il programma appropriato.</p>"
        f'<a href="{scarica_url}" class="btn btn-primary btn-sm">'
        '<i class="bi bi-download me-1"></i>Scarica documento</a>'
        "</div></body></html>"
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def preview_error_html(scarica_url: str) -> tuple[str, int, dict[str, str]]:
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">'
        '</head><body class="bg-light d-flex align-items-center justify-content-center" style="min-height:100vh">'
        '<div class="text-center p-4">'
        '<i class="bi bi-exclamation-triangle text-warning" style="font-size:3rem"></i>'
        '<h6 class="mt-3 mb-2">Impossibile visualizzare il documento</h6>'
        '<p class="text-muted small mb-3">Si e verificato un errore durante il caricamento.<br>'
        "Scarica il file per visualizzarlo con il programma appropriato.</p>"
        f'<a href="{scarica_url}" class="btn btn-primary btn-sm">'
        '<i class="bi bi-download me-1"></i>Scarica documento</a>'
        "</div></body></html>"
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def payload_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "si", "s", "on"}


def classifica_tipo_documento(nome_file: str) -> TipoDocumento:
    nome = str(nome_file or "").casefold()
    rules: list[tuple[tuple[str, ...], TipoDocumento]] = [
        (("procura", "mandato"), TipoDocumento.PROCURA),
        (("ricorso",), TipoDocumento.RICORSO),
        (("citazione",), TipoDocumento.CITAZIONE),
        (("comparsa",), TipoDocumento.COMPARSA),
        (("memoria", "note autorizzate", "conclusionale", "replica"), TipoDocumento.MEMORIA),
        (("sentenza",), TipoDocumento.SENTENZA),
        (("ordinanza",), TipoDocumento.ORDINANZA),
        (("decreto",), TipoDocumento.DECRETO),
        (("notifica", "relata"), TipoDocumento.NOTIFICA),
        (("verbale", "udienza"), TipoDocumento.VERBALE),
        (("parcella", "fattura", "proforma", "nota spese"), TipoDocumento.PARCELLA),
        (("contratto", "accordo", "scrittura privata"), TipoDocumento.CONTRATTO),
        (("deposito", "busta", "rdac", "rac", "esito"), TipoDocumento.DEPOSITO_PCT),
        (("pec", "comunicazione", "cancelleria"), TipoDocumento.COMUNICAZIONE),
        (("allegato", "doc", "documento", "immagine", "foto", "pdf"), TipoDocumento.ALLEGATO),
    ]
    for tokens, tipo in rules:
        if any(token in nome for token in tokens):
            return tipo
    return TipoDocumento.ALTRO


def applica_modalita_portale(items: list[dict[str, Any]], *, scarica_originale: bool) -> list[dict[str, Any]]:
    modalita = "originale" if scarica_originale else "copia"
    patched: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        if not str(row.get("modalita_documento_portale") or "").strip():
            row["modalita_documento_portale"] = modalita
        if row.get("original_documento_portale") is None:
            row["original_documento_portale"] = bool(scarica_originale)
        patched.append(row)
    return patched
