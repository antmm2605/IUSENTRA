"""Collaudo normativo dei calcolatori: Lex usa solo quelli che lo superano.

Un calcolatore può rispondere al posto del modello solo se il suo risultato coincide
con quello che la norma impone su casi di riferimento verificati a mano sul testo
ufficiale (regola delle fonti certe, AGENTS.md; richiesta dell'avvocato del
31/10/2026: «dobbiamo essere certi che i calcolatori siano corretti e rispettino
decreti e normative»).

Ogni caso dichiara i dati, i valori attesi, la norma da cui discendono e la data
della verifica. Il collaudo si ripete all'avvio e nei test: se una tabella
normativa cambia e il calcolatore non è aggiornato, il caso fallisce e Lex smette
di usarlo (chiuso per impostazione) finché non viene corretto o il caso
aggiornato sulla nuova fonte.

Aggiungere un calcolatore: almeno un caso per ciascun regime o scaglione che
cambia il risultato, con valori ricavati dalla fonte e non dal calcolatore stesso.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pct.calcolatori.metodi import TOOL_METHODS


@dataclass(frozen=True)
class CasoDiCollaudo:
    descrizione: str
    dati: dict[str, str]
    attesi: dict[str, Any]
    norma: str
    verificato_il: str


_CU = "art. 13, comma 1, D.P.R. 115/2002"
_CU_GRADI = "art. 13, commi 1-bis e 3, D.P.R. 115/2002 (appello +50%, cassazione doppio, monitorio metà)"


def _cu(valore: str, categoria: str = "civile_ordinario", grado: str = "primo_grado") -> dict[str, str]:
    return {"cu_categoria": categoria, "cu_grado": grado, "cu_valore": valore}


CASI: dict[str, tuple[CasoDiCollaudo, ...]] = {
    "contributo_unificato": (
        CasoDiCollaudo("primo scaglione, fino a 1.100 euro", _cu("1100"), {"totale": 43.0}, _CU, "2026-10-31"),
        CasoDiCollaudo("secondo scaglione, oltre 1.100 euro", _cu("1101"), {"totale": 98.0}, _CU, "2026-10-31"),
        CasoDiCollaudo("scaglione 26.000-52.000 euro", _cu("42350"), {"totale": 518.0}, _CU, "2026-10-31"),
        CasoDiCollaudo("oltre 520.000 euro", _cu("600000"), {"totale": 1686.0}, _CU, "2026-10-31"),
        CasoDiCollaudo("ricorso per decreto ingiuntivo: metà", _cu("42350", "decreto_ingiuntivo"), {"totale": 259.0}, _CU_GRADI, "2026-10-31"),
        CasoDiCollaudo("appello: aumento della metà", _cu("42350", grado="appello"), {"totale": 777.0}, _CU_GRADI, "2026-10-31"),
        CasoDiCollaudo("cassazione: doppio", _cu("42350", grado="cassazione"), {"totale": 1036.0}, _CU_GRADI, "2026-10-31"),
    ),
    # «interessi»: casi in collaudo_casi/credito.json (serie storica dal 1942, collaudo del 31/10/2026)
}


def _casi_da_file() -> dict[str, tuple[CasoDiCollaudo, ...]]:
    """Casi per area in ``collaudo_casi/*.json`` (verificati sulla norma dai collaudi del 31/10/2026)."""
    import json
    from pathlib import Path

    casi: dict[str, tuple[CasoDiCollaudo, ...]] = {}
    for percorso in sorted((Path(__file__).parent / "collaudo_casi").glob("*.json")):
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        verificato = str(dati.get("_verificato_il") or "")
        for tool, voci in dati.items():
            if tool.startswith("_"):
                continue
            casi[tool] = tuple(
                CasoDiCollaudo(v["descrizione"], dict(v["dati"]), dict(v["attesi"]), v["norma"], verificato)
                for v in voci
            )
    return casi


CASI.update(_casi_da_file())


def _coincide(atteso: Any, ottenuto: Any) -> bool:
    """Numeri con tolleranza di mezzo centesimo; dizionari ed elenchi come sottoinsiemi attesi."""
    if isinstance(atteso, bool) or atteso is None:
        return ottenuto == atteso
    if isinstance(atteso, (int, float)):
        try:
            return abs(float(ottenuto) - float(atteso)) < 0.005
        except (TypeError, ValueError):
            return False
    if isinstance(atteso, dict):
        return isinstance(ottenuto, dict) and all(_coincide(v, ottenuto.get(k)) for k, v in atteso.items())
    if isinstance(atteso, list):
        return isinstance(ottenuto, list) and len(ottenuto) >= len(atteso) and all(
            _coincide(a, o) for a, o in zip(atteso, ottenuto))
    return ottenuto == atteso


def esito_caso(gestore: Any, tool: str, caso: CasoDiCollaudo) -> str:
    """Stringa vuota se il caso è superato, altrimenti il motivo in italiano."""
    metodo = TOOL_METHODS.get(tool)
    if not metodo:
        return f"strumento «{tool}» senza metodo di calcolo"
    try:
        risultato = getattr(gestore, metodo)(dict(caso.dati))
    except Exception as exc:  # il collaudo non deve mai interrompere chi lo chiama
        return f"{caso.descrizione}: calcolo non eseguito ({type(exc).__name__})"
    for chiave, atteso in caso.attesi.items():
        ottenuto = risultato.get(chiave) if isinstance(risultato, dict) else None
        if not _coincide(atteso, ottenuto):
            return f"{caso.descrizione}: atteso {chiave}={atteso} ({caso.norma}), ottenuto {ottenuto}"
    return ""


def collauda(gestore: Any) -> dict[str, list[str]]:
    """Per ogni strumento con casi: elenco dei casi falliti (vuoto = collaudato)."""
    return {tool: [motivo for caso in casi if (motivo := esito_caso(gestore, tool, caso))] for tool, casi in CASI.items()}


def strumenti_collaudati(gestore: Any) -> frozenset[str]:
    """Gli strumenti che Lex può usare: tutti i casi superati."""
    return frozenset(tool for tool, falliti in collauda(gestore).items() if not falliti)


__all__ = ["CASI", "CasoDiCollaudo", "collauda", "esito_caso", "strumenti_collaudati"]
