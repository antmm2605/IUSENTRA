from __future__ import annotations

import pytest

from lex.knowledge.concept_graph import ConceptGraph, node_id


def _graph() -> ConceptGraph:
    graph = ConceptGraph()
    graph.ensure_node("concetto", "Legittimo Interesse", area="privacy", seen_at="2026-07-02")
    graph.ensure_node("norma", "art. 6 Regolamento (UE) 2016/679", seen_at="2026-07-02")
    graph.add_edge(
        node_id("concetto", "legittimo interesse"),
        node_id("norma", "art. 6 regolamento (ue) 2016/679"),
        "correlato_a",
    )
    return graph


def test_ensure_node_idempotente_e_contatore_osservazioni():
    graph = ConceptGraph()
    assert graph.ensure_node("concetto", "danno ingiusto", seen_at="t1") is True
    assert graph.ensure_node("concetto", "Danno Ingiusto", seen_at="t2") is False
    node = graph.nodes()[node_id("concetto", "danno ingiusto")]
    assert node["observation_count"] == 2
    assert node["last_seen"] == "t2"


def test_archi_solo_tra_nodi_esistenti_e_relazioni_valide():
    graph = ConceptGraph()
    graph.ensure_node("concetto", "a")
    with pytest.raises(ValueError):
        graph.add_edge(node_id("concetto", "a"), node_id("norma", "manca"), "cita")
    graph.ensure_node("norma", "b")
    with pytest.raises(ValueError):
        graph.add_edge(node_id("concetto", "a"), node_id("norma", "b"), "relazione_inventata")


def test_isolated_nodes_e_degree():
    graph = _graph()
    graph.ensure_node("concetto", "conferenza di servizi", seen_at="t")
    graph.ensure_node("concetto", "conferenza di servizi", seen_at="t")
    assert node_id("concetto", "conferenza di servizi") in graph.isolated_nodes(min_observations=2)
    assert graph.degree(node_id("concetto", "legittimo interesse")) == 1


def test_save_load_byte_identici(tmp_path):
    graph = _graph()
    path = tmp_path / "concept_graph.json"
    graph.save(path)
    first = path.read_bytes()
    reloaded = ConceptGraph.load(path)
    reloaded.save(path)
    assert path.read_bytes() == first
    assert reloaded.counts() == graph.counts()


def test_load_file_mancante_o_corrotto(tmp_path):
    assert ConceptGraph.load(tmp_path / "assente.json").counts() == {"nodes": 0, "edges": 0}
    broken = tmp_path / "rotto.json"
    broken.write_text("{non json", encoding="utf-8")
    assert ConceptGraph.load(broken).counts() == {"nodes": 0, "edges": 0}
