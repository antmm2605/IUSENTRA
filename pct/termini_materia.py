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


def esclusione_feriale_fascicolo(fascicolo: Any) -> str:
    """Perché nel fascicolo la sospensione feriale non si applica, con la norma; vuoto se si applica.

    Una sola regola nel software: `pct/ragionamento/feriale.esclusione_feriale` (art. 3 L. 742/1969 e art. 92
    R.D. 12/1941), applicata al codice oggetto PST del fascicolo; il lavoro si riconosce anche da tipo e sezione.
    """
    from pct.ragionamento.feriale import esclusione_feriale
    from pct.ragionamento.rito import rito_da_codice

    if fascicolo is None:
        return ""
    if fascicolo_di_lavoro(fascicolo):
        return esclusione_feriale("lavoro", {})
    codice = _testo(getattr(fascicolo, "codice_oggetto_pst", "")).strip()
    rito, voce = rito_da_codice(codice) if codice else ("", {})
    return esclusione_feriale(rito, voce) if voce else ""


def esclusione_da_richiesta(payload: Mapping[str, Any], carica_fascicolo: Callable[[str], Any]) -> str:
    """Il motivo dell'esclusione dalla sospensione feriale per la richiesta: ``materia_lavoro`` esplicito o fascicolo."""
    from pct.ragionamento.feriale import esclusione_feriale

    if "materia_lavoro" in payload and lavoro_da_richiesta(payload, carica_fascicolo):
        return esclusione_feriale("lavoro", {})
    id_fascicolo = str(payload.get("id_fascicolo") or "").strip()
    if not id_fascicolo:
        return ""
    try:
        motivo = esclusione_feriale_fascicolo(carica_fascicolo(id_fascicolo))
        # «materia_lavoro» esplicito e falso: l'avvocato ha detto che non è lavoro; restano le altre materie escluse.
        return "" if "materia_lavoro" in payload and motivo.startswith("controversia di lavoro") else motivo
    except Exception:  # fascicolo non leggibile: resta la regola generale, con il log per la verifica
        logger.exception("Materia del fascicolo %s non leggibile per la sospensione feriale", id_fascicolo)
        return ""


def nota_esclusione(motivo: str) -> str:
    """La nota del calcolo: per il lavoro quella storica, per le altre materie il motivo con la norma."""
    if not motivo or motivo.startswith("controversia di lavoro"):
        return NOTA_LAVORO
    return f"Sospensione feriale non applicata: {motivo}."


def profilo_per_materia(profilo: Any, *, lavoro: bool) -> Any:
    """Toglie la sospensione feriale al profilo se la controversia è di lavoro o previdenza."""
    if lavoro and getattr(profilo, "apply_ferial_suspension", False):
        return replace(profilo, apply_ferial_suspension=False)
    return profilo


__all__ = ["NOTA_LAVORO", "esclusione_da_richiesta", "esclusione_feriale_fascicolo", "fascicolo_di_lavoro", "lavoro_da_richiesta",
           "nota_esclusione", "profilo_per_materia"]


def profilo_della_richiesta(preset_key: str, profile_code: str, payload: Mapping[str, Any],
                            trova_fascicolo: Callable[[str], Any]) -> tuple[Any, bool, bool]:
    """Profilo del termine scelto (preset o profilo) adattato alla materia della richiesta.

    Restituisce (profilo, materia di lavoro, motivo della sospensione feriale tolta o «»). Art. 3 L. 742/1969 e
    art. 92 R.D. 12/1941: nessuna sospensione feriale nel lavoro e previdenza e nelle altre materie escluse.
    """
    from pct.scadenziario import ProfiloTermine, profili_termine_builtin, profilo_da_preset

    if preset_key:
        profilo = profilo_da_preset(preset_key)
    elif profile_code:
        profili = profili_termine_builtin()
        if profile_code not in profili:
            raise ValueError("Profilo termine non valido")
        profilo = ProfiloTermine.from_dict(profili[profile_code])
    else:
        raise ValueError("Seleziona un preset o un profilo termine")
    escluso = esclusione_da_richiesta(payload, trova_fascicolo)
    adattato = profilo_per_materia(profilo, lavoro=bool(escluso))
    # Il terzo valore è il motivo dell'esclusione (vuoto se la sospensione resta): la nota del calcolo lo riporta.
    return adattato, escluso.startswith("controversia di lavoro"), escluso if adattato is not profilo else ""
