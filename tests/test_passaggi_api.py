"""API dei passaggi e delle regole dello studio: autenticazione, permessi, isolamento fra studi, ciclo completo.

I dati del fascicolo arrivano da una fixture (``dati_del_fascicolo`` sostituito):
nessun dato di clienti. Il tenant è quello della richiesta, simulato sostituendo
``tenant_corrente`` del runtime.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app

HEADERS = {"X-API-Key": "passaggi-test-key"}
FASCICOLI = {
    "F1": {"id": "F1", "tribunale": "Tribunale di Milano", "giudice": "dott.ssa Bianchi", "area_pratica": "civile"},
    "F2": {"id": "F2", "tribunale": "Tribunale di Milano", "giudice": "dott.ssa Bianchi", "area_pratica": "civile"},
}


def _dati(fascicolo_id: str):
    fascicolo = FASCICOLI.get(fascicolo_id)
    if fascicolo is None:
        return None
    scadenza = {"id": f"S-{fascicolo_id}", "stato": "BOZZA", "data": "2027-01-12", "deadline_profile_code": "NOTE_127_TER",
                "titolo": "Deposito note scritte ex art. 127-ter c.p.c.", "operational_due_at": "2027-01-12T09:30:00"}
    return {"fascicolo": fascicolo, "scadenze": [scadenza], "termini_pec": []}


@pytest.fixture()
def app(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg["REGOLE_STUDIO_DB"] = str(tmp_path / "intelligence" / "regole_studio.db")
    applicazione = create_app(cfg)
    applicazione.config["API_KEY"] = HEADERS["X-API-Key"]
    applicazione.config["REGOLE_STUDIO_DB"] = cfg["REGOLE_STUDIO_DB"]
    import web.services.passaggi_runtime as runtime

    monkeypatch.setattr(runtime, "dati_del_fascicolo", _dati)
    monkeypatch.setattr(runtime, "percorso_regole", lambda paths=None: cfg["REGOLE_STUDIO_DB"])
    studio = {"tenant": "studio-a"}
    monkeypatch.setattr(runtime, "tenant_corrente", lambda: studio["tenant"])
    applicazione.studio_di_prova = studio
    return applicazione


def _termine(passaggi: list[dict]) -> dict:
    return next(voce for voce in passaggi if voce["regola"]["id"] == "127ter.termine_note")


def test_senza_autenticazione_401(app):
    with app.test_client() as client:
        assert client.get("/api/v1/ui/fascicoli/F1/passaggi").status_code == 401
        assert client.post("/api/v1/ui/fascicoli/F1/passaggi/correzioni", json={}).status_code == 401
        assert client.get("/api/v1/ui/regole-studio").status_code == 401
        assert client.post("/api/v1/ui/regole-studio/x", json={"attiva": False}).status_code == 401


def test_utente_senza_permesso_di_scrittura_403(app):
    from web.blueprints.api_v1_passaggi import fascicolo_passaggi_correzione, regole_studio_aggiorna

    class SoloLettura:
        id = "u9"
        nome_completo = "Solo Lettura"

        def ha_permesso(self, permesso):
            return permesso == "fascicoli.leggi"

    with app.test_request_context("/api/v1/ui/fascicoli/F1/passaggi/correzioni", method="POST", json={}):
        from flask import g

        g.utente_corrente = SoloLettura()
        risposta, stato = fascicolo_passaggi_correzione("F1")
        assert stato == 403 and risposta.get_json()["code"] == "forbidden"
        _risposta, stato = regole_studio_aggiorna("x")
        assert stato == 403


def test_sessione_reale_legge_i_passaggi(app):
    _crea_operatore(app)
    with app.test_client() as client:
        _login(client)
        risposta = client.get("/api/v1/ui/fascicoli/F1/passaggi")
        assert risposta.status_code == 200 and risposta.get_json()["ok"]
        assert client.get("/api/v1/ui/fascicoli/ignoto/passaggi").status_code == 404


def test_ciclo_correzione_caso_successivo_modifica_e_disattivazione(app):
    with app.test_client() as client:
        passaggi = client.get("/api/v1/ui/fascicoli/F1/passaggi", headers=HEADERS).get_json()["passaggi"]
        termine = _termine(passaggi)
        assert termine["campi"]["ora"]["valore"] == "09:30" and termine["norme"][0]["id"] == "cpc_127ter"
        creata = client.post("/api/v1/ui/fascicoli/F1/passaggi/correzioni", headers=HEADERS, json={
            "chiave": termine["chiave"], "azione": "modifica_valore", "campo": "ora", "valore": "12:00", "ambito": "giudice",
            "motivo": "Prassi del giudice", "ufficio": "Altro ufficio iniettato"}).get_json()
        assert creata["ok"] and creata["regola"]["ufficio"] == "Tribunale di Milano"
        successivo = _termine(client.get("/api/v1/ui/fascicoli/F2/passaggi", headers=HEADERS).get_json()["passaggi"])
        assert successivo["campi"]["ora"] == {**successivo["campi"]["ora"], "valore": "12:00", "valoreSoftware": "09:30"}
        assert successivo["regoleStudioApplicate"][0]["etichetta"].startswith("regola dello studio del ")
        regola_id = creata["regola"]["id"]
        elenco = client.get("/api/v1/ui/regole-studio", headers=HEADERS).get_json()["regole"]
        assert [voce["id"] for voce in elenco] == [regola_id] and elenco[0]["applicazioni"] >= 1
        assert client.post(f"/api/v1/ui/regole-studio/{regola_id}", headers=HEADERS, json={"valore": "11:00"}).get_json()["regola"]["valore"] == "11:00"
        assert client.post(f"/api/v1/ui/regole-studio/{regola_id}", headers=HEADERS, json={"attiva": False}).get_json()["ok"]
        tornato = _termine(client.get("/api/v1/ui/fascicoli/F2/passaggi", headers=HEADERS).get_json()["passaggi"])
        assert tornato["campi"]["ora"]["valore"] == "09:30" and tornato["regoleStudioApplicate"] == []
        diario = client.get(f"/api/v1/ui/regole-studio/{regola_id}/diario", headers=HEADERS).get_json()
        assert [evento["evento"] for evento in diario["eventi"]] == ["creata", "modificata", "disattivata"]
        assert diario["applicazioni"][0]["fascicolo_id"] in {"F1", "F2"}


def test_vincolo_di_legge_rifiuta_la_correzione_e_resta_nel_diario(app):
    with app.test_client() as client:
        termine = _termine(client.get("/api/v1/ui/fascicoli/F1/passaggi", headers=HEADERS).get_json()["passaggi"])
        esito = client.post("/api/v1/ui/fascicoli/F1/passaggi/correzioni", headers=HEADERS,
                            json={"chiave": termine["chiave"], "azione": "non_proporre", "ambito": "tipo"}).get_json()
        assert not esito["ok"] and esito["rifiutata"] and "art. 153" in esito["errore"]
        assert esito["rifiuto"]["norme"][0]["id"] == "cpc_153"
        assert client.get("/api/v1/ui/regole-studio", headers=HEADERS).get_json()["regole"] == []
    from web.services.passaggi_runtime import RegoleStudioRepository

    eventi = RegoleStudioRepository(app.config["REGOLE_STUDIO_DB"], tenant_id="studio-a").eventi()
    assert [evento["evento"] for evento in eventi] == ["rifiutata"]


def test_le_regole_di_uno_studio_non_valgono_per_un_altro(app):
    with app.test_client() as client:
        termine = _termine(client.get("/api/v1/ui/fascicoli/F1/passaggi", headers=HEADERS).get_json()["passaggi"])
        regola = client.post("/api/v1/ui/fascicoli/F1/passaggi/correzioni", headers=HEADERS, json={
            "chiave": termine["chiave"], "azione": "chiedi_sempre", "ambito": "tipo"}).get_json()["regola"]
        app.studio_di_prova["tenant"] = "studio-b"
        assert client.get("/api/v1/ui/regole-studio", headers=HEADERS).get_json()["regole"] == []
        altro = _termine(client.get("/api/v1/ui/fascicoli/F2/passaggi", headers=HEADERS).get_json()["passaggi"])
        assert altro["stato"] == "da_confermare" and altro["regoleStudioApplicate"] == []
        esito = client.post(f"/api/v1/ui/regole-studio/{regola['id']}", headers=HEADERS, json={"attiva": False}).get_json()
        assert not esito["ok"]
        assert client.get(f"/api/v1/ui/regole-studio/{regola['id']}/diario", headers=HEADERS).status_code == 404
        app.studio_di_prova["tenant"] = "studio-a"
        assert client.get("/api/v1/ui/regole-studio", headers=HEADERS).get_json()["regole"][0]["attiva"]
