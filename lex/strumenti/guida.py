"""La mappa guida il retrieval: con un segnale certo si interrogano solo le fonti che la domanda chiede.

1. Archivi pubblici che il router non conosce (prassi AdE/INPS, Gazzetta Ufficiale, testi della giustizia
   amministrativa): la mappa aggiunge il loro adattatore quando la scelta della domanda li indica.
2. Domande giuridiche senza fascicolo con un riconoscimento esatto (articolo citato con il suo atto da leggere, non da
   analizzare, confrontare o applicare a un caso; pronunce su un articolo; pronuncia per estremi): ``SourceRouter``
   tiene solo gli adattatori degli strumenti scelti, più il web ufficiale di riserva (che parte solo se le evidenze
   interne non bastano); se il router non li aveva scelti la mappa li aggiunge.
In ogni altro caso la scelta delle fonti resta quella di sempre.

Spegnimento: variabile d'ambiente ``LEX_MAPPA_STRUMENTI=0``.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

_log = logging.getLogger(__name__)

# Motivi della scelta che non dipendono da parole chiave ma da un riconoscimento esatto (articolo + atto, estremi).
MOTIVI_CERTI = frozenset({"articolo citato", "pronunce sull'articolo", "pronuncia per estremi",
                          "pronuncia amministrativa per estremi"})
# Archivi pubblici che il router di oggi non conosce: la mappa li aggiunge quando la domanda li chiede.
STRUMENTI_DA_AGGIUNGERE = frozenset({"prassi_ade_inps", "gazzetta_ufficiale", "giustizia_amministrativa"})
WORKFLOW_GUIDATI = frozenset({"normativa", "giurisprudenza", "giurisprudenza_specifica", "prassi", "research", "fonti",
                              "question_answering", "intelligence", "compliance"})
_RISERVA = frozenset({"OfficialWebSource"})


# Una domanda che chiede di analizzare, confrontare o applicare la norma, o nomina altre fonti, non è una semplice
# lettura del testo: le fonti restano quelle del router.
_OLTRE_IL_TESTO = re.compile(
    r"analizz|confront|interpret|appli[ck]|orientament|dottrin|prassi|gazzetta|circolar|web|sito|caso|fattispecie|"
    r"mio cliente|parere|valut|spieg|commento|rapporto tra|differenz")


def attiva() -> bool:
    return os.environ.get("LEX_MAPPA_STRUMENTI", "1").strip().lower() not in {"0", "false", "no", "off"}


def adattatori_ammessi(domanda: str) -> frozenset[str]:
    """Gli adattatori da interrogare per la domanda, o insieme vuoto se la mappa non ha un segnale certo."""
    from .mappa import strumento
    from .scelta import normalizza, scegli

    scelte = scegli(domanda)
    if not scelte or any(c.motivo not in MOTIVI_CERTI for c in scelte):
        return frozenset()
    if _OLTRE_IL_TESTO.search(normalizza(domanda)):
        return frozenset()
    ammessi: set[str] = set()
    for c in scelte:
        voce = strumento(c.nome)
        if voce is None or not voce["adattatori"]:
            return frozenset()  # uno strumento senza adattatore: decide il percorso ordinario
        ammessi.update(voce["adattatori"])
    return frozenset(ammessi)


def _istanza(nome: str) -> Any | None:
    import importlib

    from .mappa import mappa

    modulo = mappa().get("adattatori", {}).get(nome)
    try:
        return getattr(importlib.import_module(modulo), nome)() if modulo else None
    except Exception:
        _log.exception("mappa degli strumenti: adattatore %s non costruibile", nome)
        return None


def _aggiunte(domanda: str, fonti: list[Any]) -> list[Any]:
    """Gli adattatori di prassi, Gazzetta e giustizia amministrativa quando la scelta sulla mappa li indica."""
    from .mappa import strumento
    from .scelta import scegli

    presenti = {f.__class__.__name__ for f in fonti}
    nuove = []
    for c in scegli(domanda):
        if c.nome not in STRUMENTI_DA_AGGIUNGERE:
            continue
        for nome in (strumento(c.nome) or {}).get("adattatori", []):
            if nome not in presenti:
                istanza = _istanza(nome)
                if istanza is not None:
                    nuove.append(istanza)
                    presenti.add(nome)
    return nuove


def fonti_guidate(request: Any, workflow: str, fonti: list[Any]) -> list[Any]:
    if not attiva() or workflow not in WORKFLOW_GUIDATI:
        return fonti
    try:
        aggiunte = _aggiunte(str(getattr(request, "query", "") or ""), fonti)
    except Exception:
        _log.exception("mappa degli strumenti: aggiunta degli archivi pubblici non riuscita")
        aggiunte = []
    if aggiunte:
        fonti = [*aggiunte, *fonti]
        metadata = getattr(request, "metadata", None)
        if isinstance(metadata, dict):
            metadata["archivi_aggiunti_dalla_mappa"] = [f.__class__.__name__ for f in aggiunte]
    if getattr(request, "fascicolo_id", None):
        return fonti
    try:
        ammessi = adattatori_ammessi(str(getattr(request, "query", "") or ""))
    except Exception:
        _log.exception("mappa degli strumenti: scelta non riuscita, fonti invariate")
        return fonti
    if not ammessi:
        return fonti
    tenute = [f for f in fonti if f.__class__.__name__ in ammessi | _RISERVA]
    presenti = {f.__class__.__name__ for f in tenute}
    for nome in sorted(ammessi - presenti):
        aggiunta = _istanza(nome)
        if aggiunta is None:
            return fonti  # adattatore non costruibile: percorso ordinario
        tenute.insert(0, aggiunta)
    metadata = getattr(request, "metadata", None)
    if isinstance(metadata, dict):
        metadata["fonti_guidate_dalla_mappa"] = sorted(f.__class__.__name__ for f in tenute)
    return tenute


__all__ = ["MOTIVI_CERTI", "adattatori_ammessi", "attiva", "fonti_guidate"]
