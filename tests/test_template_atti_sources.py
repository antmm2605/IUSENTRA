import json
import re
from pathlib import Path

from pct.template_cartabia_rules import AREA_EVIDENCE_IDS


SOURCES = Path("docs/legal_sources/cartabia_sources.jsonl")
AUDIT = Path("docs/reports/cartabia_web_source_audit.md")


def _records():
    return [json.loads(line) for line in SOURCES.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_cartabia_sources_jsonl_esiste_e_copre_evidence_ruleset():
    records = _records()
    ids = {record["evidence_id"] for record in records}
    expected = {evidence_id for values in AREA_EVIDENCE_IDS.values() for evidence_id in values}

    assert SOURCES.exists()
    assert AUDIT.exists()
    assert expected <= ids
    for record in records:
        assert record["source_url"].startswith("https://")
        assert record["affidabilita"] in {"ufficiale", "primaria", "secondaria"}
        assert record["source_type"] in {
            "normativa",
            "ministero",
            "portale_telematico",
            "prassi",
            "giurisprudenza",
            "documentazione_tecnica",
        }
        assert record["data_accesso"] == "2026-05-12"
        assert record["usata_da_regole"]


def test_fonti_non_ufficiali_non_sono_marcate_primarie_e_non_contengono_dati_cliente():
    forbidden_domains = ("blog", "misterlex", "professionegiustizia", "wikipedia", "reddit", "studio")
    sensitive_patterns = [
        re.compile(r"\b[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]\b"),
        re.compile(r"\bcliente\s+(mario|rossi|bianchi)\b", re.IGNORECASE),
        re.compile(r"\bfascicolo\s+[0-9]+/[0-9]{4}\b", re.IGNORECASE),
    ]
    body = SOURCES.read_text(encoding="utf-8") + "\n" + AUDIT.read_text(encoding="utf-8")

    for record in _records():
        url = record["source_url"].lower()
        assert not any(domain in url for domain in forbidden_domains)
        if record["affidabilita"] == "primaria":
            assert "normattiva.it" in url or "gazzettaufficiale.it" in url
    assert not any(pattern.search(body) for pattern in sensitive_patterns)
