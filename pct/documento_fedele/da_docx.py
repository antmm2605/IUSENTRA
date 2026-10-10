"""Il DOCX letto direttamente, senza passare per un convertitore esterno.

Un atto che torna dall'editor, viene modificato in Word e rientra deve
ritrovare quello che aveva: carattere, corpo, colore, sottolineature,
allineamenti, rientri, interlinea, elenchi, tabelle con intestazioni e sfondi,
formato e margini della pagina.

Prima questa strada aveva due varianti, tutte e due con dei buchi. La rotta di
importazione usava `mammoth`, che tiene grassetto, corsivo, tabelle ed elenchi
e butta via tutto il resto — misurato su un atto: sottolineato, colore,
allineamenti, rientri, carattere, corpo e margini. `converti_docx` chiamava
LibreOffice per fare DOCX -> PDF e poi rileggeva il PDF: fedele, ma richiede un
programma da mezzo giga sul server e un processo esterno con il suo timeout, e
sul server di IUSENTRA quel programma non c'e'.

Qui il DOCX si legge com'e', con python-docx, e si scrive nell'HTML
dell'editor riusando `_html_tratti`: la stessa resa dei documenti che arrivano
da un PDF, cosi' un atto ha lo stesso aspetto da qualunque parte entri.

Solo python-docx (MIT). Nessun programma esterno, nessuna libreria AGPL.
"""

from __future__ import annotations

import base64
import html as html_lib
from pathlib import Path

from docx import Document as ApriDocx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import RGBColor

from .modello import DocumentoConvertito, PaginaConvertita, Tratto
from .paragrafi import _html_tratti
from .taratura import pila_font

def _pt(valore: float) -> str:
    """Le misure Word sono twip: non arrotondare a un decimo di punto."""
    return f"{valore:g}"


#: Gli allineamenti di Word, tradotti in quelli del foglio di stile.
ALLINEAMENTI = {
    WD_ALIGN_PARAGRAPH.LEFT: "left",
    WD_ALIGN_PARAGRAPH.CENTER: "center",
    WD_ALIGN_PARAGRAPH.RIGHT: "right",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
}

#: Corpo e carattere da usare quando il documento non li dichiara da nessuna
#: parte: sono quelli che Word stesso mette di suo.
CORPO_PREDEFINITO = 11.0
CARATTERE_PREDEFINITO = "Calibri"

#: Un paragrafo con questo stile e' una voce di elenco.
STILI_ELENCO_NUMERATO = ("list number", "elenco numerato")
STILI_ELENCO_PUNTATO = ("list bullet", "list paragraph", "elenco puntato")

NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocxError(ValueError):
    """Il documento non si apre o non e' un DOCX."""


# ---------------------------------------------------------------------------
# Quello che Word non scrive sul pezzo ma eredita dallo stile
# ---------------------------------------------------------------------------

def _eredita(oggetto, attributo: str, paragrafo, documento):
    """Il valore dichiarato sul tratto, o quello che eredita.

    In un DOCX quasi niente e' scritto dove lo si cerca: il corpo di una parola
    puo' stare sul tratto, sullo stile del paragrafo, sullo stile da cui quello
    discende, o solo nelle impostazioni del documento. Chi legge solo il primo
    livello trova `None` quasi sempre — ed e' il motivo per cui le conversioni
    veloci perdono carattere e corpo.
    """
    valore = getattr(oggetto, attributo, None)
    if valore is not None:
        return valore

    stile = getattr(paragrafo, "style", None)
    visti = 0
    while stile is not None and visti < 8:
        carattere = getattr(stile, "font", None)
        valore = getattr(carattere, attributo, None) if carattere is not None else None
        if valore is not None:
            return valore
        stile = getattr(stile, "base_style", None)
        visti += 1

    try:
        normale = documento.styles["Normal"].font
        return getattr(normale, attributo, None)
    except (KeyError, AttributeError):
        return None


def _formato_ereditato(paragrafo, attributo):
    """Il valore del formato scritto sul paragrafo, o quello che eredita.

    Un atto scritto con gli stili di Word — cioe' quasi ogni atto — non dichiara
    niente sul paragrafo: il giustificato, il rientro e la spaziatura stanno
    sullo stile. Chi legge solo `paragraph.paragraph_format` trova `None` e il
    documento torna tutto allineato a sinistra.
    """
    valore = getattr(paragrafo.paragraph_format, attributo, None)
    if valore is not None:
        return valore
    stile = getattr(paragrafo, "style", None)
    visti = 0
    while stile is not None and visti < 8:
        formato = getattr(stile, "paragraph_format", None)
        valore = getattr(formato, attributo, None) if formato is not None else None
        if valore is not None:
            return valore
        stile = getattr(stile, "base_style", None)
        visti += 1
    # Anche docDefaults appartiene al documento: ignorarlo fa usare
    # all'editor interlinea e spaziature della propria interfaccia.
    from copy import deepcopy
    from docx.oxml import OxmlElement
    from docx.text.parfmt import ParagraphFormat

    # Lo stile della tabella governa anche i paragrafi delle sue celle.
    # Table Grid dichiara interlinea singola e nessuno spazio dopo:
    # docDefaults non può scavalcarlo con 1,15/10pt.
    tabella = next(paragrafo._p.iterancestors(f'{NS}tbl'), None)
    if tabella is not None:
        riferimento = tabella.find(f'{NS}tblPr/{NS}tblStyle')
        stile_id = riferimento.get(f'{NS}val') if riferimento is not None else None
        documento_stili = paragrafo.part.package.main_document_part.document
        stile_tabella = next((s for s in documento_stili.styles
                              if s.style_id == stile_id), None)
        visitati = set()
        while stile_tabella is not None and stile_tabella.style_id not in visitati:
            visitati.add(stile_tabella.style_id)
            formato = stile_tabella.element.find(f'{NS}pPr')
            if formato is not None:
                contenitore = OxmlElement('w:p')
                contenitore.append(deepcopy(formato))
                valore = getattr(ParagraphFormat(contenitore), attributo, None)
                if valore is not None:
                    return valore
            stile_tabella = stile_tabella.base_style
    predefinito = paragrafo.part.package.main_document_part.document.styles.element.find(
        f'{NS}docDefaults/{NS}pPrDefault/{NS}pPr'
    )
    if predefinito is not None:
        contenitore = OxmlElement('w:p')
        contenitore.append(deepcopy(predefinito))
        valore = getattr(ParagraphFormat(contenitore), attributo, None)
        if valore is not None:
            return valore
    return None


