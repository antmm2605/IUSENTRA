from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from legal_deposit.models import DepositDocument, PreflightResult
from legal_deposit.policies import ChannelProfile


def build_manifest(
    *,
    job_id: str,
    tenant_id: str,
    fascicolo_id: str,
    profile: ChannelProfile,
    documents: list[DepositDocument],
    preflight: list[PreflightResult],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "iusentra.legal_deposit.manifest.v1",
        "job_id": job_id,
        "tenant_id": tenant_id,
        "fascicolo_id": fascicolo_id,
        "channel": profile.id,
        "channel_name": profile.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "documents": [
            {
                "role": doc.role,
                "filename": doc.filename,
                "mime_type": doc.mime_type,
                "size_bytes": doc.size_bytes,
                "sha256": doc.sha256,
                "signed": doc.signed,
                "signature_format": doc.signature_format,
            }
            for doc in documents
        ],
        "preflight": [item.to_dict() for item in preflight],
        "signature_policy": {
            "target": profile.signature_policy.target,
            "format": profile.signature_policy.format,
            "required": profile.signature_policy.required,
            "verify_after_sign": profile.signature_policy.verify_after_sign,
        },
        "metadata": dict(metadata or {}),
    }
