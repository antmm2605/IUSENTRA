"""Inoltro di norme, pronunce e prassi del notiziario agli archivi delle fonti del software.

Il canale è quello già esistente degli aggiornamenti legali: ogni notizia diventa
un documento acquisito (`source_documents_raw`) della fonte corrispondente,
con collegamento ufficiale, data e testo pubblicato dall'ente. Da lì prosegue
il percorso governato già in uso (analisi, verifica sul sito ufficiale,
revisione e pubblicazione): qui non si analizza e non si pubblica nulla.

L'identificativo esterno segue lo schema del lettore della pipeline
(`pct.legal_update_source_parsers._extract_feed_items`: sha256 di
«codice|url|titolo»), così il giro notturno della stessa fonte ritrova il
documento invece di duplicarlo.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from pct.notiziario.archivio import ArchivioNotiziario
from pct.notiziario.fonti import FONTI

logger = logging.getLogger(__name__)

STATO_ACQUISIZIONE = "notiziario"
_PER_FONTE = {fonte.id: fonte.codice_aggiornamenti for fonte in FONTI if fonte.codice_aggiornamenti}


def _identificativo_esterno(codice: str, url: str, titolo: str) -> str:
    return hashlib.sha256(f"{codice}|{url}|{titolo}".encode("utf-8")).hexdigest()


def _testo(notizia: dict[str, Any]) -> str:
    righe = [notizia.get("titolo") or "", notizia.get("sintesi") or "", notizia.get("riferimento_ufficiale") or ""]
    return "\n".join(riga for riga in righe if riga)


def inoltra_alla_revisione(archivio: ArchivioNotiziario, repository: Any, *, limite: int = 200) -> int:
    """Registra come documenti acquisiti le notizie non ancora inoltrate; restituisce quante."""
    fonti_censite: dict[str, dict[str, Any]] = {}
    for fonte_id, codice in _PER_FONTE.items():
        sorgente = repository.get_source_by_code(codice)
        if sorgente and sorgente.get("id"):
            fonti_censite[fonte_id] = sorgente
    inoltrate: list[str] = []
    for notizia in archivio.da_inoltrare(fonti_censite, limite=limite):
        sorgente = fonti_censite[notizia["fonte"]]
        esterno = _identificativo_esterno(str(sorgente.get("code") or ""), notizia["url"], notizia["titolo"])
        if repository.get_raw_document_by_external(int(sorgente["id"]), esterno) is None:
            repository.save_raw_document({
                "source_id": int(sorgente["id"]),
                "external_id": esterno,
                "source_url": notizia["url"],
                "title": notizia["titolo"],
                "published_at": notizia["data"],
                "raw_text": _testo(notizia),
                "fetch_status": STATO_ACQUISIZIONE,
                "http_status": 200,
            })
        inoltrate.append(notizia["id"])
    archivio.segna_inoltrate(inoltrate)
    if inoltrate:
        logger.info("[notiziario] %d documenti inoltrati alla revisione degli aggiornamenti legali", len(inoltrate))
    return len(inoltrate)


__all__ = ["STATO_ACQUISIZIONE", "inoltra_alla_revisione"]
