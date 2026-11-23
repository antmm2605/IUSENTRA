"""Regole per materia descritte come schede: riconoscimento, schema della risposta, norme vigenti, termini.

Una scheda dichiara da avvocato: quando si applica (segnali del testo), che cosa si conclude e perché (punti con la
norma e l'«ancora» letterale del testo vigente), giudice, procedibilità, rito, termini (calcolati dal motore dei termini
se il testo indica la data di partenza), cosa fare, dati da chiedere, avvertenze. Il motore trasforma la scheda nella
coppia (riconosci, analizza) dell'elenco ``REGOLE``: il controllo delle ancore e la composizione restano quelli
dell'harness (``controllo.py``, ``composizione.py``).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from ..comprensione import Comprensione
from ..fatti import Fatti
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from ..termini import data_breve, termine_anni, termine_giorni, termine_mesi


@dataclass(frozen=True)
class Scadenza:
    """Termine calcolato dalla data scritta dopo l'evento («notificato il 04/12/2026»)."""
    descrizione: str            # «ricorso entro» …
    quantita: int
    unita: str                  # «giorni» | «mesi» | «anni»
    evento: str                 # espressione dell'evento nel testo (senza accenti)
    rif: tuple[Rif, ...]
    sospensione_feriale: bool = True
    sostanziale: bool = False
    modello: str = ""           # modello del motore dei termini (pct/termini_processuali.py), se esiste


@dataclass
class Bozza:
    titolo: str
    oggetto: str
    diritto: list[str]
    conclusioni: str
    documenti: str
    norme_struttura: str


@dataclass
class Scheda:
    regola: str
    materia: str
    nome: str
    segnali: tuple[str, ...]                    # tutte devono comparire
    alcuni: tuple[str, ...] = ()                # almeno una (se indicate)
    esclusi: tuple[str, ...] = ()               # nessuna deve comparire
    punteggio: int = 6
    tipi: frozenset[str] = frozenset({"parere", "redazione", "termine", "calcolo"})
    rimedio: str = ""
    giudice: str = ""
    modello: str = ""
    capito: str = ""
    conclusione: list[Punto] = field(default_factory=list)
    inquadramento: list[Punto] = field(default_factory=list)
    competenza: list[Punto] = field(default_factory=list)
    procedibilita: list[Punto] = field(default_factory=list)
    rito: list[Punto] = field(default_factory=list)
    termini: list[Punto] = field(default_factory=list)
    scadenze: list[Scadenza] = field(default_factory=list)
    cosa_fare: list[str] = field(default_factory=list)
    dati: list[str] = field(default_factory=list)
    avvertenze: list[str] = field(default_factory=list)
    dubbi: list[str] = field(default_factory=list)
    bozza: Bozza | None = None
    extra: Callable[[Analisi, Comprensione, Fatti], None] | None = None
    # Ricerca per significato (fattispecie/significato_materie.py): lato della parte assistita, sinonimi, situazioni tipiche.
    lato: str | None = None                       # «attivo», «passivo»; None se vale per entrambi
    sinonimi: tuple[str, ...] = ()
    situazioni: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Un solo segnale scritto senza virgola finale è una stringa, non una tupla: lo si normalizza.
        for nome in ("segnali", "alcuni", "esclusi"):
            valore = getattr(self, nome)
            if isinstance(valore, str):
                setattr(self, nome, (valore,))

    # ------------------------------------------------------------------ riconoscimento
    def riconosci(self, c: Comprensione, f: Fatti) -> int:
        if c.tipo not in self.tipi:
            return 0
        t = piano(f.testo)
        if not all(re.search(s, t) for s in self.segnali):
            return 0
        if self.alcuni and not any(re.search(s, t) for s in self.alcuni):
            return 0
        if any(re.search(s, t) for s in self.esclusi):
            return 0
        return self.punteggio

    # ------------------------------------------------------------------ analisi
    def analizza(self, c: Comprensione, f: Fatti) -> Analisi:
        a = Analisi(self.regola, self.materia, modello=self.modello)
        a.forma = "atto" if c.tipo == "redazione" else "parere (consulenza)"
        a.rimedio, a.giudice = self.rimedio, self.giudice
        a.capito = [self.capito or f"Domanda su: {self.nome}."]
        for nome in ("conclusione", "inquadramento", "competenza", "procedibilita", "rito", "termini"):
            setattr(a, nome, list(getattr(self, nome)))
        a.cosa_fare, a.avvertenze, a.dubbi = list(self.cosa_fare), list(self.avvertenze), list(self.dubbi)
        a.dati_mancanti = list(self.dati)
        for s in self.scadenze:
            p = _calcola(s, f)
            if p is not None:
                a.termini.append(p)
        if self.extra is not None:
            self.extra(a, c, f)
        if c.tipo == "redazione" and self.bozza is not None:
            from ..bozze import ricorso_generico

            b = self.bozza
            a.bozza = ricorso_generico(b.titolo, a.giudice, f, b.oggetto, b.diritto, b.conclusioni, b.documenti,
                                       b.norme_struttura)
        return a

    def regola_harness(self) -> tuple[str, Callable[[Comprensione, Fatti], int], Callable[[Comprensione, Fatti], Analisi]]:
        return (self.regola, self.riconosci, self.analizza)


def _calcola(s: Scadenza, f: Fatti) -> Punto | None:
    from .strumenti import data_dopo

    dal = data_dopo(f, s.evento)
    if dal is None:
        return None
    if s.modello:
        from ..termini import termine

        al = termine(s.modello, dal)
        return Punto(f"Dal {data_breve(dal)}: {s.descrizione} {data_breve(al)} ({s.quantita} {s.unita}, calcolo del motore "
                     f"dei termini di IUSENTRA).", list(s.rif))
    if s.unita == "giorni":
        al = termine_giorni(dal, s.quantita, sospensione_feriale=s.sospensione_feriale, sostanziale=s.sostanziale)
    elif s.unita == "mesi":
        al = termine_mesi(dal, s.quantita, sospensione_feriale=s.sospensione_feriale, sostanziale=s.sostanziale)
    else:
        al = termine_anni(dal, s.quantita, sostanziale=s.sostanziale)
    feriale = (" con la sospensione feriale dei termini" if s.sospensione_feriale and not s.sostanziale
               else " senza sospensione feriale")
    return Punto(f"Dal {data_breve(dal)}: {s.descrizione} {data_breve(al)} ({s.quantita} {s.unita}{feriale}).",
                 list(s.rif))


def R(chiave: str, ancora: str, comma: str = "") -> Rif:
    return Rif(chiave, ancora, comma)


def p(testo: str, *rif: Rif) -> Punto:
    return Punto(testo, list(rif))
