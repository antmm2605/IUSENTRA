"""Il passaggio spiegabile: che cosa il software ha fatto o propone, con quale regola e su quale base.

Ogni azione automatica del software si mostra all'avvocato come una sequenza
di passaggi. Un passaggio dichiara:

- che cosa è stato fatto o proposto (``titolo``) e in quale stato;
- la regola del software che l'ha prodotto (``regola_id`` e descrizione);
- la norma che la fonda (identificativi del registro ``pct/procedura_fasi/fonti.py``,
  con URL ufficiale e data di consultazione);
- le prove lette nei documenti o nelle PEC (un estratto breve) e i dati presi
  dal fascicolo;
- i campi che il passaggio ha valorizzato, distinguendo quelli fissati dalla
  norma (``vincolato``) da quelli che sono una scelta del software;
- i vincoli inderogabili (termine perentorio, deposito non autonomo) che
  nessuna regola dello studio può superare;
- le regole dello studio applicate o rifiutate.

Il modello è puro: nessun accesso a database o Flask, serializzabile in JSON.
Base normativa del principio: art. 3 D.M. 44/2011 e art. 20 CAD (integrità e
ricostruibilità di ciò che il sistema fa sui documenti informatici).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

# Gli stati, dal più automatico al più controllato dall'avvocato.
STATI = ("eseguito", "proposto", "da_confermare", "da_chiedere")
STATO_ESCLUSO = "escluso_dallo_studio"
ETICHETTE_STATO = {
    "eseguito": "eseguito dal software",
    "proposto": "proposto",
    "da_confermare": "da confermare",
    "da_chiedere": "da chiedere all'avvocato",
    STATO_ESCLUSO: "escluso da una regola dello studio",
}


def livello_controllo(stato: str) -> int:
    """Più alto = più controllo dell'avvocato."""
    return STATI.index(stato) if stato in STATI else len(STATI)


@dataclass(frozen=True)
class Prova:
    """Ciò che il software ha letto: un estratto breve con la sua provenienza."""

    tipo: str  # "pec", "documento", "fascicolo", "agenda", "norma"
    estratto: str
    fonte: str = ""  # oggetto PEC, nome del documento, campo del fascicolo
    riferimento: str = ""  # id del messaggio o del documento

    def come_dizionario(self) -> dict[str, Any]:
        return {"tipo": self.tipo, "estratto": self.estratto[:400], "fonte": self.fonte, "riferimento": self.riferimento}


@dataclass(frozen=True)
class Dato:
    """Un dato in ingresso usato dalla regola (es. «Prossima udienza: 12/01/2027» dall'agenda)."""

    etichetta: str
    valore: str
    fonte: str = ""

    def come_dizionario(self) -> dict[str, Any]:
        return {"etichetta": self.etichetta, "valore": self.valore, "fonte": self.fonte}


@dataclass(frozen=True)
class Campo:
    """Un valore prodotto dal passaggio; ``vincolato`` se lo fissa la norma o il provvedimento."""

    etichetta: str
    valore: str
    vincolato: bool = False
    motivo_vincolo: str = ""
    valore_software: str = ""  # valorizzato quando una regola dello studio lo ha cambiato
    regola_studio_id: str = ""

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "etichetta": self.etichetta,
            "valore": self.valore,
            "vincolato": self.vincolato,
            "motivoVincolo": self.motivo_vincolo,
            "valoreSoftware": self.valore_software,
            "regolaStudioId": self.regola_studio_id,
        }


@dataclass(frozen=True)
class Contesto:
    """Dove il passaggio è avvenuto: serve a decidere quali regole dello studio valgono."""

    fascicolo_id: str
    ufficio: str = ""
    giudice: str = ""
    materia: str = ""

    def come_dizionario(self) -> dict[str, Any]:
        return {"fascicoloId": self.fascicolo_id, "ufficio": self.ufficio, "giudice": self.giudice, "materia": self.materia}


