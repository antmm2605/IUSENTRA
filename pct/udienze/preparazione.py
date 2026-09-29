"""I cinque passi della preparazione dell'udienza e il loro stato, letti dalla sessione salvata."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

PASSI = [
    (1, "briefing", "Quadro della causa", "Chi, cosa, dove: dati dell'udienza, termini aperti e verifiche di legge."),
    (2, "documenti", "Documenti", "Cosa portare o avere pronto: un clic per ogni documento."),
    (3, "strategia", "Strategia", "Argomenti, richieste al giudice ed eccezioni."),
    (4, "partenza", "Prima di uscire", "Cliente avvisato, collegamento o trasferta, firma per eventuali depositi."),
    (5, "esito", "Esito", "Cosa è successo: rinvio in agenda, termini assegnati nello scadenziario, nota nel fascicolo."),
]
STATI_DOCUMENTO = {"da_portare": "Da preparare", "pronto": "Pronto", "non_necessario": "Non serve"}
ESITI = {"rinvio": "Rinvio", "trattenuta": "Trattenuta in decisione", "riserva": "Riserva del giudice", "conciliata": "Conciliata",
         "favorevole": "Favorevole", "parziale": "Parzialmente favorevole", "sfavorevole": "Sfavorevole", "sospeso": "Sospeso"}


def passi(sessione: Any) -> list[dict[str, Any]]:
    fatti = [bool(getattr(sessione, f"step{n}_confermato", False)) for n in range(1, 6)]
    return [{"n": n, "chiave": chiave, "titolo": titolo, "descrizione": descrizione, "fatto": fatti[n - 1]}
            for n, chiave, titolo, descrizione in PASSI]


def stato_etichetta(sessione: Any | None) -> str:
    if sessione is None:
        return "Da preparare"
    if getattr(sessione, "stato", "") == "completato":
        return "Esito registrato"
    fatti = sum(1 for p in passi(sessione) if p["fatto"])
    return "Preparata" if fatti >= 4 else f"{fatti} di 5 passi"


def quando(data_ora: str, oggi: date) -> str:
    """«Oggi alle 10:00», «Domani alle 10:00», «Tra 4 giorni», «Passata»."""

    try:
        momento = datetime.fromisoformat(str(data_ora)[:19])
    except ValueError:
        return ""
    delta = (momento.date() - oggi).days
    ora = momento.strftime("%H:%M")
    if delta < 0:
        return "Passata"
    if delta == 0:
        return f"Oggi alle {ora}"
    if delta == 1:
        return f"Domani alle {ora}"
    return f"Tra {delta} giorni, alle {ora}"


__all__ = ["ESITI", "PASSI", "STATI_DOCUMENTO", "passi", "quando", "stato_etichetta"]
