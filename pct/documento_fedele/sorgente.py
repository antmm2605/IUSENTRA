"""La pagina del PDF da leggere, senza PyMuPDF.

`documento_fedele` chiedeva tutto a una `fitz.Page`: gli span di testo con i
loro attributi, i collegamenti, le linee disegnate, i rettangoli pieni, e il
rendering di un ritaglio per le immagini. Qui quella pagina diventa
`PaginaSorgente`, che mette insieme due librerie permissive: pdfplumber (MIT)
per il testo e la geometria, PDFium (BSD, via pypdfium2) per il rendering.

La struttura degli span riproduce quella che PyMuPDF restituiva con
`get_text("rawdict")` — stesse chiavi, stesso significato — perche' il codice
che la consuma (`_tratti_da_span`) resta com'era: e' la parte che decide
sottolineature, evidenziature e collegamenti carattere per carattere, ed e'
stata tarata su documenti veri. Cambiare insieme lettore e logica avrebbe
reso impossibile capire chi ha rotto cosa.
"""

from __future__ import annotations

import io
import statistics
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium

from .geometria import Riquadro

#: I bit dei flag di span, come li scriveva PyMuPDF. Il codice che li legge
#: non e' cambiato, quindi i valori devono restare questi.
APICE, CORSIVO, GRAZIE, MONO, GRASSETTO = 1, 2, 4, 8, 16

#: Un elemento disegnato piu' basso di cosi', e piu' largo di `FILETTO_LARGHEZZA_MINIMA`,
#: e' un filetto: una sottolineatura, una barratura o il bordo di una tabella.
FILETTO_ALTEZZA_MASSIMA = 2.4
FILETTO_LARGHEZZA_MINIMA = 5.0

#: Un rettangolo pieno di queste misure, dietro il testo, e' un'evidenziatura.
EVIDENZIATURA_ALTEZZA_MINIMA = 4.0
EVIDENZIATURA_ALTEZZA_MASSIMA = 26.0
EVIDENZIATURA_LARGHEZZA_MINIMA = 8.0

#: Il bianco non evidenzia niente: e' lo sfondo della pagina.
BIANCHI = {"#ffffff", "#fefefe"}

#: Nei PDF lo spazio quasi mai e' un carattere: e' un salto di posizione.
#: Oltre questo stacco, misurato in frazione del corpo, fra la fine di una
#: lettera e l'inizio della successiva ci va uno spazio. Una soglia fissa non
#: va bene: lo spazio di un corpo 10 e' piu' stretto di quello di un corpo 14,
#: e con la soglia sbagliata le parole escono attaccate.
STACCO_SPAZIO_RELATIVO = 0.18
STACCO_SPAZIO_MINIMO = 0.75

#: Oltre questo stacco, sempre in frazione del corpo, non c'e' piu' uno spazio
#: ma un'altra colonna: due celle di tabella, o due blocchi affiancati.
#: Tenerli in una riga sola fa danni a valle — la riga risulta larga quanto la
#: tabella, e il bordo della cella smette di «sporgere» dal testo, cioe'
#: diventa indistinguibile da una sottolineatura. Due volte e mezzo il corpo e'
#: largo: in un testo giustificato uno spazio non arriva a tanto.
STACCO_COLONNA_RELATIVO = 2.5


class SorgenteError(ValueError):
    """Il PDF non si apre."""


def _colore_esadecimale(valore) -> str | None:
    """Il colore di un oggetto pdfplumber in `#rrggbb`."""
    if valore is None:
        return None
    if isinstance(valore, (int, float)):
        livello = int(max(0.0, min(1.0, float(valore))) * 255)
        terna = (livello, livello, livello)
    elif isinstance(valore, (tuple, list)):
        numeri = [float(v) for v in valore]
        if len(numeri) == 1:
            livello = int(max(0.0, min(1.0, numeri[0])) * 255)
            terna = (livello, livello, livello)
        elif len(numeri) == 3:
            terna = tuple(int(max(0.0, min(1.0, v)) * 255) for v in numeri)
        elif len(numeri) == 4:  # CMYK
            c, m, y, k = (max(0.0, min(1.0, v)) for v in numeri)
            terna = (
                int(255 * (1 - c) * (1 - k)),
                int(255 * (1 - m) * (1 - k)),
                int(255 * (1 - y) * (1 - k)),
            )
        else:
            return None
    else:
        return None
    return f"#{terna[0]:02x}{terna[1]:02x}{terna[2]:02x}"


