"""Stato di salute delle sorgenti che alimentano la Panoramica React.

La Panoramica legge una decina di repository diversi (agenda, scadenziario,
fascicoli, PEC, preventivi, fatturazione...). Ogni lettura e' protetta: se un
archivio non risponde la sezione resta vuota invece di far cadere la pagina.

Il difetto di quel comportamento e' che uno zero da archivio irraggiungibile
era indistinguibile da uno zero vero, e l'utente vedeva comunque "Dati
aggiornati". Qui si tiene traccia delle sorgenti cadute durante la
costruzione del payload, cosi' la UI puo' dichiarare esplicitamente che il
quadro e' parziale e quali aree non sono attendibili.

Il tracciamento e' per contesto di esecuzione (``ContextVar``): resta isolato
per richiesta anche con i worker gevent, e fuori dalla costruzione del
payload la registrazione e' inerte.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterable, Iterator

__all__ = [
    "etichetta_sorgente",
    "etichette_sorgenti",
    "messaggio_sorgenti_degradate",
    "segnala_sorgente_non_disponibile",
    "traccia_sorgenti_panoramica",
]

# Etichette utente in italiano: i label tecnici del bridge non sono adatti
# a comparire in un avviso mostrato all'avvocato.
_ETICHETTE: dict[str, str] = {
    "agenda": "Agenda",
    "clienti": "Anagrafica clienti",
    "email_ordinaria": "Email ordinaria",
    "fascicoli": "Fascicoli",
    "fascicolo": "Fascicoli",
    "fatturazione": "Fatturazione",
    "pec": "Casella PEC",
    "preventivi": "Preventivi",
    "scadenziario": "Scadenziario",
    "soggetti": "Soggetti",
    "timesheet": "Timesheet",
    "workspace_intelligente": "Regia operativa",
}

_SORGENTI_DEGRADATE: ContextVar[set[str] | None] = ContextVar(
    "iusentra_panoramica_sorgenti_degradate", default=None
)


@contextmanager
def traccia_sorgenti_panoramica() -> Iterator[set[str]]:
    """Attiva la raccolta delle sorgenti non disponibili per il blocco corrente."""

    registro: set[str] = set()
    token = _SORGENTI_DEGRADATE.set(registro)
    try:
        yield registro
    finally:
        _SORGENTI_DEGRADATE.reset(token)


def segnala_sorgente_non_disponibile(label: str) -> None:
    """Registra una sorgente caduta; inerte fuori dal tracciamento attivo."""

    registro = _SORGENTI_DEGRADATE.get()
    if registro is None:
        return
    pulito = str(label or "").strip()
    if pulito:
        registro.add(pulito)


def etichetta_sorgente(label: str) -> str:
    """Nome leggibile della sorgente, con ricaduta sul label tecnico."""

    pulito = str(label or "").strip()
    return _ETICHETTE.get(pulito, pulito.replace("_", " ").capitalize() or "Archivio")


def etichette_sorgenti(labels: Iterable[str]) -> list[str]:
    """Etichette utente ordinate e deduplicate delle sorgenti indicate."""

    return sorted({etichetta_sorgente(label) for label in labels if str(label or "").strip()})


def messaggio_sorgenti_degradate(labels: Iterable[str]) -> str:
    """Avviso italiano da mostrare quando il quadro operativo e' parziale."""

    etichette = etichette_sorgenti(labels)
    if not etichette:
        return ""
    elenco = ", ".join(etichette)
    if len(etichette) == 1:
        return (
            f"Quadro parziale: l'archivio {elenco} non ha risposto. "
            "I conteggi di questa area non sono attendibili finche' non ricarichi."
        )
    return (
        f"Quadro parziale: gli archivi {elenco} non hanno risposto. "
        "I conteggi di queste aree non sono attendibili finche' non ricarichi."
    )
