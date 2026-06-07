from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from pct.scadenziario import PrioritaTermine, TipoTermine
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.helpers import get_scadenziario
from web.services.react_scadenziario_bridge import dedupe_calculator_templates


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "react-test-key"
    return app


def test_react_scadenziario_page_collegata_nav_api_e_lex():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/ScadenziarioPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/scadenziarioData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/ScadenziarioPage.css").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")

    assert "/scadenziario" in app_source
    assert "isScadenziarioPage?<ScadenziarioPage/>" in app_source
    assert "Scadenziario Legale" in page_source
    assert "Calcolatore termini processuali" in page_source
    assert "calculateProcessDeadline" in page_source
    assert "createProcessDeadline" in page_source
    assert "Hash audit" in page_source
    assert "formatItalianDate(result.deadline)" in page_source
    assert "formatItalianDate(step.date)" in page_source
    assert "Il risultato mostrerà la data" in page_source
    assert "mostrera" not in page_source
    assert "OperativeCards" in page_source
    assert "Completa selezionate" in page_source
    assert "Elimina selezionate" in page_source
    assert "Elimina tutto" in page_source
    assert "RemoteHearingNotice" in page_source
    assert "Apri link udienza audiovisiva" in page_source
    assert "Allegato fonte:" in page_source
    assert "Link verificato identico alla fonte letta" in page_source
    assert "Evento:" in page_source
    assert "Ufficio:" in page_source
    assert "removePdfCandidates" in page_source
    assert "Anteprima PDF svuotata" in page_source
    assert "maxDocuments: fascicoloId ? 0 : 25" in page_source
    assert "FloatingLex" in page_source
    assert 'context="scadenziario"' in page_source
    assert "postDeadlineAction" in page_source
    assert "getScadenziarioPage" in data_source
    assert "DeadlineCalculatorTemplate" in data_source
    assert "DeadlineCalculatorResult" in data_source
    assert "/api/v1/ui/scadenziario" in data_source
    assert "/api/v1/ui/scadenziario/termini/calculate" in data_source
    assert "/api/v1/ui/scadenziario/termini/crea-scadenza" in data_source
    assert '@api_v1_react.get("/scadenziario")' in api_source
    assert '@api_v1_react.post("/scadenziario/termini/calculate")' in api_source
    assert '@api_v1_react.post("/scadenziario/termini/override")' in api_source
    assert ".iu-scad-page" in css
    assert ".iu-scad-calculator" in css
    assert ".iu-scad-remote-source" in css
    assert ".iu-scad-remote-check.is-verified" in css
    assert ".iu-scad-event-line" in css
    assert ".iu-scad-pdf-danger-btn" in css
    assert ".iu-scad-pdf-row-delete" in css
    assert "@media(max-width:760px)" in css
    assert "prefers-reduced-motion" in css


