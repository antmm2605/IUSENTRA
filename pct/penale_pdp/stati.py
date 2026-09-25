"""Stati del deposito sul PDP (provvedimento DGSIA 11/07/2023, art. 7 co. 4).

IUSENTRA aggiunge solo due stati propri, prima dell'invio: ``BOZZA`` (in
preparazione) e ``PRONTO`` (controlli superati, da inviare dal portale).
Tutto il resto è lo stato che il portale mostra all'avvocato.
"""

from __future__ import annotations

import re

STATI_UFFICIALI: tuple[tuple[str, str, str], ...] = (
    ("INVIATO", "Inviato", "eseguita con successo l'operazione di invio"),
    ("IN_TRANSITO", "In transito", "in attesa di smistamento al sistema dell'ufficio destinatario"),
    ("IN_FASE_DI_VERIFICA", "In fase di verifica", "pervenuto nel sistema dell'ufficio destinatario"),
    ("ACCOLTO", "Accolto", "atto associato al procedimento; per denuncia e querela: procedimento iscritto"),
    ("RIGETTATO", "Rigettato", "deposito rifiutato; la motivazione è sul PDP"),
    ("ERRORE_TECNICO", "Errore tecnico", "problema di trasmissione: il deposito va ripetuto"),
)
STATI_LOCALI: tuple[tuple[str, str, str], ...] = (
    ("BOZZA", "In preparazione", "deposito in preparazione in IUSENTRA"),
    ("PRONTO", "Pronto per il PDP", "controlli superati: da inviare dal portale"),
)
DEFINITIVI = frozenset({"ACCOLTO", "RIGETTATO", "ERRORE_TECNICO"})
TUTTI = tuple(s[0] for s in STATI_LOCALI + STATI_UFFICIALI)
ETICHETTE = {codice: etichetta for codice, etichetta, _ in STATI_LOCALI + STATI_UFFICIALI}
TONI = {
    "BOZZA": "neutral", "PRONTO": "info", "INVIATO": "info", "IN_TRANSITO": "info",
    "IN_FASE_DI_VERIFICA": "warning", "ACCOLTO": "success", "RIGETTATO": "danger", "ERRORE_TECNICO": "danger",
}

_SINONIMI = (
    (r"errore\s+tecnico", "ERRORE_TECNICO"),
    (r"rigettat|rifiutat|respint", "RIGETTATO"),
    (r"accolt|accettat", "ACCOLTO"),
    (r"(in\s+fase\s+di\s+)?verific|presa\s+in\s+carico", "IN_FASE_DI_VERIFICA"),
    (r"in\s+transito", "IN_TRANSITO"),
    (r"inviat", "INVIATO"),
)


def normalizza(valore: str) -> str:
    """Lo stato ufficiale da un testo del portale (elenco, export, ricevuta); "" se ignoto."""
    testo = " ".join(str(valore or "").casefold().replace("_", " ").split())
    if not testo:
        return ""
    if testo.upper().replace(" ", "_") in TUTTI:
        return testo.upper().replace(" ", "_")
    for schema, codice in _SINONIMI:
        if re.search(schema, testo):
            return codice
    return ""


def etichetta(codice: str) -> str:
    return ETICHETTE.get(str(codice or "").upper(), str(codice or ""))


def e_definitivo(codice: str) -> bool:
    return str(codice or "").upper() in DEFINITIVI


def descrizione(codice: str) -> str:
    return next((d for c, _, d in STATI_LOCALI + STATI_UFFICIALI if c == str(codice or "").upper()), "")


__all__ = ["DEFINITIVI", "ETICHETTE", "STATI_LOCALI", "STATI_UFFICIALI", "TONI", "TUTTI",
           "descrizione", "e_definitivo", "etichetta", "normalizza"]
