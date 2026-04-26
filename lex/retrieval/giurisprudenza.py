"""Retrieval giurisprudenziale per Lex."""

from __future__ import annotations

from lex.schemas import LexSource
from web.helpers import get_giurisprudenza


def _first_non_empty(*values) -> str:
    for value in values:
        if isinstance(value, (list, tuple, set)):
            clean = ", ".join(str(item).strip() for item in value if str(item).strip())
        else:
            clean = str(value or "").strip()
        if clean:
            return clean
    return ""


def search_giurisprudenza_sources(message: str) -> list[LexSource]:
    gestore = get_giurisprudenza()
    rows = []
    if hasattr(gestore, "resolve_lex_giurisprudenza_route"):
        try:
            rows = list((gestore.resolve_lex_giurisprudenza_route(message) or {}).get("corpus_rows") or [])
        except Exception:
            rows = []
    if not rows:
        rows = list(gestore.cerca_corpus_professionale(q=message, limit=4) or [])
    results: list[LexSource] = []
    for row in rows[:4]:
        official_url = _first_non_empty(row.get("official_url"), row.get("url_pagina_ufficiale"))
        metadata = {
            "verified_reference": bool(row.get("verified_reference")),
            "official_url": official_url,
            "url_pagina_ufficiale": _first_non_empty(row.get("url_pagina_ufficiale"), official_url),
            "url_pdf_ufficiale": _first_non_empty(row.get("url_pdf_ufficiale"), row.get("pdf_url")),
            "organo": _first_non_empty(row.get("organo"), row.get("court"), row.get("grado")),
            "court": _first_non_empty(row.get("court"), row.get("organo"), row.get("grado")),
            "sezione": _first_non_empty(row.get("sezione")),
            "numero": _first_non_empty(row.get("numero"), row.get("numero_sentenza")),
            "anno": _first_non_empty(row.get("anno")),
            "data_deposito": _first_non_empty(row.get("data_deposito"), row.get("published_at")),
            "data_decisione": _first_non_empty(row.get("data_decisione")),
            "norme_citate": row.get("norme_citate") or row.get("riferimenti_normativi") or [],
            "questione": _first_non_empty(row.get("questione"), row.get("questione_giuridica")),
            "dispositivo": _first_non_empty(row.get("dispositivo")),
            "principio": _first_non_empty(row.get("principio"), row.get("principio_sintetico")),
            "principio_sintetico": _first_non_empty(row.get("principio_sintetico"), row.get("principio")),
            "massima_ufficiale": _first_non_empty(row.get("massima_ufficiale")),
            "published_at": _first_non_empty(row.get("published_at"), row.get("data_deposito")),
        }
        excerpt = _first_non_empty(
            row.get("dispositivo"),
            row.get("principio_sintetico"),
            row.get("massima_ufficiale"),
            row.get("text"),
            row.get("sintesi"),
        )
        results.append(
            LexSource(
                source_type="giurisprudenza",
                source_id=str(row.get("id") or row.get("sentenza_id") or ""),
                title=str(row.get("titolo") or row.get("citation") or "Sentenza"),
                excerpt=excerpt,
                score=float(row.get("score") or 0.85),
                metadata=metadata,
            )
        )
    return results
