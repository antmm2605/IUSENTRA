"""Il vocabolario italiano: quello di sistema quando c'è, il nucleo dichiarato sempre.

Un correttore ha bisogno di sapere quali parole esistono. Il gestionale non
inventa un vocabolario e non ne scarica uno a runtime: usa il dizionario
italiano installato sull'host (hunspell o myspell, `it_IT.dic`) quando è
presente e, in ogni caso, il nucleo dichiarato qui — le parole di servizio
della lingua e quelle che ricorrono negli atti oltre al lessico forense.

Senza dizionario di sistema il correttore continua a funzionare, solo su meno
parole: nessuna funzione del gestionale dipende dalla sua presenza. Il
Dockerfile installa `hunspell-it` perché in produzione il vocabolario ci sia.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# I dizionari italiani installabili sulle distribuzioni Linux, in ordine di preferenza.
PERCORSI_DIZIONARIO: tuple[str, ...] = (
    "/usr/share/hunspell/it_IT.dic",
    "/usr/share/myspell/dicts/it_IT.dic",
    "/usr/share/myspell/it_IT.dic",
    "/usr/share/dict/italian",
)
# Oltre questo numero di righe il dizionario non si carica: è un file diverso da quello atteso.
RIGHE_MASSIME = 400_000

# Il nucleo dichiarato: parole di servizio della lingua italiana e parole comuni
# degli atti che non appartengono al lessico forense.
ITALIANO_NUCLEO: tuple[str, ...] = (
    # articoli, preposizioni, congiunzioni, pronomi
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "del", "dello", "della", "dei", "degli", "delle",
    "al", "allo", "alla", "ai", "agli", "alle", "dal", "dallo", "dalla", "dai", "dagli", "dalle",
    "nel", "nello", "nella", "nei", "negli", "nelle", "sul", "sullo", "sulla", "sui", "sugli", "sulle",
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra", "e", "o", "ma", "se", "che", "chi", "cui", "non",
    "come", "quando", "dove", "perché", "poiché", "mentre", "anche", "ancora", "già", "più", "meno", "molto",
    "questo", "questa", "questi", "queste", "quello", "quella", "quelli", "quelle", "stesso", "stessa",
    "egli", "ella", "esso", "essa", "essi", "esse", "loro", "suo", "sua", "suoi", "sue", "nostro", "nostra",
    # verbi di servizio
    "è", "sono", "era", "erano", "sia", "siano", "essere", "stato", "stata", "stati", "state",
    "ha", "hanno", "aveva", "avevano", "abbia", "abbiano", "avere", "avuto", "avuta",
    "viene", "vengono", "veniva", "venivano", "venga", "vengano", "venire", "venuto", "venuta",
    "deve", "devono", "doveva", "dovevano", "debba", "debbano", "dovere", "dovuto", "dovuta",
    "può", "possono", "poteva", "potevano", "possa", "possano", "potere", "potuto", "potuta",
    "fa", "fanno", "faceva", "facevano", "faccia", "facciano", "fare", "fatto", "fatta", "fatti", "fatte",
    "dice", "dicono", "diceva", "dicevano", "dica", "dicano", "dire", "detto", "detta", "dette",
    "risulta", "risultano", "risultava", "emerge", "emergono", "consta", "consiste", "comporta",
    # sostantivi comuni degli atti che non sono lessico forense
    "signor", "signora", "signori", "nome", "cognome", "nato", "nata", "residente", "domicilio", "domiciliato",
    "via", "viale", "piazza", "corso", "numero", "civico", "comune", "provincia", "città", "italia", "italiano",
    "data", "giorno", "mese", "anno", "anni", "ora", "ore", "oggi", "ieri", "domani", "scadenza",
    "importo", "somma", "euro", "totale", "saldo", "pagamento", "pagato", "versamento", "bonifico", "ricevuta",
    "oggetto", "materia", "diritto", "motivo", "motivi", "ragione", "ragioni", "punto", "punti",
    "lettera", "raccomandata", "posta", "elettronica", "certificata", "indirizzo", "telefono", "email",
    "copia", "copie", "originale", "conforme", "estratto", "elenco", "modulo", "modello", "scheda",
    "richiesta", "risposta", "comunicazione", "avviso", "invito", "diffida", "sollecito", "riscontro",
    "primo", "prima", "secondo", "seconda", "terzo", "terza", "quarto", "quinto", "ultimo", "ultima",
    "presente", "seguente", "seguenti", "precedente", "precedenti", "allegata", "unita", "unito",
    "ulteriore", "ulteriori", "ulteriormente", "eventuale", "eventuali", "necessario", "necessaria", "necessarie",
    "opportuno", "opportuna", "idoneo", "idonea", "legittimo", "legittima", "illegittimo", "illegittima",
    "fondato", "fondata", "infondato", "infondata", "manifestamente", "palesemente", "evidentemente",
    "documentale", "documentali", "probatorio", "probatoria", "istruttorio", "processuale", "processuali",
    "sostanziale", "formale", "preliminare", "preliminari", "definitivo", "definitiva", "provvisorio", "provvisoria",
    "integrale", "parziale", "complessivo", "complessiva", "residuo", "residua", "indebito",
    "oltre", "entro", "salvo", "fermo", "ferma", "restando", "nonostante", "inoltre", "infine", "quindi",
    "relativo", "relativa", "relativi", "relative", "medesimo", "medesima", "suddetto", "suddetta", "predetto", "predetta",
    "indicato", "indicata", "riportato", "riportata", "menzionato", "menzionata", "citato", "citata",
    "avvenuta", "avvenuto", "intervenuta", "intervenuto", "trascorso", "trascorsi", "decorso", "decorsi",
)


@lru_cache(maxsize=1)
def dizionario_di_sistema() -> tuple[str, frozenset[str]]:
    """Il dizionario italiano installato: (percorso usato, parole). Vuoto se non c'è."""
    for percorso in PERCORSI_DIZIONARIO:
        file = Path(percorso)
        if not file.is_file():
            continue
        try:
            parole: set[str] = set()
            with file.open("r", encoding="utf-8", errors="ignore") as sorgente:
                for indice, riga in enumerate(sorgente):
                    if indice > RIGHE_MASSIME:
                        break
                    # Nei file hunspell la prima riga è il conteggio e ogni voce è «parola/FLAGS».
                    voce = riga.split("/", 1)[0].strip()
                    if voce and voce.isalpha():
                        parole.add(voce.casefold())
            if parole:
                return percorso, frozenset(parole)
        except OSError:
            continue
    return "", frozenset()


@lru_cache(maxsize=1)
def parole_conosciute() -> frozenset[str]:
    """Tutte le parole che il correttore può proporre: forense + italiano + dizionario di sistema."""
    from .forense import LESSICO

    _percorso, sistema = dizionario_di_sistema()
    return frozenset(parola.casefold() for parola in ITALIANO_NUCLEO) | LESSICO | sistema


__all__ = ["ITALIANO_NUCLEO", "PERCORSI_DIZIONARIO", "RIGHE_MASSIME", "dizionario_di_sistema", "parole_conosciute"]
