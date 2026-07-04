from __future__ import annotations

import json

from lex.autonomy.memory_inspection import inspect_memory
from lex.knowledge.knowledge_base import KnowledgeBase


def _kb_con_dati(tmp_path):
    kb = KnowledgeBase(tmp_path / "memoria")
    kb.append(
        "improvement_proposals",
        "prop-1",
        {
            "title": "Aggiungere 'accesso civico' all'ontologia",
            "kind": "ontologia",
            "description": "Ricorre 3 volte senza voce di ontologia.",
            "target_module": "lex/knowledge/legal_ontology.py",
            "confidence": 0.7,
            "requires_human_review": True,
        },
    )
    kb.append(
        "improvement_proposals",
        "prop-2",
        {
            "title": "Connettore dedicato Normattiva",
            "kind": "connettore_dedicato",
            "description": "robots.txt restrittivo sul dominio tier_1.",
            "target_module": "lex/sources/connectors",
            "confidence": 0.65,
            "requires_human_review": True,
        },
    )
    kb.append(
        "source_readings",
        "read-1",
        {
            "title": "Gazzetta Ufficiale - Serie Generale n. 125",
            "url": "https://www.gazzettaufficiale.it/esempio",
            "status": "ok",
            "area": "lavoro",
            "source_id": "archivio_locale:gazzetta_ufficiale",
            "text_characters": 3500,
            "citations_normalized": ["L. 20 maggio 1970, n. 300", "Regolamento (UE) 2016/679"],
            "fetched_at": "2026-07-04T12:40:36+00:00",
        },
    )
    return kb


def test_memoria_popolata_conteggi_proposte_e_letture(tmp_path):
    kb = _kb_con_dati(tmp_path)
    snapshot = inspect_memory(kb.memory_dir)
    assert snapshot["memoria_presente"] is True
    assert snapshot["conteggi"]["improvement_proposals"] == 2
    assert snapshot["conteggi"]["source_readings"] == 1
    assert snapshot["proposte"][0]["titolo"] == "Connettore dedicato Normattiva"  # più recente prima
    assert snapshot["proposte"][0]["revisione_umana"] is True
    lettura = snapshot["letture"][0]
    assert lettura["citazioni"] == 2
    assert lettura["stato"] == "ok"
    assert lettura["fonte"] == "archivio_locale:gazzetta_ufficiale"


def test_memoria_assente_payload_onesto_senza_side_effect(tmp_path):
    base = tmp_path / "non-esiste" / "lex_memory"
    snapshot = inspect_memory(base)
    assert snapshot["memoria_presente"] is False
    assert snapshot["proposte"] == [] and snapshot["letture"] == []
    assert set(snapshot["conteggi"].values()) == {0}
    assert not base.exists()  # sola lettura: mai creare la memoria da qui


def test_righe_corrotte_saltate_fail_closed(tmp_path):
    memoria = tmp_path / "memoria"
    memoria.mkdir()
    (memoria / "improvement_proposals.jsonl").write_text(
        "{json rotto}\n" + json.dumps({"created_at": "2026-07-04", "payload": {"title": "Valida"}}) + "\n",
        encoding="utf-8",
    )
    snapshot = inspect_memory(memoria)
    assert snapshot["conteggi"]["improvement_proposals"] == 2  # conteggio onesto delle righe
    assert [row["titolo"] for row in snapshot["proposte"]] == ["Valida"]


def test_limiti_rispettati(tmp_path):
    kb = KnowledgeBase(tmp_path / "memoria")
    for indice in range(5):
        kb.append("improvement_proposals", f"prop-{indice}", {"title": f"P{indice}", "kind": "ontologia"})
    snapshot = inspect_memory(kb.memory_dir, proposals_limit=2)
    assert [row["titolo"] for row in snapshot["proposte"]] == ["P4", "P3"]
