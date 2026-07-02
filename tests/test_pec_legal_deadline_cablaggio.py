"""Cablaggi B/C: proponente-termini legali agganciato alla PEC.

B — quando la PEC cita una norma con termine perentorio (es. art. 127-ter c.p.c.),
`build_validation_report` aggancia il termine LEGALE calcolato dal motore
deterministico (`legal_deadline_proposal`) e `schedule_deadline` crea una scadenza
sulla data legale, con campi legali (perentorietà, date legale/grezza, trace, template),
oltre al presidio operativo. Fail-closed: nessuna norma riconosciuta ⇒ presidio invariato.

C — `get_message_detail` espone la vista unificata `legal_event_understanding`
(schema v2), sola-lettura, che riusa il termine legale già calcolato dal report.

Fonti certe: art. 127-ter c.p.c. (5 giorni dalla comunicazione), art. 133 c.p.c.
(la sola comunicazione di deposito sentenza NON fa decorrere il termine breve ex art. 325).
"""

from __future__ import annotations

from email import policy
from email.message import EmailMessage

from pct.pec_pipeline import (
    PecAuditRepository,
    _legal_deadline_scadenza_fields,
    _report_has_legal_deadline,
    build_validation_report,
)
from pct.scadenziario import GestioneScadenziario


def _parsed_127ter() -> dict:
    return {
        "headers": {
            "subject": "Comunicazione di cancelleria - trattazione scritta ex art. 127-ter c.p.c. - RG 4321/2026",
            "from": [{"email": "tribunale.milano@giustiziapec.it"}],
            "date": "2026-07-01T09:00:00Z",
        },
        "body": {
            "text": "Il giudice dispone la trattazione scritta con note scritte in sostituzione dell'udienza ai sensi dell'art. 127-ter c.p.c.",
            "ics_text": "",
        },
        "fields": {"data_consegna": {"value": "2026-07-01T09:00:00Z"}},
        "legal_workflow": {"event_type": "comunicazione_generica", "family": "cancelleria"},
    }


def _ingest_127ter(tmp_path):
    scad_db = tmp_path / "scadenziario" / "scadenze.json"
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        scadenziario_db_path=scad_db,
    )
    msg = EmailMessage()
    msg["Subject"] = "Comunicazione di cancelleria - trattazione scritta ex art. 127-ter c.p.c. - RG 4321/2026"
    msg["From"] = "Cancelleria <tribunale.milano@giustiziapec.it>"
    msg["To"] = "studio@example.test"
    msg["Date"] = "Wed, 01 Jul 2026 09:00:00 +0200"
    msg["Message-ID"] = "<127ter-comunicazione@example.test>"
    msg.set_content(
        "Il giudice dispone la trattazione scritta con note scritte in sostituzione "
        "dell'udienza ai sensi dell'art. 127-ter c.p.c. Le parti possono opporsi."
    )
    ingest = repo.ingest_mime(
        msg.as_bytes(policy=policy.SMTP),
        account_email="studio@example.test",
        folder="INBOX",
        imap_uid="uid-127ter",
    )
    repo.run_pending_jobs(limit=30, actor="pytest")
    return repo, ingest["id"], scad_db


# --- Helper puri -----------------------------------------------------------------


def test_report_has_legal_deadline_predicate():
    assert _report_has_legal_deadline({"legal_deadline_proposal": {"ok": True, "deadline": "2026-07-06"}}) is True
    assert _report_has_legal_deadline({"legal_deadline_proposal": {"ok": False}}) is False
    assert _report_has_legal_deadline({"legal_deadline_proposal": {"ok": True}}) is False  # senza data
    assert _report_has_legal_deadline({}) is False
    assert _report_has_legal_deadline(None) is False


def test_legal_deadline_scadenza_fields_present():
    proposal = {
        "legal_deadline_proposal": {
            "ok": True,
            "deadline": "2026-07-06",
            "raw_deadline": "2026-07-06",
            "tipo": "perentorio",
            "norma": "Art. 127-ter c.p.c.",
            "template_code": "CIV_OPPOSIZIONE_127_TER",
            "dies_a_quo_type": "comunicazione",
            "dies_a_quo_date": "2026-07-01",
            "azione": "Opposizione alla trattazione scritta ex art. 127-ter c.p.c.",
            "steps": ["dies a quo 2026-07-01", "+5 giorni"],
        }
    }
    fields = _legal_deadline_scadenza_fields(proposal)
    assert fields["present"] is True
    assert fields["perentorio"] is True
    assert fields["due_date"] == "2026-07-06"
    assert fields["profile_code"] == "CIV_OPPOSIZIONE_127_TER"
    assert fields["title"].startswith("Opposizione")
    assert fields["source_event_type"] == "comunicazione"
    assert fields["source_event_at"] == "2026-07-01"
    assert set(fields["extra"]) == {"legal_due_at", "raw_due_at", "trace_json"}
    assert fields["extra"]["legal_due_at"] == "2026-07-06"
    assert fields["extra"]["trace_json"] and fields["extra"]["trace_json"] != "[]"
    assert "revisione professionale obbligatoria" in fields["note_line"]


