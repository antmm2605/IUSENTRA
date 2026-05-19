"""Sorgente Lex per i dati operativi interni indicizzati da Ricerca Studio.

La sorgente legge solo l'indice interno tenant-aware della Ricerca Studio e
scarta le fonti legali gia' presidiate dagli adapter dedicati.
"""

from __future__ import annotations

from typing import Any

from lex.contracts import EvidenceItem


_EXCLUDED_ENTITY_TYPES = {
    "fonte",
    "fonti",
    "legal_intelligence",
    "legal_updates",
    "normativa",
    "giurisprudenza",
    "prassi",
    "web_ufficiale",
    "official_web",
}

_ALLOWED_ENTITY_TYPES = {
    "fascicolo",
    "cliente",
    "soggetto",
    "scadenza",
    "appuntamento",
    "udienza",
    "attivita",
    "documento",
    "documento_fascicolo",
    "documento_indicizzato",
    "documento_chunk",
    "comunicazione",
    "pec",
    "email",
    "deposito",
    "preventivo",
    "conferimento",
    "fattura",
    "pagamento",
    "template_atto",
}

_PRIORITY_TYPES = {
    "pec",
    "comunicazione",
    "email",
    "documento",
    "documento_indicizzato",
    "documento_chunk",
    "scadenza",
    "appuntamento",
    "udienza",
    "fascicolo",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _lower(value: Any) -> str:
    return _clean(value).lower()


def _flag(value: Any) -> bool:
    return value is True or _lower(value) in {"1", "true", "vero", "yes", "si", "on", "enabled"}


def _tenant_id(context: dict[str, Any], request: Any) -> str:
    tenant = _clean((context or {}).get("tenant_id") or getattr(request, "tenant_id", ""))
    if tenant:
        return tenant
    try:
        from flask import g, has_request_context

        if has_request_context():
            current = g.get("tenant")
            return _clean(getattr(current, "id", "") or getattr(current, "slug", "")) or "default"
    except Exception:
        return "default"
    return "default"


def _search_context(context: dict[str, Any], request: Any) -> dict[str, Any]:
    ctx = dict(context or {})
    ctx["tenant_id"] = _tenant_id(ctx, request)
    if not _clean(ctx.get("search_index_path")) and not _clean(ctx.get("global_search_db_path")):
        try:
            from flask import current_app, has_request_context

            if has_request_context():
                if current_app.config.get("GLOBAL_SEARCH_INDEX"):
                    ctx["global_search_db_path"] = _clean(current_app.config.get("GLOBAL_SEARCH_INDEX"))
                else:
                    ctx["search_index_path"] = _clean(current_app.config.get("SEARCH_INDEX") or "")
        except Exception:
            pass
    return ctx


def _query_variants(query: str, workflow: str) -> list[str]:
    query = _clean(query)
    variants: list[str] = []

    def add(value: str) -> None:
        value = _clean(value)
        if value and value not in variants:
            variants.append(value)

    add(query)
    text = _lower(query)
    if "pec" in text or "posta elettronica certificata" in text:
        add(f"{query} pec comunicazione allegati ricevuta")
        add("ultima pec ricevuta allegati")
        add("messaggio pec ricevuto")
    if any(token in text for token in ("allegato", "allegati", "ocr", "pdf", "documento", "documenti")):
        add(f"{query} documento allegato ocr")
    if any(token in text for token in ("scaden", "termine", "udienza", "oggi", "domani")):
        add(f"{query} scadenza agenda udienza")
    if any(token in text for token in ("cliente", "assistito", "anagrafica", "recapiti")):
        add(f"{query} cliente soggetto anagrafica")
    if any(token in text for token in ("fascicolo", "pratica", "rg", "causa")):
        add(f"{query} fascicolo pratica documento")
    if workflow in {"cabina", "next_action", "question_answering", "studio_data_lookup"}:
        add(f"{query} fascicolo cliente scadenza agenda comunicazione documento")
    return variants[:6]


def _row_type(row: dict[str, Any]) -> str:
    return _lower(row.get("tipo") or row.get("entity_type") or row.get("type") or row.get("source_type"))


def _allowed(row: dict[str, Any]) -> bool:
    row_type = _row_type(row)
    if not row_type:
        return False
    if row_type in _EXCLUDED_ENTITY_TYPES:
        return False
    source_module = _lower(row.get("source_module") or row.get("fonte"))
    if source_module in _EXCLUDED_ENTITY_TYPES:
        return False
    return row_type in _ALLOWED_ENTITY_TYPES


def _source_id(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    raw = (
        row.get("entity_id")
        or row.get("id")
        or metadata.get("document_id")
        or metadata.get("id")
        or row.get("url")
        or row.get("titolo")
        or row.get("title")
    )
    return _clean(raw)


def _content(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    parts = [
        _clean(row.get("snippet") or row.get("excerpt") or row.get("text")),
        _clean(metadata.get("stato")),
        _clean(metadata.get("date") or metadata.get("data_scadenza") or metadata.get("data")),
    ]
    allegati = metadata.get("allegati") or metadata.get("attachments") or []
    if isinstance(allegati, list) and allegati:
        names = [_clean(item.get("nome") if isinstance(item, dict) else item) for item in allegati]
        names = [name for name in names if name]
        if names:
            parts.append("Allegati: " + ", ".join(names[:8]))
    return ". ".join(part for part in parts if part)


def _score(row: dict[str, Any], query: str) -> float:
    row_type = _row_type(row)
    score = float(row.get("score") or 0.0)
    if score <= 0:
        score = 0.74
    if row_type in _PRIORITY_TYPES:
        score = max(score, 0.82)
    text = _lower(" ".join([query, row.get("titolo") or row.get("title") or "", row.get("snippet") or ""]))
    if "pec" in text and row_type in {"pec", "comunicazione", "email"}:
        score = max(score, 0.94)
    return min(score, 0.98)


def _to_evidence(row: dict[str, Any], query: str) -> EvidenceItem | None:
    if not _allowed(row):
        return None
    row_type = _row_type(row)
    title = _clean(row.get("titolo") or row.get("title")) or row_type.title()
    content = _content(row) or title
    source_id = _source_id(row) or title.lower().replace(" ", "-")
    metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}
    metadata.update(
        {
            "origin": "global_search",
            "source_module": row.get("source_module") or row.get("fonte") or "Ricerca Studio",
            "source_url": row.get("url") or row.get("source_url") or "",
            "affidabilita": row.get("affidabilita") or "interna_verificata",
            "data_acquisizione": row.get("data_acquisizione") or metadata.get("date") or "",
        }
    )
    url = _clean(row.get("url") or row.get("source_url"))
    return EvidenceItem(
        source_type=f"studio_db:{row_type}",
        source_id=source_id,
        title=title,
        content=content,
        score=_score(row, query),
        metadata=metadata,
        authority="iusentra_studio_db",
        trust_class="B",
        source_level=3,
        verified_reference=True,
        official_url=url if url.startswith(("http://", "https://")) else None,
    )


class StudioDatabaseSource:
    """Retrieval operativo sui dati interni indicizzati da Ricerca Studio."""

    source_name = "studio_database"

    def __init__(self, *, limit: int = 18) -> None:
        self.limit = max(1, min(int(limit or 18), 40))

    def search(self, queries, request, context):
        metadata = dict(getattr(request, "metadata", {}) or {})
        if _flag(metadata.get("disable_studio_database_source")):
            return []
        try:
            from pct.global_search.service import search_for_lex
        except Exception:
            return []

        workflow = _clean(
            (context or {}).get("workflow")
            or getattr(request, "workflow_hint", "")
            or metadata.get("workflow")
            or ""
        )
        query = _clean((queries or [None])[0] or getattr(request, "query", ""))
        ctx = _search_context(context or {}, request)
        seen: set[str] = set()
        items: list[EvidenceItem] = []
        for variant in _query_variants(query, workflow):
            try:
                rows = list(search_for_lex(ctx, variant, limit=self.limit) or [])
            except Exception:
                rows = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                evidence = _to_evidence(row, variant)
                if evidence is None:
                    continue
                key = f"{evidence.source_type}:{evidence.source_id}:{evidence.title}"
                if key in seen:
                    continue
                seen.add(key)
                items.append(evidence)
                if len(items) >= self.limit:
                    return items
        return items
