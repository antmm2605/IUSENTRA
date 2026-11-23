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


TEMPO_STORICO_MASSIMO = 3300.0  # il giro orario (cron al minuto 25, una istanza) non si somma al successivo


def tempo_storico(config: Mapping[str, Any]) -> float:
    """Secondi del recupero storico in ogni giro orario: ``GAZZETTA_TEMPO_STORICO`` nella configurazione oppure
    ``PCT_GAZZETTA_TEMPO_STORICO`` / ``GAZZETTA_TEMPO_STORICO`` nell'ambiente; 1200 di base, fra 30 e 3300."""
    import os

    from pct.gazzetta.storico import TEMPO_TRATTO

    valore = str(config.get("GAZZETTA_TEMPO_STORICO") or os.environ.get("PCT_GAZZETTA_TEMPO_STORICO")
                 or os.environ.get("GAZZETTA_TEMPO_STORICO") or "").strip()
    try:
        secondi = float(valore) if valore else float(TEMPO_TRATTO)
    except ValueError:
        secondi = float(TEMPO_TRATTO)
    return max(30.0, min(TEMPO_STORICO_MASSIMO, secondi))


def esegui_da_pianificazione(config: Mapping[str, Any], *, con_storico: bool = False, **opzioni: Any) -> dict[str, Any]:
    archivio = ArchivioGazzetta(percorso_archivio(config))
    esito = esegui_giro(archivio, **opzioni)
    if con_storico and str(config.get("GAZZETTA_RECUPERO_STORICO", "1")).lower() not in {"0", "false", "no", "off"}:
        from pct.gazzetta.storico import esegui_tratto

        # Prima gli atti normativi già nella biblioteca Normattiva: non si riscaricano dal sito.
        import os

        normattiva = str(config.get("GAZZETTA_NORMATTIVA_DB") or os.environ.get("GAZZETTA_NORMATTIVA_DB")
                         or os.environ.get("PCT_NORMATTIVA_DB") or "")
        if normattiva and Path(normattiva).is_file():
            from pct.gazzetta.da_normattiva import collega

            try:
                esito["da_normattiva"] = collega(archivio, normattiva)
            except Exception as exc:  # la biblioteca non risponde: il recupero dal sito resta
                esito["da_normattiva"] = {"errore": str(exc)}

        try:
            esito["storico"] = esegui_tratto(archivio, tempo_massimo=tempo_storico(config))
        except Exception as exc:  # il giro dei 30 giorni resta valido
            esito["storico"] = {"ok": False, "errore": str(exc)}
    return esito


__all__ = ["ID_LAVORO", "esegui_da_pianificazione", "percorso_archivio", "tempo_storico"]
