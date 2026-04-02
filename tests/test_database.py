"""Test per il modulo pct/database.py — gestione e analisi del database."""

from __future__ import annotations

import json
import os
import sqlite3
import zipfile
from pathlib import Path

import pytest

from pct.database import (
    GestioneDatabase,
    StatisticheModulo,
    ProblemaIntegrita,
    RisultatoOttimizzazione,
    RisultatoMigrazione,
    _fmt_bytes,
)


# ================================================================ Fixtures

def _scrivi_json(path: Path, dati):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dati, ensure_ascii=False, indent=2))


@pytest.fixture
def percorsi(tmp_path):
    """Crea i file JSON minimi per tutti i moduli."""
    clienti = [
        {"id": "c1", "nome": "Mario", "cognome": "Rossi", "codice_fiscale": "RSSMRO80A01H501A", "email": "mario@example.com"},
        {"id": "c2", "nome": "Lucia", "cognome": "Bianchi", "codice_fiscale": "BNCLCU85B02H502B", "email": "lucia@example.com"},
    ]
    fascicoli = [
        {"id": "f1", "numero": "2024/001", "titolo": "Causa Rossi", "id_cliente": "c1"},
        {"id": "f2", "numero": "2024/002", "titolo": "Consulenza Bianchi", "id_cliente": "c2"},
    ]
    appuntamenti = [{"id": "a1", "titolo": "Udienza", "data": "2024-06-01", "id_cliente": "c1"}]
    scadenze = [
        {"id": "s1", "titolo": "Memoria", "data_scadenza": "2024-07-01", "id_fascicolo": "f1",
         "tipo": "UDIENZA", "priorita": "ALTA", "perentorio": True, "completata": False},
    ]
    messaggi = [{"id": "m1", "oggetto": "Info", "id_cliente": "c1", "id_fascicolo": "f1"}]
    utenti = [
        {"id": "u1", "username": "admin", "email": "admin@studio.it", "ruolo": "AMMINISTRATORE",
         "attivo": True, "password_hash": "$2b$12$fakehashfortest"},
        {"id": "u2", "username": "seg", "email": "seg@studio.it", "ruolo": "SEGRETERIA",
         "attivo": True, "password_hash": "$2b$12$fakehashfortest"},
    ]
    audit = [
        {"id": "au1", "azione": "clienti.crea", "utente": "admin", "timestamp": "2024-06-01T10:00:00", "esito": "successo"},
        {"id": "au2", "azione": "fascicoli.leggi", "utente": "admin", "timestamp": "2024-06-01T11:00:00", "esito": "successo"},
        {"id": "au3", "azione": "clienti.crea", "utente": "seg", "timestamp": "2024-06-01T10:30:00", "esito": "successo"},
        {"id": "au4", "azione": "auth.login", "utente": "seg", "timestamp": "2024-06-01T09:00:00", "esito": "ERRORE"},
    ]

    base = tmp_path
    paths = {
        "clienti": str(base / "clienti.json"),
        "fascicoli": str(base / "fascicoli.json"),
        "appuntamenti": str(base / "agenda.json"),
        "scadenze": str(base / "scadenze.json"),
        "messaggi": str(base / "messaggi.json"),
        "utenti": str(base / "utenti.json"),
        "audit": str(base / "audit.json"),
        "search_index": str(base / "search.db"),
    }

    _scrivi_json(Path(paths["clienti"]), clienti)
    _scrivi_json(Path(paths["fascicoli"]), fascicoli)
    _scrivi_json(Path(paths["appuntamenti"]), appuntamenti)
    _scrivi_json(Path(paths["scadenze"]), scadenze)
    _scrivi_json(Path(paths["messaggi"]), messaggi)
    _scrivi_json(Path(paths["utenti"]), utenti)
    _scrivi_json(Path(paths["audit"]), audit)

    return paths


@pytest.fixture
def db(percorsi):
    return GestioneDatabase(percorsi)


# ================================================================ _fmt_bytes

def test_fmt_bytes_bytes():
    assert _fmt_bytes(512) == "512 B"

def test_fmt_bytes_kb():
    assert "KB" in _fmt_bytes(2048)

def test_fmt_bytes_mb():
    assert "MB" in _fmt_bytes(2 * 1024 ** 2)

def test_fmt_bytes_gb():
    assert "GB" in _fmt_bytes(2 * 1024 ** 3)


# ================================================================ StatisticheModulo

def test_statistiche_modulo_dimensione_leggibile():
    s = StatisticheModulo(nome="clienti", percorso="/tmp/c.json", esiste=True, dimensione_bytes=2048)
    assert "KB" in s.dimensione_leggibile


