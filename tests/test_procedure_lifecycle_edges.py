from __future__ import annotations

import json
import runpy
import sys
from unittest.mock import patch

import pytest

from pct.digital_signature_workflow import (
    assert_required_signatures_verified,
    create_signature_requirement,
    is_signature_required,
    record_signature_result,
    verify_signature_event_consistency,
)
from pct.evidence_vault import add_evidence_document, link_evidence_to_deposit, link_evidence_to_notification
from pct.legal_coverage_sqlite_repository import CoverageSqliteConfig
from pct.notification_workflow import (
    RealNotificationConnector,
    acquire_notification_proof,
    attach_relata,
    create_notification_event,
    mark_notification_ready,
    mark_proof_deposit_required,
    mark_proof_deposited,
    proof_deposit_required,
    record_notification_delivery,
    record_notification_sent,
)
from pct.post_acceptance_obligations import complete_obligation, evaluate_post_acceptance_obligations
from pct.procedure_coverage_ext import compute_extended_coverage, enqueue_extended_gaps, list_procedure_inventory_coverage
from pct.procedure_inventory_importer import (
    compute_import_hash,
    iter_xsd_objects,
    load_catalog,
    main as importer_main,
)
from pct.procedure_knowledge_pipeline import (
    ValidationReport,
    _card_validation,
    add_source_evidence,
    approve_knowledge_card,
    publish_knowledge_card,
    save_knowledge_card,
    submit_knowledge_card_for_review,
    validate_source_evidence,
)
from pct.procedure_lifecycle import LifecycleTemplateReport, transition_workflow
from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository, json_loads, row_to_dict
from pct.procedure_source_research import (
    SourceReference,
    SourceResearchReport,
    _dedupe_references,
    build_source_plan_for_xsd,
    consult_sources_for_xsd,
    seed_multi_source_evidence_for_inventory,
)
from pct.procedure_xsd_mapper import infer_mapping_for_xsd, map_all_xsd_objects
from pct.telematic_deposit_workflow import (
    RealDepositConnector,
    add_deposit_receipt,
    create_deposit_package,
    mark_deposit_sent,
    validate_package_ready,
)
from tests.procedure_pipeline_support import make_repo, seed_inventory, write_catalog


def test_importer_edge_paths_main_e_report(tmp_path, capsys):
    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        load_catalog(str(missing))

    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_catalog(str(invalid))

    catalog = {
        "areas": [
            {
                "area": "a",
                "label": "Area",
                "items": [
                    {"codice": "", "label": "Vuoto"},
                    {"codice": "010", "label": "Famiglia", "children": [{"codice": "010001", "label": "Uno"}]},
                    {"codice": "010", "label": "Duplicato", "children": [{"codice": "010001", "label": "Uno bis"}]},
                ],
            }
        ]
    }
    rows = iter_xsd_objects(catalog)
    assert [row["xsd_code"] for row in rows] == ["010001"]
    first_hash = compute_import_hash({"xsd_code": "1", "import_hash": "old"})
    assert first_hash == compute_import_hash({"xsd_code": "1", "import_hash": "new"})

    catalog_path = write_catalog(tmp_path)
    report_path = tmp_path / "main-report.json"
    rc = importer_main(["--db", str(tmp_path / "main.db"), "--catalog", str(catalog_path), "--report", str(report_path), "--dry-run"])
    assert rc == 0
    assert json.loads(report_path.read_text(encoding="utf-8"))["dry_run"] is True
    assert "total_catalog_objects" in capsys.readouterr().out

    runpy_report_path = tmp_path / "runpy-report.json"
    old_argv = sys.argv
    sys.argv = [
        "pct.procedure_inventory_importer",
        "--db",
        str(tmp_path / "runpy.db"),
        "--catalog",
        str(catalog_path),
        "--report",
        str(runpy_report_path),
        "--dry-run",
    ]
    try:
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("pct.procedure_inventory_importer", run_name="__main__")
    finally:
        sys.argv = old_argv
    assert exc.value.code == 0
    assert json.loads(runpy_report_path.read_text(encoding="utf-8"))["dry_run"] is True


