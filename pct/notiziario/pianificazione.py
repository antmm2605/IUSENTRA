"""Ingresso del lavoro pianificato «Notizie utili dalle fonti ufficiali».

Il lavoro gira ogni 30 minuti ma interroga solo le fonti scadute secondo la
loro frequenza (Gazzetta Ufficiale e Cassazione ogni 2 ore, PST ogni 3, CURIA
e Agenzia delle Entrate ogni 4, INPS, EUR-Lex, Garante, CNF e Corte
costituzionale ogni 6, Ministero, Cassa Forense e CEDU ogni 12): quando nessuna
fonte è scaduta termina subito senza traffico di rete.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from pct.notiziario.alimentazione import inoltra_alla_revisione
from pct.notiziario.archivio import ArchivioNotiziario
from pct.notiziario.giro import esegui_giro

ID_LAVORO = "notiziario_fonti_ufficiali"
INTERVALLO_MINUTI = 30


def percorso_archivio(config: Mapping[str, Any]) -> Path:
    """Accanto agli archivi delle fonti ufficiali (`LEGAL_INTELLIGENCE_DB`), comune a tutti gli studi."""
    esplicito = str(config.get("NOTIZIARIO_DB") or "").strip()
    if esplicito:
        return Path(esplicito)
    ancora = str(config.get("LEGAL_INTELLIGENCE_DB") or "./intelligence/motori.json")
    return Path(ancora).resolve().parent / "notiziario.sqlite"


def _inoltro(config: Mapping[str, Any]):
    def _esegui(archivio: ArchivioNotiziario) -> int:
        from pct.legal_update_pipeline import build_legal_update_pipeline

        pipeline = build_legal_update_pipeline(str(config.get("LEGAL_INTELLIGENCE_DB") or "./intelligence/motori.json"))
        return inoltra_alla_revisione(archivio, pipeline.repository)

    return _esegui


def esegui_da_pianificazione(config: Mapping[str, Any], *, forza: bool = False) -> dict[str, Any]:
    archivio = ArchivioNotiziario(percorso_archivio(config))
    return esegui_giro(archivio, forza=forza, inoltra=_inoltro(config))


__all__ = ["ID_LAVORO", "INTERVALLO_MINUTI", "esegui_da_pianificazione", "percorso_archivio"]
