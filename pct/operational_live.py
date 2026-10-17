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
    "appuntamenti": ("agenda", "fascicoli"),
    "scadenze": ("scadenze", "fascicoli"),
    "termini_state": ("scadenze", "fascicoli"),
    "timesheet_entries": ("timesheet", "fascicoli"),
    "time_tracking_proposals": ("timesheet", "fascicoli"),
    "preventivi_records": ("preventivi", "fascicoli"),
    "conferimenti_records": ("preventivi", "fascicoli"),
    "parcelle": ("fatturazione", "incassi", "fascicoli"),
    # Una revisione del registro per transazione: anche più movimenti producono
    # un solo segnale, confermato insieme alla scrittura governata.
    "prima_nota_state": ("incassi", "fascicoli"),
    "ctu_state": ("fascicoli",),
    "mediazione_procedimenti": ("fascicoli",),
    # La preparazione appartiene all'Agenda: stesso presidio di permessi e
    # stessa regia delle aree aperte, senza un canale parallelo.
    "preparazioni_sessions": ("agenda", "fascicoli"),
    "messaggi": ("comunicazioni", "fascicoli"),
    "email_mailbox_records": ("comunicazioni", "fascicoli"),
    "privacy_trattamenti": ("privacy",),
    "document_catalog_assignments": ("clienti", "fascicoli"),
    "fascicolo_documenti_ai": ("fascicoli",),
    "fascicolo_documenti_ai_versioni": ("fascicoli",),
    "document_catalog_jobs": ("fascicoli",),
    "settings_config": ("fascicoli", "clienti"),
}


def ensure_domain_signal_schema(conn, domain: str) -> None:
    """Preparazione esplicita di un produttore nella regia già esistente."""
    if domain not in {value for domains in TABLE_DOMAINS.values() for value in domains}:
        raise ValueError('Dominio della sincronizzazione non previsto.')
    conn.execute('CREATE TABLE IF NOT EXISTS operational_live_revisions '
                 '(domain TEXT PRIMARY KEY,revision BIGINT NOT NULL DEFAULT 0)')
    conn.execute('INSERT INTO operational_live_revisions(domain,revision) VALUES (?,0) '
                 'ON CONFLICT(domain) DO NOTHING', (domain,))


def signal_domain_changed(conn, domain: str) -> int:
    """Conferma persistente nella stessa transazione della proiezione cambiata."""
    row = conn.execute('UPDATE operational_live_revisions SET revision=revision+1 WHERE domain=? RETURNING revision',
                       (domain,)).fetchone()
    if row is None:
        raise RuntimeError('Produttore di sincronizzazione non preparato.')
    return int(row[0])

# Archivi verticali: il segnale appartiene al tenant della riga e alla stessa
# transazione della fonte. La migrazione è chiamata soltanto dagli scrittori.
TENANT_TABLE_DOMAINS = {
    "letture": {
        table: ("fascicoli",) for table in (
            "letture_oggetti", "letture", "letture_fascicoli", "letture_viste",
            "letture_anomalie", "letture_fatti", "letture_consegne",
            "letture_eventi",
        )
    },
    "economico": {
        table: ("fascicoli", "incassi", "fatturazione") for table in (
            "sentenza_economic_audits", "contributo_unificato_audits",
            "fascicolo_economic_events", "sentenza_economic_audit_events",
        )
    },
}