def test_mapper_placeholder_e_report_edges(tmp_path):
    class DummyProc:
        code = "PROC_MATCH"
        channel_code = "PCT"
        registry_code = "REG"
        workflow_code = "WF"
        name = "ingiunzione societaria sfratto cautelare possessoria"

    for code, expected in {
        "010123": "PROC_PCT_INGIUNZIONE_ANTE_CAUSAM_NEEDS_REVIEW",
        "050123": "PROC_PCT_INGIUNZIONE_SOCIETARIA_FINANZIARIA_NEEDS_REVIEW",
        "030123": "PROC_PCT_CONVALIDA_SFRATTO_NEEDS_REVIEW",
        "011123": "PROC_PCT_CAUTELARE_NEEDS_REVIEW",
        "020123": "PROC_PCT_POSSESSORIA_NEEDS_REVIEW",
    }.items():
        assert infer_mapping_for_xsd({"xsd_code": code, "xsd_label": "test"}, procedure_registry={"dummy": object()}).procedure_code == expected

    for code in ("010123", "050123", "030123", "011123", "020123"):
        assert infer_mapping_for_xsd({"xsd_code": code, "xsd_label": "test"}, procedure_registry={"p": DummyProc()}).procedure_code == "PROC_MATCH"

    unknown_empty = infer_mapping_for_xsd({"xsd_code": "", "xsd_label": ""})
    assert unknown_empty.confidence_score == 10

    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)
    assert map_all_xsd_objects(repo, dry_run=True).to_dict()["total_xsd_objects"] == 6


def test_source_research_copre_famiglie_specialistiche():
    samples = {
        "016001": "famiglia_mantenimento",
        "103001": "navigazione_review",
        "104001": "corte_appello_trap_review",
        "108001": "giudice_pace",
        "110001": "persone_famiglia_minori",
        "120001": "successioni_volontaria_giurisdizione",
        "130001": "diritti_reali_trascrizioni",
        "130002": "diritti_reali_possesso_trascrizioni",
        "201001": "revocazione",
        "210001": "lavoro_ingiunzione",
        "211001": "lavoro_cautelare",
        "220001": "lavoro_previdenza",
        "999001": "pct_generico",
    }
    for code, family in samples.items():
        label = "possesso" if code == "130002" else "test"
        plan = build_source_plan_for_xsd(
            {"xsd_code": code, "xsd_label": label, "xsd_family_label": label, "xsd_area_label": "area"}
        )
        assert plan.family == family
        assert plan.to_dict()["review_required"] is True
    ref = SourceReference("a", "official", "https://x", "Titolo", "kind", "Principio", "official_public")
    assert _dedupe_references([ref, ref]) == [ref]
    assert SourceResearchReport(True, 1, 2, 3, 4).to_dict()["cards_created"] == 3


