from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g

from lex.operational_knowledge.models import OperationalQueryContext, OperationalRoute
from lex.operational_knowledge.response_composer import OperationalResponseComposer
from lex.operational_knowledge.tools import OperationalKnowledgeTools
from pct.pec_control_tower import PecControlTowerRepository, build_synthetic_pec_eml, classify_legal
from web.blueprints.pec_control_tower_api import pec_control_tower_api


class _User:
    id = "user-test"
    username = "Avvocato Test"
    tenant_slug = "tenant-test"

    def ha_permesso(self, permission: str) -> bool:
        return permission in {"ai.usa", "messaggi.leggi", "fascicoli.leggi"}


def _fascicoli_rows():
    return [
        SimpleNamespace(
            id="FASC-2026-001",
            numero="RG 1234/2026",
            titolo="Rossi c. Comune",
            oggetto="Comunicazione cancelleria RG 1234/2026",
            procedimento="RG 1234/2026",
            nome_cliente="Mario Rossi",
            controparte="Comune",
        )
    ]


def _sample_court_pec() -> bytes:
    return build_synthetic_pec_eml(
        subject="Comunicazione di cancelleria RG 1234/2026 - deposito provvedimento",
        body="Deposito provvedimento nel fascicolo RG 1234/2026. Verificare termini e documenti.",
        sender="cancelleria@giustiziacert.it",
        dt=datetime.now(timezone.utc),
        attachments={"provvedimento.pdf.txt": "Provvedimento di test RG 1234/2026."},
    )


def _sample_pa_pec() -> bytes:
    return build_synthetic_pec_eml(
        subject="Comune di Milano - richiesta documenti protocollo PA entro 10 giorni",
        body="Il Comune di Milano richiede integrazione documentale entro 10 giorni per RG 1234/2026.",
        sender="protocollo@comune.milano.pec.it",
        dt=datetime.now(timezone.utc),
        attachments={"richiesta-pa.pdf.txt": "Richiesta di integrazione documentale con termine espresso."},
    )


def test_control_tower_schema_crea_indici_bounded_per_fonti_pec(tmp_path: Path) -> None:
    db_path = tmp_path / "tower.sqlite"
    PecControlTowerRepository(db_path, tenant_id="tenant-test")

    with sqlite3.connect(str(db_path)) as conn:
        indexes = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='legal_communications'"
            ).fetchall()
        }

    assert "idx_legal_communications_event_received" in indexes
    assert "idx_legal_communications_event_received_prefix" in indexes


def test_pec_control_tower_sentenza_cancelleria_non_diventa_provvedimento_generico():
    legal = classify_legal(
        {
            "sender": "cancelleria@giustiziacert.it",
            "subject": "POSTA CERTIFICATA: COMUNICAZIONE 1394/2026/LAV",
            "search_text": (
                "Tribunale di Palmi. Oggetto: SENTENZA A VERBALE (art. 127-ter c.p.c.) "
                "Descrizione: SENTENZA A VERBALE CON NUMERO 784/2026. "
                "Note: Notificato alla PEC / in cancelleria il 14/07/2026."
            ),
        },
        {"receipt_role": ""},
    )

    assert legal["legal_event_type"] == "sentenza_da_valutare_per_notifica"
    assert legal["label"] == "Sentenza da valutare per la notifica"
    assert "notifica dell'avvocato" in legal["primary_task"]


class _FakeEmailArchive:
    def __init__(self, messages: dict[str, bytes]):
        self._messages = dict(messages)
        self._rows = {
            key: SimpleNamespace(
                id=key,
                cartella="INBOX",
                mittente="posta-certificata@pec.test",
                destinatari="studio@example.pec.it",
                oggetto=f"POSTA CERTIFICATA: {key}",
                corpo_testo="PEC archiviata localmente per backfill Control Tower.",
                allegati=[{"nome": "daticert.xml"}],
                message_id=f"<{key}@pec.test>",
                data="2026-06-06T09:00:00+02:00",
            )
            for key in self._messages
        }

    def _carica(self):
        return self._rows

    def leggi_eml_originale(self, email_obj):
        return self._messages.get(email_obj.id)


