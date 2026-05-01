from __future__ import annotations

from lex.providers import health
from lex.research.citation_builder import ResearchCitationBuilder


def test_provider_health_usa_runtime_risolto(monkeypatch):
    monkeypatch.setattr(
        health,
        "resolved_runtime",
        lambda: {"api_base_url": "http://127.0.0.1:11434", "chat_model": "lex-test"},
    )

    payload = health.provider_health()

    assert payload["ok"] is True
    assert payload["provider"] == "ollama"
    assert payload["runtime"]["chat_model"] == "lex-test"


def test_warm_runtime_restituisce_dizionario(monkeypatch):
    monkeypatch.setattr(health, "warm_ollama_chat_runtime", lambda: {"status": "ready"})

    assert health.warm_runtime() == {"status": "ready"}


def test_research_citation_builder_ricostruisce_da_metadata():
    rows = [
        {
            "source_type": "giurisprudenza",
            "source_id": "sentenza-49-2026",
            "title": "Sentenza n. 49/2026 - Corte costituzionale",
            "content": "Dispositivo e principio ricavabile dalla fonte ufficiale.",
            "score": 0.91,
            "metadata": {
                "authority": "Corte costituzionale",
                "official_url": "https://www.cortecostituzionale.it/",
                "trust_class": "ufficiale",
                "source_level": 1,
                "verified_reference": True,
                "published_at": "2026-04-01",
                "freshness_score": 0.8,
            },
        }
    ]

    citations = ResearchCitationBuilder().build(rows, citations=[])

    assert len(citations) == 1
    citation = citations[0]
    assert citation.title == "Sentenza n. 49/2026 - Corte costituzionale"
    assert citation.authority == "Corte costituzionale"
    assert citation.verified_reference is True
    assert citation.source_level == 1


def test_research_citation_builder_preserva_citazioni_esistenti():
    existing = [{"title": "Fonte gia' validata"}]

    assert ResearchCitationBuilder().build(rows=[], citations=existing) == existing
