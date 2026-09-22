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
    realta' ha: `pct/catalogo_caratteri.py` resta l'unica fonte.

    Quel modulo non importa niente apposta. Prima il catalogo stava dentro
    `pct/template_atti.py`, che tira dentro il driver di PostgreSQL: dove quel
    driver manca, qui arrivavano tre caratteri invece di quarantasei e ogni
    atto tornava in Times New Roman o in Arial.
    """
    try:
        from pct.catalogo_caratteri import ETICHETTE_CARATTERI
    except Exception:  # pragma: no cover - solo se il catalogo non e' caricabile
        return list(_FAMIGLIE_MINIME)
    return list(ETICHETTE_CARATTERI) or list(_FAMIGLIE_MINIME)


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
    # caratteri diffusi negli atti e nei PDF dei software giudiziari, ognuno
    # sulla famiglia del catalogo che gli somiglia di piu'
    (r"minion|sabon|janson|utopia|charter|charis|gentium|cardo|junicode", "Book Antiqua"),
    (r"ebgaramond|cormorant|sortsmill", "Garamond"),
    (r"didot|bodoni|playfair", "Perpetua"),
    (r"ptserif|notoserif|droidserif|literata|lora", "Source Serif 4"),
    (r"newcenturyschlbk|^croman$", "Century Schoolbook"),   # C059: la chiave perde le cifre
    (r"urwpalladio|^proman$", "Book Antiqua"),              # P052: idem
    (r"futura|avenir|jost|questrial", "Century Gothic"),
    (r"optima|gillsansmt", "Gill Sans MT"),
    (r"myriad|frutiger|univers|helveticaneue|helvneue", "Arial"),
    (r"calisto|goudy|bellmt", "Book Antiqua"),
    (r"nimbusmono|liberationmono|ptmono|courierprime|freemono|dejavusansmono", "Courier New"),
    (r"firamono|robotomono|jetbrainsmono|sourcecodepro|menlo|monaco", "Consolas"),
    (r"ptsans|sourcesans|firasans|ubuntu|cantarell|nunito|worksans|rubik|karla", "Inter"),
    (r"arialunicode", "Arial"),
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
    # se e' il nome intero a corrispondere, il nome intero e' quello buono:
    # «Times New Roman» ripulito diventa «Times New», che non esiste, e
    # finirebbe davanti a tutto nella pila del foglio di stile
    esatta = _MAPPA_CATALOGO.get(chiave)
    if esatta:
        return esatta, esatta
    esatta = _MAPPA_CATALOGO.get(_chiave(pulito))
    if esatta:
        return esatta, pulito
    for schema, famiglia in _MAPPA_FONT:
        if re.search(schema, chiave) and famiglia in _MAPPA_CATALOGO.values():
            return famiglia, pulito
    return _ripiego(chiave), pulito


#: Indizi che un nome porta con se' sul tipo di carattere. Un carattere fuori
#: catalogo non deve diventare Arial per scarto: se si chiama «Futura» e' senza
#: grazie, se si chiama «Courier Prime» e' a spaziatura fissa, e scegliere male
#: si vede su tutta la pagina.
_INDIZI_MONO = (
    "mono", "code", "courier", "console", "typewriter", "terminal",
    "fixed", "teletype", "prestige",
)
_INDIZI_SENZA_GRAZIE = (
    "sans", "grotesk", "grotesque", "gothic", "neue", "helv", "arial",
    "futura", "avenir", "frutiger", "univers", "franklin", "akzidenz",
    "interstate", "gill", "myriad", "verdana", "tahoma", "segoe", "calibri",
    "roboto", "lato", "ubuntu", "nunito", "poppins", "montserrat",
)
_INDIZI_CON_GRAZIE = (
    "serif", "roman", "times", "garamond", "book", "antiqua", "palatino",
    "baskerville", "caslon", "bodoni", "didot", "georgia", "cambria",
    "minion", "sabon", "utopia", "charter", "schoolbook", "century",
    "perpetua", "rockwell", "slab", "clarendon", "elzevir",
)


def _ripiego(chiave: str) -> str:
    """La famiglia da usare quando il nome non e' in catalogo.

    Si guarda cosa dice il nome: quasi tutti i caratteri portano scritto che
    cosa sono. Solo quando non dice niente si sceglie il carattere con grazie,
    perche' un atto scritto in un carattere sconosciuto quasi sempre e' scritto
    in un carattere con grazie.
    """
    disponibili = set(_MAPPA_CATALOGO.values())
    for indizio in _INDIZI_MONO:
        if indizio in chiave:
            return "Courier New" if "Courier New" in disponibili else _FAMIGLIE_MINIME[2]
    for indizio in _INDIZI_SENZA_GRAZIE:
        if indizio in chiave:
            return "Arial" if "Arial" in disponibili else _FAMIGLIE_MINIME[1]
    for indizio in _INDIZI_CON_GRAZIE:
        if indizio in chiave:
            return "Times New Roman"
    return "Times New Roman"


#: Dal tono dichiarato nel catalogo al ripiego generico del foglio di stile.
_GENERICI = {"serif": "serif", "sans": "sans-serif", "mono": "monospace"}


def _tono(famiglia: str) -> str:
    """Se la famiglia ha grazie, non le ha, o e' a spaziatura fissa.

    Il catalogo dell'editor lo dichiara per ognuna. Prima qui c'era un elenco
    scritto a mano di sei nomi: tutte le altre famiglie senza grazie —
    Century Gothic, Segoe UI, Tahoma, Trebuchet, Gill Sans, Franklin Gothic,
    Impact — ripiegavano su `serif`, e bastava che il carattere non fosse
    installato perche' il testo cambiasse faccia.
    """
    try:
        from pct.catalogo_caratteri import TONO_CARATTERI
    except Exception:  # pragma: no cover - catalogo non caricabile
        return "mono" if famiglia == "Courier New" else (
            "sans" if famiglia == "Arial" else "serif")
    return TONO_CARATTERI.get(famiglia, "serif")


def pila_font(nome_font: str) -> str:
    """Stack CSS: prima il font originale, poi quello dell'editor."""
    famiglia, originale = famiglia_editor(nome_font)
    generico = _GENERICI.get(_tono(famiglia), "serif")
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