def _colore(tratto, paragrafo, documento) -> str:
    valore = getattr(getattr(tratto, "font", None), "color", None)
    rgb = getattr(valore, "rgb", None) if valore is not None else None
    if rgb is None:
        stile = getattr(paragrafo, "style", None)
        visti = 0
        while stile is not None and visti < 8 and rgb is None:
            carattere = getattr(stile, "font", None)
            colore_stile = getattr(carattere, "color", None) if carattere is not None else None
            rgb = getattr(colore_stile, "rgb", None) if colore_stile is not None else None
            stile = getattr(stile, "base_style", None)
            visti += 1
    if rgb is None or not isinstance(rgb, RGBColor):
        return "#000000"
    return f"#{rgb}".lower()


def _evidenziazione(tratto) -> str | None:
    """Il colore dell'evidenziatore, quando c'e'."""
    nome = getattr(getattr(tratto, "font", None), "highlight_color", None)
    if nome is None:
        return None
    tinte = {
        "YELLOW": "#ffff00", "BRIGHT_GREEN": "#00ff00", "TURQUOISE": "#00ffff",
        "PINK": "#ff00ff", "RED": "#ff0000", "GRAY_25": "#c0c0c0",
        "GRAY_50": "#808080", "DARK_YELLOW": "#808000", "TEAL": "#008080",
        "BLUE": "#0000ff", "GREEN": "#008000", "VIOLET": "#800080",
    }
    return tinte.get(str(getattr(nome, "name", nome)).upper())


def _sfondo_cella(cella) -> str | None:
    """Il colore di riempimento di una cella, letto dal suo XML."""
    try:
        ombra = cella._tc.tcPr.find(f"{NS}shd")
    except AttributeError:
        return None
    if ombra is None:
        return None
    riempimento = ombra.get(f"{NS}fill")
    if not riempimento or riempimento in ("auto", "FFFFFF", "ffffff"):
        return None
    return f"#{riempimento}".lower()


def _unione(cella) -> tuple[int, bool]:
    """(quante colonne occupa, se prosegue una cella di sopra)."""
    colonne, prosegue = 1, False
    try:
        proprieta = cella._tc.tcPr
    except AttributeError:
        return colonne, prosegue
    if proprieta is None:
        return colonne, prosegue
    esteso = proprieta.find(f"{NS}gridSpan")
    if esteso is not None:
        try:
            colonne = max(1, int(esteso.get(f"{NS}val")))
        except (TypeError, ValueError):
            pass
    verticale = proprieta.find(f"{NS}vMerge")
    if verticale is not None and (verticale.get(f"{NS}val") or "continue") == "continue":
        prosegue = True
    return colonne, prosegue


# ---------------------------------------------------------------------------
# Dal paragrafo del DOCX ai tratti del modello
# ---------------------------------------------------------------------------

def _pezzi_del_paragrafo(paragrafo):
    """I tratti del paragrafo, con il loro collegamento quando ce l'hanno.

    `paragraph.runs` salta quello che sta dentro un `w:hyperlink`: su un atto
    che cita una PEC o un riferimento normativo, l'indirizzo non perdeva solo
    il collegamento — spariva anche il testo.
    """
    from docx.text.run import Run

    for elemento in paragrafo._p.iterchildren():
        if elemento.tag == f"{NS}r":
            yield Run(elemento, paragrafo), None
        elif elemento.tag == f"{NS}hyperlink":
            indirizzo = _indirizzo_collegamento(elemento, paragrafo)
            for interno in elemento.iterchildren(f"{NS}r"):
                yield Run(interno, paragrafo), indirizzo


def _indirizzo_collegamento(elemento, paragrafo) -> str | None:
    """L'indirizzo di un `w:hyperlink`, risolto nelle relazioni del documento."""
    RIF = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    riferimento = elemento.get(RIF)
    if not riferimento:
        ancora = elemento.get(f"{NS}anchor")
        return f"#{ancora}" if ancora else None
    try:
        return paragrafo.part.rels[riferimento].target_ref
    except (KeyError, AttributeError):
        return None


def _interruzioni(pezzo) -> tuple[bool, bool]:
    """(c'e' un a capo, c'e' un salto di pagina) dentro questo tratto."""
    a_capo = salto = False
    for interruzione in pezzo._r.iterchildren(f"{NS}br"):
        if interruzione.get(f"{NS}type") == "page":
            salto = True
        else:
            a_capo = True
    return a_capo, salto


def _tratti(paragrafo, documento, corpo_base: float,
            nomi: set[str] | None = None, *, pezzi=None) -> list[Tratto]:
    fuori: list[Tratto] = []
    for pezzo, indirizzo in (pezzi if pezzi is not None else _pezzi_del_paragrafo(paragrafo)):
        # Run.text comprende già w:br e w:cr: aggiungerli nuovamente
        # raddoppia gli a capo a ogni salvataggio e riapertura.
        testo = pezzo.text
        if not testo:
            continue
        misura = _eredita(pezzo.font, "size", paragrafo, documento)
        corpo = round(misura.pt, 1) if misura is not None else corpo_base
        nome = _eredita(pezzo.font, "name", paragrafo, documento) or CARATTERE_PREDEFINITO
        if nomi is not None and testo.strip():
            nomi.add(str(nome))
        spacing = pezzo._r.find(f'{NS}rPr/{NS}spacing')
        underline = pezzo._r.find(f'{NS}rPr/{NS}u')
        fuori.append(Tratto(
            testo=testo,
            famiglia=pila_font(str(nome)),
            corpo=corpo,
            grassetto=bool(_eredita(pezzo, "bold", paragrafo, documento)),
            corsivo=bool(_eredita(pezzo, "italic", paragrafo, documento)),
            sottolineato=bool(_eredita(pezzo, "underline", paragrafo, documento)),
            barrato=bool(getattr(pezzo.font, "strike", None)),
            apice=bool(getattr(pezzo.font, "superscript", None)),
            pedice=bool(getattr(pezzo.font, "subscript", None)),
            colore=_colore(pezzo, paragrafo, documento),
            evidenziato=_evidenziazione(pezzo),
            collegamento=indirizzo,
            spaziatura_pt=int(spacing.get(f'{NS}val')) / 20 if spacing is not None else 0,
            sottolineatura_word=underline.get(f'{NS}val', '') if underline is not None else '',
        ))
    return fuori


def _ha_salto_di_pagina(paragrafo) -> bool:
    """Vero se il paragrafo porta un salto di pagina."""
    for pezzo in paragrafo._p.iterchildren(f"{NS}r"):
        for interruzione in pezzo.iterchildren(f"{NS}br"):
            if interruzione.get(f"{NS}type") == "page":
                return True
    return False


