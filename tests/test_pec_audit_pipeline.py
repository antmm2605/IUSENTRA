from __future__ import annotations

import sqlite3
import zipfile
from io import BytesIO
import os
import time
from email import policy
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from flask import Flask, g

from lex.operational_knowledge.permission_guard import resolve_query_context
from lex.operational_knowledge.tools import OperationalKnowledgeTools
from pct.email_client import EmailRicevuta, GestioneEmailRicevute, StatoEmail
from pct.pec_pipeline import (
    AttachmentPayload,
    PecAuditRepository,
    build_pec_procedural_profile,
    build_validation_report,
    detect_pec_legal_context,
    extract_text_with_coverage,
    ingest_synthetic_dataset,
    synthetic_pec_messages,
)


class _User:
    id = "user-pec"
    username = "avvocato"
    tenant_slug = "default"

    @property
    def permessi_effettivi(self):
        return ["ai.usa", "messaggi.leggi", "fascicoli.leggi", "telematico.leggi"]

    def ha_permesso(self, permission: str) -> bool:
        return permission in self.permessi_effettivi


def _zip_pdf_with_link(link: str) -> bytes:
    from reportlab.pdfgen import canvas

    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer)
    pdf.drawString(72, 760, "Udienza audiovisiva ore 09:15")
    pdf.drawString(72, 740, f"Collegamento: {link}")
    pdf.save()
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("13744017s.pdf", pdf_buffer.getvalue())
    return zip_buffer.getvalue()


def test_pec_pipeline_ingests_synthetic_dataset_with_audit_grade_storage(tmp_path):
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")

    result = ingest_synthetic_dataset(repo)

    assert result["workers"]["failed"] == 0
    assert result["digest"]["new_messages"] == 5
    rows = repo.list_messages(limit=20)
    assert len(rows) == 5
    assert all(row["mime_sha256"] for row in rows)
    assert all(repo.get_message_detail(row["id"])["parsed_version"]["parsed_sha256"] for row in rows)
    with sqlite3.connect(repo.db_path) as conn:
        conn.row_factory = sqlite3.Row
        audit_rows = conn.execute("SELECT prev_hash, entry_hash FROM pec_audit_log ORDER BY rowid").fetchall()
    assert audit_rows
    assert audit_rows[0]["prev_hash"] == ""
    assert all(row["entry_hash"] for row in audit_rows)


def test_pec_pipeline_deduplicates_by_message_id_and_mime_hash(tmp_path):
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    _label, raw_mime = synthetic_pec_messages()[0]

    first = repo.ingest_mime(raw_mime, account_email="studio@example.test", folder="INBOX", imap_uid="1")
    duplicate = repo.ingest_mime(raw_mime, account_email="studio@example.test", folder="INBOX", imap_uid="2")

    assert first["duplicate"] is False
    assert duplicate["duplicate"] is True
    assert repo.list_messages(limit=10)[0]["id"] == first["id"]


def test_pec_audit_header_summaries_support_lightweight_mode(tmp_path, monkeypatch):
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    ingest_synthetic_dataset(repo)
    header = str(repo.list_messages(limit=1)[0]["message_id_header"])

    def _unexpected_detail_lookup(*_args, **_kwargs):
        raise AssertionError("La lista PEC massiva non deve caricare dettagli completi.")

    monkeypatch.setattr(repo, "latest_parsed_row", _unexpected_detail_lookup)
    monkeypatch.setattr(repo, "latest_report", _unexpected_detail_lookup)
    monkeypatch.setattr(repo, "latest_link", _unexpected_detail_lookup)
    monkeypatch.setattr(repo, "attachment_rows", _unexpected_detail_lookup)

    summaries = repo.summaries_by_header_message_ids([header, header], include_details=False)

    assert list(summaries) == [header]
    assert summaries[header]["message_id_header"] == header
    assert summaries[header]["received_at"]
    assert summaries[header]["validation_report"] == {}
    assert summaries[header]["fascicolo_link"] == {}
    assert summaries[header]["attachments"] == []


def test_semantic_context_matrix_covers_main_legal_pec_domains():
    samples = {
        "notifica_l53": "Notificazione ai sensi della legge n. 53 del 1994 con relata di notifica e attestazione di conformita",
        "pat_notifica_o_deposito": "Processo amministrativo telematico PAT SIGA TAR notifica del ricorso DPCM 40/2016",
        "ptt_notifica_o_deposito": "Processo tributario telematico PTT SIGIT Corte di giustizia tributaria decreto 163/2013",
        "penale_snt": "Sistema Notificazioni Telematiche SNT Procura della Repubblica art. 151 c.p.p.",
        "pct_deposito": "Deposito telematico busta telematica DatiAtto.xml esito controlli automatici RG 1234/2026",
        "notifica_giudice_pace": "GIUDICE DI PACE Notificazione ai sensi del D.L. 179/2012",
    }

    for expected, text in samples.items():
        context = detect_pec_legal_context(text)
        assert context["event_hint"] == expected
        assert context["normative_references"]
        assert context["agent_questions"]
        assert context["agent_policy"]["stance"] == "presidio_non_bloccante"
        assert any("scadenze operative" in item for item in context["agent_policy"]["must_do"])

    assert detect_pec_legal_context("Comunicazione compatibile con documenti tardivi generici") == {}


def test_pec_procedural_profile_reads_inline_comunicazione_xml_audiovisiva():
    xml_text = """
    <Comunicazione>
      <NumeroRuolo>1263/2026/LAV</NumeroRuolo>
      <Oggetto>FISSAZIONE UDIENZA DI DISCUSSIONE</Oggetto>
      <Contenuto><![CDATA[
      -- Comunicazione di cancelleria Sez/Coll.: LA Tipo procedimento: Diritto del Lavoro
      Numero di Ruolo generale: 1263/2026 Giudice: ANGELI ISABELLA
      Ricorr. principale: MARRA VALENTINA Resist. principale: MINISTERO DELL'ISTRUZIONE E DEL MERITO
      Oggetto: FISSAZIONE UDIENZA DI DISCUSSIONE
      Descrizione: FISSATA UDIENZA DI DISCUSSIONE IL 29/10/2026 09:15 con strumenti audiovisivi
      Note: Notificato alla PEC / in cancelleria il 26/05/2026 15:09
      Registrato da BOMBARDIERI GIULIA -- ]]></Contenuto>
      <CodiceUG>0170290098</CodiceUG>
      <CodiceFiscaleDestinatario>MNTGPP94L01G791A</CodiceFiscaleDestinatario>
    </Comunicazione>
    """

    profile = build_pec_procedural_profile(
        subject="FISSAZIONE UDIENZA DI DISCUSSIONE",
        body_text="",
        xml_texts={"Comunicazione.xml": xml_text},
        rg_candidates=[],
        sent_date="2026-05-26T15:09:00+02:00",
        delivery_date="2026-05-26T15:09:00+02:00",
        event_type="comunicazione_cancelleria",
        semantic_context={"office_hint": "Tribunale"},
    )

    assert profile["numero_rg"] == "1263/2026"
    assert profile["giudice"] == "ANGELI ISABELLA"
    assert profile["attore_principale"] == "MARRA VALENTINA"
    assert profile["convenuto_principale"] == "MINISTERO DELL'ISTRUZIONE E DEL MERITO"
    assert profile["udienza_data_ora"] == "29/10/2026 09:15"
    assert profile["modalita_udienza"] == "strumenti audiovisivi"
    assert any("PDF" in item for item in profile["checklist_avvocato"])
    assert any("strumenti audiovisivi" in item for item in profile["domande_lex"])


