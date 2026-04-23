"""Retrieval fascicoli per Lex."""

from __future__ import annotations

from typing import Any

from lex.schemas import LexSource
from web.helpers import get_fascicoli

_SECTION_LABELS = {
    "attivita_processuali": "Attivita' processuali",
    "documenti_fascicolo": "Documenti fascicolo",
    "udienze_scadenze": "Udienze e scadenze",
    "comunicazioni_cancelleria": "Comunicazioni di cancelleria",
    "istanze": "Istanze",
}
_SECTION_COUNT_KEYS = {
    "attivita_processuali": "attivita",
    "documenti_fascicolo": "documenti",
    "udienze_scadenze": "udienze_scadenze",
    "comunicazioni_cancelleria": "comunicazioni",
    "istanze": "istanze",
}
_SECTION_HINTS = {
    "attivita_processuali": ("attivit", "deposit", "fase", "proced", "stato"),
    "documenti_fascicolo": ("document", "atto", "allegat", "provved", "sentenz", "ordinanz"),
    "udienze_scadenze": ("udienz", "scadenz", "termine", "rinvio", "agenda"),
    "comunicazioni_cancelleria": ("comunicaz", "canceller", "pec", "notific"),
    "istanze": ("istanz", "richiest", "domand"),
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _structured_context(context: dict[str, Any]) -> dict[str, Any]:
    payload = dict(context or {})
    structured = payload.get("structured_context")
    return dict(structured or {}) if isinstance(structured, dict) else payload


def _row_title(row: dict[str, Any]) -> str:
    return _clean(
        row.get("titolo")
        or row.get("nome")
        or row.get("tipo_atto")
        or row.get("tipo")
        or row.get("id")
    )


def _row_excerpt(row: dict[str, Any]) -> str:
    parts = [
        _clean(row.get("titolo") or row.get("nome") or row.get("tipo_atto") or row.get("tipo")),
        _clean(row.get("descrizione") or row.get("note") or row.get("messaggio")),
    ]
    when = _clean(
        row.get("data_ora")
        or row.get("timestamp")
        or row.get("data")
        or row.get("data_documento")
        or row.get("data_caricamento")
    )
    if when:
        parts.append(f"data {when}")
    source = _clean(row.get("fonte"))
    if source:
        parts.append(f"fonte {source}")
    return ". ".join(part for part in parts if part)


def _query_matches_section(section_key: str, query: str) -> bool:
    if not query:
        return False
    return any(token in query for token in _SECTION_HINTS.get(section_key, ()))


def _section_summary_source(
    *,
    pratica_id: str,
    section_key: str,
    items: list[dict[str, Any]],
    count: int,
    query: str,
) -> LexSource | None:
    if count <= 0:
        return None
    title = _SECTION_LABELS.get(section_key, section_key.replace("_", " ").title())
    excerpt = f"{title}: {count} elementi censiti nel fascicolo."
    preview = next((_row_excerpt(row) for row in items if _row_excerpt(row)), "")
    if preview:
        excerpt += f" Ultimo elemento utile: {preview}."
    score = 0.62
    if _query_matches_section(section_key, query):
        score = 0.86
    return LexSource(
        source_type="sezione_fascicolo",
        source_id=f"{pratica_id}:{section_key}",
        title=title,
        excerpt=excerpt,
        score=score,
        metadata={"section": section_key, "count": count},
    )


def _section_item_sources(
    *,
    section_key: str,
    items: list[dict[str, Any]],
    query: str,
) -> list[LexSource]:
    results: list[LexSource] = []
    wanted = []
    if query:
        for row in items:
            haystack = f"{_row_title(row)} {_row_excerpt(row)}".lower()
            if query in haystack:
                wanted.append(row)
    if not wanted:
        wanted = list(items[:1]) if items else []
    for row in wanted[:3]:
        title = _row_title(row)
        excerpt = _row_excerpt(row)
        if not title and not excerpt:
            continue
        results.append(
            LexSource(
                source_type=f"fascicolo_{section_key}",
                source_id=str(row.get("id") or f"{section_key}:{len(results) + 1}"),
                title=title or _SECTION_LABELS.get(section_key, "Voce fascicolo"),
                excerpt=excerpt or _SECTION_LABELS.get(section_key, "Voce fascicolo"),
                score=0.78 if query else 0.58,
                metadata={"section": section_key, "fonte": row.get("fonte") or ""},
            )
        )
    return results


def search_fascicolo_sources(pratica_id: str, message: str, context: dict[str, Any]) -> list[LexSource]:
    rows: list[LexSource] = []
    query = _clean(message).lower()
    structured = _structured_context(context)
    fascicolo_sections = dict(structured.get("fascicolo_sezioni") or {})

    if pratica_id:
        fascicolo = get_fascicoli().get(pratica_id)
        if fascicolo:
            excerpt = (
                f"Fascicolo {fascicolo.numero}: {fascicolo.titolo}. "
                f"Cliente {fascicolo.nome_cliente}. Oggetto {fascicolo.oggetto or 'n.d.'}."
            )
            rows.append(
                LexSource(
                    source_type="fascicolo",
                    source_id=fascicolo.id,
                    title=fascicolo.titolo or fascicolo.numero,
                    excerpt=excerpt,
                    score=1.0,
                    metadata={"numero": fascicolo.numero, "cliente": fascicolo.nome_cliente},
                )
            )

    counts = dict(fascicolo_sections.get("counts") or {})
    for section_key, title in _SECTION_LABELS.items():
        items = list(
            fascicolo_sections.get(section_key)
            or (structured.get("documenti") if section_key == "documenti_fascicolo" else [])
            or []
        )
        count = int(counts.get(_SECTION_COUNT_KEYS.get(section_key, ""), len(items)) or 0)
        summary = _section_summary_source(
            pratica_id=pratica_id,
            section_key=section_key,
            items=items,
            count=count,
            query=query,
        )
        if summary is not None:
            rows.append(summary)
        rows.extend(_section_item_sources(section_key=section_key, items=items, query=query))

    if not fascicolo_sections:
        for row in list(structured.get("documenti") or [])[:3]:
            rows.append(
                LexSource(
                    source_type="documento_fascicolo",
                    source_id=str(row.get("id") or ""),
                    title=str(row.get("nome") or "Documento"),
                    excerpt=f"Documento {row.get('nome') or 'n.d.'} di tipo {row.get('tipo') or 'n.d.'}.",
                    score=0.55,
                    metadata={"tipo": row.get("tipo") or ""},
                )
            )
    return rows
