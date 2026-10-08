import hashlib
import json
import sqlite3
from types import SimpleNamespace

from pct.fatturazione_sdi_receipts import ingest_sdi_receipt


XML = b'''<s:NotificaScarto xmlns:s="http://www.fatturapa.gov.it/sdi/messaggi/v1.0"><IdentificativoSdI>12345</IdentificativoSdI><NomeFile>IT12345678901_00001.xml.p7m</NomeFile><ListaErrori><Errore><Descrizione>Nome file non valido</Descrizione></Errore></ListaErrori></s:NotificaScarto>'''


def context(tmp_path):
    conn = sqlite3.connect(tmp_path / "studio.db")
    conn.row_factory = sqlite3.Row
    manager = SimpleNamespace(_studio_db=SimpleNamespace(conn=conn), invoices=[], writes=[])
    manager.tutte = lambda: manager.invoices
    manager.aggiorna = lambda identifier, **changes: manager.writes.append((identifier, changes))
    source = {"message_id": "pec-1", "attachment_id": "1", "received_at": "2026-10-08T09:00:00+02:00",
              "href": "/api/v1/ui/email/source/pec-1?name=receipt.xml",
              "provenance": {"verified": True, "method": "agid_ca1_native_root_smime_crl_v1",
                             "receipt_hashes": [hashlib.sha256(XML).hexdigest()], "envelope_sha256": "a" * 64}}
    return manager, conn, source


def invoice(identifier="invoice-1"):
    return SimpleNamespace(id=identifier, sdi_identificativo="", sdi_stato="INVIATA",
        dati_personalizzati={"fatturapa_workflow": {"signed_xml": {"fileName": "IT12345678901_00001.xml.p7m"}}})


def test_unmatched_receipt_is_persistent_and_not_periodically_retried(tmp_path):
    manager, conn, source = context(tmp_path)
    first = ingest_sdi_receipt(manager, XML, tenant_id="tenant-1", source=source)
    second = ingest_sdi_receipt(manager, XML, tenant_id="tenant-1", source=source)
    assert first["persisted"] and first["receipt_id"] == second["receipt_id"]
    row = conn.execute("SELECT * FROM fatturazione_sdi_receipts").fetchone()
    assert row["invoice_id"] == "" and row["verification_state"] == "correlation_required"
    assert row["next_attempt_at"] == ""
    assert json.loads(row["receipt_json"])["errors"] == ["Nome file non valido"]
    assert conn.execute("SELECT COUNT(*) FROM fatturazione_sdi_receipts").fetchone()[0] == 1
    assert manager.writes == []


def test_later_exact_invoice_adopts_existing_evidence_once(tmp_path):
    manager, conn, source = context(tmp_path)
    before = ingest_sdi_receipt(manager, XML, tenant_id="tenant-1", source=source)
    manager.invoices = [invoice()]
    after = ingest_sdi_receipt(manager, XML, tenant_id="tenant-1", source=source)
    assert after["applied"] and after["receipt_id"] == before["receipt_id"]
    row = conn.execute("SELECT * FROM fatturazione_sdi_receipts").fetchone()
    assert row["invoice_id"] == "invoice-1" and row["verification_state"] == "verified"
    assert conn.execute("SELECT COUNT(*) FROM fatturazione_sdi_receipts").fetchone()[0] == 1
    assert manager.writes[-1][1]["sdi_stato"] == "SCARTATA"
    assert "stato" not in manager.writes[-1][1]


def test_previously_assigned_receipt_cannot_move_to_another_invoice(tmp_path):
    manager, conn, source = context(tmp_path)
    manager.invoices = [invoice()]
    assert ingest_sdi_receipt(manager, XML, tenant_id="tenant-1", source=source)["applied"]
    manager.writes.clear()
    manager.invoices = [invoice("different-invoice")]
    result = ingest_sdi_receipt(manager, XML, tenant_id="tenant-1", source=source)
    assert result["code"] == "receipt_correlation_conflict" and not result["applied"]
    assert conn.execute("SELECT invoice_id FROM fatturazione_sdi_receipts").fetchone()[0] == "invoice-1"
    assert manager.writes == []


def test_identical_evidence_is_isolated_by_tenant(tmp_path):
    manager, conn, source = context(tmp_path)
    ingest_sdi_receipt(manager, XML, tenant_id="tenant-1", source=source)
    ingest_sdi_receipt(manager, XML, tenant_id="tenant-2", source=source)
    assert conn.execute("SELECT COUNT(*) FROM fatturazione_sdi_receipts").fetchone()[0] == 2
    assert manager.writes == []


def test_fiscal_xml_has_no_hearing_or_procedural_deadline():
    from email.message import EmailMessage
    from pct.pec_pipeline import parse_pec_message, build_validation_report, PecAuditRepository
    message = EmailMessage()
    message["From"] = "sdi01@pec.fatturapa.it"
    message["To"] = "studio@example.test"
    message["Subject"] = "Notifica di scarto 12345"
    message.set_content("Ricevuta fiscale, nessuna udienza.")
    message.add_attachment(XML, maintype="application", subtype="xml", filename="receipt.xml")
    parsed = parse_pec_message(message.as_bytes())
    report = build_validation_report(parsed, [])
    assert report["event_type"] == "ricevuta_sdi" and report["severity"] == "danger"
    assert report["remote_hearing"] == {}
    assert report["deadline_proposal"]["auto_create"] is False
    assert "legal_deadline_proposal" not in report["deadline_proposal"]
    assert PecAuditRepository._notification_receipt_profile(parsed, report)["skipped"]
    assert any(item["code"] == "sdi_provenance_pending" for item in report["issues"])


def test_receipt_subject_without_official_xml_does_not_attest_sdi():
    from email.message import EmailMessage
    from pct.pec_pipeline import parse_pec_message, build_validation_report
    message = EmailMessage()
    message["From"] = "sender@example.test"
    message["Subject"] = "Notifica di scarto 12345"
    message.set_content("Ricevuta SdI dichiarata nel solo testo.")
    parsed = parse_pec_message(message.as_bytes())
    assert not parsed["sdi_receipts"]
    assert build_validation_report(parsed, [])["event_type"] != "ricevuta_sdi"
