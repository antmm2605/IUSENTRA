"""Cambio di udienza o di termine comunicato dalla cancelleria: ricezione in agenda.

Casi reali (Tribunale di Palmi, settembre 2026):
- RG 1854/2026, PEC consegnata il 10/09/2026 alle 14:58: «RINVIATO AD ALTRA UDIENZA DI
  DISCUSSIONE IL 14/04/2027 09:00 in presenza». In agenda l'udienza precedente restava
  programmata, la ricezione non compariva e la nuova udienza era intitolata «Opposizione
  alla trattazione scritta».
- RG 1733/2026, PEC consegnata il 10/09/2026 alle 16:08: «MODIFICATO TERMINE PER NOTE IN
  SOSTITUZIONE UDIENZA il 10/12/2026».

Regola: l'agenda riporta la comunicazione nel giorno e all'ora di consegna della PEC (ora
italiana), con la nuova data; l'udienza superata dello stesso fascicolo passa a «rinviato».
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from email import policy
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

from pct.agenda import Agenda, StatoAppuntamento, TipoAppuntamento
from pct.pec_change_receipt import (
    detect_schedule_change,
    receipt_datetime_rome,
    receipt_title,
    reschedule_markers,
    select_rescheduled_appointments,
)
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from tests.test_pec_audit_pipeline import _repo_con_fascicolo
from tests.test_pec_term_modification import _modifica_termine_mime, _termine_presidiato


def _it(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _profile(oggetto: str, descrizione: str, data_evento: str = "10/09/2026") -> dict[str, str]:
    return {"oggetto_evento": oggetto, "descrizione_evento": descrizione, "data_evento": data_evento}


def test_riconosce_i_cambi_di_udienza_e_di_termine_dagli_eventi_di_cancelleria():
    rinvio = detect_schedule_change(
        _profile("RINVIO AD ALTRA UDIENZA DI DISCUSSIONE", "RINVIATO AD ALTRA UDIENZA DI DISCUSSIONE IL 14/04/2027 09:00 in presenza")
    )
    assert rinvio is not None
    assert (rinvio.kind, rinvio.new_date, rinvio.new_time, rinvio.event_date) == ("rinvio_udienza", "2027-04-14", "09:00", "2026-09-10")
    assert receipt_title(rinvio, rg="1854/2026") == "PEC ricevuta: rinvio udienza al 14/04/2027 ore 09:00 - RG 1854/2026"

    termine = detect_schedule_change(
        _profile("MODIFICA TERMINE PER NOTE IN SOSTITUZIONE UDIENZA", "MODIFICATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA il 10/12/2026 00:00, ADEMPIMENTI")
    )
    assert termine is not None and termine.kind == "termine_modificato"
    assert (termine.new_date, termine.new_time) == ("2026-12-10", "")
    assert receipt_title(termine, rg="1733/2026") == "PEC ricevuta: termine modificato al 10/12/2026 - RG 1733/2026"

    # «IN DATA» è la data della registrazione, non la nuova udienza.
    rinviata = detect_schedule_change(_profile("RINVIO DI UDIENZA", "RINVIATA UDIENZA AL 02/11/2026, ORE 09:30 IN DATA 03/07/2026 Annotazioni"))
    assert rinviata is not None and (rinviata.new_date, rinviata.new_time) == ("2026-11-02", "09:30")

    revoca = detect_schedule_change(
        _profile(
            "REVOCA UDIENZA E FISSAZIONE TERMINE PER NOTE IN SOST. UDIENZA",
            "REVOCATA UDIENZA E FISSATO TERMINE PER NOTE IN SOST. UDIENZA il 08/09/2026 09:30, ADEMPIMENTI",
        )
    )
    assert revoca is not None and revoca.kind == "udienza_revocata"
    assert receipt_title(revoca) == "PEC ricevuta: udienza revocata: note scritte entro il 08/09/2026 ore 09:30"

    mancata = detect_schedule_change(
        _profile("RINVIO MANCATA COMPARIZIONE PARTI (art.309 cpc)", "UDIENZA RINVIATA AL 08/09/2026 09:00 PER MANCATA COMPARIZIONE PARTI")
    )
    assert mancata is not None and mancata.kind == "rinvio_udienza" and mancata.new_date == "2026-09-08"

    # Prima fissazione, sentenze ed estinzione non sono cambi di data.
    for oggetto, descrizione in (
        ("FISSAZIONE UDIENZA DI DISCUSSIONE", "FISSATA UDIENZA DI DISCUSSIONE IL 22/12/2026 09:30 in presenza"),
        ("FISSAZIONE TERMINE PER NOTE IN SOSTITUZIONE UDIENZA", "FISSATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA il 14/10/2026 14:00"),
        ("SENTENZA A VERBALE (art. 127 ter cpc)", "SENTENZA A VERBALE (art. 127 ter cpc) CON NUMERO 659/2026"),
        ("ESTINZIONE", "FASCICOLO ESTINTO"),
    ):
        assert detect_schedule_change(_profile(oggetto, descrizione)) is None


def test_ora_di_ricezione_in_ora_italiana_anche_con_ora_legale():
    assert receipt_datetime_rome("2026-09-10T12:58:48Z") == datetime(2026, 9, 10, 14, 58, 48)
    assert receipt_datetime_rome("2026-01-10T12:58:48Z") == datetime(2026, 1, 10, 13, 58, 48)
    assert receipt_datetime_rome("", "2026-09-10T14:08:57+02:00") == datetime(2026, 9, 10, 14, 8, 57)
    assert receipt_datetime_rome("non-una-data") is None


def _appointment(day: str, title: str, *, fascicolo: str = "F1", rg: str = "RG 1854/2026", stato: str = "PROGRAMMATO", tipo: str = "UDIENZA"):
    return SimpleNamespace(
        id=f"{day}-{title[:8]}",
        titolo=title,
        tipo=tipo,
        stato=stato,
        data_ora=f"{day}T09:00:00",
        note=f"PEC_AUDIT:pec_old\nFascicolo: {fascicolo}",
        procedimento=rg,
        external_uid="PEC_AUDIT:pec_old:deadline",
    )


def test_selezione_udienza_rinviata_e_fail_closed():
    change = detect_schedule_change(
        _profile("RINVIO AD ALTRA UDIENZA DI DISCUSSIONE", "RINVIATO AD ALTRA UDIENZA DI DISCUSSIONE IL 14/04/2027 09:00", data_evento="09/09/2026")
    )
    assert change is not None
    items = [
        _appointment("2026-09-09", "Fissazione udienza di discussione - 09/09/2026"),
        _appointment("2026-09-09", "Opposizione alla trattazione scritta ex art. 127-ter c.p.c.", tipo="UDIENZA"),
        _appointment("2026-09-09", "Udienza di altro fascicolo", fascicolo="F2", rg="RG 10/2026"),
        _appointment("2026-06-01", "Udienza già rinviata", stato="RINVIATO"),
    ]
    selected, reason = select_rescheduled_appointments(
        items, fascicolo_id="F1", rg="1854/2026", change=change, received_on=date(2026, 9, 10), message_id="pec_new"
    )
    assert [item.titolo for item in selected] == ["Fissazione udienza di discussione - 09/09/2026"]
    assert "evento di cancelleria" in reason

    senza_evento = detect_schedule_change(_profile("RINVIO DI UDIENZA", "UDIENZA RINVIATA AL 14/04/2027 09:00", data_evento=""))
    assert senza_evento is not None
    two_dates = [_appointment("2026-09-09", "Udienza di discussione"), _appointment("2026-10-06", "Udienza istruttoria")]
    selected, reason = select_rescheduled_appointments(
        two_dates, fascicolo_id="F1", rg="1854/2026", change=senza_evento, received_on=date(2026, 9, 10), message_id="pec_new"
    )
    assert selected == [] and "più udienze" in reason


def _rinvio_mime(event_day: date, new_day: date, *, rg: str = "523/2026", with_127_ter: bool = True) -> bytes:
    msg = EmailMessage()
    msg["From"] = "Tribunale di Vicenza <tribunale.vicenza@civile.ptel.giustiziacert.it>"
    msg["To"] = "studio@pec.it"
    msg["Subject"] = "POSTA CERTIFICATA: Tribunale di Vicenza Notificazione ai sensi del D.L. 179/2012"
    msg["Date"] = "Thu, 10 Sep 2026 14:58:48 +0200"
    msg["Message-ID"] = f"<rinvio-udienza-{new_day.isoformat()}@iusentra.test>"
    extra = "Già disposta la trattazione scritta ex art. 127-ter c.p.c. per la precedente udienza.\n" if with_127_ter else ""
    msg.set_content(
        f"Si da' atto che in data {_it(event_day)} alle ore 14:58 il cancelliere ROSSI MARIA ha provveduto ad inviare "
        "all'indirizzo di posta elettronica studio@pec.it il seguente messaggio:\n\n"
        f"Data Evento: {_it(event_day)}\nTipo Evento: EVENTI DI RINVIO\nOggetto: RINVIO AD ALTRA UDIENZA DI DISCUSSIONE\n"
        f"Descrizione: RINVIATO AD ALTRA UDIENZA DI DISCUSSIONE IL {_it(new_day)} 09:00 in presenza\n{extra}"
    )
    xml = f"""<Comunicazione><NumeroRuolo>{rg}</NumeroRuolo><Oggetto>RINVIO AD ALTRA UDIENZA DI DISCUSSIONE</Oggetto>
    <Contenuto><![CDATA[Ufficio: TRIBUNALE ORDINARIO DI VICENZA
    Numero di Ruolo generale: {rg}
    Giudice: GABUTTI CARLO
    Data Evento: {_it(event_day)}
    Tipo Evento: EVENTI DI RINVIO
    Oggetto: RINVIO AD ALTRA UDIENZA DI DISCUSSIONE
    Descrizione: RINVIATO AD ALTRA UDIENZA DI DISCUSSIONE IL {_it(new_day)} 09:00 in presenza]]></Contenuto></Comunicazione>""".encode()
    msg.add_attachment(xml, maintype="application", subtype="xml", filename="Comunicazione.xml")
    return msg.as_bytes(policy=policy.SMTP)


def _udienza_presidiata(tmp_path: Path, fascicolo_id: str, day: date):
    title = f"Fissazione udienza di discussione - {_it(day)} - RG 523/2026"
    appointment = Agenda(str(tmp_path / "agenda.json")).aggiungi(
        title,
        TipoAppuntamento.UDIENZA,
        f"{day.isoformat()}T09:00:00",
        allow_overlap=True,
        external_uid="PEC_AUDIT:pec_fissazione:deadline",
        external_provider="pec_audit",
        external_profile_id="pec_scadenziario",
        note=f"PEC_AUDIT:pec_fissazione\nFascicolo: {fascicolo_id}\nFonte: pipeline PEC audit-grade.",
        procedimento="RG 523/2026",
    )
    deadline = GestioneScadenziario(str(tmp_path / "scadenze.json")).nuova(
        titolo=title,
        tipo=TipoTermine.UDIENZA,
        data_scadenza=day.isoformat(),
        id_fascicolo=fascicolo_id,
        note="PEC_AUDIT:pec_fissazione",
        id_appuntamento=appointment.id,
    )
    return appointment, deadline


def test_rinvio_udienza_ricezione_in_agenda_udienza_precedente_rinviata_e_titolo_corretto(tmp_path):
    repo, fascicolo = _repo_con_fascicolo(tmp_path)
    today = date.today()
    # Differimento comunicato prima dell'udienza: l'evento di cancelleria è di oggi.
    old_day, new_day = today + timedelta(days=3), today + timedelta(days=200)
    old_appointment, old_deadline = _udienza_presidiata(tmp_path, fascicolo.id, old_day)

    ingest = repo.ingest_mime(
        _rinvio_mime(today, new_day), account_email="studio@pec.it", folder="INBOX", imap_uid="INBOX:UID:77", actor="pytest"
    )
    report = repo.run_pending_jobs(limit=40)
    link = next(job["result"] for job in report["jobs"] if job["job_type"] == "link")
    message_id = str(ingest["id"])

    receipt_result = link["auto_deadline"]["change_receipt"]
    assert receipt_result["ok"] is True and receipt_result["recorded"] == "created"
    assert receipt_result["received_at"] == "2026-09-10T14:58"
    assert receipt_result["rescheduled_agenda_ids"] == [old_appointment.id]

    appointments = {item.id: item for item in Agenda(str(tmp_path / "agenda.json")).tutti()}
    receipt = appointments[receipt_result["agenda_id"]]
    assert receipt.data_ora == "2026-09-10T14:58:00"
    assert receipt.tipo == TipoAppuntamento.ALTRO and receipt.stato == StatoAppuntamento.PROGRAMMATO
    assert receipt.titolo == f"PEC ricevuta: rinvio udienza al {_it(new_day)} ore 09:00 - RG 523/2026"
    assert "Ricevuta il: 10/09/2026 alle 14:58 (ora italiana)" in receipt.note
    assert f"Data precedente: {_it(old_day)}" in receipt.note
    assert receipt.external_source_url == f"/api/pec/messages/{message_id}"
    assert f"PEC_AUDIT:{message_id}" not in receipt.note, "la riconciliazione dei presidi non deve poterla annullare"

    previous = appointments[old_appointment.id]
    assert previous.stato == StatoAppuntamento.RINVIATO
    assert reschedule_markers(previous.note)[0] == {"message_id": message_id, "new_date": new_day.isoformat()}
    assert GestioneScadenziario(str(tmp_path / "scadenze.json")).get(old_deadline.id).stato == StatoTermine.ANNULLATO

    new_hearing = next(item for item in appointments.values() if item.data_ora.startswith(new_day.isoformat()))
    assert new_hearing.tipo == TipoAppuntamento.UDIENZA and new_hearing.stato == StatoAppuntamento.PROGRAMMATO
    assert "Opposizione" not in new_hearing.titolo, "la nuova udienza non prende il nome del termine ex art. 127-ter"
    assert len(appointments) == 3

    # Rilettura della stessa PEC: nessun duplicato, nessuna riapertura.
    rerun = repo.schedule_deadline(message_id, actor="pytest")
    assert rerun["ok"] is True
    again = Agenda(str(tmp_path / "agenda.json")).tutti()
    assert len(again) == 3
    assert sum(1 for item in again if item.external_uid.startswith("PEC_RICEZIONE:")) == 1

    # Rilettura della PEC di fissazione: l'udienza superata non torna «programmata».
    old_source = repo.schedule_deadline_from_payload(
        "pec_fissazione",
        parsed={},
        report={"deadline_proposal": {"auto_create": True, "due_date": old_day.isoformat(), "deadline_kind": "udienza", "title": old_appointment.titolo}},
        message={"linked_fascicolo_id": fascicolo.id},
        actor="pytest",
        due_date=old_day.isoformat(),
    )
    assert old_source["ok"] is True and old_source.get("rescheduled_later") is True
    assert Agenda(str(tmp_path / "agenda.json")).get(old_appointment.id).stato == StatoAppuntamento.RINVIATO
    assert GestioneScadenziario(str(tmp_path / "scadenze.json")).get(old_deadline.id).stato == StatoTermine.ANNULLATO

    # Impegno completato dall'avvocato: la manutenzione non lo riapre.
    Agenda(str(tmp_path / "agenda.json")).cambia_stato(receipt.id, StatoAppuntamento.COMPLETATO)
    maintenance = repo.record_pec_schedule_change_receipts(since="2026-01-01T00:00:00Z", actor="pytest")
    assert maintenance["ok"] is True and maintenance["recorded"] == 0
    assert Agenda(str(tmp_path / "agenda.json")).get(receipt.id).stato == StatoAppuntamento.COMPLETATO


def test_modifica_termine_riporta_la_ricezione_alla_data_e_ora_di_consegna(tmp_path):
    repo, fascicolo = _repo_con_fascicolo(tmp_path)
    today = date.today()
    old_day, new_day = today + timedelta(days=2), today + timedelta(days=91)
    previous, old_appointment = _termine_presidiato(tmp_path, fascicolo.id, old_day)

    ingest = repo.ingest_mime(
        _modifica_termine_mime(today, new_day), account_email="studio@pec.it", folder="INBOX", imap_uid="INBOX:UID:88", actor="pytest"
    )
    repo.run_pending_jobs(limit=40)

    appointments = Agenda(str(tmp_path / "agenda.json")).tutti()
    receipts = [item for item in appointments if item.external_uid == f"PEC_RICEZIONE:{ingest['id']}"]
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.data_ora == "2026-09-10T16:08:00"
    assert receipt.titolo == f"PEC ricevuta: termine modificato al {_it(new_day)} - RG 523/2026"
    assert "Comunicazione ricevuta: Termine modificato" in receipt.note
    # Il termine spostato e il promemoria alla data superata restano quelli della modifica.
    assert GestioneScadenziario(str(tmp_path / "scadenze.json")).get(previous.id).data_scadenza == new_day.isoformat()
    assert Agenda(str(tmp_path / "agenda.json")).get(old_appointment.id).stato == StatoAppuntamento.RINVIATO
    assert len(appointments) == 3


def test_backfill_manutenzione_idempotente_per_pec_gia_ricevute(tmp_path):
    repo, fascicolo = _repo_con_fascicolo(tmp_path)
    today = date.today()
    ingest = repo.ingest_mime(
        _rinvio_mime(today - timedelta(days=1), today + timedelta(days=120), with_127_ter=False),
        account_email="studio@pec.it",
        folder="INBOX",
        imap_uid="INBOX:UID:99",
        actor="pytest",
    )
    repo.run_pending_jobs(limit=40)
    agenda_path = tmp_path / "agenda.json"
    agenda = Agenda(str(agenda_path))
    for item in list(agenda.tutti()):
        if item.external_uid.startswith("PEC_RICEZIONE:"):
            agenda.elimina(item.id)

    first = repo.record_pec_schedule_change_receipts(since="2026-01-01T00:00:00Z", actor="pytest")
    second = repo.record_pec_schedule_change_receipts(since="2026-01-01T00:00:00Z", actor="pytest")

    assert first["recorded"] == 1 and first["items"][0]["message_id"] == ingest["id"]
    assert second["recorded"] == 0
    assert sum(1 for item in Agenda(str(agenda_path)).tutti() if item.external_uid.startswith("PEC_RICEZIONE:")) == 1


def test_agenda_react_mostra_la_ricezione_con_etichetta_e_date():
    from web.services.react_agenda_bridge import _agenda_event

    item = SimpleNamespace(
        id="R1",
        titolo="PEC ricevuta: rinvio udienza al 14/04/2027 ore 09:00 - RG 1854/2026",
        tipo=TipoAppuntamento.ALTRO,
        stato=StatoAppuntamento.PROGRAMMATO,
        data_ora="2026-09-10T14:58:00",
        data_ora_dt=datetime(2026, 9, 10, 14, 58),
        durata_minuti=15,
        luogo="",
        tribunale="Tribunale di Palmi",
        procedimento="RG 1854/2026",
        cliente="GRANDE GIUSEPPE",
        id_cliente="",
        avvocato="",
        note="\n".join(
            (
                "PEC_RICEZIONE:pec_abc",
                "Comunicazione ricevuta: Rinvio udienza",
                "Ricevuta il: 10/09/2026 alle 14:58 (ora italiana)",
                "Nuova data: 14/04/2027 ore 09:00",
                "Data precedente: 09/09/2026 (impegno segnato come rinviato in agenda)",
                "Ufficio: Tribunale di Palmi",
                "Cliente: GRANDE GIUSEPPE",
                "Evento: RINVIO AD ALTRA UDIENZA DI DISCUSSIONE",
                "Attività per l'avvocato: leggere il provvedimento, verificare data e ora della nuova udienza.",
            )
        ),
        external_source_url="/api/pec/messages/pec_abc",
        external_uid="PEC_RICEZIONE:pec_abc",
        external_provider="pec_audit",
        external_last_sync="2026-09-10T14:59:00",
        remote_hearing_source="",
    )
    event = _agenda_event(item)
    assert event is not None
    assert event["start"] == "2026-09-10T14:58"
    assert event["legalLabel"] == "PEC ricevuta · Rinvio udienza"
    assert event["sourceKind"] == "pec" and "pec_abc" in event["sourceHref"]
    assert "Ricevuta il: 10/09/2026 alle 14:58 (ora italiana)" in event["detailLines"]
    assert "Nuova data: 14/04/2027 ore 09:00" in event["detailLines"]


def test_agenda_react_dichiara_le_udienze_rinviate():
    agenda_page = Path("frontend/src/components/AgendaPage.tsx").read_text(encoding="utf-8")
    assert "status === 'RINVIATO'" in agenda_page
    assert "`${label} (proposta da confermare)`" in agenda_page
    assert "`${label} (rinviata)`" in agenda_page


# ---------------------------------------------------------------------------
# Sentenze, estinzioni, designazioni del giudice: ricezione e termini proposti
# ---------------------------------------------------------------------------

from pct.pec_change_receipt import classify_court_communication, communication_receipt_title  # noqa: E402
from pct.pec_provvedimento_terms import is_labour_matter, propose_terms  # noqa: E402


def _cancelleria_mime(oggetto: str, descrizione: str, *, rg: str = "523/2026", ufficio: str = "TRIBUNALE ORDINARIO DI VICENZA", when: str = "Wed, 05 Aug 2026 08:39:12 +0200", tag: str = "x") -> bytes:
    msg = EmailMessage()
    msg["From"] = "posta-certificata@legalmail.it"
    msg["To"] = "studio@pec.it"
    msg["Subject"] = f"POSTA CERTIFICATA: COMUNICAZIONE {rg}"
    msg["Date"] = when
    msg["Message-ID"] = f"<cancelleria-{tag}@iusentra.test>"
    msg.set_content(
        "Messaggio di posta certificata. I dati di cancelleria sono associati a:\n"
        f"Oggetto: {oggetto}\nDescrizione: {descrizione}\n"
    )
    xml = f"""<Comunicazione><NumeroRuolo>{rg}</NumeroRuolo><Oggetto>{oggetto}</Oggetto>
    <Contenuto><![CDATA[Ufficio: {ufficio}
    Numero di Ruolo generale: {rg}
    Oggetto: {oggetto}
    Descrizione: {descrizione}]]></Contenuto></Comunicazione>""".encode()
    msg.add_attachment(xml, maintype="application", subtype="xml", filename="Comunicazione.xml")
    msg.add_attachment(b"<postacert><tipo>posta-certificata</tipo></postacert>", maintype="application", subtype="xml", filename="daticert.xml")
    return msg.as_bytes(policy=policy.SMTP)


def test_classifica_ogni_comunicazione_di_cancelleria_e_titoli():
    cases = {
        ("SENTENZA A VERBALE (art. 127 ter cpc)", "SENTENZA A VERBALE (art. 127 ter cpc) CON NUMERO 659/2026"): ("sentenza", "PEC ricevuta: sentenza n. 659/2026 - RG 215/2026"),
        ("ESTINZIONE", "FASCICOLO ESTINTO"): ("estinzione", "PEC ricevuta: estinzione del processo - RG 215/2026"),
        ("DESIGNAZIONE GIUDICE", "FASCICOLO ASSEGNATO AL GIUDICE GROSSI SABINA"): ("designazione_giudice", "PEC ricevuta: designazione del giudice GROSSI SABINA - RG 215/2026"),
        ("COSTITUZIONE PARTI", "MINISTERO DELL'ISTRUZIONE E DEL MERITO COSTITUITO, DIFESO DALL'AVVOCATURA"): ("costituzione_parti", "PEC ricevuta: costituzione di MINISTERO DELL'ISTRUZIONE E DEL MERITO - RG 215/2026"),
        ("FISSAZIONE UDIENZA DI DISCUSSIONE", "FISSATA UDIENZA DI DISCUSSIONE IL 22/12/2026 09:30 in presenza"): ("fissazione_udienza", "PEC ricevuta: fissazione udienza al 22/12/2026 ore 09:30 - RG 215/2026"),
        ("ATTO NON CODIFICATO", "ATTO decreto corretto"): ("provvedimento", "PEC ricevuta: atto non codificato: decreto corretto - RG 215/2026"),
    }
    for (oggetto, descrizione), (kind, title) in cases.items():
        comm = classify_court_communication({"oggetto_evento": oggetto, "descrizione_evento": descrizione})
        assert comm is not None and comm.kind == kind
        assert communication_receipt_title(comm, rg="215/2026") == title
    assert classify_court_communication({"oggetto_evento": "POSTA CERTIFICATA: Ricevuta protocollo"}) is None


def test_termini_proposti_per_sentenza_ed_estinzione_con_rito_del_lavoro():
    sentenza = classify_court_communication({"oggetto_evento": "SENTENZA EX ART. 429, I comma CPC", "descrizione_evento": "NUMERO 3271/2026"})
    lavoro = propose_terms(sentenza, dies_a_quo=date(2026, 8, 5), labour=True)
    ordinario = propose_terms(sentenza, dies_a_quo=date(2026, 8, 5), labour=False)
    assert [(item.code, item.due_date) for item in lavoro] == [("CIV_APPELLO_LUNGO", "2027-02-05")]
    assert "non applicata" in lavoro[0].note and "art. 133, comma 2" in lavoro[0].note
    assert ordinario[0].due_date > lavoro[0].due_date, "fuori dal lavoro agosto non si computa"

    estinzione = classify_court_communication({"oggetto_evento": "ESTINZIONE", "descrizione_evento": "FASCICOLO ESTINTO"})
    assert [item.code for item in propose_terms(estinzione, dies_a_quo=date(2026, 9, 11), labour=True)] == ["CIV_APPELLO_LUNGO"]
    civile = propose_terms(estinzione, dies_a_quo=date(2026, 9, 11), labour=False)
    assert [(item.code, item.due_date) for item in civile] == [("CIV_APPELLO_LUNGO", "2027-03-11"), ("CIV_RECLAMO_ESTINZIONE_308", "2026-09-21")]

    designazione = classify_court_communication({"oggetto_evento": "DESIGNAZIONE GIUDICE", "descrizione_evento": "FASCICOLO ASSEGNATO AL GIUDICE ROSSI"})
    assert propose_terms(designazione, dies_a_quo=date(2026, 9, 11), labour=True) == []
    assert is_labour_matter("771/2025/LAV") and is_labour_matter("", "TRIBUNALE DI PALMI SEZIONE LAVORO")
    assert not is_labour_matter("523/2026", "TRIBUNALE ORDINARIO DI VICENZA")


def _run_cancelleria(repo, mime: bytes, uid: str):
    ingest = repo.ingest_mime(mime, account_email="studio@pec.it", folder="INBOX", imap_uid=uid, actor="pytest")
    repo.run_pending_jobs(limit=40)
    return str(ingest["id"])


def test_sentenza_estinzione_designazione_in_agenda_alla_ricezione_con_termini_in_bozza(tmp_path):
    repo, fascicolo = _repo_con_fascicolo(tmp_path)
    today = date.today()
    sentence_day = today - timedelta(days=3)
    sentenza_id = _run_cancelleria(
        repo,
        _cancelleria_mime(
            "SENTENZA A VERBALE (art. 127 ter cpc)",
            "SENTENZA A VERBALE (art. 127 ter cpc) CON NUMERO 659/2026",
            rg="523/2026/LAV",
            when=sentence_day.strftime("%a, %d %b %Y") + " 08:39:12 +0200",
            tag="sentenza",
        ),
        "INBOX:UID:301",
    )
    estinzione_id = _run_cancelleria(
        repo,
        _cancelleria_mime("ESTINZIONE", "FASCICOLO ESTINTO", rg="523/2026/LAV", when="Fri, 11 Sep 2026 08:23:37 +0200", tag="estinzione"),
        "INBOX:UID:302",
    )
    designazione_id = _run_cancelleria(
        repo,
        _cancelleria_mime("DESIGNAZIONE GIUDICE", "FASCICOLO ASSEGNATO AL GIUDICE GROSSI SABINA", when="Tue, 23 Jun 2026 14:34:00 +0200", tag="designazione"),
        "INBOX:UID:303",
    )
    receipts = {
        item.external_uid.split(":", 1)[1]: item
        for item in Agenda(str(tmp_path / "agenda.json")).tutti()
        if item.external_uid.startswith("PEC_RICEZIONE:")
    }
    assert set(receipts) == {sentenza_id, estinzione_id, designazione_id}
    assert receipts[sentenza_id].data_ora == f"{sentence_day.isoformat()}T08:39:00"
    assert receipts[sentenza_id].titolo.startswith("PEC ricevuta: sentenza n. 659/2026")
    assert "Termine proposto (bozza da confermare nello scadenziario): Impugnazione sentenza - termine lungo" in receipts[sentenza_id].note
    assert receipts[estinzione_id].data_ora == "2026-09-11T08:23:00"
    assert receipts[estinzione_id].titolo.startswith("PEC ricevuta: estinzione del processo")
    assert receipts[designazione_id].data_ora == "2026-06-23T14:34:00"
    assert receipts[designazione_id].titolo == "PEC ricevuta: designazione del giudice GROSSI SABINA - RG 523/2026"
    assert all(item.tipo == TipoAppuntamento.ALTRO for item in receipts.values())

    drafts = [
        item
        for item in GestioneScadenziario(str(tmp_path / "scadenze.json")).tutte(solo_aperte=False)
        if "PEC_TERMINE_PROPOSTO:" in item.note
    ]
    by_message = {(item.source_message_id, item.deadline_profile_code): item for item in drafts}
    assert set(by_message) == {(sentenza_id, "CIV_APPELLO_LUNGO"), (estinzione_id, "CIV_APPELLO_LUNGO")}, "rito del lavoro: niente reclamo 308"
    sentenza_draft = by_message[(sentenza_id, "CIV_APPELLO_LUNGO")]
    assert sentenza_draft.stato == StatoTermine.BOZZA and sentenza_draft.tipo == TipoTermine.IMPUGNAZIONE
    assert sentenza_draft.perentorio is True and "Sospensione feriale non applicata" in sentenza_draft.descrizione

    # Idempotenza: nessun doppione di ricezioni o bozze.
    repo.record_pec_schedule_change_receipts(since="2026-01-01T00:00:00Z", actor="pytest")
    assert sum(1 for item in Agenda(str(tmp_path / "agenda.json")).tutti() if item.external_uid.startswith("PEC_RICEZIONE:")) == 3
    assert len([item for item in GestioneScadenziario(str(tmp_path / "scadenze.json")).tutte(solo_aperte=False) if "PEC_TERMINE_PROPOSTO:" in item.note]) == 2


def test_ricevute_di_deposito_e_protocollo_non_diventano_ricezioni_di_cancelleria(tmp_path):
    repo, _fascicolo = _repo_con_fascicolo(tmp_path)
    msg = EmailMessage()
    msg["From"] = "posta-certificata@legalmail.it"
    msg["To"] = "studio@pec.it"
    msg["Subject"] = "POSTA CERTIFICATA: Ricevuta protocollo"
    msg["Date"] = "Tue, 08 Sep 2026 11:34:57 +0200"
    msg["Message-ID"] = "<protocollo@iusentra.test>"
    msg.set_content("Ricevuta di protocollo della PEC inviata.")
    _run_cancelleria(repo, msg.as_bytes(policy=policy.SMTP), "INBOX:UID:401")
    assert not [item for item in Agenda(str(tmp_path / "agenda.json")).tutti() if item.external_uid.startswith("PEC_RICEZIONE:")]
