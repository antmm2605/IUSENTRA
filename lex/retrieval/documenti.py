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

    items: list[EvidenceItem] = []
    for doc in documenti_sorted:
        nome = _clean(getattr(doc, "nome", ""))
        tipo = _tipo_val(doc)

        # Filtro testuale sul nome/tipo prima di estrarre testo
        if query:
            name_match = query in f"{nome} {tipo}".lower()
            if not name_match and tipo not in _HIGH_PRIORITY_TYPES:
                continue

        text = _extract_text(doc, documents_dir)

        # Se query presente e nome non corrisponde, verifica nel testo estratto
        if query and query not in f"{nome} {tipo}".lower():
            if not text or query not in text.lower():
                continue

        doc_id = _clean(getattr(doc, "id", ""))
        score = 0.95 if tipo in _HIGH_PRIORITY_TYPES else 0.65
        if text:
            score = min(score + 0.05, 1.0)

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
        if len(items) >= 8:
            break

    return items
