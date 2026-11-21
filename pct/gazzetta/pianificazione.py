"""Ingresso del lavoro pianificato «Gazzetta Ufficiale: sommari delle sei serie» (ogni ora, al minuto 25).

Quando non ci sono fascicoli nuovi il giro legge solo i sei elenchi «ultimi 30 giorni» e termina. Nel lavoro
pianificato (non dal pulsante «Aggiorna» della pagina) segue un tratto del recupero storico (``storico.py``):
sommari dal 01/01/2023 e testi completi degli atti, con pause gentili, ripartendo da dove si era fermato.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from pct.gazzetta.acquisizione import esegui_giro
from pct.gazzetta.archivio import ArchivioGazzetta

ID_LAVORO = "gazzetta_ufficiale_sommari"


def percorso_archivio(config: Mapping[str, Any]) -> Path:
    """Accanto agli archivi delle fonti ufficiali (`LEGAL_INTELLIGENCE_DB`), comune a tutti gli studi."""
    esplicito = str(config.get("GAZZETTA_UFFICIALE_DB") or "").strip()
    if esplicito:
        return Path(esplicito)
    ancora = str(config.get("LEGAL_INTELLIGENCE_DB") or "./intelligence/motori.json")
    return Path(ancora).resolve().parent / "gazzetta_ufficiale.sqlite"


def esegui_da_pianificazione(config: Mapping[str, Any], *, con_storico: bool = False, **opzioni: Any) -> dict[str, Any]:
    archivio = ArchivioGazzetta(percorso_archivio(config))
    esito = esegui_giro(archivio, **opzioni)
    if con_storico and str(config.get("GAZZETTA_RECUPERO_STORICO", "1")).lower() not in {"0", "false", "no", "off"}:
        from pct.gazzetta.storico import TEMPO_TRATTO, esegui_tratto

        try:
            esito["storico"] = esegui_tratto(archivio, tempo_massimo=float(config.get("GAZZETTA_TEMPO_STORICO") or TEMPO_TRATTO))
        except Exception as exc:  # il giro dei 30 giorni resta valido
            esito["storico"] = {"ok": False, "errore": str(exc)}
    return esito


__all__ = ["ID_LAVORO", "esegui_da_pianificazione", "percorso_archivio"]
