"""Riconciliazione read-only tra le fonti SQL di un tenant.

Non legge JSON come fonte decisionale e non ripara dati: segnala soltanto
divergenze osservabili, affinché ogni cutover resti esplicito e reversibile.
Il catalogo è intenzionalmente finito: non avvia scansioni ricorsive dei
filesystem tenant né indicizza documenti, OCR, ZIP o dataset rigenerabili.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

P0_TABLES = (
    "utenti",
    "audit_log",
    "clienti",
    "fascicoli",
    "appuntamenti",
    "scadenze",
    "preventivi_records",
    "conferimenti_records",
    "transactional_outbox",
)


@dataclass(frozen=True)
class P0DomainOwnership:
    """Inventario eseguibile di ownership e cutover SQL per i domini P0."""

    identifier: str
    label: str
    tables: tuple[str, ...]
    repository: str
    json_role: str = "mirror o bootstrap controllato"


P0_DOMAIN_OWNERSHIP = (
    P0DomainOwnership("identita", "Identità e audit", ("utenti", "audit_log"), "pct.auth.GestioneUtenti"),
    P0DomainOwnership("anagrafiche", "Clienti e anagrafiche", ("clienti",), "pct.clienti.GestioneClienti"),
    P0DomainOwnership("fascicoli", "Fascicoli", ("fascicoli",), "pct.fascicoli.GestioneFascicoli"),
    P0DomainOwnership("agenda", "Agenda", ("appuntamenti",), "pct.agenda.Agenda"),
    P0DomainOwnership("scadenze", "Scadenze e termini", ("scadenze",), "pct.scadenziario.GestioneScadenziario"),
    P0DomainOwnership("preventivi", "Preventivi e incarichi", ("preventivi_records", "conferimenti_records"), "pct.preventivi.GestionePreventivi"),
    P0DomainOwnership("outbox", "Eventi transazionali", ("transactional_outbox",), "pct.transactional_outbox"),
)


@dataclass(frozen=True)
class TableConsistency:
    table: str
    source_count: int | None
    target_count: int | None
    status: str
    reason: str = ""


def _count(backend: Any, table: str) -> int:
    row = backend.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    return int(row[0] if not hasattr(row, "keys") else row["n"])


def _backend_kind(backend: Any) -> str:
    return str(getattr(backend, "backend_kind", "sqlite") or "sqlite").lower()


def build_sql_consistency_snapshot(backend: Any) -> dict[str, Any]:
    """Restituisce il solo inventario SQL del tenant corrente, in sola lettura.

    Il chiamante deve fornire il backend già risolto dal runtime tenant-aware.
    Non deriva percorsi, non apre database paralleli e non conta mirror JSON.
    """

    domains: list[dict[str, Any]] = []
    all_readable = True
    outbox_summary = {"pending": 0, "processed": 0, "failed": 0, "total": 0, "readable": True}
    for domain in P0_DOMAIN_OWNERSHIP:
        table_rows: list[dict[str, Any]] = []
        domain_readable = True
        total = 0
        for table in domain.tables:
            try:
                count = _count(backend, table)
            except Exception as exc:  # noqa: BLE001 - il driver SQL dipende dal backend
                count = None
                domain_readable = False
                all_readable = False
                reason = exc.__class__.__name__
            else:
                reason = ""
                total += count
            table_rows.append({"table": table, "count": count, "reason": reason})
        if domain.identifier == "outbox" and domain_readable:
            try:
                rows = backend.conn.execute(
                    "SELECT status, COUNT(*) AS n FROM transactional_outbox GROUP BY status"
                ).fetchall()
                status_counts = {
                    str(row["status"] if hasattr(row, "keys") else row[0]).upper(): int(
                        row["n"] if hasattr(row, "keys") else row[1]
                    )
                    for row in rows
                }
                outbox_summary.update(
                    {
                        "pending": status_counts.get("PENDING", 0),
                        "processed": status_counts.get("PROCESSED", 0),
                        "failed": status_counts.get("FAILED", 0),
                        "total": total,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - il driver SQL dipende dal backend
                outbox_summary.update({"readable": False, "reason": exc.__class__.__name__})
                domain_readable = False
                all_readable = False
        domains.append(
            {
                "id": domain.identifier,
                "label": domain.label,
                "repository": domain.repository,
                "tables": table_rows,
                "records": total if domain_readable else None,
                "status": "PRESIDIATO" if domain_readable else "NON_LEGGIBILE",
                "json_role": domain.json_role,
            }
        )
    return {
        "ok": all_readable,
        "source_of_truth": _backend_kind(backend),
        "domains": domains,
        "outbox": outbox_summary,
        "contracts": {
            "writes": "none",
            "json_scanned": False,
            "fallback_used": False,
            "source_of_truth": "sql",
        },
    }


def reconcile_sql_backends(source: Any, target: Any, *, tables: tuple[str, ...] = P0_TABLES) -> dict[str, Any]:
    """Confronta conteggi SQL P0; errori di lettura non vengono nascosti."""

    results: list[TableConsistency] = []
    for table in tables:
        try:
            source_count = _count(source, table)
            target_count = _count(target, table)
        except Exception as exc:  # noqa: BLE001 - il driver SQL dipende dal backend
            results.append(TableConsistency(table, None, None, "UNREADABLE", exc.__class__.__name__))
            continue
        results.append(TableConsistency(table, source_count, target_count, "MATCH" if source_count == target_count else "MISMATCH"))
    return {
        "source_of_truth": "sql",
        "ok": all(item.status == "MATCH" for item in results),
        "tables": [item.__dict__ for item in results],
    }
