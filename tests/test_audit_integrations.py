from __future__ import annotations

from flask import Flask, g

import pytest

from audit.exceptions import AuditValidationError
from audit.integrations import emit_act_generated, emit_deposit_attempt, emit_deposit_outcome, emit_incident, emit_pec_sent
from audit.hashing import sha256_bytes

from tests.audit_test_utils import make_service


class _Tenant:
    slug = "tenant-a"


class _User:
    id = "user-1"
    nome_completo = "Avv. Rossi"


def _app(service):
    app = Flask(__name__)
    app.config.update(AUDIT_ENABLED=True, AUDIT_ENV="development")
    app.extensions["legal_audit_service"] = service
    return app


def test_domain_helpers_emit_expected_kinds(tmp_path) -> None:
    service, _public = make_service()
    app = _app(service)
    pdf = tmp_path / "atto.pdf"
    eml = tmp_path / "pec.eml"
    pdf.write_bytes(b"pdf")
    eml.write_bytes(b"eml")
    with app.test_request_context("/"):
        g.tenant = _Tenant()
        g.utente_corrente = _User()
        emit_act_generated(
            fascicolo_id="FASC-1",
            atto_type="comparsa",
            template_id="tpl",
            template_version="1",
            editor_version="2.221.0",
            output_format="pdf",
            file_path=pdf,
            storage_ref="dms://atto",
            idempotency_key="int-act",
        )
        emit_pec_sent(
            fascicolo_id="FASC-1",
            message_id="m1",
            sender_ref="casella",
            recipients_hashes=[sha256_bytes(b"dest")],
            subject_hash=sha256_bytes(b"subject"),
            provider="pec",
            sent_at="2026-05-13T10:00:00Z",
            eml_path=eml,
            storage_ref="pec://m1",
            idempotency_key="int-pec",
        )
        emit_deposit_outcome(
            fascicolo_id="FASC-1",
            accepted=False,
            portal="PCT",
            office="Tribunale",
            response_hash=sha256_bytes(b"esito"),
            error_code="E1",
            error_message_hash=sha256_bytes(b"errore"),
            idempotency_key="int-dep",
        )
        emit_incident(
            fascicolo_id="FASC-1",
            incident_id="inc-1",
            related_event_id="event-x",
            reason_hash=sha256_bytes(b"mismatch"),
            idempotency_key="int-inc",
        )
    kinds = {row["kind"] for row in service.repository.list_events(tenant_id="tenant-a", fascicolo_id="FASC-1")}
    assert kinds == {"ACT_GENERATED", "PEC_SENT", "DEPOSIT_FAILED", "INCIDENT_OPENED"}


def test_domain_helpers_fail_closed_without_tenant_context(tmp_path) -> None:
    service, _public = make_service()
    app = _app(service)
    pdf = tmp_path / "atto.pdf"
    pdf.write_bytes(b"pdf")
    with app.test_request_context("/"):
        with pytest.raises(AuditValidationError):
            emit_act_generated(
                fascicolo_id="FASC-1",
                atto_type="comparsa",
                template_id="tpl",
                template_version="1",
                editor_version="2.221.0",
                output_format="pdf",
                file_path=pdf,
                storage_ref="dms://atto",
                idempotency_key="int-no-tenant",
            )


def test_deposit_attempt_records_real_package_once(tmp_path) -> None:
    service, _public = make_service()
    app = _app(service)
    atto_enc = tmp_path / "Atto.enc"
    atto_msg = tmp_path / "Atto.msg"
    atto_enc.write_bytes(b"encrypted-package")
    atto_msg.write_bytes(b"ministerial-message")

    with app.test_request_context("/"):
        g.tenant = _Tenant()
        g.utente_corrente = _User()
        first = emit_deposit_attempt(
            fascicolo_id="FASC-DEP",
            busta_path=atto_enc,
            atto_msg_path=atto_msg,
            storage_ref_prefix="depositi://fascicoli/FASC-DEP/DEP-1",
            operation="simulazione_senza_invio",
            deposit_id="DEP-1",
        )
        second = emit_deposit_attempt(
            fascicolo_id="FASC-DEP",
            busta_path=atto_enc,
            atto_msg_path=atto_msg,
            storage_ref_prefix="depositi://fascicoli/FASC-DEP/DEP-1",
            operation="simulazione_senza_invio",
            deposit_id="DEP-1",
        )

    rows = service.repository.list_events(tenant_id="tenant-a", fascicolo_id="FASC-DEP")
    assert len(rows) == 1
    assert rows[0]["kind"] == "DEPOSIT_ATTEMPT"
    assert second.event_id == first.event_id
    envelope = service.load_envelope(rows[0])
    event = envelope["signed_event"]
    assert event["payload"]["operation"] == "simulazione_senza_invio"
    assert event["payload"]["deposit_id"] == "DEP-1"
    assert [item["label"] for item in event["files"]] == ["Atto.enc", "Atto.msg"]
