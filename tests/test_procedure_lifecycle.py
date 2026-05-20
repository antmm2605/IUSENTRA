from __future__ import annotations

import pytest

from pct.digital_signature_workflow import create_signature_requirement, record_signature_result
from pct.evidence_vault import add_evidence_document
from pct.notification_workflow import create_notification_event, mark_notification_ready, record_notification_sent
from pct.procedure_lifecycle import (
    build_lifecycle_steps_for_xsd,
    generate_lifecycle_templates_for_catalog,
    open_workflow_instance,
    transition_workflow,
)
from pct.telematic_deposit_workflow import add_deposit_receipt, create_deposit_package
from tests.procedure_pipeline_support import make_repo, seed_inventory


def _instance(repo, xsd_code="010001"):
    template = repo.list_lifecycle_templates(xsd_code=xsd_code)[0]
    return open_workflow_instance(
        repo,
        fascicolo_id=f"F{xsd_code}",
        template_id=int(template["id"]),
        procedure_code=template["procedure_code"],
        xsd_code=xsd_code,
    )


def _advance_to_signature(repo, instance_id):
    for state in (
        "PROCEDURA_CLASSIFICATA",
        "DOCUMENTI_RICHIESTI",
        "DOCUMENTI_COMPLETI",
        "ATTO_GENERATO",
        "REVISIONE_AVVOCATO",
        "PRONTO_PER_FIRMA",
        "FIRMA_RICHIESTA",
    ):
        transition_workflow(repo, instance_id, state)


def test_lifecycle_template_per_famiglie_e_state_machine_severa(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)
    report = generate_lifecycle_templates_for_catalog(repo, dry_run=True)
    assert report.xsd_total == 6
    assert "PROOF_DEPOSIT" in build_lifecycle_steps_for_xsd("010001")
    assert "NOTIFICATION_DECISION" in build_lifecycle_steps_for_xsd("030001")

    instance_id = _instance(repo)
    _advance_to_signature(repo, instance_id)
    with pytest.raises(ValueError):
        transition_workflow(repo, instance_id, "FIRMATO")

    sig_id = create_signature_requirement(
        repo,
        fascicolo_id="F010001",
        document_id="D1",
        procedure_code="PROC",
        xsd_code="010001",
        document_role="atto_principale",
        signer_expected="Avv. Rossi",
    )
    record_signature_result(repo, sig_id, signer_detected="Avv. Rossi", hash_after="hash")
    transition_workflow(repo, instance_id, "FIRMATO")
    for state in (
        "BUSTA_GENERATA",
        "DEPOSITO_PRONTO",
        "DEPOSITO_INVIATO",
        "PEC_ACCETTAZIONE_RICEVUTA",
        "PEC_CONSEGNA_RICEVUTA",
        "ESITO_CONTROLLI_RICEVUTO",
    ):
        transition_workflow(repo, instance_id, state)
    with pytest.raises(ValueError):
        transition_workflow(repo, instance_id, "DEPOSITO_ACCETTATO")

    package_id = create_deposit_package(
        repo,
        fascicolo_id="F010001",
        procedure_code="PROC",
        xsd_code="010001",
        dati_atto_xml_id="xml",
        envelope_file_id="env",
    )
    add_deposit_receipt(repo, package_id, "ACCETTAZIONE_DEPOSITO")
    transition_workflow(repo, instance_id, "DEPOSITO_ACCETTATO")


def test_lifecycle_blocca_notifica_prova_e_chiusura_con_obblighi(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)
    instance_id = repo.create_workflow_instance(
        {
            "fascicolo_id": "F2",
            "template_id": int(repo.list_lifecycle_templates(xsd_code="010001")[0]["id"]),
            "procedure_code": "PROC",
            "xsd_code": "010001",
            "current_step_code": "NOTIFICA_DA_EFFETTUARE",
            "status": "WAITING_NOTIFICATION",
        }
    )
    with pytest.raises(ValueError):
        transition_workflow(repo, instance_id, "NOTIFICA_EFFETTUATA")
    notification_id = create_notification_event(
        repo,
        fascicolo_id="F2",
        notification_type="PEC",
        act_document_id="atto",
        recipient_name="Mario",
        recipient_address="mario@example.test",
        recipient_address_source="anagrafe",
    )
    mark_notification_ready(repo, notification_id)
    record_notification_sent(repo, notification_id)
    transition_workflow(repo, instance_id, "NOTIFICA_EFFETTUATA")
    with pytest.raises(ValueError):
        transition_workflow(repo, instance_id, "PROVA_NOTIFICA_ACQUISITA")
    add_evidence_document(repo, fascicolo_id="F2", evidence_type="PROOF_OF_DELIVERY", document_id="proof", hash="h")
    transition_workflow(repo, instance_id, "PROVA_NOTIFICA_ACQUISITA")
    transition_workflow(repo, instance_id, "MONITORAGGIO_FASCICOLO")
    repo.add_obligation(
        {
            "fascicolo_id": "F2",
            "procedure_code": "PROC",
            "xsd_code": "010001",
            "trigger_event": "test",
            "obligation_type": "NOTIFICA",
        }
    )
    with pytest.raises(ValueError):
        transition_workflow(repo, instance_id, "CHIUSA")
