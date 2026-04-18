"""Sintesi di governo documentale per il fascicolo."""

from __future__ import annotations

from collections import Counter
from typing import Any


def normalize_document_tags(raw: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [chunk.strip() for chunk in raw.replace(";", ",").split(",")]
    else:
        parts = [str(chunk or "").strip() for chunk in raw]
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        key = part.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(part)
    return normalized


def build_document_management_summary(
    fascicolo: Any,
    *,
    indice: Any | None = None,
    query: str = "",
) -> dict[str, Any]:
    documenti = list(getattr(fascicolo, "documenti", []) or [])
    tags_counter: Counter[str] = Counter()
    latest_versions = 0
    signed = 0
    ocr_ready = 0
    portale = 0
    for doc in documenti:
        tags = normalize_document_tags(getattr(doc, "tags", []))
        for tag in tags:
            tags_counter[tag] += 1
        latest_versions += len(getattr(doc, "versioni", []) or [])
        if getattr(doc, "firmato_digitalmente", False):
            signed += 1
        if getattr(doc, "ocr_estratto", False):
            ocr_ready += 1
        if getattr(doc, "id_deposito_pct", ""):
            portale += 1

    search_results: list[dict[str, Any]] = []
    query_clean = str(query or "").strip()
    if indice is not None and query_clean:
        for result in indice.cerca(query_clean, tipi=["documento"], limit=12):
            meta = getattr(result, "meta", {}) or {}
            if meta.get("id_fasc") != fascicolo.id:
                continue
            id_doc = ""
            if ":" in result.id:
                _, id_doc = result.id.split(":", 1)
            doc = next((item for item in documenti if item.id == id_doc), None)
            search_results.append(
                {
                    "id_doc": id_doc,
                    "titolo": result.titolo,
                    "snippet": result.snippet,
                    "url": result.url,
                    "tipo": meta.get("tipo_doc", getattr(doc, "tipo", "")),
                    "tags": normalize_document_tags(getattr(doc, "tags", [])) if doc else [],
                }
            )

    next_action = "Carica il primo documento del fascicolo."
    if documenti:
        if any(not normalize_document_tags(getattr(doc, "tags", [])) for doc in documenti[:10]):
            next_action = "Completa i tag dei documenti principali per migliorare ricerca e filtro."
        elif any(not getattr(doc, "ocr_estratto", False) and doc.nome.lower().endswith(".pdf") for doc in documenti):
            next_action = "Completa l'indicizzazione OCR dei PDF piu' rilevanti."
        else:
            next_action = "Il dossier documentale e' ordinato: continua con versioni e review."

    recenti = sorted(documenti, key=lambda doc: getattr(doc, "data_caricamento", ""), reverse=True)[:8]
    with_versions = sorted(
        [doc for doc in documenti if getattr(doc, "versioni", [])],
        key=lambda doc: len(getattr(doc, "versioni", [])),
        reverse=True,
    )[:6]

    return {
        "query": query_clean,
        "stats": {
            "totale": len(documenti),
            "firmati": signed,
            "ocr_ready": ocr_ready,
            "taggati": sum(1 for doc in documenti if normalize_document_tags(getattr(doc, "tags", []))),
            "versioni": latest_versions,
            "dal_portale": portale,
        },
        "tag_cloud": [{"label": tag, "count": count} for tag, count in tags_counter.most_common(12)],
        "recenti": recenti,
        "with_versions": with_versions,
        "search_results": search_results,
        "next_action": next_action,
    }
