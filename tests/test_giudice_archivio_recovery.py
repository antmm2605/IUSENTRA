from types import SimpleNamespace
import sqlite3
import pytest

from pct.registro_letture import Fatto, Oggetto, RegistroLetture
from tests.test_giudice_da_provvedimento import TEXT, case
from web.services.giudice_archivio_recovery import recupera_da_testi_sql


@pytest.mark.parametrize("discordanza", ["", "cliente", "rg", "ufficio"])
def test_native_economic_recovery_updates_existing_sql_audit_without_invoice_or_replay(tmp_path, monkeypatch, discordanza):
    from tests.test_fascicolo_sentenza_economica import FakeFascicoliRepository, SENTENZA_TEXT
    from pct.fatturazione import GestioneFatturazione
    from pct.sentenza_economic_repository import SentenzaEconomicRepository
    from web.services import document_intelligence_runtime as documents
    from web.services import sentenza_economic_runtime as economics
    from web.services.giudice_archivio_recovery import recupera_giudice

    cases = FakeFascicoliRepository()
    case_record = cases.fascicolo
    case_record.documenti = [SimpleNamespace(id="source", tipo="SENTENZA", nome="sentenza.pdf", hash_sha256="a" * 64)]
    registry = RegistroLetture(tmp_path / "registry.db")
    source = Oggetto(tipo="documento", oggetto_id="source", sha256="a" * 64, nome="sentenza.pdf")
    registry.registra_inventario("tenant", case_record.id, [source])
    registry.segna_letto("tenant", case_record.id, source, "motore_documenti", esito={"origine": "nativo"})
    text = SENTENZA_TEXT.replace("€ 1.100,00", "321,00 euro")
    substitutions = {"cliente": ("Spagnolo Sara", "Bianchi Anna"), "rg": ("1548/2023", "1549/2023"),
                     "ufficio": ("Tribunale di Palmi", "Tribunale di Torino")}
    if discordanza:
        text = text.replace(*substitutions[discordanza])
    record = SimpleNamespace(id="sql-source", sha256="a" * 64, current_version_id="v1", updated_at="fixed", status="ready")
    sql = SimpleNamespace(list_documents=lambda *_: [record], get_extracted_text=lambda *_: SimpleNamespace(text=text, extraction_engine="pdfplumber"))
    invoices = GestioneFatturazione(str(tmp_path / "invoices.json"))
    audit_repo = SentenzaEconomicRepository(str(tmp_path / "economics.db"), decisions_path=str(tmp_path / "decisions.jsonl"))
    monkeypatch.setattr("web.helpers.get_clienti", lambda: SimpleNamespace(get=lambda _: SimpleNamespace(codice_fiscale="")))
    monkeypatch.setattr(documents, "build_document_ai_service", lambda: SimpleNamespace(repository=sql))
    monkeypatch.setattr(documents, "get_fascicoli", lambda: cases)
    monkeypatch.setattr(documents, "get_fatturazione", lambda: invoices)
    # Vector ingestion has separate native integration tests; keep this test on economic SQL writes.
    monkeypatch.setattr(documents, "_sentenza_vector_index_ok", lambda **_: True)
    monkeypatch.setattr(economics, "_repo", lambda: audit_repo)
    monkeypatch.setattr(economics, "_cu_tiers", lambda: [])
    recupera_giudice(case_record, registry, "tenant")
    audits = audit_repo.list_sentenza_audits("tenant", fascicolo_id=case_record.id)
    before = dict(case_record.pagamenti)
    assert recupera_giudice(case_record, registry, "tenant")["controllati"] == 0
    assert case_record.pagamenti == before
    assert audit_repo.list_sentenza_audits("tenant", fascicolo_id=case_record.id) == audits
    assert invoices.per_fascicolo(case_record.id) == []
    if discordanza:
        assert not audits and not case_record.pagamenti
    else:
        assert len(audits) == 1 and audits[0]["documento_id"] == "source"
        payment = case_record.pagamenti["liquidazione_giudice"]
        assert payment["importo"] == 321.0 and not payment["pagato"]
        assert payment["documento_fonte"] == "document_id:sql-source"
        assert "parcella" not in case_record.pagamenti


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


