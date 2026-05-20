from __future__ import annotations

import pytest

from pct.digital_signature_workflow import create_signature_requirement, record_signature_result
from pct.telematic_deposit_workflow import (
    DEPOSIT_RECEIPT_TYPES,
    DEPOSIT_STATUSES,
    DepositReceiptType,
    DepositStatus,
    add_deposit_receipt,
    assert_office_acceptance_evidence,
    create_deposit_package,
    mark_deposit_sent,
    update_deposit_status_from_receipts,
    validate_package_ready,
)
from tests.procedure_pipeline_support import make_repo, seed_inventory


def test_deposito_blocca_xsd_inattivo_firme_mancanti_e_accettazione_senza_ricevuta(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)
    assert DepositStatus.OFFICE_ACCEPTED.value in DEPOSIT_STATUSES
    assert DepositReceiptType.ACCETTAZIONE_DEPOSITO.value in DEPOSIT_RECEIPT_TYPES

    with pytest.raises(ValueError):
        create_deposit_package(repo, fascicolo_id="F1", procedure_code="PROC", xsd_code="999999")

    package_id = create_deposit_package(
        repo,
        fascicolo_id="F1",
        procedure_code="PROC",
        xsd_code="010001",
        dati_atto_xml_id="xml1",
        envelope_file_id="env1",
    )
    not_ready = validate_package_ready(repo, package_id)
    assert "Firma digitale richiesta ma non verificata." in not_ready["errors"]

    event_id = create_signature_requirement(
        repo,
        fascicolo_id="F1",
        document_id="D1",
        procedure_code="PROC",
        xsd_code="010001",
        document_role="atto_principale",
        signer_expected="Avv. Rossi",
    )
    record_signature_result(repo, event_id, signer_detected="Avv. Rossi", hash_after="hash")
    assert validate_package_ready(repo, package_id)["ready"] is True
    assert repo.get_deposit_package(package_id)["deposit_status"] == "READY"

    result = mark_deposit_sent(repo, package_id)
    assert result["sent"] is True
    assert repo.get_deposit_package(package_id)["deposit_status"] == "SENT"

    add_deposit_receipt(repo, package_id, "PEC_ACCETTAZIONE")
    assert repo.get_deposit_package(package_id)["deposit_status"] == "PEC_ACCEPTED"
    add_deposit_receipt(repo, package_id, "PEC_CONSEGNA")
    assert repo.get_deposit_package(package_id)["deposit_status"] == "PEC_DELIVERED"
    add_deposit_receipt(repo, package_id, "ESITO_CONTROLLI")
    assert repo.get_deposit_package(package_id)["deposit_status"] == "CONTROLS_RECEIVED"

    package_id_2 = create_deposit_package(
        repo,
        fascicolo_id="F2",
        procedure_code="PROC",
        xsd_code="010001",
        dati_atto_xml_id="xml2",
        envelope_file_id="env2",
    )
    with pytest.raises(ValueError):
        assert_office_acceptance_evidence(repo, package_id_2)

    add_deposit_receipt(repo, package_id, "ACCETTAZIONE_DEPOSITO", document_id="ricevuta")
    assert update_deposit_status_from_receipts(repo, package_id) == "OFFICE_ACCEPTED"
    add_deposit_receipt(repo, package_id, "RIFIUTO_DEPOSITO", notes="rifiuto")
    assert repo.get_deposit_package(package_id)["deposit_status"] == "OFFICE_REJECTED"
