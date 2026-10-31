"""Notifiche legali: il riallineamento con le prove avviene quando entra un documento o una PEC, non nell'elenco.

Verifica di produzione del 31/10/2026: l'apertura della pagina durava circa 18 secondi
perché ogni consultazione riallineava 50 presìdi dello studio.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from flask import Flask

from web.services import notification_presidia_payloads as payloads


class _Repo:
    tenant_id = "t"

    def __init__(self, stati):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE pec_legal_notification_presidia (id TEXT, tenant_id TEXT, status TEXT, updated_at TEXT)")
        for i, stato in enumerate(stati):
            self.conn.execute("INSERT INTO pec_legal_notification_presidia VALUES (?,?,?,?)", (f"p{i}", "t", stato, f"2026-10-{10 + i}"))

    @contextmanager
    def connection(self):
        yield self.conn


def test_l_elenco_conta_gli_stati_senza_riallineare(monkeypatch):
    import web.services.notification_presidia_fascicolo_reconciliation as riconciliazione

    def _vietato(*a, **k):
        raise AssertionError("l'elenco non deve riallineare i presìdi")

    monkeypatch.setattr(riconciliazione, "reconcile_presidio_with_fascicolo_notification_proof", _vietato)
    assert not hasattr(payloads, "_reconcile_open_presidia_with_fascicolo_proof")
    with Flask(__name__).app_context():
        assert payloads._status_facets(_Repo(["DETECTED", "DETECTED", "PROOF_DEPOSITED"])) == {"DETECTED": 2, "PROOF_DEPOSITED": 1}


def test_la_lettura_del_fascicolo_riallinea_solo_i_suoi_presidi(monkeypatch):
    import web.services.fascicolo_lettura_verifiche as verifiche
    from web.services.archivio_letture_runtime import _riallinea_notifiche_del_fascicolo

    chiesti = []
    monkeypatch.setattr(verifiche, "verifica_notifiche", lambda fid: chiesti.append(fid) or {"esaminati": 2, "riallineati": 1})
    assert _riallinea_notifiche_del_fascicolo("F1") == {"esaminati": 2, "riallineati": 1}
    assert chiesti == ["F1"]

    def _guasto(fid):
        raise RuntimeError("registro notifiche non disponibile")

    monkeypatch.setattr(verifiche, "verifica_notifiche", _guasto)
    # Un guasto del registro notifiche non ferma la lettura del fascicolo.
    assert _riallinea_notifiche_del_fascicolo("F1")["errore"] == "RuntimeError"
