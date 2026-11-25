from __future__ import annotations

import json
import sqlite3

import pytest

from pct import storage
from pct.storage import StudioDB


@pytest.mark.parametrize(
    ("mount_windows", "guasto", "atteso"),
    [
        (True, None, ["DELETE"]),
        (True, "database is locked", ["DELETE"]),
        (False, None, ["WAL"]),
        (False, "database is locked", ["WAL", "DELETE"]),
    ],
)
def test_journal_usa_modalita_compatibile_con_il_volume(monkeypatch, tmp_path, mount_windows, guasto, atteso):
    richieste = []

    class Connessione:
        def execute(self, sql):
            richieste.append(sql.rsplit("=", 1)[-1])
            if len(richieste) == 1 and guasto:
                raise sqlite3.OperationalError(guasto)

    monkeypatch.setattr(storage, "_requires_delete_journal_for_mount", lambda _: mount_windows)
    storage.configura_journal_mode_governato(Connessione(), tmp_path / "studio.db")
    assert richieste == atteso


def test_salvataggio_rollback_preserva_i_dati_e_riabilita_le_chiavi_esterne(tmp_path):
    db = StudioDB(str(tmp_path / "studio.db"))
    db.conn.execute("CREATE TABLE prova_salvataggio (dati_json TEXT NOT NULL)")
    db.conn.execute("INSERT INTO prova_salvataggio VALUES (?)", ('{"stato":"precedente"}',))
    db.conn.commit()

    def inserisci(conn, dato):
        conn.execute("INSERT INTO prova_salvataggio VALUES (?)", (json.dumps(dato),))

    def rifiuta(_):
        raise ValueError("Ricevuta rifiutata")

    try:
        with pytest.raises(ValueError, match="Ricevuta rifiutata"):
            db.salva_tabella("prova_salvataggio", [{"stato": "nuovo"}], inserisci, before_commit=rifiuta)
        assert db.carica_tabella("prova_salvataggio") == [{"stato": "precedente"}]
        assert db.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.ha_dati("prova_salvataggio")
        assert not db.ha_dati("tabella_inesistente")
        assert db.carica_tabella("tabella_inesistente") == []
        db.salva_tabella("prova_salvataggio", [{"stato": "nuovo"}], inserisci)
        assert db.carica_tabella("prova_salvataggio") == [{"stato": "nuovo"}]
    finally:
        db.chiudi_tutte()


@pytest.mark.parametrize("colonna_payload", [False, True])
def test_backfill_sqlite_ripara_il_profilo_preservando_identita_e_payload(monkeypatch, tmp_path, colonna_payload):
    from pct import deposito_profile_backfill as profili

    db = StudioDB(str(tmp_path / "studio.db"))
    colonna = ", dati_json TEXT" if colonna_payload else ""
    db.conn.execute(f"CREATE TABLE prova_profili (id TEXT PRIMARY KEY, profilo_deposito_json TEXT{colonna})")
    db.conn.executemany(
        "INSERT INTO prova_profili VALUES (?, ?, ?)" if colonna_payload else "INSERT INTO prova_profili VALUES (?, ?)",
        [
            (ident, profilo, '{"dato":"da conservare"}') if colonna_payload else (ident, profilo)
            for ident, profilo in (("doc-1", "illeggibile"), ("", "{}"), ("gia-pronto", '{"stato": "pronto"}'))
        ],
    )
    visitati = []

    def calcola(tabella, dati, *, verify_certificates):
        visitati.append((tabella, dati["id"], verify_certificates))
        return {"stato": "pronto"}, json.loads(dati.get("dati_json") or "{}")

    monkeypatch.setattr(profili, "CORE_DEPOSIT_PROFILE_TABLES", [("prova_profili", "id")])
    monkeypatch.setattr(profili, "build_deposit_profile_for_record", calcola)
    monkeypatch.setattr(profili, "deposit_profile_needs_update", lambda prima, dopo: prima != dopo)
    try:
        db.repair_deposit_profiles(verify_certificates=True)
        righe = {r["id"]: dict(r) for r in db.conn.execute("SELECT * FROM prova_profili")}
        assert json.loads(righe["doc-1"]["profilo_deposito_json"]) == {"stato": "pronto"}
        assert righe[""]["profilo_deposito_json"] == "{}"
        if colonna_payload:
            persistito = json.loads(righe["doc-1"]["dati_json"])
            assert persistito["dato"] == "da conservare"
            assert persistito["profilo_deposito"] == {"stato": "pronto"}
        assert {r[1] for r in visitati} == {"doc-1", "gia-pronto"}
        assert all(r[2] for r in visitati)
    finally:
        db.chiudi_tutte()


