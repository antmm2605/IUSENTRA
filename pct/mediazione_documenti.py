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


#: Bit del flag /F di un'annotazione PDF (ISO 32000-1, tabella 165): 2 =
#: Hidden, 32 = NoView. Una casella cosi' marcata il PDF non la mostra.
_ANNOTAZIONE_NON_VISIBILE = 2 | 32


def _casella_visibile(doc, widget) -> bool:
    """Se il PDF dichiara che questa casella si vede.

    Un modulo che aggiunge righe con un pulsante (il «+ Aggiungi componente»
    dei moduli per il nucleo familiare) tiene nel file anche le righe non
    ancora aggiunte, marcate nascoste: l'autocertificazione del contributo
    unificato ha 284 caselle di cui 250 nascoste, fino a sette sovrapposte
    sulla stessa cella. Disegnarle tutte significa coprire le caselle vere
    con caselle invisibili nel PDF ma cliccabili nel portale: chi compila
    scrive in una e ne vede un'altra, cioe' non riesce a compilare.

    Non si sceglie «la piu' grande» o «la prima»: si legge quello che il
    documento dichiara. Se il flag non e' leggibile, la casella resta —
    meglio una casella di troppo che un campo del modulo che sparisce.
    """
    try:
        tipo, valore = doc.xref_get_key(widget.xref, "F")
    except Exception:
        return True
    if tipo != "int":
        return True
    try:
        flag = int(valore)
    except (TypeError, ValueError):
        return True
    return not flag & _ANNOTAZIONE_NON_VISIBILE


def _rendi_visibile(doc, widget) -> None:
    """Toglie alla casella il bit Hidden, lasciando intatti gli altri flag."""
    try:
        tipo, valore = doc.xref_get_key(widget.xref, "F")
        flag = int(valore) if tipo == "int" else 0
    except Exception:
        flag = 0
    doc.xref_set_key(widget.xref, "F", str((flag & ~_ANNOTAZIONE_NON_VISIBILE) | 4))


def _nascondi(doc, widget) -> None:
    """Rimette il bit Hidden: la casella torna quella che il modulo non mostra."""
    try:
        tipo, valore = doc.xref_get_key(widget.xref, "F")
        flag = int(valore) if tipo == "int" else 0
    except Exception:
        flag = 0
    doc.xref_set_key(widget.xref, "F", str(flag | 2))


def campi_pdf(raw, *, includi_da_attivare: bool = False):
    """I campi predisposti del modulo.

    Di norma solo quelli che il PDF mostra. Con ``includi_da_attivare`` si
    ottengono anche le righe che il documento tiene pronte ma nascoste — le
    righe del nucleo familiare che nel PDF si aggiungono con un pulsante —
    ciascuna marcata ``visibile: False``: chi compila le puo' chiedere una
    alla volta, e solo quelle usate diventano visibili nella copia salvata.
    Nella stessa lettura entrano anche le caselle che il modulo usa per la
    propria impaginazione, dichiarate di sola lettura perche' non si
    compilano: servono a sapere quante righe il foglio regge.
    """
    import fitz

    compilabili = {
        fitz.PDF_WIDGET_TYPE_TEXT,
        fitz.PDF_WIDGET_TYPE_CHECKBOX,
        fitz.PDF_WIDGET_TYPE_COMBOBOX,
        fitz.PDF_WIDGET_TYPE_LISTBOX,
    }
    campi = []
    with fitz.open(stream=raw, filetype="pdf") as doc:
        for pagina in doc:
            for w in pagina.widgets() or []:
                impaginazione = w.field_type == fitz.PDF_WIDGET_TYPE_BUTTON
                if w.field_type not in compilabili and not (includi_da_attivare and impaginazione):
                    continue
                visibile = _casella_visibile(doc, w)
                if not visibile and not includi_da_attivare:
                    continue
                campi.append({
                    "nome": w.field_name,
                    "etichetta": w.field_label or w.field_name,
                    "pagina": pagina.number + 1,
                    "visibile": visibile,
                    "xref": w.xref,
                    "tipo": w.field_type_string,
                    "valore": w.field_value or "",
                    "opzioni": list(w.choice_values or []),
                    # Un pulsante non si compila: e' parte del modulo, non un campo.
                    "sola_lettura": bool(w.field_flags & 1) or impaginazione,
                    "richiesto": bool(w.field_flags & 2),
                    "max_caratteri": w.text_maxlen or 10000,
                    "selezionato": (
                        bool(w.field_value and w.field_value != "Off")
                        if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX
                        else False
                    ),
                    "rettangolo": [
                        w.rect.x0 / pagina.rect.width,
                        w.rect.y0 / pagina.rect.height,
                        w.rect.width / pagina.rect.width,
                        w.rect.height / pagina.rect.height,
                    ],
                })
    return campi