def ensure_tenant_live_schema(conn, family: str, *, postgres: bool = False) -> None:
    mapping = TENANT_TABLE_DOMAINS[family]
    signature = "tenant-live-v2|" + "|".join(f"{table}:{','.join(domains)}" for table, domains in sorted(mapping.items()))
    exists = conn.execute("SELECT to_regclass('operational_live_tenant_meta')" if postgres else "SELECT name FROM sqlite_master WHERE type='table' AND name='operational_live_tenant_meta'").fetchone()
    if exists and exists[0]:
        marker = conn.execute("SELECT signature FROM operational_live_tenant_meta WHERE family = ?", (family,)).fetchone()
        if marker and marker[0] == signature:
            return
    if postgres:
        # Solo la prima migrazione prende il lock; le scritture ordinarie non
        # si serializzano tra studi o processi. Il lock termina col commit.
        conn.execute("SELECT pg_advisory_xact_lock(?)", (1158035772,))
    conn.execute("CREATE TABLE IF NOT EXISTS operational_live_tenant_meta (family TEXT PRIMARY KEY, signature TEXT NOT NULL)")
    marker = conn.execute("SELECT signature FROM operational_live_tenant_meta WHERE family = ?", (family,)).fetchone()
    if marker and marker[0] == signature:
        return
    conn.execute("CREATE TABLE IF NOT EXISTS operational_live_tenant_revisions (family TEXT NOT NULL, tenant_id TEXT NOT NULL, domain TEXT NOT NULL, revision BIGINT NOT NULL DEFAULT 0, PRIMARY KEY(family, tenant_id, domain))")
    for table, domains in mapping.items():
        # Ripetere una presa visione o confermare lo stesso esito non è una
        # modifica del contenuto. Evitare catene GET -> timestamp -> refresh.
        technical = {"aggiornato_il", "censito_il", "visto_il", "letto_il", "durata_ms"}
        if postgres:
            columns = [str(row[0]) for row in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=? ORDER BY ordinal_position", (table,)).fetchall()]
        else:
            columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
        content = [column for column in columns if column not in technical]
        comparator = "IS DISTINCT FROM" if postgres else "IS NOT"
        changed = " OR ".join(f'OLD."{column}" {comparator} NEW."{column}"' for column in content) or "1=1"
        def increment(row: str) -> str:
            return " ".join(
                "INSERT INTO operational_live_tenant_revisions(family, tenant_id, domain, revision) "
                f"VALUES ('{family}', {row}.tenant_id, '{domain}', 1) "
                "ON CONFLICT(family, tenant_id, domain) DO UPDATE SET revision = operational_live_tenant_revisions.revision + 1;"
                for domain in domains
            )
        if postgres:
            schema = str(conn.execute("SELECT current_schema()").fetchone()[0])
            quoted = '"' + schema.replace('"', '""') + '"'
            name = f"iusentra_live_tenant_{table}"
            function = f'{quoted}."{name}"'
            conn.execute(f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql SET search_path = {quoted}, pg_temp AS $$ BEGIN IF TG_OP = 'UPDATE' AND NOT ({changed}) THEN RETURN NULL; END IF; IF TG_OP = 'DELETE' THEN {increment('OLD')} ELSE {increment('NEW')} IF TG_OP = 'UPDATE' AND OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN {increment('OLD')} END IF; END IF; RETURN NULL; END $$")
            conn.execute(f"DROP TRIGGER IF EXISTS {name} ON {table}")
            conn.execute(f"CREATE TRIGGER {name} AFTER INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {function}()")
        else:
            for action, row in (("INSERT", "NEW"), ("UPDATE", "NEW"), ("DELETE", "OLD")):
                name = f"iusentra_live_tenant_{table}_{action.lower()}"
                conn.execute(f"DROP TRIGGER IF EXISTS {name}")
                condition = f" WHEN {changed}" if action == "UPDATE" else ""
                conn.execute(f"CREATE TRIGGER {name} AFTER {action} ON {table}{condition} BEGIN {increment(row)} END")
            name = f"iusentra_live_tenant_{table}_previous_owner"
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
            conn.execute(f"CREATE TRIGGER {name} AFTER UPDATE ON {table} WHEN OLD.tenant_id <> NEW.tenant_id BEGIN {increment('OLD')} END")
    conn.execute("INSERT INTO operational_live_tenant_meta(family, signature) VALUES (?, ?) ON CONFLICT(family) DO UPDATE SET signature = excluded.signature", (family, signature))


def read_tenant_live_revisions(conn, family: str, tenant_id: str, domains: set[str], *, postgres: bool = False) -> dict[str, int]:
    # Un archivio ancora mai scritto non ha una revisione. Nessuna migrazione
    # o lettura documentale viene avviata dalla richiesta di sincronizzazione.
    exists = conn.execute("SELECT to_regclass('operational_live_tenant_revisions')" if postgres else "SELECT name FROM sqlite_master WHERE type='table' AND name='operational_live_tenant_revisions'").fetchone()
    if not exists or not exists[0]:
        return {}
    rows = conn.execute("SELECT domain, revision FROM operational_live_tenant_revisions WHERE family=? AND tenant_id=?", (family, tenant_id)).fetchall()
    return {str(row[0]): int(row[1]) for row in rows if str(row[0]) in domains}


def ensure_live_schema(conn, *, postgres: bool = False) -> None:
    # I repository verticali possono usare StudioDB con uno schema ridotto:
    # non installare trigger su tabelle appartenenti a un altro database.
    if postgres:
        existing = {str(row[0]) for row in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()").fetchall()}
        schema = str(conn.execute("SELECT current_schema()").fetchone()[0])
        quoted_schema = '"' + schema.replace('"', '""') + '"'
    else:
        existing = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    tables = sorted(set(TABLE_DOMAINS) & existing)
    # La migrazione deve rilevare anche nuove dipendenze tra sezioni, non solo
    # nuove tabelle. Conserva i contatori già confermati durante l'aggiornamento.
    signature = 'live-v4|' + '|'.join(f"{table}:{','.join(TABLE_DOMAINS[table])}" for table in tables)
    marker = conn.execute("SELECT valore FROM _meta WHERE chiave = ?", ("operational_live_v3",)).fetchone()
    if marker and marker[0] == signature:
        return
    if postgres:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(current_schema()), 1158035771)")
        # Un altro processo può aver completato la migrazione durante l'attesa.
        existing = {str(row[0]) for row in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()").fetchall()}
        tables = sorted(set(TABLE_DOMAINS) & existing)
        signature = 'live-v4|' + '|'.join(f"{table}:{','.join(TABLE_DOMAINS[table])}" for table in tables)
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
            function_ref = f'{quoted_schema}."{function}"'
            unchanged = "IF TG_OP = 'UPDATE' AND OLD.dati_json IS NOT DISTINCT FROM NEW.dati_json THEN RETURN NULL; END IF; " if table == "settings_config" else ""
            conn.execute(f"CREATE OR REPLACE FUNCTION {function_ref}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {unchanged}{updates} RETURN NULL; END $$")
            conn.execute(f"DROP TRIGGER IF EXISTS {function} ON {table}")
            unit = "ROW" if table == "settings_config" else "STATEMENT"
            conn.execute(f"CREATE TRIGGER {function} AFTER INSERT OR UPDATE OR DELETE ON {table} FOR EACH {unit} EXECUTE FUNCTION {function_ref}()")
        else:
            for action in ("INSERT", "UPDATE", "DELETE"):
                name = f"iusentra_live_{table}_{action.lower()}"
                conn.execute(f"DROP TRIGGER IF EXISTS {name}")
                changed = " WHEN OLD.dati_json IS NOT NEW.dati_json" if table == "settings_config" and action == "UPDATE" else ""
                conn.execute(f"CREATE TRIGGER {name} AFTER {action} ON {table}{changed} BEGIN {updates} END")
    conn.execute("INSERT INTO _meta(chiave, valore) VALUES (?, ?) ON CONFLICT(chiave) DO UPDATE SET valore = excluded.valore", ("operational_live_v3", signature))
    if not postgres:
        conn.commit()


def read_live_revisions(backend, domains: set[str]) -> dict[str, int]:
    rows = backend.conn.execute("SELECT domain, revision FROM operational_live_revisions").fetchall()
    return {str(row[0]): int(row[1]) for row in rows if str(row[0]) in domains}
