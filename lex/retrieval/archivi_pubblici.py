"""Lettura in sola lettura degli archivi pubblici che il software acquisisce e che Lex ora interroga.

- Prassi dell'Agenzia delle Entrate e dell'INPS (``pct.prassi``, ``prassi.sqlite``): circolari, risoluzioni, messaggi;
- Gazzetta Ufficiale (``pct.gazzetta``, ``gazzetta_ufficiale.sqlite``): sommari delle sei serie e testi degli atti;
- testi della giustizia amministrativa (``pct.giustizia_amministrativa_testi``, ``ga_testi.sqlite``): TAR, Consiglio di
  Stato e CGARS, per estremi (anno e numero) o per parole.

Ogni archivio si apre in sola lettura e solo se il file esiste: un archivio assente restituisce un elenco vuoto, mai
un file creato dalla ricerca. I percorsi sono quelli dei lavori che alimentano gli archivi (``pct.fonti_in_sfondo``,
``pct.gazzetta.pianificazione``). Fonti: art. 73 Cost. e D.P.R. 1092/1985 (Gazzetta); documenti di prassi pubblicati
sui siti dell'Agenzia delle Entrate e dell'INPS; sentenze pubblicate su giustizia-amministrativa.it.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


def _config() -> Mapping[str, Any]:
    try:
        from flask import current_app

        return current_app.config
    except Exception:  # fuori dall'applicazione: solo variabili d'ambiente
        return {}


def percorso_prassi(config: Mapping[str, Any] | None = None) -> Path:
    from pct.fonti_in_sfondo import percorso_prassi as p

    return p(_config() if config is None else config)


def percorso_gazzetta(config: Mapping[str, Any] | None = None) -> Path:
    import os

    from pct.gazzetta.pianificazione import percorso_archivio

    config = dict(_config() if config is None else config)
    config.setdefault("GAZZETTA_UFFICIALE_DB", os.environ.get("GAZZETTA_UFFICIALE_DB", ""))
    config.setdefault("LEGAL_INTELLIGENCE_DB", os.environ.get("PCT_LEGAL_INTELLIGENCE_DB", "./intelligence/motori.json"))
    return percorso_archivio(config)


def percorso_testi_ga(config: Mapping[str, Any] | None = None) -> Path:
    from pct.fonti_in_sfondo import percorso_ga

    return percorso_ga(_config() if config is None else config)


def cerca_prassi(domanda: str, *, ente: str = "", limite: int = 8, percorso: Path | None = None) -> list[dict[str, Any]]:
    """Circolari e risoluzioni pertinenti; ``ente`` è «agenzia_entrate», «inps» o vuoto."""
    from pct.prassi.archivio import ArchivioPrassi

    file = percorso or percorso_prassi()
    if not Path(file).is_file():
        return []
    ente_archivio = {"agenzia_entrate": "Agenzia delle Entrate", "inps": "INPS", "tutti": ""}.get(ente, ente)
    return ArchivioPrassi(file, sola_lettura=True).cerca(domanda, ente=ente_archivio, limite=limite)


def cerca_gazzetta(domanda: str, *, serie: tuple[str, ...] = (), dal: str = "", al: str = "", limite: int = 8,
                   percorso: Path | None = None) -> list[dict[str, Any]]:
    """Atti della Gazzetta Ufficiale per parole (titolo, ente, testo), dal più pertinente; date ISO."""
    from pct.gazzetta.archivio import ArchivioGazzetta, Filtri

    archivio = ArchivioGazzetta.in_lettura(percorso or percorso_gazzetta())
    if archivio is None:
        return []
    filtri = Filtri(q=domanda, serie=tuple(serie), dal=dal, al=al, ordine="pertinenza", per_pagina=limite)
    return list(archivio.cerca(filtri).get("atti") or [])


_ESTREMI = re.compile(r"\bn\.?\s*(\d{1,6})\s*(?:/\s*((?:19|20)\d{2})|del\s+(?:\d{1,2}[./-]\d{1,2}[./-])?((?:19|20)\d{2}))")


def cerca_testi_ga(domanda: str, *, limite: int = 8, percorso: Path | None = None) -> list[dict[str, Any]]:
    """Provvedimenti amministrativi: per estremi («n. 1234/2021») se la domanda li cita, altrimenti per parole."""
    from pct.giustizia_amministrativa_testi import ArchivioTestiGA

    file = percorso or percorso_testi_ga()
    if not Path(file).is_file():
        return []
    archivio = ArchivioTestiGA(file, sola_lettura=True)
    m = _ESTREMI.search(str(domanda or "").lower())
    if m:
        anno = int(m.group(2) or m.group(3))
        uscita = []
        for ident in archivio.trova(anno, m.group(1))[:limite]:
            voce = archivio.provvedimento(ident)
            if voce and voce.get("testo"):
                voce["brano"] = " ".join(voce.pop("testo").split())[:600]
                uscita.append(voce)
        return uscita
    return archivio.cerca(domanda, limite=limite)


__all__ = ["cerca_gazzetta", "cerca_prassi", "cerca_testi_ga", "percorso_gazzetta", "percorso_prassi", "percorso_testi_ga"]