def test_remote_hearing_report_uses_pdf_ocr_link_and_persists_lawyer_actions():
    profile = build_pec_procedural_profile(
        subject="Fissazione udienza di discussione",
        body_text="Descrizione: FISSATA UDIENZA DI DISCUSSIONE IL 29/10/2026 09:15 con strumenti audiovisivi",
        xml_texts={},
        rg_candidates=["1263/2026"],
        event_type="comunicazione_cancelleria",
        semantic_context={"event_hint": "comunicazione_cancelleria"},
    )
    parsed = {
        "headers": {"subject": "Fissazione udienza di discussione"},
        "body": {"text": "Udienza con strumenti audiovisivi. Il link è nell'allegato PDF."},
        "fields": {},
        "semantic_context": {"event_hint": "comunicazione_cancelleria", "agent_questions": [], "recommended_actions": []},
        "procedural_profile": profile,
    }
    attachments = [
        {
            "filename": "13744017s.pdf.zip",
            "content_type": "application/zip",
            "classification": "atto",
            "ocr_text": "Istruzioni udienza audiovisiva ore 09:15. Collegamento: https://teams.microsoft.com/l/meetup-join/abc?context=%7B%22Tid%22%3A%22123%22%7D&anon=true",
            "ocr_coverage": 0.91,
            "signature_status": "non_applicabile",
        }
    ]

    report = build_validation_report(parsed, attachments)
    remote = report["procedural_profile"]["remote_hearing"]

    assert remote["detected"] is True
    assert remote["mode"] == "audiovisiva"
    expected_link = "https://teams.microsoft.com/l/meetup-join/abc?context=%7B%22Tid%22%3A%22123%22%7D&anon=true"
    assert remote["links"][0]["url"] == expected_link
    assert remote["links"][0]["raw_url"] == expected_link
    assert remote["links"][0]["exact_match"] is True
    assert remote["links"][0]["integrity"] == "exact"
    assert remote["links"][0]["source"] == "13744017s.pdf.zip"
    assert any(issue["code"] == "remote_hearing_link_detected" for issue in report["issues"])
    assert any("agenda" in item.lower() and "link" in item.lower() for item in report["recommended_actions"])
    assert any("link dell'udienza audiovisiva" in item for item in report["agent_questions"])


def test_remote_hearing_report_warns_when_pdf_link_is_not_yet_ocr_read():
    profile = build_pec_procedural_profile(
        subject="Fissazione udienza",
        body_text="FISSATA UDIENZA DI DISCUSSIONE IL 29/10/2026 09:15 con strumenti audiovisivi",
        xml_texts={},
        rg_candidates=["1263/2026"],
        event_type="comunicazione_cancelleria",
        semantic_context={"event_hint": "comunicazione_cancelleria"},
    )
    parsed = {
        "headers": {"subject": "Fissazione udienza"},
        "body": {"text": "Il link per la connessione è nell'allegato PDF."},
        "fields": {},
        "semantic_context": {"event_hint": "comunicazione_cancelleria", "agent_questions": [], "recommended_actions": []},
        "procedural_profile": profile,
    }
    attachments = [
        {
            "filename": "13744017s.pdf.zip",
            "content_type": "application/zip",
            "classification": "atto",
            "ocr_text": "",
            "ocr_coverage": 0,
            "signature_status": "non_applicabile",
        }
    ]

    report = build_validation_report(parsed, attachments)
    remote = report["procedural_profile"]["remote_hearing"]

    assert remote["pdf_required"] is True
    assert "13744017s.pdf.zip" in remote["pdf_pending"]
    assert any(issue["code"] == "remote_hearing_pdf_link_required" for issue in report["issues"])
    assert any("OCR" in item or "PDF" in item for item in report["recommended_actions"])


def test_extract_text_with_coverage_reads_pdf_inside_zip():
    exact_link = "https://teams.microsoft.com/l/meetup-join/abc?context=%7B%22Tid%22%3A%22123%22%7D&anon=true"

    text, coverage = extract_text_with_coverage(
        AttachmentPayload(
            index=1,
            filename="13744017s.pdf.zip",
            content_type="application/zip",
            data=_zip_pdf_with_link(exact_link),
        )
    )

    assert coverage > 0
    assert "13744017s.pdf" in text
    assert "Udienza audiovisiva" in text
    assert exact_link in text


def test_pec_repository_persists_remote_hearing_pdf_zip_ocr_and_exact_link(tmp_path):
    exact_link = "https://teams.microsoft.com/l/meetup-join/abc?context=%7B%22Tid%22%3A%22123%22%7D&anon=true"
    xml_text = """
    <Comunicazione>
      <NumeroRuolo>1263/2026/LAV</NumeroRuolo>
      <Oggetto>FISSAZIONE UDIENZA DI DISCUSSIONE</Oggetto>
      <Contenuto><![CDATA[
      -- Comunicazione di cancelleria Sez/Coll.: LA Tipo procedimento: Diritto del Lavoro
      Numero di Ruolo generale: 1263/2026 Giudice: ANGELI ISABELLA
      Ricorr. principale: MARRA VALENTINA Resist. principale: MINISTERO DELL'ISTRUZIONE E DEL MERITO
      Oggetto: FISSAZIONE UDIENZA DI DISCUSSIONE
      Descrizione: FISSATA UDIENZA DI DISCUSSIONE IL 29/10/2026 09:15 con strumenti audiovisivi
      Note: Notificato alla PEC / in cancelleria il 26/05/2026 15:09
      Registrato da BOMBARDIERI GIULIA -- ]]></Contenuto>
      <CodiceUG>0170290098</CodiceUG>
      <CodiceFiscaleDestinatario>MNTGPP94L01G791A</CodiceFiscaleDestinatario>
    </Comunicazione>
    """
    msg = EmailMessage()
    msg["Subject"] = "FISSAZIONE UDIENZA DI DISCUSSIONE"
    msg["From"] = "Cancelleria <cancelleria@pec.example.test>"
    msg["To"] = "studio@example.test"
    msg["Date"] = "Tue, 26 May 2026 15:09:00 +0200"
    msg["Message-ID"] = "<udienza-audiovisiva-1263@example.test>"
    msg.set_content("Comunicazione di cancelleria: udienza con strumenti audiovisivi. Il link è nel PDF allegato.")
    msg.add_attachment(xml_text.encode("utf-8"), maintype="application", subtype="xml", filename="Comunicazione.xml")
    msg.add_attachment(_zip_pdf_with_link(exact_link), maintype="application", subtype="zip", filename="13744017s.pdf.zip")
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")

    ingest = repo.ingest_mime(msg.as_bytes(policy=policy.SMTP), account_email="studio@example.test", folder="INBOX", imap_uid="uid-1263")
    worker = repo.run_pending_jobs(limit=30, actor="pytest")
    detail = repo.get_message_detail(ingest["id"])
    report = detail["validation_report"]
    remote = report["procedural_profile"]["remote_hearing"]

    assert worker["failed"] == 0
    assert detail["message"]["status"] in {"validated", "link_candidates", "linked"}
    assert remote["links"][0]["url"] == exact_link
    assert remote["links"][0]["raw_url"] == exact_link
    assert remote["links"][0]["exact_match"] is True
    assert remote["links"][0]["source"] == "13744017s.pdf.zip"
    parsed_link = urlsplit(remote["links"][0]["url"])
    assert parsed_link.scheme == "https"
    assert parsed_link.netloc == "teams.microsoft.com"
    assert any(
        item["filename"] == "13744017s.pdf.zip" and "meetup-join" in item["ocr_text"]
        for item in detail["attachments"]
    )


