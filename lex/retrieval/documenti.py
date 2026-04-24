"""Retrieval documentale per Lex.

Cerca i documenti di un fascicolo, ne estrae il testo (PDF, p7m, DOCX)
e li converte in EvidenceItem con contenuto leggibile dall'LLM.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lex.contracts import EvidenceItem

_MAX_EXCERPT = 1200   # caratteri massimi per singola evidenza


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _tipo_val(doc: Any) -> str:
    tipo = getattr(doc, "tipo", None)
    return getattr(tipo, "value", "") if tipo is not None else ""


def _extract_text(doc: Any, documents_dir: Path) -> str:
    percorso = _clean(getattr(doc, "percorso", ""))
    if not percorso:
        return ""
    full_path = documents_dir / percorso
    if not full_path.exists():
        return ""
    try:
        from lex.tools._doc_extractor import extract_text_from_file
        return extract_text_from_file(full_path)
    except Exception:
        return ""


def _build_excerpt(doc: Any, text: str, tipo: str) -> str:
    nome = _clean(getattr(doc, "nome", "")) or "Documento"
    firmato = "si" if getattr(doc, "firmato_digitalmente", False) else "no"
    data_doc = _clean(getattr(doc, "data_documento", "")) or "n.d."
    da_portale = _clean(getattr(doc, "id_deposito_pct", ""))

    header = (
        f"[{tipo or 'ALTRO'}] {nome} — data: {data_doc}, firmato: {firmato}"
    )
    if da_portale:
        header += f", deposito portale: {da_portale}"

    if text:
        body = text[:_MAX_EXCERPT].rstrip()
        if len(text) > _MAX_EXCERPT:
            body += "…"
        return f"{header}\n\n{body}"
    return header


_HIGH_PRIORITY_TYPES = {
    "COMUNICAZIONE", "COMUNICAZIONE_CANCELLERIA",
    "SENTENZA", "ORDINANZA", "DECRETO", "PROVVEDIMENTO",
    "DEPOSITO_PCT", "NOTIFICA", "VERBALE",
}


def _query_tokens(query: str) -> list[str]:
    tokens: list[str] = []
    for raw in query.replace("/", " ").replace("-", " ").split():
        token = _clean(raw).lower()
        if len(token) < 3:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def _matches_tokens(value: str, tokens: list[str]) -> bool:
    haystack = str(value or "").lower()
    return bool(tokens) and any(token in haystack for token in tokens)


def _is_generic_document_query(tokens: list[str]) -> bool:
    generic_tokens = {
        "fascicolo",
        "documenti",
        "documento",
        "tutto",
        "tutti",
        "completo",
        "quadro",
        "leggi",
        "leggere",
        "catalogo",
        "inventario",
        "rag",
    }
    return not tokens or bool(set(tokens) & generic_tokens)


def _document_manifest_item(pratica_id: str, documenti: list[Any]) -> EvidenceItem | None:
    if not documenti:
        return None
    rows: list[str] = []
    for index, doc in enumerate(documenti, start=1):
        nome = _clean(getattr(doc, "nome", "")) or "Documento"
        tipo = _tipo_val(doc) or "ALTRO"
        data_doc = _clean(getattr(doc, "data_documento", "") or getattr(doc, "data_caricamento", "")) or "n.d."
        deposito = _clean(getattr(doc, "id_deposito_pct", ""))
        suffix = f", deposito {deposito}" if deposito else ""
        rows.append(f"{index}. [{tipo}] {nome} - data {data_doc}{suffix}")
    return EvidenceItem(
        source_type="documento_manifesto",
        source_id=f"{pratica_id}:documenti:manifesto",
        title=f"Inventario completo documenti fascicolo ({len(documenti)})",
        content="Documenti censiti nel fascicolo: " + " ".join(rows),
        score=0.98,
        metadata={"count": len(documenti), "authority": "internal_fascicolo_documents"},
    )


def search_document_sources(
    pratica_id: str,
    message: str,
    context: dict[str, Any],
) -> list[EvidenceItem]:
    """Cerca documenti nel fascicolo ed estrae il contenuto testuale."""
    if not pratica_id:
        return []

    store = None
    try:
        from web.helpers import get_fascicoli
        store = get_fascicoli()
    except Exception:
        return []

    try:
        fascicolo = store.get(pratica_id)
    except Exception:
        fascicolo = None
    if not fascicolo:
        return []

    documents_dir: Path = getattr(store, "documents_dir", None)
    if documents_dir is None:
        documents_dir = Path("./fascicoli/documenti")

    documenti: list[Any] = list(getattr(fascicolo, "documenti", []) or [])
    query = _clean(message).lower()

    def _sort_key(d: Any) -> tuple:
        tipo = _tipo_val(d)
        prio = 0 if tipo in _HIGH_PRIORITY_TYPES else 1
        da_portale = 0 if _clean(getattr(d, "id_deposito_pct", "")) else 1
        data = _clean(getattr(d, "data_documento", "") or getattr(d, "data_caricamento", ""))
        return (prio, da_portale, data)

    documenti_sorted = sorted(documenti, key=_sort_key)
    tokens = _query_tokens(query)
    generic_query = _is_generic_document_query(tokens)

    items: list[EvidenceItem] = []
    manifest = _document_manifest_item(pratica_id, documenti_sorted)
    if manifest is not None:
        items.append(manifest)
    for doc in documenti_sorted:
        nome = _clean(getattr(doc, "nome", ""))
        tipo = _tipo_val(doc)
        metadata_text = " ".join(
            [
                nome,
                tipo,
                _clean(getattr(doc, "note", "")),
                _clean(getattr(doc, "descrizione", "")),
                _clean(getattr(doc, "id_deposito_pct", "")),
            ]
        )
        metadata_match = _matches_tokens(metadata_text, tokens)
        text = _extract_text(doc, documents_dir)
        text_match = _matches_tokens(text, tokens)

        doc_id = _clean(getattr(doc, "id", ""))
        score = 0.95 if tipo in _HIGH_PRIORITY_TYPES else 0.65
        if text:
            score = min(score + 0.05, 1.0)
        if metadata_match or text_match:
            score = min(score + 0.12, 1.0)
        elif not generic_query and tipo not in _HIGH_PRIORITY_TYPES:
            score = max(score - 0.18, 0.45)

        items.append(
            EvidenceItem(
                source_type="documento",
                source_id=doc_id,
                title=nome or tipo or "Documento",
                content=_build_excerpt(doc, text, tipo),
                score=score,
                metadata={
                    "tipo": tipo,
                    "firmato": bool(getattr(doc, "firmato_digitalmente", False)),
                    "data_documento": _clean(getattr(doc, "data_documento", "")),
                    "id_deposito_pct": _clean(getattr(doc, "id_deposito_pct", "")),
                    "has_text": bool(text),
                },
            )
        )
    return items
