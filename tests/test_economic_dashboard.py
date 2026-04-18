from types import SimpleNamespace

from pct.economic_dashboard import build_fascicolo_economic_dashboard, build_studio_economic_dashboard
from pct.fascicoli import StatoFascicolo
from pct.fatturazione import StatoParcella


def test_dashboard_studio_calcola_kpi_e_worklist():
    fascicolo = SimpleNamespace(
        id="fas-1",
        numero="2026/001",
        titolo="Recupero crediti",
        stato=StatoFascicolo.APERTO,
        compenso_pattuito=1800.0,
    )
    parcella_emessa = SimpleNamespace(id_fascicolo="fas-1", totale=600.0, stato=StatoParcella.EMESSA)
    parcella_pagata = SimpleNamespace(id_fascicolo="fas-1", totale=300.0, stato=StatoParcella.PAGATA)
    timesheet_entry = SimpleNamespace(id_fascicolo="fas-1", minuti=120, valore_totale=240.0, fatturabile=True, username="admin")

    dashboard = build_studio_economic_dashboard(
        fascicoli=[fascicolo],
        parcelle=[parcella_emessa, parcella_pagata],
        timesheet_entries=[timesheet_entry],
        scadenze_imminenti=[{"id": "scad-1"}],
    )

    assert dashboard["scope"] == "studio"
    assert dashboard["totals"]["fatturato"] == 900.0
    assert dashboard["totals"]["incassi"] == 300.0
    assert dashboard["totals"]["insoluti"] == 600.0
    assert dashboard["top_fascicoli"][0]["numero"] == "2026/001"
    assert dashboard["produttivita_utenti"][0]["username"] == "admin"
    assert dashboard["worklist"]


def test_dashboard_fascicolo_suggerisce_conversione_commerciale():
    fascicolo = SimpleNamespace(
        id="fas-1",
        numero="2026/010",
        titolo="Appello civile",
        stato=StatoFascicolo.IN_CORSO,
        compenso_pattuito=2500.0,
    )
    parcella = SimpleNamespace(id_fascicolo="fas-1", totale=1000.0, stato=StatoParcella.PAGATA)
    timesheet_entry = SimpleNamespace(id_fascicolo="fas-1", minuti=180, valore_totale=360.0, fatturabile=True, username="avv")

    dashboard = build_fascicolo_economic_dashboard(
        fascicolo=fascicolo,
        parcelle=[parcella],
        timesheet_entries=[timesheet_entry],
        preventivo=SimpleNamespace(id="prev-1"),
        conferimento=None,
    )

    assert dashboard["scope"] == "fascicolo"
    assert "conferimento" in dashboard["next_action"].lower()
    assert dashboard["totals"]["incassato"] == 1000.0
    assert dashboard["top_fascicoli"][0]["titolo"] == "Appello civile"
