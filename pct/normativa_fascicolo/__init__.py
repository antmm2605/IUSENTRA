"""La normativa pertinente a un fascicolo: procedura, termini aperti, tipi di documento.

Richiesta dell'avvocato del 02/11/2026: un'icona «Normativa» nel fascicolo che
mostri subito le norme di quella pratica. Il pacchetto aggrega soltanto dati
già presenti nel software (schede procedurali, scadenze, catalogo dei
documenti) e registri di fonti ufficiali con URL e data di consultazione:
nessun documento viene letto, nessun testo normativo viene scritto qui.
"""

from __future__ import annotations

from typing import Any

from .documenti import norme_documenti
from .materie import materie_del_fascicolo
from .procedura import norme_procedura
from .termini import norme_termini

VERSIONE = "2026.11.02.normativa-fascicolo.v1"


def normativa_del_fascicolo(
    fascicolo: dict[str, Any], *, scadenze: list[Any], catalogo: list[Any], nomi_documenti: dict[str, str],
) -> dict[str, Any]:
    procedura = norme_procedura(fascicolo)
    termini = norme_termini(scadenze)
    documenti = norme_documenti(catalogo, nomi_documenti, len(nomi_documenti))
    gruppi = [
        {"id": "procedura", "titolo": "Procedura e fasi", "descrizione": "Le norme del rito, del deposito e delle notifiche del fascicolo.",
         "voci": procedura["voci"], "vuoto": procedura["vuoto"]},
        {"id": "termini", "titolo": "Termini e udienze aperti", "descrizione": "Le norme dei termini e delle udienze ancora aperti.",
         "voci": termini["voci"], "vuoto": termini["vuoto"]},
        {"id": "documenti", "titolo": "Documenti del fascicolo", "descrizione": "Le norme che definiscono i tipi di documento presenti.",
         "voci": documenti["voci"], "vuoto": documenti["vuoto"]},
    ]
    return {
        "versione": VERSIONE,
        "contesto": {**procedura["contesto"], "termini": termini["termini"],
                     "documenti": documenti["documenti"], "catalogati": documenti["catalogati"]},
        "materie": materie_del_fascicolo(str(fascicolo.get("tipo") or ""), str(fascicolo.get("area_pratica") or "")),
        "gruppi": gruppi,
        "totale": sum(len(g["voci"]) for g in gruppi),
    }


__all__ = ["VERSIONE", "materie_del_fascicolo", "normativa_del_fascicolo"]
