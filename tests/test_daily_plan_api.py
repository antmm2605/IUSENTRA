"""Test API /api/v1/ui/daily-plan* (lettura snapshot, ETag, azioni, refresh)."""

from datetime import datetime
from pathlib import Path

from pct.daily_plan.clock import Clock
from pct.daily_plan.models import DailyWorkItem, SignalEvidence
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.daily_plan_runtime import repository_from_paths

CLOCK = Clock(fixed_now=datetime(2026, 7, 11, 9, 0))
DATE = "2026-07-11"
HEADERS = {"X-API-Key": "daily-plan-test-key"}


def _app(tmp_path: Path, *, enabled: bool = True, write_proposals: bool = False):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg["FEATURE_FLAGS"] = {
        "lex.dailyPlan.enabled": enabled,
        "lex.dailyPlan.writeProposals": write_proposals,
        "lex.workflowAgents.enabled": True,
        "routes.appV2.dailyPlan.home": True,
    }
    app = create_app(cfg)
    app.config["API_KEY"] = "daily-plan-test-key"
    return app


def _item(key, **overrides):
    base = dict(
        id="",
        tenant_id="default",
        target_date=DATE,
        title=f"Attivita {key}",
        action_kind="deadline_fulfill",
        dedupe_key=key,
        priority="P0",
        item_rank=1,
        assigned_user_id="u1",
        reason="Termine perentorio scaduto e ancora aperto.",
        priority_reason="Termine perentorio scaduto e ancora aperto: intervento immediato.",
        priority_rule="R1",
        fascicolo_id="fasc-1",
        fascicolo_label="2026/10",
        due_at=DATE,
        peremptory=True,
        evidence=[SignalEvidence(source_type="scadenziario", source_id="sc-1", label="Scadenza")],
        available_actions=["accept", "complete", "snooze", "reject", "delegate", "create_task", "create_deadline"],
    )
    base.update(overrides)
    return DailyWorkItem(**base)


def _seed_plan(app, items=None, *, user_id="u1"):
    with app.app_context():
        repo = repository_from_paths(app.config, tenant_label="default", clock=CLOCK)
        rows = items if items is not None else [_item("k1")]
        repo.replace_items_for_date(DATE, rows, plan_version="v1")
        repo.save_snapshot(
            target_date=DATE,
            user_id=user_id,
            plan_version="v1",
            generation_mode="full",
            freshness={},
            coverage={"agenda": {"source_type": "agenda", "status": "complete"}},
            summary={"totale": len(rows), "per_priorita": {"P0": 1}},
            fixed_agenda=[],
            warnings=[],
        )
        return repo


def test_get_daily_plan_flag_spento(tmp_path):
    app = _app(tmp_path, enabled=False)
    with app.test_client() as client:
        response = client.get("/api/v1/ui/daily-plan", headers=HEADERS)
    assert response.status_code == 403
    assert response.get_json()["code"] == "feature_disabled"


def test_get_daily_plan_richiede_autenticazione(tmp_path):
    app = _app(tmp_path)
    with app.test_client() as client:
        response = client.get("/api/v1/ui/daily-plan")
    assert response.status_code == 401


def test_get_daily_plan_snapshot_ed_etag_304(tmp_path):
    app = _app(tmp_path)
    _seed_plan(app)
    with app.test_client() as client:
        risposta = client.get(f"/api/v1/ui/daily-plan?user=u1&date={DATE}", headers=HEADERS)
        assert risposta.status_code == 200
        payload = risposta.get_json()
        assert payload["stato"] == "pronto"
        assert payload["versione_piano"] == "v1"
        assert payload["sezioni"]["da_fare_ora"]
        riga = payload["sezioni"]["da_fare_ora"][0]
        assert riga["priorita"] == "P0"
        assert riga["evidenze"] == 1  # solo conteggio nel payload iniziale
        assert "evidenze_dettaglio" not in riga
        etag = risposta.headers.get("ETag")
        assert etag and "v1" in etag

        # secondo giro: payload invariato → 304 senza corpo
        secondo = client.get(
            f"/api/v1/ui/daily-plan?user=u1&date={DATE}",
            headers={**HEADERS, "If-None-Match": etag},
        )
        assert secondo.status_code == 304


def test_get_daily_plan_non_generato(tmp_path):
    app = _app(tmp_path)
    with app.test_client() as client:
        risposta = client.get(f"/api/v1/ui/daily-plan?user=u1&date={DATE}", headers=HEADERS)
    assert risposta.status_code == 200
    payload = risposta.get_json()
    assert payload["stato"] == "non_generato"
    assert payload["avvisi"]


def test_get_item_detail_lazy(tmp_path):
    app = _app(tmp_path)
    repo = _seed_plan(app)
    with app.app_context():
        item = repo.list_items(DATE)[0]
    with app.test_client() as client:
        risposta = client.get(f"/api/v1/ui/daily-plan/items/{item.id}", headers=HEADERS)
        assert risposta.status_code == 200
        dettaglio = risposta.get_json()["attivita"]
        assert dettaglio["evidenze_dettaglio"]
        assert dettaglio["spiegazione_priorita"].startswith("Termine perentorio")
        assert dettaglio["regola_priorita"] == "R1"

        mancante = client.get("/api/v1/ui/daily-plan/items/inesistente", headers=HEADERS)
        assert mancante.status_code == 404


