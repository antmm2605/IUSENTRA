from __future__ import annotations

import json

from lex.legal_sources.adapters import ADAPTER_CLASSES, BrocardiAdapter
from scripts.import_normative_brocardi import BrocardiImporter


def test_brocardi_adapter_registrato_come_fonte_secondaria_sicura():
    adapter = BrocardiAdapter()

    assert BrocardiAdapter in ADAPTER_CLASSES
    assert adapter.source_id == "brocardi"
    assert adapter.metadata.official is False
    assert adapter.metadata.enabled_by_default is False
    assert adapter.metadata.network_allowed_by_default is False
    assert adapter.metadata.supports_versions is False
    assert adapter.search("articolo 2043 codice civile") == []

    health = adapter.healthcheck()
    assert health["policy_ok"] is True
    assert health["enabled"] is False
    assert health["network_allowed"] is False

    discovery = adapter.discover()
    assert discovery["metadata"]["source_id"] == "brocardi"
    assert "Normattiva" in " ".join(discovery["citation_policy"]["notes"])


def test_brocardi_importer_genera_campione_senza_rete(tmp_path):
    importer = BrocardiImporter(output_file=tmp_path / "brocardi.jsonl")

    citations = importer.import_from_sample_data()

    assert citations
    assert {item["source_id"] for item in citations} == {"brocardi"}
    assert any(item["authority"] == "Codice Civile" and item["article"] == "1" for item in citations)
    assert all(item["url"].startswith("https://www.brocardi.it/") for item in citations)

    importer.save_to_jsonl(citations)
    rows = [
        json.loads(line)
        for line in (tmp_path / "brocardi.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == len(citations)
