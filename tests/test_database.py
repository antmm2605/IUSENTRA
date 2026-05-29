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
    bootstrap_moduli_monitorati,
    _fmt_bytes,
)
from pct.search_index import IndiceRicerca
from web.services.storage_runtime import get_request_studio_db


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
    privacy = {
        "tr1": {
            "id": "tr1",
            "nome": "Gestione pratiche",
            "finalita": "Assistenza legale",
            "categoria_dati": "anagrafici, giudiziari",
            "base_giuridica": "Contratto",
            "soggetti_interessati": "clienti",
            "destinatari": "interni studio",
            "attivo": True,
        }
    }
    notifiche = [
        {
            "ts": "2024-06-01T08:30:00",
            "tipo": "promemoria_appuntamento",
            "cliente": "Mario Rossi",
            "numero": "+393331234567",
            "esito": {"ok": True},
            "utente": "admin",
        }
    ]
    backup_registro = [
        {
            "id": "b1",
            "timestamp": "2024-06-01T04:00:00",
            "tipo": "COMPLETO",
            "stato": "OK",
            "percorso_file": "./backup/b1.zip",
            "hash_file": "abc123",
            "dimensione_bytes": 1024,
            "num_file": 3,
            "componenti": ["agenda", "fascicoli"],
            "cifrato": False,
        }
    ]
    backup_config = {
        "directory_backup": str(tmp_path / "backup"),
        "max_backup": 7,
        "frequenza": "GIORNALIERA",
        "backup_abilitato": True,
    }
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
        "privacy": str(base / "privacy.json"),
        "notifiche": str(base / "notifiche.json"),
        "backup": str(base / "backup" / "registro.json"),
        "search_index": str(base / "search.db"),
    }

    _scrivi_json(Path(paths["clienti"]), clienti)
    _scrivi_json(Path(paths["fascicoli"]), fascicoli)
    _scrivi_json(Path(paths["appuntamenti"]), appuntamenti)
    _scrivi_json(Path(paths["scadenze"]), scadenze)
    _scrivi_json(Path(paths["messaggi"]), messaggi)
    _scrivi_json(Path(paths["utenti"]), utenti)
    _scrivi_json(Path(paths["audit"]), audit)
    _scrivi_json(Path(paths["privacy"]), privacy)
    _scrivi_json(Path(paths["notifiche"]), notifiche)
    _scrivi_json(Path(paths["backup"]), backup_registro)
    _scrivi_json(Path(paths["backup"]).with_name("config.json"), backup_config)

    idx = IndiceRicerca(paths["search_index"])
    idx.indicizza(
        tipo="fascicolo",
        entity_id="f1",
        titolo="Causa Rossi",
        corpo="Vendita immobiliare e memoria ex art. 183",
        meta={"numero": "2024/001"},
    )
    idx.set_ocr_cache("hash-ocr-1", "testo OCR")
    idx._conn.execute(
        "INSERT OR REPLACE INTO meta_indice(chiave, valore) VALUES (?, ?)",
        ("ultimo_rebuild", "2024-06-01T00:00:00"),
    )
    idx._conn.commit()
    idx._conn.close()

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
    assert modulo["migrabile_sqlite"] is True


def test_statistiche_moduli_json_estesi_sono_migrabili(tmp_path):
    payloads = {
        "calendar_sync": {"profiles": [{"id": "cal-1", "provider": "google"}]},
        "condivisioni": {"link": {"lnk-1": {"id": "lnk-1"}}},
        "email_casella": {"inbox": [{"id": "msg-1", "oggetto": "PEC"}]},
        "email_ordinaria": [{"id": "mail-1", "oggetto": "Ordinaria"}],
        "giurisprudenza": [{"id": "g-1", "massima": "Massima interna"}],
        "legal_intelligence": {"monitor_runs": [{"id": "run-1"}]},
        "normative_tables": {"tables": [{"id": "tab-1"}]},
        "note_faldone": {},
        "portale": {"pst": {"attivo": True}},
        "redaction_assistant": [],
        "soggetti": [{"id": "sogg-1", "nome": "Mario Rossi"}],
        "soggetti_parti": {"parti": [{"id": "parte-1"}]},
        "template_atti": {"tpl-1": {"id": "tpl-1", "titolo": "Atto"}},
        "template_atti_prefs": {"editor_layout": {"tema": "chiaro"}},
        "validation_runs": {"runs": [{"id": "val-1"}]},
        "wizard_pro": [{"id": "wiz-1"}],
        "workspace_intelligence": {"snapshot": {"moduli": 2}},
    }
    paths = {}
    for module, payload in payloads.items():
        path = tmp_path / f"{module}.json"
        _scrivi_json(path, payload)
        paths[module] = str(path)

    db2 = GestioneDatabase(paths)
    stats = db2.statistiche()
    modules = {module["nome"]: module for module in stats["moduli"]}

    assert set(payloads).issubset(modules)
    for module in payloads:
        assert modules[module]["migrabile_sqlite"] is True


