"""Incremental personal case notes, tombstones and idempotent optimistic writes."""

import json
from uuid import UUID

from .crypto import digest, encode
from .registry import DeviceRegistry


def identifier(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Identificativo della modifica non valido.")
    return value


def validate_note(payload):
    if not isinstance(payload, dict) or set(payload) != {"fascicolo_id", "title", "text", "attachment"}:
        raise ValueError("Nota non valida.")
    for field, limit in [("fascicolo_id", 128), ("title", 200), ("text", 32000)]:
        if not isinstance(payload[field], str) or len(payload[field]) > limit:
            raise ValueError("Nota troppo lunga o incompleta.")
    if not payload["fascicolo_id"] or not payload["title"].strip():
        raise ValueError("Seleziona il fascicolo e indica il titolo.")
    attachment = payload["attachment"]
    if attachment is not None:
        if not isinstance(attachment, dict) or set(attachment) != {"name", "text"}:
            raise ValueError("Allegato non valido: sono supportati documenti di testo.")
        if not isinstance(attachment["name"], str) or not 1 <= len(attachment["name"]) <= 120:
            raise ValueError("Nome allegato non valido.")
        if not isinstance(attachment["text"], str) or len(attachment["text"].encode()) > 65536:
            raise ValueError("Il documento di testo supera 64 KB.")
    return payload


class NoteSync(DeviceRegistry):
    def _record(self, row):
        return {"id": row[0], "version": int(row[1]), "deleted": bool(row[2]), "payload": json.loads(row[3])}

    def exchange(self, device_id, proof, intent, *, can_read, can_write, lease_seconds=86400):
        if not isinstance(intent, dict) or set(intent) != {"cursor", "operations"}:
            raise ValueError("Richiesta di aggiornamento non valida.")
        cursor, operations = intent["cursor"], intent["operations"]
        if type(cursor) is not int or cursor < 0 or not isinstance(operations, list) or len(operations) > 50:
            raise ValueError("Richiesta di aggiornamento troppo ampia o non valida.")
        with self.transaction() as conn:
            self.lock(conn)
            device = self.authenticate(conn, device_id, proof, "sync:" + digest(intent))
            high = conn.execute("SELECT revision FROM offline_state WHERE tenant_key=?", (self.tenant,)).fetchone()[0]
            if cursor > high:
                raise ValueError("Archivio locale da riconciliare: avanzamento non valido.")
            results = []
            for operation in operations:
                results.append(self._apply(conn, device_id, operation, can_read, can_write))
            rows = conn.execute(
                "SELECT note_id,revision,deleted,payload_json FROM offline_notes "
                "WHERE tenant_key=? AND actor_key=? AND revision>? ORDER BY revision LIMIT 100",
                (self.tenant, self.actor, cursor),
            ).fetchall()
            # Advance over inaccessible rows without returning any of their data.
            changes = [self._record(row) for row in rows if can_read(json.loads(row[3])["fascicolo_id"])]
            next_cursor = (
                int(rows[-1][1])
                if rows
                else int(
                    conn.execute("SELECT revision FROM offline_state WHERE tenant_key=?", (self.tenant,)).fetchone()[0]
                )
            )
            self.audit(conn, device_id, "notes.sync", {"received": len(operations), "returned": len(changes)})
            return {
                "ok": True,
                "tenant": self.tenant,
                "actor": self.actor,
                "device": device_id,
                "generation": device["generation"],
                "cursor": next_cursor,
                "has_more": len(rows) == 100,
                "authorized_ids": [
                    row[0]
                    for row in conn.execute(
                        "SELECT note_id,payload_json FROM offline_notes WHERE tenant_key=? AND actor_key=?",
                        (self.tenant, self.actor),
                    ).fetchall()
                    if can_read(json.loads(row[1])["fascicolo_id"])
                ],
                "changes": changes,
                "results": results,
                "lease_until": int(self.clock()) + lease_seconds,
            }

    def _apply(self, conn, device_id, op, can_read, can_write):
        if not isinstance(op, dict) or set(op) != {"command", "id", "base", "deleted", "payload"}:
            raise ValueError("Modifica non valida.")
        command, note_id = identifier(op["command"]), identifier(op["id"])
        if type(op["base"]) is not int or op["base"] < 0 or type(op["deleted"]) is not bool:
            raise ValueError("Versione della nota non valida.")
        payload = validate_note(op["payload"])
        if not can_write(payload["fascicolo_id"]):
            raise PermissionError("Non puoi modificare le note di questo fascicolo.")
        row = conn.execute(
            "SELECT note_id,revision,deleted,payload_json FROM offline_notes "
            "WHERE tenant_key=? AND actor_key=? AND note_id=?",
            (self.tenant, self.actor, note_id),
        ).fetchone()
        if row and (
            not can_read(json.loads(row[3])["fascicolo_id"]) or not can_write(json.loads(row[3])["fascicolo_id"])
        ):
            raise PermissionError("Accesso alla nota non consentito.")
        request_hash = digest(op)
        receipt = conn.execute(
            "SELECT request_hash,result_json FROM offline_commands WHERE tenant_key=? AND device_id=? AND command_id=?",
            (self.tenant, device_id, command),
        ).fetchone()
        if receipt:
            if receipt[0] != request_hash:
                raise ValueError("Il medesimo comando non può cambiare contenuto.")
            return json.loads(receipt[1])
        if (
            row is None
            and conn.execute(
                "SELECT COUNT(*) FROM offline_notes WHERE tenant_key=? AND actor_key=?", (self.tenant, self.actor)
            ).fetchone()[0]
            >= 1000
        ):
            raise ValueError("Limite della prima area offline raggiunto: massimo 1000 note personali.")
        current = self._record(row) if row else None
        if (current["version"] if current else 0) != op["base"] or (current and current["deleted"]):
            result = {"command": command, "status": "conflict", "current": current}
        else:
            revision = conn.execute(
                "UPDATE offline_state SET revision=revision+1 WHERE tenant_key=? RETURNING revision", (self.tenant,)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO offline_notes VALUES (?,?,?,?,?,?) ON CONFLICT(tenant_key,actor_key,note_id) DO UPDATE "
                "SET revision=excluded.revision,deleted=excluded.deleted,payload_json=excluded.payload_json",
                (self.tenant, self.actor, note_id, revision, int(op["deleted"]), encode(payload)),
            )
            result = {"command": command, "status": "accepted", "version": int(revision), "id": note_id}
            self.audit(
                conn,
                device_id,
                "note.deleted" if op["deleted"] else "note.saved",
                {"id": note_id, "version": int(revision)},
            )
        conn.execute(
            "INSERT INTO offline_commands VALUES (?,?,?,?,?)",
            (self.tenant, device_id, command, request_hash, encode(result)),
        )
        return result
