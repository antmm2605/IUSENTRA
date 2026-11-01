"""Il catalogo dei tipi di deposito arriva solo alla pagina del deposito (verifica del 01/11/2026: 2,7 MB a ogni apertura)."""

from __future__ import annotations

from tests.test_strumenti_legali import _cfg_web

HEADERS = {"Accept": "application/json"}


def test_sezione_depositi_senza_catalogo_e_pagina_deposito_con_catalogo(tmp_path):
    from pct.fascicoli import TipoFascicolo
    from web.app import create_app
    from web.helpers import get_fascicoli

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        with app.test_request_context("/"):
            from flask import g

            g.utente_corrente = None
            fascicolo = get_fascicoli().nuovo("Rossi c. Bianchi", TipoFascicolo.CIVILE)
        sezione = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi", headers=HEADERS).get_json()
        assert not (sezione.get("depositCatalog") or {}).get("entries")
        pagina = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}?include=depositi,catalogo_depositi", headers=HEADERS).get_json()
        assert len(pagina["depositCatalog"]["entries"]) > 100


def test_le_sezioni_non_rispediscono_la_lettura_iniziale():
    from pathlib import Path

    sorgente = (Path(__file__).resolve().parents[1] / "web" / "services" / "react_fascicoli_bridge.py").read_text(encoding="utf-8")
    assert 'if not include or include_all or "lettura" in include' in sorgente
