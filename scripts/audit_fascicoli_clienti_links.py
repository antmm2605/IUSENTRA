"""Audit tenant-aware dei link fascicolo-cliente.

La fonte di verità è lo SQLite `studio.db`: i JSON vengono aggiornati solo come
mirror quando si usa `--repair`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.clienti import Cliente, StatoCliente, TipoCliente


@dataclass
class OrphanLink:
    fascicolo_id: str
    numero: str
    titolo: str
    id_cliente: str
    nome_cliente: str
    avvocato_referente: str

    def to_dict(self) -> dict[str, str]:
        return {
            "fascicolo_id": self.fascicolo_id,
            "numero": self.numero,
            "titolo": self.titolo,
            "id_cliente": self.id_cliente,
            "nome_cliente": self.nome_cliente,
            "avvocato_referente": self.avvocato_referente,
        }


def _row_text(row: sqlite3.Row, key: str) -> str:
    return str(row[key] or "").strip()


def _load_orphans(conn: sqlite3.Connection) -> list[OrphanLink]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
            f.id AS fascicolo_id,
            f.numero AS numero,
            f.titolo AS titolo,
            f.id_cliente AS id_cliente,
            f.nome_cliente AS nome_cliente,
            f.avvocato_referente AS avvocato_referente
        FROM fascicoli f
        LEFT JOIN clienti c ON c.id = f.id_cliente
        WHERE f.id_cliente IS NOT NULL
          AND TRIM(f.id_cliente) <> ''
          AND c.id IS NULL
        ORDER BY f.numero, f.id
        """
    ).fetchall()
    return [
        OrphanLink(
            fascicolo_id=_row_text(row, "fascicolo_id"),
            numero=_row_text(row, "numero"),
            titolo=_row_text(row, "titolo"),
            id_cliente=_row_text(row, "id_cliente"),
            nome_cliente=_row_text(row, "nome_cliente"),
            avvocato_referente=_row_text(row, "avvocato_referente"),
        )
        for row in rows
    ]


def _split_person_name(display_name: str) -> tuple[str, str]:
    cleaned = " ".join(str(display_name or "").strip().split())
    if not cleaned:
        return "", ""
    parts = cleaned.split(" ")
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _cliente_from_orphan(orphan: OrphanLink, now: str) -> Cliente:
    cognome, nome = _split_person_name(orphan.nome_cliente)
    note = (
        "Anagrafica ricostruita da fascicolo con link cliente orfano: "
        f"{orphan.numero or orphan.fascicolo_id}."
    )
    return Cliente(
        id=orphan.id_cliente,
        tipo=TipoCliente.PERSONA_FISICA,
        stato=StatoCliente.ATTIVO,
        nome=nome,
        cognome=cognome or orphan.nome_cliente,
        avvocato_referente=orphan.avvocato_referente,
        provenienza="Ripristino tenant-aware da fascicolo",
        note=note,
        creato_il=now,
        modificato_il=now,
    )