def test_giudice_di_pace_notice_generates_non_blocking_validation_and_agent_questions(tmp_path):
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    ingest_synthetic_dataset(repo)

    notice = next(row for row in repo.list_messages(limit=20) if "GIUDICE DI PACE" in row["metadata"]["headers"]["subject"])
    report = notice["validation_report"]

    assert report["event_type"] == "notifica_giudice_pace"
    assert report["blocking"] is False
    assert any(issue["code"] == "legal_notice_review_required" for issue in report["issues"])
    assert any("D.L. 179/2012" in ref["label"] for ref in report["normative_references"])
    assert any("termini" in question.lower() for question in report["agent_questions"])
    assert report["deadline_proposal"]["auto_create"] is True
    assert report["deadline_proposal"]["source_event_type"] == "notifica_giudice_pace"


def test_pct_deposit_lifecycle_explains_expected_pec_sequence(tmp_path):
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    ingest_synthetic_dataset(repo)

    deposit = next(row for row in repo.list_messages(limit=20) if "Deposito telematico RG 1234/2026" in row["metadata"]["headers"]["subject"])
    report = deposit["validation_report"]
    lifecycle = report["deposit_lifecycle"]

    assert report["event_type"] == "pct_deposito"
    assert lifecycle["current_stage"]["id"] == "consegna_pec"
    assert [item["id"] for item in lifecycle["expected_sequence"]] == [
        "accettazione_pec",
        "consegna_pec",
        "esito_controlli_deposito",
        "accettazione_o_rifiuto_deposito",
    ]
    assert any(issue["code"] == "pct_deposit_followup_expected" for issue in report["issues"])
    assert any("quattro PEC" in question for question in report["agent_questions"])
    assert "stato intermedio" in lifecycle["communication"]
    assert report["deadline_proposal"]["auto_create"] is True
    assert report["deadline_proposal"]["source_event_type"] == "pct_deposito"


def test_lex_operational_tools_expose_pec_audit_control_context(tmp_path):
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    ingest_synthetic_dataset(repo)
    context = resolve_query_context(user=_User(), studio=SimpleNamespace(slug="default"))
    tools = OperationalKnowledgeTools(repositories={"pec_audit": repo})

    result = tools.list_pec_audit_messages(context, query="GIUDICE", limit=5)

    assert result.ok
    assert result.data
    record = result.data[0]
    assert record["event_type"] == "notifica_giudice_pace"
    assert record["agent_questions"]
    assert record["normative_references"]
    assert any(source.source_id == "pec_audit" for source in result.sources)


