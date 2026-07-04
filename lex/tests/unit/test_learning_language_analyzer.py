from __future__ import annotations

from lex.learning.legal_language_analyzer import analyze_language, extract_term_observations

_TESTO_CIVILE = (
    "Ai sensi dell'art. 2043 c.c. qualunque fatto doloso o colposo che cagiona ad altri un danno "
    "ingiusto obbliga al risarcimento del danno. La responsabilità aquiliana richiede il nesso causale."
)
_TESTO_GDPR = (
    "L'art. 6 GDPR disciplina il consenso e il legittimo interesse del titolare del trattamento. "
    "Il trattamento dati richiede una base giuridica documentata."
)


def test_profilo_civile_deterministico():
    profile_a = analyze_language(_TESTO_CIVILE, sample_id="civ", area_hint="civile")
    profile_b = analyze_language(_TESTO_CIVILE, sample_id="civ", area_hint="civile")
    assert profile_a.to_dict() == profile_b.to_dict()
    assert profile_a.area == "civile"
    assert profile_a.tokens > 0
    assert profile_a.legal_density > 0
    assert 0 < profile_a.complexity_index <= 1
    assert any(citation.normalized_text == "art. 2043 c.c." for citation in profile_a.citations)


def test_profilo_gdpr_produce_termini_e_citazioni():
    profile = analyze_language(_TESTO_GDPR, sample_id="priv", area_hint="privacy")
    normalized_terms = {term.normalized for term in profile.terms}
    assert "legittimo interesse" in normalized_terms
    assert "trattamento dati" in normalized_terms
    assert any("2016/679" in citation.normalized_text for citation in profile.citations)


def test_termini_noti_vs_candidati():
    observations = extract_term_observations(
        "L'accesso civico consente a chiunque di richiedere documenti. L'accesso civico è distinto "
        "dall'accesso documentale. L'accesso civico richiede bilanciamento.",
        "amministrativo",
    )
    by_normalized = {observation.normalized: observation for observation in observations}
    assert by_normalized["accesso civico"].kind == "candidato"
    assert by_normalized["accesso civico"].occurrences >= 3
    # "accesso agli atti" è nell'ontologia: se osservato è un concetto, non candidato.
    known = extract_term_observations("Il diritto di accesso agli atti è garantito.", "amministrativo")
    kinds = {observation.normalized: observation.kind for observation in known}
    assert kinds.get("accesso agli atti") == "concetto"


def test_testo_vuoto_non_produce_nulla():
    profile = analyze_language("", sample_id="vuoto")
    assert profile.tokens == 0
    assert profile.citations == []
    assert profile.terms == []
    assert profile.complexity_index == 0.0


def test_stopword_legalese_non_generano_candidati_rumorosi():
    # Regressione dalla prova web reale (2026-07-04): il testo integrale del GDPR
    # produceva candidati come "trattamento tale" / "trattamento nonché" /
    # "qualsiasi pena". Le funzioni grammaticali del legalese non sono concetti.
    testo = (
        "Tale trattamento, nonché il trattamento seguente, riguarda qualsiasi pena "
        "e ciascuna sanzione; il medesimo trattamento informa l'interessato del "
        "presente regolamento, salvo eventuale deroga."
    )
    observations = extract_term_observations(testo, "privacy")
    normalized = {observation.normalized for observation in observations}
    for rumoroso in (
        "trattamento tale",
        "tale trattamento",
        "trattamento nonché",
        "trattamento seguente",
        "qualsiasi pena",
        "medesimo trattamento",
        "trattamento informa",
        "eventuale sanzione",
    ):
        assert rumoroso not in normalized, f"candidato rumoroso non filtrato: {rumoroso}"


def test_concetti_legittimi_sopravvivono_alle_stopword():
    testo = (
        "Il legittimo interesse del titolare del trattamento e il trattamento dati "
        "richiedono il bilanciamento; il danno ingiusto obbliga al risarcimento del danno."
    )
    observations = extract_term_observations(testo, "privacy")
    normalized = {observation.normalized for observation in observations}
    assert "legittimo interesse" in normalized
    assert "trattamento dati" in normalized
