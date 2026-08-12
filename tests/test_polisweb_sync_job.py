"""Job periodico sync Polisweb (Fase 3): canale P12, selezione, watermark.

Verifica che il job giri solo con certificato P12/PEM (canale "reale"), che
selezioni i fascicoli civili con RG, che rispetti il watermark (no re-sync
troppo frequente), che sia a lotti e che il template sia governato in console.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from pct.polisweb_sync_job import (
    esegui_sync_polisweb,
    studio_auth_mode,
)
from pct.scheduler_registry import default_scheduler_templates

TZ = timezone(timedelta(hours=2))
NOW = datetime(2026, 8, 12, 10, 0, tzinfo=TZ)


def _config(fmt: str) -> SimpleNamespace:
    return SimpleNamespace(config=SimpleNamespace(firma=SimpleNamespace(backend_firma_operativo_safe=fmt)))


def _fascicolo(fid: str, **overrides):
    base = dict(id=fid, numero_rg="100", anno_rg=2026, codice_ufficio_portale="0580010", tribunale="MILANO", events_sync_enabled=True, stato="APERTO")
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeFascicoli:
    def __init__(self, fascicoli):
        self._fascicoli = fascicoli

    def tutti(self):
        return list(self._fascicoli)


# --- Canale ----------------------------------------------------------------------


def test_auth_mode_da_config():
    assert studio_auth_mode(_config("p12")) == "reale"
    assert studio_auth_mode(_config("pem")) == "reale"
    assert studio_auth_mode(_config("pkcs11")) == "pkcs11"
    assert studio_auth_mode(_config("nessuno")) == "demo"


def test_job_saltato_senza_certificato_server(tmp_path):
    report = esegui_sync_polisweb(
        config_studio=_config("pkcs11"),
        get_fascicoli=lambda: _FakeFascicoli([_fascicolo("F1")]),
        get_clienti=lambda: None,
        get_scadenziario=lambda: None,
        state_path=str(tmp_path / "state.json"),
        now=NOW,
        sync_fn=lambda *a, **k: {"ok": True},
    )
    assert report["skipped"] is True
    assert report["reason"] == "presidio_manuale"
    assert report["sincronizzati"] == 0


# --- Selezione e watermark -------------------------------------------------------


def test_seleziona_solo_fascicoli_con_rg_e_ufficio(tmp_path):
    chiamate = []

    def fake_sync(fid, **kwargs):
        chiamate.append(fid)
        return {"ok": True, "proposte_scadenze": 1}

    fascicoli = [
        _fascicolo("F1"),
        _fascicolo("F2", numero_rg=""),  # senza RG → escluso
        _fascicolo("F3", events_sync_enabled=False),  # sync disattivato → escluso
        _fascicolo("F4", stato="ARCHIVIATO"),  # archiviato → escluso
    ]
    report = esegui_sync_polisweb(
        config_studio=_config("p12"),
        get_fascicoli=lambda: _FakeFascicoli(fascicoli),
        get_clienti=lambda: None,
        get_scadenziario=lambda: None,
        state_path=str(tmp_path / "state.json"),
        now=NOW,
        sync_fn=fake_sync,
    )
    assert chiamate == ["F1"]
    assert report["sincronizzati"] == 1
    assert report["proposte"] == 1


def test_watermark_evita_risync_troppo_frequente(tmp_path):
    state = str(tmp_path / "state.json")

    def fake_sync(fid, **kwargs):
        return {"ok": True, "proposte_scadenze": 0}

    args = dict(
        config_studio=_config("p12"),
        get_fascicoli=lambda: _FakeFascicoli([_fascicolo("F1")]),
        get_clienti=lambda: None,
        get_scadenziario=lambda: None,
        state_path=state,
        sync_fn=fake_sync,
        min_resync_minutes=180,
    )
    primo = esegui_sync_polisweb(now=NOW, **args)
    # 30 minuti dopo: entro la finestra → nessun re-sync
    secondo = esegui_sync_polisweb(now=NOW + timedelta(minutes=30), **args)
    # 4 ore dopo: oltre la finestra → risincronizza
    terzo = esegui_sync_polisweb(now=NOW + timedelta(hours=4), **args)

    assert primo["lotto"] == 1
    assert secondo["lotto"] == 0
    assert terzo["lotto"] == 1


def test_rispetta_tetto_per_giro(tmp_path):
    fascicoli = [_fascicolo(f"F{i}") for i in range(30)]
    report = esegui_sync_polisweb(
        config_studio=_config("p12"),
        get_fascicoli=lambda: _FakeFascicoli(fascicoli),
        get_clienti=lambda: None,
        get_scadenziario=lambda: None,
        state_path=str(tmp_path / "state.json"),
        now=NOW,
        max_per_run=20,
        sync_fn=lambda fid, **k: {"ok": True, "proposte_scadenze": 0},
    )
    assert report["candidati"] == 30
    assert report["lotto"] == 20


# --- Console pianificazioni ------------------------------------------------------


def test_template_governato_registrato():
    templates = {t.key: t for t in default_scheduler_templates()}
    job = templates.get("sync_polisweb_registri")
    assert job is not None
    assert job.minute == "*/30"
    assert job.hour == "7-20"
    assert job.family == "Depositi telematici"
    assert job.built_in is True