def _con_a_capo(html: str) -> str:
    """Gli a capo dentro un paragrafo diventano `<br>`.

    Nel testo arrivano come ritorni a riga, e l'HTML li collasserebbe in uno
    spazio: due righe di un indirizzo diventerebbero una sola.
    """
    return html.replace("\n", "<br>")


def _stile_paragrafo(paragrafo) -> list[str]:
    """Allineamento, rientri, interlinea e spazi, come li ha lasciati Word."""
    stile: list[str] = []

    allineamento = ALLINEAMENTI.get(_formato_ereditato(paragrafo, "alignment"))
    if allineamento and allineamento != "left":
        stile.append(f"text-align:{allineamento}")

    for attributo, proprieta in (("left_indent", "margin-left"),
                                 ("right_indent", "margin-right"),
                                 ("first_line_indent", "text-indent")):
        misura = _formato_ereditato(paragrafo, attributo)
        if misura is not None and abs(misura.pt) > 0.5:
            stile.append(f"{proprieta}:{_pt(misura.pt)}pt")

    for attributo, proprieta in (("space_before", "margin-top"),
                                 ("space_after", "margin-bottom")):
        misura = _formato_ereditato(paragrafo, attributo)
        stile.append(f"{proprieta}:{_pt(misura.pt if misura is not None else 0)}pt")

    interlinea = _formato_ereditato(paragrafo, "line_spacing")
    if interlinea is not None:
        if isinstance(interlinea, float):
            stile.append(f"line-height:{interlinea:.2f}")
        elif getattr(interlinea, "pt", None):
            stile.append(f"line-height:{_pt(interlinea.pt)}pt")
    else:
        stile.append('line-height:1')

    return stile


def _definizione_numerazione(paragrafo):
    """Livello nativo risolto dal paragrafo o dalla sua catena di stili."""
    num_pr = paragrafo._p.pPr.numPr if paragrafo._p.pPr is not None else None
    stile = paragrafo.style
    while num_pr is None and stile is not None:
        ppr = stile.element.find(f'{NS}pPr')
        num_pr = ppr.find(f'{NS}numPr') if ppr is not None else None
        stile = stile.base_style
    if num_pr is None:
        return None
    num_id = num_pr.find(f'{NS}numId')
    livello = num_pr.find(f'{NS}ilvl')
    if num_id is None:
        return None
    numerazioni = paragrafo.part.package.main_document_part.numbering_part.element
    numero = next((n for n in numerazioni.findall(f'{NS}num') if n.get(f'{NS}numId') == num_id.get(f'{NS}val')), None)
    if numero is None:
        return None
    abstract_id = numero.find(f'{NS}abstractNumId')
    if abstract_id is None:
        return None
    abstract = next((n for n in numerazioni.findall(f'{NS}abstractNum') if n.get(f'{NS}abstractNumId') == abstract_id.get(f'{NS}val')), None)
    ilvl = livello.get(f'{NS}val') if livello is not None else '0'
    definizione = next((n for n in abstract.findall(f'{NS}lvl') if n.get(f'{NS}ilvl') == ilvl), None) if abstract is not None else None
    override = next((n for n in numero.findall(f'{NS}lvlOverride') if n.get(f'{NS}ilvl') == ilvl), None)
    if override is not None and override.find(f'{NS}lvl') is not None:
        definizione = override.find(f'{NS}lvl')
    return definizione


def _misure_elenco(paragrafo):
    """Rientri e tabulazione ereditati dalla numerazione nativa, anche via stile."""
    definizione = _definizione_numerazione(paragrafo)
    ind = definizione.find(f'{NS}pPr/{NS}ind') if definizione is not None else None
    marker = definizione.find(f'{NS}lvlText') if definizione is not None else None
    glyph = marker.get(f'{NS}val', '') if marker is not None else ''
    if ind is None:
        return [], '', '', '', '', ''
    stili = []
    for proprieta, css, attr in (('left_indent','margin-left','left'),('right_indent','margin-right','right'),('first_line_indent','text-indent','firstLine')):
        misura = _formato_ereditato(paragrafo, proprieta)
        valore = misura.pt if misura is not None else (int(ind.get(f'{NS}{attr}', '0')) / 20)
        if proprieta == 'first_line_indent' and misura is None and ind.get(f'{NS}hanging') is not None:
            valore = -int(ind.get(f'{NS}hanging')) / 20
        stili.append(f'{css}:{_pt(valore)}pt')
    tabs = definizione.findall(f'{NS}pPr/{NS}tabs/{NS}tab')
    tab = next((t.get(f'{NS}pos') for t in tabs if t.get(f'{NS}val') in ('num','left')), None)
    fonts = definizione.find(f'{NS}rPr/{NS}rFonts')
    font = fonts.get(f'{NS}ascii', '') if fonts is not None else ''
    size = definizione.find(f'{NS}rPr/{NS}sz')
    bold = definizione.find(f'{NS}rPr/{NS}b')
    return stili, _pt(int(tab) / 20) if tab is not None else '', glyph, font, size.get(f'{NS}val', '') if size is not None else '', 'true' if bold is not None and bold.get(f'{NS}val', 'true') not in ('0', 'false') else 'false'


def _livello_elenco(paragrafo) -> int:
    """Il livello di annidamento della voce: 0 e' il primo."""
    try:
        numerazione = paragrafo._p.pPr.numPr
    except AttributeError:
        return 0
    if numerazione is None:
        return 0
    livello = numerazione.find(f"{NS}ilvl")
    if livello is None:
        return 0
    try:
        return max(0, min(8, int(livello.get(f"{NS}val"))))
    except (TypeError, ValueError):
        return 0


def _voce_di_elenco(paragrafo) -> str | None:
    """`ol`, `ul`, o niente se il paragrafo non e' una voce di elenco."""
    definizione = _definizione_numerazione(paragrafo)
    formato = definizione.find(f'{NS}numFmt') if definizione is not None else None
    if formato is not None:
        valore = formato.get(f'{NS}val')
        if valore == 'bullet':
            return 'ul'
        if valore and valore != 'none':
            return 'ol'
    nome = (getattr(getattr(paragrafo, "style", None), "name", "") or "").lower()
    if any(n in nome for n in STILI_ELENCO_NUMERATO):
        return "ol"
    if any(n in nome for n in STILI_ELENCO_PUNTATO):
        return "ul"
    return None


