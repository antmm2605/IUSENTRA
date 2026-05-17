from __future__ import annotations

from pathlib import Path


MATRIX = Path("docs/LEX_STUDIO_LLM_DOMAIN_MATRIX.md")


def _matrix_text() -> str:
    return MATRIX.read_text(encoding="utf-8")


def test_matrice_lex_email_definisce_sorgenti_tenant_aware_e_fail_closed() -> None:
    text = _matrix_text()

    assert "EMAIL_CASELLA_DB" in text
    assert "EMAIL_ORDINARIA_DB" in text
    assert "MESSAGGI_DB" in text
    assert "/data/tenants/<studio>/email/casella.json" in text
    assert "/data/tenants/<studio>/email/ordinaria.json" in text
    assert "fallire chiuso" in text
    assert "./email/ordinaria.json" in text
    assert "messaggi.leggi" in text


def test_matrice_lex_email_governa_allegati_compressi_e_reader_unico() -> None:
    text = _matrix_text()

    assert "archivio-allegati.zip" in text
    assert "IUSENTRA_EMAIL_ATTACHMENT_STORAGE=archive" in text
    assert "GestioneEmailRicevute.leggi_allegato()" in text
    assert "GestioneEmailRicevute.allegato_disponibile()" in text
    assert "file sciolti storici" in text
    assert "non deve esportare il contenuto binario originale" in text


def test_matrice_lex_email_separa_campi_ammessi_esclusi_e_privacy() -> None:
    text = _matrix_text()

    for expected in (
        "Mittente e destinatari",
        "Corpo testo",
        "Stato PCT/PST",
        "Correlazioni",
        "Password PEC",
        "token OAuth",
        "path assoluti",
        "HTML non sanificato",
        "highly_sensitive",
    ):
        assert expected in text


def test_matrice_lex_email_blocca_training_automatico_e_azioni_dispositive() -> None:
    text = _matrix_text()

    assert "pending_human_review" in text
    assert "training automatico" in text
    assert "invio automatico" in text
    assert "Lex può:" in text
    assert "Lex non può:" in text
    assert "cancellare, spostare, marcare come letto" in text
    assert "proporre una bozza di risposta" in text
    assert "suggerire il collegamento a un fascicolo" in text


def test_matrice_lex_email_contiene_test_accettazione_minimi() -> None:
    text = _matrix_text()

    for expected in (
        "PEC con allegato compresso",
        "email ordinaria",
        "messaggio inviato",
        "tentativo senza tenant valido",
        "nessuna azione dispositiva",
    ):
        assert expected in text
