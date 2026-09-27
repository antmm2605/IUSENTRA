"""Migrazione React: studi, utenti degli studi, archivio e account di piattaforma.

Le pagine `/admin/studi`, `/admin/studi/nuovo`, `/admin/studi/<slug>`,
`/admin/studi/<slug>/utenti`, `/admin/studi/<slug>/database` e
`/admin/utenti-piattaforma` si aprono nell'applicazione React di piattaforma;
dati e azioni passano da `/api/v1/ui/piattaforma/<pagina>` con i parametri di
percorso (`slug`) nella richiesta e nei parametri di ogni azione, e chiamano gli
stessi servizi delle rotte storiche di `web/blueprints/admin.py`.
"""

from __future__ import annotations

from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.tenant import GestioneTenant
from tests.test_migrazione_react_piattaforma import _app, _login_superadmin
from tests.test_studio_site import _seed_tenant_admin

BASE = "/api/v1/ui/piattaforma"
SLUG = "studio-react-prova"


def _pagina(client, chiave: str, slug: str = "", **query) -> dict:
    parametri = {**({"slug": slug} if slug else {}), **query}
    risposta = client.get(f"{BASE}/{chiave}", query_string=parametri)
    assert risposta.status_code == 200, (chiave, risposta.status_code)
    corpo = risposta.get_json()
    assert corpo["ok"] is True, corpo
    return corpo


def _azione(client, chiave: str, nome: str, *, slug: str = "", params=None, values=None) -> dict:
    parametri = {**(params or {}), **({"slug": slug} if slug else {})}
    risposta = client.post(
        f"{BASE}/{chiave}/azioni/{nome}",
        query_string={"slug": slug} if slug else {},
        json={"params": parametri, "values": values or {}},
    )
    assert risposta.status_code == 200, (chiave, nome, risposta.status_code)
    return risposta.get_json()


def _azioni(sezioni: list[dict]) -> list[dict]:
    trovate = []
    for sezione in sezioni:
        trovate += sezione.get("items", []) if sezione["kind"] == "actions" else []
        trovate += [sezione["action"]] if sezione["kind"] == "form" else []
        for riga in sezione.get("rows", []) if sezione["kind"] == "table" else []:
            trovate += riga.get("actions", [])
    return trovate


def _studio(app, slug: str = SLUG):
    return _seed_tenant_admin(app, studio_nome="Studio React Prova", studio_slug=slug, username="admin-react")


def _tm(app) -> GestioneTenant:
    return GestioneTenant(app.config["TENANTS_REGISTRY"])


# ------------------------------------------------------------------ lettura


def test_elenco_dettaglio_utenti_e_archivio_dal_servizio(tmp_path: Path):
    app = _app(tmp_path)
    studio, admin = _studio(app)
    with app.test_client() as client:
        _login_superadmin(client)
        elenco = _pagina(client, "studi")
        righe = [r for s in elenco["sections"] if s["kind"] == "table" for r in s["rows"]]
        assert any(r["href"] == f"/admin/studi/{SLUG}" for r in righe)
        assert elenco["filter"]["name"] == "q"
        filtrato = _pagina(client, "studi", q="nessun-riscontro")
        assert not [r for s in filtrato["sections"] if s["kind"] == "table" for r in s["rows"]]
        assert "Nessuno studio trovato." in str(filtrato["sections"])
        vai = _azione(client, "studi", "filtra", values={"q": "react", "stato": "TRIAL", "piano": ""})
        assert vai["ok"] is True and vai["navigate"] == "/admin/studi?q=react&stato=TRIAL"

        dettaglio = _pagina(client, "studio", SLUG)
        assert dettaglio["title"] == "Studio React Prova"
        chiavi = {a["key"] for a in _azioni(dettaglio["sections"])}
        assert {"impersona", "modifica", "sospendi", "moduli", "piano", "rigenera-api-key"} <= chiavi
        assert all(a["params"]["slug"] == SLUG for a in _azioni(dettaglio["sections"]))
        # La chiave riservata non compare nei dati della pagina.
        assert _tm(app).get(SLUG).api_key not in str(dettaglio)

        utenti = _pagina(client, "studio-utenti", SLUG)
        righe = [r for s in utenti["sections"] if s["kind"] == "table" for r in s["rows"]]
        assert any("admin-react" in r["cells"]["user"] for r in righe)

        archivio = _pagina(client, "studio-database", SLUG)
        campi = next(s for s in archivio["sections"] if s["kind"] == "form")["fields"]
        password = next(c for c in campi if c["name"] == "db_password")
        assert password["kind"] == "password" and password["value"] == ""

        assente = _pagina(client, "studio", "studio-inesistente")
        assert "non trovato" in str(assente["sections"]).lower()


