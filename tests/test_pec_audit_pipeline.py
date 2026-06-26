from __future__ import annotations

import sqlite3
import zipfile
from datetime import date, timedelta
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
from pct.agenda import Agenda
from pct.calendar_sync_engine import CalendarSyncEngine, PRIVACY_REDUCED
from pct.email_client import EmailRicevuta, GestioneEmailRicevute, StatoEmail
from pct.pec_pipeline import (
    AttachmentPayload,
    PecAuditRepository,
    _extract_remote_hearing_links,
    _remote_hearing_deadline_extra,
    _remote_hearing_note_lines,
    _remote_hearing_updates_for_existing,
    build_pec_procedural_profile,
    build_deadline_proposal,
    build_pct_deposit_correlation,
    build_pct_deposit_lifecycle,
    build_validation_report,
    detect_pec_legal_context,
    detect_pct_deposit_stage,
    extract_text_with_coverage,
    ingest_synthetic_dataset,
    parse_pec_message,
    synthetic_pec_messages,
    verify_signature,
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


def _zip_pdf_with_clickable_room_link(link: str) -> bytes:
    from reportlab.pdfgen import canvas

    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer)
    pdf.drawString(72, 760, "Udienza con strumenti audiovisivi ore 11:00")
    pdf.drawString(72, 740, "Collegamento alla stanza virtuale: STANZA VIRTUALE DOTT. NICOLA TRITTA")
    pdf.linkURL(link, (72, 734, 410, 752), relative=0)
    pdf.save()
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("20200029s.pdf", pdf_buffer.getvalue())
    return zip_buffer.getvalue()


def _pct_esito_mime(subject: str, xml_text: str, *, message_id: str, when: str) -> bytes:
    msg = EmailMessage(policy=policy.SMTP)
    msg["Subject"] = subject
    msg["From"] = "cancelleria@giustiziapec.it"
    msg["To"] = "studio@example.pec.it"
    msg["Date"] = when
    msg["Message-ID"] = message_id
    msg.set_content(
        "\n".join(
            [
                subject,
                "Cliente: Mario Rossi",
                "Parte processuale: Mario Rossi",
                "Ufficio: Tribunale di Palmi",
                "RG: 1733/2026",
            ]
        )
    )
    msg.add_attachment(xml_text.encode("utf-8"), maintype="application", subtype="xml", filename="EsitoAtto.xml")
    msg.add_attachment(b"<postacert><tipo>avvenuta-consegna</tipo></postacert>", maintype="application", subtype="xml", filename="daticert.xml")
    return msg.as_bytes(policy=policy.SMTP)


def _gdp_hearing_message(*, hearing_date: str = "09/10/2026", hearing_time: str = "09:15", event: str = "FISSAZIONE UDIENZA") -> bytes:
    msg = EmailMessage()
    msg["From"] = "Giudice di Pace <gdp@example.test>"
    msg["To"] = "studio@example.test"
    msg["Subject"] = "POSTA CERTIFICATA: GIUDICE DI PACE Notificazione ai sensi del D.L. 179/2012"
    msg["Date"] = "Mon, 1 Jun 2026 12:00:00 +0200"
    msg["Message-ID"] = f"<gdp-hearing-{hearing_date.replace('/', '')}@iusentra.test>"
    msg.set_content(
        "Messaggio di posta certificata. I dati di cancelleria sono associati a: "
        f"Data Evento: 25/02/2026 Tipo Evento: EVENTI DI RINVIO Oggetto: {event} "
        f"Descrizione: UDIENZA RINVIATA AL {hearing_date} {hearing_time}."
    )
    xml = f"""
    <Comunicazione>
      <NumeroRuolo>777/2026</NumeroRuolo>
      <Oggetto>{event}</Oggetto>
      <Contenuto><![CDATA[
      Ufficio: GIUDICE DI PACE DI PALMI
      Numero di Ruolo generale: 777/2026
      Giudice: ROSSI MARIA
      Oggetto: {event}
      Descrizione: UDIENZA RINVIATA AL {hearing_date} {hearing_time}
      ]]></Contenuto>
    </Comunicazione>
    """.encode("utf-8")
    msg.add_attachment(xml, maintype="application", subtype="xml", filename="Comunicazione.xml")
    return msg.as_bytes(policy=policy.SMTP)


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


def test_pec_operational_matrix_rebuild_cleans_stale_queued_jobs(tmp_path):
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    _label, raw_mime = synthetic_pec_messages()[0]
    first = repo.ingest_mime(raw_mime, account_email="studio@example.test", folder="INBOX", imap_uid="1")

    first_run = repo.run_pending_jobs(limit=10, actor="pytest")
    assert first_run["failed"] == 0
    assert first_run["processed"] >= 5

    with repo.connect() as conn:
        repo.enqueue_job(conn, "classify", message_id=first["id"], priority=25, actor="pytest")
        repo.enqueue_job(conn, "ocr", message_id=first["id"], priority=30, actor="pytest")
        queued_before = conn.execute(
            "SELECT COUNT(*) FROM pec_jobs WHERE message_id=? AND status='queued'",
            (first["id"],),
        ).fetchone()[0]
    assert queued_before >= 2

    result = repo.enqueue_operational_matrix_rebuild(actor="pytest")

    assert result["queued"] == 1
    with repo.connect() as conn:
        rows = conn.execute(
            "SELECT job_type, status FROM pec_jobs WHERE message_id=? AND status='queued' ORDER BY priority",
            (first["id"],),
        ).fetchall()
    assert [(row["job_type"], row["status"]) for row in rows] == [("parse", "queued")]

    second_run = repo.run_pending_jobs(limit=10, actor="pytest")
    assert second_run["failed"] == 0
    assert [item["job_type"] for item in second_run["jobs"]] == ["parse", "classify", "ocr", "signcheck", "validate", "link"]


def test_pec_pipeline_recovers_stale_default_tenant_duplicate(tmp_path):
    db_path = tmp_path / "pec_audit.sqlite"
    _label, raw_mime = synthetic_pec_messages()[0]
    repo_default = PecAuditRepository(db_path, tenant_id="default")
    first = repo_default.ingest_mime(raw_mime, account_email="studio@example.test", folder="INBOX", imap_uid="1")

    repo_studio = PecAuditRepository(db_path, tenant_id="studio-legale-giuseppe-montagnese")
    duplicate = repo_studio.ingest_mime(raw_mime, account_email="studio@example.test", folder="INBOX", imap_uid="2")

    assert duplicate["duplicate"] is True
    assert duplicate["id"] == first["id"]
    with sqlite3.connect(db_path) as conn:
        tenant_id = conn.execute("SELECT tenant_id FROM pec_messages WHERE id=?", (first["id"],)).fetchone()[0]
    assert tenant_id == "studio-legale-giuseppe-montagnese"
    with repo_studio.connect() as conn:
        assert repo_studio.get_message_row(conn, first["id"])["id"] == first["id"]


def test_pec_pipeline_processes_jobs_for_stale_default_tenant_message(tmp_path):
    db_path = tmp_path / "pec_audit.sqlite"
    _label, raw_mime = synthetic_pec_messages()[0]
    repo_default = PecAuditRepository(db_path, tenant_id="default")
    first = repo_default.ingest_mime(raw_mime, account_email="studio@example.test", folder="INBOX", imap_uid="1")
    repo_studio = PecAuditRepository(db_path, tenant_id="studio-legale-giuseppe-montagnese")
    with repo_studio.connect() as conn:
        repo_studio.enqueue_job(conn, "parse", message_id=first["id"], priority=20, actor="pytest")

    result = repo_studio.run_pending_jobs(limit=5, actor="pytest")

    assert result["processed"] >= 1
    assert result["failed"] == 0
    assert any(item["message_id"] == first["id"] for item in result["jobs"])
    with sqlite3.connect(db_path) as conn:
        tenant_id = conn.execute("SELECT tenant_id FROM pec_messages WHERE id=?", (first["id"],)).fetchone()[0]
    assert tenant_id == "studio-legale-giuseppe-montagnese"


