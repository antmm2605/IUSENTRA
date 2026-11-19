"""Punteggio automatico del collaudo di Lex: norme attese citate, conclusione corretta, nessuna norma inventata.

Una domanda è «corretta» se la risposta contiene tutte le espressioni della conclusione attesa, nessuna espressione
vietata, cita tutte le norme attese e non contiene riferimenti normativi che il controllore non sa verificare.
Le domande operative sono corrette se non passano dall'harness (restano ai dati dello studio).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent


def carica() -> list[dict]:
    return json.loads((CARTELLA / "domande.json").read_text(encoding="utf-8"))["domande"]


def piano(testo: str) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "").replace("’", "'").lower())
    return " ".join("".join(c for c in base if not unicodedata.combining(c)).split())


@dataclass
class Esito:
    id: str
    corretta: bool
    mancanti: list[str] = field(default_factory=list)
    vietate: list[str] = field(default_factory=list)
    norme_mancanti: list[str] = field(default_factory=list)
    inventate: list[str] = field(default_factory=list)


def valuta(domanda: dict, risposta: str, *, operativa: bool | None = None) -> Esito:
    from lex.harness.controllo import citazioni
    from lex.harness.norme import NORME, testo_norma

    e = Esito(domanda["id"], True)
    if domanda["percorso"] == "operativa":
        e.corretta = bool(operativa)
        if not e.corretta:
            e.mancanti.append("la domanda operativa è stata deviata dall'harness")
        return e
    t = piano(risposta)
    e.mancanti = [x for x in domanda["conclusione"] if not re.search(x, t)]
    e.vietate = [x for x in domanda["vietate"] if re.search(x, t)]
    citate = {chiave for _, chiave in citazioni(risposta)}
    e.norme_mancanti = [k for k in domanda["norme_attese"] if k not in citate and piano(NORME[k].citazione) not in t]
    e.inventate = sorted({cit for cit, chiave in citazioni(risposta) if not chiave or chiave not in NORME or testo_norma(chiave) is None})
    e.corretta = not (e.mancanti or e.vietate or e.norme_mancanti or e.inventate)
    return e


def riepilogo(esiti: list[Esito]) -> str:
    giuste = sum(1 for x in esiti if x.corretta)
    inventate = sum(1 for x in esiti if x.inventate)
    righe = [f"Corrette {giuste}/{len(esiti)} ({100 * giuste / max(1, len(esiti)):.0f}%); risposte con norme non verificate: {inventate}"]
    for x in esiti:
        if not x.corretta:
            righe.append(f"- {x.id}: mancano {x.mancanti} vietate {x.vietate} norme {x.norme_mancanti} non verificate {x.inventate}")
    return "\n".join(righe)
