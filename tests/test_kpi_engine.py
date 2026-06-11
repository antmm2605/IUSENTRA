"""Test del motore KPI direzionale (controllo di gestione)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from pct.kpi import compute_kpis

ROME = ZoneInfo("Europe/Rome")
NOW = datetime(2026, 6, 11, 12, 0, tzinfo=ROME)


def _dataset():
    return {
        "fascicoli": [
            {"id": "F-1", "stato": "aperto", "valore": "10.000,00", "cliente_id": "C-1"},
            {"id": "F-2", "stato": "aperto", "valore": "5000", "cliente_id": "C-2"},
            {"id": "F-3", "stato": "chiuso", "valore": "2.500,50", "cliente_id": "C-1"},
        ],
        "scadenze": [
            {"id": "S-1", "fascicolo_id": "F-1", "data": "2026-06-09", "completata": False},  # scaduta
            {"id": "S-2", "fascicolo_id": "F-1", "data": "2026-06-13", "completata": False},  # critica (entro 7gg)
            {"id": "S-3", "fascicolo_id": "F-2", "data": "2026-12-01", "completata": False},  # lontana
            {"id": "S-4", "fascicolo_id": "F-2", "data": "2026-06-10", "completata": True},   # completata
        ],
        "udienze": [
            {"id": "U-1", "fascicolo_id": "F-1", "data_ora": "2026-06-15T09:30:00"},  # entro 30
            {"id": "U-2", "fascicolo_id": "F-2", "data_ora": "2026-07-20T10:00:00"},  # entro 60
            {"id": "U-3", "fascicolo_id": "F-3", "data_ora": "2026-09-01T10:00:00"},  # entro 90
        ],
        "parcelle": [
            {"id": "P-1", "cliente_id": "C-1", "importo": "1.220,00", "stato": "pagata"},
            {"id": "P-2", "cliente_id": "C-2", "importo": "500,00", "stato": "insoluta", "scadenza_pagamento": "2026-05-01"},  # scaduta
            {"id": "P-3", "cliente_id": "C-2", "importo": "300,00", "stato": "emessa", "scadenza_pagamento": "2026-12-01"},
        ],
        "timesheet": [
            {"id": "T-1", "fascicolo_id": "F-1", "utente_id": "AVV-1", "minuti": 120, "fatturabile": True, "fatturato": False, "tariffa_oraria": "150"},
            {"id": "T-2", "fascicolo_id": "F-1", "utente_id": "AVV-2", "minuti": 60, "fatturabile": True, "fatturato": True, "tariffa_oraria": "150"},
            {"id": "T-3", "fascicolo_id": "F-2", "utente_id": "AVV-1", "minuti": 30, "fatturabile": False, "fatturato": False, "tariffa_oraria": "150"},
        ],
    }


def test_kpi_pratiche_e_valore():
    k = compute_kpis(now=NOW, **_dataset())
    assert k["pratiche"]["aperte"] == 2
    assert k["pratiche"]["chiuse"] == 1
    assert k["pratiche"]["valoreTotale"] == 17500.5


def test_kpi_scadenze_critiche_e_scadute():
    k = compute_kpis(now=NOW, **_dataset())
    assert k["scadenze"]["scadute"] == 1     # S-1
    assert k["scadenze"]["critiche"] == 2    # S-1 (scaduta) + S-2 (entro 7gg)
    assert k["scadenze"]["totaliAperte"] == 3


def test_kpi_udienze_finestre():
    k = compute_kpis(now=NOW, **_dataset())
    assert k["udienze"]["prossimi30"] == 1
    assert k["udienze"]["prossimi60"] == 2
    assert k["udienze"]["prossimi90"] == 3


def test_kpi_economia_incassi_insoluti_wip():
    k = compute_kpis(now=NOW, **_dataset())
    eco = k["economia"]
    assert eco["parcelleEmesse"] == 3
    assert eco["incassato"] == 1220.0
    assert eco["insoluto"] == 800.0
    assert eco["insolutoScaduto"] == 500.0   # solo P-2 scaduta
    # WIP = 120 minuti non fatturati * 150/h = 2h * 150 = 300
    assert eco["wip"] == 300.0


def test_kpi_tempo_e_produttivita():
    k = compute_kpis(now=NOW, **_dataset())
    tempo = k["tempo"]
    assert tempo["minutiTotali"] == 210
    assert tempo["minutiNonFatturati"] == 120
    assert tempo["perProfessionista"]["AVV-1"] == 150
    assert tempo["perFascicolo"]["F-1"] == 180


def test_kpi_marginalita_per_cliente():
    k = compute_kpis(now=NOW, **_dataset())
    assert k["marginalitaPerCliente"]["C-1"] == 1220.0
    assert "C-2" not in k["marginalitaPerCliente"]  # nessuna parcella pagata per C-2


def test_kpi_rischio_operativo_fascicolo():
    k = compute_kpis(now=NOW, **_dataset())
    rischi = {r["fascicoloId"]: r for r in k["rischioOperativo"]}
    # F-1 ha 1 scadenza scaduta (2pt) + udienza imminente entro 7gg (3pt) = 5 -> alto
    assert rischi["F-1"]["livello"] == "alto"
    assert rischi["F-1"]["udienzaImminente"] is True


def test_kpi_gestisce_dataset_vuoto_e_date_miste():
    k = compute_kpis(now=NOW)
    assert k["pratiche"]["totale"] == 0
    assert k["economia"]["incassato"] == 0.0
    # date naive e aware mescolate non devono far crashare
    mixed = compute_kpis(
        now=None,
        udienze=[{"id": "U", "fascicolo_id": "F", "data_ora": "2026-06-15T09:00:00+02:00"}, {"id": "U2", "data_ora": datetime(2026, 6, 16, 9, 0)}],
    )
    assert "udienze" in mixed
