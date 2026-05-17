from __future__ import annotations

from pathlib import Path


MATRIX = Path("docs/LEX_STUDIO_LLM_DOMAIN_MATRIX.md")


def _matrix_text() -> str:
    return MATRIX.read_text(encoding="utf-8")


def test_matrice_lex_agenda_scadenze_definisce_sorgenti_tenant_aware() -> None:
    text = _matrix_text()

    assert "## Agenda, calendario, scadenze e termini" in text
    assert "pct.agenda.Agenda" in text
    assert "pct.scadenziario.GestioneScadenziario" in text
    assert "AGENDA_DB" in text
    assert "SCADENZIARIO_DB" in text
    assert "CALENDAR_SYNC_DB" in text
    assert "/data/tenants/<studio>/agenda/appuntamenti.json" in text
    assert "/data/tenants/<studio>/scadenziario/scadenze.json" in text
    assert "fallire chiuso" in text
    assert "./agenda/appuntamenti.json" in text
    assert "./scadenziario/scadenze.json" in text


def test_matrice_lex_agenda_scadenze_copre_campi_utili_ed_esclusioni() -> None:
    text = _matrix_text()

    for expected in (
        "data_ora",
        "durata_minuti",
        "legal_due_at",
        "operational_due_at",
        "deadline_profile_code",
        "source_event_type",
        "trace_json",
        "external_provider",
        "external_uid",
        "token OAuth",
        "refresh token",
        "path assoluti",
        "Scadenze o udienze ipotetiche non presenti",
    ):
        assert expected in text


def test_matrice_lex_agenda_scadenze_governa_qa_permessi_privacy_e_azioni() -> None:
    text = _matrix_text()

    for expected in (
        "pending_human_review",
        "agenda.leggi",
        "scadenziario.leggi",
        "scadenze.leggi",
        "fascicoli.leggi",
        "messaggi.leggi",
        "brief della giornata",
        "termini urgenti",
        "preparazione udienza",
        "prossima azione",
        "conflitti calendario",
        "non crea né modifica scadenze",
        "addestrare automaticamente",
    ):
        assert expected in text


def test_matrice_lex_agenda_scadenze_contiene_test_accettazione_minimi() -> None:
    text = _matrix_text()

    for expected in (
        "appuntamento udienza",
        "scadenza perentoria",
        "operational_due_at",
        "profilo calendario sync senza segreti",
        "tentativo senza tenant valido",
        "fatti certi, calcoli derivati e lacune",
    ):
        assert expected in text
