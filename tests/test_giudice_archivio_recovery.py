from types import SimpleNamespace
import sqlite3

from pct.registro_letture import Fatto, Oggetto, RegistroLetture
from tests.test_giudice_da_provvedimento import TEXT, case
from web.services.giudice_archivio_recovery import recupera_da_testi_sql


def setup_source(tmp_path, *, engine="pdfplumber", record_hash="a" * 64):
    registry = RegistroLetture(tmp_path / "registro.db")
    source = Oggetto(tipo="documento", oggetto_id="source", sha256="a" * 64, nome="atto.pdf")
    registry.registra_inventario("tenant", "case", [source])
    registry.segna_letto("tenant", "case", source, "motore_documenti", versione="preserved-version", esito={"origine": "nativo", "fatti": 1}, durata_ms=57)
    registry.registra_fatti("tenant", "case", source, "documenti", [Fatto(categoria="data", campo="udienza", valore="2026-03-12", verifica="corretta")])
    record = SimpleNamespace(id="sql-source", sha256=record_hash, current_version_id="v1", updated_at="fixed", status="ready")
    calls = []

    def extracted(*args):
        calls.append(args)
        return SimpleNamespace(text=TEXT, extraction_engine=engine)

    repository = SimpleNamespace(list_documents=lambda *_: [record], get_extracted_text=extracted)
    return registry, repository, calls, record


def test_cached_source_adds_judge_preserving_other_facts_and_reading(tmp_path):
    registry, repository, calls, _ = setup_source(tmp_path)
    before = registry.letture("tenant", "case")[0]
    result = recupera_da_testi_sql(case(id="case"), registry, "tenant", repository)
    assert result["fatti"] == 1 and result["file_letti"] == 0
    facts = registry.fatti("tenant", "case", verifiche=None)
    assert {(f.campo, f.valore, f.verifica) for f in facts} == {
        ("udienza", "2026-03-12", "corretta"), ("giudice", "Veronica Vaccaro", "verificata")}
    after = registry.letture("tenant", "case")[0]
    assert (after.letto_il, after.versione_lettore, after.durata_ms, after.stato) == (before.letto_il, before.versione_lettore, 57, "letto")
    assert after.esito["origine"] == "nativo"
    assert recupera_da_testi_sql(case(id="case"), registry, "tenant", repository)["controllati"] == 0
    assert len(calls) == 1


def test_wrong_hash_and_other_tenant_never_extract_or_write(tmp_path):
    registry, repository, calls, _ = setup_source(tmp_path, record_hash="b" * 64)
    assert recupera_da_testi_sql(case(id="case"), registry, "tenant", repository)["fatti"] == 0
    assert recupera_da_testi_sql(case(id="case"), registry, "other", repository)["controllati"] == 0
    assert calls == []
    assert not registry.fatti("tenant", "case", campo="giudice")


def test_mixed_engine_can_recover_native_source_after_previous_ocr(tmp_path):
    registry, repository, _, _ = setup_source(tmp_path, engine='pdf-inspector:1.17.0:mixed')
    obj = registry.oggetti('tenant', 'case')[0]
    registry.segna_letto('tenant', 'case', obj, 'motore_documenti', esito={'origine': 'ocr'})
    checked = []
    def native_check(obj, record):
        checked.append(obj.oggetto_id)
        return TEXT
    result = recupera_da_testi_sql(case(id='case'), registry, 'tenant', repository, riscontro_nativo=native_check)
    assert result['fatti'] == 1 and checked == ['source']
    assert registry.letture('tenant', 'case')[0].esito['origine'] == 'ocr'


def test_ocr_not_promoted_and_changed_sql_version_resumes(tmp_path):
    registry, repository, calls, record = setup_source(tmp_path, engine="tesseract")
    assert recupera_da_testi_sql(case(id="case"), registry, "tenant", repository)["in_attesa_testo"] == 1
    assert recupera_da_testi_sql(case(id="case"), registry, "tenant", repository)["controllati"] == 0
    assert not registry.fatti("tenant", "case", campo="giudice")
    record.current_version_id = "v2"
    assert recupera_da_testi_sql(case(id="case"), registry, "tenant", repository)["controllati"] == 1
    assert len(calls) == 2


def test_category_upgrade_preserves_decisions_deliveries_and_auxiliary_objects(tmp_path):
    from pct.registro_letture.repository import SCHEMA_SQLITE

    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA_SQLITE.read_text(encoding="utf-8").replace(", 'metadato_fascicolo'", ""))
        conn.execute("CREATE INDEX retained_fact_index ON letture_fatti(oggetto_id)")
        conn.execute("CREATE TABLE retained_trigger_events (value TEXT)")
        conn.execute("CREATE TRIGGER retained_fact_trigger AFTER INSERT ON letture_fatti BEGIN INSERT INTO retained_trigger_events VALUES (NEW.id); END")
        conn.execute("INSERT INTO letture_fatti (id,tenant_id,fascicolo_id,tipo,oggetto_id,sha256,motore,chiave,letto_il,aggiornato_il,categoria,campo,valore,verifica,risolta_da) VALUES ('old','tenant','case','documento','source','hash','documenti','key','date','date','data','udienza','2026-03-12','corretta','avvocato')")
        before = conn.execute("SELECT * FROM letture_fatti").fetchall()
        conn.execute("INSERT INTO letture_consegne (id,tenant_id,fascicolo_id,fatto_id,presidio,stato,riferimento,aggiornato_il) VALUES ('receipt','tenant','case','old','agenda','consegnato','existing-appointment','date')")
    registry = RegistroLetture(path)
    with registry.connection() as conn:
        assert [tuple(r) for r in conn.execute("SELECT * FROM letture_fatti")] == before
        assert conn.execute("SELECT COUNT(*) FROM retained_trigger_events").fetchone()[0] == 1
        assert {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE name IN ('retained_fact_index','retained_fact_trigger')")} == {'retained_fact_index', 'retained_fact_trigger'}
        assert conn.execute("SELECT riferimento FROM letture_consegne WHERE fatto_id='old'").fetchone()[0] == 'existing-appointment'
    # Un secondo avvio non ricostruisce né duplica fatti o effetti.
    RegistroLetture(path)
    assert registry.fatti("tenant", "case")[0].verifica == "corretta"


def test_mixed_pdf_engine_requires_independent_native_source_before_writing(tmp_path):
    registry, repository, _, _ = setup_source(tmp_path, engine="pdf-inspector:controlled")
    calls = []

    def native(obj, record):
        calls.append(obj.oggetto_id)
        return TEXT

    result = recupera_da_testi_sql(case(id="case"), registry, "tenant", repository, riscontro_nativo=native)
    assert result["fatti"] == 1 and result["file_letti"] == 1 and calls == ["source"]
    assert registry.fatti("tenant", "case", campo="giudice")[0].verifica == 'verificata'
