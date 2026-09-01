"""Test per pct/condivisione.py — condivisione cartelle clienti."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pct.condivisione import (
    AccessoCondiviso,
    CondivisioneCartella,
    GestioneCondivisioni,
    RuoloCondivisione,
)


# ================================================================ Fixtures

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "condivisioni.json")


@pytest.fixture
def gc(db_path):
    return GestioneCondivisioni(db_path=db_path)


def _condividi(gc, id_cliente="c1", id_utente="u1", username="mario",
               nome="Mario Rossi", ruolo=RuoloCondivisione.LETTURA,
               da="admin", note=""):
    return gc.condividi(
        id_cliente=id_cliente,
        id_utente=id_utente,
        username=username,
        nome_completo=nome,
        ruolo=ruolo,
        condiviso_da=da,
        note=note,
    )


# ================================================================ RuoloCondivisione

def test_ruolo_include_gerarchia():
    assert RuoloCondivisione.GESTORE.include(RuoloCondivisione.LETTURA)
    assert RuoloCondivisione.GESTORE.include(RuoloCondivisione.SCRITTURA)
    assert RuoloCondivisione.GESTORE.include(RuoloCondivisione.GESTORE)
    assert RuoloCondivisione.SCRITTURA.include(RuoloCondivisione.LETTURA)
    assert RuoloCondivisione.SCRITTURA.include(RuoloCondivisione.SCRITTURA)
    assert not RuoloCondivisione.SCRITTURA.include(RuoloCondivisione.GESTORE)
    assert RuoloCondivisione.LETTURA.include(RuoloCondivisione.LETTURA)
    assert not RuoloCondivisione.LETTURA.include(RuoloCondivisione.SCRITTURA)


# ================================================================ AccessoCondiviso

def test_accesso_from_dict():
    d = {
        "id_utente": "u1",
        "username": "mario",
        "nome_completo": "Mario Rossi",
        "ruolo": "SCRITTURA",
        "condiviso_da": "admin",
        "data_condivisione": "2024-01-01T10:00:00",
        "note": "test",
    }
    a = AccessoCondiviso.from_dict(d)
    assert a.id_utente == "u1"
    assert a.ruolo == RuoloCondivisione.SCRITTURA
    assert a.note == "test"


def test_accesso_to_dict_ruolo_come_stringa():
    d = {
        "id_utente": "u1", "username": "x", "nome_completo": "",
        "ruolo": "GESTORE", "condiviso_da": "admin",
        "data_condivisione": "2024-01-01T10:00:00",
    }
    a = AccessoCondiviso.from_dict(d)
    assert a.to_dict()["ruolo"] == "GESTORE"


# ================================================================ CondivisioneCartella

def test_cartella_from_dict():
    d = {
        "id": "abc123",
        "id_cliente": "c1",
        "accessi": [],
        "creato_il": "2024-01-01T00:00:00",
        "modificato_il": "2024-01-01T00:00:00",
    }
    c = CondivisioneCartella.from_dict(d)
    assert c.id_cliente == "c1"
    assert c.accessi == []


def test_cartella_utente_trovato():
    c = CondivisioneCartella(id="x", id_cliente="c1")
    a = AccessoCondiviso(
        id_utente="u1", username="mario", nome_completo="Mario",
        ruolo=RuoloCondivisione.LETTURA, condiviso_da="admin",
        data_condivisione="2024-01-01T00:00:00",
    )
    c.accessi.append(a)
    assert c.utente("u1") is a


def test_cartella_utente_non_trovato():
    c = CondivisioneCartella(id="x", id_cliente="c1")
    assert c.utente("u_inesistente") is None


# ================================================================ GestioneCondivisioni — CRUD

def test_condividi_aggiunge_accesso(gc):
    _condividi(gc)
    collaboratori = gc.collaboratori_di("c1")
    assert len(collaboratori) == 1
    assert collaboratori[0].id_utente == "u1"


def test_condividi_persistenza(db_path):
    gc1 = GestioneCondivisioni(db_path=db_path)
    _condividi(gc1)
    gc2 = GestioneCondivisioni(db_path=db_path)
    assert len(gc2.collaboratori_di("c1")) == 1


def test_condividi_aggiorna_ruolo_esistente(gc):
    _condividi(gc, ruolo=RuoloCondivisione.LETTURA)
    _condividi(gc, ruolo=RuoloCondivisione.SCRITTURA)
    collab = gc.collaboratori_di("c1")
    assert len(collab) == 1
    assert collab[0].ruolo == RuoloCondivisione.SCRITTURA


def test_condividi_piu_utenti(gc):
    _condividi(gc, id_utente="u1", username="mario")
    _condividi(gc, id_utente="u2", username="luigi")
    assert len(gc.collaboratori_di("c1")) == 2


def test_revoca_rimuove_accesso(gc):
    _condividi(gc)
    assert gc.revoca("c1", "u1") is True
    assert len(gc.collaboratori_di("c1")) == 0


def test_revoca_record_vuoto_eliminato(gc):
    _condividi(gc)
    gc.revoca("c1", "u1")
    # Se non ci sono più accessi, il record deve essere eliminato
    assert gc.n_collaboratori("c1") == 0


def test_revoca_utente_inesistente(gc):
    assert gc.revoca("c_inesistente", "u_inesistente") is False


def test_revoca_tutti(gc):
    _condividi(gc, id_utente="u1")
    _condividi(gc, id_utente="u2")
    n = gc.revoca_tutti("c1")
    assert n == 2
    assert gc.n_collaboratori("c1") == 0


def test_revoca_parziale_mantiene_altri(gc):
    _condividi(gc, id_utente="u1")
    _condividi(gc, id_utente="u2")
    gc.revoca("c1", "u1")
    assert gc.n_collaboratori("c1") == 1
    assert gc.collaboratori_di("c1")[0].id_utente == "u2"


# ================================================================ GestioneCondivisioni — accesso

def test_ha_accesso_lettura(gc):
    _condividi(gc, ruolo=RuoloCondivisione.LETTURA)
    assert gc.ha_accesso("u1", "c1", RuoloCondivisione.LETTURA) is True


def test_ha_accesso_scrittura_con_lettura_nega(gc):
    _condividi(gc, ruolo=RuoloCondivisione.LETTURA)
    assert gc.ha_accesso("u1", "c1", RuoloCondivisione.SCRITTURA) is False


def test_ha_accesso_gestore_include_tutto(gc):
    _condividi(gc, ruolo=RuoloCondivisione.GESTORE)
    assert gc.ha_accesso("u1", "c1", RuoloCondivisione.LETTURA) is True
    assert gc.ha_accesso("u1", "c1", RuoloCondivisione.SCRITTURA) is True
    assert gc.ha_accesso("u1", "c1", RuoloCondivisione.GESTORE) is True


def test_ha_accesso_utente_senza_condivisione(gc):
    assert gc.ha_accesso("u_senza", "c1") is False


def test_ruolo_accesso_corretto(gc):
    _condividi(gc, ruolo=RuoloCondivisione.SCRITTURA)
    assert gc.ruolo_accesso("u1", "c1") == RuoloCondivisione.SCRITTURA


def test_ruolo_accesso_nessuno(gc):
    assert gc.ruolo_accesso("u_none", "c1") is None


# ================================================================ GestioneCondivisioni — query

def test_cartelle_condivise_con_utente(gc):
    _condividi(gc, id_cliente="c1", id_utente="u1")
    _condividi(gc, id_cliente="c2", id_utente="u1")
    _condividi(gc, id_cliente="c3", id_utente="u2")  # altro utente
    cartelle = gc.cartelle_condivise_con("u1")
    assert len(cartelle) == 2
    ids = {id_c for id_c, _ in cartelle}
    assert "c1" in ids and "c2" in ids


def test_ids_clienti_accessibili(gc):
    _condividi(gc, id_cliente="c1", id_utente="u1")
    _condividi(gc, id_cliente="c2", id_utente="u1")
    ids = gc.ids_clienti_accessibili("u1")
    assert ids == {"c1", "c2"}


def test_ids_clienti_accessibili_vuoto(gc):
    assert gc.ids_clienti_accessibili("u_nessuno") == set()


def test_clienti_condivisi_da_gestore(gc):
    _condividi(gc, id_cliente="c1", id_utente="gestore1",
               username="gestore1", ruolo=RuoloCondivisione.GESTORE)
    _condividi(gc, id_cliente="c1", id_utente="u2",
               username="u2", ruolo=RuoloCondivisione.LETTURA)
    risultato = gc.clienti_condivisi_da("gestore1")
    assert "c1" in risultato


def test_n_collaboratori(gc):
    assert gc.n_collaboratori("c1") == 0
    _condividi(gc, id_utente="u1")
    _condividi(gc, id_utente="u2")
    assert gc.n_collaboratori("c1") == 2


# ================================================================ GestioneCondivisioni — statistiche

def test_statistiche_vuoto(gc):
    s = gc.statistiche()
    assert s["cartelle_condivise"] == 0
    assert s["accessi_totali"] == 0
    assert s["per_ruolo"] == {}


def test_statistiche_con_dati(gc):
    _condividi(gc, id_cliente="c1", id_utente="u1", ruolo=RuoloCondivisione.LETTURA)
    _condividi(gc, id_cliente="c1", id_utente="u2", ruolo=RuoloCondivisione.SCRITTURA)
    _condividi(gc, id_cliente="c2", id_utente="u1", ruolo=RuoloCondivisione.GESTORE)
    s = gc.statistiche()
    assert s["cartelle_condivise"] == 2
    assert s["accessi_totali"] == 3
    assert s["per_ruolo"]["LETTURA"] == 1
    assert s["per_ruolo"]["SCRITTURA"] == 1
    assert s["per_ruolo"]["GESTORE"] == 1


# ================================================================ Route web

@pytest.fixture
def client_web(tmp_path):
    """Client Flask con avvocato autenticato."""
    from web.app import create_app
    from pct.auth import GestioneUtenti, RuoloUtente

    auth_db = str(tmp_path / "utenti.json")
    audit_db = str(tmp_path / "audit.json")
    os.makedirs(str(tmp_path / "backup"), exist_ok=True)

    gu = GestioneUtenti(db_path=auth_db, audit_path=audit_db, secret_key="test")
    gu.crea(username="avvocato", password="Avv12345!", ruolo=RuoloUtente.AVVOCATO, email="av@b.it")
    gu.crea(username="collab1", password="Col12345!", ruolo=RuoloUtente.COLLABORATORE, email="c@b.it")

    cfg = {
        "TESTING": True, "SECRET_KEY": "test",
        "AUTH_DB": auth_db, "AUDIT_DB": audit_db,
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "BACKUP_DIR": str(tmp_path / "backup"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
    }
    app = create_app(cfg)
    with app.test_client() as c:
        c.post("/login", data={"username": "avvocato", "password": "Avv12345!"}, follow_redirects=True)
        yield c, gu, cfg


def test_cartelle_condivise_route(client_web):
    c, gu, cfg = client_web
    r = c.get("/cartelle-condivise")
    assert r.status_code == 200
    html = r.data.decode()
    assert 'class="react-shell-document"' in html
    assert 'id="root"' in html


def test_gestione_collaboratori_cliente_inesistente(client_web):
    c, _gu, _cfg = client_web
    page = c.get("/clienti/id_inesistente/collaboratori")
    api = c.get("/api/v1/clienti/id_inesistente/condivisioni")

    assert page.status_code == 200
    assert 'class="react-shell-document"' in page.get_data(as_text=True)
    assert 'id="root"' in page.get_data(as_text=True)
    assert api.status_code == 404
    assert api.get_json()["errore"] == "Cliente non trovato."


def test_gestione_collaboratori_cliente_esistente(client_web, tmp_path):
    c, _gu, cfg = client_web
    from pct.clienti import GestioneClienti, TipoCliente

    with c.application.app_context():
        cliente = c.application.extensions["core_runtime"]["get_clienti"]().nuovo(
            tipo=TipoCliente.PERSONA_FISICA,
            nome="Test", cognome="Cliente",
        )

    page = c.get(f"/clienti/{cliente.id}/collaboratori")
    api = c.get(f"/api/v1/clienti/{cliente.id}/condivisioni")

    assert page.status_code == 200
    assert 'class="react-shell-document"' in page.get_data(as_text=True)
    assert api.status_code == 200
    payload = api.get_json()
    assert payload["client"]["id"] == cliente.id
    assert payload["client"]["name"] == "Cliente Test"
    assert payload["permissions"]["canManage"] is True
    assert payload["contracts"]["mock_fallback"] is False
    assert any(item["username"] == "collab1" for item in payload["availableUsers"])


def test_aggiungi_collaboratore_via_api_react(client_web, tmp_path):
    c, gu, cfg = client_web
    from pct.clienti import GestioneClienti, TipoCliente
    from pct.condivisione import GestioneCondivisioni

    with c.application.app_context():
        cliente = c.application.extensions["core_runtime"]["get_clienti"]().nuovo(
            tipo=TipoCliente.PERSONA_FISICA,
            nome="Test",
            cognome="CLI",
        )
    collab = gu.get_by_username("collab1")

    response = c.post(
        f"/api/v1/clienti/{cliente.id}/condivisioni",
        json={
            "id_utente": collab.id,
            "ruolo": "LETTURA",
            "data_scadenza": "",
            "note": "Supporto istruttoria",
            "tags": ["istruttoria"],
        },
    )

    assert response.status_code == 201
    assert response.get_json()["stato"] == "ok"
    with c.application.app_context():
        condivisioni = c.application.extensions["core_runtime"]["get_condivisioni"]()
        assert condivisioni.ha_accesso(collab.id, cliente.id, RuoloCondivisione.LETTURA)


def test_revoca_collaboratore_via_api_react(client_web, tmp_path):
    c, gu, cfg = client_web
    from pct.clienti import GestioneClienti, TipoCliente
    from pct.condivisione import GestioneCondivisioni

    with c.application.app_context():
        cliente = c.application.extensions["core_runtime"]["get_clienti"]().nuovo(
            tipo=TipoCliente.PERSONA_FISICA,
            nome="Test",
            cognome="CLI2",
        )
        collab = gu.get_by_username("collab1")
        c.application.extensions["core_runtime"]["get_condivisioni"]().condividi(
            cliente.id,
            collab.id,
            "collab1",
            "Collab 1",
            RuoloCondivisione.LETTURA,
            "avvocato",
        )

    response = c.delete(f"/api/v1/clienti/{cliente.id}/condivisioni/{collab.id}")

    assert response.status_code == 200
    assert response.get_json()["stato"] == "ok"
    with c.application.app_context():
        updated = c.application.extensions["core_runtime"]["get_condivisioni"]()
        assert not updated.ha_accesso(collab.id, cliente.id)
