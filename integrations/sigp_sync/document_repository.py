"""Repository documento SIGP: catalogo, allegati locali e download sicuro."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import sqlite3
from pathlib import Path
from typing import Any

from integrations.sigp.sync_repository import SigpSyncRepository
from integrations.sigp.sync_service import resolve_sigp_sync_db_path

from .document_catalog import normalize_document_catalog


class SigpDocumentRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.sync_repo = SigpSyncRepository(self.db_path)

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> "SigpDocumentRepository":
        return cls(resolve_sigp_sync_db_path(config or {}))

    def ensure_schema(self) -> None:
        self.sync_repo.ensure_schema()

    def fascicolo_exists(self, fascicolo_id: int) -> bool:
        self.ensure_schema()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT 1 FROM sigp_sync_fascicoli WHERE id = ?", (fascicolo_id,)).fetchone()
            return row is not None

    def list_documents(self, fascicolo_id: int) -> list[dict[str, Any]]:
        self.ensure_schema()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT *
                FROM sigp_sync_documenti
                WHERE sigp_fascicolo_id = ?
                ORDER BY
                    COALESCE(NULLIF(data_deposito, ''), NULLIF(data_documento, ''), created_at) DESC,
                    id DESC
                """,
                (fascicolo_id,),
            ).fetchall()
            return [self._decode_document_row(row) for row in rows]

    def get_document(self, fascicolo_id: int, documento_id: int) -> dict[str, Any] | None:
        self.ensure_schema()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM sigp_sync_documenti
                WHERE sigp_fascicolo_id = ? AND id = ?
                """,
                (fascicolo_id, documento_id),
            ).fetchone()
            return self._decode_document_row(row) if row else None

    def import_catalog(self, fascicolo_id: int, raw_catalog: Any, source: str = "catalogo_documenti") -> dict[str, Any]:
        self.ensure_schema()
        if not self.fascicolo_exists(fascicolo_id):
            raise ValueError(f"Fascicolo SIGP {fascicolo_id} non trovato.")

        documents = normalize_document_catalog(raw_catalog)
        inserted = 0
        updated = 0

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            for item in documents:
                existing = self._find_existing_document(conn, fascicolo_id, item)
                if existing:
                    self._update_document(conn, int(existing["id"]), item, preserve_local=True)
                    updated += 1
                else:
                    self._insert_document(conn, fascicolo_id, item)
                    inserted += 1

            self._log(
                conn,
                fascicolo_id,
                "import_catalogo_documenti",
                "ok",
                f"Catalogo documenti SIGP importato: {inserted} nuovi, {updated} aggiornati.",
                {"source": source, "nuovi": inserted, "aggiornati": updated, "totale_ricevuti": len(documents)},
            )
            conn.commit()

        return {
            "ok": True,
            "inserted": inserted,
            "updated": updated,
            "total": len(documents),
            "documents": self.list_documents(fascicolo_id),
        }

    def attach_local_file(
        self,
        fascicolo_id: int,
        documento_id: int,
        source_path: str | Path,
        storage_root: str | Path,
        original_filename: str | None = None,
    ) -> dict[str, Any]:
        """Copia un file gia' scaricato dall'utente e lo collega al documento.

        Serve quando il canale ufficiale non espone ancora il download automatico:
        l'avvocato scarica il PDF dal portale/PST e lo collega al record documento.
        """
        document = self.get_document(fascicolo_id, documento_id)
        if not document:
            raise ValueError("Documento SIGP non trovato.")

        src = Path(source_path)
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(f"File sorgente non trovato: {src}")

        storage_root = Path(storage_root)
        storage_dir = storage_root / "sigp" / str(fascicolo_id)
        storage_dir.mkdir(parents=True, exist_ok=True)

        safe_name = _safe_filename(original_filename or document.get("nome_file") or src.name)
        dest = storage_dir / safe_name
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            dest = storage_dir / f"{stem}-{documento_id}{suffix}"

        data = src.read_bytes()
        dest.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        mime_type = mimetypes.guess_type(str(dest))[0] or document.get("mime_type") or "application/octet-stream"
        rel_path = dest.relative_to(storage_root).as_posix()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE sigp_sync_documenti
                SET path_locale = ?, sha256 = ?, dimensione_bytes = ?, mime_type = ?
                WHERE sigp_fascicolo_id = ? AND id = ?
                """,
                (rel_path, digest, len(data), mime_type, fascicolo_id, documento_id),
            )
            self._log(
                conn,
                fascicolo_id,
                "allega_file_locale",
                "ok",
                f"File locale collegato al documento SIGP {documento_id}.",
                {"documento_id": documento_id, "path_locale": rel_path, "sha256": digest},
            )
            conn.commit()

        return {"ok": True, "path_locale": rel_path, "sha256": digest, "dimensione_bytes": len(data), "mime_type": mime_type}

    def set_downloaded_file(
        self,
        fascicolo_id: int,
        documento_id: int,
        storage_root: str | Path,
        filename: str,
        content: bytes,
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        document = self.get_document(fascicolo_id, documento_id)
        if not document:
            raise ValueError("Documento SIGP non trovato.")

        storage_root = Path(storage_root)
        storage_dir = storage_root / "sigp" / str(fascicolo_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_filename(filename or document.get("nome_file") or f"documento-{documento_id}.bin")
        dest = storage_dir / safe_name
        if dest.exists():
            stem, suffix = dest.stem, dest.suffix
            dest = storage_dir / f"{stem}-{documento_id}{suffix}"

        dest.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        rel_path = dest.relative_to(storage_root).as_posix()
        mime = mime_type or mimetypes.guess_type(str(dest))[0] or "application/octet-stream"

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE sigp_sync_documenti
                SET path_locale = ?, sha256 = ?, dimensione_bytes = ?, mime_type = ?
                WHERE sigp_fascicolo_id = ? AND id = ?
                """,
                (rel_path, digest, len(content), mime, fascicolo_id, documento_id),
            )
            self._log(
                conn,
                fascicolo_id,
                "download_documento",
                "ok",
                f"Documento SIGP {documento_id} scaricato tramite connettore locale.",
                {"documento_id": documento_id, "path_locale": rel_path, "sha256": digest},
            )
            conn.commit()

        return {"ok": True, "path_locale": rel_path, "sha256": digest, "dimensione_bytes": len(content), "mime_type": mime}

    def resolve_local_file(self, fascicolo_id: int, documento_id: int, storage_root: str | Path) -> Path:
        document = self.get_document(fascicolo_id, documento_id)
        if not document:
            raise ValueError("Documento SIGP non trovato.")
        rel_path = str(document.get("path_locale") or "").strip()
        if not rel_path:
            raise FileNotFoundError("Il documento non e' ancora stato scaricato o collegato a un file locale.")

        root = Path(storage_root).resolve()
        path = (root / rel_path).resolve()
        if not str(path).startswith(str(root)):
            raise PermissionError("Percorso documento non valido.")
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("File documento non presente nello storage locale.")
        return path

    def _decode_document_row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        try:
            item["tags"] = json.loads(item.get("tags_json") or "[]")
        except Exception:
            item["tags"] = []
        try:
            item["raw"] = json.loads(item.get("raw_json") or "{}")
        except Exception:
            item["raw"] = {}
        item["scaricato"] = bool(item.get("path_locale"))
        return item

    def _find_existing_document(self, conn: sqlite3.Connection, fascicolo_id: int, item: dict[str, Any]) -> sqlite3.Row | None:
        uid = item.get("documento_uid") or ""
        if uid:
            return conn.execute(
                """
                SELECT * FROM sigp_sync_documenti
                WHERE sigp_fascicolo_id = ? AND documento_uid = ?
                LIMIT 1
                """,
                (fascicolo_id, uid),
            ).fetchone()
        id_deposito = item.get("id_deposito") or ""
        if not id_deposito:
            return None
        return conn.execute(
            """
            SELECT * FROM sigp_sync_documenti
            WHERE sigp_fascicolo_id = ?
              AND COALESCE(id_deposito, '') = ?
              AND COALESCE(nome_file, '') = ?
              AND COALESCE(tipo_atto, '') = ?
            LIMIT 1
            """,
            (fascicolo_id, id_deposito, item.get("nome_file", ""), item.get("tipo_atto", "")),
        ).fetchone()

    def _insert_document(self, conn: sqlite3.Connection, fascicolo_id: int, item: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO sigp_sync_documenti (
                sigp_fascicolo_id, documento_uid, id_deposito, id_repeatto,
                nome_file, nome_originario, sezione, classificazione, tipo_atto,
                data_deposito, data_documento, depositante, mime_type,
                dimensione_bytes, scaricabile, path_locale, sha256, tags_json, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _document_params(fascicolo_id, item),
        )

    def _update_document(self, conn: sqlite3.Connection, document_id: int, item: dict[str, Any], preserve_local: bool = True) -> None:
        existing = conn.execute("SELECT path_locale, sha256 FROM sigp_sync_documenti WHERE id = ?", (document_id,)).fetchone()
        path_locale = item.get("path_locale", "")
        sha256 = item.get("sha256", "")
        if preserve_local and existing:
            path_locale = path_locale or existing["path_locale"] or ""
            sha256 = sha256 or existing["sha256"] or ""

        conn.execute(
            """
            UPDATE sigp_sync_documenti
            SET documento_uid = ?, id_deposito = ?, id_repeatto = ?, nome_file = ?,
                nome_originario = ?, sezione = ?, classificazione = ?, tipo_atto = ?,
                data_deposito = ?, data_documento = ?, depositante = ?, mime_type = ?,
                dimensione_bytes = ?, scaricabile = ?, path_locale = ?, sha256 = ?,
                tags_json = ?, raw_json = ?
            WHERE id = ?
            """,
            (
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
                int(item.get("dimensione_bytes") or 0),
                1 if item.get("scaricabile", True) else 0,
                path_locale,
                sha256,
                json.dumps(item.get("tags", []), ensure_ascii=False, sort_keys=True, default=str),
                json.dumps(item.get("raw", {}), ensure_ascii=False, sort_keys=True, default=str),
                document_id,
            ),
        )

    def _log(self, conn: sqlite3.Connection, fascicolo_id: int, azione: str, esito: str, messaggio: str, dettagli: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO sigp_sync_log (sigp_fascicolo_id, azione, esito, messaggio, dettagli_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (fascicolo_id, azione, esito, messaggio, json.dumps(dettagli, ensure_ascii=False, sort_keys=True, default=str)),
        )


def _document_params(fascicolo_id: int, item: dict[str, Any]) -> tuple[Any, ...]:
    return (
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
        int(item.get("dimensione_bytes") or 0),
        1 if item.get("scaricabile", True) else 0,
        item.get("path_locale", ""),
        item.get("sha256", ""),
        json.dumps(item.get("tags", []), ensure_ascii=False, sort_keys=True, default=str),
        json.dumps(item.get("raw", {}), ensure_ascii=False, sort_keys=True, default=str),
    )


def _safe_filename(value: str) -> str:
    name = os.path.basename(str(value or "documento.pdf")).strip() or "documento.pdf"
    cleaned = []
    for ch in name:
        if ch.isalnum() or ch in {".", "-", "_", " ", "(", ")"}:
            cleaned.append(ch)
        else:
            cleaned.append("_")
    return "".join(cleaned)[:180]
