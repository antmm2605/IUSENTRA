"""ADM-29 (riverifica 03/11/2026): la cabina telematica esclude le revisioni verticali dalla chiave di cache."""

from types import SimpleNamespace

from web.services import operational_read_revision as orr


def _prepara(monkeypatch):
    import pct.operational_live as live
    import web.services.operational_live_sources as sorgenti
    import web.services.storage_runtime as storage
    import web.services.tenant_paths as percorsi

    monkeypatch.setattr(live, "read_live_revisions", lambda backend, domains: {"fascicoli": 10})
    monkeypatch.setattr(storage, "get_request_studio_db", lambda path: object())
    monkeypatch.setattr(percorsi, "tenant_data_path", lambda *a, **k: "studio.db")
    monkeypatch.setattr(sorgenti, "read_vertical_revisions", lambda domains: {"fascicoli": 500})
    return SimpleNamespace(ha_permesso=lambda permesso: True)


def test_revisioni_con_e_senza_verticali(monkeypatch):
    utente = _prepara(monkeypatch)
    assert orr.read_authorized_revisions(utente, requested_domains={"fascicoli"}) == {"fascicoli": 510}
    assert orr.read_authorized_revisions(utente, requested_domains={"fascicoli"}, include_vertical=False) == {"fascicoli": 10}
