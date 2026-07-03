from __future__ import annotations

import sqlite3
from email import policy
from email.message import EmailMessage

from pct.pec_legal_event_understanding import SCHEMA, build_legal_event_understanding
from pct.pec_pipeline import PecAuditRepository


TEAMS = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc/0?context=xyz"


def _parsed(subject: str = "Fissazione udienza da remoto", body: str = "", *, date: str = "2026-03-02") -> dict:
    return {
        "headers": {"subject": subject, "date": date, "message_id": "<test-pec@example.test>"},
        "legal_workflow": {
            "family": "comunicazione_cancelleria_civile",
            "family_label": "Cancelleria civile",
            "event_type": "udienza_online" if "udienza" in subject.lower() else "comunicazione_generica",
            "event_label": "Udienza online" if "udienza" in subject.lower() else "Comunicazione",
            "priority": "alta",
        },
        "body": {
            "text": body or "Udienza da remoto, trattazione ex art. 127-ter. Il link verra' comunicato.",
            "html_text": "",
            "href_urls": [],
            "ics_text": "",
        },
        "fields": {"data_consegna": {"value": date}},
        "pct_deposit_receipt": {},
    }


def test_vista_unificata_aggrega_segnali():
    report = {"remote_hearing": {"detected": True, "mode_unified": "remoto", "links": [], "times": [], "pdf_required": False}}
    u = build_legal_event_understanding(_parsed(), report)
    assert u["schema"] == SCHEMA
    assert u["classification"]["family"] == "comunicazione_cancelleria_civile"
    assert u["hearing"]["mode"] == "remoto"
    assert u["deadline"]["ok"] is True
    assert u["deadline"]["template_code"] == "CIV_OPPOSIZIONE_127_TER"
    assert u["human_review_required"] is True
    assert u["priority"] == "P0"


def test_web_push_safe_title_niente_pii_e_p0_su_remoto_senza_link():
    report = {"remote_hearing": {"detected": True, "mode_unified": "remoto", "links": [], "pdf_required": False}}
    u = build_legal_event_understanding(_parsed(), report)
    title = u["web_push_safe_title"]
    assert "P0" in title and "remoto" in title.lower()
    assert "@" not in title
    assert "4321" not in title


def test_senza_report_riconosce_note_scritte_da_testo():
    u = build_legal_event_understanding(_parsed(body="Trattazione scritta ex art. 127-ter c.p.c. con deposito note scritte."), None)
    assert u["schema"] == SCHEMA
    assert u["hearing"]["mode"] == "note_scritte"
    assert u["deadlines"][0]["norma"] == "Art. 127-ter c.p.c."


def test_udienza_da_remoto_con_link_teams_in_href():
    parsed = _parsed(body="L'udienza si terra' da remoto in videoconferenza.")
    parsed["body"]["href_urls"] = [TEAMS]
    u = build_legal_event_understanding(parsed, {})
    assert u["hearings"][0]["mode"] == "remoto"
    assert u["hearings"][0]["platform"] == "Microsoft Teams"
    assert u["hearings"][0]["link"] == TEAMS
    assert u["hearings"][0]["link_verified"] is True
    assert u["priority"] == "P1"


def test_udienza_in_presenza_con_aula_e_piano():
    u = build_legal_event_understanding(
        _parsed("Fissazione udienza in presenza", "Udienza in presenza presso il Tribunale, aula 3 piano 2."),
        {},
    )
    assert u["hearings"][0]["mode"] == "presenza"
    assert u["hearings"][0]["aula"] == "3"
    assert u["hearings"][0]["piano"] == "2"


def test_udienza_mista_con_link_e_aula():
    u = build_legal_event_understanding(
        _parsed("Fissazione udienza mista", f"Udienza mista, aula MVC 4 e collegamento {TEAMS}"),
        {},
    )
    assert u["hearings"][0]["mode"] == "mista"
    assert u["hearings"][0]["link"] == TEAMS


def test_sentenza_senza_distrazione_credito_parte_e_no_termine_breve():
    text = (
        "Deposito sentenza. Condanna parte resistente alla rifusione delle spese di lite "
        "liquidando la complessiva somma di € 321,50, di cui € 21,50 per esborsi, oltre accessori."
    )
    u = build_legal_event_understanding(_parsed("Deposito sentenza RG 697/2025", text), {})
    payment = u["payments"][0]
    assert payment["payment_event_type"] == "spese_parte"
    assert payment["beneficiary"] == "parte"
    assert payment["lawyer_direct_credit"] is False
    assert payment["amounts"]["totale_testuale"] == 321.50
    assert payment["amounts"]["esborsi"] == 21.50
    assert any(item["norma"] == "Art. 133 c.p.c. / art. 325 c.p.c." for item in u["deadlines"])


def test_sentenza_con_distrazione_credito_avvocato():
    text = (
        "Condanna alle spese, liquidando la complessiva somma di € 1.100,00, "
        "con distrazione in favore del difensore antistatario."
    )
    u = build_legal_event_understanding(_parsed("Deposito sentenza", text), {})
    payment = u["payments"][0]
    assert payment["payment_event_type"] == "spese_distratte_avvocato"
    assert payment["beneficiary"] == "avvocato"
    assert payment["lawyer_direct_credit"] is True
    assert payment["amounts"]["totale_testuale"] == 1100.00


def test_spese_compensate_non_apre_incasso():
    u = build_legal_event_understanding(_parsed("Sentenza", "Il giudice compensa integralmente le spese tra le parti."), {})
    assert u["payments"][0]["payment_event_type"] == "nessuno"
    assert u["payments"][0]["lawyer_direct_credit"] is False


