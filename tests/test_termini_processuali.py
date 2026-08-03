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
    assert "La scadenza finale è 04/09/2026." in result["explanation"]
    assert "e'" not in result["explanation"]
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


def test_api_scadenziario_templates_bootstrap_guida_pratica_terms(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/api/v1/ui/scadenziario/termini/templates")

    payload = response.get_json()
    guida_templates = [
        item
        for item in payload["templates"]
        if item.get("metadata", {}).get("source") == "guida_pratica"
    ]
    assert response.status_code == 200
    assert payload["templatesRawCount"] >= 1000
    assert payload["templatesVisibleCount"] == len(payload["templates"])
    assert len(guida_templates) < payload["templatesRawCount"]
    assert any(item.get("metadata", {}).get("codice_guida") for item in guida_templates)
    visible_labels = [item.get("displayName") or item["name"] for item in guida_templates]
    assert len(visible_labels) == len(set(visible_labels))
    assert sum(1 for label in visible_labels if label == "Reclamo contro provvedimento cautelare") <= 1


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
        create_again = client.post(
            "/api/v1/ui/scadenziario/termini/crea-scadenza",
            json={
                "template_code": "CIV_APPELLO_BREVE",
                "input_date": "2026-07-30",
                "case_reference": "RG API/2026",
                "title": "Appello breve auditato",
                "suspend_august": False,
            },
        )
        expired = client.post(
            "/api/v1/ui/scadenziario/termini/crea-scadenza",
            json={
                "template_code": "CIV_APPELLO_BREVE",
                "input_date": "2000-01-01",
                "case_reference": "RG SCADUTO/2000",
                "title": "Termine scaduto da non importare",
                "suspend_august": False,
            },
        )
        deadline_date = response.get_json()["result"]["deadline"]
        deadlines_view = client.get("/api/v1/ui/scadenziario?vista=tutte")
        agenda_view = client.get(f"/api/v1/ui/agenda?from={deadline_date}&to={deadline_date}")

    payload = response.get_json()
    created = create.get_json()
    created_again = create_again.get_json()
    expired_payload = expired.get_json()
    deadlines_payload = deadlines_view.get_json()
    agenda_payload = agenda_view.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["result"]["audit"]["immutableHash"]
    assert create.status_code == 200
    assert created["ok"] is True
    assert created["agenda"]["ok"] is True
    assert created["agenda"]["agendaId"]
    assert created["notificationsPlanned"] == 5
    assert created["href"].startswith("/scadenziario/")
    assert create_again.status_code == 200
    assert created_again["alreadyExists"] is True
    assert created_again["agenda"]["agendaId"] == created["agenda"]["agendaId"]
    assert expired.status_code == 409
    assert expired_payload["expired"] is True
    assert expired_payload["messaggio"] == "Termine già superato: non riportato in scadenziario o agenda."

    assert deadlines_view.status_code == 200
    assert agenda_view.status_code == 200
    assert [item["title"] for item in deadlines_payload["items"]] == ["Appello breve auditato"]
    agenda_rows = [item for item in agenda_payload["events"] if item["id"] == created["agenda"]["agendaId"]]
    assert len(agenda_rows) == 1
    assert agenda_rows[0]["kind"] == "SCADENZA"
    assert agenda_rows[0]["title"] == "Appello breve auditato"


def test_api_scadenziario_blocca_fascicolo_di_altro_tenant(tmp_path: Path):
    from pct.fascicoli import GestioneFascicoli, TipoFascicolo
    from pct.tenant import GestioneTenant
    from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg_web(tmp_path), "MULTI_TENANT": True})
    manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio_a = manager.crea("Studio A", "studio-a")
    studio_b = manager.crea("Studio B", "studio-b")
    manager.aggiorna(studio_a.slug, api_key="studio-a-key")
    manager.aggiorna(studio_b.slug, api_key="studio-b-key")
    bootstrap_legacy_tenant_runtime_data(app, tenant_slug=studio_a.slug)
    bootstrap_legacy_tenant_runtime_data(app, tenant_slug=studio_b.slug)
    paths_a = manager.percorsi_dati(studio_a.slug, reconcile_aliases=False)
    paths_b = manager.percorsi_dati(studio_b.slug, reconcile_aliases=False)
    fascicoli_b = GestioneFascicoli(paths_b["FASCICOLI_DB"], documents_dir=paths_b["FASCICOLI_DOCS"])
    fascicolo_b = fascicoli_b.nuovo("Ricorso Studio B", TipoFascicolo.CIVILE, nome_cliente="Cliente B")

    headers_a = {"X-API-Key": "studio-a-key", "X-Tenant-Slug": studio_a.slug}
    headers_b = {"X-API-Key": "studio-b-key", "X-Tenant-Slug": studio_b.slug}
    payload = {
        "template_code": "CIV_APPELLO_BREVE",
        "input_date": "2030-07-30",
        "case_reference": "RG TENANT/2030",
        "title": "Scadenza isolamento tenant",
        "suspend_august": False,
        "id_fascicolo": fascicolo_b.id,
    }

    with app.test_client() as client:
        blocked = client.post("/api/v1/ui/scadenziario/termini/crea-scadenza", json=payload, headers=headers_a)
        scadenziario_a = client.get("/api/v1/ui/scadenziario?vista=tutte", headers=headers_a)
        agenda_a = client.get("/api/v1/ui/agenda?from=2030-07-30&to=2030-09-15", headers=headers_a)
        created = client.post("/api/v1/ui/scadenziario/termini/crea-scadenza", json=payload, headers=headers_b)
        scadenziario_b = client.get("/api/v1/ui/scadenziario?vista=tutte", headers=headers_b)
        agenda_b = client.get("/api/v1/ui/agenda?from=2030-07-30&to=2030-09-15", headers=headers_b)

    assert blocked.status_code == 404
    blocked_payload = blocked.get_json()
    assert blocked_payload["crossTenantBlocked"] is True
    assert blocked_payload["messaggio"] == "Fascicolo non trovato nello studio corrente."
    assert scadenziario_a.status_code == 200
    assert agenda_a.status_code == 200
    assert not any(item.get("fascicoloId") == fascicolo_b.id for item in scadenziario_a.get_json()["items"])
    assert not any(item.get("matter") == fascicolo_b.id for item in agenda_a.get_json()["events"])

    assert created.status_code == 200
    created_payload = created.get_json()
    assert created_payload["ok"] is True
    assert scadenziario_b.status_code == 200
    assert agenda_b.status_code == 200
    scadenze_b = [
        item
        for item in scadenziario_b.get_json()["items"]
        if item.get("title") == "Scadenza isolamento tenant"
    ]
    assert len(scadenze_b) == 1
    assert scadenze_b[0]["fascicoloId"] == fascicolo_b.id
    eventi_b = [
        item
        for item in agenda_b.get_json()["events"]
        if item.get("matter") == fascicolo_b.id and item.get("source") == "agenda"
    ]
    assert len(eventi_b) == 1


