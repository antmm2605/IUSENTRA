from __future__ import annotations

from lex.research.source_policy import (
    SourceMode,
    Tier,
    batch_evaluate_sources,
    get_tier_for_domain,
    infer_area,
)


def test_get_tier_for_domain_resta_deterministico_su_domini_noti_e_sconosciuti():
    domains = [
        "normattiva.it",
        "gazzettaufficiale.it",
        "altalex.com",
        "wikipedia.org",
        "dominio-sconosciuto.example",
    ]
    valid_tiers = {Tier.TIER_1, Tier.TIER_2, Tier.TIER_3, Tier.UNKNOWN}

    for domain in domains:
        first = get_tier_for_domain(domain, "normativa")
        assert first in valid_tiers
        for _ in range(3):
            assert get_tier_for_domain(domain, "normativa") == first


def test_infer_area_non_produce_valori_vuoti_su_query_reali():
    queries = [
        "licenziamento disciplinare e reintegra",
        "aggiornamento normativo privacy e consenso",
        "esecuzione immobiliare e pignoramento",
        "decreto ingiuntivo e opposizione",
        "mediazione obbligatoria e organismo competente",
    ]

    for query in queries:
        result = str(infer_area(query) or "").strip()
        assert result


def test_batch_evaluate_sources_preserva_ordinamento_per_score_decrescente():
    evaluated = batch_evaluate_sources(
        [
            "https://www.normattiva.it/uri-res/N2Ls",
            "https://www.gazzettaufficiale.it/eli/id/2023/10/31/23G00163/sg",
            "https://www.altalex.com/documents/news/2026/04/18/licenziamento",
            "https://blog.esempio.com/post",
        ],
        "normativa",
        SourceMode.BALANCED,
        min_score=0.0,
    )

    scores = [item.score for item in evaluated]
    assert scores == sorted(scores, reverse=True)
