"""Sito pubblico dello studio in React pre-generato (Node, renderToString) e idratato nel browser.

- tutti i 39 tipi di blocco del costruttore passano dal bundle Node: l'HTML prodotto coincide con quello
  conservato in ``frontend/src/sitoPubblico/__fixtures__``, che la story Storybook idrata nel browser
  verificando zero differenze (stesso markup sul server e nel browser);
- la pagina pubblica si legge senza JavaScript (il testo è già nell'HTML);
- la cache è per sito, pagina e versione; senza cache si genera la sola pagina richiesta.
"""

from __future__ import annotations

import json
import os
import re
from html import unescape
from pathlib import Path

import pytest

from pct.studio_site_blocks import BLOCK_TYPE_CODES, default_block
from web.services import sito_pubblico_prerender as prerender
from web.services.sito_pubblico_dati import dati_pagina

RADICE = Path(__file__).resolve().parents[1]
FIXTURE = RADICE / "frontend/src/sitoPubblico/__fixtures__"
SERVE_NODE = pytest.mark.skipif(not prerender.binario_node() or not prerender.bundle_ssr().is_file(), reason="node o bundle SSR assenti")


def _payload_completo() -> dict:
    blocchi = []
    for codice in sorted(BLOCK_TYPE_CODES):
        blocco = default_block(codice)
        blocco["title"] = f"Titolo {codice} con <em>enfasi</em> <script>x</script>"
        blocchi.append(blocco)
    articolo = {"title": "Recesso dal contratto", "slug": "recesso", "excerpt": "Guida pratica", "category": "Civile", "cover_url": ""}
    return {
        "site": {"site_name": "Studio Prova", "site_title": "Studio Prova Roma", "site_description": "Assistenza legale",
                 "public_slug": "studio-prova", "city": "Roma", "province": "RM", "contact_email": "info@example.invalid",
                 "whatsapp_number": "+39 333 000", "cookie_banner_enabled": True, "hero_claim": "Chiarezza e metodo",
                 "tenant_slug": "segreto-interno", "analytics_id": "UA-SEGRETO"},
        "home_page": {"title": "Home", "slug": "home", "excerpt": "", "body_json": blocchi},
        "menu_pages": [{"title": "Lo studio", "slug": "studio"}],
        "articles": [articolo], "latest_articles": [articolo],
        "services": [{"title": "Contenzioso civile", "icon": "bi-briefcase", "short_description": "Cause e mediazioni"}],
        "professionals": [{"full_name": "Avv. Maria Rossi", "role_title": "Titolare", "bio": "Civilista", "email": "", "phone": ""}],
        "offices": [{"id": 1, "name": "Sede di Roma", "address": "Via Roma 1", "city": "Roma", "province": "RM", "opening_hours": "9-18"}],
        "booking_enabled": True, "show_legal_tools": True, "show_applications": True, "show_legal_news": True,
        "legal_tools": [{"title": "Calcolo interessi", "subtitle": "Tasso legale", "icon": "bi-calculator", "category": "Calcoli"}],
        "applications": [{"title": "Portale clienti", "summary": "Documenti", "icon": "bi-grid", "badge": "Nuovo", "section_title": "Clienti", "access_mode": "diretta"}],
        "legal_news": [{"title": "Riforma", "summary": "Novità", "url": "https://www.gazzettaufficiale.it/", "source_name": "Gazzetta", "publication_date": "2026-11-01"}],
        "theme": {"template_code": "classic_legal"},
    }


def _richieste() -> list[dict]:
    payload = _payload_completo()
    return [dati_pagina(payload, vista) for vista in ("home", "contatti", "prenota", "strumenti-legali", "applicazioni", "news-giuridiche", "articoli")]


