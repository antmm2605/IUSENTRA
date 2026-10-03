"""Retrieval normativa per Lex."""

from __future__ import annotations

import logging
import re
from typing import Any

from lex.schemas import LexSource
from web.helpers import get_legal_intelligence

try:
    from lex.retrieval.official_sources_retriever import (
        search_gazzetta as _search_gazzetta,
    )
    from lex.retrieval.official_sources_retriever import (
        search_normattiva as _search_normattiva,
    )
except Exception:  # pragma: no cover - modulo opzionale in ambienti ridotti
    _search_gazzetta = None
    _search_normattiva = None


logger = logging.getLogger(__name__)


def catalogo_fonti_ufficiali(message: str) -> list[dict[str, Any]]:
    """Righe di catalogo delle fonti ufficiali (dove cercare). NON sono evidenze giuridiche."""

    try:
        route = get_legal_intelligence().resolve_lex_legal_route(message)
    except Exception:
        return []
    return [dict(row) for row in list(route.get("source_rows") or [])[:4]]


def search_normativa_sources(message: str) -> list[LexSource]:
    """Evidenze normative: solo testo di norma dell'archivio Normattiva (e Gazzetta).

    Le righe di catalogo ("Area ...; motore ...; capacita ...") non sono evidenze:
    non dicono nulla sulla domanda e, con punteggio alto, scavalcavano le norme.
    """

    return _dedupe_sources(_official_archive_sources(message))


def _official_archive_sources(message: str) -> list[LexSource]:
    query = str(message or "").strip()
    if not query:
        return []
    sources: list[LexSource] = []
    if _search_normattiva is not None:
        try:
            # Si leggono 8 risultati e si tengono i primi 4 pertinenti: un risultato scartato
            # non deve far perdere l'articolo che lo segue in classifica.
            for row in _search_normattiva(query, limit=8):
                if not _riga_pertinente(query, row):
                    continue
                sources.append(_archive_row_to_source(row, source_type="normativa_normattiva", default_title="Normattiva"))
                if len(sources) >= 4:
                    break
        except Exception:
            pass
    if _search_gazzetta is not None:
        try:
            for row in _search_gazzetta(query, limit=2):
                # La Gazzetta non ha l'indice di pertinenza: si controllano i termini sul testo.
                if not _testo_pertinente(query, row):
                    continue
                sources.append(_archive_row_to_source(row, source_type="normativa_gazzetta", default_title="Gazzetta Ufficiale"))
        except Exception:
            pass
    return sources


def _riga_pertinente(query: str, row: dict[str, Any]) -> bool:
    """Scarta i risultati dell'indice che non coprono i termini della domanda."""

    if "pertinenza" not in row:  # ricerca precedente (LIKE in AND): ogni termine e' presente
        return True
    try:
        from lex.ricerca_giuridica.pertinenza import e_pertinente

        testo = " ".join(str(row.get(k) or "") for k in ("titolo", "testo", "excerpt"))
        return e_pertinente(query, testo, riferimento_esatto=bool(row.get("riferimento_esatto")))
    except Exception:
        return True


def _testo_pertinente(query: str, row: dict[str, Any]) -> bool:
    try:
        from lex.ricerca_giuridica.pertinenza import e_pertinente

        testo = " ".join(str(row.get(k) or "") for k in ("titolo", "testo", "excerpt", "summary"))
        return e_pertinente(query, testo)
    except Exception:
        return True


_SIGLE_URN = {
    "legge": "l.",
    "decreto.legge": "d.l.",
    "decreto.legislativo": "d.lgs.",
    "decreto.del.presidente.della.repubblica": "d.P.R.",
    "decreto.del.presidente.del.consiglio.dei.ministri": "d.P.C.M.",
    "regio.decreto": "r.d.",
    "decreto.ministeriale": "d.m.",
    "costituzione": "Cost.",
}
_LUNGHEZZA_TITOLO_FONTE = 70


