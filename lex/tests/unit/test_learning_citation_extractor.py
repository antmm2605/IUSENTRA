from __future__ import annotations

from lex.learning.citation_extractor import extract_citations


def _by_normalized(citations):
    return {citation.normalized_text: citation for citation in citations}


def test_passthrough_estrattore_pct_su_articolo_codice():
    citations = _by_normalized(extract_citations("Ai sensi dell'art. 2043 c.c. il danno va risarcito."))
    assert "art. 2043 c.c." in citations
    assert citations["art. 2043 c.c."].reference_type == "article"
    assert citations["art. 2043 c.c."].start >= 0


def test_gdpr_nudo_diventa_regolamento_ue():
    citations = _by_normalized(extract_citations("Il GDPR disciplina il trattamento."))
    assert "Regolamento (UE) 2016/679" in citations
    assert citations["Regolamento (UE) 2016/679"].reference_type == "eu_act"


def test_named_act_aliases():
    citations = _by_normalized(extract_citations("Si applica il codice privacy insieme al GDPR."))
    assert "D.Lgs. 196/2003" in citations
    assert "Regolamento (UE) 2016/679" in citations


def test_articolo_gdpr_arricchito_e_riga_nuda_soppressa():
    citations = extract_citations("L'art. 6 GDPR individua le basi giuridiche.")
    normalized = [citation.normalized_text for citation in citations]
    assert "art. 6 Regolamento (UE) 2016/679" in normalized
    # La riga nuda "art. 6" (catturata dall'estrattore pct) è contenuta nello
    # span arricchito e non deve comparire come citazione autonoma.
    assert "art. 6" not in normalized
    enriched = next(citation for citation in citations if citation.normalized_text == "art. 6 Regolamento (UE) 2016/679")
    assert enriched.reference_type == "article"
    assert enriched.start >= 0 and enriched.end > enriched.start


def test_offset_su_testo_normalizzato():
    text = "Premessa.   L'art.   6 GDPR   si applica."
    citations = extract_citations(text)
    enriched = next(citation for citation in citations if "2016/679" in citation.normalized_text and citation.reference_type == "article")
    normalized_source = " ".join(text.split())
    assert normalized_source[enriched.start:enriched.end].casefold().startswith("art.")


def test_dedup_mantiene_confidenza_maggiore():
    citations = extract_citations("Il Regolamento (UE) 2016/679, cioè il GDPR, si applica.")
    matching = [citation for citation in citations if citation.normalized_text == "Regolamento (UE) 2016/679"]
    assert len(matching) == 1
    assert matching[0].confidence >= 0.88


def test_limit_rispettato():
    text = " ".join(f"art. {n} c.c." for n in range(1, 40))
    assert len(extract_citations(text, limit=5)) <= 5
