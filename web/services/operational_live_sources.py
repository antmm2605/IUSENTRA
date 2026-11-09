"""Revisioni dei repository verticali: soli contatori SQL, nessuna fonte letta."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from pct.operational_live import read_tenant_live_revisions


def read_vertical_revisions(domains: set[str]) -> dict[str, int]:
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    from web.services.sentenza_economic_runtime import _tenant_id
    from web.services.tenant_paths import tenant_data_path

    revisions: dict[str, int] = {}

    def include(values: dict[str, int]) -> None:
        for domain, revision in values.items():
            revisions[domain] = revisions.get(domain, 0) + revision

    if "fascicoli" in domains:
        try:
            registry = registro_corrente(sola_lettura=True)
        except FileNotFoundError:
            registry = None
        if registry is not None:
            try:
                connection = registry.connection()
                context = connection if registry.backend_kind == "postgres" else closing(connection)
                with context as conn:
                    include(read_tenant_live_revisions(conn, "letture", tenant_corrente(), domains, postgres=registry.backend_kind == "postgres"))
            finally:
                registry.close()

    if domains & {"fascicoli", "incassi", "fatturazione"}:
        # È lo stesso archivio tenant-aware del servizio economico corrente.
        # La richiesta non istanzia il repository di scrittura né crea il DB.
        path = Path(tenant_data_path("SENTENZA_ECONOMIC_DB", require_tenant=True))
        if path.is_file():
            with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
                conn.execute("PRAGMA query_only=ON")
                include(read_tenant_live_revisions(conn, "economico", _tenant_id(), domains))
    return revisions


def legal_source_file_revision() -> list:
    """Invalidate legal projections from their tenant-owned repositories.

    Stat only, including WAL and legacy owners still used by the runtime;
    never instantiate writers, migrate, acquire or read document content.
    """
    from pct.legal_intelligence_repository import derive_legal_intelligence_repository_db_path
    from pct.legal_update_repository import derive_legal_updates_db_path
    from web.services.tenant_paths import tenant_data_path

    paths = []
    for key in ("LEGAL_INTELLIGENCE_DB", "LEGAL_UPDATES_DB", "NORMATIVE_TABLES_DB", "GIURISPRUDENZA_DB"):
        value = tenant_data_path(key, require_tenant=True)
        if not value:
            continue
        paths.append(Path(value))
        if key == "GIURISPRUDENZA_DB":
            from pct.giurisprudenza_corpus import derive_corpus_db_path
            from pct.giurisprudenza_repository import derive_giurisprudenza_repository_db_path
            paths.extend((Path(derive_corpus_db_path(value)),
                          Path(derive_giurisprudenza_repository_db_path(value))))
        if key == "LEGAL_INTELLIGENCE_DB":
            paths.extend((Path(derive_legal_updates_db_path(value)),
                          Path(derive_legal_intelligence_repository_db_path(value))))
    from flask import current_app
    import os
    shared = current_app.config.get("IUSENTRA_SENTENZEWEB_DIRECTORY") or os.getenv("IUSENTRA_SENTENZEWEB_DIRECTORY")
    if shared:
        paths.append(Path(shared) / "giurisprudenza_corpus.db")
    from web.services.giurisprudenza_public_corpus import PUBLIC_DATABASE_NAME
    public_directory = current_app.config.get("IUSENTRA_CORPUS_PUBBLICO_DIRECTORY") or os.getenv("IUSENTRA_CORPUS_PUBBLICO_DIRECTORY")
    if public_directory:
        paths.append(Path(public_directory) / PUBLIC_DATABASE_NAME)
    result = []
    from lex.retrieval.normativa_catalog import wal_revision

    for path in sorted(set(paths), key=str):
        try:
            stat = path.stat()
            result.append((str(path), stat.st_ino, stat.st_size, stat.st_mtime_ns))
        except FileNotFoundError:
            result.append((str(path), "absent"))
        # WAL vuoto e WAL assente sono lo stesso stato: una lettura non è un cambiamento (LEX-20).
        result.append(wal_revision(Path(str(path) + "-wal")))
    return result
