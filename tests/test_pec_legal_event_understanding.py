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


def test_sentenza_a_verbale_429_non_resta_opposizione_127ter_e_apre_notifica():
    text = (
        "SENTENZA A VERBALE (art. 127 ter cpc). TRIBUNALE ORDINARIO DI PADOVA. "
        "Il Giudice decide la causa con sentenza a norma degli artt. 429 e 127ter cpc. "
        "Il Giudice, definitivamente decidendo: accerta il diritto di parte ricorrente; "
        "condanna il Ministero a costituire la Carta elettronica con accredito di euro 500 "
        "per ciascuno degli anni scolastici; condanna il Ministero alle spese di lite, "
        "che liquida in € 1.030,00 oltre 15% spese generali, IVA e CPA, con distrazione "
        "in favore del procuratore antistatario. "
        "http://schemi.processotelematico.giustizia.it/Schemi/Comunicazione.dtd"
    )
    parsed = _parsed(
        "Tribunale Ordinario di Padova Notificazione ai sensi del D.L. 179/2012",
        "Notificazione di cancelleria ai sensi del D.L. 179/2012.",
        date="2026-07-16T11:01:03Z",
    )
    parsed["legal_workflow"]["family"] = "comunicazione_lavoro"
    parsed["legal_workflow"]["event_type"] = "udienza_online"
    parsed["procedural_dates"] = [
        {
            "deadline_kind": "udienza",
            "date": "2026-07-16",
            "time": "13:01",
            "context": text,
            "source": "Comunicazione.xml",
        }
    ]
    report = {
        "deadline_proposal": {
            "legal_deadline_proposal": {
                "ok": True,
                "azione": "Opposizione alla trattazione scritta ex art. 127-ter c.p.c. (5 giorni dalla comunicazione)",
                "norma": "Art. 127-ter c.p.c.",
                "template_code": "CIV_OPPOSIZIONE_127_TER",
                "dies_a_quo_type": "comunicazione",
                "dies_a_quo_date": "2026-07-16",
                "durata": 5,
                "unita": "days",
                "tipo": "perentorio",
                "confidence": 0.9,
            }
        }
    }

    u = build_legal_event_understanding(
        parsed,
        report,
        attachments=[{"filename": "19040620s.pdf", "ocr_text": text, "sha256": "b" * 64}],
    )

    assert u["classification"]["primary_event"] in {"sentenza_a_verbale", "sentenza_a_verbale_429"}
    assert "sentenza_rito_lavoro_art_429" in u["classification"]["events"]
    assert all("127-ter" not in item["deadline_type"] for item in u["deadlines"])
    assert any("Esame sentenza" in item["deadline_type"] for item in u["deadlines"])
    assert any(item["notification_case"] == "judgment_to_notify_review" for item in u["notifications"])
    assert any(item["action_type"] == "notifica_legale" for item in u["actions"])
    assert u["payments"][0]["payment_event_type"] == "spese_distratte_avvocato"
    assert u["payments"][0]["amounts"]["totale_testuale"] == 1030.00
    assert all("Comunicazione.dtd" not in str(item.get("link") or "") for item in u["hearings"])


def test_pqm_di_rinvio_non_diventa_sentenza_da_notificare():
    text = (
        "Il Giudice, verificata la necessità di ulteriore documentazione, P.Q.M. "
        "rinvia la causa ai sensi degli artt. 181 e 309 c.p.c. all'udienza del "
        "08/09/2026 ore 09:00. Si comunichi."
    )
    parsed = _parsed("Comunicazione 771/2025/LAV", text, date="2026-07-16T12:12:00Z")
    parsed["legal_workflow"]["event_type"] = "comunicazione_cancelleria"

    u = build_legal_event_understanding(parsed, {})

    assert u["classification"]["primary_event"] != "sentenza_a_verbale"
    assert "sentenza_a_verbale" not in u["classification"]["events"]
    assert not any(item.get("creates_notification_candidate") for item in u["notifications"])


