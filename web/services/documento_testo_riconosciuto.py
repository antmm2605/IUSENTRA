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
  resto — script, stili, collegamenti, immagini remote — viene scartato.

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
# Sui capoversi passa il solo allineamento, perche' e' formato del documento e
# non decorazione: `pct/editor.html_to_docx` lo traduce nell'allineamento Word.
ATTRIBUTI_CONSENTITI = {
    "table": {"border", "cellspacing", "cellpadding"},
    "p": {"style"},
    "hr": {"class", "data-iu-page-break"},
}

# Nessun altro stile passa: solo l'allineamento, e solo nei valori previsti.
STILI_CONSENTITI = {
    "text-align:center": "text-align:center",
    "text-align:right": "text-align:right",
    "text-align:justify": "text-align:justify",
    "text-align:left": "text-align:left",
}

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
                stile = STILI_CONSENTITI.get(str(valore).replace(" ", "").rstrip(";").lower())
                if stile:
                    pezzi.append(f' style="{stile}"')
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


__all__ = ["docx_da_testo", "html_consentito", "nome_file_documento", "titolo_documento"]
