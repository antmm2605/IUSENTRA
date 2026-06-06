#!/usr/bin/env python
"""Audit read-only delle sorgenti operative Lex per ogni tenant."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any


SOURCE_PATHS = {
    "email_pec": Path("email/casella.json"),
    "pec_control_tower": Path("email/pec_control_tower.sqlite"),
    "fascicoli": Path("fascicoli/fascicoli.json"),
    "documenti_fascicolo": Path("fascicoli/documenti"),
    "scadenziario": Path("scadenziario/scadenze.json"),
    "agenda": Path("agenda/appuntamenti.json"),
    "notifiche": Path("notifiche/notifiche.json"),
}


def _json_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("items", "data", "records", "scadenze", "appuntamenti", "notifiche"):
            if isinstance(data.get(key), list):
                return len(data[key])
        return len(data)
    return 0


def _file_count(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    suffixes = {".pdf", ".docx", ".p7m", ".eml", ".xml", ".txt"}
    return sum(1 for item in path.rglob("*") if item.is_file() and item.suffix.lower() in suffixes)


def _control_tower_count(path: Path, tenant_ids: set[str]) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {"count": 0, "tenant_count": 0, "other_tenant_rows": 0, "tenant_ids": [], "accepted_tenant_ids": sorted(tenant_ids)}
    accepted_ids = sorted(item for item in tenant_ids if item)
    try:
        with sqlite3.connect(path) as con:
            tables = {
                str(row[0])
                for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            if "legal_communications" not in tables:
                return {"count": 0, "tenant_count": 0, "other_tenant_rows": 0, "tenant_ids": [], "accepted_tenant_ids": accepted_ids}
            total = int(con.execute("SELECT COUNT(*) FROM legal_communications").fetchone()[0])
            if accepted_ids:
                placeholders = ",".join("?" for _ in accepted_ids)
                own = int(
                    con.execute(
                        f"SELECT COUNT(*) FROM legal_communications WHERE tenant_id IN ({placeholders})",
                        tuple(accepted_ids),
                    ).fetchone()[0]
                )
            else:
                own = 0
            tenant_ids = [
                str(row[0])
                for row in con.execute(
                    "SELECT DISTINCT tenant_id FROM legal_communications ORDER BY tenant_id LIMIT 20"
                ).fetchall()
            ]
    except Exception as exc:
        return {"count": 0, "tenant_count": 0, "other_tenant_rows": 0, "tenant_ids": [], "accepted_tenant_ids": accepted_ids, "error": str(exc)[:180]}
    return {
        "count": total,
        "tenant_count": own,
        "other_tenant_rows": max(0, total - own),
        "tenant_ids": tenant_ids,
        "accepted_tenant_ids": accepted_ids,
    }


def _inside(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _tenant_alias_map(data_root: Path) -> dict[str, set[str]]:
    directory = data_root / "tenant_user_directory.json"
    aliases: dict[str, set[str]] = {}
    if not directory.exists():
        return aliases
    try:
        payload = json.loads(directory.read_text(encoding="utf-8"))
    except Exception:
        return aliases
    records: list[dict[str, Any]] = []
    for section in ("users", "emails"):
        values = payload.get(section)
        if isinstance(values, dict):
            records.extend(item for item in values.values() if isinstance(item, dict))
    for record in records:
        tenant_slug = str(record.get("tenant_slug") or "").strip()
        storage_key = str(record.get("tenant_storage_key") or "").strip()
        tenant_uuid = str(record.get("tenant_id") or "").strip()
        known = {item for item in (tenant_slug, storage_key, tenant_uuid) if item}
        for key in (tenant_slug, storage_key):
            if key:
                aliases.setdefault(key, set()).update(known)
    return aliases


def audit_tenant(tenant_dir: Path, alias_map: dict[str, set[str]] | None = None) -> dict[str, Any]:
    tenant_id = tenant_dir.name
    accepted_tenant_ids = {tenant_id, *(alias_map or {}).get(tenant_id, set())}
    sources: dict[str, Any] = {}
    warnings: list[str] = []
    for source_id, relative in SOURCE_PATHS.items():
        path = tenant_dir / relative
        under_tenant = _inside(tenant_dir, path)
        if not under_tenant:
            warnings.append(f"Sorgente {source_id} fuori dalla cartella tenant.")
        if source_id == "documenti_fascicolo":
            count = _file_count(path)
            extra: dict[str, Any] = {}
        elif source_id == "pec_control_tower":
            extra = _control_tower_count(path, accepted_tenant_ids)
            count = int(extra.get("tenant_count") or 0)
            if int(extra.get("other_tenant_rows") or 0):
                warnings.append(
                    "Control Tower contiene "
                    f"{extra['other_tenant_rows']} righe con tenant_id non collegato allo studio {tenant_id}."
                )
        else:
            count = _json_count(path)
            extra = {}
        sources[source_id] = {
            "path": str(path),
            "exists": path.exists(),
            "under_tenant": under_tenant,
            "count": count,
            **extra,
        }
    return {
        "tenant_id": tenant_id,
        "accepted_tenant_ids": sorted(item for item in accepted_tenant_ids if item),
        "tenant_dir": str(tenant_dir),
        "ok": not warnings,
        "sources": sources,
        "warnings": warnings,
    }


def run(data_root: Path) -> dict[str, Any]:
    tenants_root = data_root / "tenants"
    tenants = [item for item in sorted(tenants_root.iterdir()) if item.is_dir()] if tenants_root.exists() else []
    alias_map = _tenant_alias_map(data_root)
    payload = {
        "ok": True,
        "data_root": str(data_root),
        "tenant_count": len(tenants),
        "tenants": [audit_tenant(item, alias_map=alias_map) for item in tenants],
    }
    payload["ok"] = all(item.get("ok") for item in payload["tenants"])
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="", help="Radice dati IUSENTRA; default: PCT_DATA_ROOT o ./data.")
    args = parser.parse_args(argv)
    data_root = Path(args.data_root or os.getenv("PCT_DATA_ROOT") or Path.cwd() / "data")
    result = run(data_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
