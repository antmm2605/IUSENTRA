import sqlite3

from pct.operational_live import ensure_live_schema


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
