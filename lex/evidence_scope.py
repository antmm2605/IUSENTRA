"""Perimetro delle evidenze private, condiviso da retrieval e destinazioni dati."""

_PRIVATE_SCOPES = frozenset({"private_fascicolo", "private_session"})
_PRIVATE_AUTHORITIES = frozenset(
    {"user_attachment", "internal_fascicolo_documents", "internal_document_intelligence_index"}
)


def is_private_evidence(metadata):
    metadata = metadata if isinstance(metadata, dict) else {}
    return (
        metadata.get("evidence_scope") in _PRIVATE_SCOPES
        or metadata.get("origin") == "user_attachment"
        or metadata.get("authority") in _PRIVATE_AUTHORITIES
    )


def private_evidence_metadata(*, tenant_id="", fascicolo_id="", document_id="", session_id=""):
    return {
        "evidence_scope": "private_fascicolo" if fascicolo_id else "private_session",
        "tenant_id": str(tenant_id or ""),
        "fascicolo_id": str(fascicolo_id or ""),
        "document_id": str(document_id or ""),
        "session_id": str(session_id or ""),
        "shared_catalog_eligible": False,
        "training_eligible": False,
    }
