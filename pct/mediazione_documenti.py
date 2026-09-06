"""Bozza di istanza e compilazione dei campi nativi dei modelli PDF."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape


def bozza_istanza(payload):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    stream = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BodyIT", fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=8))
    styles.add(ParagraphStyle(name="CaptionIT", fontSize=9, leading=12, textColor=colors.HexColor("#43546B"), spaceAfter=10))
    story = [Paragraph("Istanza di mediazione", styles["Title"]),
             Paragraph("BOZZA DA VERIFICARE - Non costituisce prova di deposito e non sostituisce il modulo prescritto dall'organismo.", styles["CaptionIT"])]

    def section(label, value):
        if not value:
            value = "Da completare"
        story.extend([Paragraph(escape(label), styles["Heading2"]),
                      Paragraph(escape(str(value)).replace("\n", "<br/>"), styles["BodyIT"])])

    org = payload.get("organismo") or {}
    seat = org.get("sede") or {}
    section("Organismo destinatario", " - ".join(filter(None, [org.get("nome"), seat.get("city"), seat.get("address")])) )
    section("Procedimento", {"volontaria": "Mediazione volontaria", "obbligatoria": "Mediazione quale condizione di procedibilità", "demandata": "Mediazione demandata dal giudice", "clausola": "Mediazione prevista da clausola contrattuale/statutaria"}.get(payload.get("regime"), ""))
    for index, party in enumerate(payload.get("parti", []), 1):
        values = [party.get("nome", "")]
        for key, label in (("codice_fiscale", "C.F. / P. IVA"), ("indirizzo", "Indirizzo"), ("pec", "PEC"),
                           ("email", "Email"), ("difensore", "Difensore"), ("rappresentante", "Rappresentante / delegato")):
            if party.get(key):
                values.append(f"{label}: {party[key]}")
        role = {"istante": "istante", "invitata": "invitata", "aderente": "aderente"}.get(party.get("ruolo"), "")
        section(f"Parte {index} - {role}", "\n".join(values))
    for key, label in (("oggetto", "Oggetto della controversia"), ("ragioni", "Ragioni della pretesa"),
                       ("competenza", "Competenza territoriale")):
        section(label, payload.get(key))
    section("Valore della controversia", "Indeterminabile" if payload.get("valore_indeterminabile") else (f"€ {payload['valore']}" if payload.get('valore') else "Da completare"))
    story.extend([Spacer(1, 10 * mm), Paragraph("Luogo e data ____________________", styles["BodyIT"]),
                  Paragraph("Sottoscrizioni e allegati secondo le istruzioni dell'organismo", styles["BodyIT"])])

    def footer(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(190 * mm, 12 * mm, f"Bozza di istanza - Pagina {document.page}")

    SimpleDocTemplate(stream, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                      topMargin=18 * mm, bottomMargin=22 * mm, title="Bozza istanza di mediazione",
                      author="").build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()


def campi_pdf(raw):
    import fitz

    with fitz.open(stream=raw, filetype="pdf") as doc:
        return [{"nome": w.field_name, "etichetta": w.field_label or w.field_name, "pagina": p.number + 1,
                 "tipo": w.field_type_string, "valore": w.field_value or "", "opzioni": list(w.choice_values or []),
                 "sola_lettura": bool(w.field_flags & 1), "richiesto": bool(w.field_flags & 2),
                 "max_caratteri": w.text_maxlen or 10000,
                 "selezionato": bool(w.field_value and w.field_value != "Off") if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX else False,
                 "rettangolo": [w.rect.x0 / p.rect.width, w.rect.y0 / p.rect.height, w.rect.width / p.rect.width, w.rect.height / p.rect.height]}
                for p in doc for w in (p.widgets() or []) if w.field_type in {
                    fitz.PDF_WIDGET_TYPE_TEXT, fitz.PDF_WIDGET_TYPE_CHECKBOX,
                    fitz.PDF_WIDGET_TYPE_COMBOBOX, fitz.PDF_WIDGET_TYPE_LISTBOX}]


def compila_pdf(raw, values):
    import fitz

    if not isinstance(values, dict) or len(values) > 1000:
        raise ValueError("Campi del modulo non validi.")
    fields = {field["nome"]: field for field in campi_pdf(raw)}
    if not fields:
        raise ValueError("Questo PDF non contiene campi di compilazione predisposti dall'organismo.")
    if any(name not in fields or fields[name]["sola_lettura"] for name in values):
        raise ValueError("Uno dei campi non esiste o non è modificabile.")
    with fitz.open(stream=raw, filetype="pdf") as doc:
        if any(w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE and w.field_value for p in doc for w in (p.widgets() or [])):
            raise ValueError("Il documento contiene una firma: acquisisci un modulo vuoto prima di compilarlo.")
        for page in doc:
            for widget in page.widgets() or []:
                if widget.field_name not in values:
                    continue
                value = values[widget.field_name]
                if widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                    if not isinstance(value, bool):
                        raise ValueError("Selezione non valida.")
                    widget.field_value = widget.on_state() if value else "Off"
                else:
                    if not isinstance(value, str) or len(value) > fields[widget.field_name]["max_caratteri"]:
                        raise ValueError("Testo oltre il limite del campo.")
                    if widget.choice_values and value not in widget.choice_values:
                        raise ValueError("Opzione non presente nel modulo.")
                    widget.field_value = value
                widget.update()
        doc.scrub(javascript=True, reset_fields=False, reset_responses=False, clean_pages=False,
                  hidden_text=False, redactions=False, remove_links=False, metadata=False, xml_metadata=False)
        return doc.tobytes(garbage=4, deflate=True)
