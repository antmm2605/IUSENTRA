"""
Generatore di report PDF professionali per fascicoli legali.

Produce:
- Report completo del fascicolo (intestazione studio, parti, attività, documenti)
- Scadenziario mensile con tabella scadenze
"""

from __future__ import annotations

import os
from datetime import datetime, date
from typing import Any

from reportlab.lib import colors, pagesizes, units
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
    KeepTogether,
)
from pct.pdf_style import pdf_table_header_style


# ------------------------------------------------------------------ Costanti colori

BLU_SCURO   = colors.HexColor("#1a3a5c")
ORO_ACCENTO = colors.HexColor("#c8972b")
GRIGIO_CHIARO = colors.HexColor("#f0f4f8")
GRIGIO_MEDIO  = colors.HexColor("#dce3ea")
BIANCO        = colors.white
NERO          = colors.black
GRIGIO_TESTO  = colors.HexColor("#333333")

# Margini pagina A4
MARGIN_LEFT   = 2.2 * cm
MARGIN_RIGHT  = 2.0 * cm
MARGIN_TOP    = 2.0 * cm
MARGIN_BOTTOM = 2.5 * cm


# ------------------------------------------------------------------ Utility

def _fmt_date(value: Any) -> str:
    """Converte una stringa ISO o un oggetto date/datetime in formato italiano."""
    if not value:
        return "—"
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(value) or "—"


