"""Modelli immutabili del catalogo contratti (solo struttura, nessuna regola)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

FORME = ("libera", "scritta", "scritta_ad_substantiam", "scrittura_autenticata", "atto_pubblico")
QUALIFICAZIONI = ("tipico", "atipico", "misto", "accessorio", "atto_collegato")


@dataclass(frozen=True)
class Domanda:
    id: str
    testo: str
    tipo: str = "si_no"  # si_no | scelta | testo | numero
    opzioni: tuple[str, ...] = ()


@dataclass(frozen=True)
class Controllo:
    """Regola dichiarativa: se i fatti soddisfano ``quando`` si segnala ``esito``."""

    id: str
    quando: dict
    esito: str  # blocco | valutazione_avvocato | adempimento | avviso
    messaggio: str
    norma: str


@dataclass(frozen=True)
class Variante:
    id: str
    nome: str
    riferimenti: tuple[str, ...]
    quando: dict = field(default_factory=dict)
    forma: str = "scritta"


@dataclass(frozen=True)
class Contratto:
    id: str
    nome: str
    area: str
    riferimenti: tuple[str, ...]
    qualificazione: str = "tipico"
    forma: str = "scritta"
    note: str = ""
    varianti: tuple[Variante, ...] = ()
    domande: tuple[Domanda, ...] = ()
    controlli: tuple[Controllo, ...] = ()
    clausole: tuple[str, ...] = ()

    def come_dict(self) -> dict:
        return asdict(self)
