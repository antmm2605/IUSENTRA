from __future__ import annotations

import json
from pathlib import Path

from pct.practice_engine import PracticeEngineRepository, get_profile
from web.services.react_fascicoli_bridge import _merge_practice_audit


def _repository_path(tmp_path: Path) -> Path:
    return tmp_path / "fascicoli" / "practice_engine" / "practice_engine.json"


def test_practice_engine_uses_sql_when_legacy_mirror_is_absent(tmp_path: Path):
    """Il mirror JSON non deve essere necessario per rileggere il presidio."""
    mirror_path = _repository_path(tmp_path)
    repository = PracticeEngineRepository(str(mirror_path))
    profile = get_profile("PROC_LIC_IMP_001")
    assert profile is not None

    saved = repository.apply_profile("FASCICOLO-SQL", profile, actor="avv.test", reason="Conferma esplicita")

    assert repository.source_of_truth == "sqlite"
    assert saved["id"]
    assert repository.studio_db.conn.execute(
        "SELECT code FROM practice_profiles WHERE fascicolo_id = ?", ("FASCICOLO-SQL",)
    ).fetchone()["code"] == "PROC_LIC_IMP_001"
    assert repository.studio_db.conn.execute(
        "SELECT event_type FROM practice_audit_events WHERE fascicolo_id = ?", ("FASCICOLO-SQL",)
    ).fetchone()["event_type"] == "PROFILE_APPLIED"

    mirror_path.unlink()
    reloaded = PracticeEngineRepository(str(mirror_path))

    assert reloaded.get_profile_snapshot("FASCICOLO-SQL")["code"] == "PROC_LIC_IMP_001"
    assert reloaded.list_audit("FASCICOLO-SQL")[0].event_type == "PROFILE_APPLIED"


def test_practice_engine_migrations_keep_sqlite_postgres_audit_parity():
    root = Path(__file__).resolve().parents[1]
    sqlite_schema = (root / "pct" / "sql" / "20260504_practice_engine.sql").read_text(encoding="utf-8")
    postgres_schema = (root / "pct" / "sql" / "20260504_practice_engine_postgres.sql").read_text(encoding="utf-8")

    for schema in (sqlite_schema, postgres_schema):
        assert "CREATE TABLE IF NOT EXISTS practice_audit_events" in schema
        assert "idx_practice_audit_events_fascicolo" in schema


def test_practice_engine_runtime_uses_canonical_tenant_studio_db():
    """Il mirror annidato non deve mai generare un secondo studio.db."""
    root = Path(__file__).resolve().parents[1]
    helpers = (root / "web" / "helpers.py").read_text(encoding="utf-8")
    core_runtime = (root / "web" / "services" / "core_runtime.py").read_text(encoding="utf-8")
    telematico_runtime = (root / "web" / "services" / "telematico_runtime.py").read_text(encoding="utf-8")

    assert 'studio_db=_studio_db("FASCICOLI_DB")' in helpers
    assert 'studio_db=get_studio_db("FASCICOLI_DB")' in core_runtime
    assert 'studio_db=get_studio_db("FASCICOLI_DB")' in telematico_runtime


def test_practice_engine_imports_only_missing_records_when_sql_already_has_other_fascicoli(tmp_path: Path):
    """Un mirror non deve essere ignorato soltanto perché SQL non è vuoto."""
    mirror_path = _repository_path(tmp_path)
    repository = PracticeEngineRepository(str(mirror_path))
    profile = get_profile("PROC_LIC_IMP_001")
    assert profile is not None
    repository.apply_profile("FASCICOLO-SQL", profile, actor="avv.sql", reason="Conferma SQL")

    mirror = json.loads(mirror_path.read_text(encoding="utf-8"))
    imported_profile = profile.to_dict()
    imported_profile.update({
        "id": "profile-mirror-only",
        "fascicolo_id": "FASCICOLO-MIRROR",
        "applied_at": "2026-08-24T20:00:00+00:00",
        "applied_by": "avv.mirror",
        "manual_reason": "Importazione storica controllata",
    })
    mirror["practice_profiles"].append(imported_profile)
    mirror["audit_events"].append({
        "id": "audit-mirror-only",
        "fascicolo_id": "FASCICOLO-MIRROR",
        "event_type": "PROFILE_APPLIED",
        "actor": "avv.mirror",
        "message": "Profilo storico confermato",
        "reason": "Importazione storica controllata",
        "payload": {},
        "created_at": "2026-08-24T20:00:00+00:00",
    })
    mirror_path.write_text(json.dumps(mirror, ensure_ascii=False), encoding="utf-8")

    reloaded = PracticeEngineRepository(str(mirror_path))

    assert reloaded.get_profile_snapshot("FASCICOLO-SQL")["code"] == "PROC_LIC_IMP_001"
    assert reloaded.get_profile_snapshot("FASCICOLO-MIRROR")["code"] == "PROC_LIC_IMP_001"
    assert reloaded.list_audit("FASCICOLO-MIRROR")[0].message == "Profilo storico confermato"


