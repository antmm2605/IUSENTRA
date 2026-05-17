from __future__ import annotations

from pathlib import Path


MATRIX = Path("docs/LEX_STUDIO_LLM_DOMAIN_MATRIX.md")


def _matrix_text() -> str:
    return MATRIX.read_text(encoding="utf-8")


def test_matrice_lex_atti_redazione_definisce_sorgenti_tenant_aware() -> None:
    text = _matrix_text()

    assert "## Atti, template, redazione, editor e documenti prodotti" in text
    assert "pct.template_atti.GestioneTemplateAtti" in text
    assert "pct.assistente_redazionale.AssistenteRedazionale" in text
    assert "web.services.editor_ai_runtime" in text
    assert "web.services.document_intelligence_runtime" in text
    assert "TEMPLATE_ATTI_DB" in text
    assert "REDACTION_ASSISTANT_DB" in text
    assert "FASCICOLI_DB" in text
    assert "FASCICOLI_DOCS" in text
    assert "/data/tenants/<studio>/template_atti/templates.json" in text
    assert "/data/tenants/<studio>/intelligence/assistente_redazionale.json" in text
    assert "fallire chiuso" in text
    assert "./template_atti/templates.json" in text


def test_matrice_lex_atti_redazione_copre_campi_ammessi_ed_esclusi() -> None:
    text = _matrix_text()

    for expected in (
        "Classificazione atto",
        "Metadati template",
        "Testo bozza",
        "Documenti prodotti",
        "Evidenze fonte",
        "Audit editor",
        "draft_in_review",
        "chain-of-thought",
        "prompt raw",
        "PDF firmati",
        "Fonti normative",
        "path assoluti",
    ):
        assert expected in text


def test_matrice_lex_atti_redazione_governa_qa_permessi_e_privacy() -> None:
    text = _matrix_text()

    for expected in (
        "pending_human_review",
        "documenti.leggi",
        "documenti.scrivi",
        "fascicoli.leggi",
        "clienti.leggi",
        "messaggi.leggi",
        "agenda.leggi",
        "template, bozze e documenti",
        "classificazione privacy",
        "registrano contenuto integrale non necessario",
        "fatti del fascicolo, testo del template",
    ):
        assert expected in text


def test_matrice_lex_atti_redazione_limita_azioni_consentite_e_divieti() -> None:
    text = _matrix_text()

    for expected in (
        "selezionare o suggerire template",
        "preparare una bozza in revisione",
        "proporre modifiche puntuali all'editor",
        "costruire checklist fonti",
        "non sovrascrive",
        "firmare digitalmente",
        "depositare telematicamente",
        "inviare via PEC",
        "un atto definitivo",
        "inventare fonti",
        "addestrare automaticamente",
    ):
        assert expected in text


def test_matrice_lex_atti_redazione_contiene_test_accettazione_minimi() -> None:
    text = _matrix_text()

    for expected in (
        "un template atti",
        "una bozza redazionale",
        "modifica editor",
        "un documento prodotto con hash",
        "una checklist fonti",
        "tentativo senza tenant valido",
        "esportate come training pronto",
    ):
        assert expected in text
