"""Regole fail-closed del validatore."""
from __future__ import annotations

from pct.procedure_completion.models import ProcedureCompletionCard
from pct.procedure_completion.validator import validate_card


def _card(**extra) -> ProcedureCompletionCard:
    dati = {
        "codice": "010003",
        "denominazione": "Procedura di test",
        "sources": [{"source_type": "official", "title": "Normattiva", "url": "https://www.normattiva.it"}],
        "citations": [{"riferimento": "art. 633 c.p.c.", "url": "https://www.normattiva.it", "versione": "2026-06-06"}],
    }
    dati.update(extra)
    return ProcedureCompletionCard.from_dict(dati)


def test_card_senza_fonte_ufficiale_non_approvabile():
    report = validate_card(_card(sources=[]))
    assert report.approvable is False
    assert any("fonte" in errore.lower() for errore in report.errors)


def test_card_senza_citazioni_non_pubblicabile():
    report = validate_card(_card(citations=[]))
    assert report.approvable is False
    assert report.publishable is False


def test_termine_processuale_senza_base_normativa_blocca():
    report = validate_card(_card(termini_processuali=[{"termine": "40 giorni per opposizione", "base_normativa": "", "fonte_id": ""}]))
    assert report.valid is False
    assert any("termine" in msg.lower() for msg in report.blocking_errors)


def test_termine_con_base_normativa_non_blocca():
    report = validate_card(
        _card(termini_processuali=[{"termine": "40 giorni per opposizione", "base_normativa": "art. 641 c.p.c.", "fonte_id": "src1"}])
    )
    assert not any("termine" in msg.lower() for msg in report.blocking_errors)


def test_adempimento_fiscale_senza_fonte_produce_warning():
    report = validate_card(_card(adempimenti_fiscali=[{"adempimento": "Contributo unificato", "fonte": ""}]))
    assert any("fiscale" in msg.lower() for msg in report.warnings)


def test_citazione_senza_fonte_blocca():
    report = validate_card(_card(citations=[{"riferimento": "art. 1 c.c.", "url": "", "source_id": ""}]))
    assert any("citazione senza fonte" in msg.lower() for msg in report.blocking_errors)


def test_dati_personali_in_fonte_interna_richiede_privacy_review():
    report = validate_card(
        _card(
            sources=[
                {"source_type": "official", "title": "Normattiva", "url": "https://x"},
                {"source_type": "internal", "title": "Prassi studio", "excerpt": "Cliente RSSMRA70B10G288K, mario@example.com"},
            ]
        )
    )
    assert report.privacy_review_required is True


def test_fonte_professionale_non_summary_only_blocca():
    report = validate_card(
        _card(
            sources=[
                {"source_type": "official", "title": "Normattiva", "url": "https://x"},
                {"source_type": "professional", "title": "Rivista", "copyright_policy": "full_text"},
            ]
        )
    )
    assert any("summary_only" in msg for msg in report.blocking_errors)


def test_template_mancante_resta_needs_review_non_bloccante():
    report = validate_card(_card(template_selected={}))
    assert any("template" in msg.lower() for msg in report.warnings)
    assert report.approvable is True, "template mancante non blocca l'approvazione, ma resta tracciato"


def test_publishable_richiede_review_avvocato():
    card = _card(status="approved")
    report = validate_card(card)
    assert report.publishable is False
    card.review_avvocato = {"reviewer": "Avv. Verdi", "reviewed_at": "2026-06-12", "reason": "", "esito": "approved"}
    report2 = validate_card(card)
    assert report2.publishable is True
