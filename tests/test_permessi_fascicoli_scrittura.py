"""Scritture dei fascicoli: ogni azione richiede il suo permesso (scrivi/archivia/elimina)."""

from __future__ import annotations

import json
from pathlib import Path

from pct.auth import RuoloUtente
from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, StatoFascicolo, TipoDocumento, TipoFascicolo
from tests.test_topbar_operational_api import _cfg_web, _create_user, _login
from web.app import create_app

JSON = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}


def _gestori(app):
    clienti = GestioneClienti(app.config["CLIENTI_DB"])
    fascicoli = GestioneFascicoli(
        app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    return clienti, fascicoli


def _app(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _create_user(app, "admin2", "Admin12345!")
    _create_user(app, "praticante", "Pratica123!", ruolo=RuoloUtente.PRATICANTE)
    _create_user(app, "avvocato", "Avvocato123!", ruolo=RuoloUtente.AVVOCATO)
    clienti, fascicoli = _gestori(app)
    cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Maria", cognome="Verdi")
    fascicolo = fascicoli.nuovo("Recupero credito Alfa", TipoFascicolo.CIVILE, id_cliente=cliente.id, nome_cliente=cliente.nome_completo)
    fascicoli.aggiungi_documento(fascicolo.id, "atto.pdf", TipoDocumento.ALTRO, b"contenuto")
    return app, cliente.id, fascicolo.id


def test_praticante_non_crea_archivia_ne_elimina(tmp_path):
    app, id_cliente, id_fasc = _app(tmp_path)
    with app.test_client() as client:
        _login(client, "praticante", "Pratica123!")
        richieste = [
            ("/fascicoli/nuovo", {"titolo": "Nuovo", "tipo": "CIVILE", "id_cliente": id_cliente}),
            (f"/fascicoli/{id_fasc}/modifica", {"titolo": "Cambiato"}),
            (f"/fascicoli/{id_fasc}/stato", {"stato": "SOSPESO"}),
            (f"/fascicoli/{id_fasc}/definisci", {"esito_finale": "x"}),
            (f"/fascicoli/{id_fasc}/conformita/controlli", {"enabled": "0"}),
            (f"/fascicoli/{id_fasc}/archivia", {}),
            (f"/fascicoli/{id_fasc}/ripristina", {}),
            (f"/fascicoli/{id_fasc}/elimina", {}),
        ]
        for percorso, dati in richieste:
            risposta = client.post(percorso, data=dati, headers=JSON)
            assert risposta.status_code == 403, percorso
            assert "permesso" in risposta.get_json()["message"]
        assert client.post(f"/api/v1/ui/fascicoli/{id_fasc}/stato", json={"stato": "archiviato"}).status_code == 403
    _, fascicoli = _gestori(app)
    fascicolo = fascicoli.get(id_fasc)
    assert fascicolo is not None and fascicolo.titolo == "Recupero credito Alfa"
    assert fascicolo.stato == StatoFascicolo.APERTO
    assert len(fascicoli.tutti()) == 1


def test_avvocato_archivia_ma_non_elimina(tmp_path):
    app, _, id_fasc = _app(tmp_path)
    with app.test_client() as client:
        _login(client, "avvocato", "Avvocato123!")
        assert client.post(f"/fascicoli/{id_fasc}/elimina", headers=JSON).status_code == 403
        risposta = client.post(f"/fascicoli/{id_fasc}/stato", data={"stato": "IN_CORSO"})
        assert risposta.status_code == 302
    _, fascicoli = _gestori(app)
    assert fascicoli.get(id_fasc).stato == StatoFascicolo.IN_CORSO


def test_eliminazione_con_permesso_lascia_audit_e_cestino(tmp_path):
    app, _, id_fasc = _app(tmp_path)
    with app.test_client() as client:
        _login(client, "admin2", "Admin12345!")
        risposta = client.post(f"/fascicoli/{id_fasc}/elimina", headers=JSON)
        assert risposta.status_code == 200 and risposta.get_json()["ok"] is True
    _, fascicoli = _gestori(app)
    assert fascicoli.get(id_fasc) is None
    eventi = json.loads(Path(app.config["AUDIT_DB"]).read_text(encoding="utf-8"))
    eventi = eventi if isinstance(eventi, list) else eventi.get("eventi", [])
    assert any(e.get("azione") == "fascicoli.elimina" and e.get("risorsa_id") == id_fasc for e in eventi)
    cestino = Path(app.config["FASCICOLI_DOCS"]) / GestioneFascicoli.CESTINO_FASCICOLI
    cartelle = [p for p in cestino.iterdir() if p.name.startswith(id_fasc)]
    assert len(cartelle) == 1
    scheda = json.loads((cartelle[0] / "fascicolo.json").read_text(encoding="utf-8"))
    assert scheda["id"] == id_fasc
    assert any(p.name != "fascicolo.json" for p in cartelle[0].rglob("*") if p.is_file())


def _avvocato_senza_archivio(app):
    from pct.auth import GestioneUtenti

    gestore = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        bootstrap_admin_password="admin",
        bootstrap_admin_credentials_path=app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"],
    )
    utente = next(u for u in gestore.tutti() if u.username == "avvocato")
    gestore.aggiorna_permessi(utente.id, [], ["fascicoli.archivia"])


def test_stato_archiviato_in_ogni_grafia_richiede_il_permesso(tmp_path):
    app, _, id_fasc = _app(tmp_path)
    _avvocato_senza_archivio(app)
    with app.test_client() as client:
        _login(client, "avvocato", "Avvocato123!")
        for grafia in ("archiviato", "ARCHIVIATO", " Archiviato ", "archiviato "):
            for chiave in ("stato", "status"):
                api = client.post(f"/api/v1/ui/fascicoli/{id_fasc}/stato", json={chiave: grafia})
                assert api.status_code == 403, (chiave, grafia, api.get_json())
            classica = client.post(f"/fascicoli/{id_fasc}/stato", data={"stato": grafia}, headers=JSON)
            assert classica.status_code == 403, grafia
    _, fascicoli = _gestori(app)
    assert fascicoli.get(id_fasc).stato == StatoFascicolo.APERTO


def test_riaprire_un_archiviato_richiede_il_permesso(tmp_path):
    app, _, id_fasc = _app(tmp_path)
    _, fascicoli = _gestori(app)
    fascicoli.cambia_stato(id_fasc, StatoFascicolo.ARCHIVIATO, note="test", avvocato="test")
    _avvocato_senza_archivio(app)
    with app.test_client() as client:
        _login(client, "avvocato", "Avvocato123!")
        for stato in ("aperto", "in_corso", "SOSPESO", " definito "):
            api = client.post(f"/api/v1/ui/fascicoli/{id_fasc}/stato", json={"stato": stato})
            assert api.status_code == 403, (stato, api.get_json())
            assert "riaprire" in api.get_json()["message"]
        for stato in ("APERTO", " in_corso ", "sospeso"):
            assert client.post(f"/fascicoli/{id_fasc}/stato", data={"stato": stato}, headers=JSON).status_code == 403, stato
    _, fascicoli = _gestori(app)
    assert fascicoli.get(id_fasc).stato == StatoFascicolo.ARCHIVIATO


def test_con_il_permesso_si_archivia_e_si_riapre(tmp_path):
    app, _, id_fasc = _app(tmp_path)
    with app.test_client() as client:
        _login(client, "avvocato", "Avvocato123!")
        archivia = client.post(f"/api/v1/ui/fascicoli/{id_fasc}/stato", json={"stato": " ARCHIVIATO "})
        assert archivia.status_code == 200, archivia.get_json()
        _, fascicoli = _gestori(app)
        assert fascicoli.get(id_fasc).stato == StatoFascicolo.ARCHIVIATO
        riapri = client.post(f"/fascicoli/{id_fasc}/stato", data={"stato": " aperto "})
        assert riapri.status_code == 302
    _, fascicoli = _gestori(app)
    assert fascicoli.get(id_fasc).stato == StatoFascicolo.APERTO