def _colore_intero(valore) -> int:
    """Il colore del testo come lo scriveva PyMuPDF: un intero 0xRRGGBB."""
    esadecimale = _colore_esadecimale(valore)
    if not esadecimale:
        return 0
    return int(esadecimale[1:], 16)


def _flag(nome_carattere: str, *, apice: bool = False) -> int:
    """I bit di stile ricavati dal nome del carattere.

    PyMuPDF li leggeva dal descrittore del font; pdfplumber espone il nome, che
    per i caratteri usati negli atti dice la stessa cosa. Il codice a valle
    guarda comunque anche il nome, quindi un descrittore avaro non cambia
    l'esito.
    """
    minuscolo = (nome_carattere or "").lower()
    bit = 0
    if apice:
        bit |= APICE
    if "italic" in minuscolo or "oblique" in minuscolo:
        bit |= CORSIVO
    if "times" in minuscolo or "serif" in minuscolo or "roman" in minuscolo or "georgia" in minuscolo:
        bit |= GRAZIE
    if "mono" in minuscolo or "courier" in minuscolo:
        bit |= MONO
    if "bold" in minuscolo or "black" in minuscolo or "heavy" in minuscolo:
        bit |= GRASSETTO
    return bit


def _base_carattere(carattere: dict, altezza_pagina: float) -> float:
    """La quota della linea di base, contata dall'alto come il resto."""
    matrice = carattere.get("matrix")
    if matrice and len(matrice) >= 6:
        return altezza_pagina - float(matrice[5])
    return float(carattere.get("bottom", 0.0))


def _firma(carattere: dict) -> tuple:
    """Cosa rende due caratteri parte dello stesso span."""
    return (
        carattere.get("fontname"),
        round(float(carattere.get("size") or 0), 1),
        _colore_esadecimale(carattere.get("non_stroking_color")),
        bool(carattere.get("upright", True)),
    )


def _con_spazi(caratteri: list[dict]) -> list[dict]:
    """Rimette gli spazi fra i caratteri di una riga.

    pdfplumber consegna le lettere disegnate, e nei PDF lo spazio quasi mai e'
    una lettera: e' il punto in cui la successiva riparte piu' in la'. Senza
    questo passaggio il testo esce tutto attaccato.
    """
    if not caratteri:
        return []
    fuori = [caratteri[0]]
    for carattere in caratteri[1:]:
        precedente = fuori[-1]
        stacco = float(carattere["x0"]) - float(precedente["x1"])
        corpo = float(carattere.get("size") or precedente.get("size") or 11.0)
        soglia = max(corpo * STACCO_SPAZIO_RELATIVO, STACCO_SPAZIO_MINIMO)
        if stacco > soglia and str(precedente["text"]) != " ":
            spazio = dict(precedente)
            spazio["text"] = " "
            spazio["x0"] = float(precedente["x1"])
            spazio["x1"] = float(carattere["x0"])
            fuori.append(spazio)
        fuori.append(carattere)
    return fuori


