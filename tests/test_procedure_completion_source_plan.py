"""Piano fonti multi-sorgente: ordine, gap fail-closed, nessuna invenzione."""
from __future__ import annotations

import json
from pathlib import Path

from pct.procedure_completion.schema import normalize_request
from pct.procedure_completion.source_plan import SourcePlanSettings, build_source_plan

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "procedure_completion" / "512075_accordo_ristrutturazione_input.json").read_text(
        encoding="utf-8"
    )
)


def test_codice_in_catalogo_produce_fonte_tecnica_e_riferimenti():
    request = normalize_request({"codice": "010003", "denominazione": "Procedimento di ingiunzione ante causam"})
    plan = build_source_plan(request)
    assert plan.catalog_entry, "il codice reale del catalogo viene risolto"
    origini = {src.origin for src in plan.sources}
    assert "catalogo_pst" in origini
    tipi = {src.source_type for src in plan.sources}
    assert "technical" in tipi
    assert "official" in tipi, "la famiglia XSD porta riferimenti ufficiali"


def test_codice_512075_non_in_catalogo_produce_gap_bloccante_non_invenzioni():
    request = normalize_request(FIXTURE["input"])
    plan = build_source_plan(request)
    assert not plan.catalog_entry
    codici_gap = {gap.codice_gap for gap in plan.gaps}
    assert "codice_non_in_catalogo" in codici_gap
    bloccanti = [gap for gap in plan.gaps if gap.severita == "blocking"]
    assert bloccanti, "codice sconosciuto = gap bloccante"
    # Nessuna fonte normativa inventata per un codice non censito.
    assert not [src for src in plan.sources if src.source_type == "official"]


def test_fonte_disabilitata_genera_gap_non_contenuti():
    request = normalize_request({"codice": "010003", "denominazione": "Procedimento di ingiunzione"})
    plan = build_source_plan(request, settings=SourcePlanSettings())
    codici = {gap.codice_gap for gap in plan.gaps}
    assert "normattiva_non_abilitata" in codici
    assert "adempimenti_fiscali_senza_fonte" in codici
    assert not [src for src in plan.sources if src.origin == "normattiva"]


def test_retriever_fixture_abilitato_aggiunge_fonti_governate():
    def retriever_fixture(query: str):
        return list(FIXTURE["fonti_simulate"])

    request = normalize_request(FIXTURE["input"])
    settings = SourcePlanSettings(normattiva_enabled=True, normattiva_retriever=retriever_fixture)
    plan = build_source_plan(request, settings=settings)
    ufficiali = [src for src in plan.sources if src.source_type == "official"]
    assert ufficiali and "FIXTURE" in ufficiali[0].title
    # Il gap sul catalogo resta: la fonte non sana il codice sconosciuto.
    assert any(gap.codice_gap == "codice_non_in_catalogo" for gap in plan.gaps)


def test_retriever_che_fallisce_produce_gap_non_eccezione():
    def retriever_rotto(query: str):
        raise RuntimeError("rete non disponibile")

    request = normalize_request({"codice": "010003", "denominazione": "Procedimento di ingiunzione"})
    settings = SourcePlanSettings(normattiva_enabled=True, normattiva_retriever=retriever_rotto)
    plan = build_source_plan(request, settings=settings)
    assert any(gap.codice_gap == "normattiva_non_raggiungibile" for gap in plan.gaps)


def test_fonte_fiscale_configurata_popola_fiscal_rows():
    def agenzia(query: str):
        return [
            {
                "source_title": "FIXTURE Agenzia Entrate - contributo unificato",
                "source_url": "https://www.agenziaentrate.gov.it/fixture",
                "extracted_principle": "FIXTURE: adempimento fiscale di test.",
                "source_type": "technical",
            }
        ]

    request = normalize_request({"codice": "010003", "denominazione": "Procedimento di ingiunzione"})
    settings = SourcePlanSettings(agenzia_entrate_enabled=True, agenzia_entrate_retriever=agenzia)
    plan = build_source_plan(request, settings=settings)
    assert plan.fiscal_rows
    assert all("agenziaentrate" in str(row.get("source_url", "")) for row in plan.fiscal_rows)
