"""Regressioni della verifica visiva dell'area Studio (02/11/2026).

- un'udienza passata e' un esito da registrare, non un termine scaduto (regola V28,
  ``pct.scadenze_stato``): Panoramica, coda di lavoro, piano del giorno e notifiche
  dicono la stessa cosa di Scadenziario e Controllo Studio;
- la trattazione scritta (art. 127-ter c.p.c.) non porta l'etichetta dell'udienza
  audiovisiva (art. 127-bis c.p.c.);
- l'opposizione ex art. 127-ter, comma 2, c.p.c. (5 giorni dalla comunicazione) con una
  data a mesi di distanza e' «da verificare»;
- titoli e chiavi tecniche non arrivano all'avvocato.
"""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from pct.daily_plan.clock import Clock
from pct.daily_plan.collectors import Budget, CollectorContext, ScadenzarioCollector
from pct.proposte_decorse import opposizione_127_ter_incoerente
from web.services.react_regia_worklist import build_regia_worklist
from web.services.react_timesheet_bridge import _origin_label
from web.services.topbar_operational import _remote_hearing_notification_label

OGGI = date(2026, 11, 2)


def _scadenza(id_, giorni, tipo="ADEMPIMENTO", stato="APERTO", **extra):
    valori = dict(
        id=id_,
        titolo=f"Voce {id_}",
        descrizione="",
        data_scadenza=(OGGI + timedelta(days=giorni)).isoformat(),
        operational_due_at="",
        stato=SimpleNamespace(value=stato),
        tipo=SimpleNamespace(value=tipo),
        priorita="BASSA",
        id_fascicolo="fasc-1",
        id_utente_responsabile="",
        perentorio=False,
        creata_il="2026-10-01T10:00:00",
    )
    valori.update(extra)
    return SimpleNamespace(**valori)


def test_coda_di_lavoro_udienza_passata_esito_da_registrare():
    righe = build_regia_worklist(
        oggi=OGGI,
        scadenze=[_scadenza("udienza", -26, tipo="UDIENZA"), _scadenza("termine", -27)],
        parse_date=lambda value: date.fromisoformat(value),
        enum_value=lambda value: str(getattr(value, "value", value) or ""),
        short_text=lambda value, limit: str(value)[:limit],
        priorita_urgenti={"CRITICA", "ALTA"},
        agenda_rows=[], pec_rows=[], engagement_rows=[], operations=[],
    )
    badge = {riga["id"]: riga["badge"] for riga in righe}
    assert badge["scadenza-udienza"] == "ESITO UDIENZA DA REGISTRARE"
    assert badge["scadenza-termine"] == "SCADUTA DA 27 GG"


def test_piano_del_giorno_udienza_passata_non_e_termine_scaduto():
    class Store:
        def tutte(self, solo_aperte=True):
            return [_scadenza("udienza", -12, tipo="UDIENZA", perentorio=True), _scadenza("termine", -3)]

    ctx = CollectorContext(
        tenant_id="studio-a", clock=Clock(fixed_now=datetime(2026, 11, 2, 8, 0)), budget=Budget(),
        scadenziario_store=Store(),
    )
    segnali = {s.source_id: s for s in ScadenzarioCollector().collect(ctx).signals}
    assert segnali["udienza"].kind == "hearing_outcome"
    assert segnali["udienza"].title.startswith("Registrare l'esito dell'udienza")
    assert segnali["udienza"].peremptory is False
    assert segnali["termine"].kind == "deadline_fulfill"


def test_trattazione_scritta_senza_etichetta_audiovisiva():
    assert _remote_hearing_notification_label({"remoteHearingDetected": False, "remoteHearingMode": "Trattazione scritta"}) == ""
    assert _remote_hearing_notification_label({"remoteHearingDetected": True}) == "Udienza audiovisiva da verificare"


def test_opposizione_127_ter_con_data_lontana_e_da_verificare():
    lontana = _scadenza(
        "opp", 163, tipo="TERMINE_PERENTORIO", deadline_profile_code="CIV_OPPOSIZIONE_127_TER",
        titolo="Opposizione alla trattazione scritta ex art. 127-ter c.p.c. (5 giorni dalla comunicazione)",
        creata_il="2026-10-30T10:00:00",
    )
    vicina = _scadenza(
        "opp2", 3, tipo="TERMINE_PERENTORIO", deadline_profile_code="CIV_OPPOSIZIONE_127_TER",
        creata_il="2026-10-31T10:00:00",
    )
    assert opposizione_127_ter_incoerente(lontana) is True
    assert opposizione_127_ter_incoerente(vicina) is False
    assert opposizione_127_ter_incoerente(_scadenza("altro", 163)) is False


def test_origine_timesheet_in_italiano():
    assert _origin_label("manuale-ui") == "Inserimento manuale"
    assert _origin_label("timer-topbar") == "Timer della barra in alto"
    assert _origin_label("") == ""