def test_economic_rule_upgrade_reuses_same_source_once_and_preserves_other_facts(tmp_path):
    registry, repository, calls, _ = setup_source(tmp_path)
    recupera_da_testi_sql(case(id="case"), registry, "tenant", repository)
    before = registry.letture("tenant", "case")[0]
    invoked = []

    def recover(obj, record, text):
        invoked.append((obj.oggetto_id, record.current_version_id, text))
        return [Fatto(categoria="evento", campo="controllo_economico", valore="analizzato",
                      verifica="verificata", prove=[{"codice": "audit_economico", "dettaglio": "updated"}])]

    kwargs = {"documenti_economici": ("source",), "recupero_economico": recover}
    assert recupera_da_testi_sql(case(id="case"), registry, "tenant", repository, **kwargs)["fatti"] == 2
    assert len(invoked) == 1 and len(calls) == 2
    assert recupera_da_testi_sql(case(id="case"), registry, "tenant", repository, **kwargs)["controllati"] == 0
    assert len(invoked) == 1 and len(calls) == 2
    facts = registry.fatti("tenant", "case", verifiche=None)
    assert len([f for f in facts if f.campo == "controllo_economico"]) == 1
    assert next(f for f in facts if f.campo == "udienza").verifica == "corretta"
    after = registry.letture("tenant", "case")[0]
    assert (after.letto_il, after.versione_lettore, after.durata_ms) == (before.letto_il, before.versione_lettore, before.durata_ms)


def test_economic_recovery_never_uses_wrong_imprint_tenant_or_ocr(tmp_path):
    for suffix, engine, sha, tenant in (
        ("hash", "pdfplumber", "b" * 64, "tenant"),
        ("tenant", "pdfplumber", "a" * 64, "other"),
        ("ocr", "tesseract", "a" * 64, "tenant"),
    ):
        folder = tmp_path / suffix
        folder.mkdir()
        registry, repository, _, _ = setup_source(folder, engine=engine, record_hash=sha)
        invoked = []
        recupera_da_testi_sql(case(id="case"), registry, tenant, repository,
                            documenti_economici=("source",), recupero_economico=lambda *args: invoked.append(args))
        assert invoked == []


def test_economic_recovery_respects_manual_decision_and_other_document(tmp_path):
    registry, repository, _, _ = setup_source(tmp_path)
    obj = registry.oggetti("tenant", "case")[0]
    registry.registra_fatti("tenant", "case", obj, "documenti", [
        Fatto(categoria="evento", campo="controllo_economico", valore="analizzato", verifica="ignorata")])
    calls = []
    recupera_da_testi_sql(case(id="case"), registry, "tenant", repository,
                        documenti_economici=("source",), recupero_economico=lambda *args: calls.append(args))
    assert calls == []
    assert registry.fatti("tenant", "case", verifiche=None, campo="controllo_economico")[0].verifica == "ignorata"
    recupera_da_testi_sql(case(id="case"), registry, "tenant", repository,
                        documenti_economici=("another-document",), recupero_economico=lambda *args: calls.append(args))
    assert calls == []


def test_failed_economic_delivery_has_no_success_checkpoint_and_can_retry(tmp_path):
    import pytest
    registry, repository, _, _ = setup_source(tmp_path)

    def fail(*_):
        raise RuntimeError("Consegna non confermata")

    with pytest.raises(RuntimeError, match="Consegna non confermata"):
        recupera_da_testi_sql(case(id="case"), registry, "tenant", repository,
                            documenti_economici=("source",), recupero_economico=fail)
    assert "controllo_metadati" not in registry.letture("tenant", "case")[0].esito
    calls = []
    result = recupera_da_testi_sql(case(id="case"), registry, "tenant", repository,
                                 documenti_economici=("source",), recupero_economico=lambda *args: calls.append(args) or [])
    assert result["controllati"] == 1 and len(calls) == 1


def test_mixed_engine_requires_native_check_for_economic_source(tmp_path):
    registry, repository, _, _ = setup_source(tmp_path, engine="pdf-inspector:controlled")
    repository.get_extracted_text = lambda *_: SimpleNamespace(text="Solo dati economici", extraction_engine="pdf-inspector:controlled")
    calls = []
    checked = []
    result = recupera_da_testi_sql(case(id="case"), registry, "tenant", repository,
        documenti_economici=("source",), recupero_economico=lambda *args: calls.append(args) or [],
        riscontro_nativo=lambda *args: checked.append(args) or "Testo nativo riscontrato")
    assert result["file_letti"] == 1 and len(checked) == 1 and len(calls) == 1
    assert calls[0][-1] == "Testo nativo riscontrato"


