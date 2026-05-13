"""Forensic bundle export for a fascicolo."""

from __future__ import annotations

from dataclasses import dataclass
import io
import json
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .canonical import canonicalize
from .merkle import merkle_proof


README_VERIFICA = """# Verifica prova IUSENTRA

Questo bundle contiene eventi firmati, snapshot Merkle, proof e manifest file.
La verifica non richiede accesso al database applicativo.

Comandi principali:

```bash
python scripts/verify_audit.py verify-bundle bundle.zip
python scripts/verify_audit.py verify-chain bundle.zip --fascicolo-id <id>
python scripts/verify_audit.py verify-proof proofs/<event_id>.json
```

La fonte probatoria e' l'oggetto JSON firmato salvato in WORM. L'indice SQL e'
solo una cache di consultazione ricostruibile.
"""


@dataclass(frozen=True)
class AuditBundleResult:
    filename: str
    content: bytes
    events_count: int


class AuditBundleBuilder:
    def __init__(self, service: Any) -> None:
        self.service = service

    def build_fascicolo_bundle(self, *, tenant_id: str, fascicolo_id: str) -> AuditBundleResult:
        rows = self.service.repository.list_events(tenant_id=tenant_id, fascicolo_id=fascicolo_id, limit=100000)
        rows = sorted(rows, key=lambda item: (str(item.get("event_ts_utc") or ""), str(item.get("event_id") or "")))
        buffer = io.BytesIO()
        files_manifest: list[dict[str, Any]] = []
        signers: dict[str, str] = {}
        snapshot_cache: dict[str, dict[str, Any]] = {}
        with ZipFile(buffer, "w", ZIP_DEFLATED) as zf:
            zf.writestr("README_VERIFICA.md", README_VERIFICA)
            public_key = self.service.signer.public_key_pem()
            if public_key:
                kid = str(getattr(self.service.signer, "kid", "signer") or "signer")
                signers[kid] = f"signers/{kid}.pem"
                zf.writestr(f"signers/{kid}.pem", public_key)
            for row in rows:
                envelope = self.service.load_envelope(row)
                event_id = str(row["event_id"])
                zf.writestr(f"events/{event_id}.json", canonicalize(envelope))
                for file_ref in (envelope.get("signed_event") or {}).get("files") or []:
                    files_manifest.append(
                        {
                            "event_id": event_id,
                            "label": file_ref.get("label", ""),
                            "storage_ref": file_ref.get("storage_ref", ""),
                            "sha256": file_ref.get("sha256", ""),
                            "size_bytes": file_ref.get("size_bytes", 0),
                            "mime": file_ref.get("mime", ""),
                        }
                    )
                snapshot_id = str(row.get("snapshot_id") or "")
                if snapshot_id and snapshot_id not in snapshot_cache:
                    snap_row = self.service.repository.get_snapshot(snapshot_id, tenant_id=tenant_id)
                    if snap_row:
                        raw = self.service.worm_store.get_object(str(snap_row["worm_key"]), version_id=str(snap_row.get("worm_version_id") or "") or None)
                        snapshot_cache[snapshot_id] = json.loads(raw.decode("utf-8"))
                        zf.writestr(f"snapshots/{snapshot_id}.json", raw)
                        tsa_key = str(snap_row.get("tsa_token_worm_key") or "")
                        if tsa_key:
                            try:
                                zf.writestr(f"tsa/{snapshot_id}.tsr", self.service.worm_store.get_object(tsa_key))
                            except Exception:
                                pass
                if snapshot_id and snapshot_id in snapshot_cache:
                    snapshot = snapshot_cache[snapshot_id].get("signed_snapshot") or {}
                    hashes = [str(item) for item in snapshot.get("event_hashes") or []]
                    proof = {
                        "format": "audit-merkle-proof-v1",
                        "event_id": event_id,
                        "event_hash": str(row["event_hash"]),
                        "snapshot_id": snapshot_id,
                        "merkle_root": str(snapshot.get("merkle_root") or ""),
                        "merkle_alg": str(snapshot.get("merkle_alg") or ""),
                        "proof": [step.to_dict() for step in merkle_proof(str(row["event_hash"]), hashes)] if hashes else [],
                    }
                    zf.writestr(f"proofs/{event_id}.json", canonicalize(proof))
            zf.writestr("files_manifest.json", canonicalize({"files": files_manifest}))
            zf.writestr(
                "bundle_manifest.json",
                canonicalize(
                    {
                        "format": "audit-fascicolo-bundle-v1",
                        "tenant_id": tenant_id,
                        "fascicolo_id": fascicolo_id,
                        "events_count": len(rows),
                        "signers": signers,
                    }
                ),
            )
        return AuditBundleResult(
            filename=f"audit-fascicolo-{fascicolo_id}.zip",
            content=buffer.getvalue(),
            events_count=len(rows),
        )