def test_legal_deadline_scadenza_fields_absent_is_presidio():
    # Fail-closed: nessun termine legale ⇒ default presidio operativo invariato.
    for proposal in ({}, None, {"legal_deadline_proposal": {"ok": False}}):
        fields = _legal_deadline_scadenza_fields(proposal)
        assert fields["present"] is False
        assert fields["profile_code"] == "PEC_AUTO_PRESIDIO"
        assert fields["due_date"] == ""
        assert fields["title"] == ""
        assert fields["perentorio"] is False
        assert fields["extra"] == {}
        assert "presidio operativo" in fields["note_line"]


# --- Cablaggio B: report → proposta termine legale --------------------------------


def test_build_validation_report_attaches_legal_deadline():
    report = build_validation_report(_parsed_127ter(), [])
    legal = (report.get("deadline_proposal") or {}).get("legal_deadline_proposal") or {}
    assert legal.get("ok") is True
    assert legal.get("template_code") == "CIV_OPPOSIZIONE_127_TER"
    assert legal.get("deadline") == "2026-07-06"  # 01/07 + 5 giorni
    assert legal.get("tipo") == "perentorio"
    assert legal.get("human_review_required") is True


def test_deposito_sentenza_non_calcola_termine_breve():
    # Art. 133 c.p.c.: la sola comunicazione di deposito sentenza NON fa decorrere
    # il termine breve ex art. 325 c.p.c.
    parsed = {
        "headers": {"subject": "Comunicazione deposito sentenza - termine breve - RG 10/2026", "date": "2026-07-01T09:00:00Z"},
        "body": {"text": "Si comunica il deposito della sentenza. Termine breve per l'appello.", "ics_text": ""},
        "fields": {"data_consegna": {"value": "2026-07-01T09:00:00Z"}},
        "legal_workflow": {"event_type": "deposito_sentenza"},
    }
    report = build_validation_report(parsed, [])
    legal = (report.get("deadline_proposal") or {}).get("legal_deadline_proposal") or {}
    # Nessun termine breve calcolato in automatico: astensione + revisione umana.
    assert legal.get("ok") is not True
    assert legal.get("human_review_required") is True


# --- Cablaggio B end-to-end: scadenza legale creata su DB reale -------------------


def test_schedule_deadline_creates_legal_scadenza(tmp_path):
    repo, message_id, scad_db = _ingest_127ter(tmp_path)

    scheduled = repo.schedule_deadline(message_id, actor="pytest")
    assert scheduled["ok"] is True
    assert scheduled["due_date"] == "2026-07-06"  # data LEGALE, non presidio operativo

    scadenze = GestioneScadenziario(str(scad_db)).tutte(solo_aperte=False)
    assert len(scadenze) == 1
    s = scadenze[0]
    assert s.perentorio is True
    assert s.data_scadenza == "2026-07-06"
    assert s.legal_due_at == "2026-07-06"
    assert s.deadline_profile_code == "CIV_OPPOSIZIONE_127_TER"
    assert s.trace_json and s.trace_json != "[]"
    assert s.ha_calcolo_avanzato is True
    assert s.titolo.startswith("Opposizione")  # titolo = azione legale, non presidio generico
    assert "revisione professionale obbligatoria" in s.note


def test_schedule_deadline_idempotent_legal(tmp_path):
    repo, message_id, scad_db = _ingest_127ter(tmp_path)
    first = repo.schedule_deadline(message_id, actor="pytest")
    assert first["ok"] is True
    second = repo.schedule_deadline(message_id, actor="pytest")
    assert second["ok"] is True
    assert second.get("already_exists") is True
    scadenze = GestioneScadenziario(str(scad_db)).tutte(solo_aperte=False)
    assert len(scadenze) == 1  # nessun duplicato


# --- Cablaggio C: vista unificata esposta in get_message_detail -------------------


def test_get_message_detail_exposes_legal_event_understanding(tmp_path):
    repo, message_id, _ = _ingest_127ter(tmp_path)
    detail = repo.get_message_detail(message_id)
    und = detail.get("legal_event_understanding") or {}
    assert und.get("schema") == "iusentra.pec.legal_event_understanding.v2"
    # C riusa il termine legale già calcolato dal report (B), stesso template.
    assert (und.get("deadline") or {}).get("template_code") == "CIV_OPPOSIZIONE_127_TER"
    assert und.get("human_review_required") is True
    # Web push senza PII: solo la natura dell'evento.
    assert und.get("web_push_safe_title") == "Termine perentorio rilevato in PEC"
    assert "4321" not in und.get("web_push_safe_title", "")  # nessun RG/PII nel titolo
