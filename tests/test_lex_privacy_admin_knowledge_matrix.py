from __future__ import annotations

from pathlib import Path


MATRIX = Path("docs/LEX_STUDIO_LLM_DOMAIN_MATRIX.md")


def _matrix_text() -> str:
    return MATRIX.read_text(encoding="utf-8")


def test_matrice_lex_privacy_admin_definisce_sorgenti_tenant_aware() -> None:
    text = _matrix_text()

    assert "## Privacy, GDPR, audit e amministrazione" in text
    assert "pct.auth.GestioneUtenti" in text
    assert "AUTH_DB" in text
    assert "AUDIT_DB" in text
    assert "PRIVACY_DB" in text
    assert "STUDIO_DB" in text
    assert "/data/tenants/<studio>/auth/utenti.json" in text
    assert "/data/tenants/<studio>/auth/audit.json" in text
    assert "fallire chiuso" in text
    assert "./auth/utenti.json" in text
    assert "./auth/audit.json" in text


def test_matrice_lex_privacy_admin_copre_permessi_e_campi_rag() -> None:
    text = _matrix_text()

    for expected in (
        "utenti.leggi",
        "audit.leggi",
        "database.leggi",
        "permessi_effettivi()",
        "permessi_extra",
        "permessi_negati",
        "Registro trattamenti",
        "Diritti interessato",
        "Stato database",
        "tenant_id",
        "required_permissions",
        "privacy_classification",
    ):
        assert expected in text


def test_matrice_lex_privacy_admin_esclude_segreti_e_payload_tecnici() -> None:
    text = _matrix_text()

    for expected in (
        "Hash password",
        "password temporanee",
        "token TOTP",
        "recovery code",
        "credenziali database",
        "DSN completi",
        "access key S3/MinIO",
        "webhook secret",
        "path assoluti",
        "dump SQL",
        "backup binari",
        "payload tecnici",
    ):
        assert expected in text


def test_matrice_lex_privacy_admin_governa_qa_e_azioni_read_only() -> None:
    text = _matrix_text()

    for expected in (
        "pending_human_review",
        "training automatico",
        "riepilogo lacune",
        "controllo registro",
        "spiegazione audit",
        "checklist non distruttiva",
        "creare utenti",
        "cambiare ruoli",
        "cancellazione audit",
        "restore",
        "migrazione automatica",
        "invio esterno",
    ):
        assert expected in text


def test_matrice_lex_privacy_admin_contiene_test_accettazione_minimi() -> None:
    text = _matrix_text()

    for expected in (
        "registro trattamenti incompleto",
        "evento audit",
        "utente con permessi personalizzati",
        "profilo database senza segreti",
        "tentativo senza tenant valido",
        "non crea utenti",
        "non cambia ruoli",
        "non modifica permessi",
        "non cancella audit",
        "non avvia restore",
    ):
        assert expected in text
