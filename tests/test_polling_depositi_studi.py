"""Il giro pianificato delle ricevute dei depositi passa ogni studio con i suoi percorsi (difetto 27, 09/11/2026).

Prima il lavoro ``polling_esiti_deposito`` leggeva ``FASCICOLI_DB`` e l'archivio PEC generali dell'app: con più
studi non controllava nulla. Esempi fittizi: due studi, ciascuno con un deposito INVIATO e la ricevuta di avvenuta
consegna (art. 196-sexies disp. att. c.p.c.) nel proprio archivio PEC, collegata per Message-ID.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

from flask import Flask

from pct.fascicoli import TipoFascicolo
from tests.test_ricevute_deposito_archivio import ROMA, _archivio, _pec

STUDI = ("alfa", "beta")


def _app(tmp_path: Path) -> Flask:
    registro = tmp_path / "tenants.json"
    studi = {slug: {"id": f"id-{slug}", "slug": slug, "storage_key": f"key-{slug}", "nome": slug, "stato": "attivo"}
             for slug in STUDI}
    registro.write_text(json.dumps(studi), encoding="utf-8")
    generale = tmp_path / "generale"
    generale.mkdir()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test", TESTING=True, MULTI_TENANT=True, TENANTS_REGISTRY=str(registro),
        FASCICOLI_DB=str(generale / "fascicoli" / "fascicoli.json"),
        FASCICOLI_DOCS=str(generale / "fascicoli" / "documenti"),
        FASCICOLI_ARCH=str(generale / "fascicoli" / "archivio"),
        EMAIL_CASELLA_DB=str(generale / "email" / "casella.json"),
        # Archivio generale dell'app: non è di alcuno studio e il giro non deve leggerlo.
        PEC_AUDIT_DB=str(generale / "pec_audit.sqlite"),
    )
    return app


def _fascicoli_dello_studio(app: Flask, slug: str):
    """Il gestore dei fascicoli come lo ottiene l'app per lo studio (archivio SQL dello studio)."""
    from pct.tenant import GestioneTenant
    from web.helpers import get_fascicoli
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context

    manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
    _attach_tenant_context(manager, manager.get(slug))
    return get_fascicoli()


def _studio(app: Flask, tmp_path: Path, slug: str) -> str:
    """Fascicolo con un deposito INVIATO e la ricevuta di consegna nell'archivio PEC dello studio."""
    msgid = f"deposito-{slug}@pcstudio"
    with app.test_request_context(f"/prova/{slug}"):
        gf = _fascicoli_dello_studio(app, slug)
        fascicolo = gf.nuovo(f"Causa {slug}", TipoFascicolo.CIVILE)
        gf.aggiungi_esito_deposito(fascicolo.id, "RICORSO", "tribunale.esempio@civile.ptel.giustiziacert.it",
                                   messaggio=f"Busta inviata via PEC. Message-ID: <{msgid}>")
    email = tmp_path / "tenants" / f"key-{slug}" / "email"
    email.mkdir(parents=True)
    _archivio(email, [_ricevuta(msgid, f"<ric-{slug}@x>")])
    return fascicolo.id


def _ricevuta(msgid: str, mid: str) -> tuple[str, bytes]:
    """Ricevuta di avvenuta consegna arrivata un minuto dopo l'invio del deposito."""
    arrivo = datetime.now(ROMA) + timedelta(minutes=1)
    return arrivo.strftime("%Y-%m-%dT%H:%M:%S"), _pec(
        "CONSEGNA: DEPOSITO TELEMATICO - RICORSO", rif=f"<{msgid}>", mid=mid, data=format_datetime(arrivo))


def _stato(app: Flask, slug: str, fascicolo_id: str) -> str:
    with app.test_request_context(f"/prova/{slug}"):
        return _fascicoli_dello_studio(app, slug)._fascicoli[fascicolo_id].depositi_pct[0].stato


def _archivio_pec(tmp_path: Path, slug: str) -> str:
    return str((tmp_path / "tenants" / f"key-{slug}" / "email" / "pec_audit.sqlite").resolve())


