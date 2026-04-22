from __future__ import annotations

from hypothesis import given, settings, strategies as st

from lex.contracts import EvidenceItem, LexRequest
from lex.guards.legal_reference_guard import LegalReferenceGuard
from lex.retrieval.ranker import rank_evidence
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
        "www.inipec.gov.it",
        "accessoallebanchedati.registroimprese.it",
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


@settings(deadline=None, max_examples=30)
@given(
    domain=st.one_of(
        st.sampled_from(
            [
                "normattiva.it",
                "gazzettaufficiale.it",
                "altalex.com",
                "wikipedia.org",
            ]
        ),
        st.from_regex(r"[a-z0-9-]{3,16}\.example", fullmatch=True),
    ),
    area=st.sampled_from(["normativa", "giurisprudenza", "prassi", "default"]),
)
def test_get_tier_for_domain_resta_deterministico_property(domain, area):
    first = get_tier_for_domain(domain, area)
    assert first in {Tier.TIER_1, Tier.TIER_2, Tier.TIER_3, Tier.UNKNOWN}
    assert get_tier_for_domain(domain, area) == first


@settings(deadline=None, max_examples=25)
@given(
    urls=st.lists(
        st.sampled_from(
            [
                "https://www.normattiva.it/uri-res/N2Ls",
                "https://www.gazzettaufficiale.it/eli/id/2023/10/31/23G00163/sg",
                "https://www.altalex.com/documents/news/2026/04/18/licenziamento",
                "https://blog.esempio.com/post",
            ]
        ),
        min_size=1,
        max_size=8,
    ),
    area=st.sampled_from(["normativa", "giurisprudenza", "prassi", "default"]),
    mode=st.sampled_from(list(SourceMode)),
)
def test_batch_evaluate_sources_ritorna_score_ordinati_property(urls, area, mode):
    evaluated = batch_evaluate_sources(urls, area, mode, min_score=0.0)
    scores = [item.score for item in evaluated]
    assert scores == sorted(scores, reverse=True)


@settings(deadline=None, max_examples=20)
@given(
    base_scores=st.lists(
        st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=6,
    )
)
def test_rank_evidence_mantiene_ordinamento_decrescente_property(base_scores):
    request = LexRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        query="verifica sentenza cassazione e fonte ufficiale",
    )
    items = [
        EvidenceItem(
            source_type="giurisprudenza",
            source_id=f"item-{index}",
            title=f"Fonte {index}",
            content="Cassazione fonte ufficiale e contenuto rilevante",
            score=score,
            trust_class="A" if index == 0 else "B",
            source_level=1 if index == 0 else 2,
            verified_reference=index == 0,
            authority="Corte di cassazione" if index == 0 else "Fonte secondaria",
            metadata={"authority": "official" if index == 0 else "secondary"},
        )
        for index, score in enumerate(base_scores)
    ]

    ranked = rank_evidence(items, request, "giurisprudenza")

    scores = [item.score for item in ranked]
    assert scores == sorted(scores, reverse=True)


@settings(deadline=None, max_examples=20)
@given(numero=st.integers(min_value=1, max_value=99999))
def test_legal_reference_guard_blocca_pdf_sentenza_non_verificato_property(numero):
    guard = LegalReferenceGuard()
    request = LexRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        query=f"Scarica il PDF della sentenza Cassazione n. {numero}/2024",
    )
    evidence = {
        "items": [
            EvidenceItem(
                source_type="giurisprudenza",
                source_id=f"cass-{numero}",
                title="Richiamo giurisprudenziale non verificato",
                content="Estratto descrittivo non verificato",
                score=0.55,
            )
        ],
        "citations": [],
    }

    verdict = guard.check(
        request=request,
        context={"permessi": {"can_use_lex": True}},
        workflow="giurisprudenza",
        evidence=evidence,
        draft=None,
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "high"
