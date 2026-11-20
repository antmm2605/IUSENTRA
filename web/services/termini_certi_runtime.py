"""Conferma in sfondo le proposte di scadenza che il modello della causa rende certe (pct/fascicolo_lettura/termini_certi).

Si esegue alla fine della preparazione della Lettura in sfondo, mai nella richiesta dell'avvocato. Tocca solo le bozze
automatiche intatte (marcatore ``PEC_TERMINE_PROPOSTO`` o obbligo di notifica letto dal documento), mai quelle scritte
o modificate dall'avvocato: la conferma (BOZZA → APERTO) porta nella nota la prova, cioè il provvedimento del giudice
letto dal modello e la scadenza calcolata. Un errore non ferma la Lettura.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)
_AUTOMATICHE = ("PEC_TERMINE_PROPOSTO:", "Obbligo di notifica letto dal documento")


def conferma_termini_certi(fascicolo_id: str, lettura: dict[str, Any]) -> int:
    try:
        from pct.fascicolo_lettura.termini_certi import bozze_certe
        from pct.scadenziario import StatoTermine
        from web.helpers import get_scadenziario

        scadenziario = get_scadenziario()
        bozze = [s for s in scadenziario.tutte(id_fascicolo=str(fascicolo_id), solo_aperte=False)
                 if s.stato == StatoTermine.BOZZA and any(m in (s.note or "") for m in _AUTOMATICHE)
                 and not str(getattr(s, "id_utente_responsabile", "") or "").strip()]
        if not bozze:
            return 0
        righe = [{"id": s.id, "titolo": s.titolo, "note": s.note, "stato": "BOZZA", "data": str(s.data_scadenza or "")[:10]}
                 for s in bozze]
        certe = bozze_certe(righe, ((lettura or {}).get("ragionamento") or {}).get("conclusioni"))
        from pct.fascicolo_lettura.termini_certi import codice_della_bozza

        from pct.fascicolo_lettura.prossimi_passi import _codice_scadenza

        confermate = 0
        gia: dict[tuple[str, str], str] = {}
        for aperta in scadenziario.tutte(id_fascicolo=str(fascicolo_id), solo_aperte=False):
            if aperta.stato == StatoTermine.APERTO:
                dati = {"titolo": aperta.titolo, "note": aperta.note}
                codice = _codice_scadenza(dati) or codice_della_bozza(dati)
                if codice:
                    gia.setdefault((codice, str(aperta.data_scadenza or "")[:10]), aperta.titolo)
        for scadenza in sorted(bozze, key=lambda s: ("PEC_TERMINE_PROPOSTO:" not in (s.note or ""), s.id)):
            prova = certe.get(scadenza.id)
            if not prova:
                continue
            chiave = (codice_della_bozza({"titolo": scadenza.titolo, "note": scadenza.note}), str(scadenza.data_scadenza or "")[:10])
            if chiave in gia:
                # La stessa scadenza proposta due volte (PEC e obbligo di notifica): resta un solo termine.
                scadenziario.scarta_bozza(scadenza.id, motivo=f"doppione del termine confermato «{gia[chiave]}»",
                                          attore="modello della causa")
                continue
            scadenziario.conferma_bozza(scadenza.id, attore=f"modello della causa ({prova})")
            gia[chiave] = scadenza.titolo
            confermate += 1
        return confermate
    except Exception as exc:  # la conferma automatica non deve fermare la Lettura
        logger.warning("Termini certi non confermati per %s: %s", fascicolo_id, exc)
        return 0


def chiudi_adempimenti_provati(fascicolo_id: str, lettura: dict[str, Any]) -> list[str]:
    """Completa le scadenze automatiche di un adempimento che il modello conclude «fatto» con la prova (anche la
    costituzione della controparte, art. 156, terzo comma, c.p.c.), con il motivo e il documento nella nota.
    Mai le scadenze scritte o assegnate dall'avvocato. Un errore non ferma la Lettura."""
    try:
        from pct.fascicolo_lettura.termini_certi import adempimenti_provati
        from pct.scadenziario import StatoTermine
        from web.helpers import get_scadenziario

        if (lettura or {}).get("aggiornamento_pendente"):
            return []
        scadenziario = get_scadenziario()
        candidate = [s for s in scadenziario.tutte(id_fascicolo=str(fascicolo_id), solo_aperte=False)
                     if s.stato in {StatoTermine.BOZZA, StatoTermine.APERTO} and any(m in (s.note or "") for m in _AUTOMATICHE)
                     and not str(getattr(s, "id_utente_responsabile", "") or "").strip()]
        if not candidate:
            return []
        righe = [{"id": s.id, "titolo": s.titolo, "note": s.note, "stato": str(getattr(s.stato, "value", s.stato))} for s in candidate]
        chiuse = adempimenti_provati(righe, ((lettura or {}).get("ragionamento") or {}).get("conclusioni"))
        completate = []
        for scadenza in candidate:
            nota = chiuse.get(scadenza.id)
            if nota:
                scadenziario.completa(scadenza.id, note=nota)
                completate.append(scadenza.id)
        return completate
    except Exception as exc:  # la chiusura automatica non deve fermare la Lettura
        logger.warning("Adempimenti provati non chiusi per %s: %s", fascicolo_id, exc)
        return []


__all__ = ["chiudi_adempimenti_provati", "conferma_termini_certi"]