def test_pec_operational_audit_counts_latest_local_presidio_with_stale_message_tenant(tmp_path):
    from pct.email_client import CartellaEmail
    from scripts.audit_pec_operational_chain import audit_studio

    paths = {
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
        "NOTIFICATIONS_DB": str(tmp_path / "notifications" / "notifications.db"),
    }
    for value in paths.values():
        Path(value).parent.mkdir(parents=True, exist_ok=True)
    GestioneEmailRicevute(paths["EMAIL_CASELLA_DB"]).aggiungi(
        EmailRicevuta(
            id="MAIL-STORICA",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@example.test",
            destinatari="studio@example.pec.it",
            oggetto="POSTA CERTIFICATA: comunicazione di cancelleria",
            corpo_testo="Messaggio di posta certificata con comunicazione di cancelleria.",
            message_id="<mail-storica@example.test>",
            origine="PEC",
        )
    )
    repo = PecAuditRepository(tmp_path / "email" / "pec_audit.sqlite", tenant_id="studio-legale-giuseppe-montagnese")
    run = repo.start_local_acquire_run(total_emails=1, batch_size=1, actor="pytest")
    repo.record_local_acquire_item(
        str(run["id"]),
        email_id="MAIL-STORICA",
        message_id="pec_storica",
        subject="POSTA CERTIFICATA: comunicazione di cancelleria",
        status="ingested",
    )
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute(
            """
            INSERT INTO pec_messages
            (id, tenant_id, account_email, folder, imap_uid, message_id_header, mime_sha256, mime_size,
             original_mime, received_at, ingested_at, retention_until, metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "pec_storica",
                "default",
                "studio@example.pec.it",
                "INBOX",
                "1",
                "<mail-storica@example.test>",
                "0" * 64,
                1,
                sqlite3.Binary(b"x"),
                "2026-06-01T10:00:00Z",
                "2026-06-01T10:00:00Z",
                "2036-06-01",
                "{}",
            ),
        )

    audit = audit_studio(paths)

    assert audit["ok"] is True
    assert audit["pec_control"]["latest_local_status"]["by_email"]["ingested"] == 1


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
    assert profile["ufficio"] == "Tribunale di Brescia"
    assert profile["giudice"] == "ANGELI ISABELLA"
    assert profile["cliente"] == "MARRA VALENTINA"
    assert profile["cliente_da_verificare"] is True
    assert profile["parte_processuale"] == "MARRA VALENTINA"
    assert profile["ruolo_parte"] == "Ricorrente principale"
    assert profile["attore_principale"] == "MARRA VALENTINA"
    assert profile["convenuto_principale"] == "MINISTERO DELL'ISTRUZIONE E DEL MERITO"
    assert profile["parti_processuali"] == ["MARRA VALENTINA", "MINISTERO DELL'ISTRUZIONE E DEL MERITO"]
    assert profile["soggetti_parti"][0]["ruolo"] == "Ricorrente principale"
    assert profile["soggetti_parti"][1]["ruolo"] == "Resistente principale"
    assert profile["udienza_data_ora"] == "29/10/2026 09:15"
    assert profile["modalita_udienza"] == "strumenti audiovisivi"
    assert any("PDF" in item for item in profile["checklist_avvocato"])
    assert any("strumenti audiovisivi" in item for item in profile["domande_lex"])


def test_comunicazione_xml_separa_ricorrente_e_convenuto_sulla_stessa_riga():
    xml_text = """
    <Comunicazione>
      <NumeroRuolo>274/2026/CC</NumeroRuolo>
      <Oggetto>FISSAZIONE UDIENZA</Oggetto>
      <Contenuto><![CDATA[
      -- Comunicazione di cancelleria
      Numero di Ruolo generale: 274/2026
      Giudice: RUSCIO EMANUELA
      Ricorr. principale: LOPRETE DOMENICO Conv. principale: LAZZARO FILIPPO
      Oggetto: FISSAZIONE UDIENZA
      Descrizione: FISSATA UDIENZA IL 09/07/2026 09:30
      -- ]]></Contenuto>
      <CodiceUG>0800570092</CodiceUG>
    </Comunicazione>
    """

    profile = build_pec_procedural_profile(
        subject="POSTA CERTIFICATA: COMUNICAZIONE 274/2026/CC",
        body_text="",
        xml_texts={"Comunicazione.xml": xml_text},
        rg_candidates=[],
        sent_date="2026-05-08T14:22:04+02:00",
        delivery_date="2026-05-08T14:22:04+02:00",
        event_type="comunicazione_cancelleria",
        semantic_context={"office_hint": "Tribunale di Palmi"},
    )

    assert profile["cliente"] == "LOPRETE DOMENICO"
    assert profile["parte_processuale"] == "LOPRETE DOMENICO"
    assert profile["attore_principale"] == "LOPRETE DOMENICO"
    assert profile["convenuto_principale"] == "LAZZARO FILIPPO"
    assert profile["parti_processuali"] == ["LOPRETE DOMENICO", "LAZZARO FILIPPO"]
    assert profile["soggetti_parti"] == [
        {
            "ruolo": "Ricorrente principale",
            "nome": "LOPRETE DOMENICO",
            "valore": "LOPRETE DOMENICO",
            "fonte": "Comunicazione.xml: Ricorr. principale",
            "origine": "Comunicazione.xml: Ricorr. principale",
        },
        {
            "ruolo": "Convenuto principale",
            "nome": "LAZZARO FILIPPO",
            "valore": "LAZZARO FILIPPO",
            "fonte": "Comunicazione.xml: Conv. principale",
            "origine": "Comunicazione.xml: Conv. principale",
        },
    ]


def test_deadline_proposal_crea_udienza_da_profilo_processuale_se_manca_procedural_dates():
    hearing_day = date.today() + timedelta(days=20)
    hearing_text = hearing_day.strftime("%d/%m/%Y") + " 09:30"
    parsed = {
        "headers": {"subject": "POSTA CERTIFICATA: COMUNICAZIONE 274/2026/CC"},
        "fields": {"data_invio": {"value": date.today().isoformat()}},
        "body": {"text": "Comunicazione di cancelleria con udienza futura."},
        "procedural_dates": [],
        "procedural_profile": {
            "fase_pratica": "udienza o rinvio da calendarizzare",
            "ufficio": "Tribunale di Palmi",
            "giudice": "RUSCIO EMANUELA",
            "numero_rg": "274/2026",
            "cliente": "LOPRETE DOMENICO",
            "parte_processuale": "LOPRETE DOMENICO",
            "ruolo_parte": "Ricorrente principale",
            "oggetto_evento": "FISSAZIONE UDIENZA",
            "udienza_data_ora": hearing_text,
            "messaggio_operativo": (
                "udienza o rinvio da calendarizzare\n"
                "Ufficio: Tribunale di Palmi\n"
                "Giudice: RUSCIO EMANUELA\n"
                "RG: 274/2026\n"
                "Cliente: LOPRETE DOMENICO\n"
                "Parte/soggetto: LOPRETE DOMENICO (Ricorrente principale)\n"
                f"Udienza: {hearing_text}"
            ),
        },
    }

    proposal = build_deadline_proposal(
        parsed,
        event_type="ricevuta_pec",
        issues=[],
        deposit_lifecycle={},
    )

    assert proposal["auto_create"] is True
    assert proposal["deadline_kind"] == "udienza"
    assert proposal["calendar_scope"] == "agenda_and_scadenziario"
    assert proposal["due_date"] == hearing_day.isoformat()
    assert proposal["event_time"] == "09:30"
    assert "Cliente: LOPRETE DOMENICO" in proposal["reason"]


def test_comunicazione_xml_sentenza_espone_cliente_parti_e_ufficio_reale():
    xml_text = """
    <Comunicazione>
      <NumeroRuolo>1754/2026/LAV</NumeroRuolo>
      <Oggetto>SENTENZA EX ART. 429, I comma CPC</Oggetto>
      <Contenuto><![CDATA[
      --
      Comunicazione di cancelleria
      Sez/Coll.: LA
      Tipo procedimento: Diritto del Lavoro
      Numero di Ruolo generale: 1754/2026
      Giudice: TOSONI CLAUDIA
      Ricorr. principale: VINCI ROSA MARIA
      Resist. principale: MIM - MINISTERO ISTRUZIONE E DEL MERITO
      Oggetto: SENTENZA EX ART. 429, I comma CPC
      Descrizione: SENTENZA EX ART. 429, I comma CPC NUMERO 3271/2026 (Accoglimento totale)
      Note:
      Notificato alla PEC / in cancelleria il 19/06/2026 10:51
      Registrato da CAMPILONGO ALESSANDRO (SEZ LAVORO)
      --
      ]]></Contenuto>
      <CodiceUG>0151460094</CodiceUG>
      <CodiceFiscaleDestinatario>MNTGPP94L01G791A</CodiceFiscaleDestinatario>
    </Comunicazione>
    """

    profile = build_pec_procedural_profile(
        subject="POSTA CERTIFICATA: COMUNICAZIONE DI CANCELLERIA",
        body_text="",
        xml_texts={"Comunicazione.xml": xml_text},
        rg_candidates=[],
        sent_date="2026-06-19T10:51:00+02:00",
        delivery_date="2026-06-19T10:51:00+02:00",
        event_type="comunicazione_cancelleria",
        semantic_context={"office_hint": "Ufficio giudiziario civile"},
    )

    assert profile["fase_pratica"] == "provvedimento/sentenza da leggere e notificare o presidiare"
    assert profile["numero_rg"] == "1754/2026"
    assert profile["ufficio"] == "Tribunale di Milano"
    assert profile["ufficio_risolto_da_codice"] is True
    assert profile["giudice"] == "TOSONI CLAUDIA"
    assert profile["cliente"] == "VINCI ROSA MARIA"
    assert profile["cliente_da_verificare"] is True
    assert profile["parte_processuale"] == "VINCI ROSA MARIA"
    assert profile["ruolo_parte"] == "Ricorrente principale"
    assert profile["parti_processuali"] == ["VINCI ROSA MARIA", "MIM - MINISTERO ISTRUZIONE E DEL MERITO"]
    assert profile["soggetti_parti"] == [
        {
            "ruolo": "Ricorrente principale",
            "nome": "VINCI ROSA MARIA",
            "valore": "VINCI ROSA MARIA",
            "fonte": "Comunicazione.xml: Ricorr. principale",
            "origine": "Comunicazione.xml: Ricorr. principale",
        },
        {
            "ruolo": "Resistente principale",
            "nome": "MIM - MINISTERO ISTRUZIONE E DEL MERITO",
            "valore": "MIM - MINISTERO ISTRUZIONE E DEL MERITO",
            "fonte": "Comunicazione.xml: Resist. principale",
            "origine": "Comunicazione.xml: Resist. principale",
        },
    ]
    assert "Cliente: VINCI ROSA MARIA" in profile["messaggio_operativo"]
    assert "Parte/soggetto: VINCI ROSA MARIA (Ricorrente principale)" in profile["messaggio_operativo"]
    assert any("Leggere la sentenza o il provvedimento" in item for item in profile["checklist_avvocato"])


def test_legacy_pec_scadenze_e_agenda_filtrate_senza_rimuovere_nuova_matrice():
    from pct.pec_operational_cleanup import is_legacy_pec_agenda_item, is_legacy_pec_deadline

    old_deadline = SimpleNamespace(
        titolo="Ricevuta protocollo",
        descrizione="Sono presenti anomalie non bloccanti: il software registra un promemoria operativo per chiuderle.",
        note="PEC_AUDIT: msg-1\nEvento: Ricevuta Pec",
        deadline_profile_code="PEC_AUTO_PRESIDIO",
        source_event_type="pct_deposito",
    )
    old_agenda = SimpleNamespace(
        titolo="Udienza da PEC: fissazione udienza - RG 3001/2025",
        note="Udienza rilevata da PEC. Fascicolo RG 3001/2025. Verificare provvedimento, fascicolo e attività collegate.",
        external_uid="PEC_AUDIT:msg-2:hearing",
        external_provider="pec_audit",
    )
    new_deadline = SimpleNamespace(
        titolo="VINCI ROSA MARIA - SENTENZA EX ART. 429, I comma CPC - RG 1754/2026",
        descrizione=(
            "Cliente: VINCI ROSA MARIA\n"
            "Parte/soggetto: Ricorrente principale: VINCI ROSA MARIA\n"
            "Ufficio: Tribunale di Milano\n"
            "Giudice: TOSONI CLAUDIA\n"
            "Operatività: leggere la sentenza e valutare notifica, impugnazione o comunicazione al cliente."
        ),
        note="PEC_AUDIT: msg-3\npresidio documentale Lex",
        deadline_profile_code="PEC_PROVVEDIMENTO",
        source_event_type="comunicazione_cancelleria",
    )
    new_agenda = SimpleNamespace(
        titolo="Udienza VINCI ROSA MARIA - RG 1754/2026",
        note="Cliente: VINCI ROSA MARIA\nParte/soggetto: Ricorrente principale: VINCI ROSA MARIA\nLink udienza audiovisiva: da acquisire dal PDF allegato.",
        external_uid="PEC_AUDIT:msg-4:hearing",
        external_provider="pec_audit",
    )

    assert is_legacy_pec_deadline(old_deadline) is True
    assert is_legacy_pec_agenda_item(old_agenda) is True
    assert is_legacy_pec_deadline(new_deadline) is False
    assert is_legacy_pec_agenda_item(new_agenda) is False


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


def test_remote_hearing_report_excludes_technical_pst_dtd_ocsp_links():
    text = """
    Udienza da remoto con strumenti audiovisivi.
    http://pst.giustizia.it/
    http://schemi.processotelematico.giustizia.it/Schemi/Comunicazione.dtd
    http://ca1.agid.gov.it/OCSP0
    Collegamento udienza: https://teams.microsoft.com/l/meetup-join/vera-stanza
    """

    links = _extract_remote_hearing_links(text)

    urls = [item["url"] for item in links]
    assert urls == ["https://teams.microsoft.com/l/meetup-join/vera-stanza"]
    assert "pst.giustizia.it" not in " ".join(urls)
    assert "Comunicazione.dtd" not in " ".join(urls)
    assert "OCSP0" not in " ".join(urls)


def test_remote_hearing_extracts_full_teams_launcher_url_without_truncation():
    launcher_link = (
        "https://teams.microsoft.com/dl/launcher/launcher.html?"
        "url=%2F_%23%2Fl%2Fmeetup-join%2F19%3Ameeting_TEST%40thread.v2%2F0"
        "%3Fcontext%3D%257b%2522Tid%2522%253a%252211111111-1111-1111-1111-111111111111"
        "%2522%252c%2522Oid%2522%253a%252222222222-2222-2222-2222-222222222222%2522%257d"
        "%26anon%3Dtrue&type=meetup-join&deeplinkId=33333333-3333-3333-3333-333333333333"
        "&directDl=true&msLaunch=true&enableMobilePage=true&suppressPrompt=true"
    )
    text = f"Udienza audiovisiva. Collegamento per la connessione: {launcher_link}"

    links = _extract_remote_hearing_links(text)

    assert [item["url"] for item in links] == [launcher_link]
    assert links[0]["integrity"] == "exact"


def test_remote_hearing_rebuilds_teams_url_split_by_pdf_ocr_spaces():
    expected_link = (
        "https://teams.microsoft.com/l/meetup-join/"
        "19%3ameeting_ZmFiOGJmMzgtNDI1OS00YTI0LTkzZmEtNDhjZTZhNTc0NzNi%40thread.v2/0"
        "?context=%7b%22Tid%22%3a%22792bc8b1-9088-4858-b830-2aad443e9f3f%22"
        "%2c%22Oid%22%3a%228df10bb4-001b-4015-9737-15476113e02a%22%7d"
    )
    text = (
        "udienza in modalità da remoto mediante collegamento delle parti al link: "
        "https://teams.microsoft.com/l/meetup- join/"
        "19%3ameeting_ZmFiOGJmMzgtNDI1OS00YTI0LTkzZmEtNDhjZTZhNTc0NzNi%40thr "
        "ead.v2/0?context=%7b%22Tid%22%3a%22792bc8b1-9088-4858-b830- "
        "2aad443e9f3f%22%2c%22Oid%22%3a%228df10bb4-001b-4015-9737- "
        "15476113e02a%22%7d. Manda al ricorrente di notificare ricorso."
    )

    links = _extract_remote_hearing_links(text)

    assert [item["url"] for item in links] == [expected_link]
    assert links[0]["exact"] is False
    assert links[0]["integrity"] == "ricostruito_da_controllare"
    assert "rimossi spazi OCR interni al link" in links[0]["normalization_note"]
    assert "rimossa punteggiatura finale" in links[0]["normalization_note"]


def test_remote_hearing_profile_reads_pdf_zip_even_if_misclassified_as_daticert():
    text = (
        "Udienza fissata in modalita da remoto mediante collegamento delle parti al link: "
        "https://teams.microsoft.com/l/meetup- join/"
        "19%3ameeting_ZmFiOGJmMzgtNDI1OS00YTI0LTkzZmEtNDhjZTZhNTc0NzNi%40thr "
        "ead.v2/0?context=%7b%22Tid%22%3a%22792bc8b1-9088-4858-b830- "
        "2aad443e9f3f%22%2c%22Oid%22%3a%228df10bb4-001b-4015-9737- "
        "15476113e02a%22%7d."
    )
    report = build_validation_report(
        {
            "headers": {"subject": "POSTA CERTIFICATA: COMUNICAZIONE 1263/2026/LAV"},
            "body": {"text": "FISSATA UDIENZA DI DISCUSSIONE IL 29/10/2026 09:15 con strumenti audiovisivi"},
        },
        [
            {
                "filename": "13744017s.pdf.zip",
                "content_type": "application/zip",
                "classification": "daticert",
                "ocr_text": text,
            }
        ],
    )

    remote = report["procedural_profile"]["remote_hearing"]

    assert remote["pdf_required"] is False
    assert remote["links"][0]["source"] == "13744017s.pdf.zip"
    assert remote["links"][0]["url"].startswith("https://teams.microsoft.com/l/meetup-join/")
    assert remote["links"][0]["exact_match"] is False


def test_remote_hearing_report_excludes_technical_signature_and_invoice_urls():
    text = """
    Udienza da remoto con strumenti audiovisivi.
    http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fattura/messaggi/v1.0
    http://www.w3.org/2000/09/xmldsig#
    http://uri.etsi.org/01903/v1.3.2#
    http://cacert.actalis.it/certs/actalis-autroot01
    Collegamento udienza: https://teams.microsoft.com/l/meetup-join/vera-stanza
    """

    links = _extract_remote_hearing_links(text)

    assert [item["url"] for item in links] == ["https://teams.microsoft.com/l/meetup-join/vera-stanza"]


def test_sentenza_a_verbale_127_ter_non_diventa_udienza_audiovisiva():
    parsed = {
        "headers": {"subject": "POSTA CERTIFICATA: COMUNICAZIONE 1821/2024/LAV"},
        "body": {"text": "Comunicazione di cancelleria con sentenza allegata."},
        "fields": {},
        "semantic_context": {"event_hint": "comunicazione_cancelleria", "agent_questions": [], "recommended_actions": []},
        "procedural_profile": {
            "numero_rg": "1821/2024",
            "oggetto_evento": "SENTENZA A VERBALE (art. 127 ter cpc)",
            "descrizione_evento": "SENTENZA A VERBALE (art. 127 ter cpc) CON NUMERO 922/2026",
            "giudice": "SICARI FRANCESCA PATRIZIA",
        },
    }
    attachments = [
        {
            "filename": "1300478s.pdf.zip",
            "content_type": "application/zip",
            "classification": "atto",
            "ocr_text": (
                "TRIBUNALE DI REGGIO CALABRIA SENTENZA. "
                "Note scritte ai sensi dell'art. 127-ter cpc depositate in sostituzione dell'udienza del 4.6.2026."
            ),
            "ocr_coverage": 0.91,
            "signature_status": "non_applicabile",
        },
        {
            "filename": "smime.p7s",
            "content_type": "application/pkcs7-signature",
            "classification": "firma",
            "ocr_text": "http://ca1.agid.gov.it/OCSP0 http://www.w3.org/2000/09/xmldsig#",
            "ocr_coverage": 0.2,
            "signature_status": "valida",
        },
    ]

    report = build_validation_report(parsed, attachments)

    assert report["remote_hearing"] == {}
    assert "remote_hearing" not in report["procedural_profile"]
    assert not any(issue["code"].startswith("remote_hearing") for issue in report["issues"])


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


def test_extract_text_with_coverage_reads_clickable_pdf_link_inside_zip():
    exact_link = "https://teams.microsoft.com/l/meetup-join/torino-3950?context=%7B%22Tid%22%3A%22abc%22%7D"

    text, coverage = extract_text_with_coverage(
        AttachmentPayload(
            index=1,
            filename="20200029s.pdf.zip",
            content_type="application/zip",
            data=_zip_pdf_with_clickable_room_link(exact_link),
        )
    )

    assert coverage > 0
    assert "20200029s.pdf" in text
    assert "STANZA VIRTUALE DOTT. NICOLA TRITTA" in text
    assert exact_link in text


def test_extract_text_with_coverage_skips_pcten_mislabeled_pdf():
    text, coverage = extract_text_with_coverage(
        AttachmentPayload(
            index=1,
            filename="Atto.pdf",
            content_type="application/pdf",
            data=b"PCTENCRYPTED-PAYLOAD-NOT-A-PDF" + (b"\x00" * 200),
        )
    )

    assert text == ""
    assert coverage == 0.0


def test_extract_text_with_coverage_pdf_usa_adapter_ocr_pipeline(monkeypatch):
    calls: list[tuple[bytes, str]] = []

    def fake_estrai_testo(data: bytes, nome_file: str, lang: str = "ita") -> str:
        calls.append((bytes(data), nome_file))
        return "Testo letto dalla pipeline OCR DocumentAI."

    monkeypatch.setattr("pct.ocr.estrai_testo", fake_estrai_testo)

    text, coverage = extract_text_with_coverage(
        AttachmentPayload(
            index=1,
            filename="Atto.pdf",
            content_type="application/pdf",
            data=b"%PDF-1.7\nfake-pdf-for-ocr-adapter\n%%EOF",
        )
    )

    assert calls == [(b"%PDF-1.7\nfake-pdf-for-ocr-adapter\n%%EOF", "Atto.pdf")]
    assert "pipeline OCR DocumentAI" in text
    assert coverage > 0


def test_verify_signature_skips_pcten_mislabeled_pdf():
    status, details = verify_signature(
        AttachmentPayload(
            index=1,
            filename="Atto.pdf",
            content_type="application/pdf",
            data=b"PCTENCRYPTED-PAYLOAD-NOT-A-PDF",
        )
    )

    assert status == "non_applicabile"
    assert details["checks"][0]["detail"] == "contenuto non PDF"


def test_verify_signature_skips_non_cades_pdf_p7m_without_pdf_probe():
    status, details = verify_signature(
        AttachmentPayload(
            index=1,
            filename="Atto.pdf.p7m",
            content_type="application/pkcs7-mime",
            data=b"PCTENCRYPTED-PAYLOAD-NOT-A-CADES",
        )
    )

    assert status == "non_applicabile"
    assert details["checks"][0]["name"] == "CAdES"
    assert details["checks"][0]["detail"] == "contenuto non CAdES/PKCS#7"


def test_validation_report_deduplica_testi_operativi_ripetuti():
    parsed = {
        "semantic_context": {
            "agent_questions": ["Verificare ricevute e fascicolo", "Verificare ricevute e fascicolo"],
            "recommended_actions": ["Aggiornare il fascicolo", "Aggiornare il fascicolo"],
        },
        "procedural_profile": {
            "domande_lex": ["Verificare ricevute e fascicolo"],
            "checklist_avvocato": ["Aggiornare il fascicolo"],
        },
    }

    report = build_validation_report(parsed, [])

    assert report["agent_questions"].count("Verificare ricevute e fascicolo") == 1
    assert report["recommended_actions"].count("Aggiornare il fascicolo") == 1


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


def test_refresh_validation_reports_repairs_stale_binary_zip_ocr_for_remote_hearing(tmp_path):
    exact_link = "https://teams.microsoft.com/l/meetup-join/udienza-1263?context=%7B%22Tid%22%3A%22123%22%7D&anon=true"
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    msg = EmailMessage()
    msg["Subject"] = "FISSAZIONE UDIENZA DI DISCUSSIONE"
    msg["From"] = "Cancelleria <cancelleria@pec.example.test>"
    msg["To"] = "studio@example.test"
    msg["Date"] = "Tue, 26 May 2026 15:09:00 +0200"
    msg["Message-ID"] = "<udienza-stale-zip-ocr@example.test>"
    msg.set_content("Comunicazione di cancelleria: udienza con strumenti audiovisivi. Il link è nel PDF allegato.")
    msg.add_attachment(_zip_pdf_with_link(exact_link), maintype="application", subtype="zip", filename="13744017s.pdf.zip")
    ingest = repo.ingest_mime(msg.as_bytes(policy=policy.SMTP), account_email="studio@example.test", folder="INBOX", imap_uid="uid-stale-zip")
    repo.run_pending_jobs(limit=30, actor="pytest")

    with repo.connect() as conn:
        parsed_row = repo.latest_parsed_row(conn, ingest["id"])
        assert parsed_row is not None
        conn.execute(
            """
            UPDATE pec_attachments
            SET ocr_text=?, ocr_coverage=?
            WHERE message_id=? AND filename=?
            """,
            ("PK\x03\x04 testo binario zip 13744017s.pdf non leggibile " * 20, 0.92, ingest["id"], "13744017s.pdf.zip"),
        )
        assert len(repo._stale_zip_ocr_rows(conn, ingest["id"], str(parsed_row["id"]))) == 1

    queued = repo.enqueue_missing_operational_jobs(ingest["id"], actor="pytest")
    refreshed = repo.refresh_validation_reports(actor="pytest")
    detail = repo.get_message_detail(ingest["id"])
    remote = detail["validation_report"]["procedural_profile"]["remote_hearing"]
    zip_row = next(item for item in detail["attachments"] if item["filename"] == "13744017s.pdf.zip")

    assert queued["stage"] == "ocr_stale_zip"
    assert refreshed["ok"] is True
    assert remote["links"][0]["url"] == exact_link
    assert remote["links"][0]["source"] == "13744017s.pdf.zip"
    assert remote["links"][0]["exact_match"] is True
    assert not zip_row["ocr_text"].startswith("PK")
    assert exact_link in zip_row["ocr_text"]


def test_pec_remote_hearing_link_arrives_in_scadenziario_and_agenda(tmp_path):
    from pct.agenda import Agenda
    from pct.scadenziario import GestioneScadenziario, TipoTermine

    exact_link = "https://teams.microsoft.com/l/meetup-join/udienza-1263?context=%7B%22Tid%22%3A%22123%22%7D"
    scadenziario_db = tmp_path / "scadenziario" / "scadenze.json"
    agenda_db = tmp_path / "agenda" / "appuntamenti.json"
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        scadenziario_db_path=scadenziario_db,
        agenda_db_path=agenda_db,
    )
    msg = EmailMessage()
    msg["Subject"] = "FISSAZIONE UDIENZA DI DISCUSSIONE"
    msg["From"] = "Cancelleria <cancelleria@pec.example.test>"
    msg["To"] = "studio@example.test"
    msg["Date"] = "Tue, 26 May 2026 15:09:00 +0200"
    msg["Message-ID"] = "<udienza-audiovisiva-scadenziario@example.test>"
    msg.set_content("Comunicazione di cancelleria: udienza con strumenti audiovisivi. Il link è nel PDF allegato.")
    msg.add_attachment(
        """
        <Comunicazione>
          <NumeroRuolo>1263/2026/LAV</NumeroRuolo>
          <Oggetto>FISSAZIONE UDIENZA DI DISCUSSIONE</Oggetto>
          <Contenuto><![CDATA[
          Descrizione: FISSATA UDIENZA DI DISCUSSIONE IL 29/10/2026 09:15 con strumenti audiovisivi
          ]]></Contenuto>
        </Comunicazione>
        """.encode("utf-8"),
        maintype="application",
        subtype="xml",
        filename="Comunicazione.xml",
    )
    msg.add_attachment(_zip_pdf_with_link(exact_link), maintype="application", subtype="zip", filename="13744017s.pdf.zip")

    ingest = repo.ingest_mime(msg.as_bytes(policy=policy.SMTP), account_email="studio@example.test", folder="INBOX", imap_uid="uid-link")
    repo.run_pending_jobs(limit=30, actor="pytest")
    scheduled = repo.schedule_deadline(ingest["id"], actor="pytest")

    assert scheduled["ok"] is True
    scadenze = GestioneScadenziario(str(scadenziario_db)).tutte(solo_aperte=False)
    assert len(scadenze) == 1
    assert scadenze[0].tipo == TipoTermine.UDIENZA
    assert scadenze[0].remote_hearing_url == exact_link
    assert scadenze[0].remote_hearing_source == "13744017s.pdf.zip"
    assert scadenze[0].remote_hearing_verified is True
    assert "Link udienza audiovisiva" in scadenze[0].note
    agenda = Agenda(str(agenda_db))
    agenda_items = agenda.tutti()
    assert len(agenda_items) == 1
    assert exact_link in agenda_items[0].note
    assert agenda_items[0].luogo == "Udienza da remoto"


def test_pec_remote_hearing_clickable_pdf_link_arrives_in_scadenziario_and_agenda(tmp_path):
    from pct.agenda import Agenda, TipoAppuntamento
    from pct.scadenziario import GestioneScadenziario

    exact_link = "https://teams.microsoft.com/l/meetup-join/torino-3950?context=%7B%22Tid%22%3A%22abc%22%7D"
    scadenziario_db = tmp_path / "scadenziario" / "scadenze.json"
    agenda_db = tmp_path / "agenda" / "appuntamenti.json"
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        scadenziario_db_path=scadenziario_db,
        agenda_db_path=agenda_db,
    )
    msg = EmailMessage()
    msg["Subject"] = "POSTA CERTIFICATA: COMUNICAZIONE 3950/2026/LAV"
    msg["From"] = "Cancelleria <cancelleria@pec.example.test>"
    msg["To"] = "studio@example.test"
    msg["Date"] = "Wed, 27 May 2026 12:01:37 +0200"
    msg["Message-ID"] = "<udienza-audiovisiva-clickable-scadenziario@example.test>"
    msg.set_content("Comunicazione di cancelleria: udienza con strumenti audiovisivi. Il link è nel PDF allegato.")
    msg.add_attachment(
        """
        <Comunicazione>
          <NumeroRuolo>3950/2026/LAV</NumeroRuolo>
          <Oggetto>FISSAZIONE UDIENZA DI DISCUSSIONE</Oggetto>
          <Contenuto><![CDATA[
          Descrizione: FISSATA UDIENZA DI DISCUSSIONE IL 13/01/2027 11:00 con strumenti audiovisivi
          ]]></Contenuto>
        </Comunicazione>
        """.encode("utf-8"),
        maintype="application",
        subtype="xml",
        filename="Comunicazione.xml",
    )
    msg.add_attachment(_zip_pdf_with_clickable_room_link(exact_link), maintype="application", subtype="zip", filename="20200029s.pdf.zip")

    ingest = repo.ingest_mime(msg.as_bytes(policy=policy.SMTP), account_email="studio@example.test", folder="INBOX", imap_uid="uid-clickable-link")
    repo.run_pending_jobs(limit=30, actor="pytest")
    scheduled = repo.schedule_deadline(ingest["id"], actor="pytest")

    assert scheduled["ok"] is True
    scadenze = GestioneScadenziario(str(scadenziario_db)).tutte(solo_aperte=False)
    assert len(scadenze) == 1
    assert scadenze[0].remote_hearing_url == exact_link
    assert scadenze[0].remote_hearing_pdf_required is False
    assert "Link udienza audiovisiva: da acquisire" not in scadenze[0].note
    assert exact_link in scadenze[0].note
    agenda = Agenda(str(agenda_db))
    agenda_items = agenda.tutti()
    assert len(agenda_items) == 1
    assert exact_link in agenda_items[0].note
    assert agenda_items[0].luogo == "Udienza da remoto"

    agenda.aggiungi(
        titolo=f"Presidio PEC - {scadenze[0].titolo}",
        tipo=TipoAppuntamento.SCADENZA,
        data_ora="2027-01-13T09:00:00",
        durata_minuti=30,
        luogo="Agenda studio",
        allow_overlap=True,
        note=f"PEC_AUDIT:{ingest['id']}\nLink udienza audiovisiva: da acquisire dal PDF allegato.",
        external_source_url=f"/api/pec/messages/{ingest['id']}",
    )

    enriched = repo.enrich_deadlines_with_remote_hearing_links(actor="pytest")

    assert enriched["agenda_updated"] >= 1
    synced_items = [item for item in Agenda(str(agenda_db)).tutti() if ingest["id"] in item.note or item.external_source_url.endswith(ingest["id"])]
    assert len(synced_items) == 1
    assert all(exact_link in item.note for item in synced_items)
    assert all("da acquisire" not in item.note.lower() for item in synced_items)
    assert all(item.luogo == "Udienza da remoto" for item in synced_items)


def test_remote_hearing_existing_deadline_note_replaces_pdf_pending_marker():
    exact_link = "https://teams.microsoft.com/l/meetup-join/torino-3950?context=%7B%22Tid%22%3A%22abc%22%7D"
    report = build_validation_report(
        {
            "headers": {"subject": "POSTA CERTIFICATA: COMUNICAZIONE 3950/2026/LAV"},
            "body": {"text": "FISSATA UDIENZA DI DISCUSSIONE IL 13/01/2027 11:00 con strumenti audiovisivi"},
        },
        [
            {
                "filename": "20200029s.pdf.zip",
                "content_type": "application/zip",
                "classification": "daticert",
                "ocr_text": f"Link PDF cliccabile: {exact_link}",
            }
        ],
    )
    proposal = report["deadline_proposal"]
    existing = SimpleNamespace(
        note=(
            "PEC_AUDIT:pec_d7fae2948d6434cc67254b37\n"
            "Udienza da remoto: audiovisiva\n"
            "Orario collegamento: 13/01/2027 ore 11:00\n"
            "Link udienza audiovisiva: da acquisire dal PDF allegato.\n"
            "Fonte: pipeline PEC audit-grade."
        ),
        remote_hearing_pdf_required=True,
        remote_hearing_url="",
        remote_hearing_source="",
        remote_hearing_verified=False,
        remote_hearing_integrity="",
        tipo="ADEMPIMENTO",
    )

    updates = _remote_hearing_updates_for_existing(
        existing,
        _remote_hearing_deadline_extra(report, proposal),
        _remote_hearing_note_lines(report, proposal),
    )

    assert updates["remote_hearing_url"] == exact_link
    assert updates["remote_hearing_pdf_required"] is False
    assert exact_link in updates["note"]
    assert "da acquisire" not in updates["note"].lower()
    assert updates["note"].count("Link udienza audiovisiva:") == 1


def test_refresh_validation_reports_repairs_clickable_pdf_link_for_existing_remote_hearing(tmp_path):
    exact_link = "https://teams.microsoft.com/l/meetup-join/torino-3950?context=%7B%22Tid%22%3A%22abc%22%7D"
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    msg = EmailMessage()
    msg["Subject"] = "POSTA CERTIFICATA: COMUNICAZIONE 3950/2026/LAV"
    msg["From"] = "Cancelleria <cancelleria@pec.example.test>"
    msg["To"] = "studio@example.test"
    msg["Date"] = "Wed, 27 May 2026 12:01:37 +0200"
    msg["Message-ID"] = "<udienza-audiovisiva-clickable-refresh@example.test>"
    msg.set_content("Comunicazione di cancelleria: udienza con strumenti audiovisivi. Il link è nel PDF allegato.")
    msg.add_attachment(
        """
        <Comunicazione>
          <NumeroRuolo>3950/2026/LAV</NumeroRuolo>
          <Oggetto>FISSAZIONE UDIENZA DI DISCUSSIONE</Oggetto>
          <Contenuto><![CDATA[
          Descrizione: FISSATA UDIENZA DI DISCUSSIONE IL 13/01/2027 11:00 con strumenti audiovisivi
          ]]></Contenuto>
        </Comunicazione>
        """.encode("utf-8"),
        maintype="application",
        subtype="xml",
        filename="Comunicazione.xml",
    )
    msg.add_attachment(_zip_pdf_with_clickable_room_link(exact_link), maintype="application", subtype="zip", filename="20200029s.pdf.zip")
    ingest = repo.ingest_mime(msg.as_bytes(policy=policy.SMTP), account_email="studio@example.test", folder="INBOX", imap_uid="uid-clickable-refresh")
    repo.run_pending_jobs(limit=30, actor="pytest")

    with repo.connect() as conn:
        parsed_row = repo.latest_parsed_row(conn, ingest["id"])
        assert parsed_row is not None
        conn.execute(
            """
            UPDATE pec_attachments
            SET ocr_text=?, ocr_coverage=?
            WHERE message_id=? AND filename=?
            """,
            (
                "RGL n. 3950/2026. Udienza con strumenti audiovisivi. "
                "Collegamento alla stanza virtuale: STANZA VIRTUALE DOTT. NICOLA TRITTA.",
                0.5,
                ingest["id"],
                "20200029s.pdf.zip",
            ),
        )
        stale_report = {
            "event_type": "comunicazione_cancelleria",
            "severity": "warning",
            "procedural_profile": {
                "remote_hearing": {
                    "detected": True,
                    "mode": "audiovisiva",
                    "pdf_required": True,
                    "pdf_sources": ["20200029s.pdf.zip"],
                }
            },
            "remote_hearing": {
                "detected": True,
                "mode": "audiovisiva",
                "pdf_required": True,
                "pdf_sources": ["20200029s.pdf.zip"],
            },
            "deadline_proposal": {
                "auto_create": True,
                "due_date": "2027-01-13",
                "title": "Fissazione udienza di discussione - 13/01/2027 - RG 3950/2026",
                "remote_hearing": {
                    "detected": True,
                    "mode": "audiovisiva",
                    "pdf_required": True,
                    "pdf_sources": ["20200029s.pdf.zip"],
                },
            },
        }
        repo._insert_validation_report(
            conn,
            message_id=ingest["id"],
            parsed_version_id=str(parsed_row["id"]),
            report=stale_report,
            actor="pytest",
        )
        assert repo.latest_report(conn, ingest["id"])["remote_hearing"]["pdf_required"] is True

    refreshed = repo.refresh_validation_reports(actor="pytest")

    assert refreshed["ok"] is True
    detail = repo.get_message_detail(ingest["id"])
    remote = detail["validation_report"]["procedural_profile"]["remote_hearing"]
    assert remote["pdf_required"] is False
    assert remote["links"][0]["url"] == exact_link
    zip_row = next(item for item in detail["attachments"] if item["filename"] == "20200029s.pdf.zip")
    assert exact_link in zip_row["ocr_text"]


def test_refresh_validation_reports_rewrites_stale_remote_hearing_report(tmp_path):
    exact_link = "https://teams.microsoft.com/l/meetup-join/udienza-1263"
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    msg = EmailMessage()
    msg["Subject"] = "FISSAZIONE UDIENZA DI DISCUSSIONE"
    msg["From"] = "Cancelleria <cancelleria@pec.example.test>"
    msg["To"] = "studio@example.test"
    msg["Date"] = "Tue, 26 May 2026 15:09:00 +0200"
    msg["Message-ID"] = "<udienza-refresh@example.test>"
    msg.set_content("Udienza con strumenti audiovisivi. Link nel PDF.")
    msg.add_attachment(_zip_pdf_with_link(exact_link), maintype="application", subtype="zip", filename="13744017s.pdf.zip")
    ingest = repo.ingest_mime(msg.as_bytes(policy=policy.SMTP), account_email="studio@example.test", folder="INBOX", imap_uid="uid-refresh")
    repo.run_pending_jobs(limit=30, actor="pytest")

    with repo.connect() as conn:
        parsed_row = repo.latest_parsed_row(conn, ingest["id"])
        assert parsed_row is not None
        stale = {
            "event_type": "comunicazione_cancelleria",
            "severity": "warning",
            "issues": [],
            "procedural_profile": {
                "remote_hearing": {
                    "detected": True,
                    "links": [{"url": "http://pst.giustizia.it/", "source": "Corpo PEC", "exact_match": True}],
                }
            },
            "remote_hearing": {
                "detected": True,
                "links": [{"url": "http://pst.giustizia.it/", "source": "Corpo PEC", "exact_match": True}],
            },
            "deadline_proposal": {"auto_create": False, "remote_hearing": {}},
        }
        repo._insert_validation_report(
            conn,
            message_id=ingest["id"],
            parsed_version_id=str(parsed_row["id"]),
            report=stale,
            actor="pytest",
        )
        assert repo.latest_report(conn, ingest["id"])["remote_hearing"]["links"][0]["url"] == "http://pst.giustizia.it/"

    refreshed = repo.refresh_validation_reports(actor="pytest")

    assert refreshed["ok"] is True
    assert refreshed["updated"] == 1
    detail = repo.get_message_detail(ingest["id"])
    refreshed_remote = detail["validation_report"]["procedural_profile"]["remote_hearing"]
    assert refreshed_remote["links"][0]["url"] == exact_link
    assert all("pst.giustizia.it" not in item["url"] for item in refreshed_remote["links"])


def test_giudice_di_pace_hearing_creates_real_hearing_not_generic_notice(tmp_path):
    from pct.agenda import Agenda
    from pct.scadenziario import GestioneScadenziario, TipoTermine

    scadenziario_db = tmp_path / "scadenze.json"
    agenda_db = tmp_path / "agenda.json"
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        scadenziario_db_path=scadenziario_db,
        agenda_db_path=agenda_db,
    )

    ingest = repo.ingest_mime(_gdp_hearing_message(), account_email="studio@example.test", folder="INBOX", imap_uid="gdp-hearing")
    repo.run_pending_jobs(limit=30, actor="codex-test")
    scheduled = repo.schedule_deadline(ingest["id"], actor="codex-test")

    assert scheduled["ok"] is True
    assert scheduled["due_date"] == "2026-10-09"
    assert scheduled["proposal"]["deadline_kind"] == "udienza"
    scadenze = GestioneScadenziario(str(scadenziario_db)).tutte(solo_aperte=False)
    assert len(scadenze) == 1
    assert scadenze[0].tipo == TipoTermine.UDIENZA
    assert scadenze[0].data_scadenza == "2026-10-09"
    assert "RG 777/2026" in scadenze[0].titolo
    assert scadenze[0].titolo.startswith("Rinvio udienza")
    assert "09/10/2026" in scadenze[0].titolo
    assert "Valuta termini da notifica PEC" not in scadenze[0].titolo
    assert "Evento:" in scadenze[0].descrizione
    assert scadenze[0].id_utente_responsabile == ""
    agenda_items = Agenda(str(agenda_db)).tutti()
    assert len(agenda_items) == 1
    assert agenda_items[0].external_organizer == ""


def test_pec_repair_removes_generic_gdp_notice_2030_deadline_and_agenda(tmp_path):
    from pct.agenda import Agenda, TipoAppuntamento
    from pct.scadenziario import GestioneScadenziario, TipoTermine

    scadenziario_db = tmp_path / "scadenze.json"
    agenda_db = tmp_path / "agenda.json"
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        scadenziario_db_path=scadenziario_db,
        agenda_db_path=agenda_db,
    )
    raw = next(raw for label, raw in synthetic_pec_messages() if label == "mittente_ambiguo")
    ingest = repo.ingest_mime(raw, account_email="studio@example.test", folder="INBOX", imap_uid="generic-gdp")
    repo.run_pending_jobs(limit=30, actor="pec-demo")

    agenda = Agenda(str(agenda_db))
    app = agenda.aggiungi(
        "Presidio PEC - Valuta termini da notifica PEC",
        TipoAppuntamento.SCADENZA,
        "2030-01-15T09:00:00",
        allow_overlap=True,
        external_uid=f"PEC_AUDIT:{ingest['id']}:deadline",
        external_provider="pec_audit",
        external_profile_id="pec_scadenziario",
        external_organizer="codex-test",
    )
    manager = GestioneScadenziario(str(scadenziario_db))
    manager.nuova(
        titolo="Valuta termini da notifica PEC: GIUDICE DI PACE - Notificazione ai sensi del D.L. 179/2012",
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza="2030-01-15",
        note=f"PEC_AUDIT:{ingest['id']}\nTermine legale conclusivo: no",
        id_utente_responsabile="codex-test",
        id_appuntamento=app.id,
        deadline_profile_code="PEC_AUTO_PRESIDIO",
    )

    repaired = repo.repair_pec_deadlines(actor="codex-test")

    assert repaired["deleted"] == 1
    assert GestioneScadenziario(str(scadenziario_db)).tutte(solo_aperte=False) == []
    assert Agenda(str(agenda_db)).tutti() == []


def test_pec_repair_and_backfill_report_missing_reference_without_unbound_local(tmp_path):
    from pct.scadenziario import GestioneScadenziario, TipoTermine

    scadenziario_db = tmp_path / "scadenze.json"
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        scadenziario_db_path=scadenziario_db,
    )
    GestioneScadenziario(str(scadenziario_db)).nuova(
        titolo="Scadenza PEC con riferimento mancante",
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza="2026-10-01",
        note="PEC_AUDIT:pec_mancante\nTermine legale conclusivo: no",
        deadline_profile_code="PEC_AUTO_PRESIDIO",
    )

    repaired = repo.repair_pec_deadlines(actor="pytest")
    backfilled = repo.enrich_deadlines_with_remote_hearing_links(actor="pytest")

    assert repaired["ok"] is False
    assert backfilled["ok"] is False
    combined = "\n".join([*repaired["errors"], *backfilled["errors"]])
    assert "cannot access local variable" not in combined
    assert "pec_mancante" in combined


def test_pec_repair_and_backfill_skip_email_only_audit_reference(tmp_path):
    from pct.scadenziario import GestioneScadenziario, TipoTermine

    scadenziario_db = tmp_path / "scadenze.json"
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        scadenziario_db_path=scadenziario_db,
    )
    GestioneScadenziario(str(scadenziario_db)).nuova(
        titolo="Scadenza con riferimento email legacy",
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza="2026-10-01",
        note="PEC_AUDIT:email:03c7d9aef123\nTermine legale conclusivo: no",
        deadline_profile_code="PEC_AUTO_PRESIDIO",
    )

    repaired = repo.repair_pec_deadlines(actor="pytest")
    backfilled = repo.enrich_deadlines_with_remote_hearing_links(actor="pytest")

    assert repaired["ok"] is True
    assert backfilled["ok"] is True
    assert repaired["skipped"] == 1
    assert backfilled["skipped"] == 1
    assert repaired["errors"] == []
    assert backfilled["errors"] == []


def test_pec_repair_upgrades_old_gdp_hearing_deadline_and_clears_codex_actor(tmp_path):
    from pct.agenda import Agenda
    from pct.scadenziario import GestioneScadenziario, TipoTermine

    scadenziario_db = tmp_path / "scadenze.json"
    agenda_db = tmp_path / "agenda.json"
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        scadenziario_db_path=scadenziario_db,
        agenda_db_path=agenda_db,
    )
    ingest = repo.ingest_mime(_gdp_hearing_message(), account_email="studio@example.test", folder="INBOX", imap_uid="old-gdp-hearing")
    repo.run_pending_jobs(limit=30, actor="pec-demo")
    manager = GestioneScadenziario(str(scadenziario_db))
    manager.nuova(
        titolo="Udienza da PEC: POSTA CERTIFICATA: GIUDICE DI PACE Notificazione ai sensi del D.L. 179/2012",
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza="2026-10-09",
        note=f"PEC_AUDIT:{ingest['id']}\nTermine legale conclusivo: no",
        id_utente_responsabile="codex-test",
        deadline_profile_code="PEC_AUTO_PRESIDIO",
    )

    repaired = repo.repair_pec_deadlines(actor="codex-test")

    assert repaired["updated"] >= 1
    scadenze = GestioneScadenziario(str(scadenziario_db)).tutte(solo_aperte=False)
    assert len(scadenze) == 1
    assert scadenze[0].tipo == TipoTermine.UDIENZA
    assert scadenze[0].id_utente_responsabile == ""
    assert scadenze[0].titolo.startswith("Rinvio udienza")
    assert "09/10/2026" in scadenze[0].titolo
    assert "RG 777/2026" in scadenze[0].titolo
    assert Agenda(str(agenda_db)).tutti()[0].external_organizer == ""


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
    assert report["deadline_proposal"]["auto_create"] is False
    assert report["deadline_proposal"]["status"] == "review_required"
    assert report["deadline_proposal"]["due_date"] == ""
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
    assert report["deadline_proposal"]["auto_create"] is False
    assert report["deadline_proposal"]["status"] == "not_needed"
    assert report["deadline_proposal"]["calendar_scope"] == "fascicolo_deposito"
    assert report["deadline_proposal"]["source_event_type"] == "pct_deposito"


def test_pct_deposit_controls_non_compliant_but_waiting_acceptance_is_warning():
    parsed = {
        "headers": {
            "subject": "POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO: Ricorso RG: 1733/2026 [JQ332-L01] [RefID_001_test]"
        },
        "body": {
            "text": (
                "Codice esito: -1.\n"
                "IDBUSTA: 35508878\n"
                "NOME FILE: DatiAtto.xml.p7m\n"
                "Atto non conforme alle specifiche. In attesa di conferma da parte della cancelleria: "
                "l'atto verra comunque accettato non e necessario effettuare nuovamente il deposito."
            )
        },
        "fields": {"tipo_ricevuta": {"value": "breve"}},
    }

    stage = detect_pct_deposit_stage(parsed)
    lifecycle = build_pct_deposit_lifecycle(parsed, [{"classification": "daticert"}], "pct_deposito")

    assert stage["id"] == "esito_controlli_deposito"
    assert stage["status"] == "warning"
    assert "non richiede nuovo deposito" in stage["reason"]
    assert lifecycle["current_stage"]["status"] == "warning"
    assert "stato intermedio" in lifecycle["communication"]


def test_pct_deposit_manual_acceptance_is_final_ok():
    parsed = {
        "headers": {
            "subject": "POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO: Ricorso RG: 1733/2026 [JQ332-L01] [RefID_001_test]"
        },
        "body": {
            "text": (
                "Codice esito: 2.\n"
                "IDBUSTA: 35508878\n"
                "Accettazione manuale avvenuta con successo."
            )
        },
    }

    stage = detect_pct_deposit_stage(parsed)
    lifecycle = build_pct_deposit_lifecycle(parsed, [{"classification": "daticert"}], "pct_deposito")

    assert stage["id"] == "accettazione_deposito"
    assert stage["status"] == "ok"
    assert lifecycle["expected_next"] == []
    assert "accettato" in lifecycle["communication"].lower()
    assert lifecycle["final_state"] == "accepted_manually"
    assert lifecycle["requires_new_deposit"] is False


def test_pct_esito_atto_fixtures_extract_strong_correlation_and_receipt_profile():
    fixtures = Path("tests/fixtures/pec")
    controls_xml = (fixtures / "esito_atto_attesa_conferma.xml").read_text(encoding="utf-8")
    acceptance_xml = (fixtures / "esito_atto_accettazione_manuale.xml").read_text(encoding="utf-8")

    controls = parse_pec_message(
        _pct_esito_mime(
            "POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO: Ricorso Punturiero RG: 1733/2026",
            controls_xml,
            message_id="<controls-35508878@example.test>",
            when="Mon, 15 Jun 2026 16:09:20 +0200",
        )
    )
    acceptance = parse_pec_message(
        _pct_esito_mime(
            "POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO: Ricorso Punturiero RG: 1733/2026",
            acceptance_xml,
            message_id="<accepted-35508878@example.test>",
            when="Tue, 16 Jun 2026 07:36:00 +0200",
        )
    )

    correlation = build_pct_deposit_correlation(controls)
    controls_report = build_validation_report(controls, [{"classification": "daticert", "filename": "daticert.xml"}])
    acceptance_report = build_validation_report(acceptance, [{"classification": "daticert", "filename": "daticert.xml"}])

    assert correlation["strategy"] == "idbusta"
    assert correlation["idbusta"] == "35508878"
    assert correlation["ref_id"] == "RefID_001_saAMJE8yxr"
    assert correlation["practice_code"] == "JQ332-L01"
    assert correlation["rg"] == "1733/2026"
    assert correlation["document_name"] == "Ricorso Punturiero (originale notificato).pdf"
    assert controls_report["event_type"] == "pct_deposito"
    assert controls_report["deposit_lifecycle"]["final_state"] == "awaiting_clerk_confirmation"
    assert controls_report["deposit_lifecycle"]["requires_new_deposit"] is False
    assert controls_report["deposit_lifecycle"]["receipt"]["outcome_code"] == -1
    assert acceptance_report["event_type"] == "pct_deposito"
    assert acceptance_report["deposit_lifecycle"]["final_state"] == "accepted_manually"
    assert acceptance_report["deposit_lifecycle"]["receipt"]["outcome_code"] == 2


def test_pct_deposit_receipts_upsert_one_fascicolo_card_and_no_duplicate_history(tmp_path):
    from pct.fascicoli import GestioneFascicoli, TipoFascicolo

    fixtures = Path("tests/fixtures/pec")
    controls_xml = (fixtures / "esito_atto_attesa_conferma.xml").read_text(encoding="utf-8")
    acceptance_xml = (fixtures / "esito_atto_accettazione_manuale.xml").read_text(encoding="utf-8")
    fascicoli_db = tmp_path / "fascicoli.json"
    fascicoli_docs = tmp_path / "documenti"
    fascicoli = GestioneFascicoli(str(fascicoli_db), documents_dir=str(fascicoli_docs))
    fascicolo = fascicoli.nuovo(
        "Ricorso Punturiero",
        TipoFascicolo.CIVILE,
        nome_cliente="Mario Rossi",
        tribunale="Tribunale di Palmi",
        numero_rg="1733",
        anno_rg=2026,
        controparte="Mario Rossi",
    )
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        fascicoli_db_path=fascicoli_db,
        fascicoli_docs_path=fascicoli_docs,
    )
    first = repo.ingest_mime(
        _pct_esito_mime(
            "POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO: Ricorso Punturiero RG: 1733/2026",
            controls_xml,
            message_id="<controls-upsert-35508878@example.test>",
            when="Mon, 15 Jun 2026 16:09:20 +0200",
        )
    )
    repo.run_pending_jobs(limit=20, actor="codex-test")
    second = repo.ingest_mime(
        _pct_esito_mime(
            "POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO: Ricorso Punturiero RG: 1733/2026",
            acceptance_xml,
            message_id="<accepted-upsert-35508878@example.test>",
            when="Tue, 16 Jun 2026 07:36:00 +0200",
        )
    )
    repo.run_pending_jobs(limit=20, actor="codex-test")
    repo.ingest_mime(
        _pct_esito_mime(
            "POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO: Ricorso Punturiero RG: 1733/2026",
            acceptance_xml,
            message_id="<accepted-upsert-35508878@example.test>",
            when="Tue, 16 Jun 2026 07:36:00 +0200",
        )
    )
    repo.run_pending_jobs(limit=20, actor="codex-test")

    saved = GestioneFascicoli(str(fascicoli_db), documents_dir=str(fascicoli_docs)).get(fascicolo.id)
    assert saved is not None
    assert len(saved.depositi_pct) == 1
    deposito = saved.depositi_pct[0]
    assert deposito.id_deposito_esterno == "35508878"
    assert deposito.stato == "ACCETTATO_CANCELLERIA"
    assert deposito.nome_atto_principale == "Ricorso Punturiero (originale notificato).pdf"
    assert deposito.ricevuta_controlli_automatici
    assert deposito.ricevuta_cancelleria
    assert deposito.note.count("PEC_DEPOSIT_EVENT:") == 2
    assert first["duplicate"] is False
    assert second["duplicate"] is False


def test_scadenziario_ignora_ricevute_generiche_senza_azione_operativa():
    parsed = {
        "headers": {"subject": "Ricevuta protocollo"},
        "fields": {"tipo_ricevuta": {"value": "breve"}},
        "body": {"text": "Ricevuta PEC senza udienza, termine, provvedimento o attività concreta da svolgere."},
        "procedural_dates": [],
    }

    report = build_validation_report(parsed, [{"classification": "da confermare", "filename": "daticert.xml"}])
    proposal = report["deadline_proposal"]

    assert proposal["auto_create"] is False
    assert proposal["calendar_scope"] == "presidio_pec"
    assert proposal["title"] == ""
    assert "non indica una data o un'attività giuridica certa" in proposal["reason"]


def test_topbar_sopprime_ricevute_tecniche_deposito_grezze():
    from web.services.topbar_operational import _is_raw_pct_deposit_receipt_email

    technical = EmailRicevuta(
        id="PEC-TECNICA",
        oggetto="POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO: Ricorso RG 1733/2026",
        corpo_testo="IDBUSTA: 35508878\nCodice esito: -1",
        stato_pct="WARN_CONTROLLI",
    )
    ordinary = EmailRicevuta(
        id="PEC-ORDINARIA",
        oggetto="Comunicazione cancelleria fissazione udienza",
        corpo_testo="RG 1754/2026. Udienza da remoto da verificare.",
        stato_pct="WARN_CONTROLLI",
    )

    assert _is_raw_pct_deposit_receipt_email(technical) is True
    assert _is_raw_pct_deposit_receipt_email(ordinary) is False


def test_presidio_documentale_lex_recupera_udienza_termine_e_metadati_rag(tmp_path):
    from pct.fascicoli import GestioneFascicoli, TipoAttivita, TipoDocumento, TipoFascicolo
    from pct.scadenziario import GestioneScadenziario, TipoTermine
    from pct.storage import StudioDB

    fascicoli_db = tmp_path / "fascicoli" / "fascicoli.json"
    fascicoli_docs = tmp_path / "fascicoli" / "documenti"
    scadenziario_db = tmp_path / "scadenziario" / "scadenze.json"
    agenda_db = tmp_path / "agenda" / "appuntamenti.json"
    studio_db = StudioDB.get(str(tmp_path / "studio.db"))
    term_day = date.today() + timedelta(days=25)
    hearing_day = date.today() + timedelta(days=35)
    term_it = term_day.strftime("%d/%m/%Y")
    hearing_it = hearing_day.strftime("%d/%m/%Y")
    link = "https://teams.microsoft.com/l/meetup-join/19%3alex-presidio"

    fascicoli = GestioneFascicoli(str(fascicoli_db), documents_dir=str(fascicoli_docs), studio_db=studio_db)
    fascicolo = fascicoli.nuovo(
        "Ricorso lavoro Punturiero",
        TipoFascicolo.LAVORO,
        nome_cliente="Mario Rossi",
        tribunale="Tribunale di Palmi",
        giudice="TOSONI CLAUDIA",
        numero_rg="1754",
        anno_rg=2026,
        controparte="INPS",
        oggetto="Ricorso ex art. 429 c.p.c.",
    )
    doc = fascicoli.aggiungi_documento(
        fascicolo.id,
        "Decreto fissazione udienza.txt",
        TipoDocumento.DECRETO,
        (
            "TRIBUNALE DI PALMI\n"
            "FISSA per la discussione della causa, ai sensi dell'art. 127-ter c.p.c. in sostituzione dell'udienza, "
            f"termine del {term_it} per il deposito di note scritte.\n"
            "Fissa inoltre udienza da remoto del "
            f"{hearing_it} ore 09:30 con collegamento audiovisivo.\n"
            f"Link stanza virtuale: {link}\n"
        ).encode("utf-8"),
    )
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        fascicoli_db_path=fascicoli_db,
        fascicoli_docs_path=fascicoli_docs,
        scadenziario_db_path=scadenziario_db,
        agenda_db_path=agenda_db,
    )

    report = repo.recover_missing_hearings_from_fascicolo_documents(actor="codex-test")

    assert report["checked_fascicoli"] == 1
    assert report["new_or_changed_documents"] == 1
    assert report["already_checked"] == 0
    assert report["indexed_documents"] == 1
    assert report["candidate_dates"] == 2
    assert report["scheduled"] == 2
    assert {item["retrieval_metadata"]["tenant_id"] for item in report["items"]} == {"default"}
    assert {item["retrieval_metadata"]["fascicolo_id"] for item in report["items"]} == {fascicolo.id}
    assert {item["retrieval_metadata"]["document_id"] for item in report["items"]} == {doc.id}
    assert {item["retrieval_metadata"]["documento"] for item in report["items"]} == {"Decreto fissazione udienza.txt"}
    assert {item["retrieval_metadata"]["sha256"] for item in report["items"]} == {doc.hash_sha256}
    assert {item["retrieval_metadata"]["numero_rg"] for item in report["items"]} == {"1754/2026"}
    assert {item["retrieval_metadata"]["ufficio"] for item in report["items"]} == {"Tribunale di Palmi"}
    scadenze = GestioneScadenziario(str(scadenziario_db), studio_db=studio_db).tutte(solo_aperte=False)
    assert len(scadenze) == 2
    titles = "\n".join(item.titolo for item in scadenze)
    descriptions = "\n".join(item.descrizione for item in scadenze)
    assert "Deposito note scritte ex art. 127-ter c.p.c." in titles
    assert "udienza" in titles.lower()
    assert "Cliente: Mario Rossi" in descriptions
    assert "Parte/soggetto: INPS" in descriptions
    assert "Ufficio: Tribunale di Palmi" in descriptions
    assert "Contesto letto:" in descriptions
    assert "Link stanza virtuale: [link indicato nel campo udienza da remoto]" in descriptions
    assert f"Link udienza audiovisiva: {link}" in descriptions
    assert f"Link stanza virtuale: {link}" not in descriptions
    assert any(item.tipo == TipoTermine.UDIENZA and item.remote_hearing_url == link for item in scadenze)
    assert not any(item.tipo == TipoTermine.UDIENZA and item.remote_hearing_source == "Corpo PEC" for item in scadenze)
    assert any(item.tipo == TipoTermine.ADEMPIMENTO and item.remote_hearing_url == "" for item in scadenze)
    agenda_items = Agenda(str(agenda_db), studio_db=studio_db).tutti()
    assert len(agenda_items) == 2
    assert {item.cliente for item in agenda_items} == {"Mario Rossi"}
    assert {item.tribunale for item in agenda_items} == {"Tribunale di Palmi"}
    assert {item.procedimento for item in agenda_items} == {"RG 1754/2026"}

    saved = GestioneFascicoli(str(fascicoli_db), documents_dir=str(fascicoli_docs), studio_db=studio_db).get(fascicolo.id)
    assert saved is not None
    assert saved.data_prossima_udienza == hearing_day.isoformat()
    assert any(att.tipo == TipoAttivita.UDIENZA and att.id_documento == doc.id for att in saved.attivita)
    assert any(att.tipo == TipoAttivita.TERMINE_SCADENZA and att.id_documento == doc.id for att in saved.attivita)

    second = repo.recover_missing_hearings_from_fascicolo_documents(actor="codex-test")
    assert second["scheduled"] == 0
    assert second["candidate_dates"] == 0
    assert second["already_presided"] == 0
    assert second["already_checked"] == 1
    assert second["new_or_changed_documents"] == 0
    assert len(GestioneScadenziario(str(scadenziario_db), studio_db=studio_db).tutte(solo_aperte=False)) == 2
    assert len(Agenda(str(agenda_db), studio_db=studio_db).tutti()) == 2


def test_presidio_documentale_worker_usa_sqlite_documenti_ai_se_studio_db_sola_lettura(tmp_path):
    from pct.storage import StudioDB

    fascicoli_db = tmp_path / "fascicoli" / "fascicoli.json"
    fascicoli_db.parent.mkdir(parents=True, exist_ok=True)
    fascicoli_db.write_text("[]", encoding="utf-8")
    studio_db = StudioDB.get(str(tmp_path / "studio.db"))
    studio_db.conn.execute("PRAGMA query_only=ON")
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        fascicoli_db_path=fascicoli_db,
        fascicoli_docs_path=tmp_path / "fascicoli" / "documenti",
    )

    service = repo._document_ai_service_for_fascicoli(SimpleNamespace())

    assert service.repository.backend_kind == "sqlite"
    assert Path(service.repository.structured_db.db_path) == tmp_path / "fascicoli" / "documenti_ai" / "documenti_ai.sqlite"
    assert service.repository.storage_root == tmp_path / "fascicoli" / "documenti_ai"


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
    assert massivo_payload["acquired"] == 0
    assert massivo_payload["duplicates"] == 0
    assert massivo_payload["skipped_already_presided"] == 1
    assert massivo_payload["deadline_report"]["created"] + massivo_payload["deadline_report"]["already_exists"] == 0
    assert massivo_payload["deadline_report"]["agenda_linked"] == 0
    assert massivo_payload["has_more"] is False
    assert massivo_payload["status"] == "completed"
    assert massivo_payload["local_acquire"]["items"] == []
    assert massivo_payload["workers"]["processed"] == 0
    assert "Nessuna nuova PEC da presidiare" in massivo_payload["messaggio"]
    from web.services.react_email_bridge import build_react_email_payload

    react_payload = build_react_email_payload(db_path=str(paths["EMAIL_CASELLA_DB"]), tenant_id="default")
    assert react_payload["summary"]["warnings"] == 0
    assert react_payload["items"][0]["pecPresidiata"] is True
    from pct.scadenziario import GestioneScadenziario
    from pct.agenda import Agenda

    scadenze = GestioneScadenziario(str(paths["SCADENZIARIO_DB"])).tutte(solo_aperte=False)
    assert len(scadenze) == 0
    assert len(Agenda(str(paths["AGENDA_DB"])).tutti()) == 0


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
    assert payload["skipped_missing_mime"] == 0

    repo = PecAuditRepository(paths["PEC_AUDIT_DB"], tenant_id="default")
    report = repo.local_acquire_run_report(run_id)
    assert report["status"] == "completed"
    assert len(report["items"]) == 3
    assert {item["status"] for item in report["items"]} == {"ingested"}

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
    assert payload["local_acquire"]["skipped_missing_mime"] == 0
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
    massivo = client.post("/api/pec/email/acquisisci-locali?limit=20&worker_limit=0&queue_repairs=1")
    assert massivo.status_code == 200
    payload = massivo.get_json()
    assert payload["ok"] is True
    assert payload["duplicates"] == 1
    assert payload["deadline_report"]["created"] == 1
    assert payload["deadline_report"]["agenda_linked"] == 0

    from pct.scadenziario import GestioneScadenziario
    from pct.agenda import Agenda

    scadenze = GestioneScadenziario(str(paths["SCADENZIARIO_DB"])).tutte(solo_aperte=False)
    assert len(scadenze) == 1
    assert f"PEC_AUDIT:{ingest['id']}" in scadenze[0].note
    assert scadenze[0].data_scadenza == "2030-07-09"
    assert "09/07/2030" in scadenze[0].titolo
    assert "comunicazione 3001/2025" in scadenze[0].titolo.lower()
    assert not scadenze[0].id_appuntamento
    assert len(Agenda(str(paths["AGENDA_DB"])).tutti()) == 0
    with sqlite3.connect(paths["NOTIFICATIONS_DB"]) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE source_type='pec_deadline' AND source_id=?",
            (ingest["id"],),
        ).fetchone()[0] == 1


def test_pec_deadline_without_time_pushes_to_calendar_engine_as_all_day(tmp_path):
    agenda_db = tmp_path / "agenda.json"
    scadenziario_db = tmp_path / "scadenze.json"
    calendar_sync_db = tmp_path / "calendar_sync.json"
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        scadenziario_db_path=scadenziario_db,
        agenda_db_path=agenda_db,
        calendar_sync_db_path=calendar_sync_db,
    )
    engine = CalendarSyncEngine.from_paths(
        agenda_db=str(agenda_db),
        scadenziario_db=str(scadenziario_db),
        sync_db=str(calendar_sync_db),
        tenant_id="default",
    )
    account = engine.repository.upsert_account(
        {
            "tenant_id": "default",
            "provider": "demo",
            "display_name": "Google Calendar",
            "email": "studio@example.test",
            "auth_type": "demo",
            "encrypted_credentials": engine.credentials.encrypt({"mode": "test"}),
            "status": "active",
        }
    )
    calendar = engine.repository.upsert_calendar(
        {
            "tenant_id": "default",
            "account_id": account["id"],
            "provider": "demo",
            "provider_calendar_id": "demo-primary",
            "name": "Calendario Google",
            "role": "completo",
            "direction": "bidirectional",
            "enabled": True,
            "privacy_level": PRIVACY_REDUCED,
        }
    )
    proposal = {
        "auto_create": True,
        "deadline_kind": "adempimento",
        "due_date": "2026-07-10",
        "title": "Valuta termini da notifica PEC",
        "reason": "Adempimento: valutare opposizione entro il termine.",
        "source_event_type": "notifica_pec",
        "source_event_at": "2026-06-10",
    }

    result = repo.schedule_deadline_from_payload(
        "pec_calendar_no_time",
        parsed={"headers": {"subject": "POSTA CERTIFICATA: notifica"}},
        report={"event_type": "notifica_pec", "deadline_proposal": proposal},
        message={"linked_fascicolo_id": "RG 12/2026"},
    )
    remote_events = [
        item
        for item in engine.providers["demo"]._load()["events"].values()
        if item.get("calendar_id") == calendar["provider_calendar_id"]
    ]

    assert result["ok"] is True
    assert result["agenda"]["agenda_skipped"] is True
    assert result["calendar_sync"]["pushed"] == 1
    assert Agenda(str(agenda_db)).tutti() == []
    assert len(remote_events) == 1
    remote = remote_events[0]
    assert remote["all_day"] is True
    assert remote["start"] == "2026-07-10"
    assert remote["end"] == "2026-07-11"
    visible = f"{remote['title']} {remote['description']}"
    assert "Scadenza: Valuta termini da notifica PEC" in visible
    assert "Dettagli riservati in IUSENTRA." in visible
    assert "09:00" not in visible
    for token in ("Presidio PEC", "PEC_AUDIT", "pipeline", "audit-grade", "payload", "runtime", "backend"):
        assert token not in visible


def test_presidio_cli_ricostruisce_pec_locale_e_alimenta_catena_operativa(tmp_path):
    from pct.agenda import Agenda
    from pct.email_client import CartellaEmail
    from pct.scadenziario import GestioneScadenziario
    from scripts.audit_pec_operational_chain import audit_studio
    from scripts.presidia_pec_local_archive import presidia_studio

    paths = {
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
        "NOTIFICATIONS_DB": str(tmp_path / "notifications" / "notifications.db"),
        "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
    }
    for value in paths.values():
        Path(value).parent.mkdir(parents=True, exist_ok=True)
    from pct.auth import GestioneUtenti, RuoloUtente

    user = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="test",
        crea_admin_se_vuoto=False,
    ).crea(
        username="avvocato",
        password="Avvocato123!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.test",
        nome_completo="Avv. Test",
        must_change_password=False,
    )
    gestore = GestioneEmailRicevute(paths["EMAIL_CASELLA_DB"])
    gestore.aggiungi(
        EmailRicevuta(
            id="MAIL-PEC-RICOSTRUITA",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="Per conto di: tribunale.palmi@civile.ptel.giustiziacert.it",
            destinatari="studio@example.pec.it",
            oggetto="POSTA CERTIFICATA: COMUNICAZIONE 555/2026/LAV",
            data="2026-06-01T12:00:00",
            corpo_testo=(
                "Messaggio di posta certificata. Comunicazione di cancelleria. "
                "Numero di Ruolo generale: 555/2026. "
                "Oggetto: FISSAZIONE UDIENZA DI DISCUSSIONE. "
                "Descrizione: FISSATA UDIENZA DI DISCUSSIONE IL 29/10/2026 09:15."
            ),
            allegati=[{"nome": "Comunicazione.xml", "mime": "application/xml", "size": 140}],
            message_id="<mail-pec-ricostruita@example.test>",
            origine="PEC",
        )
    )

    result = presidia_studio(
        studio_slug="default",
        paths=paths,
        actor="pytest",
        worker_limit=80,
    )

    assert result["ok"] is True
    assert result["pec_relevant"] == 1
    assert result["reconstructed"] == 1
    assert result["missing_mime"] == 0
    assert result["deadline_created"] + result["deadline_already_exists"] == 1
    assert result["agenda_linked"] == 1
    assert result["notifications_created"] >= 1
    assert user.id in result["local_acquire"]["payload"]["notification_users"]
    scadenze = GestioneScadenziario(paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    pec_scadenze = [item for item in scadenze if "PEC_AUDIT:" in item.note]
    assert len(pec_scadenze) == 1
    assert pec_scadenze[0].data_scadenza == "2026-10-29"
    assert pec_scadenze[0].id_appuntamento
    appuntamenti_pec = [item for item in Agenda(paths["AGENDA_DB"]).tutti() if str(item.external_uid).startswith("PEC_AUDIT:")]
    assert len(appuntamenti_pec) == 1
    audit = audit_studio(paths)
    assert audit["ok"] is True
    assert audit["email_archive"]["pec_relevant"] == 1
    assert audit["pec_control"]["latest_local_status"]["missing_mime_latest"] == 0
    with sqlite3.connect(paths["NOTIFICATIONS_DB"]) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id=? AND source_type='pec_deadline'",
            (user.id,),
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
