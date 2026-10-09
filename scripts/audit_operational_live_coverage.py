"""Offline coverage inventory; never touches tenant data or starts workloads."""
from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    files = subprocess.check_output(["rg", "--files", "frontend/src", "pct", "web/services", "web/bootstrap"], cwd=root, text=True).splitlines()
    live_source = ast.parse((root / "pct/operational_live.py").read_text(encoding="utf-8"))
    installed = next(ast.literal_eval(node.value) for node in live_source.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "TABLE_DOMAINS" for target in node.targets))
    surfaces = []
    tables: dict[str, set[str]] = {}
    writers = []
    for relative in sorted(files):
        path = root / relative
        if path.suffix not in {".tsx", ".py", ".sql"}:
            continue
        source = path.read_text(encoding="utf-8")
        relative = Path(relative).as_posix()
        if path.suffix == ".tsx":
            subscriptions = re.findall(r"useOperationalRefresh\(\s*\[([^]]*)\]", source)
            surfaces.append({
                "component": relative,
                "refresh_subscriptions": subscriptions,
                "has_fetch_or_loader": bool(re.search(r"\bfetch\(|\bget\w+(?:Data|Page|Payload)\(", source)),
                "wrapper_exports": re.findall(r"export\s+\{[^}]+\}\s+from\s+['\"]([^'\"]+)", source),
                "real_acceptance": "not_verified",
                "coverage": "subscription_to_verify" if subscriptions else "to_trace",
            })
        else:
            for table in re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z][a-z0-9_]*)\s*\(", source, re.I):
                tables.setdefault(table, set()).add(relative)
            for match in re.finditer(r"salva_tabella\(\s*['\"]([a-z_]+)['\"]", source):
                end = source.find("\n", match.start())
                writers.append({"source": relative, "line": source.count("\n", 0, match.start()) + 1, "table": match.group(1), "call": source[match.start():end].strip(), "transaction_and_concurrency": "to_trace"})
    report = {
        "scope": "Intero IUSENTRA: menu, sottomenu, procedure, funzioni, task e superfici incorporate.",
        "status": "OPEN",
        "method": "Inventario statico offline. Include features e wrapper; non equivale a prova materiale, schema runtime o copertura funzionale.",
        "components": surfaces,
        "native_sql_tables": [{"table": table, "declarations": sorted(paths), "signal_domains": list(installed.get(table, ())), "runtime_and_delivery_acceptance": "not_verified"} for table, paths in sorted(tables.items())],
        "table_writer_calls": writers,
    }
    target = root / "artifacts/data-flow/live-sync-surface-inventory-20261008.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"surfaces": len(surfaces), "declared_sql_tables": len(tables), "writer_calls_to_trace": len(writers), "status": "OPEN"}))


if __name__ == "__main__":
    main()
