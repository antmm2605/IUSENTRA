"""Materia della controversia e sospensione feriale dei termini nei preset dello scadenziario.

Base normativa: art. 3 L. 7 ottobre 1969, n. 742 (testo vigente, Normattiva, verificato l'08/11/2026): «In materia
civile, l'articolo 1 non si applica alle cause ed ai procedimenti indicati nell'articolo 92 dell'ordinamento
giudiziario 30 gennaio 1941, n. 12, nonché alle controversie previste dagli articoli 429 e 459 del codice di
procedura civile» (controversie di lavoro e di previdenza, oggi artt. 409 e 442 c.p.c.).
https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1969-10-07;742~art3

Il motore spiegabile applica la stessa regola in ``ItalianDeadlineCalculator._apply_matter_rules``; qui la si
applica ai profili della pagina «Nuova scadenza» (appello breve e lungo, cassazione, ecc.), che prima contavano
sempre la sospensione di agosto. Esempio reale: RG 3001/2025 (lavoro), sentenza depositata il 01/07/2026, termine
lungo 01/01/2027 festivo -> 02/01 sabato -> 04/01/2027, non 01/02/2027.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from pct.pec_provvedimento_terms import is_labour_matter

logger = logging.getLogger(__name__)

NOTA_LAVORO = "Sospensione feriale non applicata: controversia di lavoro o previdenza (art. 3 L. 742/1969)."


def _testo(valore: Any) -> str:
    return str(getattr(valore, "value", valore) or "")


def fascicolo_di_lavoro(fascicolo: Any) -> bool:
    """Vero per i fascicoli di lavoro o previdenza: tipo LAVORO o sezione lavoro/previdenza.

    L'oggetto della causa non si usa: «infortunio sul lavoro» può essere una causa civile di risarcimento.
    """
    if fascicolo is None:
        return False
    if _testo(getattr(fascicolo, "tipo", "")).upper() == "LAVORO":
        return True
    return is_labour_matter(getattr(fascicolo, "sezione", ""), getattr(fascicolo, "ruolo_sezione", ""))


def lavoro_da_richiesta(payload: Mapping[str, Any], carica_fascicolo: Callable[[str], Any]) -> bool:
    """Materia di lavoro dalla richiesta: ``materia_lavoro`` esplicito, altrimenti dal fascicolo ``id_fascicolo``."""
    if "materia_lavoro" in payload:
        return str(payload.get("materia_lavoro") or "").strip().lower() in {"1", "true", "on", "yes", "si", "sì"}
    id_fascicolo = str(payload.get("id_fascicolo") or "").strip()
    if not id_fascicolo:
        return False
    try:
        return fascicolo_di_lavoro(carica_fascicolo(id_fascicolo))
    except Exception:  # fascicolo non leggibile: resta la regola generale, con il log per la verifica
        logger.exception("Materia del fascicolo %s non leggibile per la sospensione feriale", id_fascicolo)
        return False


def profilo_per_materia(profilo: Any, *, lavoro: bool) -> Any:
    """Toglie la sospensione feriale al profilo se la controversia è di lavoro o previdenza."""
    if lavoro and getattr(profilo, "apply_ferial_suspension", False):
        return replace(profilo, apply_ferial_suspension=False)
    return profilo


__all__ = ["NOTA_LAVORO", "fascicolo_di_lavoro", "lavoro_da_richiesta", "profilo_per_materia"]
