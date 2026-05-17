from __future__ import annotations

from pathlib import Path


MATRIX = Path("docs/LEX_STUDIO_LLM_DOMAIN_MATRIX.md")


def _matrix_text() -> str:
    return MATRIX.read_text(encoding="utf-8")


def test_matrice_lex_sito_studio_definisce_sorgenti_tenant_aware() -> None:
    text = _matrix_text()

    assert "## Sito Studio, contatti, prenotazioni e contenuti pubblici" in text
    assert "web.services.studio_site_runtime" in text
    assert "web.services.react_sito_studio_bridge" in text
    assert "SITE_STUDIO_DB" in text
    assert "SITE_STUDIO_ASSETS_DIR" in text
    assert "site_contact_submission" in text
    assert "site_booking_request" in text
    assert "site_assets/<public_slug>/" in text
    assert "fallire chiuso" in text


def test_matrice_lex_sito_studio_copre_campi_ammessi_ed_esclusi() -> None:
    text = _matrix_text()

    for expected in (
        "Stato pubblicazione",
        "Contenuti pubblici",
        "Bozze redazionali",
        "Richieste contatto",
        "Prenotazioni",
        "Asset pubblici",
        "Privacy e SEO",
        "token",
        "credenziali DNS",
        "Asset binari originali",
        "Servizi, sedi, professionisti",
    ):
        assert expected in text


def test_matrice_lex_sito_studio_governa_qa_azioni_e_divieti() -> None:
    text = _matrix_text()

    for expected in (
        "pending_human_review",
        "training automatico",
        "riepilogo richieste",
        "bozze non pubblicate",
        "lacune privacy",
        "pubblicare pagine",
        "modifica di DNS",
        "risposta automatica a richieste contatto",
        "invenzione di servizi, sedi, professionisti",
        "Lex può:",
        "Lex non può:",
    ):
        assert expected in text


def test_matrice_lex_sito_studio_contiene_test_accettazione_minimi() -> None:
    text = _matrix_text()

    for expected in (
        "pagina pubblicata",
        "bozza non pubblicata",
        "richiesta contatto",
        "prenotazione in attesa",
        "asset pubblico con hash",
        "tentativo senza tenant valido",
        "non crea eventi agenda",
    ):
        assert expected in text
