from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

spec = importlib.util.spec_from_file_location("normattiva_runtime_audit", Path(__file__).resolve().parents[1] / "deploy/hetzner/audit_normattiva_runtime.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_manifest_fingerprints_exact_files_without_mutating_database(tmp_path):
    db = tmp_path / "normattiva.sqlite"
    with sqlite3.connect(db) as conn:
        for name in ("normative_documents", "normative_articles", "normative_chunks", "normative_fts_info"):
            conn.execute("CREATE TABLE " + name + " (id INTEGER)")
            conn.execute("INSERT INTO " + name + " VALUES (1)")
    vectors = tmp_path / "vettori_normattiva"
    vectors.mkdir()
    (vectors / "meta.json").write_text(json.dumps({"righe": 1}))
    for name in ("vettori.i8", "scale.f32", "ids.i64", "impronte.u64"):
        (vectors / name).write_bytes(b"fixture")
    before = db.read_bytes()
    result = audit.manifest(db, vectors)
    assert db.read_bytes() == before
    assert result["counts"] == dict.fromkeys(("normative_documents", "normative_articles", "normative_chunks", "normative_fts_info"), 1)
    assert result["files"]["normattiva.sqlite"]["sha256"] == hashlib.sha256(before).hexdigest()
    assert result["library_file_sha256"] is None


def test_missing_file_is_not_claimed_equal(tmp_path):
    assert audit.file_sha(tmp_path / "absent") is None