def test_pec_api_demo_digest_mime_and_quick_action(tmp_path, monkeypatch):
    from web.blueprints.pec_pipeline_api import pec_pipeline_api

    paths = {
        "EMAIL_CASELLA_DB": tmp_path / "email" / "casella.json",
        "PEC_AUDIT_DB": tmp_path / "email" / "pec_audit.sqlite",
        "CLIENTI_DB": tmp_path / "clienti" / "anagrafica.json",
        "FASCICOLI_DB": tmp_path / "fascicoli" / "fascicoli.json",
        "FASCICOLI_DOCS": tmp_path / "fascicoli" / "documenti",
        "SCADENZIARIO_DB": tmp_path / "scadenziario" / "scadenze.json",
        "AGENDA_DB": tmp_path / "agenda" / "appuntamenti.json",
        "NOTIFICATIONS_DB": tmp_path / "notifications" / "notifications.db",
    }

    def fake_tenant_data_path(key, default, *aliases, require_tenant=True):
        value = paths.get(key)
        if not value:
            raise AssertionError(f"Path tenant non atteso: {key}")
        value.parent.mkdir(parents=True, exist_ok=True)
        return str(value)

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(pec_pipeline_api, url_prefix="/api/pec")
    monkeypatch.setattr("web.blueprints.pec_pipeline_api.tenant_data_path", fake_tenant_data_path)

    from pct.clienti import GestioneClienti, TipoCliente
    from pct.fascicoli import GestioneFascicoli, TipoFascicolo

    cliente = GestioneClienti(str(paths["CLIENTI_DB"])).nuovo(TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Rossi")
    fascicoli = GestioneFascicoli(str(paths["FASCICOLI_DB"]), documents_dir=str(paths["FASCICOLI_DOCS"]))
    fascicolo = fascicoli.nuovo("Ricorso Rossi", TipoFascicolo.CIVILE, id_cliente=cliente.id, nome_cliente=cliente.nome_completo)

    @app.before_request
    def _inject_user():
        g.utente_corrente = _User()
        g.tenant_slug = "default"
        g.data_paths = {
            "PEC_AUDIT_DB": str(paths["PEC_AUDIT_DB"]),
            "NOTIFICATIONS_DB": str(paths["NOTIFICATIONS_DB"]),
        }

    client = app.test_client()
    demo = client.post("/api/pec/demo/ingest")
    assert demo.status_code == 200
    assert demo.get_json()["data"]["digest"]["new_messages"] == 5

    listing = client.get("/api/pec/messages")
    assert listing.status_code == 200
    rows = listing.get_json()["data"]
    assert len(rows) == 5
    notice_id = next(row["id"] for row in rows if row["validation_report"]["event_type"] == "notifica_giudice_pace")

    mime = client.get(f"/api/pec/messages/{notice_id}/mime")
    assert mime.status_code == 200
    assert mime.headers["X-IUSENTRA-MIME-SHA256"]
    assert b"GIUDICE DI PACE" in mime.data

    request_missing = client.post(f"/api/pec/messages/{notice_id}/richiedi-allegato-mancante")
    assert request_missing.status_code == 200
    assert request_missing.get_json()["ok"] is True
    from pct.scadenziario import GestioneScadenziario
    from pct.agenda import Agenda, TipoAppuntamento

    past_schedule = client.post(f"/api/pec/messages/{notice_id}/schedula-scadenza", json={"data_scadenza": "2000-01-15"})
    assert past_schedule.status_code == 409
    past_payload = past_schedule.get_json()
    assert past_payload["expired"] is True
    assert past_payload["message"] == "Termine già superato: non riportato in scadenziario o agenda."
    assert GestioneScadenziario(str(paths["SCADENZIARIO_DB"])).tutte(solo_aperte=False) == []

    schedule = client.post(f"/api/pec/messages/{notice_id}/schedula-scadenza", json={"data_scadenza": "2030-01-15"})
    assert schedule.status_code == 200
    schedule_payload = schedule.get_json()
    assert schedule_payload["ok"] is True
    assert schedule_payload["due_date"]
    assert schedule_payload["agenda"]["ok"] is True
    assert schedule_payload["agenda"]["agenda_id"]
    assert schedule_payload["notification"]["created"] is True
    assert schedule_payload["notification"]["pushConfigured"] is False

    scadenze = GestioneScadenziario(str(paths["SCADENZIARIO_DB"])).tutte(solo_aperte=False)
    marker = f"PEC_AUDIT:{notice_id}"
    notice_deadlines = [item for item in scadenze if marker in item.note]
    assert len(notice_deadlines) == 1
    assert notice_deadlines[0].id_appuntamento == schedule_payload["agenda"]["agenda_id"]
    assert notice_deadlines[0].deadline_profile_code == "PEC_AUTO_PRESIDIO"
    assert notice_deadlines[0].operational_due_at.startswith("2030-01-15")
    assert notice_deadlines[0].legal_due_at == ""
    agenda_items = Agenda(str(paths["AGENDA_DB"])).tutti()
    assert len(agenda_items) == 1
    assert agenda_items[0].tipo == TipoAppuntamento.SCADENZA
    assert agenda_items[0].external_uid == f"PEC_AUDIT:{notice_id}:deadline"
    assert agenda_items[0].external_provider == "pec_audit"
    with sqlite3.connect(paths["NOTIFICATIONS_DB"]) as conn:
        row = conn.execute(
            "SELECT title, href, source_type, source_id FROM notifications WHERE dedupe_key=?",
            (f"PEC_AUDIT:{notice_id}:deadline",),
        ).fetchone()
    assert row is not None
    assert row[0] == "Scadenza PEC registrata"
    assert row[1] == "/scadenziario?vista=pec"
    assert row[2] == "pec_deadline"
    assert row[3] == notice_id

    schedule_again = client.post(f"/api/pec/messages/{notice_id}/schedula-scadenza", json={"data_scadenza": "2030-01-15"})
    assert schedule_again.status_code == 200
    assert schedule_again.get_json()["already_exists"] is True
    assert schedule_again.get_json()["notification"]["created"] is False
    assert len(Agenda(str(paths["AGENDA_DB"])).tutti()) == 1

    prepare_save = client.post(
        f"/api/pec/messages/{notice_id}/salva-fascicolo",
        json={"prepara": True, "nome": "Mario", "cognome": "Rossi"},
    )
    assert prepare_save.status_code == 200
    prepare_payload = prepare_save.get_json()
    assert prepare_payload["requires_confirmation"] is True
    assert prepare_payload["candidates"][0]["id"] == fascicolo.id

    direct_fascicolo = fascicoli.nuovo("Ricorso Bianchi", TipoFascicolo.CIVILE, id_cliente="", nome_cliente="Bianchi Luisa")
    prepare_direct = client.post(
        f"/api/pec/messages/{notice_id}/salva-fascicolo",
        json={"prepara": True, "nome": "Luisa Bianchi", "cognome": ""},
    )
    assert prepare_direct.status_code == 200
    direct_payload = prepare_direct.get_json()
    assert direct_payload["requires_confirmation"] is True
    assert direct_payload["candidates"][0]["id"] == direct_fascicolo.id

    confirm_save = client.post(f"/api/pec/messages/{notice_id}/salva-fascicolo", json={"fascicolo_id": fascicolo.id})
    assert confirm_save.status_code == 200
    confirm_payload = confirm_save.get_json()
    assert confirm_payload["ok"] is True
    assert confirm_payload["message"] == "MIME PEC salvato nel fascicolo."

    saved = GestioneFascicoli(str(paths["FASCICOLI_DB"]), documents_dir=str(paths["FASCICOLI_DOCS"])).get(fascicolo.id)
    assert saved is not None
    assert any(doc.msg_id_portale == notice_id and doc.fonte_documento == "PEC_AUDIT_PIPELINE" for doc in saved.documenti)

    digest = client.get("/api/pec/digest")
    assert digest.status_code == 200
    assert digest.get_json()["data"]["new_messages"] == 5


def test_pec_api_usa_tenant_autenticato_per_audit_multi_studio(tmp_path):
    from pct.tenant import GestioneTenant
    from tests.test_web_bootstrap import _cfg_web, _write_studio_config
    from web.app import create_app
    from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg_web(tmp_path), "MULTI_TENANT": True})
    manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio_a = manager.crea("Studio PEC A", "studio-pec-a")
    studio_b = manager.crea("Studio PEC B", "studio-pec-b")
    manager.aggiorna(studio_a.slug, api_key="pec-a-key")
    manager.aggiorna(studio_b.slug, api_key="pec-b-key")
    bootstrap_legacy_tenant_runtime_data(app, tenant_slug=studio_a.slug)
    bootstrap_legacy_tenant_runtime_data(app, tenant_slug=studio_b.slug)

    headers_a = {"X-API-Key": "pec-a-key", "X-Tenant-Slug": studio_a.slug}
    headers_b = {"X-API-Key": "pec-b-key", "X-Tenant-Slug": studio_b.slug}

    with app.test_client() as client:
        ingest_a = client.post("/api/pec/demo/ingest", headers=headers_a)
        ingest_b = client.post("/api/pec/demo/ingest", headers=headers_b)
        listing_a = client.get("/api/pec/messages", headers=headers_a)
        listing_b = client.get("/api/pec/messages", headers=headers_b)

    assert ingest_a.status_code == 200
    assert ingest_b.status_code == 200
    assert listing_a.status_code == 200
    assert listing_b.status_code == 200
    assert len(listing_a.get_json()["data"]) == 5
    assert len(listing_b.get_json()["data"]) == 5

    paths_a = manager.percorsi_dati(studio_a.slug, reconcile_aliases=False)
    paths_b = manager.percorsi_dati(studio_b.slug, reconcile_aliases=False)
    audit_db_a = paths_a.get("PEC_AUDIT_DB") or Path(paths_a["EMAIL_CASELLA_DB"]).parent / "pec_audit.sqlite"
    audit_db_b = paths_b.get("PEC_AUDIT_DB") or Path(paths_b["EMAIL_CASELLA_DB"]).parent / "pec_audit.sqlite"
    for db_path, expected_slug in ((audit_db_a, studio_a.slug), (audit_db_b, studio_b.slug)):
        with sqlite3.connect(db_path) as conn:
            tenant_ids = {row[0] for row in conn.execute("SELECT DISTINCT tenant_id FROM pec_messages")}
        assert tenant_ids == {expected_slug}


