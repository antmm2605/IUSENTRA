"""Copertine da stampare come PDF: copertina del fascicolo e copertina del faldone del cliente.

Sostituiscono le pagine Jinja ``fascicoli/copertina.html`` e ``clienti/copertina_faldone.html``
con gli stessi dati, impaginati con ReportLab e lo stile dei report di ``pct/reports.py``.
Ogni testo dei dati passa da ``escape``: i Paragraph di ReportLab interpretano il markup.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Any
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from flask import make_response

from reportlab.lib import pagesizes
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from pct.formatting import format_date_it, format_euro_it
from pct.pdf_style import PDF_TABLE_HEADER_TEXT, pdf_table_header_style
from pct.reports import (
    GRIGIO_CHIARO,
    GRIGIO_MEDIO,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    _build_styles,
    _griglia_campi,
    _intestazione_studio,
    _sezione_header,
)
from web.services.fascicolo_copertina import _TIPI, _chiave, _leggibile, contesto_copertina
from web.services.ui_localization import format_portal_import_note

VUOTO = "-"


def oggi_roma() -> date:
    return datetime.now(ZoneInfo("Europe/Rome")).date()


def risposta_pdf_copertina(pdf: bytes, nome_file: str):
    """PDF aperto nel browser (da stampare), mai in cache condivise."""
    nome = re.sub(r"[^A-Za-z0-9._-]+", "-", nome_file).strip("-") or "copertina.pdf"
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'inline; filename="{nome}"'
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _t(valore: Any) -> str:
    """Testo sicuro per un Paragraph (mai markup dai dati)."""
    return escape(str(valore or "").strip())


def _o(valore: Any) -> str:
    testo = _t(valore)
    return testo or VUOTO


def _data(valore: Any) -> str:
    return format_date_it(valore) if valore else VUOTO


def _rg(fascicolo: Any) -> str:
    numero = str(getattr(fascicolo, "numero_rg", "") or "").strip()
    anno = str(getattr(fascicolo, "anno_rg", "") or "").strip()
    if not numero:
        return VUOTO
    return _t(f"{numero}/{anno}" if anno else numero)


def _tipo(fascicolo: Any) -> str:
    chiave = _chiave(getattr(fascicolo, "tipo", ""))
    return _TIPI.get(chiave) or _leggibile(chiave) or VUOTO


def _stili() -> dict:
    """Stili dei report con due correzioni locali: intestazione dello studio senza sovrapposizioni
    e intestazioni di tabella leggibili (testo scuro sullo sfondo chiaro di pdf_table_header_style)."""
    styles = _build_styles()
    styles["studio_nome"] = ParagraphStyle("copertina_studio", parent=styles["studio_nome"], leading=22)
    styles["tabella_header"] = ParagraphStyle(
        "copertina_tabella_header", parent=styles["tabella_header"], textColor=PDF_TABLE_HEADER_TEXT, alignment=TA_LEFT,
    )
    return styles


def _documento(titolo: str, autore: str, storia: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesizes.A4,
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title=titolo,
        author=autore,
        lang="it-IT",
    )
    doc.build(storia)
    return buffer.getvalue()


def _larghezza() -> float:
    return pagesizes.A4[0] - MARGIN_LEFT - MARGIN_RIGHT


def _indirizzo(cliente: Any) -> str:
    indirizzo = getattr(cliente, "indirizzo_residenza", None)
    if not indirizzo or not getattr(indirizzo, "via", ""):
        return ""
    parti = [f"{indirizzo.via}, {getattr(indirizzo, 'civico', '') or ''}".strip(" ,"),
             f"{getattr(indirizzo, 'cap', '') or ''} {getattr(indirizzo, 'comune', '') or ''}".strip()]
    provincia = str(getattr(indirizzo, "provincia", "") or "").strip()
    testo = " ".join(parte for parte in parti if parte)
    return f"{testo} ({provincia})" if provincia else testo


def copertina_fascicolo_pdf(
    fascicolo: Any, cliente: Any | None, *, studio_nome: str, avvocato_studio: str = "", oggi: date | None = None,
) -> bytes:
    """Copertina del fascicolo: dati della pratica, dati giudiziari e parti."""
    styles = _stili()
    larghezza = _larghezza()
    copertina = contesto_copertina(fascicolo, avvocato_studio, oggi)
    giorno = format_date_it(oggi or date.today())
    storia: list = [
        _intestazione_studio(_t(studio_nome), "Copertina del fascicolo", _t(f"Stampata il {giorno}"), styles, larghezza),
        Spacer(1, 18),
        Paragraph(_t(fascicolo.titolo), styles["titolo_fascicolo"]),
        Paragraph(_t(getattr(fascicolo, "numero", "")), styles["numero_fascicolo"]),
    ]
    if getattr(fascicolo, "oggetto", ""):
        storia += [Spacer(1, 4), Paragraph(_t(fascicolo.oggetto), styles["note_testo"])]
    storia += [Spacer(1, 14), _sezione_header("Dati della pratica", styles, larghezza), _griglia_campi([
        ("Pratica", _o(fascicolo.titolo)),
        ("Oggetto", _o(getattr(fascicolo, "oggetto", ""))),
        ("Identificativo", _o(getattr(fascicolo, "numero", ""))),
        ("Data di apertura", _data(getattr(fascicolo, "data_apertura", ""))),
        ("Titolare pratica", _o(copertina["titolare"])),
        ("Responsabile pratica", _o(getattr(fascicolo, "avvocato_dominus", ""))),
        ("Stato della pratica", _o(copertina["stato_label"])),
    ], styles, larghezza)]
    giudiziari = [
        ("Autorità giudiziaria", _o(getattr(fascicolo, "tribunale", ""))),
        ("Sezione", _o(getattr(fascicolo, "sezione", ""))),
        ("Materia", _o(copertina["tipo_label"])),
        ("N. RG", _rg(fascicolo)),
        ("Istruttore / PM / GIP", _o(getattr(fascicolo, "giudice", ""))),
        ("Controparte", _o(getattr(fascicolo, "controparte", ""))),
    ]
    if getattr(fascicolo, "data_prima_udienza", ""):
        giudiziari.append(("Prima udienza", _data(fascicolo.data_prima_udienza)))
    if getattr(fascicolo, "data_prossima_udienza", ""):
        giudiziari.append((copertina["udienza_label"], _data(fascicolo.data_prossima_udienza)))
    if getattr(fascicolo, "valore_causa", 0):
        giudiziari.append(("Valore della causa", _t(format_euro_it(fascicolo.valore_causa))))
    storia += [Spacer(1, 10), _sezione_header("Dati giudiziari", styles, larghezza), _griglia_campi(giudiziari, styles, larghezza)]
    if getattr(fascicolo, "note", ""):
        storia += [Spacer(1, 10), _sezione_header("Note", styles, larghezza), Spacer(1, 4),
                   Paragraph(_t(format_portal_import_note(fascicolo.note)), styles["note_testo"])]
    parti = []
    if cliente is not None:
        dettagli = [getattr(cliente, "nome_completo", "")]
        if _indirizzo(cliente):
            dettagli.append(_indirizzo(cliente))
        if getattr(cliente, "codice_fiscale", ""):
            dettagli.append(f"C.F. {cliente.codice_fiscale}")
        parti.append(("Cliente", _t(" - ".join(dettagli))))
    if getattr(fascicolo, "controparte", ""):
        dettagli = [fascicolo.controparte]
        if getattr(fascicolo, "cf_controparte", ""):
            dettagli.append(f"C.F. {fascicolo.cf_controparte}")
        parti.append(("Controparte", _t(" - ".join(dettagli))))
    if parti:
        storia += [Spacer(1, 10), _sezione_header("Parti", styles, larghezza), _griglia_campi(parti, styles, larghezza, cols=1)]
    storia += [Spacer(1, 18), Paragraph(
        _t(f"{studio_nome} · {getattr(fascicolo, 'numero', '')} - {fascicolo.titolo} · {giorno}"), styles["footer"])]
    return _documento(f"Copertina fascicolo - {fascicolo.titolo}", studio_nome, storia)


def _tabella_pratiche(fascicoli: list, styles: dict, larghezza: float, *, complete: bool) -> Table:
    intestazioni = ["N.", "Pratica", "Tipo", "Tribunale"] + (["RG", "Apertura"] if complete else [])
    pesi = [0.12, 0.31, 0.11, 0.22, 0.11, 0.13] if complete else [0.15, 0.40, 0.15, 0.30]
    righe = [[Paragraph(_t(testo), styles["tabella_header"]) for testo in intestazioni]]
    for fascicolo in fascicoli:
        riga = [
            Paragraph(_o(getattr(fascicolo, "numero", "")), styles["tabella_cella"]),
            Paragraph(_o(fascicolo.titolo), styles["tabella_cella"]),
            Paragraph(_t(_tipo(fascicolo)), styles["tabella_cella"]),
            Paragraph(_o(getattr(fascicolo, "tribunale", "")), styles["tabella_cella"]),
        ]
        if complete:
            riga += [Paragraph(_rg(fascicolo), styles["tabella_cella"]),
                     Paragraph(_data(getattr(fascicolo, "data_apertura", "")), styles["tabella_cella"])]
        righe.append(riga)
    stile = TableStyle([
        *pdf_table_header_style(),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [GRIGIO_CHIARO, None]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, GRIGIO_MEDIO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])
    return Table(righe, colWidths=[larghezza * peso for peso in pesi], style=stile, repeatRows=1, hAlign="LEFT")


def copertina_faldone_pdf(
    cliente: Any, fascicoli_attivi: list, fascicoli_archiviati: list, *, studio_nome: str, oggi: date | None = None,
) -> bytes:
    """Copertina del faldone del cliente: anagrafica essenziale, conteggi e pratiche."""
    styles = _stili()
    larghezza = _larghezza()
    tutti = list(fascicoli_attivi) + list(fascicoli_archiviati)
    giorno = format_date_it(oggi or date.today())
    identificativi = []
    if getattr(cliente, "codice_fiscale", ""):
        identificativi.append(f"C.F. {cliente.codice_fiscale}")
    if getattr(cliente, "partita_iva", ""):
        identificativi.append(f"P.IVA {cliente.partita_iva}")
    recapiti = getattr(cliente, "recapiti", None)
    storia: list = [
        _intestazione_studio(_t(studio_nome), "Copertina del faldone", _t(f"Stampata il {giorno}"), styles, larghezza),
        Spacer(1, 18),
        Paragraph(_t(cliente.nome_completo), styles["titolo_fascicolo"]),
    ]
    if identificativi:
        storia.append(Paragraph(_t(" · ".join(identificativi)), styles["numero_fascicolo"]))
    dati = [
        ("Avvocato referente", _o(getattr(cliente, "avvocato_referente", ""))),
        ("Prima acquisizione", _data(getattr(cliente, "data_prima_acquisizione", ""))),
        ("Email", _o(getattr(recapiti, "email", ""))),
        ("Telefono / Cellulare", _o(getattr(recapiti, "telefono", "") or getattr(recapiti, "cellulare", ""))),
    ]
    if _indirizzo(cliente):
        dati.append(("Indirizzo", _t(_indirizzo(cliente))))
    storia += [Spacer(1, 14), _sezione_header("Cliente", styles, larghezza), _griglia_campi(dati, styles, larghezza)]
    conteggi = [
        ("Pratiche attive", str(len(fascicoli_attivi))),
        ("Pratiche archiviate", str(len(fascicoli_archiviati))),
        ("Documenti totali", str(sum(int(getattr(f, "documenti_count", 0) or 0) for f in tutti))),
        ("Pratiche totali", str(len(tutti))),
    ]
    storia += [Spacer(1, 10), _sezione_header("Riepilogo", styles, larghezza), _griglia_campi(conteggi, styles, larghezza)]
    if fascicoli_attivi:
        storia += [Spacer(1, 10), _sezione_header("Pratiche attive", styles, larghezza), Spacer(1, 4),
                   _tabella_pratiche(fascicoli_attivi, styles, larghezza, complete=True)]
    if fascicoli_archiviati:
        storia += [Spacer(1, 10), _sezione_header(f"Pratiche archiviate ({len(fascicoli_archiviati)})", styles, larghezza),
                   Spacer(1, 4), _tabella_pratiche(fascicoli_archiviati, styles, larghezza, complete=False)]
    storia += [Spacer(1, 18), Paragraph(_t(f"{studio_nome} · {cliente.nome_completo} - Faldone · {giorno}"), styles["footer"])]
    return _documento(f"Copertina faldone - {cliente.nome_completo}", studio_nome, storia)


__all__ = ["copertina_faldone_pdf", "copertina_fascicolo_pdf", "oggi_roma", "risposta_pdf_copertina"]
