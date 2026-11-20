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


# ------------------------------------------------------------------- casi del banco dell'avvocato (22 casi)
CRITERI = (("rimedio", "rimedio e forma"), ("giudice_rito", "giudice e rito"), ("norme", "norme essenziali"),
           ("termini_importi", "termini e importi"), ("avvertenze", "avvertenze e procedibilità"),
           ("dati", "dati mancanti"), ("bozza", "bozza dell'atto"), ("inventate", "nessuna norma inventata"))


def carica_casi() -> list[dict]:
    return json.loads((CARTELLA / "casi_avvocato.json").read_text(encoding="utf-8"))["casi"]


@dataclass
class EsitoCaso:
    id: str
    criteri: dict = field(default_factory=dict)
    mancanze: list[str] = field(default_factory=list)

    @property
    def corretto(self) -> bool:
        return all(self.criteri.values())


def valuta_caso(caso: dict, risposta: str) -> EsitoCaso:
    from lex.harness.controllo import citazioni
    from lex.harness.norme import NORME, testo_norma

    att = caso["attese"]
    t = piano(risposta)
    e = EsitoCaso(caso["id"])
    for chiave in ("rimedio", "giudice_rito", "termini_importi", "avvertenze", "dati"):
        manca = [x for x in att.get(chiave, []) if not re.search(x, t)]
        e.criteri[chiave] = not manca
        e.mancanze += [f"{chiave}: {x}" for x in manca]
    citate = {k for _, k in citazioni(risposta)}
    manca = [k for k in att["norme"] if k not in citate and piano(NORME[k].citazione) not in t]
    e.criteri["norme"] = not manca
    e.mancanze += [f"norma: {k}" for k in manca]
    e.criteri["bozza"] = (not att.get("bozza")) or "**bozza dell'atto**" in t or "bozza dell'atto" in t
    if not e.criteri["bozza"]:
        e.mancanze.append("bozza assente")
    inv = sorted({c for c, k in citazioni(risposta) if not k or k not in NORME or testo_norma(k) is None})
    e.criteri["inventate"] = not inv
    e.mancanze += [f"non verificata: {x}" for x in inv]
    return e


def riepilogo_casi(esiti: list[EsitoCaso]) -> str:
    ok = sum(1 for e in esiti if e.corretto)
    righe = [f"Casi dell'avvocato corretti {ok}/{len(esiti)} ({100 * ok / max(1, len(esiti)):.0f}%)"]
    for chiave, nome in CRITERI:
        righe.append(f"  {nome}: {sum(1 for e in esiti if e.criteri.get(chiave))}/{len(esiti)}")
    for e in esiti:
        if not e.corretto:
            righe.append(f"- {e.id}: {e.mancanze}")
    return "\n".join(righe)