# ================================================================ statistiche() — moduli come dict

def test_statistiche_moduli_count(db):
    stats = db.statistiche()
    assert "moduli" in stats
    assert len(stats["moduli"]) >= 1

def test_statistiche_totale_record(db):
    stats = db.statistiche()
    assert stats["totale_record"] >= 2

def test_statistiche_totale_dimensione(db):
    stats = db.statistiche()
    assert stats["totale_dimensione_bytes"] > 0
    # dimensione_leggibile è in chiave 'totale_dimensione' (non 'totale_dimensione_leggibile')
    key = "totale_dimensione" if "totale_dimensione" in stats else "totale_dimensione_leggibile"
    assert isinstance(stats[key], str)

def test_statistiche_modulo_clienti_ok(db):
    stats = db.statistiche()
    # moduli è una lista di dict
    modulo_clienti = next((m for m in stats["moduli"] if m["nome"] == "clienti"), None)
    assert modulo_clienti is not None
    assert modulo_clienti["stato"] == "OK"
    assert modulo_clienti["record_totali"] == 2

def test_statistiche_modulo_mancante(tmp_path):
    paths = {"clienti": str(tmp_path / "nonexistent.json")}
    db2 = GestioneDatabase(paths)
    stats = db2.statistiche()
    mod = stats["moduli"][0]
    assert mod["stato"] in ("NON_TROVATO", "ERRORE", "VUOTO")

def test_statistiche_modulo_vuoto(tmp_path):
    p = tmp_path / "clienti.json"
    _scrivi_json(p, [])
    db2 = GestioneDatabase({"clienti": str(p)})
    stats = db2.statistiche()
    mod = stats["moduli"][0]
    assert mod["stato"] in ("VUOTO", "OK")
    assert mod["record_totali"] == 0

def test_statistiche_include_modulo_extra_monitorato(tmp_path):
    p = tmp_path / "preventivi.json"
    _scrivi_json(p, [{"id": "pr1", "oggetto": "Preventivo"}])
    db2 = GestioneDatabase({"preventivi": str(p)})
    stats = db2.statistiche()
    modulo = next((m for m in stats["moduli"] if m["nome"] == "preventivi"), None)
    assert modulo is not None
    assert modulo["record_totali"] == 1
    assert modulo["migrabile_sqlite"] is False


# ================================================================ verifica_integrita()

def test_verifica_integrita_clean(db):
    problemi = db.verifica_integrita()
    critici = [p for p in problemi if p.severita == "CRITICO"]
    assert len(critici) == 0

def test_verifica_integrita_returns_list(db):
    problemi = db.verifica_integrita()
    assert isinstance(problemi, list)
    for p in problemi:
        assert isinstance(p, ProblemaIntegrita)
        assert p.severita in ("CRITICO", "AVVISO", "INFO")

def test_verifica_integrita_cf_duplicato(tmp_path):
    clienti = [
        {"id": "c1", "nome": "A", "cognome": "B", "codice_fiscale": "DUPDUP00A00H501Z"},
        {"id": "c2", "nome": "C", "cognome": "D", "codice_fiscale": "DUPDUP00A00H501Z"},
    ]
    p = tmp_path / "clienti.json"
    _scrivi_json(p, clienti)
    db2 = GestioneDatabase({"clienti": str(p)})
    problemi = db2.verifica_integrita()
    duplicati = [pr for pr in problemi if pr.tipo == "DUPLICATO" or "codice_fiscale" in pr.messaggio.lower() or "cf" in pr.messaggio.lower()]
    assert len(duplicati) >= 1

def test_verifica_integrita_fk_fascicolo_cliente_mancante(tmp_path):
    clienti = [{"id": "c1", "nome": "A", "cognome": "B"}]
    fascicoli = [{"id": "f1", "titolo": "T", "id_cliente": "c_INESISTENTE"}]
    _scrivi_json(tmp_path / "clienti.json", clienti)
    _scrivi_json(tmp_path / "fascicoli.json", fascicoli)
    db2 = GestioneDatabase({
        "clienti": str(tmp_path / "clienti.json"),
        "fascicoli": str(tmp_path / "fascicoli.json"),
    })
    problemi = db2.verifica_integrita()
    fk = [p for p in problemi if p.tipo == "RIFERIMENTO_MANCANTE"]
    assert len(fk) >= 1

def test_verifica_integrita_ha_modulo(db):
    problemi = db.verifica_integrita()
    for p in problemi:
        assert p.modulo != ""


