from __future__ import annotations

from lex.sources.trust import assess_source


def test_fonte_primaria_ufficiale_ammessa():
    assessment = assess_source("https://www.normattiva.it/uri-res/x", area="civile")
    assert assessment.tier == "tier_1"
    assert assessment.allowed_for_learning is True
    assert assessment.reliability == "high"


def test_blog_mai_ammesso():
    assessment = assess_source("https://blog.example.com/post-legale", area="civile")
    assert assessment.tier == "unknown"
    assert assessment.allowed_for_learning is False
    assert any("mai autorevole" in reason for reason in assessment.reasons)


def test_denylist_vince_su_tutto():
    assessment = assess_source("https://www.normattiva.it/x", area="civile", denylist=["normattiva.it"])
    assert assessment.allowed_for_learning is False
    assert any("denylist" in reason for reason in assessment.reasons)


def test_allowlist_esclude_domini_fuori_lista():
    assessment = assess_source("https://www.cortedicassazione.it/x", area="civile", allowlist=["normattiva.it"])
    assert assessment.allowed_for_learning is False
    assert assessment.requires_review is True


def test_eurlex_pubblicamente_leggibile_ammesso_nonostante_registrazione_api():
    assessment = assess_source("https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679", area="privacy")
    assert assessment.allowed_for_learning is True
    assert assessment.requires_credentials is True  # solo per l'API, non per il web
    assert assessment.official is True


def test_tier2_istituzionale_secondaria_ammessa():
    assessment = assess_source("https://www.brocardi.it/codice-civile/art2043.html", area="civile")
    assert assessment.tier == "tier_2"
    assert assessment.allowed_for_learning is True
    assert any("secondaria" in reason for reason in assessment.reasons)


def test_tier3_solo_contesto_quando_ufficiali_non_richieste():
    url = "https://commenti.blogspot.com/2026/07/art-2043.html"  # *.blogspot.com = tier_3 per area civile
    strict = assess_source(url, area="civile", require_official=True)
    context = assess_source(url, area="civile", require_official=False)
    assert strict.tier == "tier_3"
    assert strict.allowed_for_learning is False
    assert context.allowed_for_learning is True
    assert context.requires_review is True
    assert any("mai come verità primaria" in reason for reason in context.reasons)


def test_url_vuota_scartata():
    assessment = assess_source("", area="civile")
    assert assessment.allowed_for_learning is False
