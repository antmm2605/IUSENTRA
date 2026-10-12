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
