"""Offline inventory of file-backed JSON paths; never reads application data."""
from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return call_name(node.value) + "." + node.attr
    return ""


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = subprocess.check_output(["git", "ls-files", "*.py"], cwd=root, text=True).splitlines()
    excluded = {"tests", "artifacts", "examples", "docs", "tools", ".agents", ".codex", ".claude"}
    findings = []
    errors = []
    scanned = 0
    for relative in paths:
        path = root / relative
        if Path(relative).parts[0] in excluded or "tests" in Path(relative).parts or not path.is_file():
            continue
        source = path.read_text(encoding="utf-8-sig")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            errors.append({"file": relative, "line": exc.lineno, "reason": str(exc)})
            continue
        scanned += 1
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = call_name(node.func)
            operation = ""
            certainty = "file_io"
            if name == "json.load":
                operation = "read_json_stream"
                certainty = "stream_to_trace"
            elif name == "json.dump":
                operation = "write_json_stream"
                certainty = "stream_to_trace"
            elif name == "json.loads" and any(isinstance(child, ast.Call) and call_name(child.func).endswith((".read_text", ".read", ".read_bytes")) for child in ast.walk(node)):
                operation = "read_json_file"
            elif name.endswith(".write_text") and any(isinstance(child, ast.Call) and call_name(child.func) == "json.dumps" for child in ast.walk(node)):
                operation = "write_json_file"
            if not operation:
                continue
            ancestors = []
            parent = parents.get(node)
            while parent is not None:
                if isinstance(parent, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    ancestors.append(parent.name)
                parent = parents.get(parent)
            findings.append({
                "file": relative, "line": node.lineno, "scope": ".".join(reversed(ancestors)),
                "operation": operation, "evidence": certainty,
                "code": ast.get_source_segment(source, node),
                "role": "to_trace_not_automatically_a_defect",
                "sql_mentions_in_file": any(token in source for token in ("studio_db", "moduli_json_records", "get_studio_db", "sqlite3", "psycopg")),
            })
    report = {
        "status": "OPEN", "scanned_python_files": scanned,
        "method": "AST offline sui sorgenti tracciati; nessun documento o file dati letto. Include percorsi condizionali, cache, configurazioni e stream da distinguere dalle fonti operative. Le menzioni SQL non provano il ramo usato a runtime.",
        "limitations": "Adapter dinamici, alias di json, variabili serializzate prima della scrittura e accessi esterni richiedono tracciamento aggiuntivo. Nessun esito funzionale dedotto dalla sola scansione.",
        "findings": findings, "parse_errors": errors,
    }
    target = root / "artifacts/data-flow/direct-json-storage-inventory-20261008.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files_scanned": scanned, "file_or_stream_calls": len(findings), "files_with_calls": len({item['file'] for item in findings}), "parse_errors": len(errors)}))


if __name__ == "__main__":
    main()