def _tutti_i_paragrafi(documento):
    """Ogni paragrafo del documento, comprese le celle delle tabelle."""
    yield from documento.paragraphs
    for tabella in documento.tables:
        for riga in tabella.rows:
            for cella in riga.cells:
                yield from cella.paragraphs


def _corpo_prevalente(documento) -> tuple[float, str]:
    """Corpo e carattere usati piu' spesso: fanno da riferimento alla pagina.

    Si pesa per quante lettere sono scritte con quella combinazione, non per
    quanti paragrafi la usano: un titolo e' un paragrafo come il corpo
    dell'atto, ma non e' lui a dare il tono al documento.
    """
    conteggio: dict[tuple[float, str], int] = {}
    for paragrafo in _tutti_i_paragrafi(documento):
        for pezzo in paragrafo.runs:
            if not pezzo.text.strip():
                continue
            misura = _eredita(pezzo.font, "size", paragrafo, documento)
            nome = _eredita(pezzo.font, "name", paragrafo, documento) or CARATTERE_PREDEFINITO
            chiave = (round(misura.pt, 1) if misura is not None else CORPO_PREDEFINITO, str(nome))
            conteggio[chiave] = conteggio.get(chiave, 0) + len(pezzo.text)
    if not conteggio:
        return CORPO_PREDEFINITO, pila_font(CARATTERE_PREDEFINITO)
    corpo, nome = max(conteggio.items(), key=lambda voce: voce[1])[0]
    return corpo, pila_font(nome)


# ---------------------------------------------------------------------------
# Tabelle
# ---------------------------------------------------------------------------

def _immagini(paragrafo, documento, *, elemento=None) -> list[str]:
    """Le immagini del paragrafo, come `<img>` con i dati dentro.

    Logo dello studio, firma scansionata, timbro: senza queste un atto
    importato perde l'intestazione, e l'avvocato se ne accorge solo davanti
    alla stampa.
    """
    RIF = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
    from .immagini import alleggerisci_immagine

    fuori: list[str] = []
    for disegno in (elemento if elemento is not None else paragrafo._p).iter():
        if not disegno.tag.endswith("}blip"):
            continue
        riferimento = disegno.get(RIF)
        if not riferimento:
            continue
        try:
            parte = paragrafo.part.related_parts[riferimento]
            dati = parte.blob
        except (KeyError, AttributeError):
            continue
        if not dati:
            continue
        estensione = (getattr(parte, "partname", "").rsplit(".", 1)[-1] or "png").lower()
        try:
            dati, estensione = alleggerisci_immagine(dati, estensione)
        except Exception:
            estensione = estensione or "png"
        tipo = "jpeg" if estensione in ("jpg", "jpeg") else estensione
        sorgente = f"data:image/{tipo};base64," + base64.b64encode(dati).decode()
        larghezza = _larghezza_immagine(disegno)
        misura = f";width:{_pt(larghezza)}pt" if larghezza else ""
        fuori.append(
            f'<img src="{sorgente}" style="max-width:100%;height:auto{misura}" '
            f'alt="Immagine del documento">'
        )
    return fuori


def _contenuto_paragrafo(paragrafo, documento, corpo_base, famiglia_base, nomi):
    """Testo e immagini nell'ordine originale, nel corpo e nei riquadri."""
    from copy import deepcopy
    from docx.text.run import Run
    from docx.text.paragraph import Paragraph

    if paragrafo._p.findall(f'{NS}r/{NS}fldChar'):
        from docx.oxml import OxmlElement
        normalizzato = deepcopy(paragrafo._p)
        for nodo in list(normalizzato):
            if nodo.tag != f'{NS}pPr':
                normalizzato.remove(nodo)
        campo = None
        istruzione = ''
        risultato = False
        for nodo in paragrafo._p:
            if nodo.tag == f'{NS}pPr':
                continue
            if nodo.tag != f'{NS}r':
                if campo is not None:
                    raise DocxError('Campo Word complesso non ancora gestito.')
                normalizzato.append(deepcopy(nodo))
                continue
            for elemento in nodo:
                if elemento.tag == f'{NS}rPr':
                    continue
                if elemento.tag == f'{NS}fldChar':
                    tipo = elemento.get(f'{NS}fldCharType')
                    if tipo == 'begin':
                        if campo is not None:
                            raise DocxError('Campi Word annidati non ancora gestiti.')
                        campo, istruzione, risultato = OxmlElement('w:fldSimple'), '', False
                    elif tipo == 'separate' and campo is not None:
                        risultato = True
                    elif tipo == 'end' and campo is not None:
                        campo.set(f'{NS}instr', ' '.join(istruzione.split()))
                        normalizzato.append(campo)
                        campo = None
                    else:
                        raise DocxError('Il campo Word non è completo.')
                elif elemento.tag == f'{NS}instrText' and campo is not None:
                    istruzione += elemento.text or ''
                elif campo is None or risultato:
                    frammento = deepcopy(nodo)
                    for figlio in list(frammento):
                        if figlio.tag != f'{NS}rPr':
                            frammento.remove(figlio)
                    frammento.append(deepcopy(elemento))
                    (normalizzato if campo is None else campo).append(frammento)
        if campo is not None:
            raise DocxError('Il campo Word non è completo.')
        return _contenuto_paragrafo(Paragraph(normalizzato, paragrafo._parent), documento, corpo_base, famiglia_base, nomi)

    if paragrafo._p.find(f'{NS}fldSimple') is not None:
        contenuto_campi = []
        for nodo in paragrafo._p:
            if nodo.tag == f'{NS}pPr':
                continue
            frammento = deepcopy(paragrafo._p)
            for figlio in list(frammento):
                if figlio.tag != f'{NS}pPr':
                    frammento.remove(figlio)
            if nodo.tag == f'{NS}fldSimple':
                istruzione = ' '.join((nodo.get(f'{NS}instr') or '').split()).upper()
                if istruzione not in {'PAGE', 'NUMPAGES', 'PAGE \\* MERGEFORMAT', 'NUMPAGES \\* MERGEFORMAT'}:
                    raise DocxError('Il documento contiene un campo Word non ancora gestito: ' + istruzione)
                for figlio in nodo:
                    frammento.append(deepcopy(figlio))
                interno = _contenuto_paragrafo(Paragraph(frammento, paragrafo._parent), documento, corpo_base, famiglia_base, nomi)
                contenuto_campi.append(f'<span data-iu-word-field="{istruzione}" contenteditable="false">{interno or "?"}</span>')
            else:
                frammento.append(deepcopy(nodo))
                contenuto_campi.append(_contenuto_paragrafo(Paragraph(frammento, paragrafo._parent), documento, corpo_base, famiglia_base, nomi))
        return ''.join(contenuto_campi)

    contenuto = []
    for pezzo, indirizzo in _pezzi_del_paragrafo(paragrafo):
        for elemento in pezzo._r:
            if elemento.tag == f'{NS}rPr':
                continue
            if any(nodo.tag.endswith('}blip') for nodo in elemento.iter()):
                contenuto.extend(_immagini(paragrafo, documento, elemento=elemento))
                continue
            # Un solo componente del run: evita duplicazioni e conserva la
            # posizione di testo/a capo prima e dopo ciascun disegno.
            frammento = deepcopy(pezzo._r)
            for nodo in list(frammento):
                if nodo.tag != f'{NS}rPr':
                    frammento.remove(nodo)
            frammento.append(deepcopy(elemento))
            tratti = _tratti(paragrafo, documento, corpo_base, nomi,
                             pezzi=[(Run(frammento, paragrafo), indirizzo)])
            contenuto.append(_con_a_capo(_html_tratti(tratti, corpo_base, famiglia_base, preciso=True)))
    return ''.join(contenuto)