def test_termine_lungo_sospeso_nel_periodo_feriale():
    """Art. 1 L. 742/1969: la sospensione vale anche per il termine lungo.

    Il modello nasceva con la sospensione disattivata: sei mesi dal 10 marzo
    scadevano il 10 settembre, senza i 31 giorni di agosto.
    """

    from pct.termini_processuali import DEFAULT_TEMPLATES

    template = next(voce for voce in DEFAULT_TEMPLATES if voce.code == "CIV_APPELLO_LUNGO")
    assert template.suspend_august is True
    assert template.version >= 2

    result = ItalianDeadlineCalculator().calculate_template(date(2026, 3, 10), template)

    assert "ferial_suspension_1_31_august" in result["rulesApplied"]
    assert result["deadline"] > "2026-09-10"


def test_modelli_salvati_si_aggiornano_solo_se_la_regola_e_cambiata(tmp_path):
    """L'upgrade tocca i modelli con version superiore, non le personalizzazioni."""

    import json

    percorso = tmp_path / "termini.json"
    percorso.write_text(
        json.dumps(
            {
                "templates": [
                    # Modello con la vecchia regola: va corretto.
                    {
                        "code": "CIV_APPELLO_LUNGO",
                        "name": "Appello civile - termine lungo",
                        "base_value": 6,
                        "period_type": "months",
                        "suspend_august": False,
                        "reference_law": "Art. 327 c.p.c.",
                        "version": 1,
                    },
                    # Personalizzazione dello studio su un modello non corretto:
                    # deve restare intatta.
                    {
                        "code": "CIV_APPELLO_BREVE",
                        "name": "Appello - prassi di studio",
                        "base_value": 25,
                        "version": 1,
                    },
                ],
                "audit_logs": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    repo = DeadlinePracticeRepository(percorso)

    lungo = repo.get_template("CIV_APPELLO_LUNGO")
    breve = repo.get_template("CIV_APPELLO_BREVE")

    assert lungo.suspend_august is True
    assert lungo.version >= 2
    assert breve.name == "Appello - prassi di studio"
    assert breve.base_value == 25