def _backup_sqlite(studio_db: Path, backup_dir: Path, timestamp: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{studio_db.stem}.before-client-link-repair-{timestamp}.db"
    source = sqlite3.connect(f"file:{studio_db}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(target)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    return target


def _backup_file(path: Path, backup_dir: Path, timestamp: str) -> str:
    if not path.exists():
        return ""
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{path.name}.before-client-link-repair-{timestamp}.bak"
    shutil.copy2(path, target)
    return str(target)


def _upsert_clienti_json(clienti_json: Path, clienti: list[Cliente]) -> None:
    clienti_json.parent.mkdir(parents=True, exist_ok=True)
    raw: Any = {}
    if clienti_json.exists():
        try:
            raw = json.loads(clienti_json.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
    payloads = {cliente.id: cliente.to_dict() for cliente in clienti}
    if isinstance(raw, list):
        by_id = {
            str(item.get("id") or "").strip(): item
            for item in raw
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }
        by_id.update(payloads)
        raw = list(by_id.values())
    elif isinstance(raw, dict):
        raw.update(payloads)
    else:
        raw = payloads
    clienti_json.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _insert_clienti(conn: sqlite3.Connection, clienti: list[Cliente]) -> None:
    for cliente in clienti:
        payload = cliente.to_dict()
        recapiti = payload.get("recapiti") or {}
        conn.execute(
            """
            INSERT INTO clienti
            (id, tipo, stato, cognome, nome, ragione_sociale,
             codice_fiscale, partita_iva, email, telefono, note,
             creato_il, modificato_il, dati_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                cliente.id,
                cliente.tipo.value,
                cliente.stato.value,
                cliente.cognome,
                cliente.nome,
                cliente.ragione_sociale,
                cliente.codice_fiscale,
                cliente.partita_iva,
                recapiti.get("email", "") if isinstance(recapiti, dict) else "",
                recapiti.get("telefono", "") if isinstance(recapiti, dict) else "",
                cliente.note,
                cliente.creato_il,
                cliente.modificato_il,
                json.dumps(payload, ensure_ascii=False),
            ),
        )


def audit_fascicoli_clienti_links(
    studio_db: Path,
    *,
    repair: bool = False,
    clienti_json: Path | None = None,
) -> dict[str, Any]:
    studio_db = Path(studio_db)
    clienti_json = clienti_json or (studio_db.parent / "clienti" / "anagrafica.json")
    report: dict[str, Any] = {
        "ok": True,
        "source_of_truth": "sqlite",
        "json_authoritative": False,
        "studio_db": str(studio_db),
        "clienti_json": str(clienti_json),
        "repair": bool(repair),
        "orphans": [],
        "repaired": [],
        "backups": {},
        "errors": [],
    }
    if not studio_db.exists():
        report["ok"] = False
        report["errors"].append(f"studio.db non trovato: {studio_db}")
        return report

    conn = sqlite3.connect(studio_db)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        orphans = _load_orphans(conn)
        report["orphans"] = [orphan.to_dict() for orphan in orphans]
        if orphans and not repair:
            report["ok"] = False
            return report
        if orphans and repair:
            without_name = [orphan for orphan in orphans if not orphan.nome_cliente]
            if without_name:
                report["ok"] = False
                report["errors"].append(
                    "Sono presenti link orfani senza nome_cliente: riparazione automatica bloccata."
                )
                return report
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            backup_dir = studio_db.parent / "backup" / "client_link_repair"
            report["backups"]["sqlite"] = str(_backup_sqlite(studio_db, backup_dir, timestamp))
            report["backups"]["clienti_json"] = _backup_file(clienti_json, backup_dir, timestamp)
            clienti = [_cliente_from_orphan(orphan, datetime.now().isoformat()) for orphan in orphans]
            conn.execute("BEGIN IMMEDIATE")
            try:
                _insert_clienti(conn, clienti)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            _upsert_clienti_json(clienti_json, clienti)
            report["repaired"] = [cliente.id for cliente in clienti]
            remaining = _load_orphans(conn)
            report["orphans_after_repair"] = [orphan.to_dict() for orphan in remaining]
            report["ok"] = not remaining
        return report
    except Exception as exc:
        report["ok"] = False
        report["errors"].append(str(exc))
        return report
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio-db", required=True, type=Path)
    parser.add_argument("--clienti-json", type=Path, default=None)
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = audit_fascicoli_clienti_links(
        args.studio_db,
        repair=args.repair,
        clienti_json=args.clienti_json,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        status = "OK" if report.get("ok") else "KO"
        print(f"{status} source_of_truth={report['source_of_truth']} orphans={len(report.get('orphans') or [])}")
        for orphan in report.get("orphans") or []:
            print(
                f"- {orphan['numero'] or orphan['fascicolo_id']}: "
                f"{orphan['nome_cliente']} ({orphan['id_cliente']})"
            )
        if report.get("repaired"):
            print("Riparati: " + ", ".join(report["repaired"]))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