def _larghezza_immagine(blip) -> float | None:
    """La larghezza dichiarata nel disegno, in punti."""
    for antenato in blip.iterancestors():
        for estensione in antenato.iter():
            if estensione.tag.endswith("}extent"):
                try:
                    return int(estensione.get("cx")) / 12700.0   # EMU -> punti
                except (TypeError, ValueError):
                    return None
    return None


def _e_intestazione(tabella) -> bool:
    """Vero se la prima riga della tabella e' un'intestazione.

    Word lo dichiara con `tblHeader` sulle righe che si ripetono a ogni pagina.
    Quando non lo dichiara vale la regola degli atti: la prima riga ha uno
    sfondo suo, oppure e' tutta in grassetto e le altre no.
    """
    if not tabella.rows:
        return False
    prima = tabella.rows[0]
    try:
        proprieta = prima._tr.trPr
        if proprieta is not None and proprieta.find(f"{NS}tblHeader") is not None:
            return True
    except AttributeError:
        pass

    if any(_sfondo_cella(c) for c in prima.cells):
        return True

    def _tutta_grassetto(riga) -> bool:
        pezzi = [p for c in riga.cells for par in c.paragraphs
                 for p in par.runs if p.text.strip()]
        return bool(pezzi) and all(p.bold for p in pezzi)

    if not _tutta_grassetto(prima):
        return False
    return not any(_tutta_grassetto(r) for r in tabella.rows[1:])


def _larghezze_colonne(tabella) -> list[float]:
    """La larghezza di ogni colonna in percentuale, come la dichiara il DOCX.

    Senza questa, l'editor spartisce lo spazio in parti uguali: un prospetto
    con la descrizione larga e l'importo stretto esce sbilenco.
    """
    try:
        griglia = tabella._tbl.find(f"{NS}tblGrid")
    except AttributeError:
        return []
    if griglia is None:
        return []
    misure = []
    for colonna in griglia.iterchildren(f"{NS}gridCol"):
        try:
            misure.append(float(colonna.get(f"{NS}w")))
        except (TypeError, ValueError):
            misure.append(0.0)
    totale = sum(misure)
    if totale <= 0:
        return []
    return [m / totale * 100 for m in misure]


def _ha_bordi(tabella) -> bool:
    """Vero se la tabella dichiara dei bordi visibili."""
    try:
        proprieta = tabella._tbl.tblPr
    except AttributeError:
        return False
    if proprieta is None:
        return False
    bordi = proprieta.find(f"{NS}tblBorders")
    if bordi is None:
        nome = (getattr(getattr(tabella, "style", None), "name", "") or "").lower()
        return "grid" in nome or "griglia" in nome
    for lato in bordi.iterchildren():
        valore = lato.get(f"{NS}val")
        if valore and valore not in ("none", "nil"):
            return True
    return False


def _margini_cella(cella, tabella) -> list[str]:
    """Margini dichiarati nella cella, nella tabella o nello stile Word."""
    proprieta = [cella._tc.tcPr, tabella._tbl.tblPr]
    stile = tabella.style
    visitati = set()
    while stile is not None and stile.style_id not in visitati:
        visitati.add(stile.style_id)
        proprieta.append(stile.element.find(f"{NS}tblPr"))
        stile = stile.base_style
    risultato = []
    for lato, alias in (("top", "top"), ("right", "end"), ("bottom", "bottom"), ("left", "start")):
        for proprieta_livello in proprieta:
            if proprieta_livello is None:
                continue
            margini = proprieta_livello.find(f"{NS}tcMar")
            if margini is None:
                margini = proprieta_livello.find(f"{NS}tblCellMar")
            if margini is None:
                continue
            valore = margini.find(f"{NS}{lato}")
            if valore is None:
                valore = margini.find(f"{NS}{alias}")
            if valore is None or valore.get(f"{NS}type", "dxa") != "dxa":
                continue
            try:
                punti = float(valore.get(f"{NS}w")) / 20
            except (TypeError, ValueError):
                continue
            if 0 <= punti <= 100:
                risultato.append(f"padding-{lato}:{punti:g}pt")
                break
    return risultato


def _bordi_cella(cella, tabella, riga: int, colonna: int, estensione: int) -> list[str]:
    """Bordi dichiarati, con precedenza cella, tabella e stile ereditato."""
    proprieta = [tabella._tbl.tblPr]
    stile = tabella.style
    visitati = set()
    while stile is not None and stile.style_id not in visitati:
        visitati.add(stile.style_id)
        proprieta.append(stile.element.find(f'{NS}tblPr'))
        stile = stile.base_style
    diretti = cella._tc.tcPr.find(f'{NS}tcBorders') if cella._tc.tcPr is not None else None
    risultato = []
    for lato, interno, esterno in (
        ('top', 'insideH', riga == 0),
        ('bottom', 'insideH', riga == len(tabella.rows) - 1),
        ('left', 'insideV', colonna == 0),
        ('right', 'insideV', colonna + estensione == len(tabella.columns)),
    ):
        bordo = diretti.find(f'{NS}{lato}') if diretti is not None else None
        if bordo is None:
            for livello in proprieta:
                bordi = livello.find(f'{NS}tblBorders') if livello is not None else None
                if bordi is not None:
                    bordo = bordi.find(f'{NS}{lato if esterno else interno}')
                    if bordo is not None:
                        break
        if bordo is None or bordo.get(f'{NS}val') in ('nil', 'none'):
            risultato.append(f'border-{lato}:none')
            continue
        tipo = {'single': 'solid', 'double': 'double', 'dotted': 'dotted', 'dashed': 'dashed'}.get(bordo.get(f'{NS}val'))
        colore = bordo.get(f'{NS}color', 'auto')
        if colore == 'auto':
            colore = '000000'
        try:
            punti = float(bordo.get(f'{NS}sz', '4')) / 8
        except ValueError:
            continue
        if tipo and 0 < punti <= 12 and len(colore) == 6 and all(c in '0123456789abcdefABCDEF' for c in colore):
            risultato.append(f'border-{lato}:{punti:g}pt {tipo} #{colore}')
    return risultato