# ================================================================ ottimizza()

def test_ottimizza_returns_list(db):
    risultati = db.ottimizza()
    assert isinstance(risultati, list)

def test_ottimizza_elementi_sono_risultati(db):
    risultati = db.ottimizza()
    for r in risultati:
        assert isinstance(r, RisultatoOttimizzazione)
        assert hasattr(r, "modulo")
        assert hasattr(r, "riuscita")
        assert hasattr(r, "operazione")

def test_ottimizza_json_non_rompe_file(tmp_path):
    p = tmp_path / "clienti.json"
    dati = [{"id": "c1", "nome": "Mario"}]
    p.write_text(json.dumps(dati, indent=8))
    db2 = GestioneDatabase({"clienti": str(p)})
    db2.ottimizza()
    # Il file deve essere ancora un JSON valido
    letti = json.loads(p.read_text())
    assert len(letti) == 1
    assert letti[0]["id"] == "c1"


# ================================================================ migra_verso_sqlite()

def test_migra_verso_sqlite_file_creato(db, tmp_path):
    dest = str(tmp_path / "migrato.db")
    db.migra_verso_sqlite(dest)
    assert Path(dest).exists()

def test_migra_verso_sqlite_returns_risultato(db, tmp_path):
    dest = str(tmp_path / "migrato.db")
    risultato = db.migra_verso_sqlite(dest)
    assert isinstance(risultato, RisultatoMigrazione)
    # Anche con qualche errore FK il file viene creato
    assert Path(dest).exists()

def test_migra_verso_sqlite_record_migrati_dict(db, tmp_path):
    dest = str(tmp_path / "migrato.db")
    risultato = db.migra_verso_sqlite(dest)
    # record_migrati è un dict {modulo: count}
    assert isinstance(risultato.record_migrati, dict)
    # clienti (2 record) devono essere migrati con successo
    assert risultato.record_migrati.get("clienti", 0) == 2

def test_migra_verso_sqlite_tabelle(db, tmp_path):
    dest = str(tmp_path / "migrato.db")
    db.migra_verso_sqlite(dest)
    conn = sqlite3.connect(dest)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "clienti" in tables

def test_migra_percorso_db(db, tmp_path):
    dest = str(tmp_path / "migrato.db")
    risultato = db.migra_verso_sqlite(dest)
    assert risultato.percorso_db == dest

def test_migra_ms_positivo(db, tmp_path):
    dest = str(tmp_path / "migrato.db")
    risultato = db.migra_verso_sqlite(dest)
    assert risultato.ms >= 0

def test_migra_verso_sqlite_sanifica_scadenza_orfana(tmp_path):
    _scrivi_json(tmp_path / "clienti.json", [{"id": "c1", "nome": "Mario"}])
    _scrivi_json(tmp_path / "fascicoli.json", [])
    _scrivi_json(tmp_path / "agenda.json", [])
    _scrivi_json(tmp_path / "scadenze.json", [{
        "id": "s_orfana",
        "titolo": "Scadenza orfana",
        "data_scadenza": "2024-07-01",
        "id_fascicolo": "f_missing",
        "id_appuntamento": "a_missing",
        "tipo": "ALTRO",
    }])
    _scrivi_json(tmp_path / "messaggi.json", [])
    _scrivi_json(tmp_path / "utenti.json", [])
    _scrivi_json(tmp_path / "audit.json", [])

    db2 = GestioneDatabase({
        "clienti": str(tmp_path / "clienti.json"),
        "fascicoli": str(tmp_path / "fascicoli.json"),
        "appuntamenti": str(tmp_path / "agenda.json"),
        "scadenze": str(tmp_path / "scadenze.json"),
        "messaggi": str(tmp_path / "messaggi.json"),
        "utenti": str(tmp_path / "utenti.json"),
        "audit": str(tmp_path / "audit.json"),
    })
    dest = str(tmp_path / "migrato.db")
    risultato = db2.migra_verso_sqlite(dest)
    assert risultato.riuscita is True
    assert risultato.errori == []
    assert any("scadenze/s_orfana" in avviso for avviso in risultato.avvisi)

    conn = sqlite3.connect(dest)
    row = conn.execute(
        "SELECT id_fascicolo, id_appuntamento FROM scadenze WHERE id = ?",
        ("s_orfana",),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] is None
    assert row[1] is None


# ================================================================ esporta_tutto()

