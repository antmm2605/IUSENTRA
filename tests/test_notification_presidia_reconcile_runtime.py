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


def test_rettifica_richiede_lo_stesso_ruolo_estraneo_nell_originale_e_nella_pec(monkeypatch):
    from types import SimpleNamespace
    from web.services import notification_presidia_fascicolo_reconciliation as mod

    monkeypatch.setattr(mod, "_notification_document_role", lambda *_: ("1084/2026", "627/2026"))
    row = {"id": "p", "status": "ORIGINAL_ACQUIRED", "fascicolo_id": "F", "source_message_id": "PEC"}
    docs = [
        {"document_role": "portal_original", "authoritative": True, "fascicolo_document_id": "D"},
        {"document_role": "office_pec_copy", "content_sha256": "hash-esatto"},
    ]
    writes = []
    repo = SimpleNamespace(transition=lambda *args, **kwargs: writes.append((args, kwargs)) or SimpleNamespace(inserted=True))
    ocr = {"sha256": "hash-esatto", "ocr_text": "N. R.G. 1084/2026\nTRIBUNALE"}
    audit = SimpleNamespace(
        connect=_Repo([]).connection,
        latest_parsed_row=lambda *_: {"id": "V"},
        attachment_rows=lambda *_: [ocr],
    )
    assert not mod._rettifica_fonte_di_altro_ruolo(repo, audit, row, docs, [], "sistema")
    ocr["ocr_text"] = "N. R.G. 627/2026\nTRIBUNALE"
    assert not mod._rettifica_fonte_di_altro_ruolo(repo, audit, row, docs, [{"rac_message_id": "RAC"}], "sistema")
    assert not writes
    assert mod._rettifica_fonte_di_altro_ruolo(repo, audit, row, docs, [], "sistema")
    assert writes[0][0] == ("p", "CANCELLED")
    assert writes[0][1]["evidence"]["document_rg"] == "627/2026"


def test_fonte_estranea_annullata_mostra_il_motivo_senza_termine_del_fascicolo(monkeypatch):
    from web.services import notification_legal_terms

    def termina(*args):
        raise AssertionError("Nessun termine va cercato per la fonte esclusa.")

    monkeypatch.setattr(payloads, "_practice_payload", lambda fid: {"id": fid})
    monkeypatch.setattr(notification_legal_terms, "termine_per_presidio", termina)
    row = {
        "id": "p", "status": "CANCELLED", "fascicolo_id": "F",
        "notification_case": "explicit_order", "resolution_code": "PROVVEDIMENTO_ALTRO_RUOLO",
        "resolution_reason": "L’atto riguarda il R.G. 627/2026.", "explicit_due_at": "2026-12-16",
    }
    item = payloads._summary({}, row, [], [], [])
    assert item["excluded_source"] is True
    assert item["detection_reason"] == row["resolution_reason"]
    assert item["legal_term"] is None and item["explicit_due_at"] is None


def test_la_lettura_del_fascicolo_si_prepara_in_sfondo_senza_fermare_la_lettura(monkeypatch):
    """V21: la scheda «Lettura» (16-25 s alla prima apertura) si prepara alla fine della lettura in sfondo."""
    import web.blueprints.api_v1_react as api
    from web.services.archivio_letture_runtime import _prepara_lettura

    chiesti = []
    monkeypatch.setattr(api, "prepara_lettura_in_cache", lambda fid: chiesti.append(fid) or True)
    assert _prepara_lettura("F1") is True and chiesti == ["F1"]

    def _guasto(fid):
        raise RuntimeError("archivio non disponibile")

    monkeypatch.setattr(api, "prepara_lettura_in_cache", _guasto)
    assert _prepara_lettura("F1") is False
