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
