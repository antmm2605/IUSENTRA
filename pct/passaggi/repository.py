"""Persistenza delle regole dello studio (SQLite tenant-aware o PostgreSQL).

Il repository è legato a uno studio (``tenant_id``) alla costruzione: nessun
metodo accetta il tenant dal chiamante, ogni query lo filtra. Registra anche
il diario di audit: chi ha creato, cambiato, disattivato o visto rifiutare una
regola, e la prima applicazione di ogni regola a ogni caso.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from pct.postgres_runtime_support import PostgresRepositoryBackend

from .applicazione import Applicazione
from .regole_studio import RegolaStudio

SCHEMA_SQLITE = Path(__file__).resolve().parent.parent / "sql" / "20261102_regole_studio.sql"
SCHEMA_POSTGRES = Path(__file__).resolve().parent.parent / "sql" / "20261102_regole_studio_postgres.sql"
_PRONTI: set[str] = set()
_LOCK = threading.Lock()
COLONNE = (
    "id", "tenant_id", "regola_id", "produttore", "azione", "campo", "valore", "ambito", "fascicolo_id", "ufficio",
    "giudice", "materia", "motivo", "autore_id", "autore_nome", "attiva", "passaggio_json", "creata_il", "aggiornata_il",
)


class RegoleStudioError(ValueError):
    """Errore comprensibile all'avvocato (regola inesistente, dati non validi)."""


