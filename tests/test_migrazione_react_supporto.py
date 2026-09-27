"""Migrazione React: console «Assistenza remota» del pannello di piattaforma.

`/admin/supporto-remoto` si apre nell'applicazione React di piattaforma con i
dati di `/api/v1/ui/piattaforma/supporto-remoto`, calcolati da
`build_support_console_payload`; le azioni chiamano gli stessi servizi dei
gestori storici di `web/blueprints/support_remote.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from tests.test_migrazione_react_piattaforma import _app, _login_superadmin
from web.services.support_runtime import support_repository

PAGINA = "/api/v1/ui/piattaforma/supporto-remoto"
SEGRETO = "support-secret-demo"


def _azione(client, azione: str, values: dict | None = None, params: dict | None = None):
    risposta = client.post(f"{PAGINA}/azioni/{azione}", json={"params": params or {}, "values": values or {}})
    assert risposta.status_code == 200, risposta.get_data(as_text=True)
    return risposta.get_json()


def _sezione(corpo: dict, titolo: str) -> dict:
    return next(s for s in corpo["sections"] if s["title"].startswith(titolo))


def _crea(client, **values) -> tuple[dict, str]:
    corpo = _azione(client, "crea-sessione", values)
    assert corpo["ok"] is True, corpo
    sessione = next(i["value"] for i in _sezione(corpo, "Link cliente da copiare")["items"] if i["label"] == "Sessione")
    return corpo, sessione


def _impostazioni(client, **valori) -> dict:
    base = {"stun_urls": "", "turn_urls": "", "turn_shared_secret": "", "turn_ttl_seconds": "3600", "ws_token_max_age": "43200", "advanced_url_template": ""}
    return _azione(client, "configurazione", {**base, **valori})


def test_console_nella_applicazione_react(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        html = client.get("/admin/supporto-remoto").get_data(as_text=True)
        assert 'id="piattaforma-react-root"' in html and 'data-pagina="supporto-remoto"' in html
        classica = client.get("/admin/supporto-remoto?_legacy=1").get_data(as_text=True)
        assert "Assistenza remota cliente" in classica and "piattaforma-react-root" not in classica
        menu = client.get(PAGINA).get_json()["menu"]
        assert {"key": "supporto-remoto", "label": "Assistenza remota", "href": "/admin/supporto-remoto"} in menu


def test_pagina_con_elenco_dettaglio_e_audit(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        vuota = client.get(PAGINA).get_json()
        assert vuota["ok"] is True and vuota["title"] == "Assistenza remota cliente"
        assert _sezione(vuota, "Richieste dallo studio")["rows"] == []
        assert not any(s["title"].startswith("Audit sessione") for s in vuota["sections"])

        _, public_id = _crea(client, customer_name="Mario Rossi", customer_email="mario@example.it", studio_nome="Studio Rossi", practice_label="RG 1025/2024")
        corpo = client.get(f"{PAGINA}?sessione={public_id}").get_json()

    assert corpo["ok"] is True
    kinds = {"metrics", "status", "table", "facts", "notes", "shortcuts", "actions", "form"}
    assert all(s["kind"] in kinds for s in corpo["sections"])
    assert corpo["filter"]["name"] == "q"
    riga = _sezione(corpo, "Richieste dallo studio")["rows"][0]
    assert riga["cells"]["customer"] == "Mario Rossi"
    assert riga["cells"]["practice"] == "RG 1025/2024 · Studio Rossi"
    assert riga["cells"]["state"].startswith("Creata") and riga["href"] == f"/admin/supporto-remoto?sessione={public_id}"
    dettaglio = {i["label"]: i["value"] for i in _sezione(corpo, "Richiesta selezionata")["items"]}
    assert dettaglio["Cliente"] == "Mario Rossi" and dettaglio["Email"] == "mario@example.it"
    assert dettaglio["Studio"] == "Studio Rossi" and dettaglio["Avviata"] == "—"
    stanze = {r["cells"]["link"]: r for r in _sezione(corpo, "Stanze della sessione")["rows"]}
    operatore = stanze["Prendi in carico nella stanza operatore"]
    assert operatore["href"] == f"/support/operatore/{public_id}" and operatore["external"] is True
    assert stanze["Apri link cliente"]["href"].startswith("/support/join/") and stanze["Apri link cliente"]["external"] is True
    audit = _sezione(corpo, "Audit sessione")["rows"]
    assert audit and audit[-1]["cells"]["event"] == "session_created"
    comandi = {a["key"] for a in _sezione(corpo, "Gestione della sessione")["items"]}
    assert comandi == {"stato", "note", "chiudi", "cancella"}
    assert _sezione(corpo, "Sessione manuale")["kind"] == "form"
    assert _sezione(corpo, "Notifiche cellulare SUPERADMIN")["items"][0]["statusLabel"] == "SERVER DA CONFIGURARE"


def test_crea_sessione_restituisce_i_collegamenti(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        corpo, public_id = _crea(client, customer_name="Cliente Collegamenti", practice_label="Pratica ordinaria", notes="Verifica PEC")
        righe = {r["cells"]["link"]: r for r in _sezione(corpo, "Collegamenti della nuova sessione")["rows"]}
        stanza = righe["Apri stanza operatore"]
        # Il link firmato apre la stanza operatore come il `operator_url` storico.
        indirizzo = urlsplit(stanza["href"])
        aperta = client.get(f"{indirizzo.path}?{indirizzo.query}")

    assert corpo["message"].startswith("Sessione creata.")
    assert stanza["external"] is True and indirizzo.path == f"/support/operatore/{public_id}" and "token=" in indirizzo.query
    assert aperta.status_code == 200
    with app.app_context():
        riga = support_repository().get_session_by_public_id(public_id)
        eventi = [e["event_type"] for e in support_repository().list_events(public_id)]
    assert righe["Link cliente"]["external"] is True and righe["Link cliente"]["href"].endswith(f"/support/join/{riga['client_token']}")
    assert righe["Apri sessione in cabina"]["href"] == f"/admin/supporto-remoto?sessione={public_id}"
    assert riga["created_by"] == riga["assigned_to"] and riga["notes"] == "Verifica PEC"
    assert "session_created" in eventi


def test_cambia_stato_note_e_chiusura(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        _, public_id = _crea(client, customer_name="Cliente Stato")
        non_valido = _azione(client, "stato", {"status": "archiviata"}, {"public_id": public_id})
        assente = _azione(client, "stato", {"status": "active"}, {"public_id": "inesistente"})
        attiva = _azione(client, "stato", {"status": "active"}, {"public_id": public_id})
        nota = _azione(client, "note", {"notes": "Cliente guidato su sincronizzazione PEC."}, {"public_id": public_id})
        with app.app_context():
            assert support_repository().get_session_by_public_id(public_id)["status"] == "active"
        chiusa = _azione(client, "chiudi", params={"public_id": public_id})
        pagina = client.get(f"{PAGINA}?sessione={public_id}").get_json()

    assert (non_valido["ok"], non_valido["message"]) == (False, "Stato assistenza non valido.")
    assert (assente["ok"], assente["message"]) == (False, "Sessione assistenza non trovata.")
    assert attiva["ok"] is True and attiva["message"] == "Stato assistenza aggiornato."
    assert nota["ok"] is True and chiusa["ok"] is True and chiusa["message"] == "Sessione di assistenza chiusa."
    with app.app_context():
        riga = support_repository().get_session_by_public_id(public_id)
        eventi = [e["event_type"] for e in support_repository().list_events(public_id)]
    assert riga["status"] == "closed" and riga["ended_at"] and riga["notes"] == "Cliente guidato su sincronizzazione PEC."
    assert {"status_changed", "note_updated", "session_closed"} <= set(eventi)
    # Sessione chiusa: niente più «Chiudi sessione», come il modello storico.
    assert "chiudi" not in {a["key"] for a in _sezione(pagina, "Gestione della sessione")["items"]}


def test_cancella_sessione_e_prove(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        _, prova = _crea(client, customer_name="Cliente prova cleanup", practice_label="E2E prova")
        _, operativa = _crea(client, customer_name="Cliente operativo", practice_label="Assistenza ordinaria")
        _, resta = _crea(client, customer_name="Cliente reale", practice_label="Assistenza ordinaria")
        cancellata = _azione(client, "cancella", params={"public_id": operativa})
        di_nuovo = _azione(client, "cancella", params={"public_id": operativa})
        pulizia = _azione(client, "cancella-prove")

    assert cancellata["ok"] is True and cancellata["message"] == "Sessione assistenza cancellata."
    assert (di_nuovo["ok"], di_nuovo["message"]) == (False, "Sessione assistenza non trovata.")
    assert pulizia["ok"] is True and pulizia["message"] == "Sessioni di prova cancellate: 1."
    with app.app_context():
        repo = support_repository()
        assert repo.get_session_by_public_id(prova) is None and repo.get_session_by_public_id(operativa) is None
        assert repo.get_session_by_public_id(resta) is not None


def test_configurazione_conserva_la_chiave_se_vuota(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        salvata = _impostazioni(
            client,
            stun_urls="stun:turn.example.it:3478",
            turn_urls="turn:turn.example.it:3478?transport=udp",
            turn_shared_secret=SEGRETO,
            advanced_url_template="https://support.example.it/advanced/{public_id}",
        )
        assert salvata["ok"] is True and salvata["message"] == "Configurazione assistenza remota aggiornata."
        assert app.config["SUPPORT_TURN_SHARED_SECRET"] == SEGRETO
        invariata = _impostazioni(client, turn_urls="turn:turn.example.it:3478?transport=udp", turn_ttl_seconds="7200")
        errata = _impostazioni(client, turn_ttl_seconds="non un numero")
        pagina = client.get(PAGINA)

    assert invariata["ok"] is True
    assert app.config["SUPPORT_TURN_SHARED_SECRET"] == SEGRETO
    assert app.config["SUPPORT_TURN_TTL_SECONDS"] == 7200
    assert errata["ok"] is False and errata["message"].startswith("Configurazione assistenza remota non salvata")
    # La chiave del relay non torna mai al browser.
    assert SEGRETO not in pagina.get_data(as_text=True)
    campi = {c["name"]: c for c in _sezione(pagina.get_json(), "Impostazioni rete avanzate")["fields"]}
    assert campi["turn_shared_secret"]["kind"] == "password" and campi["turn_shared_secret"]["value"] == ""
    assert campi["turn_shared_secret"]["help"] == "Chiave già presente. Lascia vuoto se non vuoi cambiarla."
    assert campi["turn_ttl_seconds"]["value"] == "7200"


def test_filtri_e_prova_notifiche(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        filtro = _azione(client, "filtra", {"q": "Rossi", "stato": "active"})
        senza = _azione(client, "filtra", {"q": "", "stato": ""})
        prova = _azione(client, "prova-notifica")
        filtrata = client.get(f"{PAGINA}?q=Rossi&stato=closed").get_json()
        sconosciuta = _azione(client, "inesistente")

    assert filtro["navigate"] == "/admin/supporto-remoto?q=Rossi&stato=active"
    assert senza["navigate"] == "/admin/supporto-remoto"
    assert prova["ok"] is True and prova["message"].startswith("Notifica interna creata")
    campi = {c["name"]: c["value"] for c in _sezione(filtrata, "Filtra le richieste")["fields"]}
    assert campi == {"q": "Rossi", "stato": "closed"}
    assert sconosciuta["ok"] is False


def _sessione(client, utente, *, superadmin=None, studio=None) -> None:
    with client.session_transaction() as sessione:
        sessione["user_id"] = utente.id
        sessione["auth_scope"] = "tenant" if studio else "global"
        sessione["auth_tenant_slug"] = studio.slug if studio else ""
        if studio:
            sessione["tenant_slug"] = studio.slug
        if superadmin is not None:
            sessione["superadmin_user_id"] = superadmin.id
        sessione["last_activity"] = datetime.now(UTC).isoformat()


def test_riservata_al_superamministratore(tmp_path: Path):
    from tests.test_support_remote import _seed_runtime

    app, _, studio, amministratore = _seed_runtime(tmp_path)
    with app.test_client() as client:
        _sessione(client, amministratore, studio=studio)
        assert client.get(PAGINA).status_code == 403
        assert client.post(f"{PAGINA}/azioni/cancella-prove", json={"params": {}, "values": {}}).status_code == 403
    with app.test_client() as anonimo:
        assert anonimo.get(PAGINA).status_code == 401


def test_superamministratore_che_impersona_uno_studio(tmp_path: Path):
    """Come `support_operator_identity_or_403`: la console resta al superamministratore
    anche mentre è dentro uno studio (richiede la correzione di `api_v1_piattaforma`)."""
    from tests.test_support_remote import _seed_runtime

    app, superadmin, studio, amministratore = _seed_runtime(tmp_path)
    with app.test_client() as client:
        _sessione(client, amministratore, superadmin=superadmin, studio=studio)
        pagina = client.get(PAGINA)
        creata = client.post(f"{PAGINA}/azioni/crea-sessione", json={"params": {}, "values": {"customer_name": "Mario Rossi"}})
        altra = client.get("/api/v1/ui/piattaforma/salute-sistema")

    assert pagina.status_code == 200 and pagina.get_json()["ok"] is True
    assert creata.status_code == 200 and creata.get_json()["ok"] is True
    # Le altre pagine del pannello restano al solo superamministratore collegato come tale.
    assert altra.status_code == 403
    with app.app_context():
        righe = support_repository().list_sessions(limit=5)
    assert righe[0]["studio_slug"] == studio.slug
