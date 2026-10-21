"""Primitivi per PC autorizzati; nessuna replica o azione esterna implicita.

Il chiamante fornisce tenant e attore dal contesto autenticato, mantiene la
transazione e applica i dati tramite i repository di dominio. Questo modulo
non espone SQL remoto e non conserva chiavi private.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, fields
from typing import Any

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS offline_devices (
        tenant_id TEXT NOT NULL, device_id TEXT NOT NULL, public_key TEXT NOT NULL,
        enrolled_by TEXT NOT NULL, enrolled_at BIGINT NOT NULL,
        expires_at BIGINT NOT NULL, revoked_at BIGINT,
        PRIMARY KEY (tenant_id, device_id))""",
    """CREATE TABLE IF NOT EXISTS offline_received_operations (
        tenant_id TEXT NOT NULL, device_id TEXT NOT NULL, operation_id TEXT NOT NULL,
        digest TEXT NOT NULL, received_at BIGINT NOT NULL,
        PRIMARY KEY (tenant_id, device_id, operation_id))""",
)


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:@-]{1,128}", value):
        raise ValueError("Identificativo di sincronizzazione non valido.")
    return value


def _execute(conn: Any, sql: str, values: tuple = ()):
    # Connessioni DB-API native. Non dedurre il dialetto da dati del client.
    sqlite = isinstance(conn, sqlite3.Connection)
    if not sqlite:
        sql = sql.replace("?", "%s")
    return conn.execute(sql, values)


def ensure_schema(conn: Any) -> None:
    """Migrazione esplicita, senza executescript/commit impliciti SQLite."""
    for statement in SCHEMA:
        _execute(conn, statement)


