"""La bozza di un passo come PDF impaginato da atto (ReportLab, come le copertine e i report dello studio).

Il PDF è il documento del fascicolo; il testo modificabile resta nell'editor (registro delle bozze) e ogni
salvataggio rigenera il PDF. L'impaginazione è quella di un atto: A4, Times 12 con interlinea 1,5, testo
giustificato, titoli centrati, numeri di pagina. In testa e in piede a ogni pagina l'avviso che si tratta di una
bozza da rivedere e firmare, mai inviata, depositata o notificata. I segnaposti «[da completare: …]» risaltano
in grassetto su fondo giallo e sono contati nella prima pagina: nessun dato mancante passa inosservato.

Il PDF si genera in modo deterministico (data di creazione fissa, nessun identificativo casuale): lo stesso
testo produce gli stessi byte, così l'impronta del documento cambia solo se cambia il testo.
"""

from __future__ import annotations

import html
import io
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from xml.sax.saxutils import escape

from reportlab.lib import colors, pagesizes
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .modello import AVVISO_BOZZA, da_completare

AVVISO_TESTATA = f"{AVVISO_BOZZA.upper()} · non inviata, depositata né notificata"
_GIALLO = colors.HexColor("#ffe066")
_BORDO = colors.HexColor("#b08900")
_TESTO = colors.HexColor("#111111")
_GRIGIO = colors.HexColor("#555555")
_RE_SEGNAPOSTO = re.compile(r"\[da completare: [^\]]+\]")
_RE_CORSIVO = re.compile(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])")
_BLOCCHI = {"p", "h1", "h2", "h3", "h4", "li", "blockquote", "div"}
_INLINE = {"strong": "b", "b": "b", "em": "i", "i": "i", "u": "u"}


@dataclass
class _Blocco:
    tipo: str
    parti: list[str] = field(default_factory=list)
    elenco: bool = False

    @property
    def markup(self) -> str:
        return "".join(self.parti).strip()


class _Lettore(HTMLParser):
    """Dal HTML dell'editor ai blocchi del PDF: titoli, paragrafi, voci di elenco con grassetto e corsivo."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocchi: list[_Blocco] = []
        self._corrente: _Blocco | None = None
        self._aperti: list[str] = []
        self._in_elenco = 0

    def _blocco(self, tipo: str) -> _Blocco:
        if self._corrente is None:
            self._corrente = _Blocco(tipo, elenco=self._in_elenco > 0 or tipo == "li")
        return self._corrente

    def _chiudi(self) -> None:
        if self._corrente is not None:
            while self._aperti:
                self._corrente.parti.append(f"</{self._aperti.pop()}>")
            if self._corrente.markup:
                self.blocchi.append(self._corrente)
        self._corrente = None

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in {"ul", "ol"}:
            self._chiudi()
            self._in_elenco += 1
        elif tag in _BLOCCHI:
            self._chiudi()
            self._blocco(tag)
        elif tag == "br":
            if self._corrente is not None:
                self._corrente.parti.append("<br/>")
        elif tag in _INLINE:
            blocco = self._blocco("p")
            blocco.parti.append(f"<{_INLINE[tag]}>")
            self._aperti.append(_INLINE[tag])

    def handle_startendtag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag == "br" and self._corrente is not None:
            self._corrente.parti.append("<br/>")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"ul", "ol"}:
            self._chiudi()
            self._in_elenco = max(0, self._in_elenco - 1)
        elif tag in _BLOCCHI:
            self._chiudi()
        elif tag in _INLINE and self._corrente is not None and _INLINE[tag] in self._aperti:
            # Chiude i tag aperti dopo quello che termina (HTML malformato) e riapre il resto.
            while self._aperti:
                aperto = self._aperti.pop()
                self._corrente.parti.append(f"</{aperto}>")
                if aperto == _INLINE[tag]:
                    break

    def handle_data(self, data: str) -> None:
        if not data.strip() and self._corrente is None:
            return
        self._blocco("p").parti.append(escape(" ".join(data.replace("\xa0", " ").split(" ")) if data.strip() else " "))

    def close(self) -> None:
        super().close()
        self._chiudi()


def _evidenzia(markup: str) -> str:
    """Segnaposti in grassetto su fondo giallo; il corsivo Markdown «*…*» del modello diventa corsivo."""
    markup = _RE_CORSIVO.sub(lambda m: f"<i>{m.group(1)}</i>", markup)
    return _RE_SEGNAPOSTO.sub(lambda m: f'<font backColor="#ffe066" color="#5c3d00"><b>{m.group(0)}</b></font>', markup)


def _stili() -> dict[str, ParagraphStyle]:
    corpo = ParagraphStyle("corpo", fontName="Times-Roman", fontSize=12, leading=18, alignment=TA_JUSTIFY,
                           textColor=_TESTO, spaceAfter=6)
    return {
        "p": corpo,
        "li": ParagraphStyle("voce", parent=corpo, leftIndent=0.9 * cm, bulletIndent=0.3 * cm, spaceAfter=3),
        "blockquote": ParagraphStyle("citazione", parent=corpo, leftIndent=1.2 * cm, rightIndent=0.8 * cm, fontSize=11),
        "h1": ParagraphStyle("titolo", parent=corpo, fontName="Times-Bold", fontSize=16, leading=22, alignment=TA_CENTER,
                             spaceBefore=4, spaceAfter=12),
        "h2": ParagraphStyle("sottotitolo", parent=corpo, fontName="Times-Bold", fontSize=13, leading=19,
                             alignment=TA_CENTER, spaceBefore=10, spaceAfter=8),
        "h3": ParagraphStyle("titoletto", parent=corpo, fontName="Times-Bold", fontSize=12, leading=18,
                             alignment=TA_LEFT, spaceBefore=8, spaceAfter=4),
        "avviso": ParagraphStyle("avviso", fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=colors.HexColor("#3d2c00")),
    }


def blocchi_da_html(testo_html: str) -> list[tuple[str, str, bool]]:
    """(tipo, markup ReportLab, voce di elenco) per ogni blocco del testo dell'editor."""
    lettore = _Lettore()
    lettore.feed(str(testo_html or ""))
    lettore.close()
    return [(b.tipo if b.tipo in {"h1", "h2", "h3", "blockquote"} else ("h3" if b.tipo == "h4" else ("li" if b.elenco else "p")),
             b.markup, b.elenco) for b in lettore.blocchi]


