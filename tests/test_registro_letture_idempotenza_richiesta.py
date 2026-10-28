"""Requisiti di lettura per fonte, senza ripetizioni automatiche."""

import pytest

from pct.registro_letture import Oggetto, RegistroLetture, RegistroLettureError


def test_lettura_immutata_non_riparte_per_versione_del_lettore(tmp_path):
    registro = RegistroLetture(tmp_path / "registro.db")
    fonte = Oggetto(tipo="documento", oggetto_id="fonte-1", sha256="a" * 64)
    registro.registra_inventario("studio", "fascicolo", [fonte])
    registro.segna_letto("studio", "fascicolo", fonte, "ocr", versione="v1")

    assert registro.da_leggere("studio", "fascicolo", "ocr", versione="v2") == []
    modificata = Oggetto(tipo="documento", oggetto_id="fonte-1", sha256="b" * 64)
    registro.registra_inventario("studio", "fascicolo", [modificata])
    assert registro.da_leggere("studio", "fascicolo", "ocr", versione="v2") == [modificata]


def test_errore_invariato_non_diventa_successo_e_non_riparte_da_solo(tmp_path):
    registro = RegistroLetture(tmp_path / "registro.db")
    fonte = Oggetto(tipo="documento", oggetto_id="fonte-1", sha256="a" * 64)
    registro.registra_inventario("studio", "fascicolo", [fonte])
    registro.segna_letto("studio", "fascicolo", fonte, "ocr", stato="errore")

    assert registro.da_leggere("studio", "fascicolo", "ocr") == []
    assert registro.letture("studio", "fascicolo", lettore="ocr")[0].stato == "errore"
    # Una prova di successo già acquisita può aggiornare l'esito precedente
    # senza che la ricerca dei pendenti avvii una nuova lettura.
    assert registro.da_confermare("studio", "fascicolo", "ocr", oggetti=[fonte]) == [fonte]
    registro.segna_letto("studio", "fascicolo", fonte, "ocr", stato="letto")
    assert registro.da_confermare("studio", "fascicolo", "ocr", oggetti=[fonte]) == []


def test_stessa_identita_in_fascicoli_distinti_non_condivide_ricevute(tmp_path):
    registro = RegistroLetture(tmp_path / "registro.db")
    fonte = Oggetto(tipo="documento", oggetto_id="fonte-1", sha256="a" * 64)
    registro.registra_inventario("studio", "fascicolo-1", [fonte])
    registro.registra_inventario("studio", "fascicolo-2", [fonte])
    registro.segna_letto("studio", "fascicolo-1", fonte, "ocr", versione="v1")

    assert registro.da_leggere("studio", "fascicolo-1", "ocr", versione="v1") == []
    assert registro.da_leggere("studio", "fascicolo-2", "ocr", versione="v1") == [fonte]
    registro.segna_letto("studio", "fascicolo-2", fonte, "ocr", versione="v1")
    assert len(registro.letture("studio", "fascicolo-1", lettore="ocr")) == 1
    assert len(registro.letture("studio", "fascicolo-2", lettore="ocr")) == 1


def test_dimensione_non_basta_a_confermare_la_lettura(tmp_path):
    registro = RegistroLetture(tmp_path / "registro.db")
    fonte = Oggetto(tipo="documento", oggetto_id="fonte-1", dimensione=5)
    registro.registra_inventario("studio", "fascicolo", [fonte])
    with pytest.raises(RegistroLettureError, match="Impronta SHA-256"):
        registro.segna_letto("studio", "fascicolo", fonte, "ocr")
    assert registro.letture("studio", "fascicolo", lettore="ocr") == []
    registro.segna_letto("studio", "fascicolo", fonte, "ocr", stato="errore")
    assert registro.letture("studio", "fascicolo", lettore="ocr")[0].stato == "errore"


