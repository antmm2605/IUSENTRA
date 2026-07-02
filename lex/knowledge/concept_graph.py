"""Grafo dei concetti giuridici di Lex (dict puro, niente dipendenze grafo).

Nodi = concetti/norme/fonti/aree; archi = relazioni deterministiche
(`cita`, `definisce`, `appartiene_a`, `letta_per`). Il salvataggio ordina nodi
e archi in modo stabile: due save consecutivi producono byte identici, così il
file è diff-abile e il ciclo resta deterministico.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "iusentra.lex_concept_graph.v1"
RELATIONS: tuple[str, ...] = ("cita", "definisce", "appartiene_a", "letta_per", "correlato_a")


def node_id(kind: str, label: str) -> str:
    """Identità stabile del nodo: `kind:label` normalizzato casefold."""

    clean_label = " ".join(str(label or "").split()).casefold()
    clean_kind = " ".join(str(kind or "").split()).casefold() or "concetto"
    return f"{clean_kind}:{clean_label}"


class ConceptGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: dict[tuple[str, str, str], int] = {}

    # -- costruzione -----------------------------------------------------

    def ensure_node(self, kind: str, label: str, *, area: str = "", seen_at: str = "") -> bool:
        """Crea o aggiorna un nodo; True se il nodo è nuovo."""

        identifier = node_id(kind, label)
        node = self._nodes.get(identifier)
        if node is None:
            self._nodes[identifier] = {
                "label": " ".join(str(label or "").split()),
                "kind": " ".join(str(kind or "").split()).casefold() or "concetto",
                "area": str(area or ""),
                "observation_count": 1,
                "first_seen": str(seen_at or ""),
                "last_seen": str(seen_at or ""),
            }
            return True
        node["observation_count"] = int(node.get("observation_count") or 0) + 1
        if seen_at:
            node["last_seen"] = str(seen_at)
            node.setdefault("first_seen", str(seen_at))
        if area and not node.get("area"):
            node["area"] = str(area)
        return False

    def add_edge(self, source: str, target: str, relation: str, *, weight_delta: int = 1) -> bool:
        """Aggiunge/rafforza un arco tra nodi esistenti; True se l'arco è nuovo."""

        relation = str(relation or "").strip().casefold()
        if relation not in RELATIONS:
            raise ValueError(f"Relazione non prevista dal grafo concetti: {relation!r}")
        if source not in self._nodes or target not in self._nodes:
            raise ValueError("Gli archi collegano solo nodi già presenti nel grafo")
        key = (source, target, relation)
        is_new = key not in self._edges
        self._edges[key] = self._edges.get(key, 0) + max(1, int(weight_delta))
        return is_new

    # -- interrogazione ---------------------------------------------------

    def has_node(self, kind: str, label: str) -> bool:
        return node_id(kind, label) in self._nodes

    def degree(self, identifier: str) -> int:
        return sum(1 for source, target, _ in self._edges if identifier in (source, target))

    def nodes(self) -> dict[str, dict[str, Any]]:
        return {key: dict(value) for key, value in self._nodes.items()}

    def isolated_nodes(self, *, min_observations: int = 1) -> list[str]:
        return sorted(
            identifier
            for identifier, node in self._nodes.items()
            if self.degree(identifier) == 0 and int(node.get("observation_count") or 0) >= min_observations
        )

    def counts(self) -> dict[str, int]:
        return {"nodes": len(self._nodes), "edges": len(self._edges)}

    # -- persistenza ------------------------------------------------------

    def to_payload(self) -> dict[str, Any]:
        nodes = {key: self._nodes[key] for key in sorted(self._nodes)}
        edges = [
            {"source": source, "target": target, "relation": relation, "weight": weight}
            for (source, target, relation), weight in sorted(self._edges.items())
        ]
        return {"schema_version": SCHEMA_VERSION, "nodes": nodes, "edges": edges}

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_payload(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination

    @classmethod
    def load(cls, path: str | Path) -> ConceptGraph:
        graph = cls()
        source = Path(path)
        if not source.exists():
            return graph
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return graph
        for identifier, node in (payload.get("nodes") or {}).items():
            if isinstance(node, dict):
                graph._nodes[str(identifier)] = dict(node)
        for edge in payload.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            key = (str(edge.get("source") or ""), str(edge.get("target") or ""), str(edge.get("relation") or ""))
            if all(key) and key[0] in graph._nodes and key[1] in graph._nodes:
                graph._edges[key] = int(edge.get("weight") or 1)
        return graph


__all__ = ["RELATIONS", "SCHEMA_VERSION", "ConceptGraph", "node_id"]
