"""Riconvalida: un'anomalia aperta vale solo se le regole di oggi la rifarebbero.

Le regole di lettura si stringono nel tempo. Quando una regola nuova stabilisce
che un testo non è una data — «l. 69/2023» è la legge 69 del 2023, non il 1°
giugno 2023 — le anomalie che quella lettura aveva già prodotto restano aperte
nel registro e continuano a chiedere all'avvocato di confermare un errore che
il software non commette più.

Qui le anomalie aperte si ripassano con le regole correnti: quelle che oggi non
nascerebbero si chiudono da sole, dichiarando quale regola le ha superate. Le
altre restano aperte: non si tocca ciò che l'avvocato deve ancora decidere, e
non si tocca mai una decisione già presa (confermata, corretta, ignorata).

Base normativa dell'obbligo di tracciare: art. 20 CAD (integrità e
riconoscibilità del documento informatico) — la chiusura è registrata, non
cancellata.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from .modello import Anomalia
from .verifica import verifica_date_lette

AUTORE_RICONVALIDA = "riconvalida automatica"
# I campi che contengono una data letta: solo su questi la riconvalida decide.
CAMPI_DATA = frozenset({"data", "udienza", "termine", "costituzione", "notifica", "deposito", "decorrenza", "accettazione", "consegna", "data_atto", "data_documento"})


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def regola_superata(anomalia: Anomalia, *, contesto: dict[str, Any]) -> str:
    """Perché l'anomalia oggi non nascerebbe, oppure stringa vuota se nascerebbe ancora.

    Si ripassa lo stesso valore con lo stesso ingresso che l'aveva generata: se
    le regole correnti non producono più alcuna anomalia per quel valore, la
    vecchia è superata. Il motivo dichiara la regola che ha deciso.
    """
    if anomalia.stato != "aperta" or anomalia.campo not in CAMPI_DATA:
        return ""
    valore = _testo(anomalia.valore_letto)
    if not valore:
        return ""
    from legal_ocr.formulario.riferimenti_normativi import e_riferimento_normativo

    riferimento = e_riferimento_normativo(valore, 0, len(valore))
    if riferimento:
        return f"«{valore}» è un riferimento normativo ({riferimento}), non una data: la regola che l'aveva segnalato è superata."
    rifatte = verifica_date_lette([{"valore": valore, "campo": anomalia.campo, "contesto": anomalia.contesto}], contesto)
    if not rifatte:
        return f"Con le regole correnti «{valore}» non produce più un'anomalia: il controllo che l'aveva segnalata è superato."
    return ""


def anomalie_superate(anomalie: Iterable[Anomalia], *, contesto: dict[str, Any]) -> list[tuple[Anomalia, str]]:
    """Le anomalie aperte che le regole di oggi non rifarebbero, con il perché."""
    esito: list[tuple[Anomalia, str]] = []
    for anomalia in anomalie:
        motivo = regola_superata(anomalia, contesto=contesto)
        if motivo:
            esito.append((anomalia, motivo))
    return esito


def contesto_riconvalida(fascicolo: Any, *, oggi: date | None = None) -> dict[str, Any]:
    from .verifica_date import orizzonte_fascicolo

    return orizzonte_fascicolo(fascicolo, oggi=oggi)


__all__ = ["AUTORE_RICONVALIDA", "CAMPI_DATA", "anomalie_superate", "contesto_riconvalida", "regola_superata"]
