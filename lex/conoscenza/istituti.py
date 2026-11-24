"""Tassonomia degli istituti per materia (``dati/istituti.json``).

Ogni istituto ha un ID stabile (non cambia se cambia il nome), una materia, le regole dell'harness che lo trattano e
le norme di riferimento verificate nella biblioteca vigente. L'ordine delle materie mette prima quelle più frequenti
nello studio (pubblico impiego, lavoro, previdenza, esecuzione contro la PA, amministrativo).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATI = Path(__file__).with_name("dati")
TASSONOMIA = DATI / "istituti.json"


@dataclass(frozen=True)
class NormaRiferimento:
    chiave: str
    citazione: str
    rubrica: str = ""
    stato_biblioteca: str = ""
    comma: str = ""          # comma vigente pertinente, quando l'articolo ha commi abrogati
    nota_commi: str = ""     # quali commi sono abrogati e quali vigenti, letto dal testo della biblioteca


@dataclass(frozen=True)
class Istituto:
    id: str
    materia: str
    nome: str
    regole: tuple[str, ...] = ()
    norme: tuple[NormaRiferimento, ...] = ()
    frase_esempio: str = ""
    origine: str = ""
    norme_abrogate: tuple[dict, ...] = ()        # storico: mai norme di riferimento (abrogata_da, decorrenza, sede vigente)
    extra: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def id_scheda(self) -> str:
        return id_scheda(self.materia, self.id)


def slug(testo: str) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "").lower())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def id_scheda(materia: str, istituto: str) -> str:
    """ID stabile della scheda: «ist-<istituto>». La materia non entra nell'ID: spostare un istituto di materia o
    rinominarlo non rompe collegamenti, annotazioni e citazioni."""
    return f"ist-{slug(istituto)}"


@lru_cache(maxsize=4)
def _carica(percorso: str) -> dict:
    return json.loads(Path(percorso).read_text(encoding="utf-8"))


def carica(percorso: Path | None = None) -> tuple[list[str], list[Istituto]]:
    dati = _carica(str(percorso or TASSONOMIA))
    istituti = []
    for v in dati["istituti"]:
        norme = tuple(NormaRiferimento(n["chiave"], n.get("citazione", ""), n.get("rubrica", ""),
                                       n.get("stato_biblioteca", ""), n.get("comma", ""), n.get("nota_commi", ""))
                      for n in v.get("norme", []))
        istituti.append(Istituto(v["id"], v["materia"], v["nome"], tuple(v.get("regole", [])), norme,
                                 v.get("frase_esempio", ""), v.get("origine", ""), tuple(v.get("norme_abrogate", []))))
    materie = list(dati.get("materie") or dict.fromkeys(i.materia for i in istituti))
    for i in istituti:
        if i.materia not in materie:
            materie.append(i.materia)
    return materie, istituti
