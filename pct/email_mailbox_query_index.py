"""Proiezione consultiva del catalogo posta, aggiornata nella transazione nativa.

Nessuna acquisizione o inizializzazione durante una ricerca. Gli archivi
precedenti richiedono una migrazione esplicita e verificata della proiezione.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from pct.formatting import DISPLAY_TIMEZONE

DDL = (
    """CREATE TABLE IF NOT EXISTS email_mailbox_query_index (
        tenant_key TEXT NOT NULL, mailbox_kind TEXT NOT NULL,
        message_key TEXT NOT NULL, event_at_utc TEXT NOT NULL,
        direction TEXT NOT NULL, deposit_status TEXT NOT NULL,
        source_revision TEXT NOT NULL,
        PRIMARY KEY (tenant_key,mailbox_kind,message_key))""",
    """CREATE INDEX IF NOT EXISTS idx_email_mailbox_query_period
        ON email_mailbox_query_index
        (tenant_key,mailbox_kind,direction,event_at_utc,message_key)""",
    """CREATE INDEX IF NOT EXISTS idx_email_mailbox_query_deposit
        ON email_mailbox_query_index
        (tenant_key,mailbox_kind,deposit_status,event_at_utc,message_key)""",
    """CREATE TABLE IF NOT EXISTS email_mailbox_query_bootstrap (
        tenant_key TEXT NOT NULL, mailbox_kind TEXT NOT NULL, version INTEGER NOT NULL,
        PRIMARY KEY (tenant_key,mailbox_kind))""",
    """CREATE TABLE IF NOT EXISTS email_mailbox_query_schema (
        singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS email_mailbox_query_migrations (
        id TEXT PRIMARY KEY, tenant_key TEXT NOT NULL, mailbox_kind TEXT NOT NULL,
        backup_reference TEXT NOT NULL, backup_sha256 TEXT NOT NULL, actor_key TEXT NOT NULL,
        after_key TEXT NOT NULL DEFAULT '', processed_count INTEGER NOT NULL DEFAULT 0,
        phase TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(tenant_key,mailbox_kind,backup_reference))""",
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_email_mailbox_query_active_migration
        ON email_mailbox_query_migrations(tenant_key,mailbox_kind) WHERE phase='BACKFILL'""",
)


def source_revision(record: dict) -> str:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def projected_fields(record: dict) -> tuple[str, str, str, str]:
    # ricevuta_il è anche la data dell'importazione locale: non dimostra
    # il giorno del messaggio originario se manca il suo campo data.
    raw = str(record.get('data') or '').strip()
    stamp = ''
    if raw:
        try:
            value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if value.tzinfo is None:
                value = value.replace(tzinfo=DISPLAY_TIMEZONE)
            stamp = value.astimezone(UTC).isoformat(timespec='microseconds')
        except ValueError:
            pass
    folder = str(record.get('cartella') or '').upper()
    origin = str(record.get('origine') or '').upper()
    if origin in {'INVIATA', 'INVIATI'} or folder == 'INVIATI':
        direction = 'sent'
    elif origin in {'BOZZA', 'BOZZE'} or folder == 'BOZZE':
        direction = 'draft'
    elif folder == 'INBOX':
        direction = 'received'
    else:
        # Una PEC spostata nel cestino non diventa automaticamente ricevuta.
        direction = 'unknown'
    return stamp, direction, str(record.get('stato_pct') or ''), source_revision(record)


def upsert_projection(conn, tenant: str, kind: str, key: str, record: dict) -> None:
    conn.execute(
        'INSERT INTO email_mailbox_query_index '
        '(tenant_key,mailbox_kind,message_key,event_at_utc,direction,deposit_status,source_revision) '
        'VALUES (?,?,?,?,?,?,?) ON CONFLICT (tenant_key,mailbox_kind,message_key) DO UPDATE SET '
        'event_at_utc=excluded.event_at_utc,direction=excluded.direction,'
        'deposit_status=excluded.deposit_status,source_revision=excluded.source_revision',
        (tenant, kind, key, *projected_fields(record)),
    )


def delete_projection(conn, tenant: str, kind: str, key: str) -> None:
    conn.execute('DELETE FROM email_mailbox_query_index '
                 'WHERE tenant_key=? AND mailbox_kind=? AND message_key=?',
                 (tenant, kind, key))
