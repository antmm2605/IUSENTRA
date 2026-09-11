"""Modifica di un termine comunicata dalla cancelleria (art. 154 e 127-ter c.p.c.).

Caso reale: termine per note in sostituzione udienza presidiato al 10/09/2026;
la cancelleria comunica «MODIFICATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA il
10/12/2026». Il presidio deve spostare il termine, lasciare in agenda alla data
superata il messaggio della modifica e mostrare il termine alla nuova data.
"""

from __future__ import annotations

from datetime import date, timedelta
from email import policy
from email.message import EmailMessage
from pathlib import Path

from pct.agenda import Agenda, StatoAppuntamento, TipoAppuntamento
from pct.pec_term_modification import (
    activity_family,
    detect_term_modification,
    find_deadline_to_modify,
    modification_lines,
)
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from tests.test_pec_audit_pipeline import _repo_con_fascicolo


def _senza_ricezioni(items):
    """Esclude gli impegni «PEC ricevuta» (tests/test_pec_change_receipt.py)."""

    return [item for item in items if not str(item.external_uid or "").startswith("PEC_RICEZIONE:")]


def _it(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _modifica_termine_mime(event_day: date, new_day: date, *, rg: str = "523/2026") -> bytes:
    msg = EmailMessage()
    msg["From"] = "Tribunale di Vicenza <tribunale.vicenza@civile.ptel.giustiziacert.it>"
    msg["To"] = "studio@pec.it"
    msg["Subject"] = f"POSTA CERTIFICATA: TRIBUNALE ORDINARIO DI VICENZA Notificazione ai sensi del D.L. 179/2012 - RG {rg}"
    msg["Date"] = "Thu, 10 Sep 2026 16:08:00 +0200"
    msg["Message-ID"] = f"<modifica-termine-{new_day.isoformat()}@iusentra.test>"
    msg.set_content(
        f"Si da' atto che in data {_it(event_day)} alle ore 16:08 il cancelliere ROSSI MARIA ha provveduto ad inviare "
        "al Gestore dei Servizi Telematici, al sistema di posta elettronica certificata del Ministero della Giustizia "
        "per il successivo inoltro all'indirizzo di posta elettronica studio@pec.it della parte BARILARO FRANCESCO "
        "il seguente messaggio di posta elettronica certificata cui risultano allegati i documenti che nel registro "
        "di cancelleria sono associati a:\n\n"
        f"Data Evento: {_it(event_day)}\n"
        "Tipo Evento: EVENTI FASE ISTRUTTORIA\n"
        "Oggetto: MODIFICA TERMINE PER NOTE IN SOSTITUZIONE UDIENZA\n"
        f"Descrizione: MODIFICATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA il {_it(new_day)} 00:00, ADEMPIMENTI:\n"
    )
    xml = f"""<Comunicazione><NumeroRuolo>{rg}</NumeroRuolo>
    <Oggetto>MODIFICA TERMINE PER NOTE IN SOSTITUZIONE UDIENZA</Oggetto>
    <Contenuto><![CDATA[Ufficio: TRIBUNALE ORDINARIO DI VICENZA
    Numero di Ruolo generale: {rg}
    Data Evento: {_it(event_day)}
    Tipo Evento: EVENTI FASE ISTRUTTORIA
    Oggetto: MODIFICA TERMINE PER NOTE IN SOSTITUZIONE UDIENZA
    Descrizione: MODIFICATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA il {_it(new_day)} 00:00, ADEMPIMENTI:]]></Contenuto>
    </Comunicazione>""".encode("utf-8")
    msg.add_attachment(xml, maintype="application", subtype="xml", filename="Comunicazione.xml")
    return msg.as_bytes(policy=policy.SMTP)


def _termine_presidiato(tmp_path: Path, fascicolo_id: str, due: date, *, source: str = "pec_decreto_127ter"):
    title = f"Deposito note scritte ex art. 127-ter c.p.c. - {_it(due)} - RG 523/2026"
    agenda = Agenda(str(tmp_path / "agenda.json"))
    appointment = agenda.aggiungi(
        title,
        TipoAppuntamento.SCADENZA,
        f"{due.isoformat()}T09:00:00",
        allow_overlap=True,
        external_uid=f"PEC_AUDIT:{source}:deadline",
        external_provider="pec_audit",
        external_profile_id="pec_scadenziario",
        note=f"PEC_AUDIT:{source}\nFonte: pipeline PEC audit-grade.",
    )
    manager = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    deadline = manager.nuova(
        titolo=title,
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza=due.isoformat(),
        id_fascicolo=fascicolo_id,
        note=f"PEC_AUDIT:{source}\nTipo evento: decreto 127-ter",
        id_appuntamento=appointment.id,
    )
    return deadline, appointment


def _run_modifica(repo, event_day: date, new_day: date) -> tuple[dict, str]:
    ingest = repo.ingest_mime(
        _modifica_termine_mime(event_day, new_day),
        account_email="studio@pec.it",
        folder="INBOX",
        imap_uid=f"INBOX:UID:{new_day.toordinal()}",
        actor="pytest",
    )
    report = repo.run_pending_jobs(limit=40)
    link = next(job["result"] for job in report["jobs"] if job["job_type"] == "link")
    return link, str(ingest["id"])


def test_riconosce_la_modifica_del_termine_dalla_comunicazione_di_cancelleria():
    body = (
        "Si da' atto che in data 10/09/2026 alle ore 16:08 il cancelliere FAMA' PALMINA ha provveduto ad inviare ... "
        "Data Evento: 10/09/2026 Tipo Evento: EVENTI FASE ISTRUTTORIA Oggetto: MODIFICA TERMINE PER NOTE IN "
        "SOSTITUZIONE UDIENZA Descrizione: MODIFICATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA il 10/12/2026 00:00, ADEMPIMENTI:"
    )
    modification = detect_term_modification({"body": {"text": body}}, {})
    assert modification is not None
    assert modification.new_date == "2026-12-10"
    assert modification.new_time == ""
    assert modification.family == "note_scritte"
    assert modification.event_date == "2026-09-10"
    assert modification.communication.startswith("Si da' atto che in data 10/09/2026")

    proroga = detect_term_modification({"body": {"text": "PROROGA DEL TERMINE PER IL DEPOSITO DELLE MEMORIE EX ART. 171 TER al 15/01/2027"}}, {})
    assert proroga is not None and proroga.family == "memorie" and proroga.new_date == "2027-01-15"

    # Assegnazione originaria del termine e rinvio di udienza non sono modifiche di un termine.
    assert detect_term_modification({"body": {"text": "assegna termine per note scritte sino al 10/12/2026"}}, {}) is None
    assert detect_term_modification({"body": {"text": "UDIENZA RINVIATA AL 09/10/2026 09:15"}}, {}) is None
    assert activity_family("Deposito note scritte ex art. 127-ter c.p.c. - 10/09/2026") == "note_scritte"


def test_modifica_sposta_il_termine_e_lascia_in_agenda_il_messaggio_alla_data_superata(tmp_path):
    repo, fascicolo = _repo_con_fascicolo(tmp_path)
    today = date.today()
    old_day, new_day = today + timedelta(days=2), today + timedelta(days=91)
    previous, old_appointment = _termine_presidiato(tmp_path, fascicolo.id, old_day)
    GestioneScadenziario(str(tmp_path / "scadenze.json")).nuova(
        titolo="Deposito memorie ex art. 171-ter c.p.c.",
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza=(today + timedelta(days=5)).isoformat(),
        id_fascicolo=fascicolo.id,
        note="PEC_AUDIT:pec_memorie",
    )

    link, message_id = _run_modifica(repo, today, new_day)

    result = link["auto_deadline"]
    assert result["ok"] is True
    assert result["deadline_id"] == previous.id
    assert result["term_modification"]["old_date"] == old_day.isoformat()
    assert result["term_modification"]["new_date"] == new_day.isoformat()

    deadlines = GestioneScadenziario(str(tmp_path / "scadenze.json")).tutte(solo_aperte=False)
    assert len(deadlines) == 2, "nessun secondo termine per note: quello precedente viene spostato"
    moved = next(item for item in deadlines if item.id == previous.id)
    assert moved.data_scadenza == new_day.isoformat()
    assert moved.titolo == f"Deposito note scritte ex art. 127-ter c.p.c. - {_it(new_day)} - RG 523/2026"
    assert moved.tipo == TipoTermine.ADEMPIMENTO and moved.stato == StatoTermine.APERTO
    assert f"dal {_it(old_day)} al {_it(new_day)}" in moved.descrizione
    assert modification_lines(moved)[-1]["message_id"] == message_id
    assert "Comunicazione di cancelleria: Si da' atto" in moved.note
    memorie = next(item for item in deadlines if item.id != previous.id)
    assert memorie.data_scadenza == (today + timedelta(days=5)).isoformat()

    all_appointments = Agenda(str(tmp_path / "agenda.json")).tutti()
    appointments = {item.id: item for item in _senza_ricezioni(all_appointments)}
    assert len(appointments) == 2
    receipts = [item for item in all_appointments if item.external_uid == f"PEC_RICEZIONE:{message_id}"]
    assert len(receipts) == 1 and receipts[0].data_ora == "2026-09-10T16:08:00"
    reminder = appointments[old_appointment.id]
    assert reminder.data_ora.startswith(old_day.isoformat())
    assert reminder.stato == StatoAppuntamento.RINVIATO
    assert reminder.titolo.startswith(f"Termine modificato al {_it(new_day)}")
    assert "MODIFICATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA" in reminder.note
    new_appointment = appointments[moved.id_appuntamento]
    assert new_appointment.id != old_appointment.id
    assert new_appointment.data_ora == f"{new_day.isoformat()}T09:00:00"
    assert new_appointment.stato == StatoAppuntamento.PROGRAMMATO
    assert f"dal {_it(old_day)} al {_it(new_day)}" in new_appointment.note

    # Rilettura della stessa PEC: idempotente, nessun duplicato, nessuna udienza a mezzanotte.
    rerun = repo.schedule_deadline(message_id, actor="pytest")
    assert rerun["ok"] is True and rerun["already_exists"] is True
    again = GestioneScadenziario(str(tmp_path / "scadenze.json")).get(previous.id)
    assert again.data_scadenza == new_day.isoformat() and again.tipo == TipoTermine.ADEMPIMENTO
    assert again.titolo == moved.titolo
    appointments_again = _senza_ricezioni(Agenda(str(tmp_path / "agenda.json")).tutti())
    assert len(appointments_again) == 2
    assert {item.data_ora for item in appointments_again} == {f"{old_day.isoformat()}T09:00:00", f"{new_day.isoformat()}T09:00:00"}


def test_letture_successive_della_fonte_precedente_non_ripristinano_la_data_superata(tmp_path):
    repo, fascicolo = _repo_con_fascicolo(tmp_path)
    today = date.today()
    old_day, new_day = today + timedelta(days=2), today + timedelta(days=91)
    previous, old_appointment = _termine_presidiato(tmp_path, fascicolo.id, old_day)
    _run_modifica(repo, today, new_day)
    proposal = {
        "auto_create": True,
        "due_date": old_day.isoformat(),
        "deadline_kind": "termine",
        "title": f"Deposito note scritte ex art. 127-ter c.p.c. - {_it(old_day)} - RG 523/2026",
    }

    old_source = repo.schedule_deadline_from_payload(
        "pec_decreto_127ter",
        parsed={},
        report={"deadline_proposal": proposal},
        message={"linked_fascicolo_id": fascicolo.id},
        actor="pytest",
    )
    assert old_source["ok"] is True and old_source["term_modified_later"] is True

    document_presidio = repo.schedule_deadline_from_payload(
        "docpresidio:fascicolo:decreto:termine",
        parsed={},
        report={"deadline_proposal": proposal},
        message={"linked_fascicolo_id": fascicolo.id},
        actor="pytest",
        due_date=old_day.isoformat(),
    )
    assert document_presidio["ok"] is False
    assert document_presidio["superseded_by_modification"]["new_date"] == new_day.isoformat()

    deadlines = GestioneScadenziario(str(tmp_path / "scadenze.json")).tutte(solo_aperte=False)
    assert [item.data_scadenza for item in deadlines] == [new_day.isoformat()]
    reminder = Agenda(str(tmp_path / "agenda.json")).get(old_appointment.id)
    assert reminder.stato == StatoAppuntamento.RINVIATO
    assert len(_senza_ricezioni(Agenda(str(tmp_path / "agenda.json")).tutti())) == 2


def test_senza_termine_precedente_crea_il_nuovo_termine_dichiarando_la_modifica(tmp_path):
    repo, fascicolo = _repo_con_fascicolo(tmp_path)
    today = date.today()
    new_day = today + timedelta(days=91)

    link, _message_id = _run_modifica(repo, today, new_day)

    result = link["auto_deadline"]
    assert result["ok"] is True and "term_modification" not in result
    deadlines = GestioneScadenziario(str(tmp_path / "scadenze.json")).tutte(solo_aperte=False)
    assert len(deadlines) == 1
    created = deadlines[0]
    assert created.titolo == f"Deposito note scritte ex art. 127-ter c.p.c. - {_it(new_day)} - RG 523/2026 - termine modificato"
    assert created.tipo == TipoTermine.ADEMPIMENTO
    assert "Modifica termine:" in created.note
    appointment = Agenda(str(tmp_path / "agenda.json")).get(created.id_appuntamento)
    assert appointment.data_ora == f"{new_day.isoformat()}T09:00:00"
    assert "Comunicazione di cancelleria: Si da' atto" in appointment.note


def test_termine_di_altra_attivita_o_gia_completato_non_viene_spostato():
    from types import SimpleNamespace

    modification = detect_term_modification(
        {"body": {"text": "MODIFICATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA il 10/12/2026"}}, {}
    )
    items = [
        SimpleNamespace(id="m", id_fascicolo="F", stato="APERTO", tipo="ADEMPIMENTO", data_scadenza="2026-09-15", titolo="Deposito memorie 171-ter", descrizione="", note="PEC_AUDIT:x", deadline_profile_code="", source_event_type=""),
        SimpleNamespace(id="c", id_fascicolo="F", stato="COMPLETATO", tipo="ADEMPIMENTO", data_scadenza="2026-09-10", titolo="Deposito note scritte ex art. 127-ter c.p.c.", descrizione="", note="PEC_AUDIT:y", deadline_profile_code="", source_event_type=""),
        SimpleNamespace(id="altro", id_fascicolo="G", stato="APERTO", tipo="ADEMPIMENTO", data_scadenza="2026-09-10", titolo="Deposito note scritte ex art. 127-ter c.p.c.", descrizione="", note="PEC_AUDIT:z", deadline_profile_code="", source_event_type=""),
    ]
    assert find_deadline_to_modify(items, fascicolo_id="F", modification=modification, message_id="pec_new") is None


def test_notifica_web_push_della_modifica_del_termine():
    from web.services.pec_pipeline_runtime import build_pec_deadline_notification

    notification = build_pec_deadline_notification(
        {
            "deadline_id": "D1",
            "due_date": "2026-12-10",
            "agenda": {"agenda_id": "A1"},
            "term_modification": {
                "old_date": "2026-09-10",
                "new_date": "2026-12-10",
                "family_label": "Deposito note scritte ex art. 127-ter c.p.c.",
            },
        },
        source_id="D1",
        automatic=True,
    )
    assert notification["title"] == "Termine modificato dalla cancelleria"
    assert "dal 10/09/2026 al 10/12/2026" in notification["body"]
    assert notification["payload_json"]["termModified"] is True
    assert notification["payload_json"]["previousDueDate"] == "2026-09-10"


def test_rielaborazione_di_una_pec_gia_lavorata_annulla_il_doppione_e_sposta_il_termine(tmp_path):
    """PEC di modifica arrivata prima della regola: c'erano due termini, quello superato e il doppione."""

    repo, fascicolo = _repo_con_fascicolo(tmp_path)
    today = date.today()
    old_day, new_day = today + timedelta(days=1), today + timedelta(days=91)
    _link, message_id = _run_modifica(repo, today, new_day)
    manager = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    duplicate = manager.tutte(solo_aperte=False)[0]
    legacy_note = "\n".join(
        line
        for line in duplicate.note.splitlines()
        if not line.startswith(("PEC_MODIFICA_TERMINE|", "Modifica termine:", "Comunicazione di cancelleria:"))
    )
    manager.aggiorna(duplicate.id, note=legacy_note, titolo="Modifica termine per note in sostituzione udienza - RG 523/2026 Data Evento")
    previous, old_appointment = _termine_presidiato(tmp_path, fascicolo.id, old_day)

    result = repo.schedule_deadline(message_id, actor="pytest")

    assert result["ok"] is True
    assert result["duplicate_cancelled"] == duplicate.id
    assert result["deadline_id"] == previous.id
    items = {item.id: item for item in GestioneScadenziario(str(tmp_path / "scadenze.json")).tutte(solo_aperte=False)}
    assert items[duplicate.id].stato == StatoTermine.ANNULLATO
    assert f"PEC_AUDIT:{message_id}" not in items[duplicate.id].note.splitlines()
    assert items[previous.id].data_scadenza == new_day.isoformat()
    assert items[previous.id].stato == StatoTermine.APERTO
    open_items = [item for item in items.values() if item.stato == StatoTermine.APERTO]
    assert len(open_items) == 1

    appointments = _senza_ricezioni(Agenda(str(tmp_path / "agenda.json")).tutti())
    assert len(appointments) == 2
    assert Agenda(str(tmp_path / "agenda.json")).get(old_appointment.id).stato == StatoAppuntamento.RINVIATO
    assert Agenda(str(tmp_path / "agenda.json")).get(items[previous.id].id_appuntamento).data_ora.startswith(new_day.isoformat())

    # Una seconda rielaborazione non riapre il doppione.
    again = repo.schedule_deadline(message_id, actor="pytest")
    assert again["ok"] is True and again["deadline_id"] == previous.id
    assert GestioneScadenziario(str(tmp_path / "scadenze.json")).get(duplicate.id).stato == StatoTermine.ANNULLATO
