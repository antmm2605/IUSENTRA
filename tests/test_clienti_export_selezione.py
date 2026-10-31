"""«Esporta» e «Esporta selezione» della pagina React dei Clienti scaricano il CSV (difetto del link /clienti/esporta)."""

from __future__ import annotations

from pathlib import Path

from tests.test_strumenti_legali import _cfg_web


def test_export_csv_tutti_e_solo_selezionati(tmp_path):
    from pct.clienti import TipoCliente
    from web.app import create_app
    from web.helpers import get_clienti

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        with app.test_request_context("/"):
            from flask import g

            g.utente_corrente = None
            gestione = get_clienti()
            primo = gestione.nuovo(TipoCliente.PERSONA_FISICA, nome="Primo", cognome="Prova")
            gestione.nuovo(TipoCliente.PERSONA_FISICA, nome="Secondo", cognome="Prova")
        tutti = client.get("/clienti/export.csv").get_data(as_text=True)
        scelti = client.get(f"/clienti/export.csv?ids={primo.id}").get_data(as_text=True)
    assert "Primo" in tutti and "Secondo" in tutti
    assert "Primo" in scelti and "Secondo" not in scelti


def test_la_pagina_react_non_usa_il_percorso_inesistente():
    sorgente = Path("frontend/src/components/AnagraficaClientiPage.tsx").read_text(encoding="utf-8")
    assert "/clienti/esporta" not in sorgente
    assert "/clienti/export.csv" in sorgente


def test_collaboratori_del_fascicolo_non_finiscono_nel_dettaglio_react():
    from web.bootstrap.react_route_gate import _excluded

    assert _excluded("/fascicoli/F1/collaboratori") is True
    assert _excluded("/fascicoli/F1") is False
