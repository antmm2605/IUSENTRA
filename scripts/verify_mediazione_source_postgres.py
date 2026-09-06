"""Technical parity check on an isolated schema of the configured audit PostgreSQL.

No tenant data or existing schema is read/changed. The generated test schema is
dropped at the end. Run inside the local application container; no web server.
"""
import os
import re
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import make_dsn

from pct.mediazione_directory_repository import MediazioneDirectoryRepository
from pct.mediazione_source_history import source_status
from pct.mediazione_source_refresh import claim_jobs, finish_job, seed_jobs
from pct.mediazione_procedimenti import MediazioneProcedimentiRepository, normalizza


def main():
    schema = "iusentra_med_test_" + uuid4().hex
    if not re.fullmatch(r"iusentra_med_test_[0-9a-f]{32}", schema):
        raise ValueError("Schema di prova non valido.")
    dsn = make_dsn(host=os.getenv("AUDIT_POSTGRES_HOST", "audit-postgres"),
                   dbname=os.getenv("AUDIT_POSTGRES_DB", "iusentra_audit"),
                   user=os.getenv("AUDIT_POSTGRES_USER", "iusentra_audit"),
                   password=os.environ["AUDIT_POSTGRES_PASSWORD"], connect_timeout=10)
    admin = psycopg2.connect(dsn)
    admin.autocommit = True
    created = False
    try:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        created = True
        with TemporaryDirectory(prefix="iusentra-med-test-") as temporary:
            repo = MediazioneDirectoryRepository(temporary + "/unused.db",
                    postgres_dsn=make_dsn(dsn, options="-csearch_path=" + schema))
            now = datetime.now(timezone.utc)
            organism = dict(registration_number="1", registry_kind="organismo", name="Prova isolata",
                            is_active=True, website="https://organismo.example.test/")
            repo.import_registry([organism], source="https://mediazione.giustizia.it/ROM/", checked_at=now.isoformat())
            assert seed_jobs(repo, now=now) == 1
            job = claim_jobs(repo, now=now)[0]
            assert not claim_jobs(repo, now=now)
            result = dict(registration_number="1", checked_at=now.isoformat(), status="fonti_rilevate",
                          pages=[dict(status=200, parsed=True, url=organism["website"])])
            assert finish_job(repo, job, result, now=now) == "acquisita"
            repo.save_channel_check("1", dict(result, checked_at=(now + timedelta(seconds=1)).isoformat(), pages=[], errors=[{"error": "Timeout"}]))
            status = source_status(repo, "1", now=now)
            assert status["stato"] == "fonte_non_raggiunta" and status["revisione"] == 1
            assert status["ultima_acquisizione"] == now.isoformat() and not status["invio_autorizzato"]
            repo.save_channel_check("1", result)
            assert source_status(repo, "1", now=now)["ultimo_controllo"] == (now + timedelta(seconds=1)).isoformat()
            repo.import_registry([dict(organism, website="https://nuovo.example.test/")], source="ministero", checked_at=now.isoformat())
            assert seed_jobs(repo, now=now) == 1
            new = claim_jobs(repo, now=now)[0]
            assert new["input_sha256"] != job["input_sha256"]
            assert finish_job(repo, job, result, now=now) == "esito_superato"
            repo.import_registry([dict(organism, is_active=False)], source="ministero", checked_at=now.isoformat())
            assert finish_job(repo, new, result, now=now) == "organismo_non_attivo"
            assert not repo.records()
            with repo.connection() as conn:
                assert conn.execute("SELECT COUNT(*) FROM mediazione_source_history").fetchone()[0] == 3
                conn.execute("CREATE TABLE fascicoli (id TEXT PRIMARY KEY)")
                conn.execute("INSERT INTO fascicoli VALUES (?)", ("prova",))
                conn.execute("COMMIT")
                procedures = MediazioneProcedimentiRepository(SimpleNamespace(conn=conn, backend_kind="postgresql"))
                draft = normalizza({"titolo": "Bozza di prova isolata"}, set())
                identifier = procedures.salva("prova", "", 0, draft, "test")
                procedures.salva("prova", identifier, 1, draft, "test")
                assert procedures.lista("prova")[0]["versione"] == 2
                assert len(procedures.audit("prova")) == 2
                try:
                    procedures.salva("prova", identifier, 1, draft, "test")
                except ValueError:
                    pass
                else:
                    raise AssertionError("Conflitto di versione non rilevato.")
                assert len(procedures.audit("prova")) == 2
                assert procedures.lista("altro") == []
            print("PostgreSQL: schema, importazione, lease esclusivo, esiti, storico, revisione e disattivazione verificati.")
            print("PostgreSQL: procedimento SQL, versioni, conflitto atomico e audit isolato verificati.")
    finally:
        if created:
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            print("Rimosso esclusivamente lo schema temporaneo creato dalla prova; dati applicativi non toccati.")
        admin.close()


if __name__ == "__main__":
    main()