def test_bootstrap_moduli_monitorati_crea_file_mancanti(tmp_path):
    paths = {
        "appuntamenti": str(tmp_path / "agenda" / "appuntamenti.json"),
        "audit": str(tmp_path / "auth" / "audit.json"),
        "calendar_sync": str(tmp_path / "agenda" / "calendar_sync.json"),
        "condivisioni": str(tmp_path / "clienti" / "condivisioni.json"),
        "fascicoli": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "messaggi": str(tmp_path / "messaggi" / "storico.json"),
        "note_faldone": str(tmp_path / "clienti" / "note_faldone.json"),
        "notifiche": str(tmp_path / "notifiche" / "log.json"),
        "privacy": str(tmp_path / "privacy" / "registro.json"),
        "fatturazione": str(tmp_path / "fatturazione" / "parcelle.json"),
        "preventivi": str(tmp_path / "preventivi" / "preventivi.json"),
        "search_index": str(tmp_path / "search" / "index.db"),
        "wizard_pro": str(tmp_path / "wizard_pro" / "sessioni.json"),
        "utenti": str(tmp_path / "auth" / "utenti.json"),
        "backup": str(tmp_path / "backup" / "registro.json"),
        "legal_intelligence": str(tmp_path / "intelligence" / "motori.json"),
        "normative_tables": str(tmp_path / "intelligence" / "tabelle_normative.json"),
        "validation_runs": str(tmp_path / "intelligence" / "validation_runs.json"),
        "template_atti": str(tmp_path / "template_atti" / "templates.json"),
        "template_atti_prefs": str(tmp_path / "template_atti" / "editor_layout.json"),
        "redaction_assistant": str(tmp_path / "intelligence" / "assistente_redazionale.json"),
        "local_ai": str(tmp_path / "intelligence" / "local_ai.db"),
        "telematico": str(tmp_path / "telematico" / "workflow.db"),
    }

    creati = bootstrap_moduli_monitorati(paths)

    assert Path(paths["preventivi"]).exists()
    assert json.loads(Path(paths["appuntamenti"]).read_text(encoding="utf-8")) == {}
    assert json.loads(Path(paths["audit"]).read_text(encoding="utf-8")) == []
    assert json.loads(Path(paths["fascicoli"]).read_text(encoding="utf-8")) == {}
    assert json.loads(Path(paths["messaggi"]).read_text(encoding="utf-8")) == {}
    assert json.loads(Path(paths["notifiche"]).read_text(encoding="utf-8")) == []
    assert isinstance(json.loads(Path(paths["privacy"]).read_text(encoding="utf-8")), dict)
    assert json.loads(Path(paths["preventivi"]).read_text(encoding="utf-8")) == {}
    assert json.loads(Path(paths["utenti"]).read_text(encoding="utf-8")) == {}
    assert json.loads((tmp_path / "preventivi" / "conferimenti.json").read_text(encoding="utf-8")) == {}
    assert json.loads((tmp_path / "backup" / "registro.json").read_text(encoding="utf-8")) == []
    assert "directory_backup" in json.loads((tmp_path / "backup" / "config.json").read_text(encoding="utf-8"))
    assert json.loads(Path(paths["calendar_sync"]).read_text(encoding="utf-8")) == {"profiles": []}
    assert json.loads(Path(paths["condivisioni"]).read_text(encoding="utf-8")) == {
        "cartelle": {},
        "fascicoli": {},
        "link": {},
    }
    assert json.loads(Path(paths["validation_runs"]).read_text(encoding="utf-8")) == {"runs": []}
    assert json.loads(Path(paths["redaction_assistant"]).read_text(encoding="utf-8")) == []
    assert "tables" in json.loads(Path(paths["normative_tables"]).read_text(encoding="utf-8"))
    assert "monitor_runs" in json.loads(Path(paths["legal_intelligence"]).read_text(encoding="utf-8"))
    assert "editor_layout" in json.loads(Path(paths["template_atti_prefs"]).read_text(encoding="utf-8"))
    conn = sqlite3.connect(paths["search_index"])
    search_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert "meta_indice" in search_tables
    assert "ocr_cache" in search_tables
    assert "preventivi" in creati
    assert "normative_tables" in creati
    assert "privacy" in creati
    assert "search_index" in creati
    assert "local_ai" not in creati
    assert "telematico" not in creati
    assert not Path(paths["local_ai"]).exists()
    assert not Path(paths["telematico"]).exists()


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


def test_ripara_integrita_scollega_scadenze_orfane_con_backup(tmp_path):
    scadenze_path = tmp_path / "scadenze.json"
    _scrivi_json(tmp_path / "clienti.json", [])
    _scrivi_json(tmp_path / "fascicoli.json", [])
    _scrivi_json(tmp_path / "agenda.json", [])
    _scrivi_json(scadenze_path, [{
        "id": "s_orfana",
        "titolo": "Termine memoria",
        "data_scadenza": "2026-05-10",
        "id_fascicolo": "8946FCC7",
    }])
    _scrivi_json(tmp_path / "messaggi.json", [])

    db2 = GestioneDatabase({
        "clienti": str(tmp_path / "clienti.json"),
        "fascicoli": str(tmp_path / "fascicoli.json"),
        "appuntamenti": str(tmp_path / "agenda.json"),
        "scadenze": str(scadenze_path),
        "messaggi": str(tmp_path / "messaggi.json"),
    })

    assert any(p.modulo == "scadenze" and p.tipo == "RIFERIMENTO_MANCANTE" for p in db2.verifica_integrita())

    report = db2.ripara_integrita()
    scadenze = json.loads(scadenze_path.read_text(encoding="utf-8"))

    assert report["ok"] is True
    assert report["n_riparazioni"] == 1
    assert report["backup_files"]
    assert Path(report["backup_files"][0]).exists()
    assert scadenze[0]["id_fascicolo"] == ""
    assert "8946FCC7" in scadenze[0]["note"]
    assert scadenze[0]["riparazioni_integrita"]
    assert not [p for p in db2.verifica_integrita() if p.modulo == "scadenze" and p.tipo == "RIFERIMENTO_MANCANTE"]


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


def test_ottimizza_search_index_vacuum_fuori_transazione(db):
    risultati = db.ottimizza()
    indice = next(r for r in risultati if r.modulo == "search_index")

    assert indice.riuscita is True
    assert "cannot VACUUM" not in indice.dettagli
    assert indice.operazione == "VACUUM + ANALYZE + FTS optimize"


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
    assert "moduli_dati" in tables
    assert "moduli_json_records" in tables
    assert "privacy_trattamenti" in tables
    assert "notifiche_log" in tables
    assert "backup_records" in tables
    assert "backup_config" in tables
    assert "search_documenti" in tables
    assert "search_meta_indice" in tables
    assert "search_ocr_cache" in tables


