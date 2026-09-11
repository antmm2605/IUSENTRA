from datetime import date, timedelta

from pct.agenda import Agenda, StatoAppuntamento, TipoAppuntamento
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from scripts.audit_duplicate_presidia import apply_paths, audit_paths


def _paths(tmp_path):
    tenant_root = tmp_path / "tenant"
    return {
        "EMAIL_CASELLA_DB": str(tenant_root / "email" / "casella.json"),
        "FASCICOLI_DB": str(tenant_root / "fascicoli" / "fascicoli.json"),
        "SCADENZIARIO_DB": str(tenant_root / "scadenziario" / "scadenze.json"),
        "AGENDA_DB": str(tenant_root / "agenda" / "appuntamenti.json"),
    }


def test_audit_duplicate_presidia_annulla_solo_automatici_non_ambigui(tmp_path):
    paths = _paths(tmp_path)
    due_day = (date.today() + timedelta(days=21)).isoformat()
    at_time = f"{due_day}T09:30:00"
    title = "Deposito note scritte 127-ter - RG 1733/2026"

    deadlines = GestioneScadenziario(paths["SCADENZIARIO_DB"])
    agenda = Agenda(paths["AGENDA_DB"])
    first_agenda = agenda.aggiungi(
        titolo=title,
        tipo=TipoAppuntamento.SCADENZA,
        data_ora=at_time,
        durata_minuti=30,
        procedimento="FASC-1",
        note="PEC_AUDIT:pec-prima\nFonte: PEC cancelleria.",
        external_uid="PEC_AUDIT:pec-prima:deadline",
        allow_overlap=True,
    )
    second_agenda = agenda.aggiungi(
        titolo=title,
        tipo=TipoAppuntamento.SCADENZA,
        data_ora=at_time,
        durata_minuti=30,
        procedimento="FASC-1",
        note="docpresidio:doc-seconda\nFonte: documento fascicolo indicizzato da Lex AI.",
        external_uid="docpresidio:doc-seconda:deadline",
        allow_overlap=True,
    )
    first_deadline = deadlines.nuova(
        titolo=title,
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza=due_day,
        id_fascicolo="FASC-1",
        note="PEC_AUDIT:pec-prima\nFonte: PEC cancelleria.",
        id_appuntamento=first_agenda.id,
        source_event_type="comunicazione_cancelleria",
    )
    second_deadline = deadlines.nuova(
        titolo=title,
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza=due_day,
        id_fascicolo="FASC-1",
        note="docpresidio:doc-seconda\nFonte: documento fascicolo indicizzato da Lex AI.",
        id_appuntamento=second_agenda.id,
        source_event_type="fascicolo_documenti_audit",
    )

    before = audit_paths("studio-test", paths)
    assert before["summary"] == {"suspect_groups": 2, "repairable_groups": 2, "review_groups": 0}

    applied = apply_paths("studio-test", paths)
    assert applied["errors"] == []
    assert applied["deadlines_cancelled"] == 1
    assert applied["agenda_cancelled"] == 1
    assert applied["deadlines_enriched"] == 1

    after_deadlines = GestioneScadenziario(paths["SCADENZIARIO_DB"])
    deadline_rows = [after_deadlines.get(first_deadline.id), after_deadlines.get(second_deadline.id)]
    assert all(row is not None for row in deadline_rows)
    open_deadlines = [row for row in deadline_rows if row.stato == StatoTermine.APERTO]
    cancelled_deadlines = [row for row in deadline_rows if row.stato == StatoTermine.ANNULLATO]
    assert len(open_deadlines) == 1
    assert len(cancelled_deadlines) == 1
    assert "PEC_AUDIT:pec-prima" in open_deadlines[0].note
    assert "docpresidio:doc-seconda" in open_deadlines[0].note
    assert "Doppione automatico annullato" in cancelled_deadlines[0].note

    after_agenda = Agenda(paths["AGENDA_DB"])
    agenda_rows = [after_agenda.get(first_agenda.id), after_agenda.get(second_agenda.id)]
    assert sum(1 for row in agenda_rows if row.stato == StatoAppuntamento.PROGRAMMATO) == 1
    assert sum(1 for row in agenda_rows if row.stato == StatoAppuntamento.ANNULLATO) == 1
    assert after_agenda.get(open_deadlines[0].id_appuntamento).stato == StatoAppuntamento.PROGRAMMATO

    after = audit_paths("studio-test", paths)
    assert after["summary"] == {"suspect_groups": 0, "repairable_groups": 0, "review_groups": 0}


def test_audit_duplicate_presidia_esclude_pec_ricevute_e_voci_manuali(tmp_path):
    paths = _paths(tmp_path)
    due_day = (date.today() + timedelta(days=14)).isoformat()
    at_time = f"{due_day}T10:00:00"
    title = "PEC ricevuta - RG 1733/2026"

    agenda = Agenda(paths["AGENDA_DB"])
    for index in range(2):
        agenda.aggiungi(
            titolo=title,
            tipo=TipoAppuntamento.ALTRO,
            data_ora=at_time,
            durata_minuti=15,
            procedimento="FASC-PEC",
            note=f"PEC_RICEZIONE:msg-{index}\nVoce informativa di ricezione.",
            external_uid=f"PEC_RICEZIONE:msg-{index}",
            allow_overlap=True,
        )

    deadlines = GestioneScadenziario(paths["SCADENZIARIO_DB"])
    for index in range(2):
        deadlines.nuova(
            titolo="Promemoria manuale fascicolo RG 1733/2026",
            tipo=TipoTermine.ADEMPIMENTO,
            data_scadenza=due_day,
            id_fascicolo="FASC-PEC",
            note=f"Inserito manualmente {index}",
        )

    audit = audit_paths("studio-test", paths)
    assert audit["summary"] == {"suspect_groups": 0, "repairable_groups": 0, "review_groups": 0}