@dataclass(frozen=True)
class Passaggio:
    chiave: str  # stabile per caso: regola + fascicolo + oggetto letto
    produttore: str  # «presidio PEC», «decreto 127-ter»…
    ordine: int
    titolo: str
    stato: str
    regola_id: str
    regola_descrizione: str
    contesto: Contesto
    norme: tuple[str, ...] = ()
    prove: tuple[Prova, ...] = ()
    dati: tuple[Dato, ...] = ()
    campi: dict[str, Campo] = field(default_factory=dict)
    vincoli: tuple[str, ...] = ()
    confidenza: float | None = None
    href: str = ""
    stato_software: str = ""  # lo stato prima delle regole dello studio
    regole_applicate: tuple[dict[str, Any], ...] = ()
    regole_rifiutate: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.stato not in STATI and self.stato != STATO_ESCLUSO:
            raise ValueError(f"Stato del passaggio non ammesso: {self.stato}")
        if not self.regola_id:
            raise ValueError("Ogni passaggio dichiara la regola che l'ha prodotto.")

    def con(self, **modifiche: Any) -> "Passaggio":
        return replace(self, **modifiche)

    def come_dizionario(self) -> dict[str, Any]:
        from pct.procedura_fasi.fonti import fonti

        return {
            "chiave": self.chiave,
            "produttore": self.produttore,
            "ordine": self.ordine,
            "titolo": self.titolo,
            "stato": self.stato,
            "statoEtichetta": ETICHETTE_STATO.get(self.stato, self.stato),
            "statoSoftware": self.stato_software or self.stato,
            "regola": {"id": self.regola_id, "descrizione": self.regola_descrizione},
            "norme": fonti(self.norme),
            "prove": [prova.come_dizionario() for prova in self.prove],
            "dati": [dato.come_dizionario() for dato in self.dati],
            "campi": {nome: campo.come_dizionario() for nome, campo in self.campi.items()},
            "vincoli": list(self.vincoli),
            "confidenza": self.confidenza,
            "contesto": self.contesto.come_dizionario(),
            "href": self.href,
            "regoleStudioApplicate": list(self.regole_applicate),
            "regoleStudioRifiutate": list(self.regole_rifiutate),
        }


def passaggio_da_dizionario(dati: dict[str, Any]) -> Passaggio:
    """Ricostruisce il passaggio salvato con la regola (istantanea dell'originale)."""
    contesto = dict(dati.get("contesto") or {})
    campi = {
        nome: Campo(
            etichetta=str(voce.get("etichetta") or nome), valore=str(voce.get("valore") or ""),
            vincolato=bool(voce.get("vincolato")), motivo_vincolo=str(voce.get("motivoVincolo") or ""),
        )
        for nome, voce in dict(dati.get("campi") or {}).items()
    }
    regola = dict(dati.get("regola") or {})
    return Passaggio(
        chiave=str(dati.get("chiave") or ""), produttore=str(dati.get("produttore") or ""), ordine=int(dati.get("ordine") or 0),
        titolo=str(dati.get("titolo") or ""), stato=str(dati.get("statoSoftware") or dati.get("stato") or "proposto"),
        regola_id=str(regola.get("id") or ""), regola_descrizione=str(regola.get("descrizione") or ""),
        contesto=Contesto(str(contesto.get("fascicoloId") or ""), str(contesto.get("ufficio") or ""),
                          str(contesto.get("giudice") or ""), str(contesto.get("materia") or "")),
        norme=tuple(str(voce.get("id") or "") for voce in dati.get("norme") or [] if isinstance(voce, dict)),
        campi=campi, vincoli=tuple(str(v) for v in dati.get("vincoli") or []),
        confidenza=dati.get("confidenza"),
    )


__all__ = [
    "Campo", "Contesto", "Dato", "ETICHETTE_STATO", "Passaggio", "Prova", "STATI", "STATO_ESCLUSO",
    "livello_controllo", "passaggio_da_dizionario",
]