def _fmt_bytes(n: Any) -> str:
    """Formatta dimensione in bytes in modo leggibile."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "—"
    if n < 1024:
        return f"{n} B"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    elif n < 1024 ** 3:
        return f"{n / 1024**2:.1f} MB"
    return f"{n / 1024**3:.1f} GB"


def _val(d: dict, key: str, default: str = "—") -> str:
    """Restituisce il valore del dizionario come stringa, oppure il default."""
    v = d.get(key)
    if v is None or str(v).strip() == "":
        return default
    return str(v)


def _build_styles() -> dict:
    """Costruisce e restituisce un dizionario di ParagraphStyle."""
    base = getSampleStyleSheet()

    styles = {}

    styles["studio_nome"] = ParagraphStyle(
        "studio_nome",
        fontSize=18,
        fontName="Helvetica-Bold",
        textColor=BIANCO,
        alignment=TA_LEFT,
        spaceAfter=2,
    )
    styles["studio_sub"] = ParagraphStyle(
        "studio_sub",
        fontSize=9,
        fontName="Helvetica",
        textColor=colors.HexColor("#c8d8e8"),
        alignment=TA_LEFT,
        spaceAfter=0,
    )
    styles["report_titolo"] = ParagraphStyle(
        "report_titolo",
        fontSize=11,
        fontName="Helvetica-Bold",
        textColor=BIANCO,
        alignment=TA_RIGHT,
        spaceAfter=0,
    )
    styles["report_sub"] = ParagraphStyle(
        "report_sub",
        fontSize=8,
        fontName="Helvetica",
        textColor=colors.HexColor("#c8d8e8"),
        alignment=TA_RIGHT,
        spaceAfter=0,
    )
    styles["sezione_titolo"] = ParagraphStyle(
        "sezione_titolo",
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=BIANCO,
        alignment=TA_LEFT,
        leftIndent=6,
        spaceAfter=0,
        spaceBefore=0,
    )
    styles["campo_label"] = ParagraphStyle(
        "campo_label",
        fontSize=8,
        fontName="Helvetica-Bold",
        textColor=BLU_SCURO,
        alignment=TA_LEFT,
    )
    styles["campo_valore"] = ParagraphStyle(
        "campo_valore",
        fontSize=9,
        fontName="Helvetica",
        textColor=GRIGIO_TESTO,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )
    styles["note_testo"] = ParagraphStyle(
        "note_testo",
        fontSize=9,
        fontName="Helvetica",
        textColor=GRIGIO_TESTO,
        alignment=TA_LEFT,
        leading=13,
        wordWrap="CJK",
    )
    styles["tabella_header"] = ParagraphStyle(
        "tabella_header",
        fontSize=8,
        fontName="Helvetica-Bold",
        textColor=BIANCO,
        alignment=TA_CENTER,
    )
    styles["tabella_cella"] = ParagraphStyle(
        "tabella_cella",
        fontSize=8,
        fontName="Helvetica",
        textColor=GRIGIO_TESTO,
        alignment=TA_LEFT,
        wordWrap="CJK",
        leading=10,
    )
    styles["tabella_cella_c"] = ParagraphStyle(
        "tabella_cella_c",
        fontSize=8,
        fontName="Helvetica",
        textColor=GRIGIO_TESTO,
        alignment=TA_CENTER,
        wordWrap="CJK",
        leading=10,
    )
    styles["footer"] = ParagraphStyle(
        "footer",
        fontSize=7,
        fontName="Helvetica",
        textColor=colors.HexColor("#888888"),
        alignment=TA_CENTER,
    )
    styles["titolo_fascicolo"] = ParagraphStyle(
        "titolo_fascicolo",
        fontSize=13,
        fontName="Helvetica-Bold",
        textColor=BLU_SCURO,
        alignment=TA_LEFT,
        spaceBefore=6,
        spaceAfter=2,
    )
    styles["numero_fascicolo"] = ParagraphStyle(
        "numero_fascicolo",
        fontSize=10,
        fontName="Helvetica",
        textColor=ORO_ACCENTO,
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    styles["nota"] = ParagraphStyle(
        "nota",
        fontSize=7,
        fontName="Helvetica",
        textColor=GRIGIO_TESTO,
        alignment=TA_LEFT,
        wordWrap="CJK",
        leading=9,
    )

    return styles


def _intestazione_studio(
    studio_nome: str,
    report_titolo: str,
    report_sottotitolo: str,
    styles: dict,
    page_width: float,
) -> Table:
    """Ritorna la tabella di intestazione colorata con logo testuale e titolo report."""
    col_sx = page_width * 0.60
    col_dx = page_width * 0.40

    studio_para = Paragraph(studio_nome, styles["studio_nome"])
    studio_sub  = Paragraph("Gestione Fascicoli Legali", styles["studio_sub"])

    titolo_para = Paragraph(report_titolo, styles["report_titolo"])
    sub_para    = Paragraph(report_sottotitolo, styles["report_sub"])

    data = [
        [[studio_para, studio_sub], [titolo_para, sub_para]],
    ]

    ts = TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), BLU_SCURO),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (0, 0), 12),
        ("RIGHTPADDING", (1, 0), (1, 0), 12),
        ("TOPPADDING",   (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 14),
        ("LINEBELOW",   (0, 0), (-1, -1), 3, ORO_ACCENTO),
    ])

    return Table(data, colWidths=[col_sx, col_dx], style=ts)


def _sezione_header(titolo: str, styles: dict, larghezza: float) -> Table:
    """Riga colorata usata come intestazione di sezione."""
    data = [[Paragraph(titolo.upper(), styles["sezione_titolo"])]]
    ts = TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), BLU_SCURO),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ])
    return Table(data, colWidths=[larghezza], style=ts)


def _griglia_campi(coppie: list[tuple[str, str]], styles: dict, larghezza: float, cols: int = 2) -> Table:
    """
    Costruisce una griglia etichetta/valore su `cols` colonne.
    `coppie` è una lista di (etichetta, valore).
    """
    # Riempi fino a multiplo di cols
    while len(coppie) % cols != 0:
        coppie.append(("", ""))

    col_w = larghezza / cols / 2  # ogni coppia occupa due celle uguale
    col_widths = [col_w] * (cols * 2)

    rows = []
    for i in range(0, len(coppie), cols):
        row = []
        for j in range(cols):
            lbl, val = coppie[i + j]
            row.append(Paragraph(lbl, styles["campo_label"]) if lbl else "")
            row.append(Paragraph(val, styles["campo_valore"]) if val else "")
        rows.append(row)

    ts = TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BIANCO, GRIGIO_CHIARO]),
        ("LINEBELOW",    (0, 0), (-1, -1), 0.3, GRIGIO_MEDIO),
    ])

    return Table(rows, colWidths=col_widths, style=ts, hAlign="LEFT")


def _tabella_attivita(attivita: list, styles: dict, larghezza: float) -> Table:
    """Tabella delle attività processuali."""
    col_data    = 2.2 * cm
    col_tipo    = 3.0 * cm
    col_titolo  = larghezza - col_data - col_tipo - 2.8 * cm - 3.5 * cm
    col_esito   = 2.8 * cm
    col_note    = 3.5 * cm

    intestazione = [
        Paragraph("DATA",   styles["tabella_header"]),
        Paragraph("TIPO",   styles["tabella_header"]),
        Paragraph("TITOLO", styles["tabella_header"]),
        Paragraph("ESITO",  styles["tabella_header"]),
        Paragraph("NOTE",   styles["tabella_header"]),
    ]

    col_widths = [col_data, col_tipo, col_titolo, col_esito, col_note]
    rows = [intestazione]

    if not attivita:
        vuota = [Paragraph("Nessuna attività registrata.", styles["tabella_cella"])]
        rows.append(vuota + [""] * (len(intestazione) - 1))
    else:
        for att in attivita:
            row = [
                Paragraph(_fmt_date(att.get("data")), styles["tabella_cella_c"]),
                Paragraph(_val(att, "tipo"), styles["tabella_cella"]),
                Paragraph(_val(att, "titolo"), styles["tabella_cella"]),
                Paragraph(_val(att, "esito"), styles["tabella_cella"]),
                Paragraph(_val(att, "note"), styles["tabella_cella"]),
            ]
            rows.append(row)

    ts = TableStyle([
        ("FONTSIZE",     (0, 0), (-1, 0), 8),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BIANCO, GRIGIO_CHIARO]),
        ("LINEBELOW",    (0, 0), (-1, -1), 0.3, GRIGIO_MEDIO),
        *pdf_table_header_style(line_width=2),
        ("BOX",          (0, 0), (-1, -1), 0.5, GRIGIO_MEDIO),
    ])

    return Table(rows, colWidths=col_widths, style=ts, hAlign="LEFT", repeatRows=1)


def _tabella_documenti(documenti: list, styles: dict, larghezza: float) -> Table:
    """Tabella indice documenti del fascicolo."""
    col_nome  = larghezza - 3.0 * cm - 2.5 * cm - 2.0 * cm
    col_tipo  = 3.0 * cm
    col_data  = 2.5 * cm
    col_dim   = 2.0 * cm

    intestazione = [
        Paragraph("NOME DOCUMENTO",  styles["tabella_header"]),
        Paragraph("TIPO",            styles["tabella_header"]),
        Paragraph("DATA CARIC.",     styles["tabella_header"]),
        Paragraph("DIMENSIONE",      styles["tabella_header"]),
    ]

    col_widths = [col_nome, col_tipo, col_data, col_dim]
    rows = [intestazione]

    if not documenti:
        vuota = [Paragraph("Nessun documento allegato.", styles["tabella_cella"])]
        rows.append(vuota + [""] * (len(intestazione) - 1))
    else:
        for doc in documenti:
            row = [
                Paragraph(_val(doc, "nome"), styles["tabella_cella"]),
                Paragraph(_val(doc, "tipo"), styles["tabella_cella"]),
                Paragraph(_fmt_date(doc.get("data_caricamento")), styles["tabella_cella_c"]),
                Paragraph(_fmt_bytes(doc.get("dimensione_bytes")), styles["tabella_cella_c"]),
            ]
            rows.append(row)

    ts = TableStyle([
        ("FONTSIZE",     (0, 0), (-1, 0), 8),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BIANCO, GRIGIO_CHIARO]),
        ("LINEBELOW",    (0, 0), (-1, -1), 0.3, GRIGIO_MEDIO),
        *pdf_table_header_style(line_width=2),
        ("BOX",          (0, 0), (-1, -1), 0.5, GRIGIO_MEDIO),
    ])

    return Table(rows, colWidths=col_widths, style=ts, hAlign="LEFT", repeatRows=1)


def _tabella_scadenze(scadenze: list, styles: dict, larghezza: float) -> Table:
    """Tabella scadenze per lo scadenziario mensile."""
    col_scad    = 2.2 * cm
    col_titolo  = larghezza - col_scad - 2.4 * cm - 3.5 * cm - 2.4 * cm - 1.8 * cm - 1.8 * cm
    col_tipo    = 2.4 * cm
    col_fasc    = 3.5 * cm
    col_prio    = 2.4 * cm
    col_giorni  = 1.8 * cm
    col_per     = 1.8 * cm

    intestazione = [
        Paragraph("SCADENZA",     styles["tabella_header"]),
        Paragraph("TITOLO",       styles["tabella_header"]),
        Paragraph("TIPO",         styles["tabella_header"]),
        Paragraph("FASCICOLO",    styles["tabella_header"]),
        Paragraph("PRIORITÀ",     styles["tabella_header"]),
        Paragraph("GG RESTANTI",  styles["tabella_header"]),
        Paragraph("PERENTORIO",   styles["tabella_header"]),
    ]

    col_widths = [col_scad, col_titolo, col_tipo, col_fasc, col_prio, col_giorni, col_per]
    rows = [intestazione]

    if not scadenze:
        vuota = [Paragraph("Nessuna scadenza nel periodo.", styles["tabella_cella"])]
        rows.append(vuota + [""] * (len(intestazione) - 1))
    else:
        for scad in scadenze:
            # Calcola giorni restanti se non fornito
            giorni_str = _val(scad, "giorni_restanti", "—")
            if giorni_str == "—":
                data_val = scad.get("scadenza") or scad.get("data")
                if data_val:
                    try:
                        if isinstance(data_val, (date, datetime)):
                            target = data_val if isinstance(data_val, date) else data_val.date()
                        else:
                            target = datetime.fromisoformat(str(data_val)).date()
                        delta = (target - date.today()).days
                        giorni_str = str(delta)
                    except (ValueError, TypeError):
                        giorni_str = "—"

            perentorio_raw = scad.get("perentorio")
            if perentorio_raw is True or str(perentorio_raw).upper() in ("TRUE", "SI", "SÌ", "1", "YES"):
                perentorio_str = "Sì"
                per_color = colors.HexColor("#c0392b")
            else:
                perentorio_str = "No"
                per_color = GRIGIO_TESTO

            # Evidenzia scadenze urgenti (<=3 giorni)
            try:
                giorni_int = int(giorni_str)
                if giorni_int < 0:
                    gg_color = colors.HexColor("#c0392b")
                    giorni_str = f"{giorni_str} (SCADUTA)"
                elif giorni_int <= 3:
                    gg_color = colors.HexColor("#e67e22")
                else:
                    gg_color = GRIGIO_TESTO
            except (ValueError, TypeError):
                gg_color = GRIGIO_TESTO

            data_scad = scad.get("scadenza") or scad.get("data")

            row = [
                Paragraph(_fmt_date(data_scad),        styles["tabella_cella_c"]),
                Paragraph(_val(scad, "titolo"),        styles["tabella_cella"]),
                Paragraph(_val(scad, "tipo"),          styles["tabella_cella"]),
                Paragraph(_val(scad, "fascicolo") or _val(scad, "fascicolo_numero"), styles["tabella_cella"]),
                Paragraph(_val(scad, "priorita") or _val(scad, "priorità"), styles["tabella_cella_c"]),
                Paragraph(giorni_str,                  styles["tabella_cella_c"]),
                Paragraph(perentorio_str,              styles["tabella_cella_c"]),
            ]
            rows.append(row)

    ts = TableStyle([
        ("FONTSIZE",     (0, 0), (-1, 0), 8),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BIANCO, GRIGIO_CHIARO]),
        ("LINEBELOW",    (0, 0), (-1, -1), 0.3, GRIGIO_MEDIO),
        *pdf_table_header_style(line_width=2),
        ("BOX",          (0, 0), (-1, -1), 0.5, GRIGIO_MEDIO),
    ])

    return Table(rows, colWidths=col_widths, style=ts, hAlign="LEFT", repeatRows=1)


# ------------------------------------------------------------------ Classe principale

class GeneratoreReport:
    """
    Genera report PDF professionali per fascicoli e scadenze dello studio legale.

    Uso::

        gen = GeneratoreReport()
        path = gen.fascicolo_pdf(fascicolo.to_dict(), "/tmp/fasc_001.pdf", "Studio Rossi")
        path = gen.scadenze_pdf(lista_scadenze, "/tmp/scadenze_marzo.pdf")
    """

    # -------------------------------------------------------------- fascicolo_pdf

    def fascicolo_pdf(
        self,
        fascicolo_dict: dict,
        output_path: str,
        studio_nome: str = "Studio Legale",
    ) -> str:
        """
        Genera un report PDF completo per un fascicolo.

        Parameters
        ----------
        fascicolo_dict:
            Dizionario prodotto da ``Fascicolo.to_dict()``.
        output_path:
            Percorso del file PDF da creare.
        studio_nome:
            Nome dello studio da mostrare nell'intestazione.

        Returns
        -------
        str
            Il percorso assoluto del file PDF generato.
        """
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True) if os.path.dirname(output_path) else None

        styles = _build_styles()

        doc = SimpleDocTemplate(
            output_path,
            pagesize=pagesizes.A4,
            leftMargin=MARGIN_LEFT,
            rightMargin=MARGIN_RIGHT,
            topMargin=MARGIN_TOP,
            bottomMargin=MARGIN_BOTTOM,
        )

        page_w = pagesizes.A4[0] - MARGIN_LEFT - MARGIN_RIGHT
        story  = []

        # ---------- Intestazione studio
        story.append(_intestazione_studio(
            studio_nome,
            "Report Fascicolo",
            f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            styles,
            page_w,
        ))
        story.append(Spacer(1, 0.4 * cm))

        # ---------- Titolo fascicolo
        numero   = _val(fascicolo_dict, "numero")
        titolo_f = _val(fascicolo_dict, "titolo")
        story.append(Paragraph(titolo_f, styles["titolo_fascicolo"]))
        story.append(Paragraph(f"Fascicolo N. {numero}", styles["numero_fascicolo"]))
        story.append(HRFlowable(width=page_w, thickness=1, color=ORO_ACCENTO, spaceAfter=6))

        # ---------- Dati generali
        story.append(_sezione_header("Dati del Fascicolo", styles, page_w))
        story.append(Spacer(1, 0.15 * cm))

        anno_rg  = _val(fascicolo_dict, "anno_rg", "")
        nrg      = _val(fascicolo_dict, "numero_rg", "")
        rg_str   = f"{nrg}/{anno_rg}".strip("/") if (nrg != "—" or anno_rg) else "—"

        campi_generali = [
            ("Numero Fascicolo",    numero),
            ("Titolo",              titolo_f),
            ("Tipo",                _val(fascicolo_dict, "tipo")),
            ("Stato",               _val(fascicolo_dict, "stato")),
            ("Tribunale",           _val(fascicolo_dict, "tribunale")),
            ("N. R.G.",             rg_str),
            ("Giudice",             _val(fascicolo_dict, "giudice")),
            ("Sezione",             _val(fascicolo_dict, "sezione")),
            ("Data Apertura",       _fmt_date(fascicolo_dict.get("data_apertura"))),
            ("Data Chiusura",       _fmt_date(fascicolo_dict.get("data_chiusura"))),
        ]
        story.append(_griglia_campi(campi_generali, styles, page_w, cols=2))
        story.append(Spacer(1, 0.3 * cm))

        # ---------- Parti
        story.append(_sezione_header("Parti e Rappresentanza", styles, page_w))
        story.append(Spacer(1, 0.15 * cm))

        campi_parti = [
            ("Cliente",             _val(fascicolo_dict, "nome_cliente")),
            ("Controparte",         _val(fascicolo_dict, "controparte")),
            ("Avvocato Referente",  _val(fascicolo_dict, "avvocato_referente")),
            ("Avvocato Dominus",    _val(fascicolo_dict, "avvocato_dominus")),
        ]
        story.append(_griglia_campi(campi_parti, styles, page_w, cols=2))
        story.append(Spacer(1, 0.3 * cm))

        # ---------- Oggetto
        oggetto = fascicolo_dict.get("oggetto", "")
        if oggetto and str(oggetto).strip():
            story.append(_sezione_header("Oggetto della Controversia", styles, page_w))
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph(str(oggetto), styles["note_testo"]))
            story.append(Spacer(1, 0.3 * cm))

        # ---------- Attività processuali
        attivita = fascicolo_dict.get("attivita") or []
        story.append(_sezione_header(
            f"Attività Processuali ({len(attivita)} registrate)",
            styles, page_w,
        ))
        story.append(Spacer(1, 0.15 * cm))
        story.append(_tabella_attivita(attivita, styles, page_w))
        story.append(Spacer(1, 0.3 * cm))

        # ---------- Indice documenti
        documenti = fascicolo_dict.get("documenti") or []
        story.append(_sezione_header(
            f"Indice Documenti ({len(documenti)} allegati)",
            styles, page_w,
        ))
        story.append(Spacer(1, 0.15 * cm))
        story.append(_tabella_documenti(documenti, styles, page_w))
        story.append(Spacer(1, 0.3 * cm))

        # ---------- Note
        note = fascicolo_dict.get("note", "")
        if note and str(note).strip():
            story.append(_sezione_header("Stato Corrente / Note", styles, page_w))
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph(str(note), styles["note_testo"]))
            story.append(Spacer(1, 0.3 * cm))

        # ---------- Footer tramite onFirstPage / onLaterPages
        def _add_footer(canvas, doc_obj):
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#888888"))
            footer_text = (
                f"{studio_nome}  —  Report Fascicolo N. {numero}  —  "
                f"Pag. {doc_obj.page}"
            )
            canvas.drawCentredString(
                pagesizes.A4[0] / 2,
                MARGIN_BOTTOM / 2,
                footer_text,
            )
            canvas.restoreState()

        doc.build(story, onFirstPage=_add_footer, onLaterPages=_add_footer)
        return output_path

    # -------------------------------------------------------------- scadenze_pdf

    def scadenze_pdf(
        self,
        scadenze: list,
        output_path: str,
        titolo: str = "Scadenziario",
        studio_nome: str = "Studio Legale",
    ) -> str:
        """
        Genera un report PDF dello scadenziario.

        Parameters
        ----------
        scadenze:
            Lista di dizionari con le scadenze da riportare.
            Ogni elemento può avere: scadenza/data, titolo, tipo, fascicolo,
            priorita/priorità, giorni_restanti, perentorio.
        output_path:
            Percorso del file PDF da creare.
        titolo:
            Titolo del report (es. "Scadenziario Marzo 2026").
        studio_nome:
            Nome dello studio da mostrare nell'intestazione.

        Returns
        -------
        str
            Il percorso assoluto del file PDF generato.
        """
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True) if os.path.dirname(output_path) else None

        styles = _build_styles()

        doc = SimpleDocTemplate(
            output_path,
            pagesize=pagesizes.A4,
            leftMargin=MARGIN_LEFT,
            rightMargin=MARGIN_RIGHT,
            topMargin=MARGIN_TOP,
            bottomMargin=MARGIN_BOTTOM,
        )

        page_w = pagesizes.A4[0] - MARGIN_LEFT - MARGIN_RIGHT
        story  = []

        # ---------- Intestazione studio
        story.append(_intestazione_studio(
            studio_nome,
            titolo,
            f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            styles,
            page_w,
        ))
        story.append(Spacer(1, 0.4 * cm))

        # ---------- Titolo sezione
        story.append(Paragraph(titolo, styles["titolo_fascicolo"]))
        story.append(Paragraph(
            f"Totale scadenze: {len(scadenze)}",
            styles["numero_fascicolo"],
        ))
        story.append(HRFlowable(width=page_w, thickness=1, color=ORO_ACCENTO, spaceAfter=6))

        # ---------- Tabella scadenze
        story.append(_sezione_header("Elenco Scadenze", styles, page_w))
        story.append(Spacer(1, 0.15 * cm))
        story.append(_tabella_scadenze(scadenze, styles, page_w))
        story.append(Spacer(1, 0.4 * cm))

        # ---------- Legenda
        legenda_items = [
            ("GG RESTANTI < 0",   "Scadenza già trascorsa"),
            ("GG RESTANTI 0–3",   "Scadenza imminente (attenzione)"),
            ("PERENTORIO = Sì",   "Termine perentorio — non prorogabile"),
        ]
        story.append(_sezione_header("Legenda", styles, page_w))
        story.append(Spacer(1, 0.15 * cm))
        for codice, desc in legenda_items:
            story.append(Paragraph(
                f"<b>{codice}:</b>  {desc}",
                styles["note_testo"],
            ))
        story.append(Spacer(1, 0.2 * cm))

        # ---------- Footer
        def _add_footer(canvas, doc_obj):
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#888888"))
            footer_text = (
                f"{studio_nome}  —  {titolo}  —  Pag. {doc_obj.page}"
            )
            canvas.drawCentredString(
                pagesizes.A4[0] / 2,
                MARGIN_BOTTOM / 2,
                footer_text,
            )
            canvas.restoreState()

        doc.build(story, onFirstPage=_add_footer, onLaterPages=_add_footer)
        return output_path


    # -------------------------------------------------------------- faldone_pdf

    def faldone_pdf(
        self,
        cliente_dict: dict,
        fascicoli_per_tipo: dict,
        scadenze_aperte: list,
        timeline: list,
        note: dict,
        studio_nome: str,
        output_path: str,
        stats: dict,
    ) -> str:
        """
        Genera il PDF «Indice Faldone Digitale» per un cliente.

        Parameters
        ----------
        cliente_dict      : dati anagrafici del cliente (dict o to_dict())
        fascicoli_per_tipo: {tipo_str: [fascicolo_dict, ...]}
        scadenze_aperte   : lista di dict con chiavi data_scadenza, titolo,
                            priorita, perentorio, fascicolo_numero
        timeline          : lista di dict con data, tipo, titolo, esito,
                            fascicolo_numero
        note              : {sezione: testo} — note interne per sezione
        studio_nome       : nome dello studio (intestazione)
        output_path       : percorso file PDF da creare
        stats             : {n_doc, n_dep, n_att, n_scad}
        """
        output_path = os.path.abspath(output_path)
        if os.path.dirname(output_path):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

        styles = _build_styles()
        doc = SimpleDocTemplate(
            output_path,
            pagesize=pagesizes.A4,
            leftMargin=MARGIN_LEFT,
            rightMargin=MARGIN_RIGHT,
            topMargin=MARGIN_TOP,
            bottomMargin=MARGIN_BOTTOM,
        )
        page_w = pagesizes.A4[0] - MARGIN_LEFT - MARGIN_RIGHT
        story  = []

        nome_cliente = cliente_dict.get("nome_completo") or (
            (cliente_dict.get("nome", "") + " " + cliente_dict.get("cognome", "")).strip()
            or cliente_dict.get("ragione_sociale", "—")
        )
        cf = cliente_dict.get("codice_fiscale") or cliente_dict.get("partita_iva") or ""

        # ---------- Intestazione studio
        story.append(_intestazione_studio(
            studio_nome,
            "Faldone Digitale",
            f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            styles, page_w,
        ))
        story.append(Spacer(1, 0.4 * cm))

        # ---------- Titolo
        story.append(Paragraph(nome_cliente, styles["titolo_fascicolo"]))
        if cf:
            story.append(Paragraph(f"C.F. / P.IVA: {cf}", styles["numero_fascicolo"]))
        story.append(HRFlowable(width=page_w, thickness=1, color=ORO_ACCENTO, spaceAfter=6))

        # ---------- Riepilogo numerico
        story.append(_sezione_header("Riepilogo Faldone", styles, page_w))
        story.append(Spacer(1, 0.15 * cm))
        n_attive = sum(len(v) for v in fascicoli_per_tipo.values())
        totali   = [
            ("Pratiche attive",     str(n_attive)),
            ("Scadenze aperte",     str(stats.get("n_scad", 0))),
            ("Documenti totali",    str(stats.get("n_doc", 0))),
            ("Depositi PCT",        str(stats.get("n_dep", 0))),
            ("Attività registrate", str(stats.get("n_att", 0))),
            ("Tipologie presenti",  str(len(fascicoli_per_tipo))),
        ]
        story.append(_griglia_campi(totali, styles, page_w, cols=3))
        story.append(Spacer(1, 0.4 * cm))

        # ---------- Pratiche per tipo
        _LABEL = {
            "CIVILE": "Civile", "PENALE": "Penale",
            "AMMINISTRATIVO": "Amministrativo", "STRAGIUDIZIALE": "Stragiudiziale",
            "CONSULENZA": "Consulenza", "LAVORO": "Lavoro",
            "FAMIGLIA": "Famiglia", "SUCCESSIONI": "Successioni", "ALTRO": "Altro",
        }
        story.append(_sezione_header("Pratiche per Tipologia", styles, page_w))
        story.append(Spacer(1, 0.15 * cm))

        for tipo, fascicoli in fascicoli_per_tipo.items():
            label = _LABEL.get(tipo, tipo.replace("_", " ").title())
            story.append(Paragraph(
                f"<b>▸ {label} ({len(fascicoli)} pratiCA{'a' if len(fascicoli)==1 else 'he'})</b>",
                styles["campo_label"],
            ))
            rows = [["N.", "Titolo", "Stato", "Tribunale", "Apertura"]]
            for i, f in enumerate(fascicoli, 1):
                rows.append([
                    str(i),
                    f.get("titolo", "—")[:45],
                    f.get("stato", "—").replace("_", " "),
                    (f.get("tribunale") or "—")[:25],
                    _fmt_date(f.get("data_apertura")),
                ])
            t = Table(rows, colWidths=[0.5*cm, page_w*0.42, page_w*0.14, page_w*0.28, page_w*0.14])
            t.setStyle(TableStyle([
                *pdf_table_header_style(),
                ("FONTSIZE",     (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BIANCO, GRIGIO_CHIARO]),
                ("GRID",         (0, 0), (-1, -1), 0.3, GRIGIO_MEDIO),
                ("ALIGN",        (0, 0), (0, -1),  "CENTER"),
                ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",   (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.3 * cm))

        # ---------- Scadenze aperte
        if scadenze_aperte:
            story.append(Spacer(1, 0.2 * cm))
            story.append(_sezione_header("Scadenze Aperte", styles, page_w))
            story.append(Spacer(1, 0.15 * cm))
            sc_rows = [["Data", "Fascicolo", "Titolo", "Priorità", "Per."]]
            for sc in scadenze_aperte[:30]:
                sc_rows.append([
                    _fmt_date(sc.get("data_scadenza")),
                    sc.get("fascicolo_numero", "—"),
                    sc.get("titolo", "—")[:40],
                    sc.get("priorita", "—"),
                    "Sì" if sc.get("perentorio") else "No",
                ])
            t2 = Table(sc_rows, colWidths=[page_w*0.14, page_w*0.15, page_w*0.45, page_w*0.14, page_w*0.08])
            t2.setStyle(TableStyle([
                *pdf_table_header_style(),
                ("FONTSIZE",     (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BIANCO, GRIGIO_CHIARO]),
                ("GRID",         (0, 0), (-1, -1), 0.3, GRIGIO_MEDIO),
                ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",   (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
            ]))
            story.append(t2)
            story.append(Spacer(1, 0.4 * cm))

        # ---------- Timeline (ultime 20 attività)
        if timeline:
            story.append(_sezione_header("Ultime Attività", styles, page_w))
            story.append(Spacer(1, 0.15 * cm))
            tl_rows = [["Data", "Fascicolo", "Tipo", "Titolo", "Esito"]]
            for ev in timeline[:20]:
                tl_rows.append([
                    _fmt_date(ev.get("data")),
                    ev.get("fascicolo_numero", "—"),
                    ev.get("tipo", "—").replace("_", " "),
                    ev.get("titolo", "—")[:35],
                    ev.get("esito", "—").replace("_", " "),
                ])
            t3 = Table(tl_rows, colWidths=[page_w*0.13, page_w*0.15, page_w*0.18, page_w*0.38, page_w*0.16])
            t3.setStyle(TableStyle([
                *pdf_table_header_style(),
                ("FONTSIZE",     (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BIANCO, GRIGIO_CHIARO]),
                ("GRID",         (0, 0), (-1, -1), 0.3, GRIGIO_MEDIO),
                ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",   (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
            ]))
            story.append(t3)
            story.append(Spacer(1, 0.4 * cm))

        # ---------- Note interne (solo se presenti)
        note_testo = {k: v for k, v in note.items() if v and v.strip()}
        if note_testo:
            story.append(_sezione_header("Note Interne Faldone", styles, page_w))
            story.append(Spacer(1, 0.1 * cm))
            story.append(Paragraph(
                "<i>Documento riservato — uso interno studio legale</i>",
                styles["note_testo"],
            ))
            story.append(Spacer(1, 0.15 * cm))
            for sez, testo in note_testo.items():
                story.append(Paragraph(f"<b>{sez}:</b>", styles["campo_label"]))
                story.append(Paragraph(testo.replace("\n", "<br/>"), styles["note_testo"]))
                story.append(Spacer(1, 0.2 * cm))

        # ---------- Footer
        def _add_footer(canvas, doc_obj):
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#888888"))
            canvas.drawCentredString(
                pagesizes.A4[0] / 2,
                MARGIN_BOTTOM / 2,
                f"{studio_nome}  —  Faldone Digitale: {nome_cliente}  —  Pag. {doc_obj.page}",
            )
            canvas.restoreState()

        doc.build(story, onFirstPage=_add_footer, onLaterPages=_add_footer)
        return output_path


# ------------------------------------------------------------------ Funzioni di convenienza

_generatore = GeneratoreReport()


def fascicolo_pdf(
    fascicolo_dict: dict,
    output_path: str,
    studio_nome: str = "Studio Legale",
) -> str:
    """Funzione di convenienza — crea un report PDF del fascicolo."""
    return _generatore.fascicolo_pdf(fascicolo_dict, output_path, studio_nome)


def scadenze_pdf(
    scadenze: list,
    output_path: str,
    titolo: str = "Scadenziario",
    studio_nome: str = "Studio Legale",
) -> str:
    """Funzione di convenienza — crea un report PDF dello scadenziario."""
    return _generatore.scadenze_pdf(scadenze, output_path, titolo, studio_nome)


def lista_fascicoli_pdf(
    fascicoli: list,
    output_path: str,
    titolo: str = "Elenco Fascicoli",
    studio_nome: str = "Studio Legale",
) -> str:
    """Genera un report PDF con la lista dei fascicoli."""
    output_path = os.path.abspath(output_path)
    if os.path.dirname(output_path):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

    styles = _build_styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=pagesizes.A4,
        leftMargin=MARGIN_LEFT, rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
    )
    page_w = pagesizes.A4[0] - MARGIN_LEFT - MARGIN_RIGHT
    story = []
    story.append(_intestazione_studio(
        studio_nome, titolo,
        f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        styles, page_w,
    ))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(titolo, styles["titolo_fascicolo"]))
    story.append(Paragraph(f"Totale: {len(fascicoli)} fascicoli", styles["numero_fascicolo"]))
    story.append(HRFlowable(width=page_w, thickness=1, color=ORO_ACCENTO, spaceAfter=6))
    story.append(Spacer(1, 0.2 * cm))

    col_w = [page_w * w for w in [0.12, 0.26, 0.22, 0.20, 0.10, 0.10]]
    rows = [[
        Paragraph("<b>N. RG/Anno</b>", styles["nota"]),
        Paragraph("<b>Titolo / Oggetto</b>", styles["nota"]),
        Paragraph("<b>Cliente</b>", styles["nota"]),
        Paragraph("<b>Tribunale</b>", styles["nota"]),
        Paragraph("<b>Tipo</b>", styles["nota"]),
        Paragraph("<b>Stato</b>", styles["nota"]),
    ]]
    for f in fascicoli:
        rg = f"{f.get('numero_rg','')}/{f.get('anno_rg','')}" if f.get('numero_rg') else "—"
        rows.append([
            Paragraph(rg, styles["nota"]),
            Paragraph(str(f.get("titolo") or f.get("oggetto") or "—")[:60], styles["nota"]),
            Paragraph(str(f.get("nome_cliente") or "—")[:40], styles["nota"]),
            Paragraph(str(f.get("tribunale") or "—")[:35], styles["nota"]),
            Paragraph((f.get("tipo") or "—").replace("_", " ").title(), styles["nota"]),
            Paragraph((f.get("stato") or "—").replace("_", " ").title(), styles["nota"]),
        ])
    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        *pdf_table_header_style(),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BIANCO, GRIGIO_CHIARO]),
        ("GRID", (0, 0), (-1, -1), 0.3, GRIGIO_MEDIO), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(tbl)

    def _f(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawCentredString(pagesizes.A4[0] / 2, MARGIN_BOTTOM / 2,
            f"{studio_nome}  —  {titolo}  —  Pag. {doc_obj.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=_f, onLaterPages=_f)
    return output_path


def lista_clienti_pdf(
    clienti: list,
    output_path: str,
    titolo: str = "Elenco Clienti",
    studio_nome: str = "Studio Legale",
) -> str:
    """Genera un report PDF con la lista dei clienti."""
    output_path = os.path.abspath(output_path)
    if os.path.dirname(output_path):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

    styles = _build_styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=pagesizes.A4,
        leftMargin=MARGIN_LEFT, rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
    )
    page_w = pagesizes.A4[0] - MARGIN_LEFT - MARGIN_RIGHT
    story = []
    story.append(_intestazione_studio(
        studio_nome, titolo,
        f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        styles, page_w,
    ))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(titolo, styles["titolo_fascicolo"]))
    story.append(Paragraph(f"Totale: {len(clienti)} clienti", styles["numero_fascicolo"]))
    story.append(HRFlowable(width=page_w, thickness=1, color=ORO_ACCENTO, spaceAfter=6))
    story.append(Spacer(1, 0.2 * cm))

    col_w = [page_w * w for w in [0.30, 0.10, 0.22, 0.18, 0.10, 0.10]]
    rows = [[
        Paragraph("<b>Nome / Ragione Sociale</b>", styles["nota"]),
        Paragraph("<b>Tipo</b>", styles["nota"]),
        Paragraph("<b>Email / PEC</b>", styles["nota"]),
        Paragraph("<b>Telefono</b>", styles["nota"]),
        Paragraph("<b>Stato</b>", styles["nota"]),
        Paragraph("<b>Doc. ID</b>", styles["nota"]),
    ]]
    for c in clienti:
        rec = c.get("recapiti") or {}
        doc_str = "⚠ scaduto" if (c.get("documento") or {}).get("scaduto") else ""
        # nome_completo non è nel dict (è @property) — ricostruisco
        nome = (
            c.get("nome_completo")
            or c.get("ragione_sociale")
            or f"{c.get('cognome', '')} {c.get('nome', '')}".strip()
            or "—"
        )
        # tipo: PERSONA_FISICA → Persona Fisica
        tipo_raw = c.get("tipo") or ""
        tipo_fmt = tipo_raw.replace("_", " ").title() if tipo_raw else "—"
        rows.append([
            Paragraph(nome[:50], styles["nota"]),
            Paragraph(tipo_fmt, styles["nota"]),
            Paragraph(str(rec.get("email") or rec.get("pec") or "—")[:35], styles["nota"]),
            Paragraph(str(rec.get("telefono") or rec.get("cellulare") or "—"), styles["nota"]),
            Paragraph(str(c.get("stato") or "—"), styles["nota"]),
            Paragraph(doc_str, styles["nota"]),
        ])
    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        *pdf_table_header_style(),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BIANCO, GRIGIO_CHIARO]),
        ("GRID", (0, 0), (-1, -1), 0.3, GRIGIO_MEDIO), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(tbl)

    def _f(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawCentredString(pagesizes.A4[0] / 2, MARGIN_BOTTOM / 2,
            f"{studio_nome}  —  {titolo}  —  Pag. {doc_obj.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=_f, onLaterPages=_f)
    return output_path


def faldone_pdf(
    cliente_dict: dict,
    fascicoli_per_tipo: dict,
    scadenze_aperte: list,
    timeline: list,
    note: dict,
    studio_nome: str,
    output_path: str,
    stats: dict,
) -> str:
    """Funzione di convenienza — genera l'indice PDF del faldone digitale."""
    return _generatore.faldone_pdf(
        cliente_dict=cliente_dict,
        fascicoli_per_tipo=fascicoli_per_tipo,
        scadenze_aperte=scadenze_aperte,
        timeline=timeline,
        note=note,
        studio_nome=studio_nome,
        output_path=output_path,
        stats=stats,
    )
