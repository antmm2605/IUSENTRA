"""Riconvalida in sfondo delle definizioni automatiche, sul modello della causa della Lettura appena preparata.

Regola in `pct/definizione_riconvalida.py`. Qui solo il collegamento ai dati: la voce di avanzamento, il documento
che la voce cita (identificativo del catalogo «docai-…», nome del file o impronta SHA-256) e il cambio di stato con
la voce nello storico. Lo stato deciso dall'avvocato non si tocca: la regola considera solo le voci automatiche.
Nessuna lettura di file: il modello è quello già calcolato per la Lettura.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

logger = logging.getLogger(__name__)


def _testo(valore: Any) -> str:
    return " ".join(str(getattr(valore, "value", valore) or "").split())


def atti_citati(fascicolo: Any, voce: Any) -> list[str]:
    """Gli id dei documenti del fascicolo indicati dalla voce automatica (stessa impronta o stesso nome)."""
    from pct.definizione_riconvalida import fonte_citata

    citata = fonte_citata(_testo(getattr(voce, "note", "")))
    documenti = list(getattr(fascicolo, "documenti", []) or [])
    impronte = {citata["sha256"]} - {""}
    nomi = set()
    riferimento = citata["documento"]
    if riferimento.startswith("docai-"):
        try:
            from web.services.document_intelligence_runtime import build_document_ai_repository, document_ai_tenant_id

            record = build_document_ai_repository().get_document(document_ai_tenant_id(), _testo(fascicolo.id), riferimento)
        except Exception as exc:  # il catalogo non risponde: la riconvalida usa solo il resto del modello
            logger.debug("Documento %s non risolto per %s: %s", riferimento, getattr(fascicolo, "id", ""), exc)
            record = None
        if record is not None:
            impronte.add(_testo(record.sha256).lower())
            nomi.add(_testo(record.original_filename).casefold())
    elif riferimento:
        nomi.add(riferimento.casefold())
    impronte.discard("")
    nomi.discard("")
    return [_testo(d.id) for d in documenti
            if {_testo(getattr(d, "hash_sha256", "")).lower(), _testo(getattr(d, "hash_contenuto_sha256", "")).lower()} & impronte
            or {_testo(getattr(d, n, "")).casefold() for n in ("nome", "nome_originale", "nome_portale")} & nomi]


def modello_da_lettura(lettura: Mapping[str, Any]) -> dict[str, Any]:
    """Dalla sezione «ragionamento» della Lettura (pct/fascicolo_lettura/ragionamento.vista) i dati che la regola legge."""
    vista = lettura.get("ragionamento") or {}
    return {"impronta": vista.get("impronta"), "atti": vista.get("atti") or [], "udienze": vista.get("udienze_modello") or [],
            "oggi": vista.get("oggi") or ""}


def valuta_fascicolo(fascicolo: Any, modello: Mapping[str, Any]) -> dict[str, Any] | None:
    """Sola lettura: None se lo stato non è una definizione automatica; altrimenti l'esito della verifica."""
    from pct.definizione_riconvalida import definizione_automatica, verifica_definizione

    voce = definizione_automatica(getattr(fascicolo, "stato", ""), getattr(fascicolo, "avanzamento", []) or [])
    if voce is None or not modello or not modello.get("impronta"):
        return None
    citati = atti_citati(fascicolo, voce)
    verifica = verifica_definizione(modello, voce, citati)
    return {"voce": voce, "citati": citati, "verifica": verifica}


def riconvalida_definizione(fascicolo_id: str, lettura: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Riporta a «in corso» la definizione automatica che il modello della causa smentisce. Scrive solo in quel caso."""
    from pct.definizione_riconvalida import AUTORE, nota_riconvalida
    from pct.fascicoli import StatoFascicolo
    from web.helpers import get_fascicoli

    if not lettura or lettura.get("aggiornamento_pendente"):
        return None
    gestore = get_fascicoli()
    fascicolo = gestore.get(fascicolo_id)
    if fascicolo is None:
        return None
    esito = valuta_fascicolo(fascicolo, modello_da_lettura(lettura))
    if not esito or not esito["verifica"].revoca:
        return esito and {"revocata": False, "motivo": esito["verifica"].motivo}
    voce, verifica = esito["voce"], esito["verifica"]
    nota = nota_riconvalida(verifica, voce)
    chiusura = _testo(getattr(fascicolo, "data_chiusura", ""))
    if chiusura:
        nota += f" Data di definizione automatica {chiusura} rimossa."
    fascicolo.data_chiusura = ""
    try:
        gestore.cambia_stato(fascicolo_id, StatoFascicolo.IN_CORSO, note=nota, avvocato=AUTORE)
    except Exception:
        fascicolo.data_chiusura = chiusura
        raise
    logger.info("Definizione automatica annullata per %s: %s", fascicolo_id, verifica.motivo)
    return {"revocata": True, "motivo": verifica.motivo, "prova": verifica.prova}


__all__ = ["atti_citati", "modello_da_lettura", "riconvalida_definizione", "valuta_fascicolo"]