def test_knowledge_pipeline_edge_validation_e_blocchi(tmp_path):
    repo = make_repo(tmp_path)
    invalid = validate_source_evidence(
        {
            "procedure_code": "",
            "source_type": "sconosciuta",
            "copyright_policy": "vietata",
            "evidence_kind": "",
        }
    )
    assert {"source_type non ammesso.", "copyright_policy non ammessa."} <= set(invalid.errors)
    assert ValidationReport(True, [], [], []).to_dict()["valid"] is True
    assert validate_source_evidence({"procedure_code": "P", "source_type": "licensed_database", "source_title": "Banca", "evidence_kind": "massima"}).valid is True

    professional_warning = validate_source_evidence(
        {
            "procedure_code": "PROC",
            "source_type": "professional",
            "source_title": "Commento",
            "evidence_kind": "commento",
            "extracted_principle": "Principio.",
            "copyright_policy": "official_public",
        }
    )
    assert professional_warning.warnings

    quote_error = validate_source_evidence(
        {
            "procedure_code": "PROC",
            "source_type": "local_practice",
            "source_title": "Prassi",
            "evidence_kind": "prassi",
            "original_quote_short": "x" * 501,
        }
    )
    assert quote_error.errors

    internal_warning = validate_source_evidence(
        {
            "procedure_code": "PROC",
            "source_type": "internal",
            "source_title": "Checklist",
            "evidence_kind": "checklist",
            "copyright_policy": "summary_only",
        }
    )
    assert internal_warning.warnings
    official_error = validate_source_evidence(
        {
            "procedure_code": "PROC",
            "source_type": "official",
            "source_title": "Fonte",
            "evidence_kind": "norma",
            "copyright_policy": "summary_only",
        }
    )
    assert "Per fonti ufficiali source_url è obbligatorio." in official_error.errors
    assert official_error.warnings

    internal_id = add_source_evidence(
        repo,
        procedure_code="PROC",
        source_type="internal",
        source_title="Mario RSSMRA80A01H501U",
        evidence_kind="checklist",
    )
    assert "privacy_review_required" in repo.list_source_evidence("PROC")[0]["notes"]
    assert internal_id
    assert _card_validation([], {})["blocking_errors"]

    with pytest.raises(ValueError):
        submit_knowledge_card_for_review(repo, 999)
    with pytest.raises(ValueError):
        approve_knowledge_card(repo, 999, "Avv.")
    with pytest.raises(ValueError):
        publish_knowledge_card(repo, 999)

    source_id = add_source_evidence(
        repo,
        procedure_code="PROC",
        xsd_code="010001",
        source_type="official",
        source_url="https://pst.giustizia.it",
        source_title="PST",
        evidence_kind="catalogo",
        review_status="needs_review",
    )
    card_id = save_knowledge_card(
        repo,
        procedure_code="PROC",
        xsd_code="010001",
        title="Scheda in review",
        sources=[{**repo.list_source_evidence("PROC", "010001")[0], "id": source_id}],
    )
    with pytest.raises(ValueError):
        publish_knowledge_card(repo, card_id)
    repo.update_knowledge_card_status(card_id, status="approved", reviewer="Avv.")
    with pytest.raises(ValueError):
        publish_knowledge_card(repo, card_id)

    no_official_card = repo.create_knowledge_card(
        {
            "procedure_code": "NOOFF",
            "title": "No official",
            "status": "approved",
            "validation_report_json": {"blocking_errors": []},
        }
    )
    with pytest.raises(ValueError):
        publish_knowledge_card(repo, no_official_card)
    blocking_card = repo.create_knowledge_card(
        {
            "procedure_code": "BLOCK",
            "title": "Blocking",
            "status": "approved",
            "validation_report_json": {"blocking_errors": ["errore"]},
        }
    )
    with pytest.raises(ValueError):
        publish_knowledge_card(repo, blocking_card)


