from __future__ import annotations

from datetime import date
from pathlib import Path

from pct.termini_processuali import (
    DeadlinePracticeRepository,
    ItalianDeadlineCalculator,
    calculate_and_audit,
    canonical_sha256,
    holidays_from_csv,
)
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "termini-test-key"
    return app


def test_termine_forward_proroga_sabato_senza_sospensione():
    calc = ItalianDeadlineCalculator()

    result = calc.calculate(date(2026, 7, 30), 30, "forward")

    assert result["rawDeadline"] == "2026-08-29"
    assert result["deadline"] == "2026-08-31"
    assert "saturday_extension_out_of_hearing" in result["rulesApplied"]
    assert result["requiresLegalReview"] is False


def test_sospensione_feriale_salta_agosto_con_regola_versionata():
    calc = ItalianDeadlineCalculator()

    result = calc.calculate(
        date(2026, 7, 15),
        20,
        "forward",
        suspend_august=True,
        ferial_suspension_policy="applies",
    )

    assert result["deadline"] == "2026-09-04"
    assert "ferial_suspension_1_31_august" in result["rulesApplied"]
    assert result["rulesetVersion"]
    assert result["calendarVersion"]


def test_calcolo_a_ritroso_e_termine_libero_richiedono_review():
    calc = ItalianDeadlineCalculator()

    result = calc.calculate(
        date(2026, 10, 15),
        15,
        "backward",
        free_term=True,
    )

    assert result["deadline"] == "2026-09-29"
    assert result["requiresLegalReview"] is True
    assert "free_term" in result["rulesApplied"]


def test_calcolo_mesi_usa_ultimo_giorno_se_mese_corto():
    calc = ItalianDeadlineCalculator()

    result = calc.calculate_months(date(2026, 1, 31), 1)

    assert result == date(2026, 2, 28)


def test_audit_hash_sha256_canonico_e_repository_sqlite(tmp_path: Path):
    repo = DeadlinePracticeRepository.sqlite(tmp_path / "termini.db")

    result = calculate_and_audit(
        {
            "template_code": "CIV_OPPOSIZIONE_DI",
            "input_date": "2026-01-10",
            "case_reference": "RG 10/2026",
        },
        repository=repo,
        user_id="utente-test",
    )
    rows = repo.list_audit()

    assert result["audit"]["immutableHash"]
    assert len(result["audit"]["immutableHash"]) == 64
    assert rows[0]["immutable_hash"] == result["audit"]["immutableHash"]
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_import_calendario_ufficiale_csv_versionato(tmp_path: Path):
    csv_path = tmp_path / "istat_2026.csv"
    csv_path.write_text(
        "date,description,type\n2026-01-01,Capodanno,national\n2026-06-02,Festa della Repubblica,national\n",
        encoding="utf-8",
    )
    repo = DeadlinePracticeRepository.json(tmp_path / "termini.json")

    summary = repo.import_holidays(
        holidays_from_csv(csv_path),
        source_year=2026,
        source="CSV ISTAT verificato",
        source_url="https://www.istat.it/",
        checksum_sha256="abc123",
        calendar_version="IT-FESTIVITA-2026.TEST",
    )

    payload = repo._read_json()
    assert summary["imported"] == 2
    assert any(row["version"] == "IT-FESTIVITA-2026.TEST" for row in payload["calendar_versions"])
    assert payload["official_holidays"][0]["day"] == "2026-01-01"


def test_api_scadenziario_calcolatore_calcola_e_crea_scadenza(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/api/v1/ui/scadenziario/termini/calculate",
            json={
                "template_code": "CIV_APPELLO_BREVE",
                "input_date": "2026-07-30",
                "case_reference": "RG API/2026",
                "suspend_august": False,
            },
        )
        create = client.post(
            "/api/v1/ui/scadenziario/termini/crea-scadenza",
            json={
                "template_code": "CIV_APPELLO_BREVE",
                "input_date": "2026-07-30",
                "case_reference": "RG API/2026",
                "title": "Appello breve auditato",
                "suspend_august": False,
            },
        )

    payload = response.get_json()
    created = create.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["result"]["audit"]["immutableHash"]
    assert create.status_code == 200
    assert created["ok"] is True
    assert created["notificationsPlanned"] == 5
    assert created["href"].startswith("/scadenziario/")
