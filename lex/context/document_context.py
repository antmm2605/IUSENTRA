"""Contesto documentale di Lex."""

from __future__ import annotations

from typing import Any

from web.helpers import get_fascicoli
from web.services.document_crypto import decrypt_doc
from web.services.signed_document_runtime import (
    build_document_signed_snapshot_from_bytes,
    build_document_version_candidates,
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _apply_limit(rows: list[Any], limit: int | None) -> list[Any]:
    if limit is None:
        return rows
    try:
        max_items = int(limit)
    except Exception:
        return rows
    if max_items <= 0:
        return rows
    return rows[:max_items]


def load_document_context(
    *,
    pratica_id: str = "",
    fascicolo_id: str = "",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    target_id = _clean_spaces(pratica_id) or _clean_spaces(fascicolo_id)
    if not target_id:
        return []
    gestore = get_fascicoli()
    fascicolo = gestore.get(target_id)
    if not fascicolo:
        return []
    rows: list[dict[str, Any]] = []
    for doc in _apply_limit(list(fascicolo.documenti or []), limit):
        signed_snapshot = None
        if str(getattr(doc, "nome", "") or "").strip().lower().endswith(".p7m"):
            try:
                percorso = gestore.percorso_documento(target_id, doc.id)
                signed_snapshot = build_document_signed_snapshot_from_bytes(
                    source_name=doc.nome,
                    source_path=str(percorso),
                    data=decrypt_doc(percorso.read_bytes()),
                    version_candidates=build_document_version_candidates(
                        gestore,
                        doc,
                        decrypt_doc=decrypt_doc,
                    ),
                )
            except Exception:
                signed_snapshot = None
        rows.append(
            {
                "id": doc.id,
                "nome": doc.nome,
                "tipo": getattr(doc.tipo, "value", ""),
                "firmato": bool(getattr(doc, "firmato_digitalmente", False)),
                "data_documento": doc.data_documento,
                "data_caricamento": doc.data_caricamento,
                "note": doc.note,
                "id_deposito_pct": doc.id_deposito_pct,
                "signed_status": (signed_snapshot or {}).get("signed_status"),
                "signed_ui": (signed_snapshot or {}).get("ui_status"),
                "ai_readable": bool(((signed_snapshot or {}).get("signed_status") or {}).get("payload_available"))
                if signed_snapshot
                else not str(getattr(doc, "nome", "") or "").strip().lower().endswith(".p7m"),
            }
        )
    return rows
