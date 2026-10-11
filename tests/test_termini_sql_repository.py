"""Guardrail su archivi controllati, non accettazione del prodotto."""
import copy
import os
import sqlite3
from types import SimpleNamespace

import pytest

from pct.termini_processuali import DeadlineAuditRecord
from pct.termini_processuali_repository import DDL, DeadlineSqlRepository, archive_records
from pct.termini_rule_revisions import rectify_native_caution


@pytest.fixture
def database(tmp_path):
    postgres = os.environ.get("TERMINI_TEST_POSTGRES") == "1"
    if postgres:
        import psycopg2
        from pct.storage_postgres import PostgresCompatConnection
        raw = psycopg2.connect(host=os.environ.get("TERMINI_TEST_PG_HOST", "audit-postgres"),
                               dbname=os.environ.get("AUDIT_POSTGRES_DB", "iusentra_audit"),
                               user=os.environ.get("AUDIT_POSTGRES_USER", "iusentra_audit"),
                               password=os.environ["AUDIT_POSTGRES_PASSWORD"])
        db = SimpleNamespace(raw_conn=raw)
        db.conn = PostgresCompatConnection(db)
        for statement in DDL:
            db.conn.execute(statement.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMP TABLE"))
    else:
        raw = sqlite3.connect(tmp_path / "termini.db")
        db = SimpleNamespace(conn=raw)
        repository(db).ensure_schema()
    db.conn.execute(("CREATE TEMP TABLE" if postgres else "CREATE TABLE") +
                    " audit_log (id TEXT PRIMARY KEY,timestamp TEXT,id_utente TEXT,username TEXT,"
                    "azione TEXT,risorsa_tipo TEXT,risorsa_id TEXT,dettagli TEXT,ip TEXT,esito TEXT)")
    raw.commit()
    yield db
    raw.close()


def repository(db, tenant="studio", actor="avvocato"):
    return DeadlineSqlRepository(db, tenant, source="archivio-storico.json", actor_key=actor,
                                 expected_adoption=("a" * 64, "backup-verificato"))


def adopt(repo, payload=None):
    return repo.initialize(payload or {}, source_sha256="a" * 64, backup_reference="backup-verificato")


def audit(key="calcolo-1", user="avvocato"):
    return DeadlineAuditRecord(id=key, template_code="CIV_APPELLO_BREVE", template_version=1,
                               case_reference="F1", user_id=user, input_date="2026-01-01",
                               calculated_deadline="2026-02-02", rules_applied=[],
                               engine_version="1", ruleset_version="1", calendar_version="1")


def test_no_ddl_or_import_in_constructor(tmp_path):
    conn = sqlite3.connect(tmp_path / "empty.db")
    try:
        repo = repository(SimpleNamespace(conn=conn))
        with pytest.raises(sqlite3.OperationalError):
            repo.list_templates()
        assert conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'termini_%'").fetchall() == []
        assert not repo.path.exists()
    finally:
        conn.close()


def test_missing_adoption_is_explicit(database):
    with pytest.raises(RuntimeError, match="non riscontrata"):
        repository(database).list_templates()


def test_verified_rule_revision_preserves_history_and_calculations(database):
    repo = repository(database)
    adopt(repo)
    repo.save_audit(audit())
    original = repo.get_template("CIV_APPELLO_BREVE").to_dict()
    replacement = {**original, "version": original["version"] + 1}
    arguments = dict(expected=original, replacement=replacement, revision="revisione-controllata",
                     reason="Prova di rettifica governata", source="fonte-controllata")
    assert repo.revise_template(original["code"], **arguments)["already_present"] is False
    assert repo.revise_template(original["code"], **arguments)["already_present"] is True
    assert repo.get_template(original["code"]).to_dict() == replacement
    assert repo.list_audit()[0]["template_version"] == 1
    assert repo._records("template_revisions")[0]["previous"] == original
    assert database.conn.execute("SELECT count(*) FROM audit_log WHERE azione='termini.revisione'").fetchone()[0] == 1


def test_rule_revision_does_not_overwrite_personalized_or_concurrent_rule(database):
    repo = repository(database)
    adopt(repo)
    original = repo.get_template("CIV_APPELLO_BREVE").to_dict()
    wrong_expected = {**original, "name": "Valore precedente non concordante"}
    with pytest.raises(ValueError, match="personalizzata"):
        repo.revise_template(original["code"], expected=wrong_expected,
                             replacement={**original, "version": 2}, revision="controllata",
                             reason="Prova", source="fonte-controllata")
    assert repo.get_template(original["code"]).to_dict() == original
    assert repo._records("template_revisions") == []
    assert database.conn.execute("SELECT revision FROM termini_state").fetchone()[0] == 0


def test_native_caution_revision_matches_only_known_previous_version(database):
    from pct.termini_processuali import DeadlineTemplate
    repo = repository(database)
    old = DeadlineTemplate(code="CIV_RECLAMO_CAUTELARE_669_TERDECIES", name="Reclamo cautelare",
                           base_value=15, reference_law="Art. 669-terdecies c.p.c.",
                           metadata={"source_event": "pronuncia_udienza"}).to_dict()
    adopt(repo, {"templates": [old]})
    assert rectify_native_caution(repo)["already_present"] is False
    assert repo.get_template(old["code"]).suspend_august is False
    assert rectify_native_caution(repo)["already_current"] is True
    assert len(repo._records("template_revisions")) == 1


def test_native_caution_personalized_version_is_explicitly_preserved(database):
    repo = repository(database)
    adopt(repo)
    original = repo.get_template("CIV_RECLAMO_CAUTELARE_669_TERDECIES").to_dict()
    customized = {**original, "name": "Regola personalizzata dello studio"}
    repo.revise_template(original["code"], expected=original, replacement=customized,
                         revision="personalizzazione", reason="Scelta controllata", source="studio")
    assert rectify_native_caution(repo)["requires_review"] is True
    assert repo.get_template(original["code"]).to_dict() == customized


def test_replay_requires_same_archive(database):
    repo = repository(database)
    assert adopt(repo)["already_present"] is False
    assert adopt(repo)["already_present"] is True
    with pytest.raises(ValueError, match="discordante"):
        adopt(repo, {"historical_note": "contenuto differente"})
    assert len(repo.list_templates()) > 0


def test_two_repository_instances_preserve_both_audits(database):
    first, second = repository(database), repository(database)
    adopt(first)
    one = first.save_audit(audit("uno"))
    two = second.save_audit(audit("due"))
    rows = first.list_audit()
    assert {row["id"] for row in rows} == {"uno", "due"}
    assert {row["immutable_hash"] for row in rows} == {one.immutable_hash, two.immutable_hash}
    assert len(first.list_audit(limit=1)) == 1


def test_audit_replay_and_conflict_are_immutable(database):
    repo = repository(database)
    adopt(repo)
    original = audit()
    first = repo.save_audit(original)
    assert repo.save_audit(original) == first
    changed = copy.copy(original)
    object.__setattr__(changed, "case_reference", "F2")
    with pytest.raises(RuntimeError, match="discordante"):
        repo.save_audit(changed)
    assert repo.list_audit()[0]["case_reference"] == "F1"


def test_other_studio_and_actor_cannot_read_or_write(database):
    repo = repository(database)
    adopt(repo)
    with pytest.raises(RuntimeError, match="non riscontrata"):
        repository(database, tenant="altro").list_templates()
    with pytest.raises(ValueError, match="Attore"):
        repo.save_audit(audit(user="altro"))
    assert repo.list_audit() == []


def test_bad_hash_and_duplicate_source_are_not_dropped():
    broken = audit().with_hash().to_dict()
    broken["calculated_deadline"] = "2026-02-03"
    with pytest.raises(ValueError, match="Impronta"):
        archive_records({"audit_logs": [broken]})
    with pytest.raises(ValueError, match="duplicato"):
        archive_records({"audit_logs": [audit().with_hash().to_dict()] * 2})


def test_historical_extra_fields_are_preserved():
    payload = {"guida_pratica_terms": [{"old": "fonte"}], "unknown_history": {"value": 1}}
    records = archive_records(payload)
    import json
    extra = next(row for row in records if row[0] == "archive_metadata")
    assert json.loads(extra[2]) == payload


def test_notification_replay_preserves_plan_and_rejects_conflict(database):
    repo = repository(database)
    adopt(repo)
    repo.save_audit(audit())
    plan = [{"idempotencyKey": "promemoria-1", "date": "2026-01-25", "daysLeft": 7}]
    arguments = {"deadline_id": "calcolo-1", "case_reference": "F1", "user_id": "avvocato"}
    assert repo.save_notification_plan(**arguments, notification_plan=plan) == 1
    original = repo.list_notification_logs()
    assert repo.save_notification_plan(**arguments, notification_plan=plan) == 0
    assert repo.list_notification_logs() == original
    with pytest.raises(RuntimeError, match="discordante"):
        repo.save_notification_plan(**arguments, notification_plan=[{**plan[0], "date": "2026-01-26"}])
    assert repo.list_notification_logs() == original


def test_notification_batch_rolls_back_on_conflict(database):
    repo = repository(database)
    adopt(repo)
    repo.save_audit(audit())
    arguments = {"deadline_id": "calcolo-1", "case_reference": "F1", "user_id": "avvocato"}
    first = {"idempotencyKey": "esistente", "date": "2026-01-25", "daysLeft": 7}
    repo.save_notification_plan(**arguments, notification_plan=[first])
    with pytest.raises(RuntimeError, match="discordante"):
        repo.save_notification_plan(**arguments, notification_plan=[
            {"idempotencyKey": "nuovo", "date": "2026-01-24", "daysLeft": 8},
            {**first, "date": "2026-01-26"},
        ])
    assert [row["idempotency_key"] for row in repo.list_notification_logs()] == ["esistente"]


def test_notification_requires_audit_in_same_studio(database):
    repo = repository(database)
    adopt(repo)
    with pytest.raises(ValueError, match="non presente nello studio"):
        repo.save_notification_plan(deadline_id="altro", case_reference="F1", user_id="avvocato",
                                    notification_plan=[{"idempotencyKey": "uno", "date": "2026-01-25"}])
    assert repo.list_notification_logs() == []


def test_live_signal_is_visible_after_commit_and_not_on_replay(tmp_path):
    from pct.operational_live import ensure_live_schema
    filename = tmp_path / "studio-controllato.db"
    writer = sqlite3.connect(filename)
    reader = sqlite3.connect(filename)
    try:
        db = SimpleNamespace(conn=writer)
        repo = repository(db)
        repo.ensure_schema()
        writer.execute("CREATE TABLE _meta(chiave TEXT PRIMARY KEY,valore TEXT)")
        writer.execute("CREATE TABLE audit_log (id TEXT PRIMARY KEY,timestamp TEXT,id_utente TEXT,username TEXT,"
                       "azione TEXT,risorsa_tipo TEXT,risorsa_id TEXT,dettagli TEXT,ip TEXT,esito TEXT)")
        ensure_live_schema(writer)
        adopt(repo)
        query = "SELECT revision FROM operational_live_revisions WHERE domain='scadenze'"
        before = reader.execute(query).fetchone()[0]
        writer.execute("UPDATE termini_state SET revision=revision+1 WHERE tenant_key='studio'")
        assert reader.execute(query).fetchone()[0] == before
        writer.rollback()
        assert reader.execute(query).fetchone()[0] == before
        repo.save_audit(audit())
        assert reader.execute(query).fetchone()[0] == before + 1
        repo.save_audit(audit())
        assert reader.execute(query).fetchone()[0] == before + 1
    finally:
        reader.close()
        writer.close()


def test_missing_native_caution_keeps_partial_historical_catalog(database):
    repo = repository(database)
    from pct.termini_processuali import DEFAULT_TEMPLATES
    only = DEFAULT_TEMPLATES[0].to_dict()
    adopt(repo, {"templates": [only]})
    result = rectify_native_caution(repo)
    assert result["requires_review"] is True
    assert repo.list_templates() == [only]
    assert database.conn.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 1


def test_imported_reclami_rectify_primary_rules_and_preserve_other_remedies(database):
    from pct.termini_guide_rule_revisions import legacy_rules, rectify_imported_reclami
    repo = repository(database)
    original = legacy_rules()
    adopt(repo, {"templates": original})
    results = rectify_imported_reclami(repo)
    assert len(results) == 4 and all(row["already_present"] is False for row in results)
    templates = repo.list_templates()
    family = [row for row in templates if row["metadata"].get("codice_guida") == "411003"]
    assert len(family) == 1 and family[0]["base_value"] == 10
    assert family[0]["matter_type"] == "civil"
    assert family[0]["ferial_suspension_policy"] == "manual_review"
    caution = [row for row in templates if row["metadata"].get("codice_guida") == "014100"]
    assert len(caution) == 1 and caution[0]["suspend_august"] is False
    assert repo.get_template_payload("GP_9B6E3BC346B9")["base_value"] == 60
    assert repo.get_template_payload("GP_0BD0BDFBBF7F")["base_value"] == 6
    assert all(row["already_current"] for row in rectify_imported_reclami(repo))
    assert database.conn.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 5


def test_imported_reclamo_personalization_is_preserved(database):
    from pct.termini_guide_rule_revisions import legacy_rules, rectify_imported_reclami
    original = legacy_rules()[0]
    customized = {**original, "base_value": 17, "metadata": {**original["metadata"], "decisione_manual": True}}
    repo = repository(database)
    adopt(repo, {"templates": [customized]})
    result = rectify_imported_reclami(repo)
    assert result[0]["requires_review"] is True
    assert repo.get_template_payload(original["code"]) == customized
    assert database.conn.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 1
