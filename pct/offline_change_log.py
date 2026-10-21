"""Registro incrementale di replica, distinto dai job applicativi consumabili.

Le scritture avvengono nella transazione del repository proprietario. Il
registro non applica dati business, non esegue commit e non invia messaggi.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any
from collections.abc import Callable
import sqlite3

from pct.offline_replication import _execute, _identifier


SCHEMA = (
    """CREATE TABLE IF NOT EXISTS offline_change_clock (
        tenant_id TEXT PRIMARY KEY, revision BIGINT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS offline_changes (
        tenant_id TEXT NOT NULL, revision BIGINT NOT NULL, operation_id TEXT NOT NULL,
        domain TEXT NOT NULL, resource_id TEXT NOT NULL, actor_id TEXT NOT NULL,
        source_device TEXT NOT NULL, base_revision TEXT NOT NULL,
        content_json TEXT NOT NULL, content_digest TEXT NOT NULL,
        PRIMARY KEY (tenant_id, revision), UNIQUE (tenant_id, operation_id))""",
    """CREATE INDEX IF NOT EXISTS offline_changes_resource
        ON offline_changes(tenant_id,domain,resource_id,revision)""",
)


def ensure_schema(conn: Any) -> None:
    for statement in SCHEMA:
        _execute(conn, statement)


def append_change(conn: Any, *, tenant: str, operation_id: str, domain: str,
                  resource_id: str, actor: str, source_device: str,
                  base_revision: str, content: dict, allowed_domains: frozenset[str]) -> int:
    """Registra una mutazione già validata, nella transazione business aperta.

    allowed_domains proviene dagli adapter installati, mai dalla richiesta.
    L'adapter conserva nel contenuto base, nuova versione e riferimenti ai file;
    questa funzione non autorizza la mutazione né determina fusioni automatiche.
    """
    for value in (tenant, operation_id, domain, resource_id, actor, source_device):
        _identifier(value)
    if isinstance(conn, sqlite3.Connection) and not conn.in_transaction:
        raise RuntimeError("La mutazione deve appartenere alla transazione del repository.")
    if domain not in allowed_domains:
        raise ValueError("Modulo non abilitato alla replica governata.")
    if not isinstance(base_revision, str) or len(base_revision) > 256 or not isinstance(content, dict):
        raise ValueError("Mutazione di replica non valida.")
    raw = json.dumps(content, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False)
    if len(raw.encode()) > 1024 * 1024:
        raise ValueError("Il documento va trasferito separatamente dalla mutazione.")
    identity = json.dumps([domain, resource_id, actor, source_device, base_revision, content],
                          sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    digest = hashlib.sha256(identity.encode()).hexdigest()
    # Serializza soltanto il contatore dello studio. Un retry perde al massimo
    # una UPDATE nella propria transazione, mai una revisione confermata.
    _execute(conn, """INSERT INTO offline_change_clock(tenant_id,revision)
        VALUES (?,0) ON CONFLICT (tenant_id) DO NOTHING""", (tenant,))
    _execute(conn, "UPDATE offline_change_clock SET revision=revision WHERE tenant_id=?", (tenant,))
    prior = _execute(conn, """SELECT revision,content_digest FROM offline_changes
        WHERE tenant_id=? AND operation_id=?""", (tenant, operation_id)).fetchone()
    if prior:
        if prior[1] != digest:
            raise ValueError("Operazione già registrata con contenuto differente.")
        return int(prior[0])
    revision = int(_execute(conn, """UPDATE offline_change_clock SET revision=revision+1
        WHERE tenant_id=? RETURNING revision""", (tenant,)).fetchone()[0])
    _execute(conn, """INSERT INTO offline_changes
        (tenant_id,revision,operation_id,domain,resource_id,actor_id,source_device,
         base_revision,content_json,content_digest) VALUES (?,?,?,?,?,?,?,?,?,?)""",
             (tenant, revision, operation_id, domain, resource_id, actor, source_device,
              base_revision, raw, digest))
    return revision


def read_changes(conn: Any, *, tenant: str, after: int, domains: frozenset[str],
                 authorized_resource: Callable[[str, str], bool], limit: int = 100) -> dict:
    """Pagina ordinata filtrata da permessi server, senza rileggere gli oggetti.

    Il cursore avanza sulle sole righe della pagina esaminata, anche quando
    l'ACL della risorsa impedisce di consegnarne il contenuto. Non confermare i file né
    l'applicazione remota con questa lettura. Il chiamante gestisce il bootstrap
    coerente e invalida il cursore se cambia il perimetro dei permessi.
    """
    _identifier(tenant)
    if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("Pagina della sincronizzazione non valida.")
    for domain in domains:
        _identifier(domain)
    if not domains:
        return {"items": [], "cursor": after, "has_more": False}
    placeholders = ",".join("?" for _ in domains)
    rows = _execute(conn, f"""SELECT revision,operation_id,domain,resource_id,actor_id,
        source_device,base_revision,content_json FROM offline_changes
        WHERE tenant_id=? AND revision>? AND domain IN ({placeholders})
        ORDER BY revision LIMIT ?""", (tenant, after, *sorted(domains), limit + 1)).fetchall()
    scanned = rows[:limit]
    items = [{"revision": int(row[0]), "operation_id": row[1], "domain": row[2],
              "resource_id": row[3], "actor": row[4], "source_device": row[5],
              "base_revision": row[6], "content": json.loads(row[7])} for row in scanned
             if authorized_resource(row[2], row[3])]
    return {"items": items, "cursor": int(scanned[-1][0]) if scanned else after,
            "has_more": len(rows) > limit}