def test_dispositivo_127ter_con_richiamo_429_resta_termine_note_scritte():
    text = (
        "TRIBUNALE ORDINARIO. Il Giudice, visto l'art. 127-ter c.p.c., P.Q.M. dispone "
        "la trattazione scritta e assegna alle parti termine di cinque giorni per il "
        "deposito delle note. Il richiamo all'art. 429 c.p.c. riguarda la futura fase "
        "decisoria; non è stata pronunciata sentenza."
    )
    parsed = _parsed("Ordinanza per trattazione scritta", text, date="2026-07-17T09:00:00+02:00")
    parsed["legal_workflow"]["event_type"] = "udienza_sostituita_da_note_scritte"

    u = build_legal_event_understanding(parsed, {})

    assert u["classification"]["primary_event"] == "udienza_sostituita_da_note_scritte"
    assert "sentenza_a_verbale" not in u["classification"]["events"]
    assert any(item["norma"] == "Art. 127-ter c.p.c." for item in u["deadlines"])
    assert not any("Esame sentenza" in item["deadline_type"] for item in u["deadlines"])
    assert not any(item.get("creates_notification_candidate") for item in u["notifications"])


def test_allegato_127ter_operativo_non_viene_contaminato_da_sentenza_storica_separata():
    parsed = _parsed(
        "Comunicazione ordinanza di trattazione scritta",
        "Si comunica l'ordinanza corrente ex art. 127-ter c.p.c.; depositare le note scritte.",
        date="2026-07-17T09:30:00+02:00",
    )
    parsed["legal_workflow"]["event_type"] = "udienza_sostituita_da_note_scritte"
    current_order = {
        "filename": "ordinanza-corrente-127ter.pdf",
        "ocr_text": (
            "Il Giudice P.Q.M. dispone la trattazione scritta ai sensi dell'art. 127-ter "
            "c.p.c. e assegna termine per note."
        ),
    }
    historical_judgment = {
        "filename": "sentenza-storica-altro-evento.pdf",
        "ocr_text": (
            "TRIBUNALE ORDINARIO. SENTENZA A VERBALE. Il Giudice, definitivamente "
            "decidendo, accerta il diritto e condanna il Ministero alle spese."
        ),
    }

    u = build_legal_event_understanding(
        parsed,
        {},
        attachments=[current_order, historical_judgment],
    )

    assert u["classification"]["primary_event"] == "udienza_sostituita_da_note_scritte"
    assert any(item["norma"] == "Art. 127-ter c.p.c." for item in u["deadlines"])
    assert not any("Esame sentenza" in item["deadline_type"] for item in u["deadlines"])
    assert not any(item.get("creates_notification_candidate") for item in u["notifications"])
    binding = u["input_quality"]["source_binding"]
    assert binding["status"] == "bound"
    assert "ordinanza-corrente-127ter.pdf" in binding["selected_sources"]
    assert "sentenza-storica-altro-evento.pdf" in binding["excluded_sources"]


def test_ordinanza_di_rinvio_corrente_non_viene_contaminata_da_sentenza_storica_separata():
    parsed = _parsed(
        "Comunicazione ordinanza di rinvio",
        "Si comunica l'ordinanza corrente di rinvio dell'udienza.",
        date="2026-07-17T10:15:00+02:00",
    )
    parsed["legal_workflow"]["event_type"] = "rinvio_udienza"
    current_order = {
        "filename": "ordinanza-rinvio-corrente.pdf",
        "ocr_text": (
            "Il Giudice, letti gli atti, rinvia la causa all'udienza del 30/09/2026 "
            "alle ore 10:00. Si comunichi."
        ),
    }
    historical_judgment = {
        "filename": "sentenza-storica-separata.pdf",
        "ocr_text": (
            "TRIBUNALE ORDINARIO. SENTENZA. Il Giudice, definitivamente decidendo, "
            "accerta il diritto e condanna il Ministero alle spese."
        ),
    }

    u = build_legal_event_understanding(
        parsed,
        {},
        attachments=[current_order, historical_judgment],
    )

    assert u["classification"]["primary_event"] == "rinvio_udienza"
    assert not any("Esame sentenza" in item["deadline_type"] for item in u["deadlines"])
    assert not any(item.get("creates_notification_candidate") for item in u["notifications"])
    assert not any(item.get("notification_case") == "judgment_to_notify_review" for item in u["notifications"])
    binding = u["input_quality"]["source_binding"]
    assert binding["status"] == "bound"
    assert "ordinanza-rinvio-corrente.pdf" in binding["selected_sources"]
    assert "sentenza-storica-separata.pdf" in binding["excluded_sources"]


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
