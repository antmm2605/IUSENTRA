from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.audit_lex_tenant_sources import run


def _write_control_tower(path: Path, tenant_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute(
            """
            CREATE TABLE legal_communications (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL
            )
            """
        )
        con.executemany(
            "INSERT INTO legal_communications (id, tenant_id) VALUES (?, ?)",
            [(f"row-{index}", tenant_id) for index, tenant_id in enumerate(tenant_ids)],
        )


def test_audit_lex_tenant_sources_accepts_registered_studio_aliases(tmp_path):
    data_root = tmp_path / "data"
    (data_root / "tenants" / "tenant-abc").mkdir(parents=True)
    (data_root / "tenant_user_directory.json").write_text(
        json.dumps(
            {
                "users": {
                    "avvocato": {
                        "tenant_id": "uuid-1",
                        "tenant_slug": "studio-legale",
                        "tenant_storage_key": "tenant-abc",
                    }
                },
                "emails": {},
            }
        ),
        encoding="utf-8",
    )
    _write_control_tower(
        data_root / "tenants" / "tenant-abc" / "email" / "pec_control_tower.sqlite",
        ["tenant-abc", "studio-legale"],
    )

    result = run(data_root)

    assert result["ok"] is True
    tenant = result["tenants"][0]
    assert tenant["accepted_tenant_ids"] == ["studio-legale", "tenant-abc", "uuid-1"]
    source = tenant["sources"]["pec_control_tower"]
    assert source["tenant_count"] == 2
    assert source["other_tenant_rows"] == 0


def test_audit_lex_tenant_sources_rejects_foreign_tenant_rows(tmp_path):
    data_root = tmp_path / "data"
    (data_root / "tenants" / "tenant-abc").mkdir(parents=True)
    _write_control_tower(
        data_root / "tenants" / "tenant-abc" / "email" / "pec_control_tower.sqlite",
        ["tenant-abc", "altro-studio"],
    )

    result = run(data_root)

    assert result["ok"] is False
    tenant = result["tenants"][0]
    assert tenant["sources"]["pec_control_tower"]["other_tenant_rows"] == 1
    assert tenant["warnings"]
