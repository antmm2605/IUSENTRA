#!/usr/bin/env python3
"""Reacquisisce un documento DocumentAI già archiviato, senza creare un nuovo record."""

from __future__ import annotations
import argparse, hashlib, json, shutil, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

def iso(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def sha(data): return hashlib.sha256(data).hexdigest()

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--tenant",required=True); p.add_argument("--fascicolo",required=True); p.add_argument("--document-ai-id",required=True)
 p.add_argument("--studio-db",required=True,type=Path); p.add_argument("--storage-root",required=True,type=Path)
 p.add_argument("--apply",action="store_true"); p.add_argument("--backup-dir",type=Path)
 a=p.parse_args()
 conn=sqlite3.connect(f"file:{a.studio_db}?mode=ro",uri=True); conn.row_factory=sqlite3.Row
 d=conn.execute("select * from fascicolo_documenti_ai where tenant_id=? and fascicolo_id=? and id=?",(a.tenant,a.fascicolo,a.document_ai_id)).fetchone()
 if not d: raise SystemExit("record DocumentAI non trovato")
 v=conn.execute("select * from fascicolo_documenti_ai_versioni where id=?",(d["current_version_id"],)).fetchone()
 if not v: raise SystemExit("versione corrente non trovata")
 raw=(a.storage_root / v["storage_path"]).read_bytes()
 report={"tenant":a.tenant,"fascicolo":a.fascicolo,"document_ai_id":a.document_ai_id,"old_version_id":v["id"],"storage_path":v["storage_path"],"bytes":len(raw),"expected_sha256":d["sha256"],"actual_sha256":sha(raw)}
 if report["expected_sha256"] != report["actual_sha256"]: raise SystemExit(json.dumps(report|{"error":"hash blob diverso"}))
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
 from pct.document_intelligence.extraction import extract_text_from_document
 ext=extract_text_from_document(raw, d["original_filename"], d["file_type"])
 report |= {"engine":ext.extraction_engine,"ok":ext.ok,"chars":len(ext.text),"pages":len(ext.pages),"warnings":ext.warnings}
 if not a.apply:
  print(json.dumps(report,ensure_ascii=False)); return
 if not a.backup_dir: raise SystemExit("--apply richiede --backup-dir")
 if not ext.ok or not ext.text.strip(): raise SystemExit(json.dumps(report|{"error":"estrazione non adottabile"},ensure_ascii=False))
 a.backup_dir.mkdir(parents=True,exist_ok=False)
 backup_path = a.backup_dir / "studio.db.before.sqlite"
 with sqlite3.connect(backup_path) as backup_conn:
  conn.backup(backup_conn)
  if backup_conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
   raise SystemExit("Backup SQLite non valido")
 backup_path.chmod(0o600)
 from pct.document_intelligence.repository import DocumentAIRepository
 from pct.document_intelligence.service import DocumentAIService
 repository = DocumentAIRepository.from_sqlite_db(a.studio_db, storage_root=a.storage_root)
 service = DocumentAIService(repository)
 text = service.reacquire_existing_version(
  a.tenant, a.fascicolo, a.document_ai_id, raw,
  {"skip_permission_check": True, "user_id": "reacquisition-script"},
 )
 refreshed = repository.get_document(a.tenant, a.fascicolo, a.document_ai_id)
 report |= {"new_version_id": text.version_id, "current_version_id": refreshed.current_version_id,
            "new_engine": text.extraction_engine, "new_pages": len(text.pages)}
 print(json.dumps(report, ensure_ascii=False))
if __name__=="__main__": main()
