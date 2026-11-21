"""Riammissione dei numeri di ruolo respinti da una regola superata (riconvalida, 21/11/2026).

Un numero di ruolo letto nell'intestazione di un provvedimento è il dato che lega il provvedimento alla causa
(art. 132, primo comma, n. 1, c.p.c.: la sentenza indica il giudice che l'ha pronunciata; art. 36 disp. att. c.p.c.
e D.M. 44/2011 art. 3: il ruolo generale identifica il procedimento). Prima della correzione 0d7262bb il collaudo
respingeva il ruolo quando il contesto salvato tagliava a metà l'ultima parola dell'ufficio («TRIBUNALE DI REGGIO
CALAB» per «TRIBUNALE DI REGGIO DI CALABRIA»): la sentenza della causa usciva dalla Lettura e il modello non
calcolava né il termine per impugnare né i centoventi giorni prima del precetto (art. 14 D.L. 669/1996).

La correzione riguardava le letture nuove e l'esclusione del documento; il fatto già registrato restava «respinto».
Qui la regola di oggi ripassa quei fatti senza rileggere i documenti: se l'unica ragione del rifiuto è l'ufficio e il
collaudo corrente lo dà per compatibile, il fatto torna al verdetto che il collaudo gli darebbe oggi. Le decisioni
dell'avvocato (corretta, ignorata) non si toccano.

Modulo puro: riceve i fatti, restituisce i fatti da riammettere con il nuovo verdetto e le nuove prove.
"""

from __future__ import annotations

import copy
import re
from typing import Iterable

from pct.registro_letture.fatti_repository import Fatto

_UFFICIO_DEL_FASCICOLO = re.compile(r"dall'ufficio del fascicolo\s+(?P<ufficio>.+)$", re.IGNORECASE | re.DOTALL)


def _ufficio_della_prova(prova: dict) -> str:
    trovato = _UFFICIO_DEL_FASCICOLO.search(str(prova.get("dettaglio") or ""))
    return " ".join(trovato.group("ufficio").split()) if trovato else ""


def respinto_da_regola_superata(fatto: Fatto) -> str:
    """L'ufficio del fascicolo se il ruolo è respinto solo per l'ufficio e la regola di oggi lo ammette; altrimenti ''."""
    from .collaudo import ruolo_compatibile_con_ufficio

    if fatto.categoria != "ruolo" or fatto.verifica != "respinta":
        return ""
    respinte = [p for p in fatto.prove if isinstance(p, dict) and p.get("esito") == "respinta"]
    if not respinte or any(p.get("codice") != "ufficio_giudiziario" for p in respinte):
        return ""
    if any(isinstance(p, dict) and p.get("codice") == "decisione_avvocato" for p in fatto.prove):
        return ""
    uffici = {_ufficio_della_prova(p) for p in respinte}
    if len(uffici) != 1 or "" in uffici:
        return ""
    ufficio = uffici.pop()
    return ufficio if ruolo_compatibile_con_ufficio(fatto, ufficio) else ""


def ruoli_da_riammettere(fatti: Iterable[Fatto], *, numero_rg: str, anno_rg: str) -> list[Fatto]:
    """I fatti di ruolo da riammettere, già ricollaudati con la regola corrente (copie: gli originali restano)."""
    from .collaudo import Contesto, _collauda_ruolo, _prova

    esito: list[Fatto] = []
    for fatto in fatti:
        ufficio = respinto_da_regola_superata(fatto)
        if not ufficio:
            continue
        nuovo = copy.deepcopy(fatto)
        nuovo.prove = [p for p in nuovo.prove
                       if not (isinstance(p, dict) and p.get("codice") == "ufficio_giudiziario" and p.get("esito") == "respinta")]
        nuovo.verifica = "plausibile"
        _collauda_ruolo(nuovo, Contesto(numero_rg=numero_rg, anno_rg=anno_rg, ufficio_giudiziario=ufficio))
        if nuovo.verifica == "respinta":
            continue
        nuovo.prove.append(_prova("riconvalida", "ok",
                                  "riammesso: l'ufficio letto è tagliato a fine contesto, non un ufficio diverso "
                                  f"da {ufficio} (regola corrente del collaudo)"))
        esito.append(nuovo)
    return esito


__all__ = ["respinto_da_regola_superata", "ruoli_da_riammettere"]