@pytest.mark.parametrize("decision", ["", "corretta", "ignorata", "verificata_manual"])
def test_contribution_recovery_same_imprint_once_preserves_manual_and_other_facts(tmp_path, decision):
    from pct.archivio_letture.estrazione_importi import importo_contributo_unificato
    from tests.test_react_fascicoli_sentenze_economiche import _SCHEMA_REGISTRO_ESENTE
    from pct.archivio_letture.presidio_economico import contributo_verificato

    registry, repository, _, record = setup_source(tmp_path)
    obj = registry.oggetti("tenant", "case")[0]
    old = Fatto(categoria="evento", campo="esenzione_cu_dichiarata", valore="dichiarazione_presente",
                origine="nativo", verifica=decision if decision in {"corretta", "ignorata"} else "verificata",
                prove=[{"codice": "decisione_avvocato", "esito": "ok", "dettaglio": "Scelta registrata"}] if decision == "verificata_manual" else [])
    registry.registra_fatti("tenant", "case", obj, "documenti", [old, Fatto(categoria="data", campo="udienza", valore="2026-03-12", verifica="corretta")])
    case_record = SimpleNamespace(id="case", nome_cliente="Bianchi Anna", numero_rg="493", anno_rg="2024", tribunale="Tribunale di Palmi")
    repository.get_extracted_text = lambda *_: SimpleNamespace(text=_SCHEMA_REGISTRO_ESENTE, extraction_engine="pdfplumber")
    calls = []

    def recover(source, sql_record, text):
        calls.append((source.oggetto_id, sql_record.current_version_id))
        return importo_contributo_unificato(text, metadata={"fascicolo": case_record}, origine="nativo")

    kwargs = {"documenti_contributo": ("source",), "recupero_contributo": recover}
    before = registry.letture("tenant", "case")[0]
    recupera_da_testi_sql(case_record, registry, "tenant", repository, **kwargs)
    facts = registry.fatti("tenant", "case", verifiche=None)
    assert next(f for f in facts if f.campo == "udienza").verifica == "corretta"
    after = registry.letture("tenant", "case")[0]
    assert (after.letto_il, after.versione_lettore, after.durata_ms) == (before.letto_il, before.versione_lettore, before.durata_ms)
    assert recupera_da_testi_sql(case_record, registry, "tenant", repository, **kwargs)["controllati"] == 0
    if decision:
        assert calls == []
        assert next(f for f in facts if f.campo == "esenzione_cu_dichiarata").prove == old.prove
    else:
        assert calls == [("source", "v1")]
        result = contributo_verificato(facts)
        assert result["status"] == "non_previsto" and not result["pagato"]
        assert result["documento_id"] == "source"
        assert len([f for f in facts if f.campo == "esenzione_cu_dichiarata"]) == 1


@pytest.mark.parametrize('manual', [False, True])
def test_autocertificazione_ocr_non_si_perde_se_la_fonte_non_ha_testo_nativo(tmp_path, manual):
    from pct.archivio_letture.estrazione_importi import importo_contributo_unificato
    from pct.archivio_letture.presidio_economico import contributo_verificato
    from tests.test_react_fascicoli_sentenze_economiche import _AUTOCERTIFICAZIONE_SINTETICA

    registry, repository, _, _ = setup_source(tmp_path, engine='pdf-inspector:controlled')
    obj = registry.oggetti('tenant', 'case')[0]
    old = Fatto(categoria='evento', campo='esenzione_cu_dichiarata', valore='dichiarazione_presente',
                origine='ocr', verifica='corretta' if manual else 'plausibile')
    registry.registra_fatti('tenant', 'case', obj, 'documenti', [old,
        Fatto(categoria='data', campo='udienza', valore='2026-03-12', verifica='corretta')])
    case_record = SimpleNamespace(id='case', nome_cliente='Bianchi Anna', numero_rg='900', anno_rg='2026',
                                 tribunale='Tribunale di Vicenza',
                                 documenti=[SimpleNamespace(id='source', hash_sha256='a' * 64)])
    repository.get_extracted_text = lambda *_: SimpleNamespace(
        text=_AUTOCERTIFICAZIONE_SINTETICA, extraction_engine='pdf-inspector:controlled')
    called = []

    def recover(source, record, text):
        called.append(text)
        return importo_contributo_unificato(text, metadata={'fascicolo': case_record,
            'documento_id': source.oggetto_id, 'document_hash_sha256': source.sha256}, origine='ocr')

    kwargs = {'documenti_contributo': ('source',), 'recupero_contributo': recover,
              'riscontro_nativo': lambda *_: ''}
    recupera_da_testi_sql(case_record, registry, 'tenant', repository, **kwargs)
    assert recupera_da_testi_sql(case_record, registry, 'tenant', repository, **kwargs)['controllati'] == 0
    facts = registry.fatti('tenant', 'case', verifiche=None)
    assert next(f for f in facts if f.campo == 'udienza').verifica == 'corretta'
    assert len([f for f in facts if f.campo == 'esenzione_cu_dichiarata']) == 1
    if manual:
        assert not called
        assert next(f for f in facts if f.campo == 'esenzione_cu_dichiarata').verifica == 'corretta'
    else:
        assert called == [_AUTOCERTIFICAZIONE_SINTETICA]
        result = contributo_verificato(facts)
        assert result['status'] == 'non_previsto' and not result['richiedeConferma']
        assert not any(f.campo == 'giudice' for f in facts)
        assert next(f for f in facts if f.campo == 'esenzione_cu_dichiarata').origine == 'ocr'
