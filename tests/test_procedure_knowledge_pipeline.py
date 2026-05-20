from __future__ import annotations

import pytest

from pct.procedure_knowledge_pipeline import (
    REQUIRED_CARD_SECTIONS,
    add_source_evidence,
    approve_knowledge_card,
    build_original_knowledge_card,
    publish_knowledge_card,
    save_knowledge_card,
    submit_knowledge_card_for_review,
    validate_source_evidence,
)
from pct.procedure_knowledge_cards import build_original_knowledge_card as facade_build_card
from pct.procedure_source_evidence import validate_source_evidence as facade_validate_source
from tests.procedure_pipeline_support import make_repo


def test_source_evidence_policy_anti_copia_e_privacy(tmp_path):
    repo = make_repo(tmp_path)

    with pytest.raises(ValueError):
        add_source_evidence(
            repo,
            procedure_code="PROC",
            source_type="professional",
            source_title="Rivista",
            evidence_kind="commento",
        )

    report = validate_source_evidence(
        {
            "procedure_code": "PROC",
            "source_type": "professional",
            "source_title": "Altalex",
            "evidence_kind": "commento",
            "extracted_principle": "Principio riformulato.",
            "original_quote_short": "x" * 501,
        }
    )
    assert report.errors

    official_id = add_source_evidence(
        repo,
        procedure_code="PROC",
        xsd_code="010001",
        source_type="official",
        source_url="https://pst.giustizia.it/PST/it/download.page",
        source_title="PST",
        last_checked_at="2026-05-20",
        evidence_kind="catalogo",
        review_status="validated",
    )
    assert official_id > 0

    internal = validate_source_evidence(
        {
            "procedure_code": "PROC",
            "source_type": "internal",
            "source_title": "atto mario.rossi@example.test",
            "evidence_kind": "checklist",
        }
    )
    assert internal.privacy_review_required is True
    iban = validate_source_evidence(
        {
            "procedure_code": "PROC",
            "source_type": "internal",
            "source_title": "checklist IT60X0542811101000000123456",
            "evidence_kind": "checklist",
        }
    )
    assert iban.privacy_review_required is True
    assert facade_validate_source({"procedure_code": "PROC", "source_type": "official", "source_url": "https://pst.giustizia.it", "evidence_kind": "catalogo"}).warnings


def test_knowledge_card_originale_review_e_publish_bloccanti(tmp_path):
    repo = make_repo(tmp_path)
    source_id = add_source_evidence(
        repo,
        procedure_code="PROC",
        xsd_code="010001",
        source_type="official",
        source_url="https://pst.giustizia.it/PST/it/download.page",
        source_title="PST",
        last_checked_at="2026-05-20",
        evidence_kind="catalogo",
        review_status="validated",
    )
    sources = repo.list_source_evidence("PROC", "010001")
    card_json = build_original_knowledge_card("PROC", "010001", sources)
    assert "nota_originalita" in card_json
    assert "fonti_consultate" in card_json
    assert {"condizioni_procedibilita", "deposito_prova", "review_avvocato"} <= set(REQUIRED_CARD_SECTIONS)
    assert facade_build_card("PROC", "010001", sources)["review_avvocato"]["required"] is True

    card_id = save_knowledge_card(
        repo,
        procedure_code="PROC",
        xsd_code="010001",
        title="Scheda originale",
        sources=[{**sources[0], "id": source_id}],
    )
    submit_knowledge_card_for_review(repo, card_id, "Verifica avvocato")
    with pytest.raises(ValueError):
        approve_knowledge_card(repo, card_id, "")

    approve_knowledge_card(repo, card_id, "Avv. Verificatore")
    publish_knowledge_card(repo, card_id)
    assert repo.get_knowledge_card(card_id)["status"] == "published"
    assert repo.list_audit_log("procedure_knowledge_cards")


def test_knowledge_card_senza_fonte_ufficiale_non_pubblicabile(tmp_path):
    repo = make_repo(tmp_path)
    professional_id = add_source_evidence(
        repo,
        procedure_code="PROC",
        source_type="professional",
        source_title="Studio professionale",
        evidence_kind="commento",
        extracted_principle="Principio riformulato senza copia.",
    )
    sources = repo.list_source_evidence("PROC")
    card_id = save_knowledge_card(
        repo,
        procedure_code="PROC",
        xsd_code=None,
        title="Scheda incompleta",
        sources=[{**sources[0], "id": professional_id}],
    )
    with pytest.raises(ValueError):
        approve_knowledge_card(repo, card_id, "Avv. Reviewer")
