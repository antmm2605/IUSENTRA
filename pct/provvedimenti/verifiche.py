"""Requisiti formali che il software può controllare da solo, e i casi fuori ambito.

* Preavviso minimo tra comunicazione e udienza (art. 127-bis, comma 2, c.p.c.: quindici
  giorni; art. 79 D.Lgs. 175/2024: trenta giorni liberi; art. 71, comma 5, c.p.a.:
  sessanta giorni). Se il preavviso è insufficiente lo si segnala; se manca un dato non
  si segnala nulla (nessun allarme indovinato).
* Le norme del c.p.c. sulle udienze (127-bis, 127-ter) non valgono nel processo penale,
  amministrativo e tributario: un testo che le cita in quei riti è un caso da chiedere.
"""

from __future__ import annotations

import re

from .materia import RITI_CPC
from .modello import Voce
from .regole import tabella
from .riferimenti import Riferimenti


def verifiche_preavviso(tipi: tuple[str, ...], materia: str, rif: Riferimenti) -> list[Voce]:
    if rif.udienza is None or rif.comunicata_il is None or rif.udienza_fonte != "provvedimento":
        return []
    voci: list[Voce] = []
    for regola in tabella().get("verifiche_preavviso") or []:
        if materia not in regola["materie"] or not set(regola["tipi"]) & set(tipi):
            continue
        intervallo = (rif.udienza - rif.comunicata_il).days - (1 if regola.get("liberi") else 0)
        if intervallo >= int(regola["giorni"]):
            continue
        voci.append(Voce(
            f"verifica.{regola['id']}", "verifica",
            f"{regola['testo']}: tra la comunicazione del {rif.comunicata_il:%d/%m/%Y} e l'udienza del {rif.udienza:%d/%m/%Y} "
            f"corrono {max(intervallo, 0)} giorni, verificare",
            norme=tuple(regola["norme"]), confidenza=0.8, giorno=rif.udienza,
            dati=(rif.dato_udienza(), ("Data di comunicazione", f"{rif.comunicata_il:%d/%m/%Y}", "consegna della PEC di cancelleria")),
        ))
    return voci


def fuori_ambito(tipi: tuple[str, ...], materia: str, prova: dict[str, str], testo: str) -> list[Voce]:
    if materia in RITI_CPC:
        return []
    voci = []
    for tipo, norma, nome in (("note_127_ter", "cpc_127ter", "art. 127-ter"), ("udienza_remota_127_bis", "cpc_127bis", "art. 127-bis")):
        if tipo in tipi and re.search(rf"\b127\s*[-\s]?\s*{nome[-3:]}\b", testo, re.I):
            voci.append(Voce(
                f"esclusione.{tipo}", "da_verificare", f"Il provvedimento richiama l'{nome} c.p.c. in un procedimento {materia}",
                norme=(norma,), prova=prova.get(tipo, ""), confidenza=0.5,
                domanda=(f"L'{nome} c.p.c. regola le udienze del processo civile: in un procedimento {materia} valgono le "
                         "regole del suo rito. Indicare se il provvedimento assegna termini e quali."),
            ))
    return voci


__all__ = ["fuori_ambito", "verifiche_preavviso"]