def test_practice_engine_imports_legacy_duplicate_profile_ids_per_fascicolo(tmp_path: Path):
    """I vecchi codici-profilo non possono violare la chiave SQL dello studio."""
    mirror_path = _repository_path(tmp_path)
    repository = PracticeEngineRepository(str(mirror_path))
    legacy = repository._empty()

    for fascicolo_id in ("FASCICOLO-UNO", "FASCICOLO-DUE"):
        legacy["practice_profiles"].append({
            "id": "PROC_LEGACY_SHARED",
            "fascicolo_id": fascicolo_id,
            "code": "PROC_LEGACY_SHARED",
            "name": "Profilo legacy condiviso",
            "applied_at": "2026-08-24T20:00:00+00:00",
            "applied_by": "avv.mirror",
        })
        legacy["practice_document_slots"].append({
            "id": f"slot-{fascicolo_id}",
            "fascicolo_id": fascicolo_id,
            "profile_id": "PROC_LEGACY_SHARED",
            "slot_key": "ATTO_PRINCIPALE",
            "label": "Atto principale",
            "type": "ATTO",
            "status": "MANCANTE",
        })

    mirror_path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    reloaded = PracticeEngineRepository(str(mirror_path))
    profiles = reloaded.studio_db.conn.execute(
        "SELECT id, fascicolo_id FROM practice_profiles ORDER BY fascicolo_id"
    ).fetchall()
    slots = reloaded.studio_db.conn.execute(
        "SELECT profile_id, fascicolo_id FROM practice_document_slots ORDER BY fascicolo_id"
    ).fetchall()

    assert [row["id"] for row in profiles] == [
        "profile::FASCICOLO-DUE::PROC_LEGACY_SHARED",
        "profile::FASCICOLO-UNO::PROC_LEGACY_SHARED",
    ]
    assert [(row["fascicolo_id"], row["profile_id"]) for row in slots] == [
        ("FASCICOLO-DUE", "profile::FASCICOLO-DUE::PROC_LEGACY_SHARED"),
        ("FASCICOLO-UNO", "profile::FASCICOLO-UNO::PROC_LEGACY_SHARED"),
    ]


def test_practice_audit_is_visible_as_operational_not_probatory_evidence(tmp_path: Path):
    repository = PracticeEngineRepository(str(_repository_path(tmp_path)))
    profile = get_profile("PROC_LIC_IMP_001")
    assert profile is not None
    repository.apply_profile("FASCICOLO-AUDIT", profile, actor="avv.test", reason="Conferma esplicita")

    merged = _merge_practice_audit(
        {
            "enabled": False,
            "available": False,
            "status": "not_configured",
            "message": "",
            "events": [],
            "summary": {"total": 0, "signed": 0, "worm": 0, "snapshotted": 0, "tsaVerified": 0},
            "actions": {"bundle": ""},
        },
        repository.list_audit("FASCICOLO-AUDIT"),
    )

    assert merged["status"] == "operational"
    assert merged["summary"]["total"] == 1
    assert merged["events"][0]["kindLabel"] == "Profilo procedurale confermato"
    assert merged["events"][0]["operational"] is True