def _riquadro_avviso(mancano: tuple[str, ...], stili: dict[str, ParagraphStyle]) -> Table:
    righe = [f"<b>{escape(AVVISO_BOZZA)}.</b> Preparata dal software con i soli dati certi del fascicolo: "
             "va riletta, completata e firmata dall'avvocato. Non è stata inviata, depositata né notificata."]
    if mancano:
        righe.append(f"<b>{len(mancano)} {'dato' if len(mancano) == 1 else 'dati'} da completare</b>, evidenziati in giallo "
                     "nel testo: " + "; ".join(escape(m) for m in mancano[:12]) + ("…" if len(mancano) > 12 else "") + ".")
    tabella = Table([[Paragraph("<br/>".join(righe), stili["avviso"])]], colWidths=["100%"])
    tabella.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff6cc")),
        ("BOX", (0, 0), (-1, -1), 0.8, _BORDO),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tabella


def _testo_semplice(testo_html: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", str(testo_html or "")))


def bozza_pdf(titolo: str, testo_html: str) -> bytes:
    """Il PDF della bozza dal testo dell'editor (HTML impaginato o testo semplice)."""
    stili = _stili()
    mancano = da_completare(_testo_semplice(testo_html))
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=pagesizes.A4, leftMargin=2.5 * cm, rightMargin=2.2 * cm, topMargin=2.4 * cm,
        bottomMargin=2.2 * cm, title=str(titolo or "Bozza"), author="IUSENTRA (bozza preparata in automatico)",
        subject=AVVISO_BOZZA, creator="IUSENTRA", invariant=1,
    )
    storia: list = [_riquadro_avviso(mancano, stili), Spacer(1, 14)]
    blocchi = blocchi_da_html(testo_html) if "<" in str(testo_html or "") else [
        ("p", escape(riga), False) for riga in str(testo_html or "").splitlines() if riga.strip()]
    if not blocchi:
        blocchi = [("p", "<i>Bozza senza testo.</i>", False)]
    for indice, (tipo, markup, voce) in enumerate(blocchi):
        if tipo == "_fatto":
            continue
        paragrafo = Paragraph(_evidenzia(markup), stili[tipo], bulletText="•" if voce else None)
        # Un titolo non resta solo in fondo alla pagina.
        if tipo in {"h1", "h2", "h3"} and indice + 1 < len(blocchi):
            prossimo_tipo, prossimo, prossima_voce = blocchi[indice + 1]
            storia.append(KeepTogether([paragrafo, Paragraph(_evidenzia(prossimo), stili[prossimo_tipo],
                                                             bulletText="•" if prossima_voce else None)]))
            blocchi[indice + 1] = ("_fatto", "", False)
            continue
        storia.append(paragrafo)

    def pagina(canvas, doc) -> None:  # noqa: ANN001
        canvas.saveState()
        larghezza, altezza = pagesizes.A4
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(colors.HexColor("#8a6100"))
        canvas.drawCentredString(larghezza / 2, altezza - 1.35 * cm, AVVISO_TESTATA)
        canvas.setStrokeColor(_BORDO)
        canvas.setLineWidth(0.4)
        canvas.line(doc.leftMargin, altezza - 1.55 * cm, larghezza - doc.rightMargin, altezza - 1.55 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_GRIGIO)
        canvas.drawString(doc.leftMargin, 1.2 * cm, str(titolo or "Bozza")[:110])
        canvas.drawRightString(larghezza - doc.rightMargin, 1.2 * cm, f"Pagina {doc.page}")
        canvas.restoreState()

    documento.build(storia, onFirstPage=pagina, onLaterPages=pagina)
    return buffer.getvalue()


def nome_file_pdf(titolo: str) -> str:
    """Il nome del PDF nel fascicolo, nella stessa forma dei documenti dell'editor."""
    sicuro = re.sub(r"[^A-Za-z0-9._-]+", "_", " ".join(str(titolo or "").split()).lower()).strip("._-") or "bozza"
    return f"{sicuro[:80]}.pdf"


__all__ = ["AVVISO_TESTATA", "blocchi_da_html", "bozza_pdf", "nome_file_pdf"]
