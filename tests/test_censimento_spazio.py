"""Il censimento dello spazio: si misura di notte, si legge di giorno.

«Analizza manutenzione» faceva il conto dentro la richiesta HTTP. Su 262 GiB
sono minuti e il server chiude a 120 secondi: il bottone non tornava, quindi
quel numero nessuno lo vedeva mai.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from web.services import censimento_spazio as cs


def _config(tmp_path: Path) -> dict:
    return {"IUSENTRA_DATA_ROOT": str(tmp_path / "data")}


def test_senza_censimento_non_si_inventa_un_numero(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cs, "percorso_censimento", lambda cfg=None: tmp_path / "mai-scritto.json")

    assert cs.ultimo_censimento({}) is None


def test_il_censimento_si_scrive_e_si_rilegge(tmp_path: Path, monkeypatch):
    percorso = tmp_path / "intelligence" / "censimento_spazio.json"
    monkeypatch.setattr(cs, "percorso_censimento", lambda cfg=None: percorso)
    monkeypatch.setattr(
        cs,
        "esegui_censimento",
        cs.esegui_censimento,  # resta quella vera
    )
    import web.services.server_maintenance_surface as sms

    monkeypatch.setattr(
        sms,
        "run_professional_server_maintenance",
        lambda *, apply=False, config=None: {"bytes_reclaimable_label": "12,3 GiB", "applied": apply},
    )

    voce = cs.esegui_censimento({})

    assert voce["risultato"]["bytes_reclaimable_label"] == "12,3 GiB"
    assert voce["risultato"]["applied"] is False, "il censimento misura, non cancella"
    riletto = cs.ultimo_censimento({})
    assert riletto is not None
    assert riletto["risultato"]["bytes_reclaimable_label"] == "12,3 GiB"


def test_un_censimento_vecchio_si_riconosce(tmp_path: Path, monkeypatch):
    percorso = tmp_path / "censimento.json"
    vecchio = datetime.now(UTC) - timedelta(hours=50)
    percorso.write_text(
        json.dumps({"eseguito_il": vecchio.isoformat(), "risultato": {"bytes_reclaimable_label": "1 GiB"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cs, "percorso_censimento", lambda cfg=None: percorso)

    ore = cs.eta_ore(cs.ultimo_censimento({}))

    assert ore is not None and ore > cs.ORE_PRIMA_DI_DICHIARARLO_VECCHIO


def test_un_file_illeggibile_non_fa_cadere_il_pannello(tmp_path: Path, monkeypatch):
    percorso = tmp_path / "rotto.json"
    percorso.write_text("{ questo non e' json", encoding="utf-8")
    monkeypatch.setattr(cs, "percorso_censimento", lambda cfg=None: percorso)

    assert cs.ultimo_censimento({}) is None


def test_il_job_notturno_e_registrato_a_un_orario_notturno():
    from pct.scheduler_registry import template_catalog

    voce = next(t for t in template_catalog() if t.key == "censimento_spazio_notturno")

    assert voce.trigger_kind == "cron"
    assert voce.hour == "0"
    assert voce.minute == "40"
    assert voce.built_in is True
