"""Test per l'agenda digitale."""

import json

import pytest
from datetime import date, datetime, timedelta

from pct.agenda import Agenda, Appuntamento, TipoAppuntamento, StatoAppuntamento
from pct.ical_import import EventoImportato
from pct.storage import StudioDB


@pytest.fixture
def agenda(tmp_path):
    return Agenda(db_path=str(tmp_path / "appuntamenti.json"))


def test_agenda_sqlite_importa_json_tenant_pec_quando_db_vuoto(tmp_path):
    agenda_path = tmp_path / "agenda" / "appuntamenti.json"
    agenda_path.parent.mkdir(parents=True)
    agenda_path.write_text(
        json.dumps(
            {
                "app-pec": {
                    "id": "app-pec",
                    "titolo": "Presidio PEC - Comunicazione",
                    "tipo": TipoAppuntamento.SCADENZA.value,
                    "stato": StatoAppuntamento.PROGRAMMATO.value,
                    "data_ora": "2026-10-29T09:00:00",
                    "durata_minuti": 30,
                    "luogo": "Agenda studio",
                    "note": "Fonte: pipeline PEC audit-grade.",
                    "external_uid": "PEC_AUDIT:msg-1:deadline",
                    "external_provider": "pec_audit",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    studio_db = StudioDB.get(str(tmp_path / "studio.db"))
    assert studio_db.conn.execute("SELECT COUNT(*) FROM appuntamenti").fetchone()[0] == 0

    agenda = Agenda(db_path=str(agenda_path), studio_db=studio_db)

    assert agenda.get("app-pec") is not None
    assert studio_db.conn.execute("SELECT COUNT(*) FROM appuntamenti").fetchone()[0] == 1


def test_agenda_sqlite_salva_anche_mirror_json_tenant(tmp_path):
    agenda_path = tmp_path / "agenda" / "appuntamenti.json"
    studio_db = StudioDB.get(str(tmp_path / "studio.db"))
    agenda = Agenda(db_path=str(agenda_path), studio_db=studio_db)

    appuntamento = agenda.aggiungi(
        titolo="Presidio PEC sincronizzato",
        tipo=TipoAppuntamento.SCADENZA,
        data_ora="2026-12-17T09:00:00",
        durata_minuti=30,
        luogo="Agenda studio",
        external_uid="PEC_AUDIT:msg-2:deadline",
        external_provider="pec_audit",
    )

    raw = json.loads(agenda_path.read_text(encoding="utf-8"))
    assert appuntamento.id in raw
    assert raw[appuntamento.id]["external_provider"] == "pec_audit"
    assert studio_db.conn.execute("SELECT COUNT(*) FROM appuntamenti").fetchone()[0] == 1


def _domani_ore(ora: str) -> str:
    d = date.today() + timedelta(days=1)
    return f"{d.isoformat()}T{ora}:00"


def test_aggiungi_appuntamento(agenda):
    app = agenda.aggiungi(
        titolo="Udienza RG 1234/2024",
        tipo=TipoAppuntamento.UDIENZA,
        data_ora=_domani_ore("10:00"),
        durata_minuti=60,
        luogo="Aula 3 - Tribunale Milano",
        cliente="Mario Rossi",
    )
    assert app.id is not None
    assert app.titolo == "Udienza RG 1234/2024"
    assert app.tipo == TipoAppuntamento.UDIENZA
    assert app.stato == StatoAppuntamento.PROGRAMMATO


def test_persistenza(tmp_path):
    """Verifica che gli appuntamenti vengano salvati e ricaricati."""
    db = str(tmp_path / "agenda.json")
    a1 = Agenda(db_path=db)
    app = a1.aggiungi(
        titolo="Test persistenza",
        tipo=TipoAppuntamento.CONSULTAZIONE,
        data_ora=_domani_ore("14:00"),
    )
    a2 = Agenda(db_path=db)
    caricato = a2.get(app.id)
    assert caricato is not None
    assert caricato.titolo == "Test persistenza"


def test_sovrapposizione_rilevata(agenda):
    agenda.aggiungi(
        titolo="Primo",
        tipo=TipoAppuntamento.RIUNIONE,
        data_ora=_domani_ore("10:00"),
        durata_minuti=60,
    )
    with pytest.raises(ValueError, match="Sovrapposizione"):
        agenda.aggiungi(
            titolo="Secondo sovrapposto",
            tipo=TipoAppuntamento.RIUNIONE,
            data_ora=_domani_ore("10:30"),
            durata_minuti=60,
        )


def test_nessuna_sovrapposizione_consecutivi(agenda):
    agenda.aggiungi(
        titolo="Primo",
        tipo=TipoAppuntamento.RIUNIONE,
        data_ora=_domani_ore("09:00"),
        durata_minuti=60,
    )
    app2 = agenda.aggiungi(
        titolo="Secondo consecutivo",
        tipo=TipoAppuntamento.RIUNIONE,
        data_ora=_domani_ore("10:00"),
        durata_minuti=60,
    )
    assert app2 is not None


def test_modifica_appuntamento(agenda):
    app = agenda.aggiungi(
        titolo="Da modificare",
        tipo=TipoAppuntamento.ALTRO,
        data_ora=_domani_ore("11:00"),
    )
    modificato = agenda.modifica(app.id, titolo="Titolo aggiornato", note="Nota aggiunta")
    assert modificato.titolo == "Titolo aggiornato"
    assert modificato.note == "Nota aggiunta"


def test_cambia_stato(agenda):
    app = agenda.aggiungi(
        titolo="Udienza",
        tipo=TipoAppuntamento.UDIENZA,
        data_ora=_domani_ore("15:00"),
    )
    aggiornato = agenda.cambia_stato(app.id, StatoAppuntamento.CONFERMATO)
    assert aggiornato.stato == StatoAppuntamento.CONFERMATO


def test_elimina(agenda):
    app = agenda.aggiungi(
        titolo="Da eliminare",
        tipo=TipoAppuntamento.ALTRO,
        data_ora=_domani_ore("16:00"),
    )
    agenda.elimina(app.id)
    assert agenda.get(app.id) is None


def test_elimina_inesistente(agenda):
    with pytest.raises(KeyError):
        agenda.elimina("XXXXXXXX")


def test_per_giorno(agenda):
    domani = (date.today() + timedelta(days=1))
    agenda.aggiungi(
        titolo="Oggi",
        tipo=TipoAppuntamento.CONSULTAZIONE,
        data_ora=_domani_ore("09:00"),
    )
    risultati = agenda.per_giorno(domani)
    assert len(risultati) >= 1


def test_per_settimana(agenda):
    for h in ["09:00", "11:00", "14:00"]:
        agenda.aggiungi(
            titolo=f"App {h}",
            tipo=TipoAppuntamento.ALTRO,
            data_ora=_domani_ore(h),
            durata_minuti=30,
        )
    domani = date.today() + timedelta(days=1)
    risultati = agenda.per_settimana(date.today())
    assert len(risultati) >= 3


def test_cerca_testo(agenda):
    agenda.aggiungi(
        titolo="Udienza Bianchi",
        tipo=TipoAppuntamento.UDIENZA,
        data_ora=_domani_ore("10:00"),
        cliente="Giovanni Bianchi",
    )
    agenda.aggiungi(
        titolo="Consulenza Rossi",
        tipo=TipoAppuntamento.CONSULTAZIONE,
        data_ora=_domani_ore("12:00"),
        cliente="Mario Rossi",
    )
    risultati = agenda.cerca(testo="bianchi")
    assert len(risultati) == 1
    assert "Bianchi" in risultati[0].titolo


def test_cerca_per_tipo(agenda):
    agenda.aggiungi(
        titolo="Udienza 1",
        tipo=TipoAppuntamento.UDIENZA,
        data_ora=_domani_ore("09:00"),
        durata_minuti=30,
    )
    agenda.aggiungi(
        titolo="Deposito 1",
        tipo=TipoAppuntamento.DEPOSITO,
        data_ora=_domani_ore("10:00"),
        durata_minuti=30,
    )
    udienze = agenda.cerca(tipo=TipoAppuntamento.UDIENZA)
    assert all(a.tipo == TipoAppuntamento.UDIENZA for a in udienze)


def test_statistiche(agenda):
    agenda.aggiungi(
        titolo="App stats",
        tipo=TipoAppuntamento.RIUNIONE,
        data_ora=_domani_ore("09:00"),
    )
    stats = agenda.statistiche()
    assert "totale" in stats
    assert "per_tipo" in stats
    assert stats["totale"] >= 1


def test_annullato_non_causa_sovrapposizione(agenda):
    app = agenda.aggiungi(
        titolo="Annullato",
        tipo=TipoAppuntamento.RIUNIONE,
        data_ora=_domani_ore("10:00"),
        durata_minuti=60,
    )
    agenda.cambia_stato(app.id, StatoAppuntamento.ANNULLATO)
    # Deve poter aggiungere nello stesso slot
    app2 = agenda.aggiungi(
        titolo="Nuovo nello stesso slot",
        tipo=TipoAppuntamento.RIUNIONE,
        data_ora=_domani_ore("10:00"),
        durata_minuti=60,
    )
    assert app2 is not None


def test_serializzazione_roundtrip(agenda):
    app = agenda.aggiungi(
        titolo="Roundtrip",
        tipo=TipoAppuntamento.SCADENZA,
        data_ora=_domani_ore("08:00"),
        note="Nota di test",
        cliente="Cliente test",
    )
    d = app.to_dict()
    ricostruito = Appuntamento.from_dict(d)
    assert ricostruito.titolo == app.titolo
    assert ricostruito.tipo == app.tipo
    assert ricostruito.stato == app.stato
    assert ricostruito.note == app.note


def test_upsert_evento_esterno_crea_e_aggiorna(agenda):
    evento = EventoImportato(
        uid="evt-123",
        titolo="Call cliente",
        data_ora=_domani_ore("10:00"),
        durata_minuti=45,
        luogo="Teams",
        descrizione="Prima versione",
        organizzatore="calendar@example.com",
    )
    creato = agenda.upsert_da_evento_importato(
        evento,
        provider="google",
        source_url="https://calendar.example.com/feed.ics",
        profile_id="prof1",
        default_tipo=TipoAppuntamento.RIUNIONE,
        reminder_minuti=30,
    )
    assert creato["outcome"] == "created"
    assert len(agenda.tutti()) == 1
    app = agenda.tutti()[0]
    assert app.external_uid == "evt-123"
    assert app.tipo == TipoAppuntamento.RIUNIONE
    assert app.reminder_minuti == 30

    evento_aggiornato = EventoImportato(
        uid="evt-123",
        titolo="Call cliente aggiornata",
        data_ora=_domani_ore("11:00"),
        durata_minuti=60,
        luogo="Studio",
        descrizione="Seconda versione",
        organizzatore="calendar@example.com",
    )
    aggiornato = agenda.upsert_da_evento_importato(
        evento_aggiornato,
        provider="google",
        source_url="https://calendar.example.com/feed.ics",
        profile_id="prof1",
        default_tipo=TipoAppuntamento.RIUNIONE,
        reminder_minuti=30,
    )
    assert aggiornato["outcome"] == "updated"
    assert len(agenda.tutti()) == 1
    app_finale = agenda.tutti()[0]
    assert app_finale.titolo == "Call cliente aggiornata"
    assert app_finale.data_ora.endswith("11:00:00")


def test_upsert_evento_esterno_skippa_se_gia_allineato(agenda):
    evento = EventoImportato(
        uid="evt-456",
        titolo="Evento stabile",
        data_ora=_domani_ore("12:00"),
        durata_minuti=30,
    )
    agenda.upsert_da_evento_importato(
        evento,
        provider="outlook",
        source_url="https://outlook.example.com/calendar.ics",
        profile_id="prof2",
    )
    report = agenda.upsert_da_evento_importato(
        evento,
        provider="outlook",
        source_url="https://outlook.example.com/calendar.ics",
        profile_id="prof2",
    )
    assert report["outcome"] == "skipped"
    assert len(agenda.tutti()) == 1


def test_upsert_evento_esterno_consente_sovrapposizione_per_presidi_automatici(agenda):
    primo = EventoImportato(
        uid="pec-1",
        titolo="Presidio PEC 1",
        data_ora=_domani_ore("09:00"),
        durata_minuti=30,
    )
    secondo = EventoImportato(
        uid="pec-2",
        titolo="Presidio PEC 2",
        data_ora=_domani_ore("09:00"),
        durata_minuti=30,
    )

    assert agenda.upsert_da_evento_importato(primo, provider="pec_audit")["outcome"] == "created"
    assert agenda.upsert_da_evento_importato(secondo, provider="pec_audit")["outcome"] == "conflict"
    assert agenda.upsert_da_evento_importato(secondo, provider="pec_audit", allow_overlap=True)["outcome"] == "created"
    assert len(agenda.tutti()) == 2
