"""Adozione esplicita delle preparazioni: backup verificato prima del fence.

Si invoca dalla procedura amministrativa con produttori drenati e lock della
fonte condiviso; mai da una GET o dal caricamento dell'interfaccia.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from pct.udienze.repository import PreparazioniRepository, validate_record


def read_source(source):
    try:
        content = Path(source).read_bytes()
    except FileNotFoundError:
        content = None
    payload = [] if content is None else json.loads(content.decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Fonte delle preparazioni non valida: atteso un elenco, nessuna riga scartata.")
    records = [validate_record(record) for record in payload]
    if len({r["id"] for r in records}) != len(records):
        raise ValueError("Preparazioni duplicate: riconciliazione necessaria prima dell'adozione.")
    hearings = [r["id_appuntamento"] for r in records if r["id_appuntamento"]]
    if len(set(hearings)) != len(hearings):
        raise ValueError("Più preparazioni per la stessa udienza: nessuna copia cancellata.")
    fingerprint = hashlib.sha256(b"__absent_preparazioni_source__" if content is None else content).hexdigest()
    return records, fingerprint, content


def verify_references(db, records):
    """Solo le identità già registrate: nessuna scansione o lettura di allegati."""
    for item in records:
        row = db.conn.execute("SELECT id,dati_json,attivita_json,documenti_json FROM fascicoli WHERE id=?", (item["id_fascicolo"],)).fetchone()
        if row is None or json.loads(row[1]).get("id") != item["id_fascicolo"]:
            raise ValueError("Fascicolo della preparazione mancante o con identità SQL discordante.")
        for key in (item["id_appuntamento"], item["id_appuntamento_rinvio"]):
            if key:
                hearing = db.conn.execute("SELECT dati_json FROM appuntamenti WHERE id=?", (key,)).fetchone()
                if hearing is None or json.loads(hearing[0]).get("id") != key:
                    raise ValueError("Udienza della preparazione mancante o discordante.")
        documents = {doc["id"] for doc in json.loads(row[3] or "[]")}
        if any(doc.get("id_documento") and doc["id_documento"] not in documents for doc in item["checklist_documenti"]):
            raise ValueError("Documento collegato alla preparazione non presente nel fascicolo: recupero necessario.")
        activity = item["id_attivita_fascicolo"]
        if activity and not any(a.get("id") == activity for a in json.loads(row[2] or "[]")):
            raise ValueError("Attività della preparazione non presente nel fascicolo.")
        for term in item["termini_assegnati"]:
            key = term.get("id_scadenza", "")
            if not key:
                raise ValueError("Termine dell'esito senza consegna riscontrata: recupero necessario.")
            deadline = db.conn.execute("SELECT id_fascicolo,dati_json FROM scadenze WHERE id=?", (key,)).fetchone()
            payload = json.loads(deadline[1]) if deadline else {}
            if (deadline is None or deadline[0] != item["id_fascicolo"] or payload.get("id") != key
                    or payload.get("id_fascicolo") != item["id_fascicolo"]):
                raise ValueError("Termine della preparazione mancante o appartenente ad altro fascicolo.")


def verify_backup(destination, *, source, fingerprint, content, tenant, db, postgres):
    from deploy.hetzner.backup_structured import _sha256

    root = Path(destination).resolve()
    manifest = json.loads((root / "source-manifest.json").read_text(encoding="utf-8"))
    expected = {"tenant": tenant, "source": str(Path(source).resolve()), "source_sha256": fingerprint,
                "source_exists": content is not None, "sql_path": str(getattr(db, "db_path", "postgresql")), "postgres": postgres}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Backup delle preparazioni riferito a fonte, archivio o studio diversi.")
    sql_backup = root / ("studio-preparazioni.dump" if postgres else "studio-preparazioni.db")
    if not sql_backup.is_file() or not sql_backup.stat().st_size or _sha256(sql_backup) != manifest.get("backup", {}).get("sha256"):
        raise RuntimeError("Backup SQL delle preparazioni non riscontrato.")
    original = root / "preparazioni-original.json"
    if content is None:
        if original.exists():
            raise RuntimeError("Backup discordante sull'assenza della fonte.")
    elif not original.is_file() or original.read_bytes() != content:
        raise RuntimeError("Fonte originale delle preparazioni non riscontrata nel backup.")
    return manifest


def adopt_locked(db, source, *, tenant, destination, writers_drained, data_root):
    """Il chiamante mantiene prima_nota_source_lock sulla sola fonte Wizard."""
    from deploy.hetzner.backup_structured import _backup_sqlite
    from scripts.postgres_backup import backup_postgres
    from pct.prima_nota_transition import prepare_transition_locked, commit_transition_locked
    from pct.operational_live import ensure_live_schema

    if writers_drained is not True or not tenant:
        raise ValueError("Drain dei produttori e studio obbligatori per l'adozione delle preparazioni.")
    root, data = Path(destination).resolve(), Path(data_root).resolve()
    if not root.is_relative_to(data) or root == data or not Path(source).resolve().is_relative_to(data):
        raise ValueError("Fonte e backup delle preparazioni devono restare nel volume dati dello studio.")
    records, fingerprint, content = read_source(source)
    verify_references(db, records)
    if content is None:
        mirrors = db.conn.execute("SELECT count(*) FROM moduli_json_records WHERE modulo IN ('wizard_pro','preparazioni_udienze')").fetchone()[0]
        if mirrors:
            raise RuntimeError("Fonte delle preparazioni assente con mirror non vuoto: recupero necessario.")
    postgres = getattr(db, "backend_kind", "") == "postgresql"
    if root.exists():
        manifest = verify_backup(root, source=source, fingerprint=fingerprint, content=content, tenant=tenant, db=db, postgres=postgres)
    else:
        root.mkdir(parents=True, exist_ok=False)
        manifest = {"tenant": tenant, "source": str(Path(source).resolve()), "source_sha256": fingerprint,
                    "source_exists": content is not None, "sql_path": str(getattr(db, "db_path", "postgresql")), "postgres": postgres}
        if postgres:
            manifest["backup"] = backup_postgres(db.dsn, root / "studio-preparazioni.dump")
        else:
            if shutil.disk_usage(root).free < Path(db.db_path).stat().st_size + 1024**3:
                raise RuntimeError("Spazio insufficiente per il backup coerente delle preparazioni.")
            manifest["backup"] = _backup_sqlite(Path(db.db_path), root / "studio-preparazioni.db")
        if content is not None:
            (root / "preparazioni-original.json").write_bytes(content)
        (root / "source-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        verify_backup(root, source=source, fingerprint=fingerprint, content=content, tenant=tenant, db=db, postgres=postgres)
    current, current_sha, _ = read_source(source)
    if fingerprint != current_sha or current != records:
        raise RuntimeError("Fonte cambiata durante il backup: adozione sospesa.")
    verify_references(db, records)
    prepare_transition_locked(source, tenant=tenant, source_sha256=fingerprint)
    repository = PreparazioniRepository(db, tenant, actor="migrazione-preparazioni")
    repository.ensure_schema()
    ensure_live_schema(db.conn, postgres=postgres)
    repository.initialize(records, source_sha256=fingerprint, backup_reference=str(root))
    state = db.conn.execute("SELECT source_sha256,backup_reference FROM preparazioni_state WHERE tenant_key=?", (tenant,)).fetchone()
    if state is None or tuple(state[i] for i in range(2)) != (fingerprint, str(root)):
        raise RuntimeError("Adozione SQL non riscontrata: barriera conservata.")
    audit = db.conn.execute("SELECT dettagli,esito FROM audit_log WHERE azione='udienza.adozione' AND risorsa_id='__adoption' AND id_utente='migrazione-preparazioni'").fetchall()
    matches = [json.loads(row[0]) for row in audit if row[1] == "OK" and json.loads(row[0]).get("tenant") == tenant]
    expected = {"records": len(records), "source_sha256": fingerprint, "backup_reference": str(root)}
    if len(matches) != 1 or matches[0].get("after") != expected:
        raise RuntimeError("Audit dell'adozione non concordante: barriera conservata.")
    commit_transition_locked(source, tenant=tenant, source_sha256=fingerprint)
    return {"tenant": tenant, "source_sha256": fingerprint, "records": len(records), "backup": str(root), "phase": "committed"}