def test_esporta_tutto_zip_creato(db, tmp_path):
    out_dir = str(tmp_path / "export")
    zip_path = db.esporta_tutto(out_dir)
    assert Path(zip_path).exists()
    assert zip_path.endswith(".zip")

def test_esporta_tutto_zip_valido(db, tmp_path):
    out_dir = str(tmp_path / "export")
    zip_path = db.esporta_tutto(out_dir)
    assert zipfile.is_zipfile(zip_path)

def test_esporta_tutto_contiene_manifest(db, tmp_path):
    out_dir = str(tmp_path / "export")
    zip_path = db.esporta_tutto(out_dir)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert any("manifest" in n for n in names)

def test_esporta_tutto_contiene_dati_clienti(db, tmp_path):
    out_dir = str(tmp_path / "export")
    zip_path = db.esporta_tutto(out_dir)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert any("clienti" in n for n in names)


# ================================================================ analisi_uso()

def test_analisi_uso_chiavi_principali(db):
    uso = db.analisi_uso()
    assert "azioni_frequenti" in uso
    assert "utenti_attivi" in uso
    assert "tasso_errori" in uso

def test_analisi_uso_totale_eventi(db):
    uso = db.analisi_uso()
    # totale_eventi (non totale_operazioni)
    assert uso.get("totale_eventi") == 4

def test_analisi_uso_azione_frequente(db):
    uso = db.analisi_uso()
    # azioni_frequenti è una lista di tuple (azione, count)
    af = uso["azioni_frequenti"]
    assert isinstance(af, list)
    azioni = {a for a, _ in af}
    assert "clienti.crea" in azioni
    count_crea = next(c for a, c in af if a == "clienti.crea")
    assert count_crea == 2

def test_analisi_uso_tasso_errori_calcolo(db):
    uso = db.analisi_uso()
    # 1 errore su 4 = 25%
    assert uso["tasso_errori"] == 25.0

def test_analisi_uso_audit_mancante(tmp_path):
    db2 = GestioneDatabase({"audit": str(tmp_path / "inesistente.json")})
    uso = db2.analisi_uso()
    assert uso.get("totale_eventi", 0) == 0


# ================================================================ statistiche_sqlite()

def test_statistiche_sqlite_None_se_non_esiste(db, tmp_path):
    info = db.statistiche_sqlite(str(tmp_path / "nonexistent.db"))
    assert info is None

def test_statistiche_sqlite_esistente(db, tmp_path):
    dest = str(tmp_path / "test.db")
    db.migra_verso_sqlite(dest)
    info = db.statistiche_sqlite(dest)
    assert info is not None
    assert info.get("esiste") is True
    assert "tabelle" in info
    assert info["frammentazione_pct"] >= 0


# ================================================================ Route web admin/database

@pytest.fixture
def client_admin(tmp_path):
    """Client Flask con utente admin autenticato."""
    from web.app import create_app
    from pct.auth import GestioneUtenti, RuoloUtente

    auth_db = str(tmp_path / "utenti.json")
    audit_db = str(tmp_path / "audit.json")
    backup_dir = str(tmp_path / "backup")
    os.makedirs(backup_dir, exist_ok=True)

    gu = GestioneUtenti(db_path=auth_db, audit_path=audit_db, secret_key="test")
    # GestioneUtenti crea un admin di default; usiamo quello aggiornando la password
    # oppure creiamo un secondo admin con username diverso
    gu.crea(username="testadmin", password="Admin1234!", ruolo=RuoloUtente.AMMINISTRATORE, email="a@b.it")

    cfg = {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": auth_db,
        "AUDIT_DB": audit_db,
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "BACKUP_DIR": backup_dir,
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
    }
    app = create_app(cfg)
    with app.test_client() as c:
        c.post("/login", data={"username": "testadmin", "password": "Admin1234!"}, follow_redirects=True)
        yield c


def test_admin_database_get(client_admin):
    r = client_admin.get("/admin/database")
    assert r.status_code == 200
    assert b"Database" in r.data

def test_admin_database_verifica_json(client_admin):
    r = client_admin.get("/admin/database/verifica")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert "problemi" in data

def test_admin_database_ottimizza_json(client_admin):
    r = client_admin.post("/admin/database/ottimizza")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert "risultati" in data

def test_admin_database_migra_json(client_admin):
    r = client_admin.post("/admin/database/migra")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert "record_migrati" in data
    assert "messaggio" in data
    assert "avvisi" in data

def test_admin_database_export_zip(client_admin):
    r = client_admin.get("/admin/database/export")
    assert r.status_code == 200
    assert r.content_type == "application/zip"
