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


def test_endpoint_dashboard_mostra_motore_giornaliero(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    cfg["LEGAL_INTELLIGENCE_DAILY_DB"] = str(tmp_path / "daily.sqlite")
    app = create_app(cfg)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/legal-intelligence/?_legacy=1")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Motore giornaliero fonti ufficiali" in body
    assert "Esegui controllo ora" in body


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