def test_lifecycle_repository_e_state_machine_edges(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)
    assert LifecycleTemplateReport(True, 1, 1, 1).to_dict()["xsd_total"] == 1

    with pytest.raises(ValueError):
        transition_workflow(repo, 999, "CHIUSA")

    template = repo.list_lifecycle_templates(xsd_code="010001")[0]
    instance_id = repo.create_workflow_instance(
        {
            "fascicolo_id": "FEDGE",
            "template_id": int(template["id"]),
            "procedure_code": "PROC",
            "xsd_code": "010001",
            "current_step_code": "PRATICA_APERTA",
        }
    )
    with pytest.raises(ValueError):
        transition_workflow(repo, instance_id, "NON_AMMESSO")
    with pytest.raises(ValueError):
        transition_workflow(repo, instance_id, "FIRMATO")

    unknown_id = repo.create_workflow_instance(
        {
            "fascicolo_id": "FUNK",
            "template_id": int(template["id"]),
            "procedure_code": "PROC",
            "xsd_code": "999001",
            "current_step_code": "FIRMA_RICHIESTA",
        }
    )
    transition_workflow(repo, unknown_id, "FIRMATO")

    office_id = repo.create_workflow_instance(
        {
            "fascicolo_id": "FOFF",
            "template_id": int(template["id"]),
            "procedure_code": "PROC",
            "xsd_code": "010001",
            "current_step_code": "ESITO_CONTROLLI_RICEVUTO",
        }
    )
    repo.create_deposit_package(
        {
            "fascicolo_id": "FOFF",
            "procedure_code": "PROC",
            "xsd_code": "010001",
            "channel_code": "PCT_CIVILE",
            "deposit_status": "OFFICE_ACCEPTED",
        }
    )
    transition_workflow(repo, office_id, "DEPOSITO_ACCETTATO")

    receipt_id = repo.create_workflow_instance(
        {
            "fascicolo_id": "FREC",
            "template_id": int(template["id"]),
            "procedure_code": "PROC",
            "xsd_code": "010001",
            "current_step_code": "ESITO_CONTROLLI_RICEVUTO",
        }
    )
    package_id = repo.create_deposit_package(
        {"fascicolo_id": "FREC", "procedure_code": "PROC", "xsd_code": "010001", "channel_code": "PCT_CIVILE"}
    )
    repo.add_deposit_receipt({"deposit_package_id": package_id, "receipt_type": "ACCETTAZIONE_DEPOSITO", "receipt_status": "RECEIVED"})
    transition_workflow(repo, receipt_id, "DEPOSITO_ACCETTATO")
    from pct.procedure_lifecycle import generate_lifecycle_templates_for_catalog

    assert generate_lifecycle_templates_for_catalog(repo, dry_run=False).templates_generated == 0
    reject_id = repo.create_workflow_instance(
        {
            "fascicolo_id": "FNOACC",
            "template_id": int(template["id"]),
            "procedure_code": "PROC",
            "xsd_code": "010001",
            "current_step_code": "ESITO_CONTROLLI_RICEVUTO",
        }
    )
    reject_package_id = repo.create_deposit_package(
        {"fascicolo_id": "FNOACC", "procedure_code": "PROC", "xsd_code": "010001", "channel_code": "PCT_CIVILE"}
    )
    repo.add_deposit_receipt({"deposit_package_id": reject_package_id, "receipt_type": "PEC_ACCETTAZIONE", "receipt_status": "RECEIVED"})
    with pytest.raises(ValueError):
        transition_workflow(repo, reject_id, "DEPOSITO_ACCETTATO")