def test_migra_verso_sqlite_migra_servizi_operativi_aggiuntivi(db, tmp_path):
    dest = str(tmp_path / "migrato.db")
    risultato = db.migra_verso_sqlite(dest)
    assert risultato.record_migrati.get("privacy", 0) == 1
    assert risultato.record_migrati.get("notifiche", 0) == 1
    assert risultato.record_migrati.get("backup", 0) == 1
    assert risultato.record_migrati.get("backup_config", 0) >= 1
    assert risultato.record_migrati.get("search_index", 0) == 1

    conn = sqlite3.connect(dest)
    counts = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM moduli_dati),
            (SELECT COUNT(*) FROM privacy_trattamenti),
            (SELECT COUNT(*) FROM notifiche_log),
            (SELECT COUNT(*) FROM backup_records),
            (SELECT COUNT(*) FROM backup_config),
            (SELECT COUNT(*) FROM search_documenti),
            (SELECT COUNT(*) FROM search_meta_indice),
            (SELECT COUNT(*) FROM search_ocr_cache)
        """
    ).fetchone()
    conn.close()

    assert counts is not None
    assert counts[0] >= 11
    assert counts[1:] == (1, 1, 1, 4, 1, 1, 1)


def test_migra_verso_sqlite_migra_moduli_json_estesi(tmp_path):
    payloads = {
        "calendar_sync": {"profiles": [{"id": "cal-1", "provider": "google"}]},
        "email_ordinaria": [
            {"id": "mail-1", "oggetto": "Primo messaggio"},
            {"id": "mail-2", "oggetto": "Secondo messaggio"},
        ],
        "giurisprudenza": [{"id": "g-1", "massima": "Massima interna"}],
        "normative_tables": {"tables": [{"id": "tab-1"}]},
        "soggetti": [{"id": "sogg-1", "nome": "Mario Rossi"}],
        "template_atti_prefs": {"editor_layout": {"tema": "chiaro"}},
        "workspace_intelligence": {"snapshot": {"moduli": 2}},
    }
    paths = {}
    for module, payload in payloads.items():
        path = tmp_path / f"{module}.json"
        _scrivi_json(path, payload)
        paths[module] = str(path)

    dest = str(tmp_path / "migrato.db")
    risultato = GestioneDatabase(paths).migra_verso_sqlite(dest)

    assert risultato.riuscita is True
    assert risultato.record_migrati["email_ordinaria"] == 2
    assert risultato.record_migrati["calendar_sync"] == 1
    assert risultato.record_migrati["moduli_json_records"] == 8

    conn = sqlite3.connect(dest)
    rows = dict(
        conn.execute(
            """
            SELECT modulo, COUNT(*)
            FROM moduli_json_records
            GROUP BY modulo
            """
        ).fetchall()
    )
    email_meta = conn.execute(
        "SELECT payload_json FROM moduli_dati WHERE nome = ?",
        ("email_ordinaria",),
    ).fetchone()
    email_payload = conn.execute(
        """
        SELECT payload_json
        FROM moduli_json_records
        WHERE modulo = ?
        ORDER BY record_index
        LIMIT 1
        """,
        ("email_ordinaria",),
    ).fetchone()
    conn.close()

    assert rows["email_ordinaria"] == 2
    assert rows["template_atti_prefs"] == 1
    assert json.loads(email_meta[0])["root_type"] == "list"
    assert json.loads(email_meta[0])["record_entries"] == 2
    assert json.loads(email_payload[0])["id"] == "mail-1"


def test_schema_moduli_json_records_presente_per_sqlite_e_postgresql():
    root = Path(__file__).resolve().parents[1]
    sqlite_sql = (root / "pct" / "sql" / "20260503_moduli_json_records.sql").read_text(encoding="utf-8")
    postgres_sql = (
        root / "pct" / "sql" / "20260503_moduli_json_records_postgres.sql"
    ).read_text(encoding="utf-8")

    for script in (sqlite_sql, postgres_sql):
        assert "CREATE TABLE IF NOT EXISTS moduli_dati" in script
        assert "CREATE TABLE IF NOT EXISTS moduli_json_records" in script
        assert "FOREIGN KEY (modulo) REFERENCES moduli_dati(nome) ON DELETE CASCADE" in script
        assert "idx_moduli_json_records_modulo" in script


def test_migra_verso_sqlite_crea_base_strutturale_procedurale_e_forense(db, tmp_path):
    dest = str(tmp_path / "migrato.db")
    db.migra_verso_sqlite(dest)
    conn = sqlite3.connect(dest)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    conn.close()

    assert "macro_aree" in tables
    assert "procedimenti" in tables
    assert "atti" in tables
    assert "procedimento_atto" in tables
    assert "fascicoli_strutturati" in tables
    assert "template_atto_versioni" in tables
    assert "forense_versioni" in tables
    assert "forense_tabelle" in tables
    assert "forense_fasi" in tables
    assert "forense_scaglioni_valore" in tables
    assert "forense_parametri_compenso" in tables
    assert "forense_spese_standard" in tables
    assert "procedimento_tariffario_map" in tables
    assert "pratiche_economiche" in tables
    assert "preventivi" in tables
    assert "preventivo_voci" in tables
    assert "preventivo_accessori" in tables
    assert "accordi_compenso" in tables
    assert "preventivo_snapshot" in tables
    assert "preventivo_accettazioni" in tables
    assert "controlli_forensi" in tables
    assert "preventivo_controllo_map" in tables


def test_migra_verso_sqlite_seed_macro_aree_e_portali_base(db, tmp_path):
    dest = str(tmp_path / "migrato.db")
    db.migra_verso_sqlite(dest)
    conn = sqlite3.connect(dest)

    macro_codes = {
        row[0]
        for row in conn.execute("SELECT codice FROM macro_aree").fetchall()
    }
    canali_codes = {
        row[0]
        for row in conn.execute("SELECT codice FROM portali_riti").fetchall()
    }
    conn.close()

    assert {
        # Macro-aree dominio legale (14 storiche)
        "civile",
        "penale",
        "amministrativo",
        "costituzionale",
        "commerciale",
        "lavoro",
        "tributario",
        "processuale_civile",
        "processuale_penale",
        "unione_europea",
        "internazionale",
        "famiglia",
        "societario",
        "crisi_impresa",
        # Macro-aree aggiunte (v2.109.6)
        "penale_difensivo",
        "societario_commerciale",
        "immigrazione_cittadinanza",
        # Macro-aree procedurali — allineamento NODE_CATALOG (v2.109.7)
        "esecuzione_civile",
        "previdenza_assistenza",
        "mediazione",
        "negoziazione_assistita",
        "arbitrato",
        "volontaria_giurisdizione",
        "corte_dei_conti",
        "giurisdizioni_superiori",
        "consulenza_contrattualistica",
        "servizi_professionali",
        "immobiliare_tavolare",
    }.issubset(macro_codes)
    assert {
        "PCT",
        "PST",
        "PAT",
        "PTT",
        "SIGIT",
        "REGISTRO_IMPRESE",
        "TELEMACO",
        "DIRE",
        "STRAGIUDIZIALE",
        "CARTACEO",
        "PEC",
    }.issubset(canali_codes)


def test_migra_verso_sqlite_seed_sottobranche_specifiche(db, tmp_path):
    """Le 24 sottobranche del NODE_CATALOG devono essere seedate nel DB."""
    dest = str(tmp_path / "migrato.db")
    db.migra_verso_sqlite(dest)
    conn = sqlite3.connect(dest)

    sub_codes = {
        row[0]
        for row in conn.execute("SELECT codice FROM sottobranche").fetchall()
    }
    conn.close()

    # Tutte e 24 le sottobranche specifiche del NODE_CATALOG
    assert {
        "COGNIZIONE_CREDITI",
        "LOCAZIONI_SFRATTI",
        "RESPONSABILITA_DANNI",
        "ISTR_PREV_CAUTELARE",
        "PARERI_DIFFIDE",
        "RECUPERO_STRAGIUD_SINISTRI",
        "FAMIGLIA_MINORI",
        "LAVORO_SUBORDINATO",
        "PREVIDENZA_ASSISTENZA",
        "PENALE_ORDINARIO",
        "GDP_MISURE_SORVEGLIANZA",
        "TAR_CDS",
        "CGT_PRIMO_SECONDO_GRADO",
        "PUBBLICITA_TAVOLARE",
        "ESECUZIONE_CIVILE",
        "ADS_TUTELA_CURATELA",
        "MEDIAZIONE_CIVILE",
        "NEGOZIAZIONE_ASSISTITA",
        "ARBITRATO_RITUALE_IRRITUALE",
        "CONSULENZA_CONTRATTI",
        "DOMICILIAZIONE_E_TEMPO",
        "CORTE_DEI_CONTI",
        "CORTE_COST_CEDU_CGUE",
        "LIQUIDAZIONE_E_PASSIVO",
    }.issubset(sub_codes)


def test_migra_verso_sqlite_seed_forense_minimo(db, tmp_path):
    dest = str(tmp_path / "migrato.db")
    db.migra_verso_sqlite(dest)
    conn = sqlite3.connect(dest)

    versioni = {
        row[0]
        for row in conn.execute("SELECT codice FROM forense_versioni").fetchall()
    }
    fasi = {
        row[0]
        for row in conn.execute("SELECT codice FROM forense_fasi").fetchall()
    }
    spese = {
        row[0]
        for row in conn.execute("SELECT codice FROM forense_spese_standard").fetchall()
    }
    controlli = {
        row[0]
        for row in conn.execute("SELECT codice FROM controlli_forensi").fetchall()
    }
    conn.close()

    assert "DM55_2014_DM147_2022" in versioni
    assert {
        "FASE_STUDIO",
        "FASE_INTRODUTTIVA",
        "FASE_ISTRUTTORIA",
        "FASE_DECISIONALE",
        "FASE_ESECUTIVA",
        "FASE_CAUTELARE",
        "FASE_MONITORIA",
        "FASE_IMPUGNAZIONE",
        "FASE_STRAGIUDIZIALE",
    }.issubset(fasi)
    assert {
        "SPESE_GENERALI_15",
        "CPA_4",
        "IVA_22",
        "CU_DEFAULT",
    }.issubset(spese)
    assert {
        "CHK_VALORE_PRATICA",
        "CHK_SCAGLIONE",
        "CHK_TABELLA_FORENSE",
        "CHK_EQUO_COMPENSO",
        "CHK_ACCESSORI",
        "CHK_SNAPSHOT",
        "CHK_ACCORDO_COMPENSO",
        "CHK_PREVENTIVO_FIRMABILE",
    }.issubset(controlli)


def test_migra_verso_sqlite_base_forense_restando_strutturale_non_popola_mappe(db, tmp_path):
    dest = str(tmp_path / "migrato.db")
    db.migra_verso_sqlite(dest)
    conn = sqlite3.connect(dest)
    counts = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM procedimenti),
            (SELECT COUNT(*) FROM atti),
            (SELECT COUNT(*) FROM allegati_obbligatori),
            (SELECT COUNT(*) FROM controlli_conformita),
            (SELECT COUNT(*) FROM procedimento_portale_rito),
            (SELECT COUNT(*) FROM procedimento_atto),
            (SELECT COUNT(*) FROM atto_allegato),
            (SELECT COUNT(*) FROM atto_controllo),
            (SELECT COUNT(*) FROM fascicoli_strutturati),
            (SELECT COUNT(*) FROM template_atto_versioni),
            (SELECT COUNT(*) FROM forense_tabelle),
            (SELECT COUNT(*) FROM forense_scaglioni_valore),
            (SELECT COUNT(*) FROM forense_parametri_compenso),
            (SELECT COUNT(*) FROM forense_maggiorazioni_riduzioni),
            (SELECT COUNT(*) FROM forense_regole_applicative),
            (SELECT COUNT(*) FROM procedimento_tariffario_map),
            (SELECT COUNT(*) FROM atto_fase_tariffaria_map),
            (SELECT COUNT(*) FROM pratiche_economiche),
            (SELECT COUNT(*) FROM preventivi),
            (SELECT COUNT(*) FROM preventivo_voci),
            (SELECT COUNT(*) FROM preventivo_accessori),
            (SELECT COUNT(*) FROM accordi_compenso),
            (SELECT COUNT(*) FROM preventivo_snapshot),
            (SELECT COUNT(*) FROM preventivo_accettazioni),
            (SELECT COUNT(*) FROM preventivo_controllo_map)
        """
    ).fetchone()
    conn.close()

    assert counts is not None
    assert all(count == 0 for count in counts)

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


