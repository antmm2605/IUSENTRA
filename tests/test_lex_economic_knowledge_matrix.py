from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STUDIO_MATRIX = ROOT / "docs" / "LEX_STUDIO_LLM_DOMAIN_MATRIX.md"
SOFTWARE_MATRIX = ROOT / "docs" / "lex_software_domain_dataset_matrix.json"


def _studio_text() -> str:
    return STUDIO_MATRIX.read_text(encoding="utf-8")


def _economic_domain() -> dict:
    matrix = json.loads(SOFTWARE_MATRIX.read_text(encoding="utf-8"))
    return next(domain for domain in matrix["domains"] if domain["id"] == "pagamenti_fatturazione")


def test_matrice_lex_economica_definisce_sorgenti_tenant_aware_e_fail_closed() -> None:
    text = _studio_text()

    assert "## Pagamenti, fatturazione, preventivi, compensi e timesheet" in text
    assert "FATTURAZIONE_DB" in text
    assert "PREVENTIVI_DB" in text
    assert "TIMESHEET_DB" in text
    assert "PAGAMENTI_DIR" in text
    assert "/data/tenants/<studio>/fatturazione/parcelle.json" in text
    assert "/data/tenants/<studio>/preventivi/" in text
    assert "/data/tenants/<studio>/timesheet/entries.json" in text
    assert "fallire chiuso" in text
    assert "./fatturazione/parcelle.json" in text
    assert "./preventivi/preventivi.json" in text


def test_matrice_lex_economica_copre_campi_ammessi_esclusioni_e_privacy() -> None:
    text = _studio_text()

    for expected in (
        "Importi economici",
        "Coerenza economica",
        "Pagamenti",
        "amount_summary",
        "Chiavi SumUp, Stripe, PagoPA, SDI",
        "webhook secret",
        "URL privati di pagamento",
        "path assoluti",
        "Importi ipotetici",
        "privacy_classification",
    ):
        assert expected in text


def test_matrice_lex_economica_governa_qa_e_azioni_read_only() -> None:
    text = _studio_text()

    for expected in (
        "pending_human_review",
        "Riepiloga saldo",
        "attività validate a timesheet",
        "coerenza tra preventivo, conferimento, parcella e timesheet",
        "bozza di descrizione parcella",
        "Lex può:",
        "Lex non può:",
        "emettere fatture",
        "creare link pagamento",
        "registrare incassi",
        "modifica di importi",
        "addestrare automaticamente",
    ):
        assert expected in text


def test_matrice_software_economica_allinea_fonti_permessi_e_divieti() -> None:
    domain = _economic_domain()
    payload = json.dumps(domain, ensure_ascii=False)

    for expected in (
        "GestioneFatturazione",
        "GestionePreventivi",
        "GestioneTimesheet",
        "GestionePagamenti",
        "FATTURAZIONE_DB",
        "PREVENTIVI_DB",
        "TIMESHEET_DB",
        "PAGAMENTI_DIR",
        "fatturazione.leggi",
        "pagamenti.leggi",
        "riepilogo saldo cliente",
        "controllo coerenza preventivo-conferimento-parcella-timesheet",
        "bozza descrizione parcella senza emissione",
        "creare link pagamento o avviare checkout",
        "registrare incassi, storni, rimborsi o riconciliazioni",
        "modificare importi",
        "pending_human_review",
    ):
        assert expected in payload


def test_matrice_software_economica_non_autorizza_training_o_azioni_dispositive() -> None:
    domain = _economic_domain()
    forbidden = " ".join(domain["lex_forbidden_actions"]).lower()
    allowed = " ".join(domain["lex_allowed_actions"]).lower()

    assert "addestrare automaticamente" in forbidden
    assert "usare dati economici di un altro tenant" in forbidden
    assert "emettere fatture" in forbidden
    assert "creare link pagamento" in forbidden
    assert "registrare incassi" in forbidden
    assert "modificare importi" in forbidden
    assert "read-only" in allowed
    assert "senza emissione" in allowed