def test_signature_deposit_notification_evidence_edges(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)
    assert is_signature_required("PROC", "010001", "allegato") is True

    event_id = create_signature_requirement(
        repo,
        fascicolo_id="FSIG",
        document_id="DOC",
        procedure_code="PROC",
        xsd_code="010001",
        document_role="atto_principale",
    )
    with pytest.raises(ValueError):
        record_signature_result(repo, event_id, signer_detected="Avv.", hash_after="h", token="no")
    assert verify_signature_event_consistency({"required": 1})["status"] == "ERROR"
    assert verify_signature_event_consistency({"required": 1, "signer_detected": "Avv.", "signature_invalid": True})["status"] == "INVALID"
    assert verify_signature_event_consistency({"required": 1, "signer_detected": "Avv."})["warnings"]
    with pytest.raises(ValueError):
        assert_required_signatures_verified(repo, "FSIG", document_ids=("MISSING",))
    with pytest.raises(ValueError):
        assert_required_signatures_verified(repo, "FSIG", document_ids=("DOC",))
    assert_required_signatures_verified(repo, "NO_REQUIRED")

    with pytest.raises(NotImplementedError):
        RealDepositConnector().send({})
    with pytest.raises(ValueError):
        validate_package_ready(repo, 999)
    with pytest.raises(ValueError):
        mark_deposit_sent(repo, 999)
    with pytest.raises(ValueError):
        create_deposit_package(repo, fascicolo_id="FEMPTY", procedure_code="PROC", xsd_code="")
    assert repo.get_xsd_object("010001")
    direct_missing = repo.create_deposit_package({"fascicolo_id": "FRAW", "procedure_code": "PROC", "channel_code": "PCT_CIVILE"})
    assert "xsd_code mancante." in validate_package_ready(repo, direct_missing)["errors"]
    direct_inactive = repo.create_deposit_package({"fascicolo_id": "FRAW2", "procedure_code": "PROC", "xsd_code": "999999", "channel_code": "PCT_CIVILE"})
    assert "xsd_code non attivo nel catalogo ministeriale." in validate_package_ready(repo, direct_inactive)["errors"]
    package_id = create_deposit_package(repo, fascicolo_id="FDEP", procedure_code="PROC", xsd_code="010001")
    not_ready = validate_package_ready(repo, package_id)
    assert {"DatiAtto.xml non associato.", "Busta o pacchetto deposito non associato."} <= set(not_ready["errors"])
    with pytest.raises(ValueError):
        mark_deposit_sent(repo, package_id)
    with pytest.raises(ValueError):
        add_deposit_receipt(repo, package_id, "NON_AMMESSA")
    add_deposit_receipt(repo, package_id, "ERRORE_TECNICO", notes="errore")
    assert repo.get_deposit_package(package_id)["deposit_status"] == "TECHNICAL_ERROR"

    with pytest.raises(NotImplementedError):
        RealNotificationConnector().send({})
    with pytest.raises(ValueError):
        mark_notification_ready(repo, 999)
    notification_id = create_notification_event(repo, fascicolo_id="FNOT", notification_type="PEC", act_document_id="atto")
    with pytest.raises(ValueError):
        record_notification_sent(repo, 999)
    with pytest.raises(ValueError):
        record_notification_delivery(repo, 999)
    with pytest.raises(ValueError):
        acquire_notification_proof(repo, 999, 1)
    with pytest.raises(ValueError):
        mark_notification_ready(repo, notification_id)
    with pytest.raises(ValueError):
        record_notification_sent(repo, notification_id)
    with pytest.raises(ValueError):
        record_notification_delivery(repo, notification_id)
    with pytest.raises(ValueError):
        acquire_notification_proof(repo, notification_id, 999)
    assert proof_deposit_required(repo, notification_id) is False
    with pytest.raises(ValueError):
        attach_relata(repo, notification_id, "")
    with pytest.raises(ValueError):
        mark_proof_deposit_required(repo, 999)
    with pytest.raises(ValueError):
        mark_proof_deposit_required(repo, notification_id)
    with pytest.raises(ValueError):
        mark_proof_deposited(repo, 999, 1)
    with pytest.raises(ValueError):
        mark_proof_deposited(repo, notification_id, 1)
    repo.update_notification_event(notification_id, {"status": "PROOF_ACQUIRED"})
    mark_proof_deposit_required(repo, notification_id)
    assert repo.get_notification_event(notification_id)["status"] == "PROOF_ACQUIRED"
    with pytest.raises(ValueError):
        mark_proof_deposited(repo, notification_id, 999)

    evidence_id = add_evidence_document(repo, fascicolo_id="FNOT", evidence_type="GENERICA", document_id="ev", storage_path="missing.txt", hash="already")
    add_evidence_document(repo, fascicolo_id="FNOT", evidence_type="GENERICA", document_id="missing-path", storage_path="missing.txt")
    with pytest.raises(ValueError):
        link_evidence_to_notification(repo, notification_id=999, evidence_id=evidence_id)
    with pytest.raises(ValueError):
        link_evidence_to_deposit(repo, package_id=999, evidence_id=evidence_id)
    with pytest.raises(ValueError):
        link_evidence_to_deposit(repo, package_id=package_id, evidence_id=999)


