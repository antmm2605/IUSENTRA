"""Migrazione React 2.413.0: moduli per cliente, scheda parcella, schede della Ricerca legale.

- `/fatturazione/nuova/<cliente>`, `/preventivi/nuovo/<cliente>` e
  `/preventivi/conferimento/nuovo/<cliente>` portano al modulo React con il
  cliente già scelto (`?id_cliente=`);
- `/fatturazione/<id>` apre la scheda nella pagina React (`?id_parcella=`), con
  link di pagamento ed eliminazione della sola bozza (art. 26 D.P.R. 633/1972);
- news, scheda della fonte e differenze della Ricerca legale sono pagine React.
"""

from __future__ import annotations

from pathlib import Path

from tests.test_revisione_2410_sicurezza import _app as _app_sessione
from tests.test_topbar_operational_api import _login

HTML = {"Accept": "text/html"}


def test_moduli_per_cliente_e_scheda_parcella_portano_alla_pagina_react(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        casi = {
            "/fatturazione/nuova/C1": "/fatturazione/nuova?id_cliente=C1",
            "/preventivi/nuovo/C1": "/preventivi/nuovo?id_cliente=C1",
            "/preventivi/conferimento/nuovo/C1?id_fascicolo=F9": "/preventivi/conferimento/nuovo?id_fascicolo=F9&id_cliente=C1",
            "/fatturazione/P1": "/fatturazione?id_parcella=P1",
        }
        for origine, destinazione in casi.items():
            risposta = client.get(origine, headers=HTML)
            assert risposta.status_code == 302, origine
            assert risposta.headers["Location"].endswith(destinazione), (origine, risposta.headers["Location"])
        # La vista storica resta raggiungibile solo esplicitamente, i documenti restano del server.
        assert client.get("/fatturazione/P1?_legacy=1", headers=HTML).status_code in {404, 200}
        assert client.get("/fatturazione/P1/pdf", headers=HTML).status_code == 404


def test_scheda_parcella_link_di_pagamento_ed_eliminazione_della_bozza(tmp_path):
    from pct.fatturazione import StatoParcella, VoceParcella
    from web.helpers import get_fatturazione

    app = _app_sessione(tmp_path)
    with app.app_context():
        archivio = get_fatturazione()
        bozza = archivio.crea("C1", [VoceParcella(descrizione="Parere", prezzo_unitario=500.0)])
        emessa = archivio.crea("C1", [VoceParcella(descrizione="Atto", prezzo_unitario=800.0)])
        archivio.cambia_stato(emessa.id, StatoParcella.EMESSA)
    with app.test_client() as client:
        _login(client)
        scheda = client.get(f"/api/v1/ui/fatturazione/{bozza.id}").get_json()
        azioni = scheda["item"]["sheetActions"]
        assert azioni["canDelete"] is True and azioni["paymentLink"]["canCreate"] is True
        assert azioni["paymentLink"]["href"] == ""

        link = client.post(f"/api/v1/ui/fatturazione/{bozza.id}/link-pagamento", json={"giorni_validita": 10})
        assert link.status_code == 200, link.get_json()
        assert "/pagamenti/paga/" in link.get_json()["paymentLink"]["href"]
        dopo = client.get(f"/api/v1/ui/fatturazione/{bozza.id}").get_json()["item"]["sheetActions"]["paymentLink"]
        assert "/pagamenti/paga/" in dopo["href"] and dopo["expiresAt"]
        # Un nuovo link sostituisce il precedente.
        rinnovo = client.post(f"/api/v1/ui/fatturazione/{bozza.id}/link-pagamento", json={}).get_json()
        assert rinnovo["paymentLink"]["href"] != link.get_json()["paymentLink"]["href"]

        # Una fattura emessa non si elimina: si annulla o si rettifica.
        emessa_scheda = client.get(f"/api/v1/ui/fatturazione/{emessa.id}").get_json()["item"]["sheetActions"]
        assert emessa_scheda["canDelete"] is False and "art. 26" in emessa_scheda["deleteBlockedReason"]
        rifiuto = client.post(f"/api/v1/ui/fatturazione/{emessa.id}/elimina", json={})
        assert rifiuto.status_code == 409

        eliminata = client.post(f"/api/v1/ui/fatturazione/{bozza.id}/elimina", json={})
        assert eliminata.status_code == 200 and eliminata.get_json()["redirect_href"] == "/fatturazione"
        assert client.post(f"/api/v1/ui/fatturazione/{bozza.id}/elimina", json={}).status_code == 404


def test_link_di_pagamento_non_serve_per_parcella_pagata(tmp_path):
    from pct.fatturazione import StatoParcella, VoceParcella
    from web.helpers import get_fatturazione

    app = _app_sessione(tmp_path)
    with app.app_context():
        archivio = get_fatturazione()
        pagata = archivio.crea("C1", [VoceParcella(descrizione="Parere", prezzo_unitario=300.0)])
        archivio.cambia_stato(pagata.id, StatoParcella.PAGATA)
    with app.test_client() as client:
        _login(client)
        assert client.get(f"/api/v1/ui/fatturazione/{pagata.id}").get_json()["item"]["sheetActions"]["paymentLink"]["canCreate"] is False
        assert client.post(f"/api/v1/ui/fatturazione/{pagata.id}/link-pagamento", json={}).status_code == 409


def test_schede_ricerca_legale_nella_shell_react():
    from web.blueprints import react_shell
    from web.bootstrap.react_route_gate import _excluded, _is_react_route

    for percorso in ("/ricerca-legale/news/nuova-legge", "/ricerca-legale/fonte/gazzetta", "/ricerca-legale/daily/update/12/diff"):
        assert _is_react_route(percorso) and not _excluded(percorso), percorso
        assert react_shell._route_component_key(percorso) == "src/components/RicercaLegaleSchedaPage.tsx"
    # Il download del testo archiviato e le azioni del motore restano del server.
    assert _excluded("/ricerca-legale/fonte/gazzetta/scarica")
    assert _excluded("/ricerca-legale/daily/esegui")


def test_api_schede_ricerca_legale(tmp_path):
    from legal_intelligence.engine import LegalIntelligenceDailyEngine

    app = _app_sessione(tmp_path)
    with app.test_request_context():
        from web.blueprints.legal_intelligence import _daily_db_path

        db = _daily_db_path()
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    motore = LegalIntelligenceDailyEngine(db)
    id_variazione = motore.store.create_update(
        {"source_id": "gazzetta", "title": "Nuovo testo", "summary": "Cambia l'art. 1", "new_sha256": "b" * 64, "old_sha256": "a" * 64, "diff_text": "- vecchio\n+ nuovo"}
    )
    with app.test_client() as client:
        _login(client)
        assert client.get("/api/v1/ui/ricerca-legale/news/inesistente").status_code == 404
        assert client.get("/api/v1/ui/ricerca-legale/fonti/inesistente").status_code == 404
        fonte = client.get("/api/v1/ui/ricerca-legale/fonti/anac").get_json()
        assert fonte["ok"] is True and fonte["item"]["officialHref"].startswith("https://")
        variazione = client.get(f"/api/v1/ui/ricerca-legale/aggiornamenti/{id_variazione}").get_json()
        assert variazione["item"]["diff"] == "- vecchio\n+ nuovo"
        assert variazione["item"]["approveAction"].endswith(f"/aggiornamenti/{id_variazione}/approva")
        approvata = client.post(variazione["item"]["approveAction"], json={})
        assert approvata.status_code == 200, approvata.get_json()
        assert client.get(f"/api/v1/ui/ricerca-legale/aggiornamenti/{id_variazione}").get_json()["item"]["status"] == "applied"
        # Una variazione già applicata non si approva due volte.
        assert client.post(variazione["item"]["approveAction"], json={}).status_code == 409
        pagina = client.get(f"/ricerca-legale/daily/update/{id_variazione}/diff", headers=HTML)
        assert "iusentra-react-bootstrap" in pagina.get_data(as_text=True)


def test_fonte_del_registro_mostra_lo_storico_della_fonte_giornaliera_dello_stesso_sito(tmp_path):
    from legal_intelligence.engine import LegalIntelligenceDailyEngine

    app = _app_sessione(tmp_path)
    with app.test_request_context():
        from web.blueprints.legal_intelligence import _daily_db_path

        db = _daily_db_path()
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    motore = LegalIntelligenceDailyEngine(db)
    giornaliera = next(f for f in motore.sources if "normattiva" in f.url)
    motore.store.create_update({"source_id": giornaliera.id, "title": "Variazione Normattiva", "new_sha256": "e" * 64})
    with app.test_client() as client:
        _login(client)
        scheda = client.get("/api/v1/ui/ricerca-legale/fonti/normattiva").get_json()
        assert scheda["ok"] is True
        assert any(voce["id"] == giornaliera.id for voce in scheda["item"]["dailySources"])
        assert [u["title"] for u in scheda["item"]["updates"]] == ["Variazione Normattiva"]
        # La fonte del controllo giornaliero ha anche una scheda propria.
        propria = client.get(f"/api/v1/ui/ricerca-legale/fonti/{giornaliera.id}").get_json()
        assert propria["ok"] is True and propria["item"]["channel"] == "controllo giornaliero"


def test_cruscotto_del_controllo_giornaliero(tmp_path, monkeypatch):
    from legal_intelligence.engine import LegalIntelligenceDailyEngine

    avviati = []
    monkeypatch.setattr(LegalIntelligenceDailyEngine, "run_daily_sync", lambda self, **_kw: avviati.append(True) or {})
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        cruscotto = client.get("/api/v1/ui/ricerca-legale/controllo-giornaliero").get_json()
        assert cruscotto["ok"] is True and cruscotto["counts"]["sources"] >= 1
        assert all(fonte["href"].startswith("/ricerca-legale/fonte/") for fonte in cruscotto["sources"])
        avvio = client.post(cruscotto["runAction"], json={})
        assert avvio.status_code in {200, 202} and avvio.get_json()["ok"] is True
    import time

    for _ in range(50):
        if avviati:
            break
        time.sleep(0.05)
    assert avviati == [True]