def _adesso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RegoleStudioRepository:
    def __init__(self, db_path: str | Path, *, tenant_id: str, postgres_dsn: str = "") -> None:
        self.tenant_id = str(tenant_id or "").strip()
        if not self.tenant_id:
            raise RegoleStudioError("Studio non identificato.")
        self.db_path = Path(db_path)
        self._pg = PostgresRepositoryBackend(postgres_dsn, SCHEMA_POSTGRES) if str(postgres_dsn or "").strip() else None
        if self._pg is None:
            self._schema_sqlite()

    def _schema_sqlite(self) -> None:
        chiave = str(self.db_path.resolve())
        with _LOCK:
            if chiave in _PRONTI and self.db_path.exists():
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self.connection() as conn:
                conn.executescript(SCHEMA_SQLITE.read_text(encoding="utf-8"))
            _PRONTI.add(chiave)

    @contextmanager
    def connection(self) -> Iterator[Any]:
        if self._pg is not None:
            with self._pg.connection() as conn:
                yield conn
            return
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # --- lettura -----------------------------------------------------------------
    @staticmethod
    def _regola(riga: Any) -> RegolaStudio:
        dati = dict(riga)
        return RegolaStudio(
            id=dati["id"], regola_id=dati["regola_id"], produttore=dati["produttore"], azione=dati["azione"], campo=dati["campo"],
            valore=dati["valore"], ambito=dati["ambito"], fascicolo_id=dati["fascicolo_id"], ufficio=dati["ufficio"],
            giudice=dati["giudice"], materia=dati["materia"], motivo=dati["motivo"], autore_id=dati["autore_id"],
            autore_nome=dati["autore_nome"], attiva=bool(int(dati["attiva"] or 0)), creata_il=dati["creata_il"],
            aggiornata_il=dati["aggiornata_il"], passaggio_originale=json.loads(dati["passaggio_json"] or "{}"),
        )

    def elenco(self, *, solo_attive: bool = False) -> list[RegolaStudio]:
        sql = "SELECT * FROM regole_studio WHERE tenant_id = ?" + (" AND attiva = 1" if solo_attive else "") + " ORDER BY aggiornata_il DESC"
        with self.connection() as conn:
            return [self._regola(riga) for riga in conn.execute(sql, (self.tenant_id,)).fetchall()]

    def attive_per(self, regole_id: set[str]) -> list[RegolaStudio]:
        if not regole_id:
            return []
        segnaposti = ",".join("?" for _ in regole_id)
        with self.connection() as conn:
            righe = conn.execute(
                f"SELECT * FROM regole_studio WHERE tenant_id = ? AND attiva = 1 AND regola_id IN ({segnaposti})",
                (self.tenant_id, *sorted(regole_id)),
            ).fetchall()
        return [self._regola(riga) for riga in righe]

    def leggi(self, regola_studio_id: str) -> RegolaStudio:
        with self.connection() as conn:
            riga = conn.execute("SELECT * FROM regole_studio WHERE tenant_id = ? AND id = ?", (self.tenant_id, str(regola_studio_id))).fetchone()
        if riga is None:
            raise RegoleStudioError("Regola dello studio non trovata.")
        return self._regola(riga)

    def eventi(self, regola_studio_id: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM regole_studio_eventi WHERE tenant_id = ?"
        parametri: tuple[Any, ...] = (self.tenant_id,)
        if regola_studio_id:
            sql += " AND regola_studio_id = ?"
            parametri += (regola_studio_id,)
        with self.connection() as conn:
            righe = conn.execute(sql + " ORDER BY creato_il", parametri).fetchall()
        return [{**dict(riga), "dati": json.loads(dict(riga)["dati_json"] or "{}")} for riga in righe]

    def applicazioni(self, regola_studio_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            righe = conn.execute(
                "SELECT * FROM regole_studio_applicazioni WHERE tenant_id = ? AND regola_studio_id = ? ORDER BY prima_il",
                (self.tenant_id, regola_studio_id),
            ).fetchall()
        return [dict(riga) for riga in righe]

    # --- scrittura ----------------------------------------------------------------
    def _evento(self, conn: Any, regola_studio_id: str, evento: str, autore_id: str, dati: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO regole_studio_eventi (id, tenant_id, regola_studio_id, evento, autore_id, dati_json, creato_il) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), self.tenant_id, regola_studio_id, evento, autore_id, json.dumps(dati, ensure_ascii=False, default=str), _adesso()),
        )

    def crea(self, regola: RegolaStudio) -> RegolaStudio:
        regola.valida_forma()
        adesso = _adesso()
        regola.id, regola.creata_il, regola.aggiornata_il, regola.attiva = str(uuid.uuid4()), adesso, adesso, True
        valori = {
            "id": regola.id, "tenant_id": self.tenant_id, "regola_id": regola.regola_id, "produttore": regola.produttore,
            "azione": regola.azione, "campo": regola.campo, "valore": regola.valore, "ambito": regola.ambito,
            "fascicolo_id": regola.fascicolo_id, "ufficio": regola.ufficio, "giudice": regola.giudice, "materia": regola.materia,
            "motivo": regola.motivo[:600], "autore_id": regola.autore_id, "autore_nome": regola.autore_nome, "attiva": 1,
            "passaggio_json": json.dumps(regola.passaggio_originale, ensure_ascii=False, default=str), "creata_il": adesso, "aggiornata_il": adesso,
        }
        with self.connection() as conn:
            conn.execute(f"INSERT INTO regole_studio ({', '.join(COLONNE)}) VALUES ({', '.join('?' for _ in COLONNE)})",
                         tuple(valori[colonna] for colonna in COLONNE))
            self._evento(conn, regola.id, "creata", regola.autore_id, {"descrizione": regola.descrizione(), "motivo": regola.motivo})
        return regola

    def registra_rifiuto(self, regola: RegolaStudio, motivo: str) -> None:
        """Una correzione non salvata perché urta un vincolo inderogabile: resta nel diario."""
        with self.connection() as conn:
            self._evento(conn, "", "rifiutata", regola.autore_id,
                         {"regolaId": regola.regola_id, "descrizione": regola.descrizione(), "fascicoloId": regola.fascicolo_id, "motivo": motivo})

    def aggiorna(self, regola_studio_id: str, *, autore_id: str, valore: str | None = None, motivo: str | None = None, attiva: bool | None = None) -> RegolaStudio:
        regola = self.leggi(regola_studio_id)
        modifiche: dict[str, Any] = {}
        if valore is not None and valore != regola.valore:
            if regola.azione != "modifica_valore" or not valore.strip():
                raise RegoleStudioError("Il valore si cambia solo nelle regole che correggono un valore, e non può restare vuoto.")
            modifiche["valore"] = valore.strip()
        if motivo is not None and motivo != regola.motivo:
            modifiche["motivo"] = motivo[:600]
        if attiva is not None and attiva != regola.attiva:
            modifiche["attiva"] = 1 if attiva else 0
        if not modifiche:
            return regola
        modifiche["aggiornata_il"] = _adesso()
        evento = "modificata"
        if "attiva" in modifiche and len(modifiche) == 2:
            evento = "riattivata" if modifiche["attiva"] else "disattivata"
        assegnazioni = ", ".join(f"{colonna} = ?" for colonna in modifiche)
        with self.connection() as conn:
            conn.execute(f"UPDATE regole_studio SET {assegnazioni} WHERE tenant_id = ? AND id = ?",
                         (*modifiche.values(), self.tenant_id, regola.id))
            self._evento(conn, regola.id, evento, autore_id, {"prima": {k: getattr(regola, k) for k in ("valore", "motivo", "attiva")},
                                                               "dopo": {k: v for k, v in modifiche.items() if k != "aggiornata_il"}})
        return self.leggi(regola.id)

    def registra_applicazioni(self, applicazioni: list[Applicazione]) -> int:
        """La prima applicazione di ogni regola a ogni caso; le richieste successive non riscrivono."""
        if not applicazioni:
            return 0
        adesso = _adesso()
        with self.connection() as conn:
            for voce in applicazioni:
                conn.execute(
                    "INSERT INTO regole_studio_applicazioni (id, tenant_id, regola_studio_id, chiave_passaggio, fascicolo_id, esito, motivo, prima_il)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (tenant_id, regola_studio_id, chiave_passaggio, esito) DO NOTHING",
                    (str(uuid.uuid4()), self.tenant_id, voce.regola_studio_id, voce.chiave_passaggio, voce.fascicolo_id, voce.esito, voce.motivo[:600], adesso),
                )
        return len(applicazioni)


__all__ = ["RegoleStudioError", "RegoleStudioRepository", "SCHEMA_POSTGRES", "SCHEMA_SQLITE"]