def test_giro_aggiorna_ogni_studio_con_il_suo_archivio_e_non_legge_quello_generale(tmp_path, monkeypatch, caplog):
    import pct.ricevute_deposito_archivio as archivio_mod
    from web.services.polling_depositi_runtime import run_polling_esiti_deposito

    app = _app(tmp_path)
    studi = {slug: _studio(app, tmp_path, slug) for slug in STUDI}
    letti: list[str] = []
    originale = archivio_mod.ricevute_da_archivio

    def traccia(percorso, **kwargs):
        letti.append(str(Path(percorso).resolve()))
        return originale(percorso, **kwargs)

    monkeypatch.setattr(archivio_mod, "ricevute_da_archivio", traccia)
    monkeypatch.setattr("pct.polling_depositi.ricevute_da_archivio", traccia, raising=False)
    with caplog.at_level(logging.INFO, logger="pct.scheduler"), app.app_context():
        report = run_polling_esiti_deposito(app, giorni=3)

    assert report["ok"], report
    assert [voce["tenant"] for voce in report["tenants"]] == list(STUDI)
    assert all(voce["controllati"] == 1 and voce["aggiornati"] == 1 for voce in report["tenants"]), report
    for slug, fascicolo_id in studi.items():
        assert _stato(app, slug, fascicolo_id) == "CONSEGNATO", slug
    # Ogni studio legge il suo archivio, mai quello generale dell'app.
    assert letti == [_archivio_pec(tmp_path, slug) for slug in STUDI]
    assert str(Path(app.config["PEC_AUDIT_DB"]).resolve()) not in letti
    for slug in STUDI:
        assert f"Polling depositi ({slug}): 1 controllati, 1 aggiornati" in caplog.text


def test_ricevuta_di_un_altro_studio_non_aggiorna_il_deposito(tmp_path):
    """Lo studio beta ha nel suo archivio solo la ricevuta del deposito di alfa: il suo deposito resta INVIATO."""
    from web.services.polling_depositi_runtime import run_polling_esiti_deposito

    app = _app(tmp_path)
    id_alfa = _studio(app, tmp_path, "alfa")
    id_beta = _studio(app, tmp_path, "beta")
    Path(_archivio_pec(tmp_path, "beta")).unlink()
    _archivio(Path(_archivio_pec(tmp_path, "beta")).parent, [_ricevuta("deposito-alfa@pcstudio", "<ric-alfa-copia@x>")])
    with app.app_context():
        report = run_polling_esiti_deposito(app, giorni=3)

    assert _stato(app, "alfa", id_alfa) == "CONSEGNATO"
    assert _stato(app, "beta", id_beta) == "INVIATO"
    assert {voce["tenant"]: voce["aggiornati"] for voce in report["tenants"]} == {"alfa": 1, "beta": 0}


def test_studio_senza_pec_ne_archivio_non_carica_i_fascicoli(tmp_path, monkeypatch):
    import web.helpers as helpers
    from web.services.polling_depositi_runtime import run_polling_esiti_deposito

    app = _app(tmp_path)
    monkeypatch.setattr(helpers, "get_fascicoli", lambda: (_ for _ in ()).throw(AssertionError("fascicoli caricati")))
    with app.app_context():
        report = run_polling_esiti_deposito(app, giorni=3)
    assert report["ok"] and {voce["esito"] for voce in report["tenants"]} == {"pec_non_configurata"}


def test_multi_studio_senza_studi_attivi_e_un_esito_fallito(tmp_path):
    from web.services.polling_depositi_runtime import run_polling_esiti_deposito

    app = _app(tmp_path)
    Path(app.config["TENANTS_REGISTRY"]).write_text("{}", encoding="utf-8")
    with app.app_context():
        report = run_polling_esiti_deposito(app, giorni=3)
    assert report["ok"] is False and "nessuno studio attivo" in report["error"]


def test_lavoro_pianificato_aggiorna_i_depositi_di_ogni_studio(tmp_path, monkeypatch):
    """Il lavoro ``polling_esiti_deposito`` della console Pianificazioni, non solo la funzione del giro."""
    from pct.scheduler import start_scheduler

    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    monkeypatch.delenv("PCT_DISABLE_SCHEDULER", raising=False)
    app = _app(tmp_path)
    app.config.update(BACKUP_ORA="02:00", WA_REMINDER_ORA="18:00", PCT_SCHEDULER_WORKER=True,
                      SCHEDULER_REGISTRY_DB=str(tmp_path / "scheduler.sqlite"))
    studi = {slug: _studio(app, tmp_path, slug) for slug in STUDI}
    scheduler = start_scheduler(app)
    try:
        report = scheduler.get_job("polling_esiti_deposito").func()
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    assert report["ok"] and report["aggiornati"] == 2, report
    assert all(_stato(app, slug, fascicolo_id) == "CONSEGNATO" for slug, fascicolo_id in studi.items())
