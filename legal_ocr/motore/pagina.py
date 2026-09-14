"""Una pagina, dall'immagine al documento: il percorso completo di lettura.

E' l'unico punto in cui una pagina immagine diventa testo con la sua forma:
il fascicolo, l'editor professionale, l'utility di conversione e l'indice
passano tutti da qui. Il percorso: preparazione dell'immagine, lettura con
Tesseract e in parallelo con il secondo lettore, consenso sulle parole
incerte, zone grafiche, impaginazione (titoli, capoversi, elenchi, tabelle,
numeri di pagina), formato misurato (corpo, grassetto, allineamento),
correzioni del formulario legale dichiarate, riferimenti giuridici.

Base normativa: la copia informatica per immagine di documento analogico
(D.Lgs. 82/2005, art. 22) resta una scansione; il testo letto e' uno strato di
lavoro e ricerca e non trasforma la scansione in atto nativo digitale
(Specifiche tecniche DGSIA D.M. 44/2011, art. 15, comma 1, lett. c).
"""

from __future__ import annotations

import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from ..formato import blocchi_con_formato, densita_parole
from ..page_layout import NUMERO_PAGINA, TABELLA, Blocco, analizza_pagina
from .consenso import applica_consenso, leggi_con_secondo_lettore, secondo_lettore_disponibile
from .correzioni import correggi_blocchi
from .errori import ErroreLettura, MotoreNonDisponibile
from .immagine import apri_immagine, prepara_pagina, regioni_grafiche
from .lettura import LINGUA, Lettura, leggi_immagine
from .riferimenti import riferimenti_del_testo

MAX_IMMAGINE_BYTES = 60 * 1024 * 1024
MAX_PIXEL = 50_000_000
_SLOTS = threading.BoundedSemaphore(max(1, int(os.environ.get("IUSENTRA_OCR_PAGE_CONCURRENCY", "2") or 2)))
_ATTESA_SLOT_SECONDI = 45


@dataclass(frozen=True)
class PaginaLetta:
    """Il risultato completo della lettura di una pagina immagine."""

    pdf: bytes
    parole: list[dict[str, Any]]
    blocchi: list[dict[str, Any]]
    paragrafi: list[str]
    figure: list[dict[str, Any]]
    confidenza: float
    motore: str
    dpi: int
    passaggi: tuple[str, ...] = ()
    correzioni: list[dict[str, Any]] = field(default_factory=list)
    riferimenti: dict[str, list[str]] = field(default_factory=dict)
    immagine: Any = None
    consenso: int = 0
    secondo_lettore: str = ""
    avvisi: tuple[str, ...] = ()
    secondi: float = 0.0

    @property
    def testo(self) -> str:
        return "\n\n".join(self.paragrafi)

    @property
    def caratteri(self) -> int:
        return sum(len(re.sub(r"\s+", "", paragrafo)) for paragrafo in self.paragrafi)

    @property
    def tabelle(self) -> int:
        return sum(1 for blocco in self.blocchi if blocco.get("tipo") == TABELLA)


def paragrafi_dai_blocchi(blocchi: list[dict[str, Any]] | list[Blocco]) -> list[str]:
    """Testo lineare dei blocchi: tabelle riga per riga, numeri di pagina esclusi."""
    paragrafi: list[str] = []
    for blocco in blocchi:
        voce = blocco.come_dizionario() if isinstance(blocco, Blocco) else blocco
        if voce.get("tipo") == NUMERO_PAGINA:
            continue
        if voce.get("tipo") == TABELLA:
            paragrafi.extend(" | ".join(str(cella) for cella in riga) for riga in voce.get("righe") or [] if any(riga))
        elif voce.get("testo"):
            paragrafi.append(str(voce["testo"]))
    return paragrafi


def _pytesseract(modulo: object | None):
    if modulo is not None:
        return modulo
    try:
        import pytesseract  # type: ignore

        return pytesseract
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        raise MotoreNonDisponibile("Il riconoscimento del testo non è disponibile su questa installazione.") from exc


def _controlla(immagine) -> None:
    if immagine.width * immagine.height > MAX_PIXEL:
        raise ErroreLettura("La pagina supera 50 megapixel.")


