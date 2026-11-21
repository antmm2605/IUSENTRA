"""Le tabelle delle notifiche hanno i contatori dei pannelli pronti, preparati da soli anche su un database esistente."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pct.pannelli_pronti import revisioni
from pct.legal_coverage_sqlite_repository import CoverageSqliteConfig
from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository
from web.services import pannelli_pronti_contatori as contatori
from web.services.pannelli_pronti_fonti import TABELLE_STUDIO


def _studio(tmp_path: Path) -> Path:
    cartella = tmp_path / "tenants" / "studio-prova"
    cartella.mkdir(parents=True)
    studio_db = cartella / "studio.db"
    conn = sqlite3.connect(studio_db)
    conn.execute("CREATE TABLE scadenze (id TEXT PRIMARY KEY, id_fascicolo TEXT, titolo TEXT)")
    conn.commit()
    conn.close()
    return studio_db


def _schema_notifiche(studio_db: Path) -> None:
    """Lo schema reale delle notifiche, come lo crea il repository della pipeline procedurale al primo uso."""
    ProcedureLifecycleRepository(CoverageSqliteConfig(str(studio_db))).ensure_extended_schema()


def _revisione(studio_db: Path, fascicolo: str) -> int:
    conn = sqlite3.connect(studio_db)
    try:
        return revisioni.leggi(conn, fascicolo)[1]
    finally:
        conn.close()


def test_notifica_nuova_aggiorna_il_contatore_del_fascicolo_su_database_gia_preparato(tmp_path, monkeypatch):
    monkeypatch.setattr(contatori, "MARGINE_DISCO_BYTE", 0)
    studio_db = _studio(tmp_path)
    percorsi = {"STUDIO_DB": str(studio_db), "FASCICOLI_DB": str(studio_db.parent / "fascicoli" / "fascicoli.json")}

    # Primo avvio: i trigger esistono solo per le tabelle presenti (come sugli studi preparati al rilascio).
    (primo,) = [e for e in contatori.prepara_contatori(percorsi, slug="studio-prova", forza=True)
                if e["database"] == str(studio_db)]
    assert primo["cambiato"] is True

    # Le tabelle delle notifiche nascono dopo il rilascio, al primo uso della matrice probatoria.
    _schema_notifiche(studio_db)
    prima = _revisione(studio_db, "FASC1")

    # Al giro successivo la preparazione automatica le vede e installa i contatori, con backup verificato.
    esiti = [e for e in contatori.prepara_contatori(percorsi, slug="studio-prova", forza=True)
             if e["database"] == str(studio_db)]
    assert esiti and esiti[0]["cambiato"] is True, esiti
    conn = sqlite3.connect(studio_db)
    trigger = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'pannelli_rev_notification_%'")}
    assert {"pannelli_rev_notification_cases_i", "pannelli_rev_notification_receipts_i",
            "pannelli_rev_notification_relata_i", "pannelli_rev_notification_dati_atto_receipt_refs_i"} <= trigger
    conn.execute("INSERT INTO notification_cases(tenant_id, fascicolo_id, case_uid, case_type, status) "
                 "VALUES ('t', 'FASC1', 'C1', 'PEC', 'OPEN')")
    caso = conn.execute("SELECT id FROM notification_cases").fetchone()[0]
    conn.commit()
    dopo_caso = revisioni.leggi(conn, "FASC1")[1]
    # La ricevuta legata al fascicolo solo attraverso il caso aggiorna lo stesso fascicolo.
    conn.execute("INSERT INTO notification_dati_atto_receipt_refs(tenant_id, notification_case_id, recipient_id, receipt_id, "
                 "receipt_type) VALUES ('t', ?, 1, 1, 'CONSEGNA')", (caso,))
    conn.commit()
    dopo_ricevuta = revisioni.leggi(conn, "FASC1")[1]
    conn.close()
    assert dopo_caso > prima and dopo_ricevuta > dopo_caso

    # Backup verificato nella cartella persistente del rilascio, solo l'ultimo piano conservato.
    backup = tmp_path / "backup" / "pannelli-pronti" / "studio-prova"
    copie = sorted(p.name for p in backup.iterdir() if p.name.startswith("studio-"))
    assert len(copie) == 1 and (backup / copie[0] / "manifest.json").is_file(), copie

    # A piano invariato non si scrive nulla.
    assert all(not e.get("cambiato") for e in contatori.prepara_contatori(percorsi, slug="studio-prova", forza=True))


def test_senza_spazio_per_il_backup_si_rinvia_senza_toccare_il_database(tmp_path, monkeypatch):
    monkeypatch.setattr(contatori, "MARGINE_DISCO_BYTE", 1 << 62)
    studio_db = _studio(tmp_path)
    esiti = contatori.prepara_contatori({"STUDIO_DB": str(studio_db)}, slug="studio-prova", forza=True)
    assert [e for e in esiti if e["database"] == str(studio_db)][0]["rinviato"].startswith("spazio")
    conn = sqlite3.connect(studio_db)
    assert revisioni.stato(conn) == ""
    conn.close()


def test_il_piano_del_rilascio_comprende_le_tabelle_delle_notifiche(tmp_path):
    _schema_notifiche(tmp_path / "studio.db")
    conn = sqlite3.connect(tmp_path / "studio.db")
    piano = revisioni.piano_trigger(conn, TABELLE_STUDIO)
    conn.close()
    tabelle = {nome[len("pannelli_rev_"):].rsplit("_", 1)[0] for nome in piano}
    attese = {"notification_cases", "notification_events", "notification_recipients", "notification_receipts",
              "notification_relata", "notification_proof_bundles", "notification_evidence_links",
              "notification_dati_atto_receipt_refs"}
    assert attese <= tabelle, sorted(tabelle)


def test_il_lavoro_dello_scheduler_prepara_i_contatori_prima_di_tutto():
    sorgente = Path("web/services/pannelli_pronti_calcolatore.py").read_text(encoding="utf-8")
    corpo = sorgente[sorgente.index("def avvia_se_serve"):]
    assert corpo.index("prepara_tutti(studi(app))") < corpo.index("if in_esecuzione()")
