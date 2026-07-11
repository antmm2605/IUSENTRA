"""Test sicurezza del piano del giorno: RBAC, tenant, PII, azioni vietate."""

import logging
from datetime import datetime
from pathlib import Path

from pct.daily_plan.clock import Clock
from pct.daily_plan.models import DailyWorkItem, OperationalSignal
from pct.daily_plan.repository import DailyPlanRepository
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.daily_plan_runtime import repository_from_paths

CLOCK = Clock(fixed_now=datetime(2026, 7, 11, 9, 0))
DATE = "2026-07-11"
HEADERS = {"X-API-Key": "daily-plan-test-key"}


def _app(tmp_path: Path, **flags):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg["FEATURE_FLAGS"] = {
        "lex.dailyPlan.enabled": True,
        "lex.dailyPlan.writeProposals": True,
        "lex.workflowAgents.enabled": True,
        **flags,
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
        priority="P1",
        assigned_user_id="u1",
    )
    base.update(overrides)
    return DailyWorkItem(**base)


def test_client_non_puo_imporre_tenant(tmp_path):
    """Caso obbligatorio: nessun tenant deciso dal client."""
    app = _app(tmp_path)
    with app.test_client() as client:
        risposta = client.post(
            "/api/v1/ui/daily-plan/refresh",
            json={"mode": "incremental", "tenant_id": "altro-studio"},
            headers=HEADERS,
        )
    assert risposta.status_code == 400
    codice = risposta.get_json()["code"]
    assert codice in {"client_control_rejected", "backend_security_control_param"}


def test_azione_con_path_filesystem_rifiutata(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        repo = repository_from_paths(app.config, tenant_label="default", clock=CLOCK)
        repo.replace_items_for_date(DATE, [_item("k1")], plan_version="v1")
        item = repo.list_items(DATE)[0]
    with app.test_client() as client:
        risposta = client.post(
            f"/api/v1/ui/daily-plan/items/{item.id}/action",
            json={"action": "create_task", "params": {"file_path": "/etc/passwd"}},
            headers=HEADERS,
        )
    assert risposta.status_code == 400


def test_utente_senza_permessi_403(tmp_path):
    app = _app(tmp_path)
    # utente di sessione senza permessi agenda/scadenziario
    from tests.test_applicazioni import _crea_operatore, _login

    _crea_operatore(app)
    with app.test_client() as client:
        _login(client)
        # l'operatore amministratore HA i permessi → 200/stato
        ok = client.get("/api/v1/ui/daily-plan")
        assert ok.status_code == 200

    class _SenzaPermessi:
        id = "u9"
        nome_completo = "Senza Permessi"

        def ha_permesso(self, _p):
            return False

    with app.test_request_context("/api/v1/ui/daily-plan"):
        from flask import g

        g.utente_corrente = _SenzaPermessi()
        from web.blueprints.api_v1_daily_plan import daily_plan_home

        risposta = daily_plan_home()
        assert risposta[1] == 403


def test_isolamento_cross_tenant_nel_repository(tmp_path):
    """Caso obbligatorio 14: nessuna lettura cross-tenant."""
    db = str(tmp_path / "daily_plan.db")
    repo_a = DailyPlanRepository(db, tenant_id="studio-a", clock=CLOCK)
    repo_b = DailyPlanRepository(db, tenant_id="studio-b", clock=CLOCK)
    repo_a.replace_items_for_date(DATE, [_item("k1", tenant_id="studio-a")], plan_version="v1")

    assert repo_b.list_items(DATE) == []
    item_a = repo_a.list_items(DATE)[0]
    assert repo_b.get_item(item_a.id) is None
    assert repo_b.get_snapshot(DATE, "u1") is None


def test_nessuna_pii_nei_log_durante_costruzione(tmp_path, caplog):
    """Caso obbligatorio 15: nessuna PII nei log."""
    with caplog.at_level(logging.DEBUG):
        segnale = OperationalSignal(
            id="sig_1",
            tenant_id="studio-a",
            source_type="pec",
            kind="pec_review",
            title="PEC con IBAN IT60X0542811101000000123456 e CF RSSMRA85M01H501Z",
            dedupe_key="k",
            description="documento in /home/user/segreti.pdf",
            metadata={"password": "supersegreta", "iban": "IT60X0542811101000000123456"},
        )
    testo_log = " ".join(r.getMessage() for r in caplog.records)
    assert "IT60X0542811101000000123456" not in testo_log
    assert "supersegreta" not in testo_log
    # e nemmeno nei payload serializzati
    data = segnale.to_dict()
    assert "IT60X0542811101000000123456" not in str(data)
    assert "RSSMRA85M01H501Z" not in str(data)
    assert "/home/user" not in str(data)
    assert "password" not in data["metadata"]


def test_azioni_legali_vietate_non_raggiungibili(tmp_path):
    """Le azioni vietate (invio PEC, firma, deposito, elimina) non esistono."""
    from web.services.react_daily_plan_bridge import DOMAIN_ACTIONS, STATUS_ACTIONS

    vietate = {"send_pec", "invia_pec", "firma", "deposita", "delete", "elimina",
               "emetti_fattura", "cancella_fascicolo"}
    assert not (vietate & set(DOMAIN_ACTIONS)), "azione vietata esposta"
    assert not (vietate & set(STATUS_ACTIONS)), "azione vietata esposta"
    # la bozza PEC resta con invio bloccato per costruzione del tool
    assert DOMAIN_ACTIONS["create_pec_draft"] == "create_pec_draft"


def test_proposta_dominio_non_scrive_nel_dominio(tmp_path):
    """Caso obbligatorio 13: zero scritture senza approvazione."""
    app = _app(tmp_path)
    with app.app_context():
        repo = repository_from_paths(app.config, tenant_label="default", clock=CLOCK)
        repo.replace_items_for_date(DATE, [_item("k1")], plan_version="v1")
        item = repo.list_items(DATE)[0]
    with app.test_client() as client:
        risposta = client.post(
            f"/api/v1/ui/daily-plan/items/{item.id}/action",
            json={"action": "create_deadline"},
            headers=HEADERS,
        )
        assert risposta.status_code == 200
    # lo scadenziario del tenant è rimasto intatto
    from pct.scadenziario import GestioneScadenziario

    scadenze = GestioneScadenziario(db_path=str(app.config["SCADENZIARIO_DB"])).tutte(
        solo_aperte=False
    )
    assert scadenze == [] or all("piano del giorno" not in s.titolo.lower() for s in scadenze)


def test_liste_sempre_con_metadata_di_troncamento(tmp_path):
    """Caso obbligatorio 20: nessun troncamento silenzioso."""
    app = _app(tmp_path)
    with app.app_context():
        repo = repository_from_paths(app.config, tenant_label="default", clock=CLOCK)
        items = [_item(f"k{i}", in_backlog=True, priority="P2", item_rank=i) for i in range(4)]
        repo.replace_items_for_date(DATE, items, plan_version="v1")
    with app.test_client() as client:
        risposta = client.get(
            f"/api/v1/ui/daily-plan/backlog?user=u1&date={DATE}&limit=2", headers=HEADERS
        )
    payload = risposta.get_json()
    assert "truncated" in payload and "total_matching" in payload
    assert payload["truncated"] is True
