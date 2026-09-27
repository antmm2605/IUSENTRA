"""Migrazione React 2.413.0: contenuti e impostazioni del sito dello studio.

Servizi, professionisti, sedi e orari prenotabili, impostazioni del sito e
nuovo articolo passano dalla pagina React; pagine, prenotazioni e anteprima
portano al builder e ai contatti React che già li gestiscono.
"""

from __future__ import annotations

from tests.test_revisione_2410_sicurezza import _app as _app_sessione
from tests.test_topbar_operational_api import _login

HTML = {"Accept": "text/html"}
BASE = "/api/v1/ui/sito-studio/contenuti"


def test_pagine_del_sito_nella_shell_react():
    from web.blueprints import react_shell
    from web.bootstrap.react_route_gate import _excluded, _is_react_route, _sito_studio_react_allowed

    for percorso in (
        "/sito-studio/servizi",
        "/sito-studio/servizi/nuovo",
        "/sito-studio/professionisti/3/modifica",
        "/sito-studio/sedi/nuova",
        "/sito-studio/regole-agenda/2/modifica",
        "/sito-studio/impostazioni",
        "/sito-studio/articoli/nuovo",
    ):
        assert _sito_studio_react_allowed(percorso) and _is_react_route(percorso) and not _excluded(percorso), percorso
        assert react_shell._route_component_key(percorso) == "src/components/SitoStudioContenutiPage.tsx", percorso


def test_pagine_prenotazioni_e_anteprima_portano_a_builder_e_contatti(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        casi = {
            "/sito-studio/pagine/nuova": "/sito-studio/builder",
            "/sito-studio/pagine/7/modifica": "/sito-studio/builder?page_id=7",
            "/sito-studio/prenotazioni": "/sito-studio/contatti",
            "/sito-studio/preview": "/sito-studio/builder",
        }
        for origine, destinazione in casi.items():
            risposta = client.get(origine, headers=HTML)
            assert risposta.status_code == 302, origine
            assert risposta.headers["Location"].endswith(destinazione), (origine, risposta.headers["Location"])


def test_raccolte_del_sito_crea_modifica_elimina(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        servizi = client.get(f"{BASE}/servizi").get_json()
        assert servizi["ok"] is True and {c["key"] for c in servizi["collections"]} == {"servizi", "professionisti", "sedi", "regole-agenda"}
        assert client.post(f"{BASE}/servizi", json={"title": ""}).get_json()["errors"]["title"] == "Campo obbligatorio."
        creato = client.post(f"{BASE}/servizi", json={"title": "Diritto di famiglia", "short_description": "Separazioni", "is_visible": True}).get_json()
        assert creato["ok"] is True
        ident = creato["item"]["id"]
        # Un campo svuotato si svuota davvero (prima restava il valore precedente).
        client.post(f"{BASE}/servizi/{ident}", json={"title": "Diritto di famiglia", "short_description": "", "is_visible": False})
        voce = next(i for i in client.get(f"{BASE}/servizi").get_json()["items"] if i["id"] == ident)
        assert voce["values"]["short_description"] == "" and voce["visible"] is False
        assert client.post(f"{BASE}/servizi/{ident}/elimina", json={}).get_json()["ok"] is True
        assert client.post(f"{BASE}/servizi/{ident}/elimina", json={}).status_code == 404
        assert client.get(f"{BASE}/sconosciuta").status_code == 404
        assert client.post(f"{BASE}/professionisti", json={"full_name": "Avv. Rossi", "email": "non-valida"}).status_code == 400


def test_orari_prenotabili_controllati_e_sede_protetta(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        # Il sito nasce con la sede principale dello studio: gli orari si legano a una sede.
        assert client.get(f"{BASE}/regole-agenda").get_json()["needsOffice"] is False
        sede = client.post(f"{BASE}/sedi", json={"name": "Sede di Palmi", "city": "Palmi", "is_visible": True}).get_json()["item"]["id"]
        invertito = client.post(f"{BASE}/regole-agenda", json={"office_id": sede, "weekday": "0", "start_time": "13:00", "end_time": "09:00", "slot_minutes": "30", "max_requests_per_slot": "1"})
        assert invertito.status_code == 400 and "end_time" in invertito.get_json()["errors"]
        lunedi = client.post(f"{BASE}/regole-agenda", json={"office_id": sede, "weekday": "0", "start_time": "09:00", "end_time": "13:00", "slot_minutes": "30", "max_requests_per_slot": "1", "is_active": True})
        assert lunedi.get_json()["ok"] is True
        elenco = client.get(f"{BASE}/regole-agenda").get_json()
        assert any(item["title"] == "Lunedi 09:00-13:00 · Sede di Palmi" for item in elenco["items"])
        # Una sede con orari prenotabili non si elimina.
        assert client.post(f"{BASE}/sedi/{sede}/elimina", json={}).status_code == 409


def test_impostazioni_del_sito_e_cookie(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        impostazioni = client.get(f"{BASE}/impostazioni").get_json()
        assert impostazioni["ok"] is True and any(c["name"] == "primary_color" and c["kind"] == "color" for c in impostazioni["fields"])
        valori = dict(impostazioni["values"])
        valori.update(studio_nome="Studio Legale Prova", analytics_enabled=True, cookie_banner_enabled=False)
        rifiuto = client.post(f"{BASE}/impostazioni", json=valori)
        assert rifiuto.status_code == 400 and "Garante" in rifiuto.get_json()["errors"]["analytics_enabled"]
        valori.update(cookie_banner_enabled=True, primary_color="#123456")
        salvate = client.post(f"{BASE}/impostazioni", json=valori).get_json()
        assert salvate["ok"] is True and salvate["values"]["primary_color"] == "#123456"
        bozza = client.post(f"{BASE}/articoli/bozza", json={"title": "Le novità del processo civile"}).get_json()
        assert bozza["ok"] is True and bozza["redirect_href"].endswith("/modifica")