def test_pagine_riservate_al_superamministratore(tmp_path: Path):
    from tests.test_revisione_2410_sicurezza import _app as _app_sessione
    from tests.test_topbar_operational_api import _login

    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        for chiave in ("studi", "studio-nuovo", "studio", "studio-utenti", "studio-database", "utenti-piattaforma"):
            assert client.get(f"{BASE}/{chiave}", query_string={"slug": SLUG}).status_code == 403, chiave
        assert client.post(f"{BASE}/studio/azioni/sospendi", json={"params": {"slug": SLUG}, "values": {}}).status_code == 403


# ------------------------------------------------------------------ studi


def test_crea_studio_come_la_rotta_storica(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        modulo = next(s for s in _pagina(client, "studio-nuovo")["sections"] if s["kind"] == "form")
        assert {"nome", "slug", "piano", "db_mode", "admin_username", "admin_password"} <= {c["name"] for c in modulo["fields"]}

        assert _azione(client, "studio-nuovo", "crea", values={"nome": "", "slug": ""})["message"] == "Nome e slug sono obbligatori."
        assert "password" in _azione(client, "studio-nuovo", "crea", values={"nome": "Studio Nuovo", "slug": "studio-nuovo-react"})["message"]

        valori = {"nome": "Studio Nuovo", "slug": "studio-nuovo-react", "piano": "TRIAL", "db_mode": "SQLITE", "admin_username": "amministratore", "admin_password": "PasswordSicura!123", "admin_nome": "", "admin_email": ""}
        creato = _azione(client, "studio-nuovo", "crea", values=valori)
        assert creato["ok"] is True and creato["navigate"] == "/admin/studi/studio-nuovo-react"
        assert "PasswordSicura" not in str(creato)
        studio = _tm(app).get("studio-nuovo-react")
        assert studio is not None and studio.database.normalized_mode == "SQLITE"
        percorsi = _tm(app).percorsi_dati("studio-nuovo-react")
        gu = GestioneUtenti(db_path=percorsi["AUTH_DB"], audit_path=percorsi["AUDIT_DB"], secret_key=app.secret_key, crea_admin_se_vuoto=False)
        assert gu.get_by_username("amministratore").ruolo == RuoloUtente.AMMINISTRATORE

        doppione = _azione(client, "studio-nuovo", "crea", values=valori)
        assert doppione["ok"] is False and "già in uso" in doppione["message"]

        postgres = _azione(client, "studio-nuovo", "crea", values={**valori, "slug": "studio-pg-react", "piano": "ENTERPRISE", "db_mode": "POSTGRESQL"})
        assert postgres["navigate"] == "/admin/studi/studio-pg-react/database"


def test_modifica_piano_sospensione_e_chiave_riservata(tmp_path: Path):
    app = _app(tmp_path)
    _studio(app)
    with app.test_client() as client:
        _login_superadmin(client)
        dettaglio = _pagina(client, "studio", SLUG)
        modifica = next(a for a in _azioni(dettaglio["sections"]) if a["key"] == "modifica")
        valori = {c["name"]: c["value"] for c in modifica["fields"]}
        assert valori["nome"] == "Studio React Prova"
        valori.update(pec="studio.react@pec.example.it", note_admin="Nota di prova")
        assert _azione(client, "studio", "modifica", slug=SLUG, values=valori)["message"] == "Dati studio aggiornati."
        studio = _tm(app).get(SLUG)
        assert studio.pec == "studio.react@pec.example.it" and studio.nome == "Studio React Prova"

        moduli = _azione(client, "studio", "moduli", slug=SLUG, values={"modulo_fascicoli": True, "modulo_agenda": True, "modulo_pec": False})
        assert moduli["message"] == "Moduli aggiornati: 2 attivi."
        assert _tm(app).get(SLUG).moduli_override == ["fascicoli", "agenda"]

        piano = _azione(client, "studio", "piano", slug=SLUG, values={"piano": "PROFESSIONAL"})
        assert piano["ok"] is True and "Professional" in piano["message"]
        studio = _tm(app).get(SLUG)
        assert studio.piano == "PROFESSIONAL" and studio.stato == "ATTIVO" and studio.moduli_override == []

        sospeso = _azione(client, "studio", "sospendi", slug=SLUG)
        assert sospeso["tone"] == "warning" and _tm(app).get(SLUG).stato == "SOSPESO"
        assert _azione(client, "studio", "impersona", slug=SLUG)["ok"] is False
        assert _azione(client, "studio", "riattiva", slug=SLUG)["ok"] is True and _tm(app).get(SLUG).stato == "ATTIVO"

        vecchia = _tm(app).get(SLUG).api_key
        rigenera = next(a for a in _azioni(_pagina(client, "studio", SLUG)["sections"]) if a["key"] == "rigenera-api-key")
        assert rigenera["confirm"]
        esito = _azione(client, "studio", "rigenera-api-key", slug=SLUG)
        nuova = _tm(app).get(SLUG).api_key
        assert esito["ok"] is True and nuova != vecchia and nuova in str(esito["sections"])
        # Dopo la rigenerazione la chiave non torna nei dati della pagina.
        assert nuova not in str(_pagina(client, "studio", SLUG))

        assert _azione(client, "studio", "sospendi", slug="studio-inesistente")["message"] == "Studio non trovato."


def test_impersonazione_scrive_la_sessione_storica(tmp_path: Path):
    app = _app(tmp_path)
    _, admin = _studio(app)
    with app.test_client() as client:
        _login_superadmin(client)
        with client.session_transaction() as sessione:
            superadmin_id = sessione["user_id"]
        esito = _azione(client, "studio", "impersona", slug=SLUG)
        assert esito["ok"] is True and esito["navigate"] == "/"
        with client.session_transaction() as sessione:
            assert sessione["superadmin_user_id"] == superadmin_id
            assert sessione["user_id"] == admin.id
            assert sessione["tenant_slug"] == SLUG and sessione["auth_tenant_slug"] == SLUG
            assert sessione["auth_scope"] == "tenant"


# ------------------------------------------------------------------ utenti dello studio


def test_utenti_dello_studio_crea_disattiva_elimina(tmp_path: Path):
    app = _app(tmp_path)
    _studio(app)
    _tm(app).aggiorna_piano(SLUG, "PROFESSIONAL")
    with app.test_client() as client:
        _login_superadmin(client)
        assert _azione(client, "studio-utenti", "nuovo", slug=SLUG, values={"username": "", "password": ""})["message"] == "Nome utente e password sono obbligatori."
        creato = _azione(client, "studio-utenti", "nuovo", slug=SLUG, values={"username": "segreteria-react", "password": "PasswordSicura!123", "ruolo": "SEGRETERIA"})
        assert creato["ok"] is True and "segreteria-react" in creato["message"]
        assert _azione(client, "studio-utenti", "nuovo", slug=SLUG, values={"username": "secondo-admin", "password": "PasswordSicura!123", "ruolo": "SUPERADMIN"})["ok"] is True

        pagina = _pagina(client, "studio-utenti", SLUG)
        righe = [r for s in pagina["sections"] if s["kind"] == "table" for r in s["rows"]]
        # Nessun SUPERADMIN dentro uno studio: il ruolo diventa AMMINISTRATORE.
        assert next(r for r in righe if "secondo-admin" in r["cells"]["user"])["cells"]["role"] == "AMMINISTRATORE"
        riga = next(r for r in righe if "segreteria-react" in r["cells"]["user"])
        assert riga["cells"]["role"] == "SEGRETERIA"
        per_chiave = {a["key"]: a for a in riga["actions"]}
        assert per_chiave["elimina"]["confirm"] and per_chiave["elimina"]["params"]["slug"] == SLUG

        disattiva = _azione(client, "studio-utenti", "attiva-disattiva", slug=SLUG, params=per_chiave["attiva-disattiva"]["params"])
        assert disattiva["message"] == "Utente 'segreteria-react' disattivato."
        reset = _azione(client, "studio-utenti", "reset-password", slug=SLUG, params=per_chiave["reset-password"]["params"], values={"nuova_password": "AltraPassword!456"})
        assert reset["ok"] is True and "AltraPassword" not in str(reset)
        elimina = _azione(client, "studio-utenti", "elimina", slug=SLUG, params=per_chiave["elimina"]["params"])
        assert elimina["ok"] is True and elimina["tone"] == "warning"
        assert "segreteria-react" not in str(_pagina(client, "studio-utenti", SLUG)["sections"])

        estraneo = _azione(client, "studio-utenti", "elimina", slug=SLUG, params={"uid": "inesistente"})
        assert estraneo["ok"] is False and estraneo["message"] == "Utente non trovato in questo studio."


# ------------------------------------------------------------------ archivio


def test_archivio_salva_senza_esporre_la_password(tmp_path: Path):
    app = _app(tmp_path)
    _studio(app)
    with app.test_client() as client:
        _login_superadmin(client)
        vietato = _azione(client, "studio-database", "salva", slug=SLUG, values={"db_mode": "JSON"})
        assert vietato["ok"] is False and "SQLite a JSON" in vietato["message"]

        salvato = _azione(client, "studio-database", "salva", slug=SLUG, values={"db_mode": "POSTGRESQL", "host": "db.example.test", "porta": "5433", "db_name": "studio", "db_utente": "studio", "db_password": "Segreta!789", "pool_size": "5", "pool_timeout": "30", "ssl": True})
        assert salvato["ok"] is True
        db = _tm(app).get(SLUG).database
        assert db.normalized_mode == "POSTGRESQL" and db.password == "Segreta!789" and db.ssl is True and db.porta == 5433

        # Password vuota: resta quella salvata, come nella vista storica.
        _azione(client, "studio-database", "salva", slug=SLUG, values={"db_mode": "POSTGRESQL", "host": "db.example.test", "db_password": "", "ssl": True})
        assert _tm(app).get(SLUG).database.password == "Segreta!789"

        pagina = _pagina(client, "studio-database", SLUG)
        assert "Segreta!789" not in str(pagina)
        assert {"test", "attiva-postgres", "ripara-runtime"} <= {a["key"] for a in _azioni(pagina["sections"])}

        riparazione = _azione(client, "studio-database", "ripara-runtime", slug=SLUG)
        assert riparazione["sections"]


# ------------------------------------------------------------------ account di piattaforma


def test_account_di_piattaforma_modifica(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        pagina = _pagina(client, "utenti-piattaforma")
        righe = [r for s in pagina["sections"] if s["kind"] == "table" for r in s["rows"]]
        superadmin = next(r for r in righe if "superadmin-operativo" in r["cells"]["user"])
        modifica = next(a for a in superadmin["actions"] if a["key"] == "modifica")
        valori = {c["name"]: c["value"] for c in modifica["fields"]}
        assert valori["attivo"] is True
        esito = _azione(client, "utenti-piattaforma", "modifica", params=modifica["params"], values={**valori, "nome_completo": "Superamministratore di prova"})
        assert esito["ok"] is True and "aggiornato" in esito["message"]
        disattiva = _azione(client, "utenti-piattaforma", "modifica", params=modifica["params"], values={**valori, "attivo": False})
        assert disattiva["ok"] is False and "non può essere disattivato" in disattiva["message"]

        gu = GestioneUtenti(db_path=app.config["AUTH_DB"], audit_path=app.config["AUDIT_DB"], secret_key=app.secret_key, crea_admin_se_vuoto=False)
        assert gu.get_by_username("superadmin-operativo").nome_completo == "Superamministratore di prova"


def test_trasferimento_superadmin_chiude_la_sessione(tmp_path: Path):
    app = _app(tmp_path)
    gu = GestioneUtenti(db_path=app.config["AUTH_DB"], audit_path=app.config["AUDIT_DB"], secret_key=app.secret_key, crea_admin_se_vuoto=False)
    destinazione = next(u for u in gu.lista() if u.username == "admin-operativo")
    with app.test_client() as client:
        _login_superadmin(client)
        esito = _azione(client, "utenti-piattaforma", "trasferisci-superadmin", params={"uid": destinazione.id}, values={"ruolo_superadmin_precedente": "AMMINISTRATORE"})
        assert esito["ok"] is True and esito["navigate"] == "/login"
        with client.session_transaction() as sessione:
            assert "user_id" not in sessione
        assert client.get(f"{BASE}/utenti-piattaforma").status_code == 401
