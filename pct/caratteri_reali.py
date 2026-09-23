"""I caratteri veri da usare quando si riscrive un PDF.

Chi riesporta un atto ha, di suo, i quattordici caratteri base del PDF: Times,
Helvetica, Courier e poco altro. Sono *metriche Adobe*, e non sono quelle dei
caratteri con cui gli atti sono scritti davvero — Times New Roman non e' Times,
Arial non e' Helvetica, e la differenza di larghezza e' circa l'uno per cento:
su una riga giustificata di quattrocento punti fanno quattro punti, e le parole
in mezzo si spostano di piu' di un millimetro.

Times New Roman, Arial, Calibri e Cambria non si possono distribuire: sono di
Microsoft e di Monotype. Esistono pero' i loro **equivalenti metrici** aperti —
Liberation Serif, Liberation Sans, Liberation Mono, Carlito, Caladea — che
hanno le stesse larghezze carattere per carattere, apposta. Sono gli stessi che
usa LibreOffice quando apre un documento Word su una macchina Linux.

Qui si cercano sul sistema, si registrano una volta sola, e si dice a chi
esporta quale usare per la famiglia dichiarata dal documento. Se non ci sono,
non succede niente: si torna ai quattordici di base, come prima.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Optional

_LOG = logging.getLogger(__name__)

#: Dove si cercano i caratteri. La prima cartella e' quella del progetto, cosi'
#: chi vuole puo' portarseli dietro senza dipendere dal sistema.
CARTELLE = (
    Path(__file__).resolve().parent.parent / "assets" / "caratteri",
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".fonts",
    Path.home() / ".local/share/fonts",
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
)

#: Le famiglie che sappiamo registrare, con i nomi dei file da cercare e le
#: famiglie del documento che ognuna copre.
#:
#: Si sostituisce **solo fra equivalenti metrici**: Liberation Serif ha le
#: stesse larghezze di Times New Roman, Carlito quelle di Calibri, Caladea
#: quelle di Cambria — sono stati disegnati apposta. Mettere al posto di Book
#: Antiqua un DejaVu Serif, che serif lo e' ma con larghezze sue, peggiora:
#: provato, e quel documento e' passato dal 30% al 6%. Per le famiglie senza
#: equivalente si resta ai quattordici di base, che e' un ripiego dichiarato.
#:
#: Fuori anche i nomi generici — «Times», «Helvetica», «serif» — perche' sono
#: quelli che il riconoscimento scrive quando *non* ha riconosciuto niente:
#: sostituirli significherebbe scommettere su un nome che nessuno ha detto.
FAMIGLIE: tuple[tuple[str, tuple[str, str, str, str], tuple[str, ...]], ...] = (
    (
        "Liberation Serif",
        ("LiberationSerif-Regular", "LiberationSerif-Bold",
         "LiberationSerif-Italic", "LiberationSerif-BoldItalic"),
        ("times new roman", "timesnewroman", "tinos", "thorndale",
         "liberation serif"),
    ),
    (
        "Liberation Sans",
        ("LiberationSans-Regular", "LiberationSans-Bold",
         "LiberationSans-Italic", "LiberationSans-BoldItalic"),
        ("arial", "arimo", "albany", "liberation sans"),
    ),
    (
        "Liberation Sans Narrow",
        ("LiberationSansNarrow-Regular", "LiberationSansNarrow-Bold",
         "LiberationSansNarrow-Italic", "LiberationSansNarrow-BoldItalic"),
        ("arial narrow", "liberation sans narrow"),
    ),
    (
        "Liberation Mono",
        ("LiberationMono-Regular", "LiberationMono-Bold",
         "LiberationMono-Italic", "LiberationMono-BoldItalic"),
        ("courier new", "couriernew", "cousine", "cumberland",
         "liberation mono"),
    ),
    (
        "Carlito",
        ("Carlito-Regular", "Carlito-Bold", "Carlito-Italic", "Carlito-BoldItalic"),
        ("calibri", "carlito"),
    ),
    (
        "Caladea",
        ("Caladea-Regular", "Caladea-Bold", "Caladea-Italic", "Caladea-BoldItalic"),
        ("cambria", "caladea"),
    ),
    (
        "DejaVu Serif",
        ("DejaVuSerif", "DejaVuSerif-Bold", "DejaVuSerif-Italic", "DejaVuSerif-BoldItalic"),
        ("dejavu serif",),
    ),
    (
        "DejaVu Sans",
        ("DejaVuSans", "DejaVuSans-Bold", "DejaVuSans-Oblique", "DejaVuSans-BoldOblique"),
        ("dejavu sans",),
    ),
    (
        "DejaVu Sans Mono",
        ("DejaVuSansMono", "DejaVuSansMono-Bold",
         "DejaVuSansMono-Oblique", "DejaVuSansMono-BoldOblique"),
        ("dejavu sans mono",),
    ),
)

_STILI = ("normal", "bold", "italic", "bold_italic")

_serratura = threading.Lock()
_registro: Optional[dict] = None


def _cerca(nomi: tuple[str, str, str, str]) -> Optional[dict]:
    """I quattro file della famiglia, se ci sono tutti e quattro."""
    trovati: dict = {}
    for stile, nome in zip(_STILI, nomi):
        for cartella in CARTELLE:
            try:
                if not cartella.is_dir():
                    continue
                for estensione in (".ttf", ".TTF", ".otf", ".OTF"):
                    candidati = list(cartella.rglob(nome + estensione))
                    if candidati:
                        trovati[stile] = candidati[0]
                        break
            except (OSError, PermissionError):
                continue
            if stile in trovati:
                break
        if stile not in trovati:
            return None
    return trovati


def _registra(famiglia: str, file: dict) -> Optional[dict]:
    """Registra i quattro tagli e restituisce i nomi con cui chiamarli."""
    try:
        from reportlab.lib.fonts import addMapping
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return None

    senza_spazi = famiglia.replace(" ", "")
    nomi = {}
    for stile in _STILI:
        etichetta = f"{senza_spazi}-{stile}"
        try:
            pdfmetrics.registerFont(TTFont(etichetta, str(file[stile])))
        except Exception as errore:
            _LOG.debug("carattere non registrabile: %s (%s)", file[stile], errore)
            return None
        nomi[stile] = etichetta
    try:
        pdfmetrics.registerFontFamily(
            senza_spazi, normal=nomi["normal"], bold=nomi["bold"],
            italic=nomi["italic"], boldItalic=nomi["bold_italic"],
        )
        for grassetto, corsivo, stile in (
            (0, 0, "normal"), (1, 0, "bold"), (0, 1, "italic"), (1, 1, "bold_italic"),
        ):
            addMapping(senza_spazi, grassetto, corsivo, nomi[stile])
    except Exception:
        pass
    return nomi


def registro() -> dict:
    """Le famiglie registrate: nome dichiarato dal documento -> quattro tagli.

    Si costruisce una volta sola. Una famiglia entra solo se sul sistema ci
    sono tutti e quattro i tagli: mezzo corredo e' peggio di nessuno, perche'
    il corsivo tornerebbe tondo senza dirlo.
    """
    global _registro
    if _registro is not None:
        return _registro
    with _serratura:
        if _registro is not None:
            return _registro
        fuori: dict = {}
        for famiglia, nomi_file, coperte in FAMIGLIE:
            file = _cerca(nomi_file)
            if not file:
                continue
            tagli = _registra(famiglia, file)
            if not tagli:
                continue
            for nome in (famiglia,) + coperte:
                fuori.setdefault(nome.strip().lower(), tagli)
        _registro = fuori
        if fuori:
            _LOG.info("caratteri reali registrati: %d famiglie", len(set(map(id, fuori.values()))))
        return fuori


#: I nomi che un PDF rifatto da un convertitore da' ai suoi caratteri: non
#: dicono niente, e dietro c'e' il nome vero.
_SENZA_NOME = re.compile(r"^(?:cidfont\+)?[a-z]{1,3}\d{1,3}$|^iu-[0-9a-f]+$")


def tagli_per(famiglia: str) -> Optional[dict]:
    """I quattro tagli da usare per la famiglia che il documento dichiara.

    Decide **la prima famiglia che ha un nome**. Quello che arriva qui e' una
    pila — «'F1', 'Times New Roman', serif» — dove la prima voce e' quella del
    documento e le altre sono i ripieghi che ci mette il riconoscimento
    quando non ha riconosciuto niente. Scorrerla tutta fino a trovare una
    corrispondenza significa scommettere su un nome che nessuno ha detto: su
    «'Helvetica', 'Arial'» si finirebbe per usare le metriche di Arial per un
    carattere che Arial non e', e il documento peggiora.
    """
    if not famiglia:
        return None
    disponibili = registro()
    if not disponibili:
        return None
    for pezzo in famiglia.split(","):
        candidato = pezzo.strip().strip("'\"").lower()
        if not candidato or _SENZA_NOME.match(candidato):
            continue          # «F1»: e' un'etichetta, non un carattere
        return disponibili.get(candidato)
    return None


def azzera_per_prova() -> None:
    """Rifa' il registro: serve solo ai test."""
    global _registro
    _registro = None
