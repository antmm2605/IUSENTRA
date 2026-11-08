"""Le norme citate negli atti del fascicolo, per collegare le Notizie utili ai fascicoli.

Il lettore «norme_citate» del registro delle letture lavora in sfondo sui testi
già salvati (indice documentale e OCR), mai riaprendo i file e mai durante una
richiesta: per ogni documento registra gli atti citati per estremi (chiave
«tipo:numero:anno» e articolo/comma citati), e per il fascicolo un riepilogo
che la pagina «Notizie utili» legge in una sola interrogazione.

Base: art. 3 D.M. 44/2011 e art. 20 CAD per l'impronta dei documenti letti
(il registro rilegge solo ciò che è nuovo o cambiato).
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from pct.notiziario.classifica import citazioni_atti

LETTORE = "norme_citate"
VERSIONE = "norme-citate.v1"
MASSIMO_PER_DOCUMENTO = 60
MASSIMO_PER_FASCICOLO = 80


def esito_documento(testo: str) -> dict[str, Any]:
    """Esito di lettura di un documento: gli atti citati con l'eventuale articolo."""
    return {
        "atti": [
            {"chiave": chiave, "articolo": articolo}
            for chiave, articolo in citazioni_atti(testo, massimo=MASSIMO_PER_DOCUMENTO)
        ]
    }


def riepilogo_fascicolo(letture: Iterable[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Da (nome del documento, esito) al riepilogo del fascicolo: per atto, l'articolo più citato e il primo documento.

    Ordine: prima gli atti citati in più documenti.
    """
    per_atto: dict[str, dict[str, Any]] = {}
    for nome, esito in letture:
        for voce in (esito or {}).get("atti") or []:
            chiave = str(voce.get("chiave") or "")
            if not chiave:
                continue
            riga = per_atto.setdefault(chiave, {"chiave": chiave, "articoli": {}, "documento": nome, "documenti": 0})
            riga["documenti"] += 1
            articolo = str(voce.get("articolo") or "")
            if articolo:
                riga["articoli"][articolo] = riga["articoli"].get(articolo, 0) + 1
    ordinati = sorted(per_atto.values(), key=lambda riga: (-riga["documenti"], riga["chiave"]))
    return {
        "atti": [
            {
                "chiave": riga["chiave"],
                "articolo": max(riga["articoli"].items(), key=lambda voce: (voce[1], voce[0]))[0] if riga["articoli"] else "",
                "documento": riga["documento"],
                "documenti": riga["documenti"],
            }
            for riga in ordinati[:MASSIMO_PER_FASCICOLO]
        ]
    }


def atti_dai_riepiloghi(righe: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Righe `letture_fascicoli` del lettore → {fascicolo: [atti]} (una sola lettura per lo studio)."""
    risultato: dict[str, list[dict[str, Any]]] = {}
    for riga in righe:
        try:
            esito = json.loads(riga.get("esito_json") or "{}") if isinstance(riga.get("esito_json"), str) else dict(riga.get("esito_json") or {})
        except (TypeError, ValueError):
            continue
        atti = [voce for voce in esito.get("atti") or [] if isinstance(voce, dict) and voce.get("chiave")]
        if atti:
            risultato[str(riga.get("fascicolo_id") or "")] = atti
    return risultato


__all__ = ["LETTORE", "VERSIONE", "atti_dai_riepiloghi", "esito_documento", "riepilogo_fascicolo"]
