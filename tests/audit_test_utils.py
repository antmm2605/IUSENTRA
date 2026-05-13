from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from audit.repository import AuditRepository
from audit.schemas import ActorContext, AuditFileRef, AuditKind, SourceContext
from audit.service import AuditService
from audit.signing import JwsAuditSigner
from audit.worm import InMemoryWormStore


def make_key_pair() -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def make_service() -> tuple[AuditService, bytes]:
    private_pem, public_pem = make_key_pair()
    service = AuditService(
        repository=AuditRepository.in_memory(),
        worm_store=InMemoryWormStore(),
        signer=JwsAuditSigner(private_key_pem=private_pem, kid="test-signer", alg="RS256"),
        config={
            "AUDIT_ENABLED": True,
            "AUDIT_ENV": "development",
            "AUDIT_REQUIRE_WORM": True,
            "AUDIT_REQUIRE_SIGNATURE": True,
            "AUDIT_REQUIRE_TSA_FOR_SNAPSHOT": False,
            "AUDIT_RETENTION_YEARS": 10,
        },
    )
    return service, public_pem


def emit_sample_event(
    service: AuditService,
    tmp_path: Path,
    *,
    idempotency_key: str = "idem-1",
    kind: AuditKind = AuditKind.ACT_GENERATED,
    fascicolo_id: str = "FASC-1",
    content: bytes = b"atto probatorio",
) -> Any:
    file_path = tmp_path / f"{idempotency_key}.pdf"
    file_path.write_bytes(content)
    return service.emit_event(
        kind=kind,
        tenant_id="tenant-a",
        fascicolo_id=fascicolo_id,
        actor=ActorContext(actor_id="user-1", actor_type="user", display_name="Avv. Rossi"),
        payload={
            "atto_type": "comparsa",
            "template_id": "tpl-atto",
            "template_version": "1",
            "editor_version": "2.221.0",
            "output_format": "pdf",
            "fascicolo_id": fascicolo_id,
        },
        files=[
            AuditFileRef(
                label="atto.pdf",
                storage_ref=f"dms://fascicoli/{fascicolo_id}/atti/{idempotency_key}.pdf",
                path=file_path,
                mime="application/pdf",
            )
        ],
        source=SourceContext(service="iusentra", module="test", request_id=idempotency_key),
        idempotency_key=idempotency_key,
    )


def read_zip_json(zip_path: Path, name: str) -> dict[str, Any]:
    with ZipFile(zip_path, "r") as zf:
        return json.loads(zf.read(name).decode("utf-8"))