def test_repository_helper_filters_e_noop_updates(tmp_path):
    repo = make_repo(tmp_path)
    assert json_loads("", []) == []
    assert json_loads("", {}) == {}
    assert json_loads("", "fallback") == "fallback"
    assert json_loads("not-json", []) == []
    assert json_loads("not-json", {}) == {}
    assert json_loads("not-json", "fallback") == "fallback"
    assert json_loads({"a": 1}, {}) == {"a": 1}
    assert row_to_dict(None) is None
    from pct.procedure_lifecycle_repository import sanitize_audit_payload

    assert sanitize_audit_payload(("a@example.test",), "email") == ["[email-masked]"]
    with pytest.raises(RuntimeError):
        with ProcedureLifecycleRepository(CoverageSqliteConfig("")).connect():
            pass
    raw_repo = ProcedureLifecycleRepository(CoverageSqliteConfig(str(tmp_path / "raw.db")))
    with raw_repo.connect() as conn:
        raw_repo._ensure_tenant_columns(conn)
        conn.execute("CREATE TABLE legal_ministerial_xsd_objects (id INTEGER PRIMARY KEY)")
        raw_repo._ensure_tenant_columns(conn)
        assert "tenant_id" in {row["name"] for row in conn.execute("PRAGMA table_info(legal_ministerial_xsd_objects)").fetchall()}

    seed_inventory(repo, tmp_path)
    mapping = repo.list_xsd_mappings("010001")[0]
    with patch.object(ProcedureLifecycleRepository, "ensure_extended_schema", lambda self: None), patch.object(
        ProcedureLifecycleRepository,
        "_fetch_one",
        side_effect=[mapping, mapping],
    ):
        repo.upsert_xsd_mapping(mapping)
    assert repo.list_audit_log()
    assert isinstance(repo.list_audit_log(entity_id=mapping["id"]), list)
    assert repo.list_xsd_mappings(procedure_code=mapping["procedure_code"])
    assert repo.get_knowledge_card(999) is None
    assert repo.list_knowledge_cards(procedure_code="none") == []
    assert repo.list_lifecycle_templates(procedure_code=mapping["procedure_code"])
    assert repo.list_signature_events("none", "doc") == []

    sig_id = repo.add_signature_event(
        {"fascicolo_id": "F", "document_id": "D", "required": 0, "verification_status": "NOT_REQUIRED"}
    )
    repo.update_signature_event(sig_id, {"not_allowed": "x"})
    package_id = repo.create_deposit_package(
        {"fascicolo_id": "F", "procedure_code": "PROC", "xsd_code": "010001", "channel_code": "PCT_CIVILE"}
    )
    repo.update_deposit_package(package_id, {"not_allowed": "x"})
    obligation_id = repo.add_obligation(
        {"fascicolo_id": "F", "procedure_code": "PROC", "xsd_code": "010001", "trigger_event": "T", "obligation_type": "NOTIFICA"}
    )
    repo.update_obligation(obligation_id, {"not_allowed": "x"})
    notification_id = repo.create_notification_event(
        {"fascicolo_id": "F", "notification_type": "PEC", "act_document_id": "atto"}
    )
    repo.update_notification_event(notification_id, {"not_allowed": "x"})
    assert repo.list_evidence_documents("F", source_event_id=999) == []


def test_post_acceptance_coverage_e_source_runtime_edges(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)
    assert evaluate_post_acceptance_obligations(
        repo,
        fascicolo_id="F050",
        procedure_code="PROC",
        xsd_code="050001",
        trigger_event="ACC",
        proof_deposit_configured=False,
    )
    assert evaluate_post_acceptance_obligations(repo, fascicolo_id="FCAU", procedure_code="PROC", xsd_code="011001", trigger_event="ACC")
    assert evaluate_post_acceptance_obligations(repo, fascicolo_id="FPOS", procedure_code="PROC", xsd_code="020001", trigger_event="ACC")
    no_evidence = repo.add_obligation(
        {"fascicolo_id": "FNONE", "procedure_code": "PROC", "xsd_code": "999001", "trigger_event": "T", "obligation_type": "ALTRO"}
    )
    complete_obligation(repo, no_evidence)
    with pytest.raises(ValueError):
        complete_obligation(repo, 999)

    coverage_050 = compute_extended_coverage(repo, "PROC", "050001")
    assert coverage_050["risk_level"] == "HIGH"
    coverage_017 = compute_extended_coverage(repo, "PROC", "017001")
    assert coverage_017["risk_level"] == "HIGH"
    gaps = enqueue_extended_gaps(repo, {"xsd_code": "010001", "procedure_code": "PROC", "missing_blocks": ["unknown"]})
    assert gaps == []

    no_mapping_dir = tmp_path / "no-mapping"
    no_mapping_dir.mkdir()
    repo2 = make_repo(no_mapping_dir)
    catalog_path = write_catalog(no_mapping_dir)
    from pct.procedure_inventory_importer import import_xsd_objects

    import_xsd_objects(repo2, str(catalog_path), dry_run=False)
    assert any(row["procedure_code"] == "" for row in list_procedure_inventory_coverage(repo2))

    with pytest.raises(ValueError):
        consult_sources_for_xsd(repo, "missing")
    assert seed_multi_source_evidence_for_inventory(repo, dry_run=True).xsd_total >= 1
