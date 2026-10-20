"""Create navigation indexes without changing or extending the official graph."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def build_index(repo: Path, out: Path) -> dict:
    manifest_path = out / "source-manifest.json"
    graph_path = out / "graphify-out/graph.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if Path(manifest["repository"]).resolve() != repo.resolve():
        raise ValueError("Il manifesto appartiene a un altro repository.")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = graph["nodes"]
    edges = graph.get("edges", graph.get("links", []))
    by_file = defaultdict(list)
    for node in nodes:
        source = node.get("source_file", "").replace("\\", "/")
        if source in manifest["files"]:
            by_file[source].append({
                "id": node["id"], "label": node.get("label", ""),
                "location": node.get("source_location", ""),
                "callable": bool(node.get("_callable")),
                "origin": node.get("_origin", "not_declared"),
            })
    registry = json.loads((repo / "tools/agent_knowledge/domains.json").read_text(encoding="utf-8"))
    domains = []
    for domain in registry["domains"]:
        matched = sorted(name for name in by_file if any(
            name.startswith(anchor) if anchor.endswith("/") else name == anchor
            for anchor in domain["anchors"]
        ))
        domains.append({**domain, "files": matched, "nodes": sum(len(by_file[n]) for n in matched)})
    # Read the declared legal taxonomy without importing application modules.
    taxonomy = repo / registry["legal_subjects_source"]
    assignments = {}
    subjects = []
    for statement in ast.parse(taxonomy.read_text(encoding="utf-8")).body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            name = statement.targets[0].id
            if isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
                assignments[name] = (statement.value.value, statement.lineno)
            elif name == "MATERIE" and isinstance(statement.value, ast.Tuple):
                for item in statement.value.elts:
                    if not isinstance(item, ast.Name) or item.id not in assignments:
                        raise ValueError("Tassonomia cambiata: verificare il nuovo formato.")
                    label, line = assignments[item.id]
                    subjects.append({"symbol": item.id, "label": label, "source": registry["legal_subjects_source"], "line": line, "confidence": "EXTRACTED"})
    result = {
        "schema_version": 1, "head": manifest["head"],
        "graphify_version": manifest["graphify_version"],
        "graph_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "source_files": len(manifest["files"]),
        "files_with_nodes": len(by_file),
        "files_without_nodes": sorted(set(manifest["files"]) - set(by_file)),
        "node_count": len(nodes), "edge_count": len(edges),
        "edge_confidence": dict(Counter(e.get("confidence", "not_declared") for e in edges)),
        "files": dict(sorted(by_file.items())), "domains": domains, "legal_subjects": subjects,
        "limitations": ["Static extraction is not runtime acceptance.", "Not every file node contains extracted symbols.", "Domain anchors are navigation hints, not exhaustive ownership contracts.", "Legal subject presence does not certify substantive legal coverage."],
    }
    (out / "coverage-index.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Indice del software per gli agenti", "", f"Graphify {result['graphify_version']}; {len(nodes)} nodi, {len(edges)} collegamenti.", "", "## Settori", ""]
    lines.extend(f"- {d['label']}: {len(d['files'])} file nei punti d’ingresso, {d['nodes']} nodi. Query iniziale: `{d['id']}`; verificare gli anchor in domains.json." for d in domains)
    lines.extend(["", "## Materie dichiarate", ""])
    lines.extend(f"- {s['label']}: `{s['source']}:{s['line']}` ({s['symbol']}, EXTRACTED)." for s in subjects)
    lines.extend(["", "## Copertura e limiti", "", f"Sorgenti inventariati: {result['source_files']}; file con nodi: {len(by_file)}. I file senza nodi sono elencati in coverage-index.json. Consultare anche la diagnostica di estrazione; un nodo-file non prova che il parser abbia riconosciuto tutti i simboli.", "", "Il file coverage-index.json conserva ogni funzione/simbolo riconosciuto con file, posizione e ID. I collegamenti restano nel graph.json originale, senza aggiunte inventate."])
    (out / "SOFTWARE_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {key: result[key] for key in ("source_files", "files_with_nodes", "node_count", "edge_count", "edge_confidence")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_index(Path(__file__).resolve().parents[2], args.out.resolve())))


if __name__ == "__main__":
    main()