def enroll_device(conn: Any, *, tenant: str, device: str, public_key: str,
                  actor: str, now: int, expires_at: int) -> None:
    """Solo dopo autorizzazione online e prova di possesso del chiamante.

    Nessun upsert: una chiave esistente non è sostituibile da una nuova
    richiesta di associazione. L'autorizzazione RBAC appartiene alla route.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    for value in (tenant, device, actor):
        _identifier(value)
    if type(now) is not int or type(expires_at) is not int or not 0 <= now < expires_at:
        raise ValueError("Validità del PC non valida.")
    try:
        key = base64.b64decode(public_key, validate=True)
        Ed25519PublicKey.from_public_bytes(key)
    except (ValueError, TypeError) as exc:
        raise ValueError("Chiave pubblica del PC non valida.") from exc
    _execute(conn, """INSERT INTO offline_devices
        (tenant_id,device_id,public_key,enrolled_by,enrolled_at,expires_at)
        VALUES (?,?,?,?,?,?)""", (tenant, device, public_key, actor, now, expires_at))


def revoke_device(conn: Any, *, tenant: str, device: str, now: int) -> bool:
    _identifier(tenant)
    _identifier(device)
    if type(now) is not int or now < 0:
        raise ValueError("Data di revoca non valida.")
    row = _execute(conn, """UPDATE offline_devices SET revoked_at=?
        WHERE tenant_id=? AND device_id=? AND revoked_at IS NULL
        RETURNING device_id""", (now, tenant, device)).fetchone()
    return row is not None


def renew_device(conn: Any, *, tenant: str, device: str, public_key: str,
                 now: int, expires_at: int) -> bool:
    """Rinnovo dopo nuova autorizzazione online e prova della stessa chiave.

    Non cambia chiave o autore storico e non riattiva un PC revocato.
    """
    _identifier(tenant)
    _identifier(device)
    if type(now) is not int or type(expires_at) is not int or not 0 <= now < expires_at:
        raise ValueError('Validità del rinnovo non valida.')
    row = _execute(conn, """UPDATE offline_devices SET expires_at=?
        WHERE tenant_id=? AND device_id=? AND public_key=? AND revoked_at IS NULL
        AND enrolled_at<=? RETURNING device_id""",
                   (expires_at, tenant, device, public_key, now)).fetchone()
    return row is not None


@dataclass(frozen=True)
class SignedOperation:
    tenant: str
    device: str
    operation_id: str
    audience: str
    issued_at: int
    expires_at: int
    domain: str
    resource_id: str
    base_revision: str
    payload: dict
    actor: str = ""

    @classmethod
    def from_canonical(cls, raw: bytes) -> 'SignedOperation':
        """Il browser firma e inoltra questi byte senza riserializzarli.

        Evita differenze JavaScript/Python su decimali, esponenti e ordine
        delle chiavi Unicode. Rifiuta anche chiavi duplicate o sconosciute.
        """
        if not isinstance(raw, bytes) or len(raw) > 1024 * 1024:
            raise ValueError('Operazione firmata non valida.')
        try:
            data = json.loads(raw.decode('utf-8'))
        except RecursionError as exc:
            raise ValueError('Operazione firmata eccessivamente annidata.') from exc
        if not isinstance(data, dict) or type(data.get('protocol')) is not int or data.pop('protocol') != 1:
            raise ValueError('Protocollo della sincronizzazione non valido.')
        if set(data) != {field.name for field in fields(cls)}:
            raise ValueError('Campi dell’operazione firmata non validi.')
        operation = cls(**data)
        if operation.canonical_bytes() != raw:
            raise ValueError('Byte dell’operazione discordanti dalla forma firmata.')
        return operation

    def canonical_bytes(self) -> bytes:
        for value in (self.tenant, self.device, self.operation_id, self.domain, self.resource_id):
            _identifier(value)
        if self.actor:
            _identifier(self.actor)
        if not self.audience or not isinstance(self.audience, str):
            raise ValueError("Destinazione della sincronizzazione mancante.")
        if type(self.issued_at) is not int or type(self.expires_at) is not int:
            raise ValueError("Date dell'operazione non valide.")
        if not isinstance(self.base_revision, str) or len(self.base_revision) > 256:
            raise ValueError("Revisione di base non valida.")
        if not isinstance(self.payload, dict):
            raise ValueError("Contenuto dell'operazione non valido.")
        raw = json.dumps({"protocol": 1, **self.__dict__}, sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(raw) > 1024 * 1024:
            raise ValueError("Operazione troppo grande: usare il trasferimento documenti.")
        return raw

    def operation_digest(self) -> str:
        """Identità durevole distinta dalla breve finestra della richiesta.

        Dopo una lunga disconnessione il PC firma una nuova richiesta per la
        stessa operazione: cambiano le date di trasporto, non l'operazione.
        """
        data = json.loads(self.canonical_bytes())
        del data["issued_at"]
        del data["expires_at"]
        return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def verify_operation(conn: Any, operation: SignedOperation, signature: str, *,
                     authenticated_tenant: str, expected_audience: str, now: int,
                     authenticated_actor: str | None = None) -> str:
    """Verifica identità, revoca, scadenza e firma; nessuna scrittura business.

    Il digest restituito non è una conferma di applicazione: l'adapter deve
    controllare revisione, permessi e dipendenze nella transazione di scrittura.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    raw = operation.canonical_bytes()
    if authenticated_actor is not None:
        _identifier(authenticated_actor)
        if operation.actor != authenticated_actor:
            raise PermissionError("Autore della modifica discordante dalla sessione autenticata.")
    if operation.tenant != authenticated_tenant or operation.audience != expected_audience:
        raise PermissionError("PC o destinazione non autorizzati per questo studio.")
    if type(now) is not int or not operation.issued_at <= now < operation.expires_at:
        raise PermissionError("Operazione scaduta o non ancora valida.")
    if operation.expires_at - operation.issued_at > 300:
        raise PermissionError("Richiesta firmata con validità eccessiva.")
    row = _execute(conn, """SELECT public_key,enrolled_at,expires_at,revoked_at
        FROM offline_devices WHERE tenant_id=? AND device_id=?""",
                   (authenticated_tenant, operation.device)).fetchone()
    if row is None or row[3] is not None or not row[1] <= now < row[2]:
        raise PermissionError("PC non autorizzato, scaduto o revocato.")
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(row[0], validate=True))
        key.verify(base64.b64decode(signature, validate=True), raw)
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise PermissionError("Firma della richiesta di sincronizzazione non valida.") from exc
    return operation.operation_digest()


def reserve_operation(conn: Any, operation: SignedOperation, digest: str, *, now: int) -> bool:
    """Riserva idempotente nella STESSA transazione dell'adapter.

    True: nuova operazione; False: già applicata. Se l'adapter fallisce deve
    eseguire rollback anche della riserva. Non usare come conferma anticipata.
    """
    if digest != operation.operation_digest():
        raise ValueError("Impronta dell'operazione discordante.")
    inserted = _execute(conn, """INSERT INTO offline_received_operations
        (tenant_id,device_id,operation_id,digest,received_at) VALUES (?,?,?,?,?)
        ON CONFLICT (tenant_id,device_id,operation_id) DO NOTHING
        RETURNING operation_id""", (operation.tenant, operation.device,
                                    operation.operation_id, digest, now)).fetchone()
    if inserted is not None:
        return True
    existing = _execute(conn, """SELECT digest FROM offline_received_operations
        WHERE tenant_id=? AND device_id=? AND operation_id=?""",
                        (operation.tenant, operation.device, operation.operation_id)).fetchone()
    if existing is None or existing[0] != digest:
        raise ValueError("Identificativo già utilizzato per un'operazione diversa.")
    return False
