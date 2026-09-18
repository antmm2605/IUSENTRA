"""Taratura della conversione e corrispondenza fra i font del PDF e quelli dell'editor.

Le soglie qui sotto decidono che cosa e' un paragrafo, un rientro voluto, una
testata: sono dichiarate in un posto solo perche' si possano leggere e
correggere senza cercarle dentro la logica."""

from __future__ import annotations

import re
from typing import Any, Optional


# ===========================================================================
# Taratura
# ===========================================================================

class Taratura:
    #: due righe appartengono allo stesso paragrafo se il salto verticale non
    #: supera questo multiplo dell'interlinea corrente
    SALTO_PARAGRAFO = 1.38

    #: scostamento minimo (in punti) perche' un rientro sia considerato voluto
    RIENTRO_MINIMO = 8.0

    #: tolleranza per dire che due bordi sono allineati
    TOLLERANZA = 2.5

    #: un blocco grafico piu' piccolo di cosi' (in punti) viene ignorato
    GRAFICA_MINIMA = 6.0

    #: risoluzione con cui si rasterizza la grafica vettoriale
    DPI_GRAFICA = 200

    #: sotto questo numero di caratteri la pagina e' considerata una scansione
    SOGLIA_SCANSIONE = 40

    #: fascia alta/bassa della pagina in cui cercare intestazioni e piedi
    FASCIA_TESTATA = 0.10

    #: un'immagine sotto queste dimensioni e' probabilmente un artefatto
    IMMAGINE_MINIMA = 8.0


# ---------------------------------------------------------------------------
# Corrispondenza fra i font del PDF e quelli disponibili nell'editor
# ---------------------------------------------------------------------------

def _famiglie_dal_catalogo() -> list[str]:
    """Le famiglie che l'editor atti offre in tendina, prese dal suo catalogo.

    Una seconda lista qui accanto si disallineerebbe al primo font aggiunto, e
    l'importazione ricadrebbe su un ripiego per un carattere che l'editor in
    realta' ha: il catalogo di `pct/template_atti.py` resta l'unica fonte.
    """
    try:
        from pct.template_atti import EDITOR_FONT_CATALOG
    except Exception:  # pragma: no cover - solo se il catalogo non e' caricabile
        return list(_FAMIGLIE_MINIME)
    famiglie = [str(voce.get("label") or "").strip() for voce in EDITOR_FONT_CATALOG.values()]
    return [voce for voce in famiglie if voce] or list(_FAMIGLIE_MINIME)


#: ripiego se il catalogo dell'editor non e' caricabile: i caratteri che nessun
#: atto italiano puo' non avere
_FAMIGLIE_MINIME = ("Times New Roman", "Arial", "Courier New")

#: famiglie offerte dall'editor atti (ordine della tendina)
FAMIGLIE_EDITOR = _famiglie_dal_catalogo()


def _chiave(nome: str) -> str:
    """Il nome di un font ridotto alle sole lettere minuscole, per confrontarlo."""
    return re.sub(r"[^a-z]", "", str(nome or "").lower())


#: da ogni famiglia del catalogo a se stessa: «Book Antiqua» nel PDF deve
#: restare «Book Antiqua» nell'editor, non diventare il suo parente piu' vicino
_MAPPA_CATALOGO = {_chiave(famiglia): famiglia for famiglia in FAMIGLIE_EDITOR if _chiave(famiglia)}

