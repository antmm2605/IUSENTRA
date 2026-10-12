import sqlite3

from pct.operational_live import ensure_live_schema


def test_studio_settings_refreshes_fields_only_when_content_changes(tmp_path):
    connection = sqlite3.connect(tmp_path / "settings.db")
    try:
        connection.execute("CREATE TABLE _meta(chiave TEXT PRIMARY KEY,valore TEXT)")
        connection.execute("CREATE TABLE settings_config(section TEXT PRIMARY KEY,dati_json TEXT,updated_at TEXT)")
        ensure_live_schema(connection)
        connection.execute("INSERT INTO settings_config VALUES ('studio','{\"citta\":\"Torino\"}','prima')")
        connection.commit()
        def revision():
            return connection.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0]
        assert revision() == 1
        connection.execute("UPDATE settings_config SET updated_at='dopo'")
        connection.commit()
        assert revision() == 1
        connection.execute("UPDATE settings_config SET dati_json='{\"citta\":\"Milano\"}'")
        connection.commit()
        assert revision() == 2
    finally:
        connection.close()


def test_document_repository_installs_shared_signals_for_a_new_studio(tmp_path):
    from pct.document_intelligence.repository import DocumentAIRepository
    from pct.storage import StudioDB

    database = StudioDB(str(tmp_path / 'studio.db'))
    try:
        DocumentAIRepository(tmp_path / 'ai.json', tmp_path / 'ai', structured_db=database)
        triggers = {row[0] for row in database.conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        assert 'iusentra_live_fascicolo_documenti_ai_update' in triggers
        assert 'iusentra_live_fascicolo_documenti_ai_versioni_insert' in triggers
        assert 'iusentra_live_document_catalog_jobs_update' in triggers
    finally:
        database.conn.close()


def test_existing_trigger_dependencies_are_migrated_without_resetting_revisions():
    with sqlite3.connect(':memory:') as connection:
        connection.execute('CREATE TABLE _meta(chiave TEXT PRIMARY KEY, valore TEXT)')
        connection.execute('CREATE TABLE appuntamenti(id TEXT PRIMARY KEY)')
        ensure_live_schema(connection)
        connection.execute("UPDATE operational_live_revisions SET revision=17 WHERE domain='agenda'")
        # Riproduce un database già installato con il segnale precedente.
        connection.execute('DROP TRIGGER iusentra_live_appuntamenti_insert')
        connection.execute("CREATE TRIGGER iusentra_live_appuntamenti_insert AFTER INSERT ON appuntamenti BEGIN UPDATE operational_live_revisions SET revision=revision+1 WHERE domain='agenda'; END")
        connection.execute("UPDATE _meta SET valore='appuntamenti' WHERE chiave='operational_live_v3'")
        connection.commit()
        ensure_live_schema(connection)
        connection.execute("INSERT INTO appuntamenti VALUES ('a1')")
        revisions = dict(connection.execute('SELECT domain, revision FROM operational_live_revisions'))
        assert revisions['agenda'] == 18
        assert revisions['fascicoli'] == 1
        connection.commit()
        ensure_live_schema(connection)
        connection.execute("UPDATE appuntamenti SET id='a2'")
        assert connection.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0] == 2


def test_fascicolo_dependencies_are_visible_to_other_connections_only_after_commit(tmp_path):
    database = tmp_path / 'studio.db'
    with sqlite3.connect(database) as writer, sqlite3.connect(database) as reader:
        writer.execute('CREATE TABLE _meta(chiave TEXT PRIMARY KEY, valore TEXT)')
        for table in ('appuntamenti', 'scadenze', 'parcelle', 'messaggi', 'ctu_state', 'mediazione_procedimenti'):
            writer.execute(f'CREATE TABLE {table}(id TEXT PRIMARY KEY)')
        ensure_live_schema(writer)
        for index, table in enumerate(('appuntamenti', 'scadenze', 'parcelle', 'messaggi', 'ctu_state', 'mediazione_procedimenti')):
            writer.execute(f"INSERT INTO {table} VALUES ('record')")
            assert reader.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0] == index
            writer.commit()
            assert reader.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0] == index + 1
        writer.execute("DELETE FROM messaggi")
        writer.rollback()
        assert reader.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0] == 6


def test_vertical_repository_can_initialize_without_other_module_tables():
    with sqlite3.connect(':memory:') as connection:
        connection.execute('CREATE TABLE _meta(chiave TEXT PRIMARY KEY, valore TEXT)')
        connection.execute('CREATE TABLE clienti(id TEXT PRIMARY KEY)')
        ensure_live_schema(connection)
        connection.execute("INSERT INTO clienti VALUES ('c1')")
        connection.commit()
        assert connection.execute("SELECT revision FROM operational_live_revisions WHERE domain = 'clienti'").fetchone()[0] == 1
        ensure_live_schema(connection)
        connection.execute('CREATE TABLE email_mailbox_records(id TEXT PRIMARY KEY)')
        ensure_live_schema(connection)
        connection.execute("INSERT INTO email_mailbox_records VALUES ('m1')")
        assert connection.execute("SELECT revision FROM operational_live_revisions WHERE domain = 'comunicazioni'").fetchone()[0] == 1


def test_prima_nota_emette_segnale_solo_al_commit_e_preserva_rollback():
    from types import SimpleNamespace
    from pct.prima_nota import MovimentoPrimaNota
    from pct.prima_nota_repository import PrimaNotaRepository
    with sqlite3.connect(':memory:') as connection:
        connection.execute('CREATE TABLE _meta(chiave TEXT PRIMARY KEY, valore TEXT)')
        db = SimpleNamespace(conn=connection)
        repo = PrimaNotaRepository(db, 'studio-controllato', actor_key='attore-test')
        repo.ensure_schema()
        ensure_live_schema(connection)
        repo.initialize({}, source_sha256='a' * 64, backup_reference='backup-controllato')
        before = connection.execute("SELECT revision FROM operational_live_revisions WHERE domain='incassi'").fetchone()[0]
        # Due record nello stesso comando: conta la revisione governata del registro.
        movements = {key: MovimentoPrimaNota(id=key, importo=amount).to_dict()
                     for key, amount in [('one', 260), ('two', 500)]}
        repo.save(movements)
        assert connection.execute("SELECT revision FROM operational_live_revisions WHERE domain='incassi'").fetchone()[0] == before + 1
        connection.execute("UPDATE prima_nota_state SET revision=revision+1 WHERE tenant_key='studio-controllato'")
        connection.rollback()
        assert connection.execute("SELECT revision FROM operational_live_revisions WHERE domain='incassi'").fetchone()[0] == before + 1
        repo.save(movements)
        assert connection.execute("SELECT revision FROM operational_live_revisions WHERE domain='incassi'").fetchone()[0] == before + 1