def test_backlog_paginato_con_metadata(tmp_path):
    app = _app(tmp_path)
    items = [
        _item(f"k{i}", priority="P2", item_rank=i, in_backlog=True) for i in range(5)
    ]
    _seed_plan(app, items)
    with app.test_client() as client:
        risposta = client.get(
            f"/api/v1/ui/daily-plan/backlog?user=u1&date={DATE}&limit=2", headers=HEADERS
        )
    payload = risposta.get_json()
    assert len(payload["items"]) == 2
    assert payload["total_matching"] == 5
    assert payload["truncated"] is True
    assert payload["next_cursor"]


def test_refresh_accoda_202_idempotente(tmp_path):
    app = _app(tmp_path)
    with app.test_client() as client:
        primo = client.post(
            "/api/v1/ui/daily-plan/refresh",
            json={"mode": "incremental"},
            headers={**HEADERS, "Idempotency-Key": "r1"},
        )
        assert primo.status_code == 202
        assert primo.get_json()["accettato"] is True

        replay = client.post(
            "/api/v1/ui/daily-plan/refresh",
            json={"mode": "incremental"},
            headers={**HEADERS, "Idempotency-Key": "r1"},
        )
        assert replay.status_code == 202
        assert replay.get_json()["gia_in_coda"] is True
        assert replay.get_json()["job_id"] == primo.get_json()["job_id"]


def test_azione_stato_accept_e_replay_idempotente(tmp_path):
    app = _app(tmp_path)
    repo = _seed_plan(app)
    with app.app_context():
        item = repo.list_items(DATE)[0]
    with app.test_client() as client:
        risposta = client.post(
            f"/api/v1/ui/daily-plan/items/{item.id}/action",
            json={"action": "accept"},
            headers={**HEADERS, "Idempotency-Key": "a1"},
        )
        assert risposta.status_code == 200
        assert risposta.get_json()["attivita"]["stato"] == "accepted"

        replay = client.post(
            f"/api/v1/ui/daily-plan/items/{item.id}/action",
            json={"action": "accept"},
            headers={**HEADERS, "Idempotency-Key": "a1"},
        )
        assert replay.status_code == 200
        assert replay.get_json().get("replayed") is True


def test_transizione_non_ammessa_409(tmp_path):
    app = _app(tmp_path)
    repo = _seed_plan(app)
    with app.app_context():
        item = repo.list_items(DATE)[0]
        repo.update_item_status(item.id, "completed", actor="test")
    with app.test_client() as client:
        risposta = client.post(
            f"/api/v1/ui/daily-plan/items/{item.id}/action",
            json={"action": "accept"},
            headers=HEADERS,
        )
    assert risposta.status_code == 409
    assert risposta.get_json()["code"] == "invalid_transition"


def test_azione_dominio_bloccata_senza_flag(tmp_path):
    """Caso obbligatorio 13: nessuna scrittura senza approvazione/flag."""
    app = _app(tmp_path, write_proposals=False)
    repo = _seed_plan(app)
    with app.app_context():
        item = repo.list_items(DATE)[0]
    with app.test_client() as client:
        risposta = client.post(
            f"/api/v1/ui/daily-plan/items/{item.id}/action",
            json={"action": "create_deadline"},
            headers=HEADERS,
        )
    assert risposta.status_code == 403
    assert risposta.get_json()["code"] == "feature_disabled"


def test_azione_dominio_crea_proposta_approvabile(tmp_path):
    app = _app(tmp_path, write_proposals=True)
    repo = _seed_plan(app)
    with app.app_context():
        item = repo.list_items(DATE)[0]
    with app.test_client() as client:
        risposta = client.post(
            f"/api/v1/ui/daily-plan/items/{item.id}/action",
            json={"action": "create_deadline", "params": {"titolo": "Verifica termine"}},
            headers=HEADERS,
        )
        assert risposta.status_code == 200
        payload = risposta.get_json()
        assert payload["proposta_creata"] is True
        assert payload["proposal_id"]

        # la proposta compare nella coda approvazioni Workflow Agents
        approvals = client.get("/api/v1/ui/workflow-agents/approvals", headers=HEADERS)
        assert approvals.status_code == 200
        rows = approvals.get_json()["approvals"]
        assert any(r["id"] == payload["proposal_id"] for r in rows)

        # e NESSUNA scadenza è stata creata nel dominio (solo proposta)
        dettaglio = client.get(
            f"/api/v1/ui/workflow-agents/runs/{payload['run_id']}", headers=HEADERS
        )
        assert dettaglio.status_code == 200
        run = dettaglio.get_json()["run"]
        assert run["status"] == "needs_approval"
        assert all(p["status"] == "pending" for p in run["proposals"])


def test_azione_sconosciuta_400(tmp_path):
    app = _app(tmp_path)
    repo = _seed_plan(app)
    with app.app_context():
        item = repo.list_items(DATE)[0]
    with app.test_client() as client:
        risposta = client.post(
            f"/api/v1/ui/daily-plan/items/{item.id}/action",
            json={"action": "invia_pec"},
            headers=HEADERS,
        )
    assert risposta.status_code == 400
    assert risposta.get_json()["code"] == "unknown_action"


def test_coverage_endpoint(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        repo = repository_from_paths(app.config, tenant_label="default", clock=CLOCK)
        repo.set_watermark("pec", watermark="2026-07-11T07:00:00", status="ok")
    with app.test_client() as client:
        risposta = client.get("/api/v1/ui/daily-plan/coverage", headers=HEADERS)
    assert risposta.status_code == 200
    fonti = risposta.get_json()["fonti"]
    assert fonti["pec"]["stato"] == "ok"