def test_migra_verso_sqlite_blocca_svuotamento_db_operativo_esistente(tmp_path):
    clienti_path = tmp_path / "clienti" / "anagrafica.json"
    fascicoli_path = tmp_path / "fascicoli" / "fascicoli.json"
    studio_db = tmp_path / "studio.db"
    _scrivi_json(
        clienti_path,
        {
            "CLI001": {
                "id": "CLI001",
                "nome": "Giuseppe",
                "cognome": "Montagnese",
                "codice_fiscale": "MNTGPP70A01H501Z",
            }
        },
    )
    _scrivi_json(
        fascicoli_path,
        {
            "FASC001": {
                "id": "FASC001",
                "numero": "1/2026",
                "titolo": "Pratica da preservare",
                "id_cliente": "CLI001",
            }
        },
    )

    iniziale = GestioneDatabase({
        "clienti": str(clienti_path),
        "fascicoli": str(fascicoli_path),
    }).migra_verso_sqlite(str(studio_db))
    assert iniziale.riuscita is True

    _scrivi_json(clienti_path, {})
    _scrivi_json(fascicoli_path, {})
    bloccato = GestioneDatabase({
        "clienti": str(clienti_path),
        "fascicoli": str(fascicoli_path),
    }).migra_verso_sqlite(str(studio_db))

    assert bloccato.riuscita is False
    assert any("Blocco anti-perdita su clienti" in errore for errore in bloccato.errori)
    assert bloccato.audit["precheck"]["modules"]["clienti"]["status"] == "blocked"

    conn = sqlite3.connect(studio_db)
    counts = conn.execute(
        "SELECT (SELECT COUNT(*) FROM clienti), (SELECT COUNT(*) FROM fascicoli)"
    ).fetchone()
    conn.close()
    assert counts == (1, 1)


