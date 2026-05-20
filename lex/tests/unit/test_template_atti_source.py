from __future__ import annotations

import importlib.util
from pathlib import Path

from lex.contracts import LexRequest


def _template_atti_source_class():
    path = Path(__file__).parents[2] / "retrieval" / "sources" / "template_atti.py"
    spec = importlib.util.spec_from_file_location("lex_template_atti_source_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.TemplateAttiSource


def _request(query: str) -> LexRequest:
    return LexRequest(
        tenant_id="tenant-1",
        user_id="utente-1",
        session_id="sessione-1",
        query=query,
    )


def test_template_atti_source_trova_atto_di_citazione():
    items = _template_atti_source_class()().search(["atto di citazione"], _request("atto di citazione"), {})

    assert items
    assert items[0].source_type == "template_atto"
    assert items[0].metadata["model_code"] == "CIV_CIT_001"
    assert items[0].authority == "iusentra_template_atti"
    assert items[0].trust_class == "B"
    assert items[0].verified_reference is True
    assert items[0].metadata["compile_url"].endswith("/CIV_CIT_001")


def test_template_atti_source_trova_diffida():
    items = _template_atti_source_class()().search(["crea diffida"], _request("crea diffida"), {})

    assert items
    assert items[0].metadata["model_code"] == "STR_DIFF_001"
    assert items[0].metadata["prefill_capable"] is True
    assert "required_fields" in items[0].metadata
