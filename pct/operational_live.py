"""Commit-visible invalidations in the existing tenant SQL database.

Counters contain no record identifiers or personal data. Triggers are installed
at schema migration, never by a read request. Rollback rolls back the counter.
"""
from __future__ import annotations

TABLE_DOMAINS = {
    "clienti": ("clienti", "fascicoli", "soggetti"),
    "fascicoli": ("fascicoli",),
    "soggetti": ("soggetti", "fascicoli"),
    "soggetti_parti": ("soggetti", "fascicoli"),
    "appuntamenti": ("agenda",),
    "scadenze": ("scadenze",),
    "timesheet_entries": ("timesheet",),
    "preventivi_records": ("preventivi",),
    "conferimenti_records": ("preventivi", "fascicoli"),
    "parcelle": ("fatturazione", "incassi"),
    # Una revisione del registro per transazione: anche più movimenti producono
    # un solo segnale, confermato insieme alla scrittura governata.
    "prima_nota_state": ("incassi",),
    "messaggi": ("comunicazioni",),
    "email_mailbox_records": ("comunicazioni",),
    "privacy_trattamenti": ("privacy",),
    "document_catalog_assignments": ("clienti", "fascicoli"),
}


def ensure_live_schema(conn, *, postgres: bool = False) -> None:
    # I repository verticali possono usare StudioDB con uno schema ridotto:
    # non installare trigger su tabelle appartenenti a un altro database.
    if postgres:
        existing = {str(row[0]) for row in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()").fetchall()}
    else:
        existing = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    tables = sorted(set(TABLE_DOMAINS) & existing)
    signature = ','.join(tables)
    marker = conn.execute("SELECT valore FROM _meta WHERE chiave = ?", ("operational_live_v3",)).fetchone()
    if marker and marker[0] == signature:
        return
    conn.execute("CREATE TABLE IF NOT EXISTS operational_live_revisions (domain TEXT PRIMARY KEY, revision BIGINT NOT NULL DEFAULT 0)")
    for domain in sorted({domain for domains in TABLE_DOMAINS.values() for domain in domains}):
        conn.execute("INSERT INTO operational_live_revisions(domain, revision) VALUES (?, 0) ON CONFLICT(domain) DO NOTHING", (domain,))
    for table, domains in TABLE_DOMAINS.items():
        if table not in existing:
            continue
        updates = " ".join(f"UPDATE operational_live_revisions SET revision = revision + 1 WHERE domain = '{domain}';" for domain in domains)
        if postgres:
            function = f"iusentra_live_{table}"
            conn.execute(f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {updates} RETURN NULL; END $$")
            conn.execute(f"DROP TRIGGER IF EXISTS {function} ON {table}")
            conn.execute(f"CREATE TRIGGER {function} AFTER INSERT OR UPDATE OR DELETE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {function}()")
        else:
            for action in ("INSERT", "UPDATE", "DELETE"):
                name = f"iusentra_live_{table}_{action.lower()}"
                conn.execute(f"CREATE TRIGGER IF NOT EXISTS {name} AFTER {action} ON {table} BEGIN {updates} END")
    conn.execute("INSERT INTO _meta(chiave, valore) VALUES (?, ?) ON CONFLICT(chiave) DO UPDATE SET valore = excluded.valore", ("operational_live_v3", signature))
    if not postgres:
        conn.commit()


def read_live_revisions(backend, domains: set[str]) -> dict[str, int]:
    rows = backend.conn.execute("SELECT domain, revision FROM operational_live_revisions").fetchall()
    return {str(row[0]): int(row[1]) for row in rows if str(row[0]) in domains}