def test_gratuito_patrocinio_apre_workflow_erario_review():
    text = "Decreto di pagamento in patrocinio a spese dello Stato, DPR 115/2002, da monitorare su SIAMM/LSG."
    u = build_legal_event_understanding(_parsed("Decreto pagamento gratuito patrocinio", text), {})
    payment = u["payments"][0]
    assert payment["payment_event_type"] == "gratuito_patrocinio"
    assert payment["payer"] == "Erario"
    assert payment["human_review_required"] is True


def test_contributo_unificato_distinto_da_esborsi():
    text = (
        "Contributo unificato c.u. versato € 98,00. "
        "Liquidando la complessiva somma di € 321,50, di cui € 21,50 per esborsi."
    )
    u = build_legal_event_understanding(_parsed("Sentenza con spese", text), {})
    cu = next(item for item in u["payments"] if item["payment_event_type"] == "contributo_unificato")
    spese = next(item for item in u["payments"] if item["payment_event_type"] == "spese_parte")
    assert cu["amounts"]["totale_testuale"] == 98.00
    assert spese["amounts"]["esborsi"] == 21.50


def test_127_bis_propone_richiesta_presenza_5_giorni():
    u = build_legal_event_understanding(
        _parsed("Udienza da remoto ex art. 127-bis", "Udienza mediante collegamento audiovisivo ai sensi dell'art. 127-bis c.p.c."),
        {},
        dies_a_quo_date="2026-07-01",
    )
    assert any(item["norma"] == "Art. 127-bis c.p.c." and item["duration_value"] == 5 for item in u["deadlines"])


def test_catena_pct_ricevuta_accettazione_non_chiude_workflow():
    parsed = _parsed("Ricevuta di accettazione deposito")
    parsed["pct_deposit_receipt"] = {"receipt_stage": "ricevuta_accettazione"}
    u = build_legal_event_understanding(parsed, {"deposit_lifecycle": {"current_stage": {"id": "ricevuta_accettazione", "label": "Accettazione PEC"}}})
    assert u["pct_receipts"]["is_pct_receipt"] is True
    assert u["pct_receipts"]["can_close_deposit_workflow"] is False
    assert u["pct_receipts"]["deposit_chain_status"] == "incomplete"


def test_udienza_teams_valida_non_diventa_falso_errore_pct():
    parsed = _parsed(
        "Fissazione udienza da remoto RG 1754/2026",
        f"RG 1754/2026. Udienza da remoto il 20/05/2026 ore 10:00 con collegamento {TEAMS}.",
    )
    parsed["pct_deposit_receipt"] = {"receipt_stage": "deposito_da_ricondurre"}
    report = {
        "remote_hearing": {
            "detected": True,
            "mode_unified": "remoto",
            "links": [{"url": TEAMS, "source": "Corpo PEC", "exact_match": True}],
            "times": ["10:00"],
        },
        "deposit_lifecycle": {
            "current_stage": {
                "id": "deposito_da_ricondurre",
                "label": "Deposito da ricondurre",
            }
        },
    }
    u = build_legal_event_understanding(parsed, report)
    assert u["priority"] == "P1"
    assert u["pct_receipts"]["is_pct_receipt"] is False
    assert u["pct_receipts"]["blocking_errors"] == []


def test_penale_non_applica_regole_civili_automatiche():
    parsed = _parsed(
        "Deposito atti penali PDP proc. pen. n. 1365_2016 RG APP",
        "Comunicazione penale PDP con RG APP; non applicare regole civili automatiche.",
    )
    parsed["legal_workflow"] = {
        "family": "deposito_penale_pdp",
        "event_type": "comunicazione_penale_pdp",
        "human_review_required": True,
        "registri": [{"numero": "1365", "anno": "2016", "registro_normalizzato": "RG_APP", "canale": "PDP_PENALE"}],
    }
    u = build_legal_event_understanding(parsed, {})
    assert u["classification"]["family"] == "deposito_penale_pdp"
    assert u["procedimento"]["canale"] == "PDP_PENALE"
    assert u["human_review_required"] is True


def test_worker_persisted_legal_event_tables(tmp_path):
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    msg = EmailMessage()
    msg["Subject"] = "Fissazione udienza da remoto ex art. 127-ter c.p.c."
    msg["From"] = "Cancelleria <tribunale.milano@giustiziacert.it>"
    msg["To"] = "studio@example.test"
    msg["Date"] = "Wed, 01 Jul 2026 09:00:00 +0200"
    msg["Message-ID"] = "<legal-understanding-v2@example.test>"
    msg.set_content("Udienza da remoto mediante collegamento audiovisivo; il link verra' comunicato.")

    ingest = repo.ingest_mime(msg.as_bytes(policy=policy.SMTP), account_email="studio@example.test", folder="INBOX", imap_uid="1")
    repo.run_pending_jobs(limit=20, actor="pytest")

    with sqlite3.connect(tmp_path / "pec_audit.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        event = conn.execute("SELECT * FROM pec_legal_events WHERE message_id=?", (ingest["id"],)).fetchone()
        assert event is not None
        assert event["primary_event"]
        assert event["priority"] == "P0"
        hearings = conn.execute("SELECT * FROM pec_legal_hearings WHERE legal_event_id=?", (event["id"],)).fetchall()
        deadlines = conn.execute("SELECT * FROM pec_legal_deadlines WHERE legal_event_id=?", (event["id"],)).fetchall()
        assert hearings and hearings[0]["mode"] == "remoto"
        assert deadlines