def _separa_colonne(caratteri: list[dict]) -> list[list[dict]]:
    """Spezza una riga dove il testo salta in un'altra colonna.

    pdfplumber mette sulla stessa riga tutto quello che sta alla stessa
    altezza, comprese due celle di tabella lontane fra loro. PyMuPDF le teneva
    separate, e il codice a valle ci conta: misura quanto un filetto sporge
    oltre il testo per decidere se e' una sottolineatura o il bordo di una
    cella. Con la riga larga quanto tutta la tabella quel confronto si
    capovolge e ogni cella esce sottolineata.
    """
    if not caratteri:
        return []
    pezzi: list[list[dict]] = [[caratteri[0]]]
    for carattere in caratteri[1:]:
        precedente = pezzi[-1][-1]
        corpo = float(carattere.get("size") or precedente.get("size") or 11.0)
        stacco = float(carattere["x0"]) - float(precedente["x1"])
        if stacco > corpo * STACCO_COLONNA_RELATIVO:
            pezzi.append([carattere])
        else:
            pezzi[-1].append(carattere)
    return pezzi


@dataclass(frozen=True)
class PaginaSorgente:
    """Una pagina, con quello che serviva a `documento_fedele`."""

    numero: int
    _pagina: object
    _documento_grafico: object

    # -- misure -------------------------------------------------------------

    @property
    def larghezza(self) -> float:
        return float(self._pagina.width)

    @property
    def altezza(self) -> float:
        return float(self._pagina.height)

    @property
    def rotazione(self) -> int:
        return int(self._pagina.rotation or 0)

    @property
    def riquadro(self) -> Riquadro:
        return Riquadro(0.0, 0.0, self.larghezza, self.altezza)

    #: Il nome che aveva in PyMuPDF. Tenerlo evita di riscrivere le decine di
    #: `pagina.rect.width` sparse nel pacchetto.
    @property
    def rect(self) -> Riquadro:
        return self.riquadro

    # -- cosa c'e' disegnato ------------------------------------------------

    @property
    def rettangoli(self) -> list[dict]:
        """I rettangoli disegnati sulla pagina, pieni o solo bordati."""
        return list(self._pagina.rects or [])

    @property
    def linee(self) -> list[dict]:
        """Le linee disegnate sulla pagina."""
        return list(self._pagina.lines or [])

    @property
    def caratteri(self) -> list[dict]:
        """Tutte le lettere della pagina, con posizione e carattere."""
        return list(self._pagina.chars or [])

    @property
    def curve(self) -> list[dict]:
        """I tracciati curvi: archi, cerchi, la parte tonda di un timbro."""
        return list(self._pagina.curves or [])

    @property
    def disegni(self) -> list[dict]:
        """Tutto quello che e' disegnato e non e' testo.

        PyMuPDF li dava insieme con `get_drawings()`; pdfplumber li tiene
        divisi per tipo, quindi qui si rimettono insieme.
        """
        return self.rettangoli + self.linee + self.curve

    @property
    def immagini(self) -> list[dict]:
        """Le immagini incorporate, con il loro riquadro sulla pagina."""
        return list(self._pagina.images or [])

    @property
    def campi_modulo(self) -> list[Riquadro]:
        """I riquadri dei campi compilabili.

        La cornice di un campo modulo e' solo il vestito grafico del campo, e
        la scritta dentro viene gia' letta come testo: rasterizzarla
        raddoppierebbe ogni etichetta.
        """
        fuori: list[Riquadro] = []
        for annotazione in getattr(self._pagina, "annots", []) or []:
            dati = annotazione.get("data") or {}
            if str(dati.get("Subtype") or "").strip("/'") != "Widget":
                continue
            try:
                fuori.append(Riquadro(
                    annotazione["x0"], annotazione["top"],
                    annotazione["x1"], annotazione["bottom"],
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return fuori

    def tabelle(self, strategia: str = "lines_strict") -> list:
        """Le tabelle trovate sulla pagina, con la strategia indicata.

        Le strategie hanno i nomi di pdfplumber: `lines_strict` si fida solo
        dei filetti disegnati, `text` deduce la griglia dall'incolonnamento.
        Si prova la prima e, se non trova niente, la seconda: una tabella senza
        filetti resta una tabella.
        """
        try:
            return self._pagina.find_tables({
                "vertical_strategy": strategia,
                "horizontal_strategy": strategia,
            }) or []
        except Exception:
            return []

    @property
    def collegamenti(self) -> list[tuple[Riquadro, str]]:
        fuori: list[tuple[Riquadro, str]] = []
        for legame in getattr(self._pagina, "hyperlinks", []) or []:
            indirizzo = legame.get("uri")
            if not indirizzo:
                continue
            fuori.append((
                Riquadro(legame["x0"], legame["top"], legame["x1"], legame["bottom"]),
                str(indirizzo),
            ))
        return fuori

    @property
    def filetti(self) -> list[tuple[float, float, float]]:
        """Linee orizzontali sottili: `(x0, x1, y)`.

        Nel PDF una sottolineatura non e' un attributo del testo, e' una linea
        disegnata sotto le lettere — e lo sono anche i bordi di una tabella.
        Qui si raccolgono entrambe: distinguerle tocca a chi legge il testo.
        """
        fuori: list[tuple[float, float, float]] = []
        for elemento in list(self._pagina.lines or []) + list(self._pagina.rects or []):
            alto = float(elemento.get("top", 0.0))
            basso = float(elemento.get("bottom", 0.0))
            sinistro = float(elemento.get("x0", 0.0))
            destro = float(elemento.get("x1", 0.0))
            if abs(basso - alto) > FILETTO_ALTEZZA_MASSIMA:
                continue
            if abs(destro - sinistro) <= FILETTO_LARGHEZZA_MINIMA:
                continue
            fuori.append((sinistro, destro, (alto + basso) / 2))
        return fuori

    @property
    def evidenziature(self) -> list[tuple[Riquadro, str]]:
        """Rettangoli pieni e chiari dietro il testo."""
        fuori: list[tuple[Riquadro, str]] = []
        for rettangolo in self._pagina.rects or []:
            if not rettangolo.get("fill"):
                continue
            colore = _colore_esadecimale(rettangolo.get("non_stroking_color"))
            if not colore or colore.lower() in BIANCHI:
                continue
            riquadro = Riquadro(
                rettangolo["x0"], rettangolo["top"], rettangolo["x1"], rettangolo["bottom"]
            )
            if (
                EVIDENZIATURA_ALTEZZA_MINIMA < riquadro.height < EVIDENZIATURA_ALTEZZA_MASSIMA
                and riquadro.width > EVIDENZIATURA_LARGHEZZA_MINIMA
            ):
                fuori.append((riquadro, colore))
        return fuori

    # -- il testo -----------------------------------------------------------

    def righe_grezze(self) -> list[dict]:
        """Le righe della pagina, ognuna con i suoi span.

        La forma e' quella che PyMuPDF restituiva: ogni riga ha `bbox` e
        `spans`, ogni span ha `text`, `bbox`, `size`, `font`, `flags`, `color`,
        `origin` e `chars`.
        """
        try:
            righe = self._pagina.extract_text_lines(return_chars=True)
        except Exception:
            return []

        fuori: list[dict] = []
        for riga in righe:
            caratteri = [c for c in (riga.get("chars") or []) if c.get("text")]
            if not caratteri:
                continue
            for pezzo in _separa_colonne(caratteri):
                span = self._span_da_caratteri(pezzo)
                if not span:
                    continue
                fuori.append({
                    "bbox": (
                        min(float(c["x0"]) for c in pezzo),
                        min(float(c["top"]) for c in pezzo),
                        max(float(c["x1"]) for c in pezzo),
                        max(float(c["bottom"]) for c in pezzo),
                    ),
                    "spans": span,
                })
        return fuori

    def _span_da_caratteri(self, caratteri: list[dict]) -> list[dict]:
        """Raggruppa i caratteri consecutivi che condividono lo stile."""
        caratteri = _con_spazi(caratteri)
        corpo_riga = statistics.median([float(c.get("size") or 0) or 11.0 for c in caratteri])
        gruppi: list[list[dict]] = []
        firma_corrente = None
        for carattere in caratteri:
            firma = _firma(carattere)
            if firma != firma_corrente or not gruppi:
                gruppi.append([carattere])
                firma_corrente = firma
            else:
                gruppi[-1].append(carattere)

        fuori: list[dict] = []
        for gruppo in gruppi:
            testo = "".join(str(c["text"]) for c in gruppo)
            if not testo:
                continue
            nome = str(gruppo[0].get("fontname") or "")
            corpo = round(statistics.median([float(c.get("size") or 0) for c in gruppo]), 1)
            alto = min(float(c["top"]) for c in gruppo)
            basso = max(float(c["bottom"]) for c in gruppo)
            base = _base_carattere(gruppo[0], self.altezza)
            apice = corpo < corpo_riga * 0.78 and base < alto + (basso - alto) * 0.72

            fuori.append({
                "text": testo,
                "bbox": (
                    min(float(c["x0"]) for c in gruppo), alto,
                    max(float(c["x1"]) for c in gruppo), basso,
                ),
                "size": corpo,
                "font": nome.split("+")[-1],
                "flags": _flag(nome, apice=apice),
                "color": _colore_intero(gruppo[0].get("non_stroking_color")),
                "origin": (float(gruppo[0]["x0"]), base),
                "chars": [
                    {
                        "c": str(c["text"]),
                        "bbox": (float(c["x0"]), float(c["top"]),
                                 float(c["x1"]), float(c["bottom"])),
                    }
                    for c in gruppo
                ],
            })
        return fuori

    # -- rendering ----------------------------------------------------------

    def png(self, *, dpi: int = 150, ritaglio: Riquadro | None = None,
            trasparente: bool = False) -> bytes:
        """La pagina, o un suo ritaglio, come PNG."""
        pagina = self._documento_grafico[self.numero - 1]
        immagine = pagina.render(scale=dpi / 72.0, draw_annots=True).to_pil()
        immagine = immagine.convert("RGBA" if trasparente else "RGB")
        if ritaglio is not None:
            fattore = dpi / 72.0
            r = ritaglio.normalizzato()
            immagine = immagine.crop((
                max(0, int(r.x0 * fattore)), max(0, int(r.y0 * fattore)),
                min(immagine.width, int(r.x1 * fattore) + 1),
                min(immagine.height, int(r.y1 * fattore) + 1),
            ))
        fuori = io.BytesIO()
        immagine.save(fuori, format="PNG")
        return fuori.getvalue()


class DocumentoSorgente:
    """Il PDF aperto due volte: per leggerlo e per disegnarlo.

    Si usa come gestore di contesto; chiudendolo si chiudono entrambe le
    letture.
    """

    def __init__(self, origine: bytes | str | Path) -> None:
        dati = Path(origine).read_bytes() if not isinstance(origine, bytes) else origine
        try:
            self._testo = pdfplumber.open(io.BytesIO(dati))
            self._grafica = pdfium.PdfDocument(dati)
        except Exception as errore:
            raise SorgenteError("PDF illeggibile") from errore

    def __enter__(self) -> DocumentoSorgente:
        return self

    def __exit__(self, *_) -> None:
        self.chiudi()

    def chiudi(self) -> None:
        for aperto in (getattr(self, "_testo", None), getattr(self, "_grafica", None)):
            try:
                aperto.close()
            except Exception:
                pass

    #: `chiudi()` ha il nome italiano del resto del pacchetto; `close()` e'
    #: quello che il codice chiamava quando sotto c'era PyMuPDF.
    close = chiudi

    def __len__(self) -> int:
        return len(self._testo.pages)

    def __getitem__(self, indice: int) -> PaginaSorgente:
        pagina = self._testo.pages[indice]
        return PaginaSorgente(
            numero=indice + 1 if indice >= 0 else len(self) + indice + 1,
            _pagina=pagina, _documento_grafico=self._grafica,
        )

    def __iter__(self):
        return iter(self.pagine)

    @property
    def pagine(self) -> list[PaginaSorgente]:
        return [
            PaginaSorgente(numero=indice + 1, _pagina=pagina, _documento_grafico=self._grafica)
            for indice, pagina in enumerate(self._testo.pages)
        ]
