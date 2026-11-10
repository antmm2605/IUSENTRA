"""Ingresso del lavoro pianificato «Gazzetta Ufficiale: sommari delle sei serie» (ogni ora, al minuto 25).

Quando non ci sono fascicoli nuovi il giro legge solo i sei elenchi «ultimi 30 giorni» e termina.
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


def esegui_da_pianificazione(config: Mapping[str, Any], **opzioni: Any) -> dict[str, Any]:
    return esegui_giro(ArchivioGazzetta(percorso_archivio(config)), **opzioni)


__all__ = ["ID_LAVORO", "esegui_da_pianificazione", "percorso_archivio"]