def test_titolo_rinvio_senza_ripetizione():
    from pct.pec_pipeline import _hearing_event_summary

    parsed = {"procedural_profile": {"oggetto_evento": "RINVIO DI UDIENZA", "tipo_evento": "Rinvio"}}
    assert _hearing_event_summary(parsed, {"context": ""}) == "Rinvio udienza"
    parsed = {"procedural_profile": {"oggetto_evento": "Rinvio udienza per trattative", "tipo_evento": "Rinvio"}}
    assert _hearing_event_summary(parsed, {"context": ""}) == "Rinvio udienza per trattative"


def test_titolo_scelto_dall_avvocato_tracciato_nella_provenienza():
    from pct.scadenze_titolo_avvocato import CHIAVE_TITOLO_AVVOCATO, conserva_scelta_titolo, traccia_titolo_avvocato

    voce = SimpleNamespace(titolo="Rinvio udienza - Rinvio di udienza", provenienza={"ruleset": "v1"})
    campi = traccia_titolo_avvocato(voce, "Udienza Rossi")
    assert campi["provenienza"]["ruleset"] == "v1"
    assert campi["provenienza"][CHIAVE_TITOLO_AVVOCATO]["titolo_precedente"] == "Rinvio udienza - Rinvio di udienza"
    assert traccia_titolo_avvocato(voce, "Rinvio udienza -  Rinvio di udienza") == {}  # titolo invariato
    scelta = SimpleNamespace(provenienza=campi["provenienza"])
    aggiornamenti = conserva_scelta_titolo({"titolo": "Nuovo", "provenienza": {"ruleset": "v2"}, "data_scadenza": "2026-11-03"}, scelta)
    assert "titolo" not in aggiornamenti and aggiornamenti["data_scadenza"] == "2026-11-03"
    assert CHIAVE_TITOLO_AVVOCATO in aggiornamenti["provenienza"] and aggiornamenti["provenienza"]["ruleset"] == "v2"


def test_manutenzione_pec_non_riscrive_il_titolo_dell_avvocato(tmp_path):
    from pct.scadenze_titolo_avvocato import CHIAVE_TITOLO_AVVOCATO
    from pct.scadenziario import GestioneScadenziario, TipoTermine
    from tests.test_pec_audit_pipeline import PecAuditRepository, _gdp_hearing_message

    giorno = date.today() + timedelta(days=120)
    data_it = giorno.strftime("%d/%m/%Y")
    db = tmp_path / "scadenze.json"
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default", scadenziario_db_path=db, agenda_db_path=tmp_path / "agenda.json")
    ingest = repo.ingest_mime(_gdp_hearing_message(hearing_date=data_it), account_email="studio@example.test", folder="INBOX", imap_uid="titolo-avvocato")
    repo.run_pending_jobs(limit=30, actor="pytest")
    manager = GestioneScadenziario(str(db))
    for voce in manager.tutte(solo_aperte=False):
        manager.elimina(voce.id)
    voce = manager.nuova(
        titolo="Udienza GdP generata",
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza=giorno.isoformat(),
        note=f"PEC_AUDIT:{ingest['id']}\nTermine legale conclusivo: no",
        deadline_profile_code="PEC_AUTO_PRESIDIO",
    )
    # salvataggio dalla scheda della scadenza (stessa funzione usata dalla route di modifica)
    from pct.scadenze_titolo_avvocato import traccia_titolo_avvocato

    manager.aggiorna(voce.id, titolo="Udienza GdP — titolo scelto dall'avvocato", **traccia_titolo_avvocato(voce, "Udienza GdP — titolo scelto dall'avvocato"))

    repo.repair_pec_deadlines(actor="pytest")

    voci = GestioneScadenziario(str(db)).tutte(solo_aperte=False)
    assert len(voci) == 1
    assert voci[0].titolo == "Udienza GdP — titolo scelto dall'avvocato"
    assert voci[0].tipo == TipoTermine.UDIENZA  # il resto si riallinea comunque
    assert CHIAVE_TITOLO_AVVOCATO in voci[0].provenienza  # la traccia resta
    assert "TITOLO" not in voci[0].note


def test_manutenzione_pec_riallinea_il_titolo_generato():
    from pct.pec_pipeline import _deadline_updates_for_existing

    generata = SimpleNamespace(titolo="Rinvio udienza - Rinvio di udienza - 02/11/2026", note="PEC_AUDIT:x", descrizione="")
    scelta = SimpleNamespace(titolo="Titolo mio", note="PEC_AUDIT:x", descrizione="",
                             provenienza={"titolo_scelto_dall_avvocato": {"il": "2026-11-02T10:00:00+01:00"}})
    assert _deadline_updates_for_existing(generata, {}, title="Rinvio udienza - 02/11/2026")["titolo"] == "Rinvio udienza - 02/11/2026"
    assert "titolo" not in _deadline_updates_for_existing(scelta, {}, title="Rinvio udienza - 02/11/2026")