def test_pec_api_acquisisce_mime_locale_da_casella_storica(tmp_path, monkeypatch):
    from email.message import EmailMessage

    from pct.email_client import CartellaEmail
    from web.blueprints.pec_pipeline_api import pec_pipeline_api

    paths = {
        "EMAIL_CASELLA_DB": tmp_path / "email" / "casella.json",
        "PEC_AUDIT_DB": tmp_path / "email" / "pec_audit.sqlite",
        "CLIENTI_DB": tmp_path / "clienti" / "anagrafica.json",
        "FASCICOLI_DB": tmp_path / "fascicoli" / "fascicoli.json",
        "FASCICOLI_DOCS": tmp_path / "fascicoli" / "documenti",
        "SCADENZIARIO_DB": tmp_path / "scadenziario" / "scadenze.json",
        "AGENDA_DB": tmp_path / "agenda" / "appuntamenti.json",
        "NOTIFICATIONS_DB": tmp_path / "notifications" / "notifications.db",
    }

    def fake_tenant_data_path(key, default, *aliases, require_tenant=True):
        value = paths.get(key)
        if not value:
            raise AssertionError(f"Path tenant non atteso: {key}")
        value.parent.mkdir(parents=True, exist_ok=True)
        return str(value)

    msg = EmailMessage()
    msg["From"] = "posta-certificata@legalmail.it"
    msg["To"] = "studio@example.pec.it"
    msg["Subject"] = "POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO RG: 98/2026"
    msg["Message-ID"] = "<legacy-pec-98-2026@example.test>"
    msg.set_content("Messaggio di posta certificata. ACCETTAZIONE DEPOSITO TELEMATICO RG: 98/2026.")
    msg.add_attachment(b"<EsitoAtto><Stato>ACCETTATO</Stato></EsitoAtto>", maintype="application", subtype="xml", filename="EsitoAtto.xml")
    msg.add_attachment(b"<daticert><msgid>legacy-pec-98</msgid></daticert>", maintype="application", subtype="xml", filename="daticert.xml")
    raw_mime = msg.as_bytes()

    gestore = GestioneEmailRicevute(str(paths["EMAIL_CASELLA_DB"]))
    eml_info = gestore._salva_eml_originale("MAIL-LEGACY-PEC", raw_mime)
    gestore.aggiungi(
        EmailRicevuta(
            id="MAIL-LEGACY-PEC",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="Per conto di: tribunale.palmi@civile.ptel.giustiziacert.it",
            destinatari="studio@example.pec.it",
            oggetto="POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO RG: 98/2026",
            corpo_testo="Messaggio di posta certificata. ACCETTAZIONE DEPOSITO TELEMATICO RG: 98/2026.",
            allegati=[
                {"nome": "EsitoAtto.xml", "mime": "application/xml", "size": 49},
                {"nome": "daticert.xml", "mime": "application/xml", "size": 48},
            ],
            eml_file=eml_info["eml_file"],
            eml_sha256=eml_info["eml_sha256"],
        )
    )

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(pec_pipeline_api, url_prefix="/api/pec")
    monkeypatch.setattr("web.blueprints.pec_pipeline_api.tenant_data_path", fake_tenant_data_path)

    @app.before_request
    def _inject_user():
        g.utente_corrente = _User()
        g.tenant_slug = "default"
        g.data_paths = {
            "PEC_AUDIT_DB": str(paths["PEC_AUDIT_DB"]),
            "NOTIFICATIONS_DB": str(paths["NOTIFICATIONS_DB"]),
        }

    client = app.test_client()
    single = client.post("/api/pec/email/MAIL-LEGACY-PEC/acquisisci")
    assert single.status_code == 200
    single_payload = single.get_json()
    assert single_payload["ok"] is True
    assert single_payload["pec_message_id"]

    repo = PecAuditRepository(paths["PEC_AUDIT_DB"], tenant_id="default")
    rows = repo.list_messages(limit=20)
    assert len(rows) == 1
    assert rows[0]["validation_report"]["event_type"] == "pct_deposito"

    massivo = client.post("/api/pec/email/acquisisci-locali?limit=20")
    assert massivo.status_code == 200
    massivo_payload = massivo.get_json()
    assert massivo_payload["ok"] is True
    assert massivo_payload["acquired"] == 1
    assert massivo_payload["duplicates"] == 1
    assert massivo_payload["deadline_report"]["created"] + massivo_payload["deadline_report"]["already_exists"] == 1
    assert massivo_payload["deadline_report"]["agenda_linked"] == 1
    assert massivo_payload["has_more"] is False
    assert massivo_payload["status"] == "completed"
    assert massivo_payload["local_acquire"]["items"][0]["email_id"] == "MAIL-LEGACY-PEC"
    assert massivo_payload["workers"]["processed"] == 0
    assert "Presidio PEC completato" in massivo_payload["messaggio"]
    assert "scadenze" in massivo_payload["messaggio"]
    from web.services.react_email_bridge import build_react_email_payload

    react_payload = build_react_email_payload(db_path=str(paths["EMAIL_CASELLA_DB"]), tenant_id="default")
    assert react_payload["summary"]["warnings"] == 0
    assert react_payload["items"][0]["pecPresidiata"] is True
    from pct.scadenziario import GestioneScadenziario
    from pct.agenda import Agenda

    scadenze = GestioneScadenziario(str(paths["SCADENZIARIO_DB"])).tutte(solo_aperte=False)
    assert len(scadenze) == 1
    assert scadenze[0].deadline_profile_code == "PEC_AUTO_PRESIDIO"
    assert scadenze[0].id_appuntamento
    assert len(Agenda(str(paths["AGENDA_DB"])).tutti()) == 1


