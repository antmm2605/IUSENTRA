from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from pct.agenda import Agenda, TipoAppuntamento
from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.pec_pipeline import PecAuditRepository
from pct.scadenziario import GestioneScadenziario, PrioritaTermine, StatoTermine, TipoTermine
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.helpers import get_agenda, get_scadenziario
from web.services.pdf_deadline_import import import_pdf_deadlines, preview_pdf_deadlines
from web.services.react_scadenziario_bridge import (
    _document_presidio_event_label,
    _source_evidence,
    _visible_legal_text,
    build_react_scadenziario_payload,
    calculator_templates_for_guide,
    dedupe_calculator_templates,
)


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "react-test-key"
    return app


def _remote_hearing_pdf_bytes(link: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.drawString(72, 790, "Tribunale di Milano")
    pdf.drawString(72, 770, "Sezione Lavoro")
    pdf.drawString(72, 740, "N. R.G. 1754/2026")
    pdf.drawString(72, 720, "Fissa l'udienza in data 20/05/2026, alle ore 10:00, con collegamento audiovisivo.")
    pdf.drawString(72, 700, "Data di firma del provvedimento: 24/02/2026.")
    pdf.drawString(72, 680, "Partecipa alla riunione Microsoft Teams")
    pdf.linkURL(link, (72, 670, 420, 695), relative=0)
    pdf.save()
    return buffer.getvalue()


def _write_control_tower_receipt(email_dir: Path, *, tenant_id: str = "studio-test") -> Path:
    email_dir.mkdir(parents=True, exist_ok=True)
    audit_db = email_dir / "pec_audit.sqlite"
    tower_db = email_dir / "pec_control_tower.sqlite"
    with sqlite3.connect(audit_db) as connection:
        connection.execute(
            """
            CREATE TABLE pec_messages (
                id TEXT PRIMARY KEY,
                tenant_id TEXT,
                message_id_header TEXT,
                received_at TEXT,
                metadata_json TEXT,
                mime_sha256 TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO pec_messages (id, tenant_id, message_id_header, received_at, metadata_json, mime_sha256)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "pec_f205aa7f34c13b363f94af81",
                tenant_id,
                "<jpec1329.20260716163700.49709.401.1.2@pec.aruba.it>",
                "2026-07-16T14:37:00Z",
                json.dumps(
                    {
                        "headers": {
                            "from": "posta-certificata@pec.aruba.it",
                            "subject": "ACCETTAZIONE: Liquidazione delle spese legali relative sentenza n.325/2025 pubblicata il 26/02/2025 Tribunale di Vibo Valentia",
                            "to": "giuseppe.montagnese94@pec.it",
                        }
                    }
                ),
                "f205aa7f34c13b363f94af8117df82909b606a380680ca77f183f4597333cfa2",
            ),
        )
    with sqlite3.connect(tower_db) as connection:
        connection.execute(
            """
            CREATE TABLE legal_communications (
                id TEXT PRIMARY KEY,
                tenant_id TEXT,
                message_id_header TEXT,
                original_message_id TEXT,
                subject TEXT,
                sender TEXT,
                recipients_json TEXT,
                received_at TEXT,
                sent_at TEXT,
                mime_sha256 TEXT,
                technical_type TEXT,
                legal_category TEXT,
                legal_event_type TEXT,
                confidence REAL,
                confidence_label TEXT,
                requires_human_confirmation INTEGER,
                status TEXT,
                fascicolo_id TEXT,
                fascicolo_score REAL,
                risk_level TEXT,
                summary TEXT,
                extracted_json TEXT,
                evidence_json TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO legal_communications (
                id, tenant_id, message_id_header, original_message_id, subject, sender,
                recipients_json, received_at, sent_at, mime_sha256, technical_type,
                legal_category, legal_event_type, confidence, confidence_label,
                requires_human_confirmation, status, fascicolo_id, fascicolo_score,
                risk_level, summary, extracted_json, evidence_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "lcom_9451841b00e74febb0360758",
                tenant_id,
                "jpec1329.20260716163700.49709.401.1.2@pec.aruba.it",
                "TI9V9N$0E3FCC23CD7CFC5028E721EE5F348032@pec.it",
                "ACCETTAZIONE: Liquidazione delle spese legali relative sentenza n.325/2025 pubblicata il 26/02/2025 Tribunale di Vibo Valentia",
                "posta-certificata@pec.aruba.it",
                json.dumps([{"email": "giuseppe.montagnese94@pec.it", "name": ""}]),
                "2026-07-16T14:37:00+00:00",
                "2026-07-16T14:37:00+00:00",
                "f205aa7f34c13b363f94af8117df82909b606a380680ca77f183f4597333cfa2",
                "PEC_RECEIPT_ACCEPTANCE",
                "PEC_OUTBOUND_PROOF",
                "ricevuta_accettazione_da_presidiare",
                0.95,
                "alta",
                1,
                "open",
                "",
                1.5,
                "alta",
                "Ricevuta di accettazione senza chiusura automatica della notifica.",
                json.dumps(
                    {
                        "fascicolo_match": {
                            "fascicolo_id": "",
                            "label": "Contarese c. MIM",
                            "reason": "tribunale",
                            "requires_human_match": True,
                            "score": 1.5,
                        },
                        "registri": [{"anno": "2025", "numero": "325"}],
                    }
                ),
                json.dumps(
                    {
                        "daticert": {
                            "mittente": "giuseppe.montagnese94@pec.it",
                            "destinatario": "usp.vv@istruzione.it",
                            "oggetto": "Liquidazione delle spese legali relative sentenza n.325/2025 pubblicata il 26/02/2025 Tribunale di Vibo Valentia",
                        }
                    }
                ),
            ),
        )
    return audit_db


def test_scadenziario_non_espone_marker_interno_del_presidio_notifica() -> None:
    text = _visible_legal_text(
        "IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:02245673-6b37-4173-bebe-2fbb7a1f9d77:da_preparare\n"
        "Preparare la relata di notifica."
    )

    assert text == "Preparare la relata di notifica."
    assert "IUSENTRA_LEGAL_NOTIFICATION" not in text


def test_evento_documentale_non_scambia_originale_notificato_per_notifica() -> None:
    source = SimpleNamespace(
        tipo=TipoTermine.ADEMPIMENTO,
        titolo="Attività processuale da presidiare",
        descrizione="Fonte documentale: Ricorso Zagari (originale notificato).pdf",
        note="PEC_AUDIT:docpresidio:FASC:DOC:termine:2026-08-31",
    )
    actual_notification = SimpleNamespace(
        tipo=TipoTermine.ADEMPIMENTO,
        titolo="Verifica o attività di notifica",
        descrizione="",
        note="",
    )

    assert _document_presidio_event_label(source) == "Attività processuale"
    assert _document_presidio_event_label(actual_notification) == "Notifica"


def test_react_scadenziario_page_collegata_nav_api_e_lex():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/ScadenziarioPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/scadenziarioData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/ScadenziarioPage.css").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")

    assert "/scadenziario" in app_source
    assert "isScadenziarioPage?<ScadenziarioPage/>" in app_source
    assert "/scadenziario/calcola-termini" in app_source
    assert "isCalculatorPage?<CalcolaTerminiPage/>" in app_source
    assert "Scadenziario Legale" in page_source
    assert "Calcolatore termini processuali" in page_source
    assert "export function CalcolaTerminiPage" in page_source
    assert "getDeadlineCalculator" in page_source
    assert "calculateProcessDeadline" in page_source
    assert "createProcessDeadline" in page_source
    assert "Prova di controllo" in page_source
    assert "formatItalianDate(result.deadline)" in page_source
    assert "formatItalianDate(step.date)" in page_source
    assert "Il risultato mostrerà la data" in page_source
    assert "mostrera" not in page_source
    assert "OperativeCards" in page_source
    assert "Completa selezionate" in page_source
    assert "Elimina selezionate" in page_source
    assert "Elimina tutto" in page_source
    assert "RemoteHearingNotice" in page_source
    assert "Apri link udienza audiovisiva" in page_source
    assert "Allegato udienza:" in page_source
    assert "Link verificato sull’allegato" in page_source
    assert "SourceEvidenceLink" in page_source
    assert "Apri fonte" in page_source
    assert "SourceDocumentModal" in page_source
    assert "OperationalModal" in page_source
    assert "openDeadlineDetail" in page_source
    assert "closeDeadlineDetail" in page_source
    assert 'ariaLabel="Scadenza selezionata"' in page_source
    assert "onOpenDetail={openDeadlineDetail}" in page_source
    assert "onOpen={onOpenSource}" in page_source
    assert ".iu-scad-source-link" in css
    assert "Hash audit" not in page_source
    assert "Fonte link" not in page_source
    assert "Normalizzato da verificare" not in page_source
    assert "Evento:" in page_source
    assert "Ufficio:" in page_source
    assert "removePdfCandidates" in page_source
    assert "Anteprima PDF svuotata" in page_source
    assert "maxDocuments: fascicoloId ? 0 : 25" in page_source
    assert "FloatingLex" in page_source
    assert 'context="scadenziario"' in page_source
    assert "postDeadlineAction" in page_source
    assert "useScadenziarioMobileLayout" in page_source
    assert "mobileLayout ? (" in page_source
    assert "getScadenziarioPage" in data_source
    assert "focus_id" in data_source
    assert "compatto" in data_source
    assert "calcolatore', '0" in data_source
    assert "buildQuery(true)" in page_source
    assert "if (data.query.compact)" in page_source
    assert "const completePayload = await getScadenziarioPage(buildQuery(false))" not in page_source
    assert "setBackgroundLoading(true)" not in page_source
    assert "DeadlineCalculatorTemplate" in data_source
    assert "DeadlineCalculatorResult" in data_source
    assert "focusId: asString(queryPayload.focusId" in data_source
    assert "compact: asBoolean(queryPayload.compact)" in data_source
    assert "/api/v1/ui/scadenziario" in data_source
    assert "/api/v1/ui/scadenziario/termini/calculate" in data_source
    assert "/api/v1/ui/scadenziario/termini/crea-scadenza" in data_source
    assert '@api_v1_react.get("/scadenziario")' in api_source
    assert '@api_v1_react.post("/scadenziario/termini/calculate")' in api_source
    assert '@api_v1_react.post("/scadenziario/termini/override")' in api_source
    assert ".iu-scad-page" in css
    assert ".iu-scad-calculator" in css
    assert ".iu-scad-remote-source" in css
    assert ".iu-scad-remote-check.is-verified" in css
    assert ".iu-scad-event-line" in css
    assert ".iu-scad-pdf-danger-btn" in css
    assert ".iu-scad-pdf-row-delete" in css
    assert "@media(max-width:760px)" in css
    assert "prefers-reduced-motion" in css


def test_calcolatore_separato_non_carica_template_nello_scadenziario_e_mantiene_guida() -> None:
    page_source = Path("frontend/src/components/ScadenziarioPage.tsx").read_text(encoding="utf-8")
    email_source = Path("frontend/src/emailData.ts").read_text(encoding="utf-8")
    bridge_source = Path("web/services/react_scadenziario_bridge.py").read_text(encoding="utf-8")

    assert "includeCalculator: false" in page_source
    assert "carica solo template, regole e fonti necessarie" in page_source
    assert "/api/v1/ui/email/source/${encoded}?name=${encodeURIComponent(name)}" in email_source
    assert "Allegato originale disponibile per visualizzazione o scarico." in email_source
    assert "include_calculator" in bridge_source

    templates = [
        {"code": "GUIDA-A", "name": "Termine A", "metadata": {"codice_guida": "GUIDA-A"}},
        {"code": "GUIDA-B", "name": "Termine B", "metadata": {"codice_guida": "GUIDA-B"}},
    ]
    assert [template["code"] for template in calculator_templates_for_guide(templates, "GUIDA-A")] == ["GUIDA-A"]


def test_react_scadenziario_bridge_usa_repository_reale(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        gestione = get_scadenziario()
        scadenza = gestione.nuova(
            "Deposito memoria conclusionale",
            TipoTermine.DEPOSITO_MEMORIA,
            (date.today() + timedelta(days=2)).isoformat(),
            descrizione="Termine da fascicolo test React",
            perentorio=True,
        )
        gestione.aggiorna(scadenza.id, priorita=PrioritaTermine.CRITICA)

    response = client.get("/api/v1/ui/scadenziario", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["read_only"] is False
    assert payload["contracts"]["writes"] == "operational_routes"
    assert payload["summary"]["open"] >= 1
    assert payload["summary"]["critical"] >= 1
    assert any(item["title"] == "Deposito memoria conclusionale" for item in payload["items"])
    row = next(item for item in payload["items"] if item["title"] == "Deposito memoria conclusionale")
    assert row["priority"] == "CRITICA"
    assert row["peremptory"] is True
    assert row["completeHref"].endswith(f"/{scadenza.id}/completa")
    assert payload["actions"]["exportCsv"] == "/scadenziario/export.csv"
    assert payload["actions"]["exportPdf"] == "/scadenziario/pdf"
    assert payload["actions"]["exportIcs"] == "/scadenziario/export.ics"
    assert payload["operativeCards"]
    assert payload["calculator"]["templates"]
    assert payload["calculator"]["endpoints"]["calculate"].endswith("/termini/calculate")
    assert payload["calculator"]["scheduler"]["channel"] == "PEC"


def test_react_scadenziario_apertura_non_scrive_e_calcola_scaduto_in_memoria(tmp_path: Path, monkeypatch):
    gestione = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = gestione.nuova(
        "Termine trascorso",
        TipoTermine.ALTRO,
        (date.today() - timedelta(days=1)).isoformat(),
    )

    def scrittura_vietata():
        raise AssertionError("La lettura React non deve aggiornare in massa le scadenze")

    monkeypatch.setattr(gestione, "scadute", scrittura_vietata)
    payload = build_react_scadenziario_payload(
        gestione_scadenziario=gestione,
        gestione_fascicoli=None,
        query_args={"vista": "scadute"},
    )

    row = next(item for item in payload["items"] if item["id"] == scadenza.id)
    assert row["status"] == "SCADUTO"
    assert row["statusLabel"] == "Scaduta"
    assert payload["summary"]["open"] == 0
    assert payload["summary"]["overdue"] == 1


def test_react_scadenziario_mantiene_contesto_legale_agenda_nel_dettaglio(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    due_date = (date.today() + timedelta(days=2)).isoformat()
    with app.app_context():
        get_agenda().aggiungi(
            "Udienza RG 274/2026",
            TipoAppuntamento.UDIENZA,
            f"{due_date}T09:30:00",
            cliente="LOPRETE DOMENICO",
            procedimento="RG 274/2026",
            tribunale="Tribunale di Palmi",
            avvocato="Avv. Giuseppe Montagnese",
        )
        scadenza = get_scadenziario().nuova(
            "Opposizione alla trattazione scritta ex art. 127-ter c.p.c. - RG 274/2026",
            TipoTermine.ADEMPIMENTO,
            due_date,
            id_fascicolo="B6A03AE6",
            id_utente_responsabile="scheduler",
            descrizione="Evento: esito deposito telematico. RG 274/2026.",
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            source_event_type="cancelleria_comunicazione",
            note="PEC_AUDIT:contesto-agenda",
        )

    response = client.get("/api/v1/ui/scadenziario?vista=tutte", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    row = next(item for item in payload["items"] if item["id"] == scadenza.id)

    assert response.status_code == 200
    assert row["title"] == "Opposizione alla trattazione scritta"
    assert row["clientLabel"] == "LOPRETE DOMENICO"
    assert row["fascicoloLabel"] == "RG 274/2026"
    assert row["officeLabel"] == "Tribunale di Palmi"
    assert row["ownerLabel"] == "Studio"
    assert row["sourceEventTypeLabel"] == "Opposizione alla trattazione scritta"
    assert "LOPRETE DOMENICO" in row["detailDescription"]
    assert "RG 274/2026" in row["detailDescription"]
    assert "Tribunale di Palmi" in row["detailDescription"]
    assert "PEC_AUDIT" not in row["detailDescription"]


def test_react_scadenziario_recupera_ufficio_dal_profilo_pec_salvato(tmp_path: Path):
    pec_db = tmp_path / "email" / "pec_audit.sqlite"
    repository = PecAuditRepository(pec_db, tenant_id="studio-test")
    message = EmailMessage()
    message["From"] = "tribunale.palmi@example.test"
    message["To"] = "studio@example.test"
    message["Date"] = "Tue, 14 Jul 2026 09:30:00 +0200"
    message["Message-ID"] = "<rg771-ufficio@example.test>"
    message["Subject"] = "Comunicazione RG 771/2025"
    message.set_content("Revoca udienza e fissazione termine per note in sostituzione udienza.")
    ingested = repository.ingest_mime(
        message.as_bytes(),
        account_email="studio@example.test",
        enqueue=False,
    )
    parsed = repository.parse_and_store(ingested["id"])
    with repository.connect() as connection:
        repository._insert_validation_report(
            connection,
            message_id=ingested["id"],
            parsed_version_id=parsed["parsed_version_id"],
            report={
                "event_type": "comunicazione_cancelleria",
                "severity": "ok",
                "procedural_profile": {
                    "ufficio": "Tribunale di Palmi",
                    "numero_ruolo": "771/2025",
                },
            },
            actor="test",
        )

    gestione = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = gestione.nuova(
        "Revoca udienza e fissazione termine",
        TipoTermine.UDIENZA,
        "2026-07-14",
        note=f"PEC_AUDIT:{ingested['id']}",
    )
    payload = build_react_scadenziario_payload(
        gestione_scadenziario=gestione,
        gestione_fascicoli=None,
        query_args={"vista": "tutte"},
        pec_audit_db=str(pec_db),
        tenant_id="studio-test",
    )

    row = next(item for item in payload["items"] if item["id"] == scadenza.id)
    assert row["officeLabel"] == "Tribunale di Palmi"
    assert row["sourceHref"] == f"/email/?audit_id={ingested['id']}"


def test_react_scadenziario_ricerca_globale_trova_scaduta_per_ufficio_pec(tmp_path: Path):
    pec_db = tmp_path / "email" / "pec_audit.sqlite"
    repository = PecAuditRepository(pec_db, tenant_id="studio-test")
    message = EmailMessage()
    message["From"] = "tribunale.palmi@example.test"
    message["To"] = "studio@example.test"
    message["Date"] = "Tue, 14 Jul 2026 09:30:00 +0200"
    message["Message-ID"] = "<rg771-search@example.test>"
    message["Subject"] = "Comunicazione RG 771/2025"
    message.set_content("Revoca udienza e fissazione termine per note in sostituzione udienza.")
    ingested = repository.ingest_mime(
        message.as_bytes(),
        account_email="studio@example.test",
        enqueue=False,
    )
    parsed = repository.parse_and_store(ingested["id"])
    with repository.connect() as connection:
        repository._insert_validation_report(
            connection,
            message_id=ingested["id"],
            parsed_version_id=parsed["parsed_version_id"],
            report={
                "event_type": "comunicazione_cancelleria",
                "severity": "ok",
                "procedural_profile": {
                    "ufficio": "Tribunale di Palmi",
                    "numero_ruolo": "771/2025",
                },
            },
            actor="test",
        )

    gestione = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = gestione.nuova(
        "Revoca udienza e fissazione termine - RG 771/2025",
        TipoTermine.UDIENZA,
        "2026-07-14",
        note=f"PEC_AUDIT:{ingested['id']}",
    )
    payload = build_react_scadenziario_payload(
        gestione_scadenziario=gestione,
        gestione_fascicoli=None,
        query_args={"vista": "aperte", "q": "Tribunale di Palmi"},
        pec_audit_db=str(pec_db),
        tenant_id="studio-test",
    )

    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == scadenza.id
    assert payload["items"][0]["status"] == "SCADUTO"
    assert payload["items"][0]["officeLabel"] == "Tribunale di Palmi"
    assert payload["query"]["view"] == "aperte"
    assert payload["query"]["searchAcrossAll"] is True


def test_scadenziario_ricevuta_accettazione_control_tower_apre_pec_specifica(tmp_path: Path):
    pec_db = _write_control_tower_receipt(tmp_path / "email")
    gestione = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = gestione.nuova(
        "Presidio ricevute PEC da completare",
        TipoTermine.ADEMPIMENTO,
        "2026-07-17",
        descrizione="Bozza da confermare generata da presidio PEC Control Tower.",
        note="Termine operativo non definitivo: conferma professionale obbligatoria.",
        source_event_type="ricevuta_accettazione_da_presidiare",
        source_event_at="2026-07-16T14:37:00+00:00",
    )

    payload = build_react_scadenziario_payload(
        gestione_scadenziario=gestione,
        gestione_fascicoli=None,
        query_args={"vista": "tutte"},
        pec_audit_db=str(pec_db),
        tenant_id="studio-test",
    )

    row = next(item for item in payload["items"] if item["id"] == scadenza.id)
    assert row["sourceHref"] == "/email/?audit_id=pec_f205aa7f34c13b363f94af81"
    assert row["sourceLabel"] == "PEC di accettazione"
    assert row["sourceEventTypeLabel"] == "Ricevuta di accettazione PEC da presidiare"
    assert row["title"].startswith("PEC di accettazione: Liquidazione delle spese legali")
    assert "usp.vv@istruzione.it" in row["detailDescription"]
    assert "Prova parziale" in row["detailDescription"]
    assert "Possibile fascicolo da verificare: Contarese c. MIM" in row["detailDescription"]
    assert row["clientLabel"] != "Contarese c. MIM"
    assert row["fascicoloLabel"] != "Contarese c. MIM"


def test_scadenziario_ricevuta_consegna_prevale_su_tipo_tecnico_storico(tmp_path: Path):
    pec_db = _write_control_tower_receipt(tmp_path / "email")
    tower_db = pec_db.with_name("pec_control_tower.sqlite")
    with sqlite3.connect(tower_db) as connection:
        connection.execute(
            """
            UPDATE legal_communications
            SET subject = ?,
                legal_event_type = ?,
                technical_type = ?
            WHERE id = ?
            """,
            (
                "CONSEGNA: Notificazione ai sensi della legge n. 53/1994 [JQ278-L01]",
                "ricevuta_accettazione_da_presidiare",
                "PEC_RECEIPT_ACCEPTANCE",
                "lcom_9451841b00e74febb0360758",
            ),
        )

    gestione = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = gestione.nuova(
        "Presidio ricevute PEC da completare",
        TipoTermine.ADEMPIMENTO,
        "2026-07-17",
        source_event_type="ricevuta_accettazione_da_presidiare",
        source_event_at="2026-07-16T14:37:00+00:00",
    )

    payload = build_react_scadenziario_payload(
        gestione_scadenziario=gestione,
        gestione_fascicoli=None,
        query_args={"vista": "tutte"},
        pec_audit_db=str(pec_db),
        tenant_id="studio-test",
    )

    row = next(item for item in payload["items"] if item["id"] == scadenza.id)
    assert row["sourceLabel"] == "PEC di consegna"
    assert row["sourceEventTypeLabel"] == "Ricevuta di consegna PEC da conservare"
    assert row["title"].startswith("PEC di consegna:")
    assert row["sourceHref"] == "/email/?audit_id=pec_f205aa7f34c13b363f94af81"


def test_react_scadenziario_dettaglio_compatto_arriva_prima_dell_elenco_completo(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    bridge_source = Path("web/services/react_scadenziario_bridge.py").read_text(encoding="utf-8")
    due_date = (date.today() + timedelta(days=2)).isoformat()
    with app.app_context():
        get_agenda().aggiungi(
            "Udienza RG 274/2026",
            TipoAppuntamento.UDIENZA,
            f"{due_date}T09:30:00",
            cliente="LOPRETE DOMENICO",
            procedimento="RG 274/2026",
            tribunale="Tribunale di Palmi",
        )
        selected = get_scadenziario().nuova(
            "Opposizione alla trattazione scritta ex art. 127-ter c.p.c. - RG 274/2026",
            TipoTermine.ADEMPIMENTO,
            due_date,
            id_fascicolo="B6A03AE6",
            descrizione="Evento collegato al fascicolo RG 274/2026.",
        )
        get_scadenziario().nuova(
            "Deposito memoria non selezionato",
            TipoTermine.DEPOSITO_MEMORIA,
            due_date,
        )

    response = client.get(
        f"/api/v1/ui/scadenziario?vista=tutte&focus_id={selected.id}&compatto=1",
        headers={"X-API-Key": "react-test-key"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["query"]["focusId"] == selected.id
    assert payload["query"]["compact"] is True
    assert [item["id"] for item in payload["items"]] == [selected.id]
    assert payload["items"][0]["title"] == "Opposizione alla trattazione scritta"
    assert payload["items"][0]["clientLabel"] == "LOPRETE DOMENICO"
    assert payload["calculator"]["templates"] == []
    assert payload["overduePreview"] == []
    assert payload["nextItems"] == []
    assert "focused_item = gestione_scadenziario.get(focus_id)" in bridge_source
    assert "if compact:" in bridge_source
    assert "filtered = [item for item in all_items if str(getattr(item, \"id\", \"\") or \"\") == focus_id]" in bridge_source
    assert "pec_profile_items = filtered" in bridge_source
    assert "base_items=all_items" in bridge_source
    assert "_agenda_candidates_for_compact_deadline" in bridge_source
    assert "selected_rgs: set[str] = set()" in bridge_source
    assert "needs_agenda_context = not (" in bridge_source
    assert "all(_is_legal_notification_presidio(item) for item in filtered)" in bridge_source
    assert "agenda_items = _agenda_candidates_for_compact_deadline(agenda_items, filtered)" in bridge_source
    assert "for item in filtered:" in bridge_source


def test_react_scadenziario_mostra_cliente_fascicolo_non_responsabile(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        cliente = GestioneClienti(db_path=app.config["CLIENTI_DB"]).nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Filippo",
        cognome="Azzaro",
        )
        fascicoli = GestioneFascicoli(
            db_path=app.config["FASCICOLI_DB"],
            documents_dir=app.config["FASCICOLI_DOCS"],
            archive_dir=app.config["FASCICOLI_ARCH"],
        )
        fascicolo = fascicoli.nuovo(
            "Usucapione",
            TipoFascicolo.CIVILE,
            id_cliente=cliente.id,
            nome_cliente=cliente.nome_completo,
            numero_rg="274",
            anno_rg=2026,
            oggetto="Usucapione",
            avvocato_referente="Antonella Mammola",
        )
        scadenza = get_scadenziario().nuova(
            "Udienza da portale",
            TipoTermine.UDIENZA,
            "2026-07-09",
            id_fascicolo=fascicolo.id,
        )

    response = client.get("/api/v1/ui/scadenziario?vista=tutte", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    row = next(item for item in payload["items"] if item["id"] == scadenza.id)

    assert response.status_code == 200
    assert row["fascicoloLabel"] == "RG 274/2026 - Usucapione"
    assert row["clientLabel"] == "Azzaro Filippo"
    assert row["ownerLabel"] == "Antonella Mammola"


def test_react_scadenziario_presidio_notifica_sentenza_usa_pec_e_titolo_uniforme(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        cliente = GestioneClienti(db_path=app.config["CLIENTI_DB"]).nuovo(
            TipoCliente.PERSONA_FISICA,
            nome="Maria",
            cognome="Romeo",
        )
        fascicoli = GestioneFascicoli(
            db_path=app.config["FASCICOLI_DB"],
            documents_dir=app.config["FASCICOLI_DOCS"],
            archive_dir=app.config["FASCICOLI_ARCH"],
        )
        fascicolo = fascicoli.nuovo(
            "Romeo Maria c. MIM",
            TipoFascicolo.LAVORO,
            id_cliente=cliente.id,
            nome_cliente=cliente.nome_completo,
            numero_rg="1428",
            anno_rg=2026,
            oggetto="Romeo Maria c. MIM",
            tribunale="TRIBUNALE DI PALMI",
        )
        scadenza = get_scadenziario().nuova(
            "ROMEO MARIA - SENTENZA A VERBALE (art. 127 ter cpc) Comunicazione di cancelleria - RG 1428/2026",
            TipoTermine.NOTIFICA,
            "2026-07-20",
            id_fascicolo=fascicolo.id,
            descrizione="Sentenza o sentenza a verbale già resa: la comunicazione di cancelleria non prova la notifica.",
            note=(
                "IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:presidio-romeo:da_preparare\n"
                "PEC_AUDIT:pec_romeo\n"
                "Fonte documentale: 9732730s.pdf.zip"
            ),
            source_event_type="legal_notification_presidio",
        )

    response = client.get("/api/v1/ui/scadenziario?vista=tutte", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    row = next(item for item in payload["items"] if item["id"] == scadenza.id)

    assert row["title"] == "Sentenza da valutare per la notifica - Romeo Maria - RG 1428/2026"
    assert row["sourceEventTypeLabel"] == "Sentenza da valutare per la notifica"
    assert row["sourceKind"] == "pec"
    assert row["sourceHref"] == "/api/v1/ui/email/source/pec_romeo?name=9732730s.pdf.zip"
    assert row["sourceLabel"] == "PEC originale - 9732730s.pdf.zip"
    assert "/fascicoli/" not in row["sourceHref"]
    assert "non fa decorrere da sola il termine breve" in row["detailDescription"]


def test_source_evidence_presidio_notifica_senza_marker_pec_non_apre_documenti_fascicolo():
    scadenza = SimpleNamespace(
        tipo=TipoTermine.NOTIFICA,
        titolo="Sentenza da valutare per la notifica",
        descrizione="Fonte documentale: 19040620s.pdf",
        note="IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:presidio-alfano:da_preparare",
        source_event_type="legal_notification_presidio",
        hearing_mode_source="19040620s.pdf",
    )

    source = _source_evidence(scadenza, fascicolo_id="C3565650")

    assert source == {
        "sourceHref": "",
        "sourceLabel": "PEC sorgente da riallineare",
        "sourceKind": "pec",
        "sourceVerified": False,
    }


def test_source_evidence_corpo_pec_apre_pec_originale_non_allegato_vuoto():
    scadenza = SimpleNamespace(
        tipo=TipoTermine.UDIENZA,
        titolo="Rinvio udienza da comunicazione di cancelleria - RG 771/2025",
        descrizione="Data processuale futura letta da corpo PEC: udienza rinviata.",
        note="PEC_AUDIT:pec_rinvio\nFonte documentale: corpo PEC",
        source_event_type="comunicazione_cancelleria",
        hearing_mode_source="corpo PEC",
    )

    source = _source_evidence(scadenza, fascicolo_id="FASC-RINVIO")

    assert source == {
        "sourceHref": "/email/?audit_id=pec_rinvio",
        "sourceLabel": "PEC originale",
        "sourceKind": "pec",
        "sourceVerified": True,
    }


def test_source_evidence_marker_strutturale_preserva_id_legacy_con_due_punti():
    scadenza = SimpleNamespace(
        tipo=TipoTermine.UDIENZA,
        titolo="Udienza da PEC",
        descrizione="Fonte documentale: corpo PEC",
        note="PEC_AUDIT:email:03c7d9aef123:hearing:udienza-1:deadline",
        source_event_type="comunicazione_cancelleria",
        hearing_mode_source="corpo PEC",
    )

    source = _source_evidence(scadenza)

    assert source["sourceHref"] == "/email/?audit_id=email%3A03c7d9aef123"
    assert source["sourceKind"] == "pec"
    assert source["sourceVerified"] is True


def test_source_evidence_testo_href_apre_pec_originale_non_allegato_vuoto():
    scadenza = SimpleNamespace(
        tipo=TipoTermine.UDIENZA,
        titolo="Link udienza da PEC - RG 1754/2026",
        descrizione="Collegamento audiovisivo letto da testo/href della PEC.",
        note="PEC_AUDIT:pec_link\nFonte documentale: testo/href",
        source_event_type="comunicazione_cancelleria",
        hearing_mode_source="testo/href",
    )

    source = _source_evidence(scadenza, fascicolo_id="FASC-LINK")

    assert source == {
        "sourceHref": "/email/?audit_id=pec_link",
        "sourceLabel": "PEC originale",
        "sourceKind": "pec",
        "sourceVerified": True,
    }


def test_source_evidence_fonte_link_udienza_apre_zip_pdf_della_pec():
    scadenza = SimpleNamespace(
        tipo=TipoTermine.UDIENZA,
        titolo="Fissazione udienza - RG 2780/2024",
        descrizione="Udienza comunicata dalla cancelleria.",
        note=(
            "PEC_AUDIT:pec_udienza_2780\n"
            "Fonte link udienza: Decreto fissazione udienza 8960334s.pdf.zip"
        ),
        source_event_type="comunicazione_cancelleria",
        hearing_mode_source="",
        remote_hearing_source="",
    )

    source = _source_evidence(scadenza, fascicolo_id="FASC-2780")

    assert source == {
        "sourceHref": "/api/v1/ui/email/source/pec_udienza_2780?name=Decreto%20fissazione%20udienza%208960334s.pdf.zip",
        "sourceLabel": "PEC originale - Decreto fissazione udienza 8960334s.pdf.zip",
        "sourceKind": "pec",
        "sourceVerified": True,
    }


def test_source_evidence_label_generica_non_blocca_zip_nelle_note():
    scadenza = SimpleNamespace(
        tipo=TipoTermine.UDIENZA,
        titolo="Fissazione udienza - RG 2780/2024",
        descrizione="Data letta dal corpo PEC, documento nello ZIP.",
        note=(
            "PEC_AUDIT:pec_udienza_generica\n"
            "Fonte documentale: Decreto fissazione udienza 2780s.pdf.zip"
        ),
        source_event_type="comunicazione_cancelleria",
        hearing_mode_source="corpo PEC",
        remote_hearing_source="",
    )

    source = _source_evidence(scadenza, fascicolo_id="FASC-2780")

    assert source["sourceHref"] == "/api/v1/ui/email/source/pec_udienza_generica?name=Decreto%20fissazione%20udienza%202780s.pdf.zip"
    assert source["sourceLabel"] == "PEC originale - Decreto fissazione udienza 2780s.pdf.zip"


def test_source_evidence_fonte_evento_esatta_vince_su_altro_zip_del_profilo():
    scadenza = SimpleNamespace(
        tipo=TipoTermine.NOTIFICA,
        titolo="Sentenza da valutare per la notifica",
        descrizione="Provvedimento ricevuto tramite PEC.",
        note="PEC_AUDIT:pec_sentenza\nFonte documentale: sentenza.pdf",
        source_event_type="sentenza_da_valutare_per_notifica",
        hearing_mode_source="sentenza.pdf",
        remote_hearing_source="",
    )

    source = _source_evidence(
        scadenza,
        fascicolo_id="FASC-SENTENZA",
        pec_profile={"_indexed_source_name": "ricorso.pdf.zip"},
    )

    assert source["sourceHref"] == "/api/v1/ui/email/source/pec_sentenza?name=sentenza.pdf"
    assert source["sourceLabel"] == "PEC originale - sentenza.pdf"


def test_pdf_notificato_alimenta_scadenziario_agenda_senza_duplicare_link_audiovisivo(tmp_path: Path):
    exact_link = "https://teams.microsoft.com/meet/38858779158973?p=Js9ShyCOEg7O19oPeQ"
    cliente = GestioneClienti(db_path=str(tmp_path / "clienti.json")).nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Rosa Maria",
        cognome="Vinci",
    )
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fascicolo = fascicoli.nuovo(
        "Carta docente",
        TipoFascicolo.LAVORO,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        numero_rg="1754",
        anno_rg=2026,
        oggetto="Carta docente",
        tribunale="Tribunale di Milano",
    )
    documento = fascicoli.aggiungi_documento(
        fascicolo.id,
        "Decreto fissazione udienza (originale notificato).pdf",
        TipoDocumento.DECRETO,
        _remote_hearing_pdf_bytes(exact_link),
    )
    scadenziario = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    agenda = Agenda(db_path=str(tmp_path / "agenda.json"))

    preview = preview_pdf_deadlines(
        gestione_fascicoli=fascicoli,
        gestione_scadenziario=scadenziario,
        id_fascicolo=fascicolo.id,
    )
    candidate = next(item for item in preview.candidates if item.type == TipoTermine.UDIENZA.value)

    assert candidate.document_id == documento.id
    assert candidate.due_date == "2026-05-20"
    assert candidate.event_time == "10:00"
    assert candidate.remote_hearing_url == exact_link
    assert candidate.remote_hearing_verified is True
    assert candidate.client_label == "Vinci Rosa Maria"
    assert not any(item.due_date == "2026-02-24" for item in preview.candidates)

    result = import_pdf_deadlines(
        gestione_fascicoli=fascicoli,
        gestione_scadenziario=scadenziario,
        gestione_agenda=agenda,
        selected_ids=[candidate.id],
        id_fascicolo=fascicolo.id,
        user_id="avvocato",
    )
    repeated = import_pdf_deadlines(
        gestione_fascicoli=fascicoli,
        gestione_scadenziario=scadenziario,
        gestione_agenda=agenda,
        selected_ids=[candidate.id],
        id_fascicolo=fascicolo.id,
        user_id="avvocato",
    )
    scadenze = scadenziario.tutte(solo_aperte=False)
    appuntamenti = agenda.tutti()

    assert result["created"] == 1
    assert repeated["created"] == 0
    assert len(scadenze) == 1
    assert len(appuntamenti) == 1
    assert scadenze[0].source_event_type == "documento_fascicolo"
    assert scadenze[0].remote_hearing_url == exact_link
    assert scadenze[0].id_appuntamento == appuntamenti[0].id
    assert appuntamenti[0].data_ora.startswith("2026-05-20T10:00")
    assert appuntamenti[0].cliente == "Vinci Rosa Maria"
    assert exact_link in appuntamenti[0].note


def test_react_scadenziario_bridge_espone_link_udienza_remota(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    exact_link = (
        "https://teams.microsoft.com/dl/launcher/launcher.html?"
        "url=%2F_%23%2Fl%2Fmeetup-join%2F19%3Ameeting_TEST%40thread.v2%2F0"
        "%3Fcontext%3D%257b%2522Tid%2522%253a%252211111111-1111-1111-1111-111111111111"
        "%2522%252c%2522Oid%2522%253a%252222222222-2222-2222-2222-222222222222%2522%257d"
        "%26anon%3Dtrue&type=meetup-join&deeplinkId=33333333-3333-3333-3333-333333333333"
        "&directDl=true&msLaunch=true&enableMobilePage=true&suppressPrompt=true"
    )
    with app.app_context():
        gestione = get_scadenziario()
        scadenza = gestione.nuova(
            "Udienza da PEC: RG 1263/2026/LAV",
            TipoTermine.UDIENZA,
            (date.today() + timedelta(days=10)).isoformat(),
            descrizione="Fissazione udienza con strumenti audiovisivi",
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            note=f"PEC_AUDIT:msg-link\nLink udienza audiovisiva: {exact_link}\nFonte link udienza: 13744017s.pdf.zip\nVerifica link udienza: identico alla fonte letta.",
            remote_hearing_detected=True,
            remote_hearing_mode="audiovisiva",
            remote_hearing_url=exact_link,
            remote_hearing_source="13744017s.pdf.zip",
            remote_hearing_verified=True,
            remote_hearing_time="29/10/2026 ore 09:15",
        )

    response = client.get("/api/v1/ui/scadenziario?vista=pec", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    row = next(item for item in payload["items"] if item["id"] == scadenza.id)

    assert response.status_code == 200
    assert row["remoteHearingDetected"] is True
    assert row["remoteHearingUrl"] == exact_link
    assert row["remoteHearingSource"] == "13744017s.pdf.zip"
    assert row["remoteHearingVerified"] is True
    assert exact_link in row["remoteHearingUrl"]
    assert row["sourceHref"] == "/api/v1/ui/email/source/msg-link?name=13744017s.pdf.zip"
    assert row["sourceLabel"] == "PEC originale - 13744017s.pdf.zip"
    assert row["sourceKind"] == "pec"
    assert row["sourceVerified"] is True


def test_react_scadenziario_bridge_espone_modalita_udienza_in_presenza(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        gestione = get_scadenziario()
        scadenza = gestione.nuova(
            "Udienza RG 1548/2026",
            TipoTermine.UDIENZA,
            (date.today() + timedelta(days=20)).isoformat(),
            descrizione="Udienza fissata dal decreto presente nel fascicolo",
            hearing_mode="presenza",
            hearing_mode_source="Decreto fissazione udienza.pdf",
            hearing_time="09:30",
        )

    response = client.get("/api/v1/ui/scadenziario?vista=tutte", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    row = next(item for item in payload["items"] if item["id"] == scadenza.id)

    assert response.status_code == 200
    assert row["hearingMode"] == "In presenza"
    assert row["hearingModeSource"] == "Decreto fissazione udienza.pdf"
    assert row["hearingTime"] == "09:30"
    assert row["remoteHearingDetected"] is False


def test_react_scadenziario_bridge_nasconde_testi_tecnici_da_pec(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        gestione = get_scadenziario()
        legacy = gestione.nuova(
            "Udienza da PEC: POSTA CERTIFICATA: COMUNICAZIONE 3950/2026/LAV",
            TipoTermine.UDIENZA,
            (date.today() + timedelta(days=12)).isoformat(),
            id_fascicolo="RG 3950/2026",
            descrizione="Data processuale futura letta da Comunicazione.xml: Oggetto: FISSAZIONE UDIENZA. backend payload runtime source_event profile_id",
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            source_event_type="pct_deposito",
            note=(
                "PEC_AUDIT:msg-tech-old\n"
                "Scadenza: scad-old\n"
                "Fonte: pipeline PEC audit-grade.\n"
                "Fissazione udienza di discussione con strumenti audiovisivi."
            ),
        )
        scadenza = gestione.nuova(
            "VINCI ROSA MARIA - FISSAZIONE UDIENZA DI DISCUSSIONE - RG 3950/2026",
            TipoTermine.UDIENZA,
            (date.today() + timedelta(days=12)).isoformat(),
            id_fascicolo="RG 3950/2026",
            descrizione=(
                "Cliente: VINCI ROSA MARIA\n"
                "Parte/soggetto: Ricorrente principale: VINCI ROSA MARIA\n"
                "Ufficio: Tribunale di Milano\n"
                "Giudice: TOSONI CLAUDIA\n"
                "Evento: FISSAZIONE UDIENZA DI DISCUSSIONE\n"
                "Udienza: 09/07/2026 09:30 notifica/comunicazione che può generare termini\n"
                "Attività per l'avvocato: verificare provvedimento, link audiovisivo e istruzioni di collegamento."
            ),
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            source_event_type="comunicazione_cancelleria",
            note=(
                "PEC_AUDIT:msg-tech\n"
                "Scadenza: scad-123\n"
                "Fonte: pipeline PEC audit-grade.\n"
                "Link udienza audiovisiva: da acquisire dal PDF allegato."
            ),
        )

    response = client.get("/api/v1/ui/scadenziario?vista=pec", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    row = next(item for item in payload["items"] if item["id"] == scadenza.id)
    ids = {item["id"] for item in payload["items"]}
    visible = " ".join(
        str(row.get(key) or "")
        for key in ("title", "description", "sourceEventTypeLabel", "officeLabel", "remoteHearingSource", "remoteHearingAccessInfo")
    )

    assert response.status_code == 200
    assert legacy.id not in ids
    assert row["title"] == "VINCI ROSA MARIA - FISSAZIONE UDIENZA DI DISCUSSIONE - RG 3950/2026"
    assert "Cliente: VINCI ROSA MARIA" in row["description"]
    assert "Parte/soggetto: Ricorrente principale: VINCI ROSA MARIA" in row["description"]
    assert "Tribunale di Milano" in row["description"]
    assert "Udienza: 09/07/2026 09:30" in row["description"]
    assert "Cliente: VINCI ROSA MARIA" in row["detailDescription"]
    assert "Parte/soggetto: Ricorrente principale: VINCI ROSA MARIA" in row["detailDescription"]
    assert "Udienza: 09/07/2026 09:30" in row["detailDescription"]
    assert "notifica/comunicazione" not in row["detailDescription"]
    assert "Attività per l'avvocato" in row["detailDescription"]
    assert row["detailDescription"].count("Cliente: VINCI ROSA MARIA") == 1
    assert row["sourceEventTypeLabel"] == "Udienza"
    assert "Fissazione udienza" not in visible
    for token in ("POSTA CERTIFICATA", "COMUNICAZIONE 3950/2026", "Data processuale futura", "PEC_AUDIT", "pipeline", "payload", "runtime", "backend", "source_event", "profile_id", "audit-grade", "Deposito telematico"):
        assert token.lower() not in visible.lower()
        assert token.lower() not in row["detailDescription"].lower()


def test_react_scadenziario_bridge_non_sintetizza_presidio_documentale_lex_come_pec_generica(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        gestione = get_scadenziario()
        scadenza = gestione.nuova(
            "Deposito note scritte ex art. 127-ter c.p.c. - 09/07/2026 - RG 1754/2026",
            TipoTermine.ADEMPIMENTO,
            "2026-07-09",
            descrizione=(
                "Presidio documentale Lex AI: verificare il provvedimento e predisporre l'attività processuale rilevata. "
                "Ufficio: Tribunale di Palmi Giudice: TOSONI CLAUDIA RG: 1754/2026 "
                "Cliente: Mario Rossi Codex Parte/soggetto: INPS - Istituto Nazionale Previdenza Sociale."
            ),
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            source_event_type="fascicolo_documenti_audit",
            note="PEC_AUDIT:docpresidio:FASC:DOC:termine:2026-07-09\nTipo evento: fascicolo_documenti_audit",
        )

    response = client.get("/api/v1/ui/scadenziario?vista=tutte", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    row = next(item for item in payload["items"] if item["id"] == scadenza.id)

    assert response.status_code == 200
    assert row["title"].startswith("Deposito note scritte ex art. 127-ter c.p.c.")
    assert "Udienza da PEC" not in row["title"]
    assert row["sourceEventTypeLabel"] == "Deposito note scritte"
    assert "Mario Rossi Codex" in row["description"]
    assert "Tribunale di Palmi" in row["description"]
    assert "INPS - Istituto Nazionale Previdenza Sociale" in row["detailDescription"]
    assert row["sourceHref"] == "/fascicoli/FASC/documenti/DOC/visualizza"
    assert row["sourceKind"] == "documento"
    assert row["sourceVerified"] is True


def test_react_scadenziario_presidio_documentale_annullato_non_restera_adempimento_operativo(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        gestione = get_scadenziario()
        scadenza = gestione.nuova(
            "Attività processuale da presidiare - 31/08/2026 - RG 143/2026",
            TipoTermine.ADEMPIMENTO,
            "2026-08-31",
            descrizione=(
                "Presidio documentale Lex AI: verificare il provvedimento e predisporre "
                "l'attività processuale rilevata. Fonte documentale: Ricorso Zagari (originale notificato).pdf"
            ),
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            source_event_type="fascicolo_documenti_audit",
            note=(
                "PEC_AUDIT:docpresidio:FASC:DOC:termine:2026-08-31\n"
                "Tipo evento: fascicolo_documenti_audit\n"
                "Presidio documentale automatico annullato: la fonte non contiene un adempimento dell'ufficio. "
                "Motivo: atto_di_parte_non_genera_adempimento_automatico"
            ),
        )
        gestione.aggiorna(scadenza.id, stato=StatoTermine.ANNULLATO)

    response = client.get("/api/v1/ui/scadenziario?vista=tutte", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    row = next(item for item in payload["items"] if item["id"] == scadenza.id)
    visible = " ".join(str(row.get(key) or "") for key in ("title", "description", "detailDescription", "typeLabel", "sourceEventTypeLabel"))

    assert response.status_code == 200
    assert row["statusLabel"] == "Annullata"
    assert row["tone"] == "neutral"
    assert row["overdue"] is False
    assert row["title"] == "Presidio documentale annullato"
    assert row["typeLabel"] == "Presidio annullato"
    assert row["sourceEventTypeLabel"] == "Presidio documentale annullato"
    assert "atto di parte" in row["description"]
    assert "non viene trattata come scadenza operativa" in row["detailDescription"]
    assert "Attività processuale da presidiare" not in visible
    assert "Adempimento" not in visible
    assert row["sourceHref"] == "/fascicoli/FASC/documenti/DOC/visualizza"


def test_react_scadenziario_vista_pec_mostra_solo_scadenze_operative(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        gestione = get_scadenziario()
        legacy_futura = gestione.nuova(
            "Udienza da PEC operativa",
            TipoTermine.UDIENZA,
            (date.today() + timedelta(days=20)).isoformat(),
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            note="PEC_AUDIT:pec-futura-legacy",
        )
        futura = gestione.nuova(
            "VINCI ROSA MARIA - Udienza da remoto - RG 1754/2026",
            TipoTermine.UDIENZA,
            (date.today() + timedelta(days=20)).isoformat(),
            descrizione=(
                "Cliente: VINCI ROSA MARIA\n"
                "Parte/soggetto: Ricorrente principale: VINCI ROSA MARIA\n"
                "Ufficio: Tribunale di Milano\n"
                "Link udienza audiovisiva: da acquisire dal PDF allegato."
            ),
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            note="PEC_AUDIT:pec-futura",
        )
        scaduta = gestione.nuova(
            "VINCI ROSA MARIA - Udienza già superata - RG 1754/2026",
            TipoTermine.UDIENZA,
            (date.today() - timedelta(days=20)).isoformat(),
            descrizione=(
                "Cliente: VINCI ROSA MARIA\n"
                "Parte/soggetto: Ricorrente principale: VINCI ROSA MARIA\n"
                "Ufficio: Tribunale di Milano."
            ),
            deadline_profile_code="PEC_AUTO_PRESIDIO",
            note="PEC_AUDIT:pec-scaduta",
        )

    response = client.get("/api/v1/ui/scadenziario?vista=pec", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    ids = {item["id"] for item in payload["items"]}

    assert response.status_code == 200
    assert legacy_futura.id not in ids
    assert futura.id in ids
    assert scaduta.id not in ids
    assert payload["summary"]["pec"] == 1
    assert payload["summary"]["pec_future"] == 1
    assert payload["summary"]["pec_overdue"] >= 1


def test_react_scadenziario_calcolatore_non_ripete_template_identici():
    base = {
        "name": "Reclamo contro provvedimento cautelare",
        "matter_type": "civil",
        "base_value": 15,
        "period_type": "days",
        "direction": "forward",
        "suspend_august": True,
        "ferial_suspension_policy": "applies",
        "free_term": False,
        "urgent": False,
        "extend_saturday": True,
        "extend_holiday": True,
        "reference_law": "c.p.c. art. 669-terdecies",
        "cartabia_compliant": True,
        "metadata": {
            "source": "guida_pratica",
            "decorrenza": "Dalla comunicazione o notificazione del provvedimento",
            "natura": "termine di reclamo",
        },
        "version": 1,
    }
    templates = [
        {"code": "GP_A", **base, "metadata": {**base["metadata"], "codice_guida": "190010"}},
        {"code": "GP_B", **base, "metadata": {**base["metadata"], "codice_guida": "190020"}},
        {"code": "GP_C", **base, "base_value": 30},
    ]

    visible = dedupe_calculator_templates(templates)

    assert [template["code"] for template in visible] == ["GP_A", "GP_C"]
    assert len({template["displayName"] for template in visible}) == 2


def test_route_ufficiale_scadenziario_serve_react_con_vista_classica_tecnica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/scadenziario")
        classic = client.get("/scadenziario?_legacy=1")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in html
    assert 'id="root"' in html
    assert classic.status_code == 200
    assert 'id="root"' not in classic.get_data(as_text=True)