def etichetta_fonte_normattiva(row: dict[str, Any]) -> str:
    """Nome breve dell'atto per l'intestazione della fonte mostrata al modello.

    «Codice civile» per i codici e la Costituzione; «l. 53/1994, Facolta' di notificazioni…» per gli altri atti
    (sigla dalla URN, numero/anno, inizio del titolo). Senza queste informazioni resta il titolo dell'archivio.
    """

    from lex.ricerca_giuridica.testo import CODICI_PER_CHIAVE, codice_da_atto

    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    titolo = str(row.get("titolo") or metadata.get("titolo") or "").strip()
    numero = str(metadata.get("numero") or "").strip()
    data = str(row.get("data") or metadata.get("data_atto") or "").strip()
    codice = codice_da_atto(numero, data[:10], titolo)
    if codice == "costituzione":
        return "Costituzione"
    if codice in CODICI_PER_CHIAVE:
        return CODICI_PER_CHIAVE[codice].etichetta
    urn = str(row.get("url_origine") or metadata.get("urn") or "")
    m = re.match(r"urn:nir:stato:([a-z.]+):(\d{4})-\d{2}-\d{2}(?:;(\d+))?", urn.strip().lower())
    breve = re.sub(r"\s*\(\d{2}[A-Z]\d{4,5}\)\.?$", "", titolo).strip()  # codice redazionale tra parentesi
    if len(breve) > _LUNGHEZZA_TITOLO_FONTE:
        breve = breve[:_LUNGHEZZA_TITOLO_FONTE].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    if m and m.group(3):
        sigla = _SIGLE_URN.get(m.group(1), m.group(1).replace(".", " "))
        riferimento = f"{sigla} {m.group(3)}/{m.group(2)}"
        return f"{riferimento}, {breve}" if breve else riferimento
    return breve or titolo


def _articolo_fonte(row: dict[str, Any]) -> str:
    """'Art. 3-bis.' / '3bis' -> 'art. 3-bis' per l'intestazione; vuoto se il chunk non e' un articolo."""

    from lex.ricerca_giuridica.testo import articolo_normalizzato

    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    grezzo = str(metadata.get("article_number") or row.get("articolo_o_chunk") or "")
    if not re.search(r"\d", grezzo) or grezzo == str(row.get("chunk_id") or ""):
        return ""
    normalizzato = articolo_normalizzato(grezzo)
    if not normalizzato:
        return ""
    return "art. " + re.sub(r"^(\d+)([a-z]+)$", r"\1-\2", normalizzato)


def _archive_row_to_source(row: dict[str, Any], *, source_type: str, default_title: str) -> LexSource:
    title = etichetta_fonte_normattiva(row) if source_type == "normativa_normattiva" else str(row.get("titolo") or default_title)
    title = title or str(row.get("titolo") or default_title)
    excerpt = str(row.get("testo") or row.get("excerpt") or "")[:1600]
    source_id = str(row.get("chunk_id") or row.get("document_id") or title)
    metadata: dict[str, Any] = {
        "official_url": row.get("url_origine") or row.get("url") or "",
        "authority": row.get("fonte") or default_title,
        "published_at": row.get("data") or "",
        "verified_reference": True,
        "archive_context": True,
        "titolo_archivio": row.get("titolo") or "",
    }
    articolo = _articolo_fonte(row) if source_type == "normativa_normattiva" else ""
    if articolo:
        metadata["articolo"] = articolo
    vigenza = str(row.get("vigenza") or "").strip().lower()
    if vigenza in {"vigente", "originale"}:
        metadata["vigenza"] = vigenza
    return LexSource(
        source_type=source_type,
        source_id=source_id,
        title=title,
        excerpt=excerpt,
        score=_score_riga(row, source_type),
        metadata=metadata,
    )


def _score_riga(row: dict[str, Any], source_type: str) -> float:
    """Punteggio guidato dalla pertinenza della ricerca (non da un valore fisso per tipo di fonte)."""

    if "pertinenza" in row:
        base = 0.45 + 0.5 * float(row.get("pertinenza") or 0.0)
        if row.get("riferimento_esatto"):
            base = max(base, 0.97)
        return round(min(0.99, base), 4)
    return 0.96 if source_type == "normativa_normattiva" else 0.9


def _dedupe_sources(rows: list[LexSource]) -> list[LexSource]:
    seen: set[str] = set()
    output: list[LexSource] = []
    for row in rows:
        key = f"{row.source_type}:{row.source_id}:{row.title}"
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output
