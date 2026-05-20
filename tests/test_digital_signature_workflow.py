from __future__ import annotations

import pytest

from pct.digital_signature_workflow import (
    create_signature_requirement,
    is_signature_required,
    record_signature_result,
    verify_signature_event_consistency,
)
from tests.procedure_pipeline_support import make_repo


def test_firma_richiesta_non_conserva_credenziali_e_verifica(tmp_path):
    repo = make_repo(tmp_path)
    assert is_signature_required("PROC", "010001", "atto_principale") is True
    assert is_signature_required("PROC", None, "bozza") is False

    with pytest.raises(ValueError):
        create_signature_requirement(
            repo,
            fascicolo_id="F1",
            document_id="D1",
            procedure_code="PROC",
            xsd_code="010001",
            document_role="atto_principale",
            pin="1234",
        )

    event_id = create_signature_requirement(
        repo,
        fascicolo_id="F1",
        document_id="D1",
        procedure_code="PROC",
        xsd_code="010001",
        document_role="atto_principale",
        signer_expected="Avv. Rossi",
    )
    assert repo.list_signature_events("F1")[0]["verification_status"] == "REQUIRED_PENDING"

    mismatch = record_signature_result(repo, event_id, signer_detected="Avv. Bianchi", hash_after="abc")
    assert mismatch["status"] == "MISMATCH_SIGNER"

    event_id_2 = create_signature_requirement(
        repo,
        fascicolo_id="F1",
        document_id="D2",
        procedure_code="PROC",
        xsd_code="010001",
        document_role="atto_principale",
        signer_expected="Avv. Rossi",
    )
    verified = record_signature_result(repo, event_id_2, signer_detected="Avv. Rossi", hash_after="def")
    assert verified["status"] == "VERIFIED"

    not_required = verify_signature_event_consistency({"required": 0})
    assert not_required["status"] == "NOT_REQUIRED"
