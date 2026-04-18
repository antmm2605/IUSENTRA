from pathlib import Path

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
