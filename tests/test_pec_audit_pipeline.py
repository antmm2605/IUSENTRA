from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from flask import Flask, g

from lex.operational_knowledge.permission_guard import resolve_query_context
from lex.operational_knowledge.tools import OperationalKnowledgeTools
from pct.email_client import EmailRicevuta, GestioneEmailRicevute, StatoEmail
from pct.pec_pipeline import (
    PecAuditRepository,
    detect_pec_legal_context,
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
        "FASCICOLI_DB": tmp_path / "fascicoli" / "fascicoli.json",
        "FASCICOLI_DOCS": tmp_path / "fascicoli" / "documenti",
        "SCADENZIARIO_DB": tmp_path / "scadenziario" / "scadenze.json",
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

    @app.before_request
    def _inject_user():
        g.utente_corrente = _User()
        g.tenant_slug = "default"
        g.data_paths = {"PEC_AUDIT_DB": str(paths["PEC_AUDIT_DB"])}

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

    schedule = client.post(f"/api/pec/messages/{notice_id}/schedula-scadenza")
    assert schedule.status_code == 200
    schedule_payload = schedule.get_json()
    assert schedule_payload["ok"] is True
    assert schedule_payload["due_date"]
    from pct.scadenziario import GestioneScadenziario

    scadenze = GestioneScadenziario(str(paths["SCADENZIARIO_DB"])).tutte(solo_aperte=False)
    marker = f"PEC_AUDIT:{notice_id}"
    notice_deadlines = [item for item in scadenze if marker in item.note]
    assert len(notice_deadlines) == 1
    assert notice_deadlines[0].deadline_profile_code == "PEC_AUTO_PRESIDIO"
    assert notice_deadlines[0].operational_due_at.startswith(schedule_payload["due_date"][:10])
    assert notice_deadlines[0].legal_due_at == ""

    schedule_again = client.post(f"/api/pec/messages/{notice_id}/schedula-scadenza")
    assert schedule_again.status_code == 200
    assert schedule_again.get_json()["already_exists"] is True

    digest = client.get("/api/pec/digest")
    assert digest.status_code == 200
    assert digest.get_json()["data"]["new_messages"] == 5


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
