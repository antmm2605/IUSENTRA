"""Tool Lex per leggere documenti del fascicolo (PDF, PDF.p7m, DOCX, TXT)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseLexTool
from ._doc_extractor import extract_text_from_file, get_fascicoli_store


_SUPPORTED_EXTENSIONS = (".pdf", ".p7m", ".docx", ".doc", ".txt", ".xml")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _tipo_label(doc: Any) -> str:
    tipo = getattr(doc, "tipo", None)
    return getattr(tipo, "value", "") if tipo is not None else ""


def _doc_meta(doc: Any, fascicolo_id: str = "") -> dict[str, Any]:
    return {
        "id": getattr(doc, "id", ""),
        "nome": getattr(doc, "nome", ""),
        "tipo": _tipo_label(doc),
        "percorso": getattr(doc, "percorso", ""),
        "firmato_digitalmente": bool(getattr(doc, "firmato_digitalmente", False)),
        "data_documento": getattr(doc, "data_documento", ""),
        "data_caricamento": getattr(doc, "data_caricamento", ""),
        "id_deposito_pct": getattr(doc, "id_deposito_pct", ""),
        "note": getattr(doc, "note", ""),
        "fascicolo_id": fascicolo_id,
    }


def _is_readable(nome: str) -> bool:
    name_lower = str(nome or "").lower()
    return any(
        name_lower.endswith(ext) or name_lower.endswith(ext + ".p7m")
        for ext in _SUPPORTED_EXTENSIONS
    )


def _extract_doc_text(store: Any, doc: Any) -> str:
    percorso = _clean(getattr(doc, "percorso", ""))
    if not percorso:
        return ""
    try:
        path = Path(store.documents_dir) / percorso
        if path.exists():
            return extract_text_from_file(path)
    except Exception as exc:
        return f"[Errore estrazione: {exc}]"
    return ""


class DocumentTool(BaseLexTool):
    tool_name = "documento"

    def run(self, **kwargs) -> dict[str, Any]:
        """Legge documenti da un fascicolo.

        Parametri:
        - fascicolo_id / pratica_id: ID fascicolo (obbligatorio)
        - documento_id / id: ID specifico → restituisce testo completo
        - q / query: ricerca per parola nel nome o tipo
        - tipo: filtra per TipoDocumento (COMUNICAZIONE, SENTENZA, MEMORIA...)
        - portale / telematico: True → solo documenti con id_deposito_pct
        - cancelleria: True → solo COMUNICAZIONE/NOTIFICA/DEPOSITO_PCT
        - limit: max risultati (default 8)
        - extract_text: True (default) → estrae testo leggibile
        """
        store = get_fascicoli_store()
        if store is None:
            return {"error": "store_unavailable", "items": []}

        fascicolo_id = _clean(kwargs.get("fascicolo_id") or kwargs.get("pratica_id"))
        doc_id = _clean(kwargs.get("documento_id") or kwargs.get("id"))
        query = _clean(kwargs.get("q") or kwargs.get("query")).lower()
        tipo_filtro = _clean(kwargs.get("tipo")).upper()
        solo_portale = bool(kwargs.get("portale") or kwargs.get("telematico"))
        solo_cancelleria = bool(kwargs.get("cancelleria"))
        limit = max(int(kwargs.get("limit") or 8), 1)
        extract_text = str(kwargs.get("extract_text", "true")).lower() not in {"false", "0", "no"}

        if not fascicolo_id:
            return {"error": "fascicolo_id obbligatorio", "items": []}

        try:
            fascicolo = store.get(fascicolo_id)
        except Exception:
            fascicolo = None
        if not fascicolo:
            return {"found": False, "fascicolo_id": fascicolo_id, "items": []}

        documenti: list[Any] = list(getattr(fascicolo, "documenti", []) or [])

        # Documento specifico per ID → restituisce testo completo
        if doc_id:
            match = next((d for d in documenti if getattr(d, "id", "") == doc_id), None)
            if not match:
                return {"found": False, "documento_id": doc_id, "items": []}
            meta = _doc_meta(match, fascicolo_id)
            if extract_text and _is_readable(meta["nome"]):
                meta["testo"] = _extract_doc_text(store, match)
            else:
                meta["testo"] = ""
            return {"found": True, "documento": meta, "items": [meta]}

        # Lista con filtri
        items: list[dict[str, Any]] = []
        for doc in documenti:
            nome = _clean(getattr(doc, "nome", ""))
            tipo = _tipo_label(doc)

            if query and query not in nome.lower() and query not in tipo.lower():
                continue
            if tipo_filtro and tipo_filtro not in tipo.upper():
                continue
            if solo_portale and not _clean(getattr(doc, "id_deposito_pct", "")):
                continue
            if solo_cancelleria and tipo.upper() not in {"COMUNICAZIONE", "NOTIFICA", "DEPOSITO_PCT"}:
                continue

            meta = _doc_meta(doc, fascicolo_id)
            if extract_text and _is_readable(nome):
                meta["testo"] = _extract_doc_text(store, doc)
            else:
                meta["testo"] = ""
            items.append(meta)
            if len(items) >= limit:
                break

        return {"fascicolo_id": fascicolo_id, "items": items, "total": len(items)}