def test_preverifica_attivazione_sqlite_reporta_blocco_anti_perdita(tmp_path):
    clienti_path = tmp_path / "clienti" / "anagrafica.json"
    studio_db = tmp_path / "studio.db"
    _scrivi_json(
        clienti_path,
        {
            "CLI001": {"id": "CLI001", "nome": "Anna", "cognome": "Rossi"},
            "CLI002": {"id": "CLI002", "nome": "Luca", "cognome": "Bianchi"},
        },
    )
    iniziale = GestioneDatabase({"clienti": str(clienti_path)}).migra_verso_sqlite(str(studio_db))
    assert iniziale.riuscita is True

    _scrivi_json(clienti_path, {"CLI001": {"id": "CLI001", "nome": "Anna", "cognome": "Rossi"}})
    report = GestioneDatabase({"clienti": str(clienti_path)}).preverifica_attivazione_sqlite(str(studio_db))

    assert report["ok"] is False
    assert report["stato"] == "Bloccata per protezione dati"
    assert report["record_migrati"] == 0
    assert "riconciliazione sicura" in report["azione_consigliata"]
    modulo = report["audit_migrazione"]["precheck"]["modules"]["clienti"]
    assert modulo["status"] == "blocked"
    assert modulo["existing_sqlite_count"] == 2
    assert modulo["json_count"] == 1
    assert modulo["only_database_count"] == 1


def test_riconcilia_verso_sqlite_preserva_database_e_importa_solo_sorgente(tmp_path):
    clienti_path = tmp_path / "clienti" / "anagrafica.json"
    studio_db = tmp_path / "studio.db"
    iniziali = {
        f"CLI{i:03d}": {"id": f"CLI{i:03d}", "nome": f"Nome {i}", "cognome": "Esistente"}
        for i in range(1, 26)
    }
    _scrivi_json(clienti_path, iniziali)
    primo = GestioneDatabase({"clienti": str(clienti_path)}).migra_verso_sqlite(str(studio_db))
    assert primo.riuscita is True

    sorgente_ridotta = {
        **{
            f"CLI{i:03d}": {"id": f"CLI{i:03d}", "nome": f"Nome {i}", "cognome": "Esistente"}
            for i in range(1, 9)
        },
        "CLI999": {"id": "CLI999", "nome": "Nuovo", "cognome": "Solo Sorgente"},
    }
    _scrivi_json(clienti_path, sorgente_ridotta)
    riconciliato = GestioneDatabase({"clienti": str(clienti_path)}).riconcilia_verso_sqlite(str(studio_db))

    assert riconciliato.riuscita is True
    assert riconciliato.audit["precheck"]["modules"]["clienti"]["status"] == "blocked"
    assert riconciliato.audit["reconciliation"]["executed"] is True
    assert Path(riconciliato.audit["reconciliation"]["backup_db"]).exists()

    conn = sqlite3.connect(studio_db)
    count, nuovo = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN id = 'CLI999' THEN 1 ELSE 0 END) FROM clienti"
    ).fetchone()
    conn.close()
    assert count == 26
    assert nuovo == 1


