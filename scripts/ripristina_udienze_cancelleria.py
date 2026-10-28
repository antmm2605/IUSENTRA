#!/usr/bin/env python3
"""Ripristino governato (dry-run / --apply) delle udienze annullate dalla rettifica automatica del 17/09/2026
ma confermate da una comunicazione di cancelleria (pct/udienze/ripristino_cancelleria.py).

Dry-run (predefinito): stampa il piano, non scrive nulla.
--apply: richiede --backup-dir; copia studio.db con l'API di backup SQLite, poi in UNA transazione riporta
ogni udienza a PROGRAMMATO (colonne e dati_json concordi), aggiunge la nota con la prova e registra
l'operazione in audit_log. Se una riga e' cambiata rispetto al piano, non tocca nulla.
Le udienze ripristinate gia' trascorse compaiono poi fra i passi «Registrare l'esito dell'udienza».

Uso: python3 scripts/ripristina_udienze_cancelleria.py --studio-db <tenant>/studio.db \
       --archivio <tenant>/email/allegati/archivio-allegati.zip [--apply --backup-dir DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.udienze.ripristino_cancelleria import nota_ripristino, pianifica, prove_da_comunicazione  # noqa: E402


def _leggi(z: zipfile.ZipFile, allegato: dict) -> str:
    try:
        return z.read(allegato["archivio_membro"]).decode("utf-8", "replace")
    except (KeyError, TypeError):
        return ""


def raccogli_prove(conn: sqlite3.Connection, archivio: Path) -> list:
    prove = []
    with zipfile.ZipFile(archivio) as z:
        for chiave, payload in conn.execute(
                "SELECT message_key, payload_json FROM email_mailbox_records WHERE mailbox_kind='pec' "
                "AND payload_json LIKE '%Comunicazione.xml%'"):
            messaggio = json.loads(payload)
            allegati = messaggio.get("allegati") or []
            per_nome = {str(a.get("nome") or "").lower(): a for a in allegati if isinstance(a, dict)}
            if "comunicazione.xml" not in per_nome:
                continue
            prove += prove_da_comunicazione(_leggi(z, per_nome["comunicazione.xml"]),
                                            daticert=_leggi(z, per_nome.get("daticert.xml") or {}), pec_id=chiave,
                                            fascicolo_id=str(messaggio.get("linked_fascicolo_id") or ""))
    return prove


def appuntamenti(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for (dati,) in conn.execute("SELECT dati_json FROM appuntamenti WHERE tipo='UDIENZA' AND stato='ANNULLATO'"):
        d = json.loads(dati or "{}")
        d["_impronta"] = hashlib.sha256((dati or "").encode("utf-8")).hexdigest()
        out.append(d)
    return out


def applica(conn: sqlite3.Connection, piano, studio_db: Path, backup_dir: Path) -> dict:
    backup_dir.mkdir(parents=True, exist_ok=True)
    adesso = datetime.now(ZoneInfo("Europe/Rome"))
    copia = backup_dir / f"studio-prima-ripristino-udienze-{adesso:%Y%m%d-%H%M%S}-{uuid.uuid4().hex}.db"
    with copia.open("xb"):
        pass
    copia.chmod(0o600)
    with sqlite3.connect(copia) as dest:
        conn.backup(dest)
        if dest.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise RuntimeError("Backup non integro: ripristino non avviato.")
        if dest.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("Backup con riferimenti incoerenti: ripristino non avviato.")
    operazione = "ripristino-udienze-cancelleria-" + uuid.uuid4().hex
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        for voce in piano.ripristinare:
            riga = conn.execute("SELECT dati_json, stato FROM appuntamenti WHERE id=?", (voce["id"],)).fetchone()
            if riga is None or riga[1] != "ANNULLATO" or hashlib.sha256((riga[0] or "").encode()).hexdigest() != voce["impronta_riga"]:
                raise RuntimeError(f"Udienza {voce['id']} cambiata dopo il piano: nessuna modifica eseguita.")
            d = json.loads(riga[0])
            d["stato"] = "PROGRAMMATO"
            d["note"] = (str(d.get("note") or "") + "\n" + nota_ripristino(voce, operazione)).strip()
            d["modificato_il"] = adesso.isoformat(timespec="seconds")
            conn.execute("UPDATE appuntamenti SET stato=?, note=?, modificato_il=?, dati_json=? WHERE id=?",
                         (d["stato"], d["note"], d["modificato_il"], json.dumps(d, ensure_ascii=False), voce["id"]))
            conn.execute("INSERT INTO audit_log(id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (uuid.uuid4().hex, adesso.isoformat(timespec="seconds"), "sistema", "ripristino_udienze_cancelleria",
                          "RIPRISTINO_UDIENZA", "appuntamento", voce["id"],
                          json.dumps({"operazione": operazione, **voce}, ensure_ascii=False), "", "OK"))
    return {"operazione": operazione, "backup": str(copia), "ripristinate": len(piano.ripristinare)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--studio-db", type=Path, required=True)
    ap.add_argument("--archivio", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup-dir", type=Path)
    a = ap.parse_args()
    if a.apply and a.backup_dir is None:
        ap.error("--apply richiede --backup-dir")
    uri = a.studio_db.resolve().as_uri() + ("?mode=rw" if a.apply else "?mode=ro")
    conn = sqlite3.connect(uri, uri=True)
    piano = pianifica(appuntamenti(conn), raccogli_prove(conn, a.archivio))
    esito = {"dry_run": not a.apply, "da_ripristinare": len(piano.ripristinare),
             "annullate_dalla_rettifica_senza_prova": piano.senza_prova,
             "piano": [{k: v for k, v in voce.items() if k != "impronta_riga"} for voce in piano.ripristinare]}
    if a.apply and piano.ripristinare:
        esito.update(applica(conn, piano, a.studio_db, a.backup_dir))
    print(json.dumps(esito, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