@pytest.mark.parametrize("reverse_columns", [False, True])
@pytest.mark.parametrize("explicit_index", [False, True])
def test_migrazione_ricevute_conserva_righe_indici_e_trigger(tmp_path, reverse_columns, explicit_index):
    import sqlite3

    from pct.registro_letture.repository import SCHEMA_SQLITE, _allinea_identita_ricevute

    schema = SCHEMA_SQLITE.read_text(encoding="utf-8")
    legacy = schema.replace(
        "UNIQUE (tenant_id, fascicolo_id, tipo, oggetto_id, sha256, lettore)",
        "UNIQUE (tenant_id, tipo, oggetto_id, sha256, lettore)",
    )
    if reverse_columns:
        legacy = legacy.replace("    letto_il TEXT NOT NULL,\n    aggiornato_il TEXT NOT NULL,", "    aggiornato_il TEXT NOT NULL,\n    letto_il TEXT NOT NULL,")
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(legacy)
        conn.execute("INSERT INTO letture (id, tenant_id, fascicolo_id, tipo, oggetto_id, sha256, lettore, stato, letto_il, aggiornato_il) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     ("ricevuta-storica", "studio", "f1", "documento", "d1", "a" * 64, "ocr", "letto", "2026-10-28T12:00:00Z", "2026-10-28T12:00:00Z"))
        conn.execute("CREATE INDEX prova_indice_ricevute ON letture(lettore)")
        if explicit_index:
            conn.execute("CREATE UNIQUE INDEX prova_identita_legacy ON letture(tenant_id, tipo, oggetto_id, sha256, lettore)")
        conn.execute("CREATE TRIGGER prova_trigger_ricevute AFTER UPDATE ON letture BEGIN SELECT 1; END")
        conn.commit()
        columns = ",".join(row[1] for row in conn.execute("PRAGMA table_info(letture)"))
        before = conn.execute(f"SELECT {columns} FROM letture").fetchall()
        _allinea_identita_ricevute(conn, schema)
        assert conn.execute(f"SELECT {columns} FROM letture").fetchall() == before
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name IN ('prova_indice_ricevute', 'prova_trigger_ricevute')").fetchone()[0] == 2
        _allinea_identita_ricevute(conn, schema)
        assert conn.execute(f"SELECT {columns} FROM letture").fetchall() == before
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    registro = RegistroLetture(path)
    fonte = Oggetto(tipo="documento", oggetto_id="d1", sha256="a" * 64)
    registro.segna_letto("studio", "f2", fonte, "ocr")
    assert len(registro.letture("studio", "f1", lettore="ocr")) == 1
    assert len(registro.letture("studio", "f2", lettore="ocr")) == 1


def test_migrazione_ricevute_rifiuta_cascata_su_relazioni_esterne(tmp_path):
    import sqlite3

    from pct.registro_letture.repository import SCHEMA_SQLITE, _allinea_identita_ricevute

    schema = SCHEMA_SQLITE.read_text(encoding="utf-8")
    legacy = schema.replace(
        "UNIQUE (tenant_id, fascicolo_id, tipo, oggetto_id, sha256, lettore)",
        "UNIQUE(tenant_id,tipo,oggetto_id,sha256,lettore)",
    )
    with sqlite3.connect(tmp_path / "linked.db") as conn:
        conn.executescript(legacy)
        conn.execute("CREATE TABLE link_esterno (ricevuta TEXT REFERENCES letture(id) ON DELETE CASCADE)")
        conn.commit()
        before = conn.execute("SELECT sql FROM sqlite_master WHERE name='letture'").fetchone()[0]
        with pytest.raises(RegistroLettureError, match="riferimenti esterni"):
            _allinea_identita_ricevute(conn, schema)
        assert conn.execute("SELECT sql FROM sqlite_master WHERE name='letture'").fetchone()[0] == before
        assert not conn.in_transaction
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_ricevute_concorrenti_non_duplicano_e_non_mescolano_studi(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "concorrenza.db"
    registro = RegistroLetture(path)
    fonte = Oggetto(tipo="documento", oggetto_id="fonte", sha256="b" * 64)

    def registra(studio):
        RegistroLetture(path).segna_letto(studio, "fascicolo", fonte, "ocr")

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(registra, ["studio-a", "studio-b"] * 6))
    assert len(registro.letture("studio-a", "fascicolo", lettore="ocr")) == 1
    assert len(registro.letture("studio-b", "fascicolo", lettore="ocr")) == 1


def _scrivi_ricevuta_da_processo(path, start):
    start.wait(10)
    fonte = Oggetto(tipo="documento", oggetto_id="fonte", sha256="c" * 64)
    RegistroLetture(path).segna_letto("studio", "fascicolo", fonte, "ocr")


def test_ricevute_da_processi_distinti_non_duplicano(tmp_path):
    import multiprocessing

    path = tmp_path / "processi.db"
    registro = RegistroLetture(path)
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    processes = [context.Process(target=_scrivi_ricevuta_da_processo, args=(path, start)) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        start.set()
        for process in processes:
            process.join(30)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)
    assert len(registro.letture("studio", "fascicolo", lettore="ocr")) == 1