def test_migra_verso_sqlite_preserva_payload_completo_e_timer_topbar(tmp_path):
    clienti_path = tmp_path / "clienti" / "anagrafica.json"
    fascicoli_path = tmp_path / "fascicoli" / "fascicoli.json"
    timer_path = tmp_path / "timesheet" / "time_tracking.json"
    email_path = tmp_path / "email" / "ordinaria.json"
    studio_db = tmp_path / "studio.db"
    cliente = {
        "id": "CLI100",
        "nome": "Laura",
        "cognome": "Verdi",
        "recapiti": {"telefono_principale": "3330000000", "pec": "laura@example.pec.it"},
        "campi_ui": {"origine": "form-anagrafica", "preferenza": "email"},
    }
    fascicolo = {
        "id": "FAS100",
        "numero": "100/2026",
        "titolo": "Verifica campi UI",
        "id_cliente": "CLI100",
        "documenti": [{"id": "DOC1", "nome_file": "atto.pdf", "tag_ui": ["principale"]}],
        "scadenze_interne": [{"id": "SC1", "titolo": "Deposito"}],
    }
    timer = {
        "id": "TMR100",
        "user_id": "USR1",
        "username": "admin",
        "case_id": "FAS100",
        "client_id": "CLI100",
        "activity_type": "drafting",
        "description": "Redazione atto",
        "started_at": "2026-05-29T08:00:00Z",
        "elapsed_seconds": 120,
        "status": "paused",
        "created_at": "2026-05-29T08:00:00Z",
        "updated_at": "2026-05-29T08:02:00Z",
    }
    email = {"id": "MAIL100", "oggetto": "Messaggio", "campi_ui": {"cartella": "INBOX"}}
    _scrivi_json(clienti_path, {"CLI100": cliente})
    _scrivi_json(fascicoli_path, {"FAS100": fascicolo})
    _scrivi_json(timer_path, {"TMR100": timer})
    _scrivi_json(email_path, [email])

    risultato = GestioneDatabase({
        "clienti": str(clienti_path),
        "fascicoli": str(fascicoli_path),
        "time_tracking": str(timer_path),
        "email_ordinaria": str(email_path),
    }).migra_verso_sqlite(str(studio_db))

    assert risultato.riuscita is True
    assert risultato.audit["validation"]["ok"] is True
    assert risultato.record_migrati["time_tracking"] == 1
    assert risultato.record_migrati["email_ordinaria"] == 1

    conn = sqlite3.connect(studio_db)
    cliente_payload = json.loads(conn.execute(
        "SELECT dati_json FROM clienti WHERE id = ?",
        ("CLI100",),
    ).fetchone()[0])
    fascicolo_payload = json.loads(conn.execute(
        "SELECT dati_json FROM fascicoli WHERE id = ?",
        ("FAS100",),
    ).fetchone()[0])
    timer_payload = json.loads(conn.execute(
        "SELECT dati_json FROM time_tracking_timers WHERE id = ?",
        ("TMR100",),
    ).fetchone()[0])
    email_payload = json.loads(conn.execute(
        """
        SELECT payload_json
        FROM moduli_json_records
        WHERE modulo = ? AND record_key LIKE ?
        """,
        ("email_ordinaria", "%MAIL100"),
    ).fetchone()[0])
    conn.close()

    assert cliente_payload["campi_ui"]["origine"] == "form-anagrafica"
    assert fascicolo_payload["documenti"][0]["tag_ui"] == ["principale"]
    assert timer_payload["description"] == "Redazione atto"
    assert email_payload["campi_ui"]["cartella"] == "INBOX"


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


def test_statistiche_sqlite_non_marca_assente_se_vtable_search_fallisce(db, tmp_path, monkeypatch):
    db_path = tmp_path / "snapshot.db"
    db_path.write_bytes(b"sqlite placeholder")

    class FakeCursor:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

        def fetchone(self):
            return self.rows[0] if self.rows else None

    class FakeConnection:
        closed = False

        def execute(self, sql: str):
            if "FROM sqlite_master" in sql:
                return FakeCursor([("clienti",), ("search_documenti",)])
            if 'COUNT(*) FROM "clienti"' in sql:
                return FakeCursor([(2,)])
            if 'COUNT(*) FROM "search_documenti"' in sql:
                raise sqlite3.DatabaseError("vtable constructor failed: search_documenti")
            if sql == "PRAGMA page_size":
                return FakeCursor([(4096,)])
            if sql == "PRAGMA page_count":
                return FakeCursor([(4,)])
            if sql == "PRAGMA freelist_count":
                return FakeCursor([(1,)])
            raise AssertionError(sql)

        def close(self):
            self.closed = True

    fake = FakeConnection()
    monkeypatch.setattr(sqlite3, "connect", lambda *_args, **_kwargs: fake)

    info = db.statistiche_sqlite(str(db_path))

    assert info is not None
    assert info["esiste"] is True
    assert info["tabelle"]["clienti"] == 2
    assert info["tabelle"]["search_documenti"] == 0
    assert "Snapshot presente con avvisi" in info["errore"]
    assert "search_documenti" in info["errori_tabelle"]
    assert fake.closed is True


# ================================================================ Route web admin/database