def test_pec_api_acquisisci_locali_prosegue_a_blocchi_e_azzera_presidio(tmp_path, monkeypatch):
    from pct.email_client import CartellaEmail
    from web.blueprints.pec_pipeline_api import pec_pipeline_api
    from web.services.react_email_bridge import build_react_email_payload

    paths = {
        "EMAIL_CASELLA_DB": tmp_path / "email" / "casella.json",
        "PEC_AUDIT_DB": tmp_path / "email" / "pec_audit.sqlite",
        "CLIENTI_DB": tmp_path / "clienti" / "anagrafica.json",
        "FASCICOLI_DB": tmp_path / "fascicoli" / "fascicoli.json",
        "FASCICOLI_DOCS": tmp_path / "fascicoli" / "documenti",
        "SCADENZIARIO_DB": tmp_path / "scadenziario" / "scadenze.json",
        "AGENDA_DB": tmp_path / "agenda" / "appuntamenti.json",
    }

    def fake_tenant_data_path(key, default, *aliases, require_tenant=True):
        value = paths.get(key)
        if not value:
            raise AssertionError(f"Path tenant non atteso: {key}")
        value.parent.mkdir(parents=True, exist_ok=True)
        return str(value)

    gestore = GestioneEmailRicevute(str(paths["EMAIL_CASELLA_DB"]))
    for index in range(3):
        gestore.aggiungi(
            EmailRicevuta(
                id=f"MAIL-PRESIDIO-{index}",
                cartella=CartellaEmail.INBOX,
                stato=StatoEmail.NON_LETTA,
                mittente="cancelleria@giustiziacert.it",
                destinatari="studio@example.pec.it",
                oggetto=f"POSTA CERTIFICATA: comunicazione cancelleria {index}",
                data=f"2026-06-0{index + 1}T09:00:00",
                corpo_testo="Messaggio di posta certificata con daticert.xml da controllare.",
                allegati=[{"nome": "daticert.xml", "mime": "application/xml", "size": 20}],
                message_id=f"<presidio-{index}@pec.test>",
                stato_pct="WARN_CONTROLLI",
            )
        )

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(pec_pipeline_api, url_prefix="/api/pec")
    monkeypatch.setattr("web.blueprints.pec_pipeline_api.tenant_data_path", fake_tenant_data_path)

    @app.before_request
    def _inject_user():
        g.utente_corrente = _User()
        g.tenant_slug = "default"
        g.data_paths = {"PEC_AUDIT_DB": str(paths["PEC_AUDIT_DB"])}

    client = app.test_client()
    first = client.post("/api/pec/email/acquisisci-locali?limit=20&batch_size=1")
    assert first.status_code == 200
    first_payload = first.get_json()
    assert first_payload["has_more"] is True
    assert first_payload["cursor_index"] < first_payload["total_emails"]
    run_id = first_payload["run_id"]

    payload = first_payload
    for _ in range(5):
        if not payload["has_more"]:
            break
        response = client.post(f"/api/pec/email/acquisisci-locali?limit=20&batch_size=1&run_id={run_id}")
        assert response.status_code == 200
        payload = response.get_json()

    assert payload["has_more"] is False
    assert payload["status"] == "completed"
    assert payload["skipped_missing_mime"] == 1

    repo = PecAuditRepository(paths["PEC_AUDIT_DB"], tenant_id="default")
    report = repo.local_acquire_run_report(run_id)
    assert report["status"] == "completed"
    assert len(report["items"]) == 3
    assert {item["status"] for item in report["items"]} == {"missing_mime"}

    react_payload = build_react_email_payload(db_path=str(paths["EMAIL_CASELLA_DB"]), tenant_id="default")
    assert react_payload["summary"]["warnings"] == 0
    assert all(item["pecPresidiata"] for item in react_payload["items"])


def test_pec_api_presidia_avvisi_warn_storici_senza_lasciare_arretrato(tmp_path, monkeypatch):
    from pct.email_client import CartellaEmail
    from web.blueprints.pec_pipeline_api import pec_pipeline_api
    from web.services.react_email_bridge import build_react_email_payload

    paths = {
        "EMAIL_CASELLA_DB": tmp_path / "email" / "casella.json",
        "PEC_AUDIT_DB": tmp_path / "email" / "pec_audit.sqlite",
        "CLIENTI_DB": tmp_path / "clienti" / "anagrafica.json",
        "FASCICOLI_DB": tmp_path / "fascicoli" / "fascicoli.json",
        "FASCICOLI_DOCS": tmp_path / "fascicoli" / "documenti",
        "SCADENZIARIO_DB": tmp_path / "scadenziario" / "scadenze.json",
        "AGENDA_DB": tmp_path / "agenda" / "appuntamenti.json",
    }

    def fake_tenant_data_path(key, default, *aliases, require_tenant=True):
        value = paths.get(key)
        if not value:
            raise AssertionError(f"Path tenant non atteso: {key}")
        value.parent.mkdir(parents=True, exist_ok=True)
        return str(value)

    gestore = GestioneEmailRicevute(str(paths["EMAIL_CASELLA_DB"]))
    for index in range(3):
        gestore.aggiungi(
            EmailRicevuta(
                id=f"MAIL-WARN-STORICA-{index}",
                cartella=CartellaEmail.INBOX,
                stato=StatoEmail.NON_LETTA,
                mittente="ufficio@example.it",
                destinatari="studio@example.pec.it",
                oggetto=f"Comunicazione da controllare {index}",
                data=f"2026-06-0{index + 1}T09:00:00",
                corpo_testo="Scheda storica importata senza MIME locale disponibile.",
                allegati=[],
                message_id=f"<warn-storica-{index}@pec.test>",
                stato_pct="WARN_CONTROLLI",
            )
        )

    before = build_react_email_payload(db_path=str(paths["EMAIL_CASELLA_DB"]), tenant_id="default")
    assert before["summary"]["warnings"] == 3

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(pec_pipeline_api, url_prefix="/api/pec")
    monkeypatch.setattr("web.blueprints.pec_pipeline_api.tenant_data_path", fake_tenant_data_path)

    @app.before_request
    def _inject_user():
        g.utente_corrente = _User()
        g.tenant_slug = "default"
        g.data_paths = {"PEC_AUDIT_DB": str(paths["PEC_AUDIT_DB"])}

    client = app.test_client()
    payload = client.post("/api/pec/email/acquisisci-locali?limit=20&batch_size=1").get_json()
    run_id = payload["run_id"]
    while payload["has_more"]:
        response = client.post(f"/api/pec/email/acquisisci-locali?limit=20&batch_size=1&run_id={run_id}")
        assert response.status_code == 200
        payload = response.get_json()

    assert payload["status"] == "completed"
    assert payload["local_acquire"]["skipped_missing_mime"] == 3
    assert "non alimentano" in payload["messaggio"]

    after = build_react_email_payload(db_path=str(paths["EMAIL_CASELLA_DB"]), tenant_id="default")
    assert after["summary"]["warnings"] == 0
    assert all(item["pecPresidiata"] for item in after["items"])


