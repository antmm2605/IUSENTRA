"""Dal testo riconosciuto a un documento modificabile nell'editor del fascicolo.

Il riconoscimento restituisce un testo che l'avvocato ha riletto e corretto: se
quel testo resta in una schermata di revisione serve a poco, perche' il lavoro
vero comincia dopo — estrarre un passaggio, rispondere a una memoria, ricucire
un verbale in un atto. Qui il testo corretto diventa un `.docx`, cioe' il
formato che l'editor dello studio apre e modifica davvero.

Due scelte hanno ragioni precise:

- **Niente timbro dello studio.** Il documento e' la trascrizione di un atto
  altrui: un'intestazione dello studio lo farebbe sembrare un atto proprio.
- **HTML consentito e nient'altro.** Il testo arriva dal browser dopo la
  revisione; prima di diventare un documento viene ridotto ai soli elementi che
  la revisione puo' produrre (capoversi, grassetto, elenchi, tabelle). Tutto il
  resto — script, collegamenti, immagini remote — viene scartato. Degli stili
  passa solo il formato del documento — allineamento, colore, carattere, corpo —
  ciascuno controllato valore per valore.

Base normativa: la trascrizione non sostituisce ne' certifica l'originale. La
copia per immagine resta il documento che fa fede (D.Lgs. 82/2005, art. 22) e il
`.docx` prodotto qui e' materiale di lavoro dell'avvocato, non una copia
conforme; per questo nasce come documento distinto e l'originale non si tocca.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from web.services.document_tools import DocumentToolError

# Elementi prodotti da `blocksToHtml` nella revisione del riconoscimento.
TAG_CONSENTITI = {
    "p",
    "br",
    # Interruzione di pagina: e' impaginazione del documento riconosciuto.
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "strong",
    "em",
    "u",
    # barrato e colore dentro la riga: sono formato dell'atto riconosciuto
    "s",
    "span",
    "ul",
    "ol",
    "li",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}
TAG_VUOTI = {"br", "hr"}
# Il contenuto di questi elementi non e' testo del documento: va scartato con
# l'elemento, altrimenti il codice di una pagina finirebbe nell'atto come testo.
TAG_MUTI = {"script", "style", "head", "title"}
# Attributi della sola tabella: servono a renderla leggibile nel documento.
# Su capoversi e titoli passa lo stile, ridotto al formato del documento:
# `pct/editor.html_to_docx` lo traduce in allineamento e formato Word.
ATTRIBUTI_CONSENTITI = {
    "table": {"border", "cellspacing", "cellpadding"},
    "p": {"style"},
    "h1": {"style"},
    "h2": {"style"},
    "h3": {"style"},
    "h4": {"style"},
    # dentro la riga passa solo il colore: il resto e' del capoverso
    "span": {"style"},
    "hr": {"class", "data-iu-page-break"},
    # Tipo e numero di partenza dell'elenco: sono forma del documento
    # riconosciuto (a), b), c); I., II.; 3., 4.), non decorazione.
    "ol": {"type", "start"},
}
TIPI_ELENCO = {"1", "a", "A", "i", "I"}

# Lo stile si legge dichiarazione per dichiarazione e passa solo il formato del
# documento, nei valori che il documento sa rendere. Prima si confrontava lo
# stile intero con quattro valori ammessi: un capoverso centrato *e* colorato
# («text-align:center;color:#1f57a4») non combaciava con nessuno e perdeva
# tutto, anche il centrato.
ALLINEAMENTI_CONSENTITI = {"left", "right", "center", "justify"}
_RE_COLORE = re.compile(r"^#[0-9a-f]{6}$")
# Una famiglia sola, il nome e basta: niente url(), niente virgolette annidate.
_RE_FAMIGLIA = re.compile(r"^['\"]?([A-Za-z0-9][A-Za-z0-9 \-]{0,59})['\"]?$")
_RE_CORPO = re.compile(r"^(\d{1,2}(?:\.\d)?)pt$")
CORPO_MINIMO = 2.0
CORPO_MASSIMO = 96.0
# Interlinea come moltiplicatore del corpo (1, 1,15, 1,5, 2…) e rientro
# sinistro in punti: sono impaginazione del capoverso, scelta in revisione.
_RE_INTERLINEA = re.compile(r"^([0-9](?:\.[0-9]{1,2})?)$")
INTERLINEA_MINIMA = 0.8
INTERLINEA_MASSIMA = 4.0
_RE_RIENTRO = re.compile(r"^([0-9]{1,3}(?:\.[0-9]{1,2})?)pt$")
RIENTRO_MASSIMO_PT = 400.0


def _numero_pulito(valore: float) -> str:
    return f"{valore:g}"


def stile_consentito(stile: str, *, solo_colore: bool = False) -> str:
    """Le sole dichiarazioni di formato del documento, nei valori ammessi.

    `solo_colore` vale per i pezzi dentro la riga: il colore di una parola si,
    ma allineamento, carattere e corpo sono del capoverso intero.
    """
    tenute: dict[str, str] = {}
    for dichiarazione in str(stile or "").split(";"):
        if ":" not in dichiarazione:
            continue
        proprieta, valore = dichiarazione.split(":", 1)
        proprieta = proprieta.strip().lower()
        valore = valore.strip()
        if proprieta == "text-align" and valore.lower() in ALLINEAMENTI_CONSENTITI:
            tenute[proprieta] = valore.lower()
        elif proprieta == "color" and _RE_COLORE.match(valore.lower()):
            tenute[proprieta] = valore.lower()
        elif proprieta == "font-family":
            # Della pila si tiene la prima famiglia: e' quella che il documento vuole.
            trovata = _RE_FAMIGLIA.match(valore.split(",")[0].strip())
            if trovata:
                tenute[proprieta] = f"'{trovata.group(1).strip()}'"
        elif proprieta == "font-size":
            trovato = _RE_CORPO.match(valore.replace(" ", "").lower())
            if trovato and CORPO_MINIMO <= float(trovato.group(1)) <= CORPO_MASSIMO:
                tenute[proprieta] = f"{_numero_pulito(float(trovato.group(1)))}pt"
        elif proprieta == "line-height":
            trovato = _RE_INTERLINEA.match(valore.replace(" ", ""))
            if trovato and INTERLINEA_MINIMA <= float(trovato.group(1)) <= INTERLINEA_MASSIMA:
                tenute[proprieta] = _numero_pulito(float(trovato.group(1)))
        elif proprieta == "margin-left":
            trovato = _RE_RIENTRO.match(valore.replace(" ", "").lower())
            if trovato and 0 < float(trovato.group(1)) <= RIENTRO_MASSIMO_PT:
                tenute[proprieta] = f"{_numero_pulito(float(trovato.group(1)))}pt"
    if solo_colore:
        # dentro la riga passa il solo colore: il resto e' del capoverso
        tenute = {proprieta: valore for proprieta, valore in tenute.items() if proprieta == "color"}
    return ";".join(f"{proprieta}:{valore}" for proprieta, valore in tenute.items())

MAX_HTML_CARATTERI = 4_000_000

_RE_TAG = re.compile(r"<[^>]*>")


class _Ripulitore(HTMLParser):
    """Tiene gli elementi consentiti e il testo, scarta tutto il resto."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pezzi: list[str] = []
        self._aperti: list[str] = []
        self._muto = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in TAG_MUTI:
            self._muto += 1
            return
        if tag not in TAG_CONSENTITI:
            return
        ammessi = ATTRIBUTI_CONSENTITI.get(tag, set())
        pezzi: list[str] = []
        for nome, valore in attrs:
            if nome not in ammessi or valore is None:
                continue
            if nome == "class" and str(valore).strip() != "iu-ted-page-break":
                continue
            if nome == "data-iu-page-break" and str(valore).strip().lower() not in {"true", "1"}:
                continue
            if nome == "style":
                stile = stile_consentito(str(valore), solo_colore=tag == "span")
                if stile:
                    pezzi.append(f' style="{_attributo(stile)}"')
                continue
            if nome == "type" and str(valore).strip() not in TIPI_ELENCO:
                continue
            if nome == "start" and not str(valore).strip().isdigit():
                continue
            pezzi.append(f' {nome}="{_attributo(valore)}"')
        coppie = "".join(pezzi)
        if tag in TAG_VUOTI:
            self.pezzi.append(f"<{tag}{coppie}/>")
            return
        self._aperti.append(tag)
        self.pezzi.append(f"<{tag}{coppie}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in TAG_MUTI:
            self._muto = max(0, self._muto - 1)
            return
        if tag not in TAG_CONSENTITI or tag in TAG_VUOTI:
            return
        if tag not in self._aperti:
            return
        while self._aperti:
            aperto = self._aperti.pop()
            self.pezzi.append(f"</{aperto}>")
            if aperto == tag:
                break

    def handle_data(self, data: str) -> None:
        if self._muto:
            return
        self.pezzi.append(_testo(data))

    def chiudi(self) -> str:
        while self._aperti:
            self.pezzi.append(f"</{self._aperti.pop()}>")
        return "".join(self.pezzi)


def _attributo(valore: str) -> str:
    return str(valore).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _testo(valore: str) -> str:
    return str(valore).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def html_consentito(html: str) -> str:
    """HTML ridotto agli elementi della revisione: nessun codice, nessuno stile."""
    grezzo = str(html or "")
    if len(grezzo) > MAX_HTML_CARATTERI:
        raise DocumentToolError("Il testo riconosciuto è troppo lungo per essere trasformato in documento.")
    ripulitore = _Ripulitore()
    ripulitore.feed(grezzo)
    ripulitore.close()
    pulito = ripulitore.chiudi().strip()
    if not _RE_TAG.sub("", pulito).strip():
        raise DocumentToolError("Non c'è testo da portare nell'editor: controlla la revisione del riconoscimento.")
    return pulito


def titolo_documento(nome: str) -> str:
    """Titolo leggibile del documento di lavoro, senza estensione."""
    gambo = Path(str(nome or "")).name
    gambo = gambo[: -len(Path(gambo).suffix)] if Path(gambo).suffix else gambo
    gambo = " ".join(gambo.replace("_", " ").split())
    return (gambo or "Documento")[:100]


def nome_file_documento(nome: str) -> str:
    """Nome del `.docx` di lavoro: dice da dove viene e che e' una trascrizione."""
    pulito = titolo_documento(nome)
    for carattere in '\\/:*?"<>|':
        pulito = pulito.replace(carattere, " ")
    pulito = " ".join(pulito.split()) or "Documento"
    return f"{pulito} - testo riconosciuto.docx"


def docx_da_testo(html: str, nome: str) -> tuple[bytes, str]:
    """`.docx` del testo riconosciuto e corretto, pronto per l'editor del fascicolo."""
    from pct.editor import html_to_docx

    pulito = html_consentito(html)
    try:
        # Nessun timbro: il documento trascrive un atto altrui, non lo firma.
        dati = html_to_docx(pulito, titolo_documento(nome), None)
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        raise DocumentToolError(
            "La conversione in documento modificabile non è disponibile su questa installazione."
        ) from exc
    except Exception as exc:
        raise DocumentToolError("Il testo riconosciuto non è stato convertito in documento. Riprova.") from exc
    if not dati:
        raise DocumentToolError("Il testo riconosciuto non è stato convertito in documento. Riprova.")
    return dati, nome_file_documento(nome)


def nome_file_pdf(nome: str) -> str:
    """Nome del PDF di lavoro: il testo riconosciuto e corretto, impaginato."""
    return nome_file_documento(nome)[: -len(".docx")] + ".pdf"


def pdf_da_testo(html: str, nome: str) -> tuple[bytes, str]:
    """PDF del testo riconosciuto e corretto: e' il testo impaginato, non la scansione.

    Serve quando l'avvocato vuole consegnare o archiviare il testo corretto in
    un formato non modificabile. La copia per immagine dell'originale resta
    l'atto che fa fede: questo PDF e' materiale di lavoro come il `.docx`.
    """
    from pct.editor import html_to_pdf

    pulito = html_consentito(html)
    try:
        dati = html_to_pdf(pulito, titolo_documento(nome), None, None)
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        raise DocumentToolError("La conversione in PDF non è disponibile su questa installazione.") from exc
    except Exception as exc:
        raise DocumentToolError("Il testo riconosciuto non è stato convertito in PDF. Riprova.") from exc
    if not dati:
        raise DocumentToolError("Il testo riconosciuto non è stato convertito in PDF. Riprova.")
    return dati, nome_file_pdf(nome)


__all__ = [
    "docx_da_testo",
    "html_consentito",
    "nome_file_documento",
    "nome_file_pdf",
    "pdf_da_testo",
    "stile_consentito",
    "titolo_documento",
]