def test_create_app_bootstrap_moduli_monitorati(tmp_path):
    from web.app import create_app
    from pct.auth import GestioneUtenti, RuoloUtente

    auth_db = str(tmp_path / "auth" / "utenti.json")
    audit_db = str(tmp_path / "auth" / "audit.json")
    clienti_db = str(tmp_path / "clienti" / "anagrafica.json")
    studio_db = get_request_studio_db(clienti_db)
    gu = GestioneUtenti(
        db_path=auth_db,
        audit_path=audit_db,
        secret_key="test",
        crea_admin_se_vuoto=False,
        studio_db=studio_db,
    )
    gu.crea(username="bootstrap", password="Admin1234!", ruolo=RuoloUtente.AMMINISTRATORE, email="bootstrap@test.it")

    cfg = {
        "TESTING": True,
        "MULTI_TENANT": False,
        "SECRET_KEY": "test",
        "AUTH_DB": auth_db,
        "AUDIT_DB": audit_db,
        "CLIENTI_DB": clienti_db,
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi" / "storico.json"),
        "NOTIFICHE_LOG": str(tmp_path / "notifiche" / "log.json"),
        "PRIVACY_DB": str(tmp_path / "privacy" / "registro.json"),
        "SEARCH_INDEX": str(tmp_path / "search" / "index.db"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(tmp_path / "fascicoli" / "archivio"),
        "BACKUP_DIR": str(tmp_path / "backup"),
        "PORTALE_DB": str(tmp_path / "portale" / "portali.json"),
        "FATTURAZIONE_DB": str(tmp_path / "fatturazione" / "parcelle.json"),
        "PREVENTIVI_DB": str(tmp_path / "preventivi" / "preventivi.json"),
        "CONDIVISIONI_DB": str(tmp_path / "clienti" / "condivisioni.json"),
        "NOTE_FALDONE_DB": str(tmp_path / "clienti" / "note_faldone.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "WIZARD_PRO_DB": str(tmp_path / "wizard_pro" / "sessioni.json"),
        "LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json"),
        "NORMATIVE_TABLES_DB": str(tmp_path / "intelligence" / "tabelle_normative.json"),
        "VALIDATION_RUNS_DB": str(tmp_path / "intelligence" / "validation_runs.json"),
        "REDACTION_ASSISTANT_DB": str(tmp_path / "intelligence" / "assistente_redazionale.json"),
        "TEMPLATE_ATTI_DB": str(tmp_path / "template_atti" / "templates.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(tmp_path / "template_atti" / "editor_layout.json"),
        "SOGGETTI_DB": str(tmp_path / "soggetti" / "anagrafica.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "soggetti" / "parti.json"),
    }

    create_app(cfg)

    assert Path(cfg["PREVENTIVI_DB"]).exists()
    assert Path(cfg["NOTIFICHE_LOG"]).exists()
    assert Path(cfg["PRIVACY_DB"]).exists()
    assert Path(cfg["SEARCH_INDEX"]).exists()
    assert Path(cfg["BACKUP_DIR"]).joinpath("registro.json").exists()
    assert Path(cfg["BACKUP_DIR"]).joinpath("config.json").exists()
    assert Path(tmp_path / "preventivi" / "conferimenti.json").exists()
    assert Path(cfg["FATTURAZIONE_DB"]).exists()
    assert Path(cfg["EMAIL_CASELLA_DB"]).exists()
    assert Path(cfg["WIZARD_PRO_DB"]).exists()
    assert Path(cfg["LEGAL_INTELLIGENCE_DB"]).exists()
    assert Path(cfg["NORMATIVE_TABLES_DB"]).exists()
    assert Path(cfg["VALIDATION_RUNS_DB"]).exists()
    assert Path(cfg["REDACTION_ASSISTANT_DB"]).exists()
    assert Path(cfg["TEMPLATE_ATTI_DB"]).exists()
    assert Path(cfg["TEMPLATE_ATTI_PREFS_DB"]).exists()


@pytest.fixture
def client_admin(tmp_path):
    """Client Flask con utente admin autenticato."""
    from web.app import create_app
    from pct.auth import GestioneUtenti, RuoloUtente

    auth_db = str(tmp_path / "auth" / "utenti.json")
    audit_db = str(tmp_path / "auth" / "audit.json")
    backup_dir = str(tmp_path / "backup")
    clienti_db = str(tmp_path / "clienti" / "anagrafica.json")
    os.makedirs(backup_dir, exist_ok=True)

    gu = GestioneUtenti(
        db_path=auth_db,
        audit_path=audit_db,
        secret_key="test",
        crea_admin_se_vuoto=False,
        studio_db=None,
    )
    gu.crea(
        username="testadmin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="a@b.it",
        must_change_password=False,
    )

    cfg = {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": auth_db,
        "AUDIT_DB": audit_db,
        "CLIENTI_DB": clienti_db,
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi" / "storico.json"),
        "NOTIFICHE_LOG": str(tmp_path / "notifiche" / "log.json"),
        "PRIVACY_DB": str(tmp_path / "privacy" / "registro.json"),
        "BACKUP_DIR": backup_dir,
        "SEARCH_INDEX": str(tmp_path / "search" / "index.db"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(tmp_path / "fascicoli" / "archivio"),
        "MULTI_TENANT": False,
    }
    app = create_app(cfg)
    with app.test_client() as c:
        c.post("/login", data={"username": "testadmin", "password": "Admin1234!"}, follow_redirects=True)
        yield c


def test_admin_database_get(client_admin):
    r = client_admin.get("/admin/database?_legacy=1")
    assert r.status_code == 200
    assert b"Database" in r.data


def test_admin_database_get_rileva_ultimo_sqlite_migrato(client_admin):
    backup_dir = Path(client_admin.application.config["BACKUP_DIR"])
    backup_dir.mkdir(parents=True, exist_ok=True)
    db_path = backup_dir / "studio_legale_2026-04-05.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE clienti (id TEXT)")
    conn.commit()
    conn.close()

    r = client_admin.get("/admin/database?_legacy=1")

    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Database SQLite già presente" in html


def test_admin_database_verifica_json(client_admin):
    r = client_admin.get("/admin/database/verifica")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert "problemi" in data


def test_admin_database_verifica_ripara_json(client_admin):
    scadenze_path = Path(client_admin.application.config["SCADENZIARIO_DB"])
    fascicoli_path = Path(client_admin.application.config["FASCICOLI_DB"])
    scadenze_path.parent.mkdir(parents=True, exist_ok=True)
    fascicoli_path.parent.mkdir(parents=True, exist_ok=True)
    _scrivi_json(fascicoli_path, [])
    _scrivi_json(scadenze_path, [{
        "id": "s_orfana",
        "titolo": "Termine memoria",
        "data_scadenza": "2026-05-10",
        "id_fascicolo": "8946FCC7",
    }])

    r = client_admin.post("/admin/database/verifica-ripara")
    assert r.status_code == 200
    data = r.get_json()
    riparata = json.loads(scadenze_path.read_text(encoding="utf-8"))[0]

    assert data["ok"] is True
    assert data["n_riparazioni"] == 1
    assert data["n_problemi"] == 0
    assert data["backup_files"]
    assert riparata["id_fascicolo"] == ""
    assert "8946FCC7" in riparata["note"]


def test_admin_database_ottimizza_json(client_admin):
    r = client_admin.post("/admin/database/ottimizza")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert "risultati" in data
    assert data["risultati"]
    assert "ok" in data["risultati"][0]
    assert "bytes_prima" in data["risultati"][0]
    assert "bytes_dopo" in data["risultati"][0]

def test_admin_database_migra_json(client_admin):
    r = client_admin.post("/admin/database/migra")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert "record_migrati" in data
    assert "messaggio" in data
    assert "avvisi" in data


def test_admin_database_attiva_sqlite_blocca_json_vuoti_su_db_pieno(client_admin):
    clienti_path = Path(client_admin.application.config["CLIENTI_DB"])
    fascicoli_path = Path(client_admin.application.config["FASCICOLI_DB"])
    _scrivi_json(clienti_path, {
        "CLI001": {"id": "CLI001", "nome": "Anna", "cognome": "Rossi"},
    })
    _scrivi_json(fascicoli_path, {
        "FASC001": {"id": "FASC001", "numero": "1/2026", "titolo": "Pratica", "id_cliente": "CLI001"},
    })

    primo = client_admin.post("/admin/database/attiva-sqlite")
    assert primo.status_code == 200
    assert primo.get_json()["ok"] is True

    _scrivi_json(clienti_path, {})
    _scrivi_json(fascicoli_path, {})
    secondo = client_admin.post("/admin/database/attiva-sqlite")
    payload = secondo.get_json()

    assert secondo.status_code == 200
    assert payload["ok"] is False
    assert payload["stato"] == "Bloccata per protezione dati"
    assert "non verrà sovrascritto" in payload["messaggio"]
    assert any("Blocco anti-perdita su clienti" in errore for errore in payload["errori"])
    assert payload["audit_migrazione"]["precheck"]["modules"]["clienti"]["status"] == "blocked"

    studio_db = Path(clienti_path).resolve().parents[1] / "studio.db"
    conn = sqlite3.connect(studio_db)
    counts = conn.execute(
        "SELECT (SELECT COUNT(*) FROM clienti), (SELECT COUNT(*) FROM fascicoli)"
    ).fetchone()
    conn.close()
    assert counts == (1, 1)


def test_admin_database_preverifica_e_riconcilia_sqlite_json(client_admin):
    clienti_path = Path(client_admin.application.config["CLIENTI_DB"])
    _scrivi_json(
        clienti_path,
        {
            f"CLI{i:03d}": {"id": f"CLI{i:03d}", "nome": f"Nome {i}", "cognome": "Preservato"}
            for i in range(1, 26)
        },
    )
    primo = client_admin.post("/admin/database/attiva-sqlite")
    assert primo.status_code == 200
    assert primo.get_json()["ok"] is True

    _scrivi_json(
        clienti_path,
        {
            **{
                f"CLI{i:03d}": {"id": f"CLI{i:03d}", "nome": f"Nome {i}", "cognome": "Preservato"}
                for i in range(1, 9)
            },
            "CLI999": {"id": "CLI999", "nome": "Nuovo", "cognome": "Solo Sorgente"},
        },
    )

    precheck = client_admin.post("/admin/database/preverifica-sqlite")
    precheck_payload = precheck.get_json()
    assert precheck.status_code == 200
    assert precheck_payload["ok"] is False
    assert precheck_payload["stato"] == "Bloccata per protezione dati"
    assert precheck_payload["audit_migrazione"]["precheck"]["modules"]["clienti"]["only_source_count"] == 1

    riconcilia = client_admin.post("/admin/database/riconcilia-sqlite")
    payload = riconcilia.get_json()
    assert riconcilia.status_code == 200
    assert payload["ok"] is True
    assert payload["stato"] == "Eseguita riconciliazione"
    assert payload["audit_migrazione"]["reconciliation"]["executed"] is True

    studio_db = Path(clienti_path).resolve().parents[1] / "studio.db"
    conn = sqlite3.connect(studio_db)
    count, nuovo = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN id = 'CLI999' THEN 1 ELSE 0 END) FROM clienti"
    ).fetchone()
    conn.close()
    assert count == 26
    assert nuovo == 1


def test_admin_database_export_zip(client_admin):
    r = client_admin.get("/admin/database/export")
    assert r.status_code == 200
    assert r.content_type == "application/zip"