def test_react_scadenziario_bridge_usa_repository_reale(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        gestione = get_scadenziario()
        scadenza = gestione.nuova(
            "Deposito memoria conclusionale",
            TipoTermine.DEPOSITO_MEMORIA,
            (date.today() + timedelta(days=2)).isoformat(),
            descrizione="Termine da fascicolo test React",
            perentorio=True,
        )
        gestione.aggiorna(scadenza.id, priorita=PrioritaTermine.CRITICA)

    response = client.get("/api/v1/ui/scadenziario", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["read_only"] is False
    assert payload["contracts"]["writes"] == "operational_routes"
    assert payload["summary"]["open"] >= 1
    assert payload["summary"]["critical"] >= 1
    assert any(item["title"] == "Deposito memoria conclusionale" for item in payload["items"])
    row = next(item for item in payload["items"] if item["title"] == "Deposito memoria conclusionale")
    assert row["priority"] == "CRITICA"
    assert row["peremptory"] is True
    assert row["completeHref"].endswith(f"/{scadenza.id}/completa")
    assert payload["actions"]["exportCsv"] == "/scadenziario/export.csv"
    assert payload["actions"]["exportPdf"] == "/scadenziario/pdf"
    assert payload["actions"]["exportIcs"] == "/scadenziario/export.ics"
    assert payload["operativeCards"]
    assert payload["calculator"]["templates"]
    assert payload["calculator"]["endpoints"]["calculate"].endswith("/termini/calculate")
    assert payload["calculator"]["scheduler"]["channel"] == "PEC"


def test_react_scadenziario_bridge_espone_link_udienza_remota(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    exact_link = (
        "https://teams.microsoft.com/dl/launcher/launcher.html?"
        "url=%2F_%23%2Fl%2Fmeetup-join%2F19%3Ameeting_TEST%40thread.v2%2F0"
        "%3Fcontext%3D%257b%2522Tid%2522%253a%252211111111-1111-1111-1111-111111111111"
        "%2522%252c%2522Oid%2522%253a%252222222222-2222-2222-2222-222222222222%2522%257d"
        "%26anon%3Dtrue&type=meetup-join&deeplinkId=33333333-3333-3333-3333-333333333333"
        "&directDl=true&msLaunch=true&enableMobilePage=true&suppressPrompt=true"
    )
    with app.app_context():
        gestione = get_scadenziario()
        scadenza = gestione.nuova(
            "Udienza da PEC: RG 1263/2026/LAV",
            TipoTermine.UDIENZA,
            (date.today() + timedelta(days=10)).isoformat(),
            descrizione="Fissazione udienza con strumenti audiovisivi",
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            note=f"PEC_AUDIT:msg-link\nLink udienza audiovisiva: {exact_link}\nFonte link udienza: 13744017s.pdf.zip\nVerifica link udienza: identico alla fonte letta.",
            remote_hearing_detected=True,
            remote_hearing_mode="audiovisiva",
            remote_hearing_url=exact_link,
            remote_hearing_source="13744017s.pdf.zip",
            remote_hearing_verified=True,
            remote_hearing_time="29/10/2026 ore 09:15",
        )

    response = client.get("/api/v1/ui/scadenziario?vista=pec", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    row = next(item for item in payload["items"] if item["id"] == scadenza.id)

    assert response.status_code == 200
    assert row["remoteHearingDetected"] is True
    assert row["remoteHearingUrl"] == exact_link
    assert row["remoteHearingSource"] == "13744017s.pdf.zip"
    assert row["remoteHearingVerified"] is True


def test_react_scadenziario_vista_pec_mostra_solo_scadenze_operative(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        gestione = get_scadenziario()
        futura = gestione.nuova(
            "Udienza da PEC operativa",
            TipoTermine.UDIENZA,
            (date.today() + timedelta(days=20)).isoformat(),
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            note="PEC_AUDIT:pec-futura",
        )
        scaduta = gestione.nuova(
            "Udienza da PEC già superata",
            TipoTermine.UDIENZA,
            (date.today() - timedelta(days=20)).isoformat(),
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            note="PEC_AUDIT:pec-scaduta",
        )

    response = client.get("/api/v1/ui/scadenziario?vista=pec", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    ids = {item["id"] for item in payload["items"]}

    assert response.status_code == 200
    assert futura.id in ids
    assert scaduta.id not in ids
    assert payload["summary"]["pec"] == 1
    assert payload["summary"]["pec_future"] == 1
    assert payload["summary"]["pec_overdue"] >= 1


def test_react_scadenziario_calcolatore_non_ripete_template_identici():
    base = {
        "name": "Reclamo contro provvedimento cautelare",
        "matter_type": "civil",
        "base_value": 15,
        "period_type": "days",
        "direction": "forward",
        "suspend_august": True,
        "ferial_suspension_policy": "applies",
        "free_term": False,
        "urgent": False,
        "extend_saturday": True,
        "extend_holiday": True,
        "reference_law": "c.p.c. art. 669-terdecies",
        "cartabia_compliant": True,
        "metadata": {
            "source": "guida_pratica",
            "decorrenza": "Dalla comunicazione o notificazione del provvedimento",
            "natura": "termine di reclamo",
        },
        "version": 1,
    }
    templates = [
        {"code": "GP_A", **base, "metadata": {**base["metadata"], "codice_guida": "190010"}},
        {"code": "GP_B", **base, "metadata": {**base["metadata"], "codice_guida": "190020"}},
        {"code": "GP_C", **base, "base_value": 30},
    ]

    visible = dedupe_calculator_templates(templates)

    assert [template["code"] for template in visible] == ["GP_A", "GP_C"]
    assert len({template["displayName"] for template in visible}) == 2


def test_route_ufficiale_scadenziario_serve_react_con_vista_classica_tecnica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/scadenziario")
        classic = client.get("/scadenziario?_legacy=1")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in html
    assert 'id="root"' in html
    assert classic.status_code == 200
    assert 'id="root"' not in classic.get_data(as_text=True)
