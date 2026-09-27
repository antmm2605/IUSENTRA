"""Revisione 2.418.0: portale del cliente, operazioni della Ricerca legale,
deposito penale nel fascicolo React e password provvisoria.

- il portale del cliente carica documenti solo nelle pratiche di quel cliente;
- le operazioni della pagina storica `/ricerca-legale` (monitoraggio,
  tabelle normative, registro della mediazione) si avviano dalla pagina React;
- `/fascicoli/<id>/penale/pdp` porta alla sezione React del fascicolo;
- con la password provvisoria le API non modificano dati.
"""

from __future__ import annotations

import io

from tests.test_revisione_2410_sicurezza import _app as _app_sessione
from tests.test_topbar_operational_api import _login

BASE = "/api/v1/ui/ricerca-legale"


def _cliente_e_fascicolo(app, nome: str):
    from pct.clienti import TipoCliente
    from pct.fascicoli import TipoFascicolo
    from web.helpers import get_clienti, get_fascicoli

    with app.test_request_context("/"):
        cliente = get_clienti().nuovo(TipoCliente.PERSONA_FISICA, nome=nome, cognome="Prova")
        fascicolo = get_fascicoli().nuovo(f"{nome} c. Terzi", TipoFascicolo.CIVILE, nome_cliente=nome, id_cliente=cliente.id)
    return cliente, fascicolo


def test_portale_non_carica_nelle_pratiche_di_altri_clienti(tmp_path):
    from web.blueprints.portale import _get_portale
    from web.helpers import get_fascicoli

    app = _app_sessione(tmp_path)
    mario, pratica_mario = _cliente_e_fascicolo(app, "Mario")
    _luigi, pratica_luigi = _cliente_e_fascicolo(app, "Luigi")
    with app.test_request_context("/"):
        token, _portale = _get_portale().crea(mario.id, creato_da="test")
    with app.test_client() as client:
        estranea = client.post(
            f"/portale/{token}/documenti/carica",
            data={"files[]": (io.BytesIO(b"contenuto"), "nota.txt"), "id_fascicolo": pratica_luigi.id},
            content_type="multipart/form-data",
        )
        assert estranea.status_code == 403
        propria = client.post(
            f"/portale/{token}/documenti/carica",
            data={"files[]": (io.BytesIO(b"contenuto"), "nota.txt"), "id_fascicolo": pratica_mario.id},
            content_type="multipart/form-data",
        )
        assert propria.status_code == 200
    with app.test_request_context("/"):
        assert not get_fascicoli().get(pratica_luigi.id).documenti
        assert get_fascicoli().get(pratica_mario.id).documenti


def test_link_scaduto_del_portale_resta_nel_portale(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        portale = client.get("/portale/token-inesistente?_legacy=1")
        portale_react = client.get("/portale/token-inesistente")
        pagamento = client.post("/pagamenti/paga/token-inesistente/avvia", data={"provider": "bonifico"})
    assert portale.status_code == 410
    assert portale_react.status_code == 410
    assert pagamento.status_code == 410
    # Il pagamento scaduto ha la sua pagina, non quella del portale del cliente.
    assert "Link non valido" in portale.get_data(as_text=True)
    # Pagina React del portale: stessa risposta 410, schermata «link scaduto» della shell.
    assert 'data-stato="scaduto"' in portale_react.get_data(as_text=True)
    assert "Link scaduto" in pagamento.get_data(as_text=True)


def test_operazioni_della_ricerca_legale(tmp_path, monkeypatch):
    from pct.legal_intelligence import GestioneLegalIntelligence

    chiamate: list[tuple] = []
    monkeypatch.setattr(GestioneLegalIntelligence, "run_monitor_cycle", lambda self: chiamate.append(("monitor",)) or {"ok": True})
    monkeypatch.setattr(GestioneLegalIntelligence, "sync_normative_tables", lambda self, **kw: chiamate.append(("sync", kw)) or {"ok": True})
    monkeypatch.setattr(GestioneLegalIntelligence, "import_registro_mediazione_snapshot", lambda self, contenuto, filename="": {"rows": 12})
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        cruscotto = client.get(f"{BASE}/controllo-giornaliero").get_json()
        assert {o["key"] for o in cruscotto["operations"]} == {"monitoraggio", "tabelle-normative", "registro-mediazione"}
        for operazione in cruscotto["operations"]:
            risposta = client.post(operazione["action"], json={})
            assert risposta.status_code in (200, 202), operazione["key"]
        importa = client.post(
            cruscotto["importAction"],
            data={"snapshot_file": (io.BytesIO(b"<html><table></table></html>"), "registro.html")},
            content_type="multipart/form-data",
        ).get_json()
        assert importa["ok"] is True and importa["rows"] == 12
        vuoto = client.post(cruscotto["importAction"], data={}, content_type="multipart/form-data")
        assert vuoto.status_code == 400
    import time

    for _ in range(50):
        if len(chiamate) >= 3:
            break
        time.sleep(0.1)
    assert ("monitor",) in chiamate
    assert ("sync", {}) in chiamate and ("sync", {"source_ids": ["registro_mediazione"]}) in chiamate


def test_deposito_penale_nella_sezione_react_del_fascicolo(tmp_path):
    app = _app_sessione(tmp_path)
    _cliente, pratica = _cliente_e_fascicolo(app, "Anna")
    with app.test_client() as client:
        _login(client)
        risposta = client.get(f"/fascicoli/{pratica.id}/penale/pdp", headers={"Accept": "text/html"})
        assert risposta.status_code == 302
        assert risposta.headers["Location"].endswith(f"/fascicoli/{pratica.id}#penale-pdp")


def test_password_provvisoria_blocca_le_scritture_delle_api(tmp_path):
    from web.helpers import get_utenti

    app = _app_sessione(tmp_path)
    with app.test_request_context("/"):
        gestione = get_utenti()
        utente = gestione.get_by_username("operatore")
        gestione.cambia_password(utente.id, "Provvisoria123!", must_change_password=True)
    with app.test_client() as client:
        client.post("/login", data={"username": "operatore", "password": "Provvisoria123!"})
        app.testing = False
        try:
            bloccata = client.post(f"{BASE}/monitoraggio/esegui", json={})
            lettura = client.get(f"{BASE}/controllo-giornaliero")
        finally:
            app.testing = True
    assert bloccata.status_code == 403 and bloccata.get_json()["code"] == "password_change_required"
    assert lettura.status_code == 200