def _html_tabella(tabella, documento, corpo_base: float, famiglia_base: str,
                  nomi: set[str] | None = None) -> str:
    intestazione = _e_intestazione(tabella)
    larghezze = _larghezze_colonne(tabella)
    classi = "iu-doc-tabella"
    if not _ha_bordi(tabella):
        classi += " iu-doc-tabella--senza-bordi"
    stile_tabella = ['margin:0']
    griglia = tabella._tbl.find(f'{NS}tblGrid')
    if griglia is not None:
        try:
            larghezza = sum(float(c.get(f'{NS}w')) for c in griglia) / 20
            if 1 <= larghezza <= 2000:
                stile_tabella += [f'width:{larghezza:g}pt', 'max-width:100%']
        except (TypeError, ValueError):
            pass
    descrizione = tabella._tbl.tblPr.find(f'{NS}tblDescription')
    casella = (descrizione is not None
               and descrizione.get(f'{NS}val') == 'IUSENTRA:text-box:v1'
               and len(tabella.rows) == 1 and len(tabella.columns) == 1)
    attributo_casella = ' data-iu-text-box="true"' if casella else ''
    if casella:
        stile_tabella.append('table-layout:fixed')
    pezzi = [f'<table class="{classi}"{attributo_casella} style="{";".join(stile_tabella)}"><tbody>']
    celle_logiche = [list(riga.cells) for riga in tabella.rows]
    viste = set()
    for indice_riga, riga in enumerate(tabella.rows):
        pezzi.append("<tr>")
        for indice_colonna, cella in enumerate(celle_logiche[indice_riga]):
            if cella._tc in viste:
                continue
            viste.add(cella._tc)
            colonne, prosegue = _unione(cella)
            inizio_colonna = indice_colonna
            if prosegue:
                continue
            righe_unite = 1
            while (indice_riga + righe_unite < len(celle_logiche)
                   and indice_colonna < len(celle_logiche[indice_riga + righe_unite])
                   and celle_logiche[indice_riga + righe_unite][indice_colonna]._tc is cella._tc):
                righe_unite += 1

            marchio = "th" if (intestazione and indice_riga == 0) else "td"
            attributi = f' colspan="{colonne}"' if colonne > 1 else ""
            if righe_unite > 1:
                attributi += f' rowspan="{righe_unite}"'

            stile = _margini_cella(cella, tabella)
            stile += _bordi_cella(cella, tabella, indice_riga, inizio_colonna, colonne)
            if cella._tc.tcPr is not None:
                verticale = cella._tc.tcPr.find(f'{NS}vAlign')
                if verticale is not None:
                    valore = {'top': 'top', 'center': 'middle', 'bottom': 'bottom'}.get(verticale.get(f'{NS}val'))
                    if valore:
                        stile.append(f'vertical-align:{valore}')
            if larghezze:
                quota = sum(larghezze[inizio_colonna:inizio_colonna + colonne])
                if quota > 0:
                    stile.append(f"width:{quota:.6f}%")
            sfondo = _sfondo_cella(cella)
            if sfondo:
                stile.append(f"background-color:{sfondo}")

            contenuto = []
            for paragrafo in cella.paragraphs:
                interno = _contenuto_paragrafo(paragrafo, documento, corpo_base, famiglia_base, nomi)
                stile_paragrafo = ";".join(_stile_paragrafo(paragrafo))
                contenuto.append(f'<p style="{stile_paragrafo}">{interno or "&nbsp;"}</p>')

            attributo_stile = f' style="{";".join(stile)}"' if stile else ""
            pezzi.append(
                f"<{marchio}{attributi}{attributo_stile}>"
                f'{"".join(contenuto) or "&nbsp;"}</{marchio}>'
            )
        pezzi.append("</tr>")
    pezzi.append("</tbody></table>")
    return "".join(pezzi)


# ---------------------------------------------------------------------------
# Il documento intero
# ---------------------------------------------------------------------------

def _in_ordine(documento):
    """Paragrafi e tabelle nell'ordine in cui stanno nel documento.

    `document.paragraphs` e `document.tables` sono due elenchi separati: chi
    usa quelli si ritrova tutte le tabelle in fondo, staccate dal testo che
    le introduce.
    """
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    contenitore = documento.element.body if hasattr(documento, 'sections') else documento._element
    for elemento in contenitore.iterchildren():
        if elemento.tag == f"{NS}p":
            yield Paragraph(elemento, documento)
        elif elemento.tag == f"{NS}tbl":
            yield Table(elemento, documento)


def _regioni_word(documento, indice, corpo_base, famiglia_base, nomi):
    """Parti native per sezione: mai appiattite nel corpo del documento."""
    fuori = {}
    sezione = documento.sections[indice]
    for regione in ('header', 'footer'):
        for variante, prefisso in (('default', ''), ('first', 'first_page_'), ('even', 'even_page_')):
            parte = getattr(sezione, prefisso + regione)
            collegata = parte.is_linked_to_previous and indice > 0
            blocchi = []
            for blocco in _in_ordine(parte):
                if blocco.__class__.__name__ == 'Table':
                    blocchi.append(_html_tabella(blocco, documento, corpo_base, famiglia_base, nomi))
                else:
                    interno = _contenuto_paragrafo(blocco, documento, corpo_base, famiglia_base, nomi)
                    blocchi.append(f'<p style="{";".join(_stile_paragrafo(blocco))}">{interno or "<br>"}</p>')
            chiave = html_lib.escape(str(parte.part.partname), quote=True)
            fuori[(regione, variante)] = {
                'html': ''.join(blocchi), 'linked': collegata, 'key': chiave,
                'nonvuota': bool(''.join(parte._element.itertext()).strip()),
            }
    return fuori