def test_pec_api_schedula_duplicato_audit_senza_report_da_mime_locale(tmp_path, monkeypatch):
    from email.message import EmailMessage

    from pct.email_client import CartellaEmail
    from web.blueprints.pec_pipeline_api import pec_pipeline_api

    paths = {
        "EMAIL_CASELLA_DB": tmp_path / "email" / "casella.json",
        "PEC_AUDIT_DB": tmp_path / "email" / "pec_audit.sqlite",
        "CLIENTI_DB": tmp_path / "clienti" / "anagrafica.json",
        "FASCICOLI_DB": tmp_path / "fascicoli" / "fascicoli.json",
        "FASCICOLI_DOCS": tmp_path / "fascicoli" / "documenti",
        "SCADENZIARIO_DB": tmp_path / "scadenziario" / "scadenze.json",
        "AGENDA_DB": tmp_path / "agenda" / "appuntamenti.json",
        "NOTIFICATIONS_DB": tmp_path / "notifications" / "notifications.db",
    }

    def fake_tenant_data_path(key, default, *aliases, require_tenant=True):
        value = paths.get(key)
        if not value:
            raise AssertionError(f"Path tenant non atteso: {key}")
        value.parent.mkdir(parents=True, exist_ok=True)
        return str(value)

    msg = EmailMessage()
    msg["From"] = "posta-certificata@legalmail.it"
    msg["To"] = "studio@example.pec.it"
    msg["Subject"] = "POSTA CERTIFICATA: COMUNICAZIONE 3001/2025/LAV"
    msg["Message-ID"] = "<duplicato-audit-senza-report@example.test>"
    msg["Date"] = "Thu, 01 Jan 2026 12:00:00 +0100"
    msg.set_content(
        "Messaggio di posta certificata. Il messaggio COMUNICAZIONE 3001/2025/LAV "
        "è stato inviato dal Tribunale. UDIENZA DEL 09/07/2030."
    )
    msg.add_attachment(
        (
            b"<Comunicazione><Numero>3001</Numero><Anno>2025</Anno><Materia>LAV</Materia>"
            b"<Contenuto>NRG: 3001/2025 UDIENZA DEL 09/07/2030 PARTI: Rossi</Contenuto>"
            b"</Comunicazione>"
        ),
        maintype="application",
        subtype="xml",
        filename="Comunicazione.xml",
    )
    msg.add_attachment(
        b"<daticert><msgid>duplicato-audit-senza-report</msgid></daticert>",
        maintype="application",
        subtype="xml",
        filename="daticert.xml",
    )
    raw_mime = msg.as_bytes()

    gestore = GestioneEmailRicevute(str(paths["EMAIL_CASELLA_DB"]))
    eml_info = gestore._salva_eml_originale("MAIL-DUPLICATA-SENZA-REPORT", raw_mime)
    gestore.aggiungi(
        EmailRicevuta(
            id="MAIL-DUPLICATA-SENZA-REPORT",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="Per conto di: tribunale.santamariacapuavetere@civile.ptel.giustiziacert.it",
            destinatari="studio@example.pec.it",
            oggetto="POSTA CERTIFICATA: COMUNICAZIONE 3001/2025/LAV",
            corpo_testo="Messaggio di posta certificata. COMUNICAZIONE 3001/2025/LAV.",
            allegati=[
                {"nome": "Comunicazione.xml", "mime": "application/xml", "size": 86},
                {"nome": "daticert.xml", "mime": "application/xml", "size": 63},
            ],
            message_id="<duplicato-audit-senza-report@example.test>",
            eml_file=eml_info["eml_file"],
            eml_sha256=eml_info["eml_sha256"],
        )
    )
    pre_repo = PecAuditRepository(paths["PEC_AUDIT_DB"], tenant_id="default")
    ingest = pre_repo.ingest_mime(
        raw_mime,
        account_email="studio@example.pec.it",
        folder="INBOX",
        imap_uid="legacy:MAIL-DUPLICATA-SENZA-REPORT",
        actor="test",
    )
    assert ingest["duplicate"] is False
    with sqlite3.connect(paths["PEC_AUDIT_DB"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM pec_validation_reports").fetchone()[0] == 0

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(pec_pipeline_api, url_prefix="/api/pec")
    monkeypatch.setattr("web.blueprints.pec_pipeline_api.tenant_data_path", fake_tenant_data_path)

    @app.before_request
    def _inject_user():
        g.utente_corrente = _User()
        g.tenant_slug = "default"
        g.data_paths = {
            "PEC_AUDIT_DB": str(paths["PEC_AUDIT_DB"]),
            "NOTIFICATIONS_DB": str(paths["NOTIFICATIONS_DB"]),
        }

    client = app.test_client()
    massivo = client.post("/api/pec/email/acquisisci-locali?limit=20&worker_limit=0")
    assert massivo.status_code == 200
    payload = massivo.get_json()
    assert payload["ok"] is True
    assert payload["duplicates"] == 1
    assert payload["deadline_report"]["created"] == 1
    assert payload["deadline_report"]["agenda_linked"] == 1

    from pct.scadenziario import GestioneScadenziario
    from pct.agenda import Agenda

    scadenze = GestioneScadenziario(str(paths["SCADENZIARIO_DB"])).tutte(solo_aperte=False)
    assert len(scadenze) == 1
    assert f"PEC_AUDIT:{ingest['id']}" in scadenze[0].note
    assert scadenze[0].data_scadenza == "2030-07-09"
    assert "Udienza da PEC" in scadenze[0].titolo
    assert scadenze[0].id_appuntamento
    assert len(Agenda(str(paths["AGENDA_DB"])).tutti()) == 1
    with sqlite3.connect(paths["NOTIFICATIONS_DB"]) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE source_type='pec_deadline' AND source_id=?",
            (ingest["id"],),
        ).fetchone()[0] == 1


def test_pec_repository_quarantines_stale_sqlite_journal(tmp_path):
    db_path = tmp_path / "pec_audit.sqlite"
    db_path.write_bytes(b"interrupted sqlite data")
    journal_path = tmp_path / "pec_audit.sqlite-journal"
    journal_path.write_bytes(b"x" * (1024 * 1024 + 1))
    old_time = time.time() - 300
    os.utime(db_path, (old_time, old_time))
    os.utime(journal_path, (old_time, old_time))

    repo = PecAuditRepository(db_path)

    assert repo.db_path.exists()
    assert list(tmp_path.glob("pec_audit.sqlite.interrotto-*"))
    assert list(tmp_path.glob("pec_audit.sqlite-journal.interrotto-*"))
    with repo.connect() as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='pec_messages'").fetchone()


def test_email_search_normalizza_plurali_accenti_e_allegati(tmp_path):
    from pct.email_client import CartellaEmail

    gestore = GestioneEmailRicevute(str(tmp_path / "email" / "casella.json"))
    gestore.aggiungi(
        EmailRicevuta(
            id="MAIL-COMUNICAZIONE",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@example.test",
            destinatari="studio@example.pec.it",
            oggetto="Comunicazione di cancelleria",
            corpo_testo="Deposito provvedimento.",
            allegati=[{"nome": "Comunicazione.xml", "mime": "application/xml", "size": 10}],
        )
    )

    assert [item.id for item in gestore.tutte(q="comunicazioni")] == ["MAIL-COMUNICAZIONE"]
    assert [item.id for item in gestore.tutte(q="cancellerìa comunicazioni")] == ["MAIL-COMUNICAZIONE"]


def test_react_email_bridge_lists_audit_only_pec_messages(tmp_path):
    from web.services.react_email_bridge import build_react_email_payload

    email_db = tmp_path / "email" / "casella.json"
    repo = PecAuditRepository(email_db.parent / "pec_audit.sqlite", tenant_id="default")
    ingest_synthetic_dataset(repo)

    payload = build_react_email_payload(db_path=str(email_db), tenant_id="default")

    assert payload["summary"]["total"] == 5
    assert payload["summary"]["filtered"] == 5
    assert payload["summary"]["pst"] == 5
    assert all(item["auditOnly"] for item in payload["items"])
    notice = next(item for item in payload["items"] if item["pecAudit"]["eventType"] == "notifica_giudice_pace")
    assert notice["detailHref"].startswith("/api/pec/messages/")
    assert notice["pecAudit"]["quickActions"]["openMime"].endswith("/mime")
    deposit = next(item for item in payload["items"] if item["pecAudit"]["eventType"] == "pct_deposito")
    assert deposit["pecAudit"]["depositLifecycle"]["current_stage"]["id"] in {"accettazione_pec", "consegna_pec"}


def test_react_email_bridge_exposes_provisional_audit_for_legacy_pec(tmp_path):
    from web.services.react_email_bridge import build_react_email_detail_payload, build_react_email_payload

    email_db = tmp_path / "email" / "casella.json"
    gestore = GestioneEmailRicevute(str(email_db))
    gestore.aggiungi(
        EmailRicevuta(
            id="MAIL-GDP-1",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="Per conto di: gdp.palmi@civile.ptel.giustiziacert.it",
            destinatari="roberto.montagnese@coapalmi.legalmail.it",
            oggetto="POSTA CERTIFICATA: GIUDICE DI PACE Notificazione ai sensi del D.L. 179/2012",
            data="2026-05-14T10:47:11",
            corpo_testo=(
                "Messaggio di posta certificata. GIUDICE DI PACE Notificazione ai sensi del D.L. 179/2012. "
                "L'allegato daticert.xml contiene informazioni di servizio sulla trasmissione."
            ),
            allegati=[
                {"nome": "postacert.eml", "mime": "message/rfc822", "size": 170100},
                {"nome": "daticert.xml", "mime": "application/xml", "size": 928},
                {"nome": "atto.pdf", "mime": "application/pdf", "size": 42000},
            ],
            message_id="FC338A4C.025A7971.25AB1E0C.FABBBFE3.posta-certificata@legalmail.it",
            origine="IMAP",
        )
    )

    payload = build_react_email_payload(db_path=str(email_db), tenant_id="default")
    row = payload["items"][0]
    audit = row["pecAudit"]

    assert payload["summary"]["pst"] == 1
    assert row["isPst"] is True
    assert audit["persisted"] is False
    assert audit["storageLabel"] == "MIME da acquisire automaticamente"
    assert audit["quickActions"]["runAudit"] == "/api/pec/fetch?limit=50"
    assert audit["quickActions"]["openMime"] == ""
    assert audit["eventType"] == "notifica_giudice_pace"
    assert audit["confidence"]["contesto_legale"]["confidence"] >= 0.7
    assert any("Giudice di Pace" in item["label"] or "D.L. 179" in item["label"] for item in audit["normativeReferences"])
    assert any(issue["code"] == "audit_storage_pending" for issue in audit["validationIssues"])

    detail = build_react_email_detail_payload(db_path=str(email_db), id_email="MAIL-GDP-1", tenant_id="default")
    assert detail is not None
    assert detail["pecAudit"]["persisted"] is False
    assert detail["pecAudit"]["quickActions"]["runAudit"] == "/api/pec/fetch?limit=50"


def test_react_email_bridge_provisional_pec_usa_mime_locale_quando_presente(tmp_path):
    from email.message import EmailMessage

    from web.services.react_email_bridge import build_react_email_detail_payload, build_react_email_payload

    email_db = tmp_path / "email" / "casella.json"
    gestore = GestioneEmailRicevute(str(email_db))
    msg = EmailMessage()
    msg["From"] = "posta-certificata@legalmail.it"
    msg["To"] = "studio@example.pec.it"
    msg["Subject"] = "POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO RG: 98/2026"
    msg.set_content("Messaggio di posta certificata. ACCETTAZIONE DEPOSITO TELEMATICO RG: 98/2026.")
    raw_mime = msg.as_bytes()
    eml_info = gestore._salva_eml_originale("MAIL-GDP-EML", raw_mime)
    gestore.aggiungi(
        EmailRicevuta(
            id="MAIL-GDP-EML",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="Per conto di: tribunale.palmi@civile.ptel.giustiziacert.it",
            destinatari="studio@example.pec.it",
            oggetto="POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO RG: 98/2026",
            corpo_testo="Messaggio di posta certificata. ACCETTAZIONE DEPOSITO TELEMATICO RG: 98/2026.",
            allegati=[{"nome": "daticert.xml", "mime": "application/xml", "size": 928}],
            eml_file=eml_info["eml_file"],
            eml_sha256=eml_info["eml_sha256"],
        )
    )

    payload = build_react_email_payload(db_path=str(email_db), tenant_id="default")
    assert payload["actions"]["pecLocalAcquire"] == "/api/pec/email/acquisisci-locali?limit=5000&batch_size=50"
    audit = payload["items"][0]["pecAudit"]
    assert audit["persisted"] is False
    assert audit["storageLabel"] == "MIME pronto da acquisire"
    assert audit["quickActions"]["runAudit"] == "/api/pec/email/MAIL-GDP-EML/acquisisci"

    detail = build_react_email_detail_payload(db_path=str(email_db), id_email="MAIL-GDP-EML", tenant_id="default")
    assert detail is not None
    assert detail["pecAudit"]["quickActions"]["runAudit"] == "/api/pec/email/MAIL-GDP-EML/acquisisci"
