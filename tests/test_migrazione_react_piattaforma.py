"""Migrazione React 2.414.0: pannello di piattaforma del superamministratore.

Panoramica, governance del prodotto, stato installazione, salute del sistema, siti degli studi, valutazione di Lex e
osservabilità si aprono nell'applicazione React di piattaforma
(`#piattaforma-react-root`), con i dati di `/api/v1/ui/piattaforma/<pagina>`
calcolati dagli stessi servizi delle viste storiche.
"""

from __future__ import annotations

from pathlib import Path

from tests.test_operational_surfaces import _cfg_web, _seed_runtime, _write_studio_config
from web.app import create_app

PAGINE = {
    "/admin/": "cruscotto",
    "/admin/governance": "governance",
    "/admin/stato-installazione": "stato-installazione",
    "/admin/salute-sistema": "salute-sistema",
    "/admin/siti-studio/": "siti-studio",
    "/admin/lex-scorecard": "lex-scorecard",
    "/admin/osservabilita": "osservabilita",
}


def _app(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _write_studio_config(tmp_path / "config" / "studio.json")
    _seed_runtime(cfg)
    return create_app(cfg)


def _login_superadmin(client) -> None:
    risposta = client.post("/login", data={"username": "superadmin-operativo", "password": "Admin1234!"}, follow_redirects=False)
    assert risposta.status_code == 302


def test_pagine_del_pannello_nella_applicazione_react(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        for percorso, chiave in PAGINE.items():
            risposta = client.get(percorso)
            html = risposta.get_data(as_text=True)
            assert risposta.status_code == 200, percorso
            assert 'id="piattaforma-react-root"' in html and f'data-pagina="{chiave}"' in html, percorso
            # Il modulo parte solo con il parametro di versione (main.tsx).
            assert '.js?v=' in html, percorso


def test_dati_delle_pagine_dal_servizio(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        for chiave in PAGINE.values():
            dati = client.get(f"/api/v1/ui/piattaforma/{chiave}")
            corpo = dati.get_json()
            assert dati.status_code == 200 and corpo["ok"] is True, chiave
            assert corpo["title"] and corpo["sections"], chiave
            assert {voce["key"] for voce in corpo["menu"]} == set(PAGINE.values())
            assert corpo["user"] == "superadmin-operativo"
            for sezione in corpo["sections"]:
                assert sezione["kind"] in {"metrics", "status", "table", "facts", "notes", "shortcuts"}
        assert client.get("/api/v1/ui/piattaforma/sconosciuta").status_code == 404


def test_vista_classica_ancora_raggiungibile(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        _login_superadmin(client)
        for percorso in PAGINE:
            risposta = client.get(f"{percorso}?_legacy=1")
            assert risposta.status_code == 200, percorso
            assert "piattaforma-react-root" not in risposta.get_data(as_text=True), percorso


def test_pannello_riservato_al_superamministratore(tmp_path: Path):
    from tests.test_revisione_2410_sicurezza import _app as _app_sessione
    from tests.test_topbar_operational_api import _login

    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        assert client.get("/api/v1/ui/piattaforma/salute-sistema").status_code == 403
    with app.test_client() as anonimo:
        assert anonimo.get("/api/v1/ui/piattaforma/salute-sistema").status_code == 401


def test_date_in_formato_italiano():
    from web.services.react_piattaforma_bridge import data_ora

    assert data_ora("2026-09-27T08:05:00+00:00") == "27/09/2026 10:05"
    assert data_ora("2026-01-02T03:04:05") == "02/01/2026 03:04"
    assert data_ora("") == "" and data_ora("non una data") == "non una data"


def test_moduli_react_avviati_con_il_parametro_di_versione():
    """main.tsx avvia React solo dal modulo con `?v=`: senza, la pagina resta vuota."""
    from pathlib import Path

    for modello in ("web/templates/piattaforma_shell.html", "web/templates/support/operator_room.html"):
        testo = Path(modello).read_text(encoding="utf-8")
        assert 'src="{{ js_file }}?v={{ app_version }}"' in testo, modello


def test_collegamenti_del_pannello_raggiungibili(tmp_path: Path):
    """Ogni collegamento del menu e delle pagine risponde senza rimandare altrove."""
    import re

    app = _app(tmp_path)
    sorgente = Path("frontend/src/components/PiattaformaApp.tsx").read_text(encoding="utf-8")
    indirizzi = set(re.findall(r"href: '(/admin[^']*)'", sorgente))
    with app.test_client() as client:
        _login_superadmin(client)
        for chiave in PAGINE.values():
            corpo = client.get(f"/api/v1/ui/piattaforma/{chiave}").get_json()
            indirizzi |= {v["href"] for v in corpo["menu"]}
            indirizzi |= {c["href"] for c in corpo.get("links") or [] if not c.get("external")}
            for sezione in corpo["sections"]:
                if sezione["kind"] == "shortcuts":
                    indirizzi |= {v["href"] for v in sezione["items"]}
        for indirizzo in sorted(indirizzi):
            risposta = client.get(indirizzo)
            assert risposta.status_code == 200, (indirizzo, risposta.status_code, risposta.headers.get("Location"))
