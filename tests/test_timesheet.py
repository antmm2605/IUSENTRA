from pathlib import Path

from pct.economic_pipeline import build_timesheet_billing_summary, genera_parcella_da_timesheet
from pct.fatturazione import GestioneFatturazione
from pct.timesheet import GestioneTimesheet, StatoTimesheet


def test_timesheet_crea_statistiche_e_riepiloghi(tmp_path: Path):
    repo = GestioneTimesheet(db_path=str(tmp_path / "timesheet.json"))

    repo.crea(
        descrizione="Studio fascicolo",
        minuti=90,
        id_cliente="cli-1",
        id_fascicolo="fas-1",
        username="mrossi",
        valore_unitario=100.0,
        fatturabile=True,
    )
    repo.crea(
        descrizione="Telefonata cliente",
        minuti=30,
        id_cliente="cli-1",
        id_fascicolo="fas-1",
        username="mrossi",
        valore_unitario=80.0,
        fatturabile=False,
        stato=StatoTimesheet.VALIDATO,
    )

    stats = repo.statistiche()
    summary = repo.riepilogo_cliente("cli-1")

    assert stats["totale_voci"] == 2
    assert stats["totale_ore"] == 2.0
    assert stats["fatturabili"] == 1
    assert stats["valore_totale"] == 150.0
    assert summary["stats"]["totale_voci"] == 2
    assert summary["per_utente"][0]["username"] == "mrossi"
    assert summary["ultimi"][0].id_cliente == "cli-1"


def test_timesheet_cambia_stato(tmp_path: Path):
    repo = GestioneTimesheet(db_path=str(tmp_path / "timesheet.json"))
    entry = repo.crea(descrizione="Deposita memoria", minuti=45, username="admin")

    updated = repo.cambia_stato(entry.id, StatoTimesheet.FATTURATO)

    assert updated.stato == StatoTimesheet.FATTURATO
    assert repo.get(entry.id).stato == StatoTimesheet.FATTURATO


def test_timesheet_genera_parcella_dalle_voci_validate(tmp_path: Path):
    timesheet = GestioneTimesheet(db_path=str(tmp_path / "timesheet.json"))
    fatturazione = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))

    voce = timesheet.crea(
        descrizione="Redazione memoria conclusionale",
        minuti=120,
        id_cliente="cli-1",
        id_fascicolo="fas-1",
        username="mrossi",
        valore_unitario=120.0,
        fatturabile=True,
        stato=StatoTimesheet.VALIDATO,
    )

    summary = build_timesheet_billing_summary(timesheet.tutte())
    payload = genera_parcella_da_timesheet(
        timesheet=timesheet,
        fatturazione=fatturazione,
        creato_da="mrossi",
        entry_ids=[voce.id],
    )

    parcella = payload["parcella"]

    assert summary["ready"] is True
    assert summary["count"] == 1
    assert parcella.origine == "timesheet"
    assert parcella.id_cliente == "cli-1"
    assert parcella.id_fascicolo == "fas-1"
    assert len(parcella.voci) == 1
    assert "Redazione memoria conclusionale" in parcella.voci[0].descrizione
    assert timesheet.get(voce.id).stato == StatoTimesheet.FATTURATO


def test_valore_a_tempo_sui_minuti_effettivi(tmp_path: Path):
    """20 minuti a 300 €/h valgono 100,00 € (non 99,00 € dalle ore arrotondate a 0,33)."""
    from pct.timesheet import VoceTimesheet

    assert VoceTimesheet(id="x", minuti=20, valore_unitario=300).valore_totale == 100.0
    assert VoceTimesheet(id="y", minuti=7, valore_unitario=95).valore_totale == 11.08
    assert VoceTimesheet(id="z", minuti=20, valore_unitario=300, fatturabile=False).valore_totale == 0.0

    timesheet = GestioneTimesheet(db_path=str(tmp_path / "timesheet.json"))
    fatturazione = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    ids = [timesheet.crea(descrizione=f"Telefonata {n}", minuti=20, id_cliente="cli-1", id_fascicolo="fas-1",
                          valore_unitario=300.0, stato=StatoTimesheet.VALIDATO).id for n in range(3)]
    summary = build_timesheet_billing_summary(timesheet.tutte())
    assert summary["ore_totali"] == 1.0
    assert summary["valore_totale"] == 300.0
    parcella = genera_parcella_da_timesheet(timesheet=timesheet, fatturazione=fatturazione, entry_ids=ids)["parcella"]
    assert [voce.importo for voce in parcella.voci] == [100.0, 100.0, 100.0]


def test_statistiche_escludono_le_voci_annullate(tmp_path: Path):
    repo = GestioneTimesheet(db_path=str(tmp_path / "timesheet.json"))
    repo.crea(descrizione="Annullata", minuti=30, valore_unitario=100.0, stato=StatoTimesheet.ANNULLATO)
    repo.crea(descrizione="Valida", minuti=60, valore_unitario=100.0)
    stats = repo.statistiche()
    assert (stats["totale_voci"], stats["annullate"], stats["totale_minuti"], stats["valore_totale"]) == (1, 1, 60, 100.0)


def test_data_attivita_nel_giorno_di_roma(tmp_path: Path, monkeypatch):
    """Alle 00:30 italiane (22:30 UTC del giorno prima) l'attività prende il giorno italiano."""
    import pct.timesheet as modulo
    from datetime import date

    monkeypatch.setattr(modulo, "oggi_roma", lambda: date(2026, 11, 8))
    voce = GestioneTimesheet(db_path=str(tmp_path / "timesheet.json")).crea(descrizione="Studio", minuti=10)
    assert voce.data_attivita == "2026-11-08"
