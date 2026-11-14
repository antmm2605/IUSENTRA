from pathlib import Path

from legal_intelligence.engine import LegalIntelligenceDailyEngine
from legal_intelligence.fetcher import FetchResult
from legal_intelligence.jobs.daily_sync import main as daily_sync_main
from legal_intelligence.sources import LegalSource
from tests.test_applicazioni import _cfg_web, _crea_operatore, _login
from web.app import create_app


def _source(source_id: str = "fonte_test", *, apply_mode: str = "manual") -> LegalSource:
    return LegalSource(
        id=source_id,
        name=f"Fonte {source_id}",
        url=f"https://example.test/{source_id}",
        category="test",
        apply_mode=apply_mode,
        impact_areas=("PCT", "compliance"),
    )


def _fetcher_with_payloads(payloads: dict[str, list[str]]):
    counters: dict[str, int] = {}

    def fetcher(source: LegalSource, _headers: dict[str, str]) -> FetchResult:
        index = counters.get(source.id, 0)
        counters[source.id] = index + 1
        values = payloads[source.id]
        content = values[min(index, len(values) - 1)].encode("utf-8")
        return FetchResult(
            ok=True,
            url=source.url,
            status_code=200,
            content=content,
            headers={"content-type": "text/plain", "etag": f"v{index}"},
        )

    return fetcher


def test_fonte_invariata_non_crea_update_duplicati(tmp_path: Path):
    fonte = _source()
    engine = LegalIntelligenceDailyEngine(
        tmp_path / "daily.sqlite",
        sources=[fonte],
        fetcher=_fetcher_with_payloads({fonte.id: ["contenuto invariato", "contenuto invariato"]}),
    )

    first = engine.run_daily_sync()
    second = engine.run_daily_sync()
    snapshot = engine.dashboard_snapshot()

    assert first["updates_detected"] == 0
    assert second["updates_detected"] == 0
    assert snapshot["counts"]["updates"] == 0


def test_fonte_modificata_crea_legal_update(tmp_path: Path):
    fonte = _source()
    engine = LegalIntelligenceDailyEngine(
        tmp_path / "daily.sqlite",
        sources=[fonte],
        fetcher=_fetcher_with_payloads({fonte.id: ["prima versione", "seconda versione con deposito telematico"]}),
    )

    engine.run_daily_sync()
    report = engine.run_daily_sync()
    snapshot = engine.dashboard_snapshot()

    assert report["updates_detected"] == 1
    assert snapshot["counts"]["updates"] == 1
    assert snapshot["updates"][0]["status"] == "pending_review"
    assert "compliance" in snapshot["updates"][0]["summary"].lower()


def test_auto_apply_applica_solo_fonti_tecniche_sicure(tmp_path: Path):
    auto = _source("pst_tecnico", apply_mode="auto")
    manual = _source("normativa", apply_mode="manual")
    engine = LegalIntelligenceDailyEngine(
        tmp_path / "daily.sqlite",
        sources=[auto, manual],
        fetcher=_fetcher_with_payloads(
            {
                auto.id: ["versione iniziale", "schema tecnico deposito aggiornato"],
                manual.id: ["versione iniziale", "nuova norma e termini"],
            }
        ),
    )

    engine.run_daily_sync()
    report = engine.run_daily_sync()
    snapshot = engine.dashboard_snapshot()
    statuses = {item["source_id"]: item["status"] for item in snapshot["updates"]}

    assert report["updates_detected"] == 2
    assert statuses[auto.id] == "applied"
    assert statuses[manual.id] == "pending_review"
    assert snapshot["counts"]["applied"] == 1
    assert snapshot["counts"]["pending"] == 1


def test_endpoint_react_mostra_monitor_fonti_giornaliere(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    cfg["LEGAL_INTELLIGENCE_DAILY_DB"] = str(tmp_path / "daily.sqlite")
    app = create_app(cfg)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        legacy = client.get("/legal-intelligence/?_legacy=1", follow_redirects=False)
        response = client.get("/ricerca-legale")
        payload_response = client.get("/api/v1/ui/ricerca-legale")

    assert legacy.status_code == 301
    assert legacy.headers["Location"].startswith("/ricerca-legale")
    assert response.status_code == 200
    assert 'id="root"' in response.get_data(as_text=True)
    assert payload_response.status_code == 200
    payload = payload_response.get_json()
    assert any(section["id"] == "acquisizione_fonti" for section in payload["sections"])
    assert any(metric["id"] == "fonti_monitorate" for metric in payload["metrics"])


def test_comando_daily_sync_eseguibile_con_fonte_selezionata(tmp_path: Path):
    def fetcher(source: LegalSource, _headers: dict[str, str]) -> FetchResult:
        return FetchResult(ok=True, url=source.url, status_code=200, content=b"snapshot cli", headers={})

    code = daily_sync_main(
        ["--db", str(tmp_path / "daily.sqlite"), "--source", "normattiva_opendata"],
        fetcher=fetcher,
    )

    assert code == 0
    engine = LegalIntelligenceDailyEngine(tmp_path / "daily.sqlite", fetcher=fetcher)
    assert engine.dashboard_snapshot()["last_run"]["sources_checked"] == 1


def test_job_fonti_scrive_nei_due_studi_con_una_sola_acquisizione(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from flask import Flask, g
    from pct.scheduler import start_scheduler
    from web.services import fascicoli_presidi_runtime

    studi = [SimpleNamespace(slug="studio-a"), SimpleNamespace(slug="studio-b")]
    monkeypatch.setattr(fascicoli_presidi_runtime, "_active_tenants", lambda app: studi)
    monkeypatch.setattr("pct.tenant.GestioneTenant", lambda **kw: None)

    def collega(manager, studio):
        g.data_paths = {"LEGAL_INTELLIGENCE_DAILY_DB": str(tmp_path / studio.slug / "daily.sqlite")}

    monkeypatch.setattr(fascicoli_presidi_runtime, "_attach_tenant_context", collega)
    fonte = _source()
    monkeypatch.setattr("legal_intelligence.engine.DEFAULT_LEGAL_SOURCES", [fonte])
    chiamate = []

    def acquisisci(self, source):
        chiamate.append(source.id)
        return FetchResult(True, source.url, 200, b"Testo pubblico", {"content-type": "text/plain"})

    monkeypatch.setattr("legal_intelligence.fetcher.OfficialSourceFetcher.fetch", acquisisci)
    app = Flask(__name__)
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    monkeypatch.delenv("PCT_DISABLE_SCHEDULER", raising=False)
    app.config.update(
        MULTI_TENANT=True, TENANTS_REGISTRY="test", DATA_DIR=str(tmp_path), PCT_SCHEDULER_WORKER=True,
    )
    scheduler = start_scheduler(app)
    try:
        from pct.scheduler_notturno.guardia import esegui_manualmente

        result = esegui_manualmente(scheduler.get_job("legal_sources_daily_check").func, [], {})
    finally:
        scheduler.shutdown(wait=False)

    assert result["totals"]["studi"] == 2
    assert chiamate == [fonte.id]
    for studio in studi:
        db = tmp_path / studio.slug / "daily.sqlite"
        assert db.is_file()
        assert LegalIntelligenceDailyEngine(db, sources=[fonte]).dashboard_snapshot()["last_run"]
