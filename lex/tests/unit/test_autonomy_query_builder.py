from __future__ import annotations

from lex.autonomy.models import ResearchQuestion
from lex.autonomy.query_builder import build_queries


def test_citazione_nazionale_va_su_normattiva():
    question = ResearchQuestion(question="Cosa stabilisce art. 2043 c.c.?", area="civile", target_citation="art. 2043 c.c.")
    queries = build_queries(question, max_queries=3)
    assert queries[0] == "art. 2043 c.c. site:normattiva.it"
    assert all("site:" in query or query == "art. 2043 c.c." for query in queries)


def test_citazione_ue_va_su_eurlex():
    question = ResearchQuestion(
        question="Cosa stabilisce art. 6 Regolamento (UE) 2016/679?",
        area="privacy",
        target_citation="art. 6 Regolamento (UE) 2016/679",
    )
    queries = build_queries(question, max_queries=3)
    assert queries[0] == "art. 6 Regolamento (UE) 2016/679 site:eur-lex.europa.eu"
    assert any("garanteprivacy.it" in query for query in queries)


def test_termine_usa_domini_governati_dell_area():
    question = ResearchQuestion(question="Definizione?", area="privacy", target_term="legittimo interesse")
    queries = build_queries(question, max_queries=3)
    assert any("site:garanteprivacy.it" in query or "site:gpdp.it" in query or "site:eur-lex.europa.eu" in query for query in queries)
    assert all('"legittimo interesse"' in query for query in queries)


def test_dedup_ordine_e_tetto():
    question = ResearchQuestion(question="Cosa stabilisce L. 241/1990?", area="amministrativo", target_citation="L. 241/1990")
    queries = build_queries(question, max_queries=2)
    assert len(queries) == 2
    assert len({query.casefold() for query in queries}) == 2
    assert build_queries(question, max_queries=2) == queries  # deterministico


def test_domanda_senza_target_usa_query_di_area():
    question = ResearchQuestion(question="Quali sono le fonti dell'area civile?", area="civile")
    queries = build_queries(question, max_queries=3)
    assert queries
    assert any("fonti normative primarie civile" in query for query in queries)


def test_query_solo_da_campi_strutturati_niente_testo_libero():
    # Il testo libero (potenzialmente con PII) NON deve finire nelle query.
    question = ResearchQuestion(
        question="Il cliente Mario Rossi chiede se l'art. 2043 c.c. si applica",
        area="civile",
        target_citation="art. 2043 c.c.",
    )
    queries = build_queries(question, max_queries=3)
    assert all("Mario" not in query and "Rossi" not in query for query in queries)
