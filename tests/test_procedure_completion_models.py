"""Modelli del Procedure Completion Engine: confidence, policy fonti, serializzazione."""
from __future__ import annotations

from pct.procedure_completion.models import (
    MAX_PROFESSIONAL_EXCERPT_CHARS,
    ProcedureCompletionCard,
    ProcedureCompletionSource,
    assign_confidence,
    card_summary,
)


def _card_base(**extra) -> ProcedureCompletionCard:
    dati = {
        "codice": "010003",
        "denominazione": "Procedimento di ingiunzione ante causam",
        "sources": [],
        "citations": [],
        "gap_evidenza": [],
    }
    dati.update(extra)
    return ProcedureCompletionCard.from_dict(dati)


def test_fonte_professionale_e_sempre_summary_only_e_troncata():
    fonte = ProcedureCompletionSource(
        source_type="professional",
        title="Rivista professionale",
        excerpt="x" * 2000,
    )
    assert fonte.copyright_policy == "summary_only"
    assert len(fonte.excerpt) <= MAX_PROFESSIONAL_EXCERPT_CHARS


def test_confidence_low_senza_fonti():
    card = _card_base()
    assert assign_confidence(card) == "LOW"


def test_confidence_medium_con_fonti_ma_review_pendente():
    card = _card_base(
        sources=[{"source_type": "official", "title": "Normattiva", "url": "https://www.normattiva.it"}],
    )
    assert assign_confidence(card) == "MEDIUM"


def test_confidence_high_solo_con_fonti_template_e_review():
    card = _card_base(
        status="approved",
        sources=[{"source_type": "official", "title": "Normattiva", "url": "https://www.normattiva.it"}],
        template_selected={"template_id": "TPL1", "titolo": "Ricorso monitorio"},
        review_avvocato={"reviewer": "Avv. Verdi", "reviewed_at": "2026-06-12", "reason": "", "esito": "approved"},
    )
    assert assign_confidence(card) == "HIGH"
    # Senza template niente HIGH anche se approvata.
    card.template_selected = {}
    assert assign_confidence(card) == "MEDIUM"


def test_confidence_mai_high_con_gap_bloccanti():
    card = _card_base(
        status="approved",
        sources=[{"source_type": "official", "title": "Normattiva"}],
        template_selected={"template_id": "TPL1"},
        review_avvocato={"reviewer": "Avv. Verdi"},
        gap_evidenza=[{"codice_gap": "x", "descrizione": "gap", "severita": "blocking"}],
    )
    assert assign_confidence(card) == "LOW"


def test_card_roundtrip_e_summary():
    card = _card_base(citations=[{"riferimento": "art. 633 c.p.c.", "url": "https://www.normattiva.it"}])
    ricostruita = ProcedureCompletionCard.from_dict(card.to_dict())
    assert ricostruita.codice == "010003"
    assert ricostruita.citazioni_verificabili
    riassunto = card_summary(ricostruita)
    assert riassunto["codice"] == "010003"
    assert riassunto["status"] == "draft"
    assert riassunto["confidence"] in {"LOW", "MEDIUM", "HIGH"}