#: alias: nomi con cui lo stesso carattere si presenta nei PDF (cloni metrici
#: delle distribuzioni Linux, nomi PostScript, varianti di Office)
_MAPPA_FONT = [
    (r"times|tinos|liberationserif|nimbusroman|freeserif", "Times New Roman"),
    (r"garamondmt|garamond|egaramond|adobegaramond", "Garamond"),
    (r"cambriamath", "Cambria Math"),
    (r"cambria|caladea", "Cambria"),
    (r"georgia|gelasio", "Georgia"),
    (r"bookantiqua|palatinolinotype|palatino|pagella", "Book Antiqua"),
    (r"baskervilleoldface", "Baskerville Old Face"),
    (r"baskerville", "Libre Baskerville"),
    (r"bookmanoldstyle|bookman|urwbookman", "Bookman Old Style"),
    (r"centuryschoolbook|schoolbook|centuryschl", "Century Schoolbook"),
    (r"centurygothic|urwgothic", "Century Gothic"),
    (r"constantia", "Constantia"),
    (r"perpetua", "Perpetua"),
    (r"rockwell", "Rockwell"),
    (r"sylfaen", "Sylfaen"),
    (r"merriweather", "Merriweather"),
    (r"spectral", "Spectral"),
    (r"crimson", "Crimson Text"),
    (r"sourceserif", "Source Serif 4"),
    (r"calibri|carlito", "Calibri"),
    (r"aptos", "Aptos"),
    (r"candara", "Candara"),
    (r"corbel", "Corbel"),
    (r"tahoma", "Tahoma"),
    (r"verdana|dejavusans(?!mono)", "Verdana"),
    (r"segoeui|segoe", "Segoe UI"),
    (r"trebuchet", "Trebuchet MS"),
    (r"franklingothic|librefranklin", "Franklin Gothic"),
    (r"gillsans", "Gill Sans MT"),
    (r"lucidaconsole", "Lucida Console"),
    (r"lucidasans|lucidagrande", "Lucida Sans"),
    (r"arialnarrow", "Arial Narrow"),
    (r"arialblack", "Arial Black"),
    (r"impact|anton", "Impact"),
    (r"comicsans", "Comic Sans MS"),
    (r"microsoftsansserif|mssansserif", "Microsoft Sans Serif"),
    (r"bahnschrift|dinalternate", "Bahnschrift"),
    (r"ebrima", "Ebrima"),
    (r"arial|helvetica|arimo|liberationsans|nimbussans|freesans", "Arial"),
    (r"inter", "Inter"),
    (r"manrope", "Manrope"),
    (r"roboto|opensans|lato|notosans", "Inter"),
    (r"consolas|inconsolata", "Consolas"),
    (r"ibmplexmono", "IBM Plex Mono"),
    (r"courier|mono|cousine", "Courier New"),
]


def famiglia_editor(nome_font: str) -> tuple[str, str]:
    """
    Da "ABCDEF+TimesNewRomanPS-BoldMT" a ("Times New Roman", "TimesNewRomanPS").
    Ritorna (famiglia dell'editor, nome originale ripulito).
    """
    originale = re.sub(r"^[A-Z]{6}\+", "", nome_font or "").strip()
    pulito = re.sub(
        r"[-,_ ]?(bold|italic|oblique|regular|roman|medium|light|semibold|"
        r"black|heavy|book|condensed|mt|ms|ps|pro|std)+$",
        "", originale, flags=re.I,
    ).strip("-_, ") or originale

    chiave = _chiave(originale)
    esatta = _MAPPA_CATALOGO.get(chiave) or _MAPPA_CATALOGO.get(_chiave(pulito))
    if esatta:
        return esatta, pulito
    for schema, famiglia in _MAPPA_FONT:
        if re.search(schema, chiave) and famiglia in _MAPPA_CATALOGO.values():
            return famiglia, pulito
    # ripiego sul tipo: con grazie o senza
    return ("Times New Roman" if "serif" in chiave else "Arial"), pulito


def pila_font(nome_font: str) -> str:
    """Stack CSS: prima il font originale, poi quello dell'editor."""
    famiglia, originale = famiglia_editor(nome_font)
    generico = "monospace" if famiglia == "Courier New" else (
        "sans-serif" if famiglia in ("Arial", "Verdana", "Inter", "Manrope",
                                     "Calibri", "Aptos") else "serif"
    )
    if originale and originale.lower() != famiglia.lower():
        return f"'{originale}', '{famiglia}', {generico}"
    return f"'{famiglia}', {generico}"


# ---------------------------------------------------------------------------
# Utilita'
# ---------------------------------------------------------------------------

def _colore(valore: int) -> str:
    return "#{:06x}".format(int(valore) & 0xFFFFFF)


def _colore_da_float(c: Any) -> Optional[str]:
    if c is None:
        return None
    if isinstance(c, (int, float)):
        v = int(round(float(c) * 255))
        return "#{:02x}{:02x}{:02x}".format(v, v, v)
    try:
        r, g, b = (int(round(float(x) * 255)) for x in list(c)[:3])
        return "#{:02x}{:02x}{:02x}".format(r, g, b)
    except Exception:
        return None


def _quasi(a: float, b: float, tol: float = Taratura.TOLLERANZA) -> bool:
    return abs(a - b) <= tol


def _pt(valore: float) -> str:
    return f"{valore:.1f}".rstrip("0").rstrip(".")