def _interlinea_prevalente(documento, corpo_base: float) -> float:
    """L'interlinea usata piu' spesso nel documento, in punti.

    Word la dichiara per paragrafo, in due modi: un moltiplicatore del corpo o
    una misura esatta. Qui diventa sempre una misura, perche' chi riesporta
    ragiona in punti.
    """
    conteggio: dict[float, int] = {}
    for paragrafo in _tutti_i_paragrafi(documento):
        lettere = len(paragrafo.text or "")
        if not lettere:
            continue
        valore = _formato_ereditato(paragrafo, "line_spacing")
        if valore is None:
            passo = round(corpo_base * 1.2, 1)
        elif isinstance(valore, float):
            passo = round(corpo_base * valore, 1)
        else:
            passo = round(getattr(valore, "pt", corpo_base * 1.2), 1)
        conteggio[passo] = conteggio.get(passo, 0) + lettere
    if not conteggio:
        return round(corpo_base * 1.2, 1)
    return max(conteggio.items(), key=lambda voce: voce[1])[0]


def _formato_pagina(documento, indice: int = 0) -> dict:
    if not documento.sections:
        return {}
    sezione = documento.sections[indice]

    def _punti(misura, altrimenti: float) -> float:
        return round(misura.pt, 2) if misura is not None else altrimenti

    larghezza = _punti(sezione.page_width, 595.3)
    altezza = _punti(sezione.page_height, 841.9)
    corto, lungo = min(larghezza, altezza), max(larghezza, altezza)
    nome = f"{corto:.0f}×{lungo:.0f} pt"
    for etichetta, (fl, fa) in {
        "A4": (595.3, 841.9), "A5": (419.5, 595.3), "A3": (841.9, 1190.6),
        "Letter": (612.0, 792.0), "Legal": (612.0, 1008.0),
    }.items():
        if abs(corto - fl) < 6 and abs(lungo - fa) < 6:
            nome = etichetta
            break

    return {
        "formato": nome,
        "orientamento": "orizzontale" if larghezza > altezza else "verticale",
        "larghezza_pt": larghezza,
        "altezza_pt": altezza,
        "margini_pt": {
            "alto": _punti(sezione.top_margin, 56.7),
            "destro": _punti(sezione.right_margin, 56.7),
            "basso": _punti(sezione.bottom_margin, 56.7),
            "sinistro": _punti(sezione.left_margin, 56.7),
        },
    }