def test_salvataggio_su_connessione_occupata_riprova_una_sola_transazione(tmp_path, monkeypatch):
    db = StudioDB(str(tmp_path / "studio.db"))
    db.conn.execute("CREATE TABLE prova_ritento (dati_json TEXT)")
    db.conn.commit()
    tentativi = []
    sospensioni = []

    def inserisci(conn, dato):
        tentativi.append(conn)
        if len(tentativi) == 1:
            raise sqlite3.OperationalError("database is locked")
        conn.execute("INSERT INTO prova_ritento VALUES (?)", (json.dumps(dato),))

    monkeypatch.setattr(storage.time, "sleep", sospensioni.append)
    try:
        db.salva_tabella("prova_ritento", [{"id": 1}], inserisci)
        assert db.carica_tabella("prova_ritento") == [{"id": 1}]
        assert len(tentativi) == 2 and tentativi[0] is not tentativi[1]
        assert len(sospensioni) == 1
    finally:
        db.chiudi_tutte()


def test_invalida_solo_le_connessioni_sotto_la_cartella_ripristinata(tmp_path):
    radice = tmp_path / "studio-da-ripristinare"
    estraneo = tmp_path / "altro-studio"
    db = StudioDB.from_data_path(str(radice / "clienti" / "anagrafica.json"))
    altro = StudioDB.get(str(estraneo / "studio.db"))
    aperta = db.conn
    try:
        assert db.db_path == radice / "studio.db"
        assert StudioDB.invalidate_sotto(radice) == 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            aperta.execute("SELECT 1")
        assert StudioDB.get(str(estraneo / "studio.db")) is altro
        assert altro.conn.execute("SELECT 1").fetchone()[0] == 1
        assert StudioDB.get(str(db.db_path)) is not db
    finally:
        StudioDB.invalidate_sotto(tmp_path)


def test_mount_con_lock_conserva_la_consultazione_fino_al_ritorno_della_scrittura(tmp_path, monkeypatch):
    db = StudioDB(str(tmp_path / "studio.db"))
    db.conn.execute("CREATE TABLE dati_montati (dati_json TEXT)")
    db.conn.execute("INSERT INTO dati_montati VALUES (?)", ('{"stato":"salvato"}',))
    db.conn.commit()
    db.chiudi()
    apri_scrittura = db._connect_writable

    def temporaneamente_occupato():
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(storage, "_requires_delete_journal_for_mount", lambda _: True)
    monkeypatch.setattr(db, "_connect_writable", temporaneamente_occupato)
    try:
        assert db.carica_tabella("dati_montati") == [{"stato": "salvato"}]
        assert db.conn.execute("PRAGMA query_only").fetchone()[0] == 1
        monkeypatch.setattr(db, "_connect_writable", apri_scrittura)

        def inserisci(conn, dato):
            conn.execute("INSERT INTO dati_montati VALUES (?)", (json.dumps(dato),))

        db.salva_tabella("dati_montati", [{"stato": "aggiornato"}], inserisci)
        assert db.conn.execute("PRAGMA query_only").fetchone()[0] == 0
        assert db.carica_tabella("dati_montati") == [{"stato": "aggiornato"}]
    finally:
        db.chiudi_tutte()
