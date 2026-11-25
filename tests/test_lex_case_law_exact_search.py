from __future__ import annotations

from types import SimpleNamespace

from lex.research.case_law_exact_search import (
    parse_case_law_reference,
    search_exact_case_law_reference,
)
from lex.retrieval import official_web


def test_ricerca_pronuncia_distingue_dispositivo_e_motivazione(monkeypatch):
    reference = parse_case_law_reference("Cassazione ordinanza n. 12345/2024")
    url = "https://www.cortedicassazione.it/decisioni/12345.pdf"
    calls = []

    def search(query, *, limit_results):
        calls.append(query)
        assert limit_results == 4
        return [
            SimpleNamespace(
                title="Corte di Cassazione, ordinanza n. 12345/2024",
                official_url=url,
                excerpt="Ritenuto in fatto. La parte ricorrente ha depositato memoria.",
            )
        ]

    monkeypatch.setattr(official_web, "search_recognized_official_web", search)
    result = search_exact_case_law_reference(reference)

    assert calls == reference.normalized_queries
    assert result.exact_match_found and result.completed_from_web
    assert result.official_url == url
    assert result.has_pdf and result.has_motivazione
    assert not result.has_dispositivo
    assert result.missing_parts == ["dispositivo"]


def test_ricerca_pronuncia_non_parte_senza_numero_e_anno(monkeypatch):
    reference = parse_case_law_reference("orientamento della Corte di Cassazione")

    def search(*args, **kwargs):
        raise AssertionError("La ricerca esatta richiede un riferimento esatto")

    monkeypatch.setattr(official_web, "search_recognized_official_web", search)
    result = search_exact_case_law_reference(reference)

    assert not result.official_search_run
    assert result.missing_parts == ["numero", "data o anno"]


def test_ricerca_pronuncia_conserva_indizio_locale_quando_la_fonte_non_risponde(monkeypatch):
    reference = parse_case_law_reference("Ordinanza n. 12345/2024 della Corte di Cassazione")

    def search(*args, **kwargs):
        raise TimeoutError("Fonte ufficiale non raggiungibile")

    monkeypatch.setattr(official_web, "search_recognized_official_web", search)
    result = search_exact_case_law_reference(reference, {"title": "Massima in archivio"})

    assert result.official_search_run
    assert result.local_fragment_found
    assert result.local_fragment_summary == "Massima in archivio"
    assert not result.completed_from_web
    assert result.official_url == ""
    assert result.web_blocked_reason == "Fonte ufficiale non raggiungibile"


def test_massima_senza_fonte_non_completa_la_ricerca_esatta(monkeypatch):
    reference = parse_case_law_reference("Ordinanza n. 12345/2024 della Corte di Cassazione")
    monkeypatch.setattr(
        official_web,
        "search_recognized_official_web",
        lambda *args, **kwargs: [
            {
                "title": "Ordinanza n. 12345/2024",
                "excerpt": "Massima di terzi",
                "url": "https://example.test/12345",
            },
        ],
    )

    result = search_exact_case_law_reference(reference)

    assert result.possible_match_found and not result.exact_match_found
    assert not result.completed_from_web
    assert result.confidence_cap == 0.45
    assert result.related_results[0]["content"] == "Massima di terzi"
    assert result.missing_parts == ["testo integrale", "dispositivo", "motivazione", "URL/PDF ufficiale"]
