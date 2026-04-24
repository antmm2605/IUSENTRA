"""Repository SQLite per gli snapshot autorizzati del fascicolo SIGP."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SQLITE_SCHEMA = Path(__file__).resolve().parents[2] / "pct" / "sql" / "20260424_sigp_repository.sql"


class SigpSyncRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SQLITE_SCHEMA.read_text(encoding="utf-8"))
            conn.commit()

    def import_snapshot(self, normalized: dict, fascicolo_locale_id: str | None = None) -> dict:
        self.ensure_schema()
        fascicolo = normalized["fascicolo"]
        local_id = fascicolo_locale_id or fascicolo.get("fascicolo_locale_id") or None
        raw_json = _json(normalized.get("raw", {}))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                INSERT INTO sigp_sync_fascicoli (
                    sigp_uid, fascicolo_locale_id, ufficio_codice, ufficio, registro,
                    numero_rg, anno_rg, atto_introduttivo, rito, ruolo, materia,
                    oggetto, giudice, sezione, stato, data_iscrizione,
                    data_prima_comparizione, data_ultima_udienza, hash_snapshot,
                    raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(sigp_uid) DO UPDATE SET
                    fascicolo_locale_id=excluded.fascicolo_locale_id,
                    ufficio_codice=excluded.ufficio_codice,
                    ufficio=excluded.ufficio,
                    registro=excluded.registro,
                    numero_rg=excluded.numero_rg,
                    anno_rg=excluded.anno_rg,
                    atto_introduttivo=excluded.atto_introduttivo,
                    rito=excluded.rito,
                    ruolo=excluded.ruolo,
                    materia=excluded.materia,
                    oggetto=excluded.oggetto,
                    giudice=excluded.giudice,
                    sezione=excluded.sezione,
                    stato=excluded.stato,
                    data_iscrizione=excluded.data_iscrizione,
                    data_prima_comparizione=excluded.data_prima_comparizione,
                    data_ultima_udienza=excluded.data_ultima_udienza,
                    hash_snapshot=excluded.hash_snapshot,
                    raw_json=excluded.raw_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    fascicolo["sigp_uid"],
                    local_id,
                    fascicolo.get("ufficio_codice", ""),
                    fascicolo.get("ufficio", ""),
                    fascicolo.get("registro", ""),
                    fascicolo.get("numero_rg", ""),
                    fascicolo.get("anno_rg", ""),
                    fascicolo.get("atto_introduttivo", ""),
                    fascicolo.get("rito", ""),
                    fascicolo.get("ruolo", ""),
                    fascicolo.get("materia", ""),
                    fascicolo.get("oggetto", ""),
                    fascicolo.get("giudice", ""),
                    fascicolo.get("sezione", ""),
                    fascicolo.get("stato", ""),
                    fascicolo.get("data_iscrizione", ""),
                    fascicolo.get("data_prima_comparizione", ""),
                    fascicolo.get("data_ultima_udienza", ""),
                    normalized["hash_snapshot"],
                    raw_json,
                ),
            )
            row = conn.execute(
                "SELECT id FROM sigp_sync_fascicoli WHERE sigp_uid = ?",
                (fascicolo["sigp_uid"],),
            ).fetchone()
            fascicolo_id = int(row["id"])
            self._replace_children(conn, fascicolo_id, normalized)
            conn.execute(
                """
                INSERT INTO sigp_sync_log (
                    sigp_fascicolo_id, azione, esito, messaggio, dettagli_json
                ) VALUES (?, 'import_snapshot', 'ok', ?, ?)
                """,
                (
                    fascicolo_id,
                    "Snapshot SIGP importato da canale autorizzato.",
                    _json({"hash_snapshot": normalized["hash_snapshot"], "conteggi": _counts(normalized)}),
                ),
            )
            conn.commit()
        return {"ok": True, "sigp_fascicolo_id": fascicolo_id, "conteggi": _counts(normalized)}

    def get_snapshot(self, sigp_fascicolo_id: int) -> dict | None:
        self.ensure_schema()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            fascicolo = conn.execute(
                "SELECT * FROM sigp_sync_fascicoli WHERE id = ?",
                (sigp_fascicolo_id,),
            ).fetchone()
            if not fascicolo:
                return None
            return {
                "fascicolo": dict(fascicolo),
                "parti": self._fetch_children(conn, "sigp_sync_parti", sigp_fascicolo_id),
                "eventi": self._fetch_children(conn, "sigp_sync_eventi", sigp_fascicolo_id),
                "udienze": self._fetch_children(conn, "sigp_sync_udienze", sigp_fascicolo_id),
                "documenti": self._fetch_children(conn, "sigp_sync_documenti", sigp_fascicolo_id),
                "comunicazioni": self._fetch_children(conn, "sigp_sync_comunicazioni", sigp_fascicolo_id),
            }

    def _replace_children(self, conn: sqlite3.Connection, fascicolo_id: int, normalized: dict) -> None:
        for table in (
            "sigp_sync_parti",
            "sigp_sync_eventi",
            "sigp_sync_udienze",
            "sigp_sync_documenti",
            "sigp_sync_comunicazioni",
        ):
            conn.execute(f"DELETE FROM {table} WHERE sigp_fascicolo_id = ?", (fascicolo_id,))

        for item in normalized["parti"]:
            conn.execute(
                """
                INSERT INTO sigp_sync_parti (
                    sigp_fascicolo_id, ruolo, tipo, nome, cognome, denominazione,
                    codice_fiscale, partita_iva, difensore, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fascicolo_id,
                    item.get("ruolo", ""),
                    item.get("tipo", ""),
                    item.get("nome", ""),
                    item.get("cognome", ""),
                    item.get("denominazione", ""),
                    item.get("codice_fiscale", ""),
                    item.get("partita_iva", ""),
                    item.get("difensore", ""),
                    _json(item.get("raw", {})),
                ),
            )

        for item in normalized["eventi"]:
            conn.execute(
                """
                INSERT INTO sigp_sync_eventi (
                    sigp_fascicolo_id, evento_uid, tipo_evento, descrizione,
                    data_evento, data_udienza, esito, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fascicolo_id,
                    item.get("evento_uid", ""),
                    item.get("tipo_evento", ""),
                    item.get("descrizione", ""),
                    item.get("data_evento", ""),
                    item.get("data_udienza", ""),
                    item.get("esito", ""),
                    _json(item.get("raw", {})),
                ),
            )

        for item in normalized["udienze"]:
            conn.execute(
                """
                INSERT INTO sigp_sync_udienze (
                    sigp_fascicolo_id, udienza_uid, data_udienza, ora, tipo,
                    descrizione, esito, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fascicolo_id,
                    item.get("udienza_uid", ""),
                    item.get("data_udienza", ""),
                    item.get("ora", ""),
                    item.get("tipo", ""),
                    item.get("descrizione", ""),
                    item.get("esito", ""),
                    _json(item.get("raw", {})),
                ),
            )

        for item in normalized["documenti"]:
            conn.execute(
                """
                INSERT INTO sigp_sync_documenti (
                    sigp_fascicolo_id, documento_uid, id_deposito, id_repeatto,
                    nome_file, nome_originario, sezione, classificazione,
                    tipo_atto, data_deposito, data_documento, depositante,
                    mime_type, dimensione_bytes, scaricabile, path_locale,
                    sha256, tags_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fascicolo_id,
                    item.get("documento_uid", ""),
                    item.get("id_deposito", ""),
                    item.get("id_repeatto", ""),
                    item.get("nome_file", ""),
                    item.get("nome_originario", ""),
                    item.get("sezione", ""),
                    item.get("classificazione", ""),
                    item.get("tipo_atto", ""),
                    item.get("data_deposito", ""),
                    item.get("data_documento", ""),
                    item.get("depositante", ""),
                    item.get("mime_type", ""),
                    item.get("dimensione_bytes", 0),
                    1 if item.get("scaricabile", True) else 0,
                    item.get("path_locale", ""),
                    item.get("sha256", ""),
                    _json(item.get("tags", [])),
                    _json(item.get("raw", {})),
                ),
            )

        for item in normalized["comunicazioni"]:
            conn.execute(
                """
                INSERT INTO sigp_sync_comunicazioni (
                    sigp_fascicolo_id, comunicazione_uid, tipo, oggetto,
                    data_comunicazione, mittente, destinatario, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fascicolo_id,
                    item.get("comunicazione_uid", ""),
                    item.get("tipo", ""),
                    item.get("oggetto", ""),
                    item.get("data_comunicazione", ""),
                    item.get("mittente", ""),
                    item.get("destinatario", ""),
                    _json(item.get("raw", {})),
                ),
            )

    def _fetch_children(self, conn: sqlite3.Connection, table: str, fascicolo_id: int) -> list[dict]:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE sigp_fascicolo_id = ? ORDER BY id",
            (fascicolo_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _counts(normalized: dict) -> dict:
    return {
        "parti": len(normalized.get("parti", [])),
        "eventi": len(normalized.get("eventi", [])),
        "udienze": len(normalized.get("udienze", [])),
        "documenti": len(normalized.get("documenti", [])),
        "comunicazioni": len(normalized.get("comunicazioni", [])),
    }