def test_pec_control_tower_repository_tracks_event_deadline_task_and_audit(tmp_path):
    repo = PecControlTowerRepository(
        tmp_path / "pec_control_tower.sqlite",
        tenant_id="tenant-test",
        fascicoli_rows=_fascicoli_rows(),
    )

    result = repo.ingest_eml(_sample_court_pec(), account_email="studio@example.pec.it", actor="pytest")
    communication = result["data"]

    assert communication["legal_category"] == "PROVVEDIMENTO_GIUDIZIARIO"
    assert communication["fascicolo_id"] == "FASC-2026-001"
    assert communication["events"]
    assert communication["deadlines"]
    assert communication["tasks"]
    assert communication["events"][0]["expected_documents"]
    assert communication["events"][0]["legal_articles"]
    assert repo.verify_audit_chain()["ok"] is True

    tables = {
        row[0]
        for row in repo._connect().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {
        "legal_communications",
        "pec_receipt_events",
        "legal_deadlines",
        "agenda_events",
        "notification_jobs",
        "notification_recipients",
        "registry_lookups",
        "legal_rule_versions",
        "audit_events",
    }.issubset(tables)


def test_lex_backfills_pec_control_tower_from_local_email_archive(tmp_path):
    repo = PecControlTowerRepository(
        tmp_path / "pec_control_tower.sqlite",
        tenant_id="tenant-test",
        fascicoli_rows=_fascicoli_rows(),
    )
    archive = _FakeEmailArchive({"pa-risposta": _sample_pa_pec()})
    tools = OperationalKnowledgeTools(repositories={"pec_control_tower": repo, "email_pec": archive})
    context = OperationalQueryContext(
        tenant_id="tenant-test",
        user_id="user-test",
        username="Avvocato Test",
        user=_User(),
        permissions={"ai.usa", "messaggi.leggi", "fascicoli.leggi"},
        tenant_context_available=True,
    )

    result = tools.answer_pec_control_question("Quali comunicazioni PA richiedono risposta?", context)

    assert result.ok is True
    payload = result.data[0]
    assert payload["runtime_backfill"]["ingested"] == 1
    assert payload["items"]
    assert payload["items"][0]["legal_category"] == "ATTO_AMMINISTRATIVO_PA"
    assert repo.list_deadlines(limit=10)


def test_pec_control_tower_backfill_keeps_tenants_separated(tmp_path):
    shared_db = tmp_path / "pec_control_tower.sqlite"
    repo_a = PecControlTowerRepository(shared_db, tenant_id="studio-a")
    repo_b = PecControlTowerRepository(shared_db, tenant_id="studio-b")

    report_a = repo_a.backfill_from_email_archive(_FakeEmailArchive({"pa-a": _sample_pa_pec()}), actor="pytest-a")
    report_b = repo_b.backfill_from_email_archive(_FakeEmailArchive({"court-b": _sample_court_pec()}), actor="pytest-b")

    assert report_a["ingested"] == 1
    assert report_b["ingested"] == 1
    rows_a = repo_a.list_communications(limit=10)
    rows_b = repo_b.list_communications(limit=10)
    assert {row["legal_category"] for row in rows_a} == {"ATTO_AMMINISTRATIVO_PA"}
    assert {row["legal_category"] for row in rows_b} == {"PROVVEDIMENTO_GIUDIZIARIO"}
    assert all(row["tenant_id"] == "studio-a" for row in rows_a)
    assert all(row["tenant_id"] == "studio-b" for row in rows_b)


def test_lex_pec_control_tower_risolve_alias_tenant_e_mostra_prova_completa(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    db_path = data_root / "tenants" / "tenant-storage" / "email" / "pec_control_tower.sqlite"
    db_path.parent.mkdir(parents=True)
    repo = PecControlTowerRepository(db_path, tenant_id="tenant-storage")
    created_at = "2026-06-06T12:00:00+02:00"
    with repo._connect() as con:
        for index, role in enumerate(("acceptance", "delivery"), start=1):
            communication_id = f"comm-{role}"
            con.execute(
                """
                INSERT INTO legal_communications
                (id, tenant_id, direction, account_email, folder, message_id_header, original_message_id,
                 subject, sender, recipients_json, received_at, sent_at, mime_sha256, technical_type,
                 legal_category, legal_event_type, confidence, confidence_label, requires_human_confirmation,
                 status, fascicolo_id, fascicolo_score, risk_level, summary, extracted_json, evidence_json,
                 source_json, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    communication_id,
                    "tenant-storage",
                    "outbound",
                    "studio@example.pec.it",
                    "INBOX",
                    f"<receipt-{role}@pec.test>",
                    "<atto-notificato@pec.test>",
                    f"Ricevuta PEC {role}",
                    "posta-certificata@pec.test",
                    "[]",
                    f"2026-06-06T12:0{index}:00+02:00",
                    "",
                    f"{role}-sha256",
                    "pec_receipt",
                    "PEC_OUTBOUND_PROOF",
                    f"PEC_RECEIPT_{role.upper()}",
                    0.99,
                    "alta",
                    0,
                    "open",
                    "FASC-1",
                    1.0,
                    "media",
                    f"Ricevuta PEC {role}",
                    "{}",
                    "{}",
                    "{}",
                    created_at,
                    created_at,
                ),
            )
            con.execute(
                """
                INSERT INTO pec_receipt_events
                (id, tenant_id, communication_id, role, referred_message_id, receipt_type, recipient,
                 receipt_at, daticert_sha256, daticert_json, proof_status, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    f"receipt-{role}",
                    "tenant-storage",
                    communication_id,
                    role,
                    "<atto-notificato@pec.test>",
                    role,
                    "controparte@example.pec.it",
                    f"2026-06-06T12:0{index}:00+02:00",
                    f"daticert-{role}",
                    "{}",
                    "complete" if role == "delivery" else "partial",
                    created_at,
                ),
            )

    app = Flask(__name__)
    app.config.update(TESTING=True)
    tenant_paths = {
        "EMAIL_CASELLA_DB": db_path.parent / "casella.json",
        "PEC_CONTROL_TOWER_DB": db_path,
        "FASCICOLI_DB": tmp_path / "fascicoli" / "fascicoli.json",
        "FASCICOLI_DOCS": tmp_path / "fascicoli" / "documenti",
        "SCADENZIARIO_DB": tmp_path / "scadenziario" / "scadenze.json",
        "AGENDA_DB": tmp_path / "agenda" / "agenda.json",
    }
    for path in tenant_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    def fake_tenant_data_path(key, default="", *aliases, require_tenant=True):
        return str(tenant_paths[key])

    monkeypatch.setattr("web.services.tenant_paths.tenant_data_path", fake_tenant_data_path)
    context = OperationalQueryContext(
        tenant_id="studio-slug",
        user_id="user-test",
        username="Avvocato Test",
        user=_User(),
        permissions={"ai.usa", "messaggi.leggi", "fascicoli.leggi"},
        tenant_context_available=True,
    )
    tools = OperationalKnowledgeTools(repositories={})
    with app.app_context():
        g.tenant_slug = "studio-slug"
        g.auth_tenant_slug = "studio-slug"
        g.data_paths = {key: str(value) for key, value in tenant_paths.items()}
        result = tools.answer_pec_control_question("Qual è la prova completa di questa notifica?", context, limit=5)

    assert result.ok is True
    payload = result.data[0]
    assert payload["summary"] == "Fascicoli prova notifica ricostruiti: 1 (1 completi)."
    assert payload["items"][0]["proof_complete"] is True
    assert payload["items"][0]["matter_id"] == "FASC-1"
    answer = OperationalResponseComposer().compose(
        question="Qual è la prova completa di questa notifica?",
        route=OperationalRoute(
            "pec_control_tower",
            "pec_control_tower",
            ("pec_control_tower",),
            "Qual è la prova completa di questa notifica?",
        ),
        results=[result],
    )
    assert "Prova: completa" in answer.answer
    assert "Ricevute collegate" in answer.answer
    assert "ricevuta di accettazione" in answer.answer
    assert "ricevuta di consegna" in answer.answer


def test_pec_control_tower_generation_script_answers_lex_matrix(tmp_path):
    script = Path("scripts/test_pec_control_tower.py")
    completed = subprocess.run(
        [sys.executable, str(script), "--runtime-root", str(tmp_path / "runtime")],
        cwd=Path.cwd(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["audit"]["ok"] is True
    assert len(payload["answers"]) == 10
    assert any("Prova: completa" in item["answer"] for item in payload["answers"])
    assert any("Scadenza" in item["answer"] and "da confermare" in item["answer"] for item in payload["answers"])


def test_pec_control_tower_api_ingest_list_and_confirm_deadline(tmp_path, monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True)

    paths = {
        "EMAIL_CASELLA_DB": tmp_path / "email" / "casella.json",
        "FASCICOLI_DB": tmp_path / "fascicoli" / "fascicoli.json",
        "FASCICOLI_DOCS": tmp_path / "fascicoli" / "documenti",
        "SCADENZIARIO_DB": tmp_path / "scadenziario" / "scadenze.json",
        "AGENDA_DB": tmp_path / "agenda" / "appuntamenti.json",
    }
    for path in paths.values():
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)

    def fake_tenant_data_path(key, default="", *aliases, require_tenant=True):
        return str(paths[key])

    monkeypatch.setattr("web.blueprints.pec_control_tower_api.tenant_data_path", fake_tenant_data_path)
    monkeypatch.setattr(
        "web.blueprints.pec_control_tower_api.GestioneEmailRicevute",
        lambda _path: _FakeEmailArchive({"pa-risposta": _sample_pa_pec()}),
    )

    @app.before_request
    def _auth():
        g.utente_corrente = _User()
        g.tenant_slug = "tenant-test"
        g.data_paths = {"PEC_CONTROL_TOWER_DB": str(tmp_path / "email" / "pec_control_tower.sqlite")}

    app.register_blueprint(pec_control_tower_api, url_prefix="/api")

    with app.test_client() as client:
        ingest = client.post(
            "/api/pec/ingest",
            data=_sample_court_pec(),
            content_type="message/rfc822",
            headers={"X-IUSENTRA-PEC-ACCOUNT": "studio@example.pec.it"},
        )
        assert ingest.status_code == 201
        communication = ingest.get_json()["data"]
        assert communication["legal_category"] == "PROVVEDIMENTO_GIUDIZIARIO"

        listing = client.get("/api/communications")
        assert listing.status_code == 200
        assert listing.get_json()["count"] == 1

        backfill = client.post("/api/pec/backfill-locali")
        assert backfill.status_code == 200
        assert backfill.get_json()["backfill"]["ingested"] == 1

        deadlines = client.get("/api/deadlines")
        assert deadlines.status_code == 200
        deadline_id = deadlines.get_json()["data"][0]["id"]

        confirmed = client.post(
            f"/api/deadlines/{deadline_id}/confirm",
            json={"confirmation_rule": "Verifica avvocato su fascicolo e comunicazione PEC."},
        )
        assert confirmed.status_code == 200
        assert confirmed.get_json()["data"]["status"] == "confirmed"

        audit = client.get("/api/audit/")
        assert audit.status_code == 200
        assert audit.get_json()["chain"]["ok"] is True
