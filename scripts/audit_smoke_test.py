#!/usr/bin/env python
"""Operational smoke test for WORM audit emission."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit import ActorContext, AuditFileRef, AuditKind, SourceContext, emit_event


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emette un evento audit ACT_GENERATED di smoke test su WORM.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--fascicolo-id", required=True)
    parser.add_argument("--idempotency-key", default="")
    args = parser.parse_args(argv)
    idempotency_key = args.idempotency_key or f"audit-smoke-{uuid.uuid4()}"
    with tempfile.NamedTemporaryFile("wb", delete=True) as handle:
        handle.write(b"IUSENTRA audit smoke evidence\n")
        handle.flush()
        result = emit_event(
            AuditKind.ACT_GENERATED,
            tenant_id=args.tenant_id,
            fascicolo_id=args.fascicolo_id,
            actor=ActorContext(actor_id="audit-smoke", actor_type="service"),
            payload={
                "atto_type": "SMOKE_TEST",
                "template_id": "audit-smoke",
                "template_version": "1",
                "editor_version": "smoke",
                "output_format": "txt",
                "fascicolo_id": args.fascicolo_id,
            },
            files=[
                AuditFileRef(
                    label="audit-smoke.txt",
                    storage_ref="dms://audit-smoke/transient",
                    path=handle.name,
                    mime="text/plain",
                )
            ],
            source=SourceContext(
                service="iusentra",
                module="scripts.audit_smoke_test",
                request_id=str(uuid.uuid4()),
                idempotency_key=idempotency_key,
            ),
            idempotency_key=idempotency_key,
        )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