def righe_disponibili(raw) -> dict[str, int]:
    """Quante righe della tabella il modulo mostra e quante ne puo' mostrare."""
    from pct.moduli_compilabili import impaginazioni_dichiarate, righe_gia_mostrate

    campi = campi_pdf(raw, includi_da_attivare=True)
    impaginazioni = impaginazioni_dichiarate(campi)
    return {
        "mostrate": righe_gia_mostrate(campi),
        "massimo": max(impaginazioni) if impaginazioni else righe_gia_mostrate(campi),
    }


def imposta_righe(raw, righe: int):
    """Il modulo con la tabella portata a ``righe``, senza toccare i valori.

    Serve a far vedere a chi compila il foglio come sara' davvero: la griglia
    con quel numero di righe e le caselle al posto che avranno. Oltre le
    impaginazioni che il modulo si porta dietro non si va.
    """
    import fitz

    from pct.moduli_compilabili import (
        caselle_per_impaginazione,
        impaginazioni_dichiarate,
        righe_gia_mostrate,
    )

    campi = campi_pdf(raw, includi_da_attivare=True)
    impaginazioni = impaginazioni_dichiarate(campi)
    mostrate = righe_gia_mostrate(campi)
    righe = int(righe or 0)
    if not impaginazioni or righe <= mostrate:
        return raw
    if righe not in impaginazioni:
        raise ValueError(
            f"Il modulo prevede al massimo {max(impaginazioni)} righe del nucleo familiare: "
            "per altri componenti serve un foglio aggiuntivo."
        )
    caselle = caselle_per_impaginazione(campi, righe)
    with fitz.open(stream=raw, filetype="pdf") as doc:
        _applica_impaginazione(doc, impaginazioni, caselle, righe)
        return doc.tobytes(garbage=4, deflate=True)


def _applica_impaginazione(doc, impaginazioni, caselle, righe: int) -> None:
    """Mostra la griglia di ``righe`` e, di ogni campo, la casella che le appartiene."""
    nomi_griglia = {casella["nome"]: numero for numero, casella in impaginazioni.items()}
    for page in doc:
        for widget in page.widgets() or []:
            nome = widget.field_name
            if nome in nomi_griglia:
                if nomi_griglia[nome] == righe:
                    _rendi_visibile(doc, widget)
                else:
                    _nascondi(doc, widget)
            elif nome in caselle:
                if caselle[nome] == widget.xref:
                    _rendi_visibile(doc, widget)
                else:
                    _nascondi(doc, widget)


def compila_pdf(raw, values):
    import fitz

    if not isinstance(values, dict) or len(values) > 1000:
        raise ValueError("Campi del modulo non validi.")
    letti = campi_pdf(raw, includi_da_attivare=True)
    fields = {}
    for field in letti:
        # Fra i duplicati di uno stesso campo vince quello che il PDF mostra.
        if field["nome"] not in fields or field.get("visibile"):
            fields[field["nome"]] = field
    if not fields:
        raise ValueError("Questo PDF non contiene campi di compilazione predisposti dall'organismo.")
    if any(name not in fields or fields[name]["sola_lettura"] for name in values):
        raise ValueError("Uno dei campi non esiste o non è modificabile.")
    # Righe in piu' del nucleo familiare. Il modulo non puo' ridisegnare la
    # griglia: se la tiene pronta, una per ogni numero di righe. Si sceglie
    # l'impaginazione che serve e, di ogni campo, la casella che le appartiene:
    # tutto il resto resta nascosto, altrimenti lo stesso dato comparirebbe in
    # piu' punti del foglio.
    from pct.moduli_compilabili import (
        caselle_per_impaginazione,
        impaginazioni_dichiarate,
        righe_gia_mostrate,
        _riga_dal_nome,
    )

    impaginazioni = impaginazioni_dichiarate(letti)
    mostrate = righe_gia_mostrate(letti)
    compilate = [
        _riga_dal_nome(nome)[1]
        for nome, valore in values.items()
        if _riga_dal_nome(nome)[0] and valore not in ("", False, None)
    ]
    righe_volute = max([mostrate, *compilate]) if compilate else mostrate
    if impaginazioni and righe_volute > mostrate:
        if righe_volute not in impaginazioni:
            raise ValueError(
                f"Il modulo prevede al massimo {max(impaginazioni)} righe del nucleo familiare: "
                "per altri componenti serve un foglio aggiuntivo."
            )
        caselle_attive = caselle_per_impaginazione(letti, righe_volute)
        impaginazione_attiva = impaginazioni[righe_volute]
    else:
        caselle_attive = {}
        impaginazione_attiva = None

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
        if impaginazione_attiva is not None:
            _applica_impaginazione(doc, impaginazioni, caselle_attive, righe_volute)
        doc.scrub(javascript=True, reset_fields=False, reset_responses=False, clean_pages=False,
                  hidden_text=False, redactions=False, remove_links=False, metadata=False, xml_metadata=False)
        return doc.tobytes(garbage=4, deflate=True)