def test_dati_pubblici_contengono_tutti_i_blocchi_e_nessun_dato_interno():
    richieste = _richieste()
    assert {blocco["type"] for blocco in richieste[0]["pagina"]["body_json"]} == BLOCK_TYPE_CODES
    corpo = json.dumps(richieste)
    assert "segreto-interno" not in corpo and "UA-SEGRETO" not in corpo
    atteso = json.loads((FIXTURE / "tutti-i-blocchi.json").read_text(encoding="utf-8"))
    if os.environ.get("IUSENTRA_AGGIORNA_FIXTURE") == "1":
        (FIXTURE / "tutti-i-blocchi.json").write_text(json.dumps(richieste, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        atteso = richieste
    assert atteso == richieste, "fixture dei blocchi superata: rigenerare con IUSENTRA_AGGIORNA_FIXTURE=1"


@SERVE_NODE
def test_html_di_node_coincide_con_quello_idratato_nella_story_e_si_legge_senza_javascript():
    richieste = _richieste()
    html = prerender.genera(richieste, timeout=60)
    assert html is not None and len(html) == len(richieste)
    percorso = FIXTURE / "tutti-i-blocchi.ssr.json"
    if os.environ.get("IUSENTRA_AGGIORNA_FIXTURE") == "1":
        percorso.write_text(json.dumps(html, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    assert json.loads(percorso.read_text(encoding="utf-8")) == html, "HTML del server cambiato: rigenerare la fixture"
    testo = unescape(re.sub(r"<[^>]+>", " ", html[0]))
    senza_titolo = {"trust_bar": "studio-site-trust-bar", "text_ticker": "studio-site-ticker", "hero_slider": "studio-site-hero-slider"}
    for codice in BLOCK_TYPE_CODES - set(senza_titolo):
        # Ogni blocco mostra il suo titolo già nell'HTML, senza JavaScript (come nei template Jinja).
        assert f"Titolo {codice}" in testo, codice
    for classe in senza_titolo.values():
        assert classe in html[0]
    assert "<script>" not in html[0] and "&lt;script&gt;x&lt;/script&gt;" in html[0]
    assert "<em>enfasi</em>" in html[0]
    assert "Avv. Maria Rossi" in testo and "Sede di Roma" in testo and "Calcolo interessi" in unescape(html[3])


@SERVE_NODE
def test_cache_per_sito_pagina_e_versione_e_generazione_singola_se_manca(tmp_path: Path):
    payload = _payload_completo()
    home = dati_pagina(payload, "home")
    contatti = dati_pagina(payload, "contatti")
    assert prerender.pre_genera_sito(tmp_path, [home, contatti]) == 2
    assert prerender.pre_genera_sito(tmp_path, [home, contatti]) == 0
    file_home = sorted(path.name for path in tmp_path.glob("home--*.html"))
    assert len(file_home) == 1 and prerender.versione(home) in file_home[0]
    payload["site"]["site_name"] = "Studio Prova Rinominato"
    nuova = dati_pagina(payload, "home")
    html = prerender.pagina_pre_generata(tmp_path, nuova)
    assert html is not None and "Studio Prova Rinominato" in html
    assert len(list(tmp_path.glob("home--*.html"))) == 1  # la versione superata è rimossa


def test_senza_node_la_pagina_parte_senza_html_pre_generato(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(prerender, "binario_node", lambda: "")
    assert prerender.pagina_pre_generata(tmp_path, dati_pagina(_payload_completo(), "contatti")) is None


def test_salvataggio_dei_contenuti_avvia_la_pre_generazione_e_il_visitatore_legge_la_cache(tmp_path: Path, monkeypatch):
    from web.app import create_app
    from web.services import sito_pubblico_runtime
    from web.services.studio_site_runtime import studio_site_repository
    from tests.test_studio_site import _cfg_web, _login_tenant_admin, _seed_tenant_admin, _write_studio_config

    avviate: list[tuple[Path, list]] = []
    monkeypatch.setattr(sito_pubblico_runtime, "pre_genera_in_sfondo", lambda cartella, pagine: avviate.append((cartella, pagine)))
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)
    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")
        with app.app_context():
            repo = studio_site_repository()
            site = repo.get_site_by_tenant_slug(studio.slug)
            repo.save_site(int(site["id"]), {"is_published": True, "is_active": True})
        lettura = client.get("/api/v1/ui/sito-studio/contenuti/impostazioni")
        rifiutato = client.post("/api/v1/ui/sito-studio/contenuti/impostazioni", json={"primary_color": "rosso"})
        assert avviate == []  # né la lettura né un salvataggio respinto avviano la pre-generazione
        valori = dict(lettura.get_json().get("values") or {})
        valori["site_name"] = "Studio Sito Rinominato"
        salvataggio = client.post("/api/v1/ui/sito-studio/contenuti/impostazioni", json=valori)
    assert rifiutato.status_code == 400
    assert salvataggio.status_code == 200, salvataggio.get_data(as_text=True)[:300]
    assert len(avviate) == 1
    cartella, pagine = avviate[0]
    assert cartella.name == site["public_slug"] and cartella.parent.name == "site_prerender"
    assert {dati["vista"] for dati in pagine} >= {"home", "articoli", "contatti"}
    assert lettura.status_code == 200

    with app.test_client() as visitatore:
        pagina = visitatore.get(f"/web/{site['public_slug']}/contatti")
    html = pagina.get_data(as_text=True)
    assert pagina.status_code == 200
    assert 'id="sito-pubblico-root" data-sito-pubblico="1"' in html
    assert 'id="sito-pubblico-dati"' in html and "tenant_slug" not in html.split('id="sito-pubblico-dati"')[1]
    if prerender.binario_node() and prerender.bundle_ssr().is_file():
        assert "Contatta lo studio" in html.split('id="sito-pubblico-root"')[1]  # leggibile senza JavaScript