def converti_docx(percorso: str | Path) -> DocumentoConvertito:
    """Legge un DOCX e lo consegna all'editor come fa `converti` con un PDF."""
    try:
        documento = ApriDocx(str(percorso))
    except Exception as errore:
        raise DocxError(f"documento illeggibile: {Path(percorso).name}") from errore

    corpo_base, famiglia_base = _corpo_prevalente(documento)
    formato = _formato_pagina(documento)

    pagine: list[list[str]] = [[]]
    sezioni_pagine = [0]
    indice_sezione = 0
    prossima_sezione = False
    aperti: list[str] = []          # gli elenchi aperti, uno per livello
    voci_aperte: list[bool] = []
    caratteri: set[str] = set()
    elementi = 0
    tabelle = 0
    immagini = 0

    def pezzi() -> list[str]:
        return pagine[-1]

    def _chiudi_elenchi(fino_a: int = 0):
        while len(aperti) > fino_a:
            if voci_aperte.pop():
                pezzi().append('</li>')
            pezzi().append(f"</{aperti.pop()}>")

    for blocco in _in_ordine(documento):
        if prossima_sezione:
            _chiudi_elenchi()
            indice_sezione += 1
            pagine.append([])
            sezioni_pagine.append(indice_sezione)
            prossima_sezione = False
        if blocco.__class__.__name__ == "Table":
            _chiudi_elenchi()
            pezzi().append(_html_tabella(blocco, documento, corpo_base, famiglia_base, caratteri))
            tabelle += 1
            continue

        # La sectPr del paragrafo conclude la sezione corrente: le misure
        # successive valgono dal blocco seguente, non da questo paragrafo.
        proprieta = blocco._p.pPr
        prossima_sezione = (proprieta is not None and proprieta.sectPr is not None
                            and indice_sezione + 1 < len(documento.sections))
        if _ha_salto_di_pagina(blocco):
            _chiudi_elenchi()
            pagine.append([])
            sezioni_pagine.append(indice_sezione)

        figure = _immagini(blocco, documento)
        tratti = _tratti(blocco, documento, corpo_base, caratteri)
        scritto = "".join(t.testo for t in tratti).strip()
        if not scritto and not figure:
            _chiudi_elenchi()
            stile = _stile_paragrafo(blocco)
            size = blocco._p.find(f'{NS}pPr/{NS}rPr/{NS}sz')
            corpo_vuoto = float(size.get(f'{NS}val')) / 2 if size is not None else corpo_base
            stile.extend([f'font-size:{_pt(corpo_vuoto)}pt', 'min-height:1em'])
            pezzi().append(f'<p style="{";".join(stile)}" data-iu-word-empty-size="{_pt(corpo_vuoto)}"></p>')
            elementi += 1
            continue

        if figure:
            immagini += len(figure)
        interno = (_contenuto_paragrafo(blocco, documento, corpo_base, famiglia_base, caratteri)
                   if figure or blocco._p.find(f'{NS}fldSimple') is not None or blocco._p.findall(f'{NS}r/{NS}fldChar')
                   else _con_a_capo(_html_tratti(tratti, corpo_base, famiglia_base, preciso=True)))
        marchio = _voce_di_elenco(blocco)
        if marchio:
            livello = _livello_elenco(blocco) + 1
            _chiudi_elenchi(livello)
            if len(aperti) == livello and aperti[-1] != marchio:
                _chiudi_elenchi(livello - 1)
            while len(aperti) < livello:
                if aperti and not voci_aperte[-1]:
                    pezzi().append('<li>')
                    voci_aperte[-1] = True
                pezzi().append(f'<{marchio} data-iu-word-list="true">')
                aperti.append(marchio)
                voci_aperte.append(False)
            if voci_aperte[-1]:
                pezzi().append('</li>')
            stile = _stile_paragrafo(blocco)
            rientri, tab, glyph, font, size, bold = _misure_elenco(blocco)
            stile.extend(rientri)
            hanging = next((x.split(':', 1)[1] for x in rientri if x.startswith('text-indent:')), '-18pt')
            stile.append(f'--iu-word-list-hanging:{hanging}')
            attributo = f' style="{";".join(stile)}"' if stile else ""
            if tab:
                attributo += f' data-iu-word-list-tab="{tab}"'
            if marchio == 'ul' and glyph and '%' not in glyph:
                attributo += f' data-iu-word-list-glyph="{html_lib.escape(glyph, quote=True)}"'
            if font:
                attributo += f' data-iu-word-list-font="{html_lib.escape(font, quote=True)}"'
            if size:
                attributo += f' data-iu-word-list-size="{size}"'
            if bold == 'true':
                attributo += ' data-iu-word-list-bold="true"'
            pezzi().append(f"<li{attributo}>{interno}")
            voci_aperte[-1] = True
        else:
            _chiudi_elenchi()
            stile = _stile_paragrafo(blocco)
            attributo = f' style="{";".join(stile)}"' if stile else ""
            pezzi().append(f"<p{attributo}>{interno}</p>")
        elementi += 1

    _chiudi_elenchi()

    if prossima_sezione:
        # Anche una sezione finale vuota appartiene alla fonte e può portare
        # un cambio di orientamento o una pagina bianca intenzionale.
        pagine.append([])
        sezioni_pagine.append(indice_sezione + 1)

    stile_pagina = [f"font-family:{famiglia_base}", f"font-size:{_pt(corpo_base)}pt"]
    # La pagina porta con se' le sue misure: servono a chi la riesporta in PDF.
    interlinea = _pt(_interlinea_prevalente(documento, corpo_base))
    esito = DocumentoConvertito()
    esito.formato = formato
    esito.pagine = []
    regioni_sezioni = [_regioni_word(documento, indice, corpo_base, famiglia_base, caratteri)
                      for indice in range(len(documento.sections))]
    esito.caratteri = sorted(c for c in caratteri if c)
    ha_regioni = any(parte['nonvuota'] for regioni in regioni_sezioni for parte in regioni.values())
    viste_sezioni = set()
    for numero, (contenuto, indice) in enumerate(zip(pagine, sezioni_pagine), start=1):
        formato_sezione = _formato_pagina(documento, indice)
        margini = formato_sezione.get("margini_pt") or {}
        inizio = int(documento.sections[indice].start_type)
        stile_sezione = list(stile_pagina)
        layout_sezione = ''
        if len(documento.sections) > 1 or ha_regioni:
            layout_sezione = ' data-layout-sezione="true"'
            stile_sezione += [
                f'width:{formato_sezione.get("larghezza_pt", 595.3):g}pt',
                f'min-height:{formato_sezione.get("altezza_pt", 841.9):g}pt',
                'padding:' + ' '.join(f'{margini.get(lato, 56.7):g}pt'
                                     for lato in ('alto', 'destro', 'basso', 'sinistro')),
            ]
        misure = (
            f' data-sezione-word="{indice + 1}" data-inizio-sezione="{inizio}"'
            f' data-larghezza="{formato_sezione.get("larghezza_pt", 595.3):g}"'
            f' data-altezza="{formato_sezione.get("altezza_pt", 841.9):g}"'
            f' data-margine-alto="{margini.get("alto", 56.7):g}"'
            f' data-margine-destro="{margini.get("destro", 56.7):g}"'
            f' data-margine-basso="{margini.get("basso", 56.7):g}"'
            f' data-margine-sinistro="{margini.get("sinistro", 56.7):g}"'
            f' data-interlinea="{interlinea}"'
        )
        intestazioni = piedi = varianti = ''
        if ha_regioni:
            sezione = documento.sections[indice]
            prima = indice not in viste_sezioni
            prima_diversa = sezione.different_first_page_header_footer
            pari_diverse = documento.settings.odd_and_even_pages_header_footer
            misure += (
                f' data-iu-word-first-page="{str(prima_diversa).lower()}"'
                f' data-iu-word-even-pages="{str(pari_diverse).lower()}"'
                f' data-iu-word-header-distance="{sezione.header_distance.pt:g}"'
                f' data-iu-word-footer-distance="{sezione.footer_distance.pt:g}"'
            )
            attiva = 'first' if prima and prima_diversa else ('even' if numero % 2 == 0 and pari_diverse else 'default')
            alternative = []
            for (regione, variante), parte in regioni_sezioni[indice].items():
                label = ('Intestazione' if regione == 'header' else 'Piè di pagina') + {'default': '', 'first': ' prima pagina', 'even': ' pagine pari'}[variante]
                attributi = (f' data-iu-word-region="{regione}" data-iu-word-kind="{variante}"'
                             f' data-iu-word-key="{parte["key"]}" data-iu-word-linked="{str(parte["linked"]).lower()}"')
                if variante == attiva:
                    distanza = sezione.header_distance.pt if regione == 'header' else sezione.footer_distance.pt
                    lato = 'top' if regione == 'header' else 'bottom'
                    marcatura = ' data-iu-word-copy="true"' if not prima else ''
                    stile = f'position:absolute;{lato}:{distanza:g}pt;left:{margini.get("sinistro", 56.7):g}pt;right:{margini.get("destro", 56.7):g}pt'
                    pezzo = f'<div class="iu-doc-regione-word"{attributi}{marcatura} aria-label="{label}" style="{stile}">{parte["html"]}</div>'
                    if regione == 'header':
                        intestazioni += pezzo
                    else:
                        piedi += pezzo
                elif prima:
                    alternative.append(f'<div class="iu-doc-variante-word"{attributi} contenteditable="true" aria-label="{label}">{parte["html"]}</div>')
            if alternative:
                varianti = ('<details class="iu-doc-varianti-word" data-iu-word-variants="true" contenteditable="false">'
                            '<summary>Altre intestazioni e piè di pagina</summary>' + ''.join(alternative) + '</details>')
            viste_sezioni.add(indice)
            stile_sezione.append('position:relative')
        html_pagina = (
            f'<section class="iu-doc-pagina" data-pagina="{numero}" data-origine="docx"{misure}{layout_sezione} '
            f'style="{";".join(stile_sezione)}">{intestazioni}{"".join(contenuto)}{piedi}{varianti}</section>'
        )
        esito.pagine.append(PaginaConvertita(
            numero=numero, html=html_pagina,
            larghezza=formato_sezione.get("larghezza_pt", 595.3),
            altezza=formato_sezione.get("altezza_pt", 841.9),
            orientamento=formato_sezione.get("orientamento", "verticale"),
            margini=tuple(margini.get(lato, 56.7) for lato in ("alto", "destro", "basso", "sinistro")),
            elementi=elementi, tabelle=tabelle, immagini=immagini,
        ))
    esito.html = "".join(pagina.html for pagina in esito.pagine)
    if not elementi and not tabelle:
        esito.avvisi.append("il documento non contiene testo")
    return esito
