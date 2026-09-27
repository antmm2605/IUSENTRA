"""Migrazione React 2.415.0: azioni del pannello di piattaforma.

Pianificazioni, crash test operativo, pacchetto di installazione e assistente
migrazione eseguono le loro azioni da `/api/v1/ui/piattaforma/<pagina>/azioni/<azione>`
con gli stessi servizi delle viste storiche.
"""

from __future__ import annotations

from pathlib import Path

from tests.test_migrazione_react_piattaforma import _app, _login_superadmin

BASE = "/api/v1/ui/piattaforma"


def _azioni(sezioni: list[dict]) -> list[dict]:
    trovate = []
    for sezione in sezioni:
        trovate += sezione.get("items", []) if sezione["kind"] == "actions" else []
        trovate += [sezione["action"]] if sezione["kind"] == "form" else []
        for riga in sezione.get("rows", []) if sezione["kind"] == "table" else []:
            trovate += riga.get("actions", [])
    return trovate


def _azione(client, pagina: str, chiave: str, *, params=None, values=None):
    return client.post(f"{BASE}/{pagina}/azioni/{chiave}", json={"params": params or {}, "values": values or {}})


def test_pianificazioni_crea_modifica_esegue_e_annulla(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        pagina = client.get(f"{BASE}/pianificazioni").get_json()
        azioni = _azioni(pagina["sections"])
        modulo = next(a for a in azioni if a["key"] == "crea")
        assert modulo["label"] == "Crea pianificazione"
        esegui = next(a for a in azioni if a["key"] == "esegui")
        modifica = next(a for a in azioni if a["key"] == "salva")
        assert {c["name"] for c in modifica["fields"]} >= {"name", "trigger_kind", "hour", "minute", "enabled"}

        agente = next(s for s in pagina["sections"] if s["kind"] == "form")["fields"][0]["value"]
        creata = _azione(client, "pianificazioni", "crea", values={"template_key": agente, "name": "Controllo serale di prova", "trigger_kind": "cron", "hour": "21", "minute": "15", "interval_minutes": "60"}).get_json()
        assert creata["ok"] is True and "Controllo serale di prova" in creata["message"]

        # La pianificazione creata si modifica dalla sua riga.
        righe = [r for s in client.get(f"{BASE}/pianificazioni").get_json()["sections"] if s["kind"] == "table" for r in s["rows"]]
        riga = next(r for r in righe if "Controllo serale di prova" in r["cells"].get("job", ""))
        modifica = next(a for a in riga["actions"] if a["key"] == "salva")
        valori = {c["name"]: c["value"] for c in modifica["fields"]}
        valori.update(description="Descrizione aggiornata dalla pagina React", hour="20")
        salvata = _azione(client, "pianificazioni", "salva", params=modifica["params"], values=valori).get_json()
        assert salvata["ok"] is True

        richiesta = _azione(client, "pianificazioni", "esegui", params=esegui["params"]).get_json()
        assert richiesta["ok"] is True and "Esecuzione richiesta" in richiesta["message"]
        assert _azione(client, "pianificazioni", "annulla-fonti").get_json()["ok"] is True

        dopo = client.get(f"{BASE}/pianificazioni").get_json()
        testo = str(dopo["sections"])
        assert "Controllo serale di prova" in testo and "Descrizione aggiornata dalla pagina React" in testo
        assert _azione(client, "pianificazioni", "sconosciuta").get_json()["ok"] is False


def test_crash_test_e_backup_con_i_servizi_storici(tmp_path: Path, monkeypatch):
    import web.services.operational_resilience_surface as superficie

    chiamate = []
    monkeypatch.setattr(superficie, "execute_operational_crash_surface", lambda **kw: chiamate.append(("crash", kw)) or {"overall_ok": True, "report_path": "/tmp/report.json"})
    monkeypatch.setattr(superficie, "execute_operational_backup_surface", lambda **kw: chiamate.append(("backup", kw)) or {"success": True, "report_path": "/tmp/backup.json"})
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        azioni = _azioni(client.get(f"{BASE}/crash-test").get_json()["sections"])
        crash = next(a for a in azioni if a["key"] == "esegui")
        assert crash["confirm"]
        esito = _azione(client, "crash-test", "esegui", params=crash["params"]).get_json()
        assert esito["ok"] is True and esito["tone"] == "success"
        backup = _azione(client, "crash-test", "backup", params=next(a for a in azioni if a["key"] == "backup")["params"]).get_json()
        assert backup["ok"] is True
    assert chiamate[0][0] == "crash" and chiamate[0][1]["auto_repair"] is True and chiamate[0][1]["max_attempts"] == 3
    assert chiamate[1][0] == "backup" and chiamate[1][1]["trigger_source"] == "manual"


def test_pacchetto_di_installazione_e_assistente_migrazione(tmp_path: Path, monkeypatch):
    import web.services.migration_assistant as assistente

    monkeypatch.setattr(assistente, "execute_migration_assistant", lambda **kw: {"report_path": "/tmp/migrazione.json", "generated_at": "2026-09-27T10:00:00"})
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        pack = client.get(f"{BASE}/installazione-pack").get_json()
        aggiorna = next(a for a in _azioni(pack["sections"]) if a["key"] == "refresh")
        assert _azione(client, "installazione-pack", "refresh", params=aggiorna["params"]).get_json()["ok"] is True

        migrazione = client.get(f"{BASE}/assistente-migrazione").get_json()
        assert migrazione["ok"] is True
        esegui = [a for a in _azioni(migrazione["sections"]) if a["key"] == "esegui"]
        if esegui:
            esito = _azione(client, "assistente-migrazione", "esegui", params=esegui[0]["params"]).get_json()
            assert esito["ok"] is True


def test_azioni_riservate_e_protette(tmp_path: Path):
    from tests.test_revisione_2410_sicurezza import _app as _app_sessione
    from tests.test_topbar_operational_api import _login
    from web.services.security_runtime import _CSRF_PROTECTED_ENDPOINTS

    assert "api_v1_piattaforma.azione" in _CSRF_PROTECTED_ENDPOINTS
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        assert _azione(client, "pianificazioni", "annulla-fonti").status_code == 403
    with app.test_client() as anonimo:
        assert _azione(anonimo, "pianificazioni", "annulla-fonti").status_code == 401
