from __future__ import annotations

from ai_lex_sources import batch_evaluate_sources as compat_batch_evaluate_sources
from ai_lex_sources import infer_area as compat_infer_area
from lex.research import classify_request
from lex.research.source_policy import (
    SourceMode,
    Tier,
    batch_evaluate_sources,
    evaluate_source,
    evaluate_source_row,
    get_tier_for_domain,
    infer_area,
    summarize_evaluated_sources,
)


def test_infer_area_riconosce_lavoro():
    assert infer_area("licenziamento ingiustificato e tfr non pagato") == "lavoro"


def test_get_tier_for_domain_classifica_normattiva_come_tier_1():
    assert get_tier_for_domain("normattiva.it", "normativa") == Tier.TIER_1


def test_evaluate_source_segna_altalex_come_affidabilita_media_in_balanced():
    evaluated = evaluate_source(
        "https://www.altalex.com/documents/news/2026/04/18/licenziamento",
        "lavoro",
        SourceMode.BALANCED,
    )

    assert evaluated.tier == Tier.TIER_2
    assert evaluated.reliability == "medium"
    assert evaluated.score > 0.4


def test_batch_evaluate_sources_filtra_domini_deboli_in_strict():
    evaluated = batch_evaluate_sources(
        [
            "https://www.normattiva.it/uri-res/N2Ls",
            "https://blog.esempio.com/post",
        ],
        "normativa",
        SourceMode.STRICT,
        min_score=0.2,
    )

    assert [item.domain for item in evaluated] == ["normattiva.it"]


def test_evaluate_source_row_valorizza_contesto_interno_verificato():
    row = evaluate_source_row(
        {
            "id": "fascicolo:abc",
            "type": "fascicolo",
            "title": "Fascicolo RG 10/2026",
            "verified_reference": True,
        },
        area="civile",
        mode="balanced",
    )

    assert row["source_policy_tier"] == "tier_1"
    assert row["source_reliability_label"] == "high"


def test_summarize_evaluated_sources_blocca_risposte_strict_senza_primarie():
    summary = summarize_evaluated_sources(
        [
            evaluate_source_row(
                {
                    "id": "documento:1",
                    "type": "documento",
                    "title": "Nota interna",
                },
                area="normativa",
                mode="strict",
            )
        ],
        area="normativa",
        area_confidence=0.91,
        mode="strict",
        require_primary=True,
    )

    assert summary.block_unverified_answer is True
    assert "Mancano fonti primarie" in summary.warnings[0]


def test_classify_request_promuove_la_normativa_in_modalita_strict():
    profile = classify_request("Verifica la normativa vigente sul consenso privacy")

    assert profile.intent == "normativa"
    assert profile.source_mode == "strict"
    assert profile.risk_level == "high"


def test_ai_lex_sources_compat_module_resta_importabile():
    assert compat_infer_area("licenziamento ingiustificato") == "lavoro"
    items = compat_batch_evaluate_sources(
        ["https://www.normattiva.it/uri-res/N2Ls"],
        "normativa",
        SourceMode.STRICT,
        min_score=0.2,
    )

    assert len(items) == 1
    assert items[0].domain == "normattiva.it"
