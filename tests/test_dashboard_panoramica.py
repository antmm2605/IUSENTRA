"""Regressioni della Panoramica React: fuso utente e quadro dichiarato.

Due invarianti coperte qui:

1. i riferimenti temporali della Panoramica seguono ``Europe/Rome``, non
   l'ora UTC del processo (regola obbligatoria CLAUDE.md/AGENTS.md);
2. quando un archivio non risponde la Panoramica lo dichiara: uno zero da
   sorgente caduta non puo' essere presentato come uno zero reale.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from tests.test_web_bootstrap import _cfg_web
from web.app import create_app
from web.services.react_dashboard_health import (
    etichetta_sorgente,
    etichette_sorgenti,
    messaggio_sorgenti_degradate,
    segnala_sorgente_non_disponibile,
    traccia_sorgenti_panoramica,
)
from web.services.react_dashboard_time import ROME_TZ, adesso_rome, oggi_rome, rome_aware


def test_oggi_rome_segue_il_fuso_italiano():
    atteso = datetime.now(ZoneInfo("Europe/Rome")).date()
    assert oggi_rome() == atteso
    assert adesso_rome().tzinfo is ROME_TZ


def test_rome_aware_normalizza_naive_e_aware_insieme():
    """Agenda e scadenze mescolano datetime naive e con offset: vanno confrontabili."""

    naive = datetime(2026, 8, 5, 10, 0)
    aware_utc = datetime(2026, 8, 5, 8, 0, tzinfo=timezone.utc)
    normalizzato_naive = rome_aware(naive)
    normalizzato_aware = rome_aware(aware_utc)
    assert normalizzato_naive.tzinfo is not None
    assert normalizzato_aware.tzinfo is not None
    # Nessun TypeError: e' il confronto che in produzione saturava i worker.
    assert normalizzato_naive == normalizzato_aware
    assert (normalizzato_naive - normalizzato_aware) == timedelta(0)


def test_mezzanotte_italiana_non_ricade_nel_giorno_utc_precedente():
    mezzanotte_rome = datetime(2026, 8, 6, 0, 30, tzinfo=ROME_TZ)
    assert mezzanotte_rome.astimezone(timezone.utc).date() == date(2026, 8, 5)
    assert rome_aware(mezzanotte_rome.astimezone(timezone.utc)).date() == date(2026, 8, 6)


def test_registro_sorgenti_degradate_e_isolato_fuori_dal_contesto():
    # Fuori dal tracciamento la segnalazione e' inerte e non deve esplodere.
    segnala_sorgente_non_disponibile("agenda")
    with traccia_sorgenti_panoramica() as registro:
        segnala_sorgente_non_disponibile("agenda")
        segnala_sorgente_non_disponibile("pec")
        segnala_sorgente_non_disponibile("pec")
        segnala_sorgente_non_disponibile("   ")
    assert registro == {"agenda", "pec"}
    with traccia_sorgenti_panoramica() as secondo:
        pass
    assert secondo == set()


def test_etichette_e_messaggio_sono_in_italiano():
    assert etichetta_sorgente("scadenziario") == "Scadenziario"
    assert etichetta_sorgente("sorgente_ignota") == "Sorgente ignota"
    assert etichette_sorgenti(["pec", "agenda", "pec"]) == ["Agenda", "Casella PEC"]
    singolo = messaggio_sorgenti_degradate(["agenda"])
    assert singolo.startswith("Quadro parziale: l'archivio Agenda")
    plurale = messaggio_sorgenti_degradate(["agenda", "pec"])
    assert plurale.startswith("Quadro parziale: gli archivi Agenda, Casella PEC")
    assert messaggio_sorgenti_degradate([]) == ""


def test_payload_dashboard_dichiara_stato_e_ora_italiana(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "panoramica-test-key"
    client = app.test_client()
    response = client.get("/api/v1/ui/dashboard", headers={"X-API-Key": "panoramica-test-key"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] in {"ok", "parziale", "errore"}
    assert isinstance(payload["degraded_sources"], list)
    # Timestamp gia' localizzato: la UI non deve indovinare il fuso.
    generato = datetime.fromisoformat(payload["generated_at_rome"])
    assert generato.utcoffset() is not None
    if payload["status"] == "parziale":
        assert payload["warning"]
        assert payload["degraded_sources"]
    else:
        assert not payload["degraded_sources"]


def test_payload_di_errore_controllato_non_finge_dati_reali():
    from web.blueprints.api_v1_react import _dashboard_error_payload

    payload = _dashboard_error_payload()
    assert payload["status"] == "errore"
    assert payload["source"] == "errore_controllato"
    assert payload["warning"]
    assert payload["stats"]["urgentActions"] == 0
    assert payload["contracts"]["mock_fallback"] is False