def rifinisci_blocchi(blocchi: list[Blocco], parole: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]], dict[str, list[str]]]:
    """Blocchi con formato e correzioni, paragrafi, correzioni applicate e riferimenti.

    I riferimenti si cercano nel testo gia' normalizzato: un numero di ruolo
    spezzato dagli spazi del motore non verrebbe riconosciuto prima.
    """
    con_formato = blocchi_con_formato(blocchi, parole)
    corretti, applicate = correggi_blocchi(con_formato)
    paragrafi = paragrafi_dai_blocchi(corretti)
    return corretti, paragrafi, applicate, riferimenti_del_testo("\n".join(paragrafi))


def riconosci_immagine(
    sorgente: bytes | Any,
    *,
    rotazione: int = 0,
    raddrizza: bool = True,
    pytesseract: object | None = None,
    lingua: str = LINGUA,
    secondo_lettore: bool = True,
    con_pdf: bool = True,
) -> PaginaLetta:
    """Legge una pagina immagine (byte o immagine PIL) e restituisce testo e forma."""
    inizio = time.monotonic()
    motore = _pytesseract(pytesseract)
    if isinstance(sorgente, (bytes, bytearray)):
        if len(sorgente) > MAX_IMMAGINE_BYTES:
            raise ErroreLettura("La pagina supera 60 MB.")
        originale = apri_immagine(bytes(sorgente), rotazione)
    else:
        originale = sorgente
        angolo = int(rotazione or 0) % 360
        if angolo in {90, 180, 270}:
            originale = originale.rotate(-angolo, expand=True)
    _controlla(originale)
    if not _SLOTS.acquire(timeout=_ATTESA_SLOT_SECONDI):
        raise ErroreLettura("Il riconoscimento del testo è impegnato da altre pagine. Riprova tra qualche istante.")
    preparata = None
    avvisi: list[str] = []
    try:
        preparata = prepara_pagina(originale, raddrizza=raddrizza)
        immagine = preparata.immagine
        usa_secondo = secondo_lettore and secondo_lettore_disponibile()
        if usa_secondo:
            with ThreadPoolExecutor(max_workers=2) as esecutore:
                futuro_lettura = esecutore.submit(leggi_immagine, immagine, pytesseract=motore, lingua=lingua, dpi=preparata.dpi, con_pdf=con_pdf)
                futuro_secondo = esecutore.submit(leggi_con_secondo_lettore, immagine)
                lettura: Lettura = futuro_lettura.result()
                secondaria = futuro_secondo.result()
        else:
            lettura = leggi_immagine(immagine, pytesseract=motore, lingua=lingua, dpi=preparata.dpi, con_pdf=con_pdf)
            secondaria = None
        avvisi.extend(lettura.avvisi)
        parole, sostituite = applica_consenso(lettura.parole, secondaria)
        try:
            figure = regioni_grafiche(immagine, parole)
        except Exception:
            figure = []
        # Misure sull'immagine finche' e' in memoria: il grassetto si vede
        # dall'inchiostro della pagina che il motore ha letto.
        densita_parole(immagine, parole)
    finally:
        _SLOTS.release()
        if originale is not sorgente and originale is not (preparata.immagine if preparata else None):
            try:
                originale.close()
            except Exception:
                pass
    if con_pdf and not lettura.pdf.startswith(b"%PDF-"):
        dettaglio = f" ({lettura.avvisi[-1]})" if lettura.avvisi else ""
        raise ErroreLettura(f"Riconoscimento del testo non completato per questa pagina.{dettaglio}")
    blocchi = analizza_pagina(parole)
    corretti, paragrafi, applicate, riferimenti = rifinisci_blocchi(blocchi, parole)
    etichetta = f"tesseract · lettura {lettura.configurazione}" if lettura.configurazione else "tesseract"
    return PaginaLetta(
        pdf=lettura.pdf,
        parole=parole,
        blocchi=corretti,
        paragrafi=paragrafi,
        figure=figure,
        confidenza=round(lettura.confidenza, 4),
        motore=etichetta,
        dpi=preparata.dpi,
        passaggi=preparata.passaggi,
        correzioni=applicate,
        riferimenti=riferimenti,
        immagine=preparata.immagine,
        consenso=sostituite,
        secondo_lettore=secondaria.motore if secondaria is not None else "",
        avvisi=tuple(avvisi),
        secondi=round(time.monotonic() - inizio, 3),
    )


__all__ = ["MAX_IMMAGINE_BYTES", "MAX_PIXEL", "PaginaLetta", "paragrafi_dai_blocchi", "riconosci_immagine", "rifinisci_blocchi"]
