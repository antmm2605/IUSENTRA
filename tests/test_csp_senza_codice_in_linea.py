"""CSP senza 'unsafe-inline' per gli script: i template non contengono codice in linea.

Ogni blocco <script> in linea porta il nonce della richiesta, nessun attributo
evento (onclick=…) né URL javascript: resta nei template, e ogni gestore
convertito (data-iu-on) esiste nel registro servito al browser.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import csp_gestori_legacy as conv

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "web" / "templates"
_BLOCCO_SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.S | re.I)
_COMMENTI = re.compile(r"<!--.*?-->|\{#.*?#\}", re.S)
_ATTRIBUTO_EVENTO = re.compile(r"""(?<![\w-])on[a-z]+\s*=\s*["']""", re.I)


def _template():
    for percorso in sorted(TEMPLATES.rglob("*.html")):
        yield percorso, percorso.read_text(encoding="utf-8")


def _senza_contenuto_script(testo: str) -> str:
    testo = _COMMENTI.sub("", testo)
    return _BLOCCO_SCRIPT.sub(lambda m: f"<script{m.group(1)}></script>", testo)


def test_conversione_allineata():
    assert conv.main(["--check"]) == 0


def test_nessun_attributo_evento_ne_url_javascript():
    trovati = []
    for percorso, testo in _template():
        pulito = _senza_contenuto_script(testo)
        for m in _ATTRIBUTO_EVENTO.finditer(pulito):
            trovati.append(f"{percorso.relative_to(ROOT)}: {pulito[m.start():m.start() + 50]!r}")
        if re.search(r"""(href|src|action)\s*=\s*["']\s*javascript:""", pulito, re.I):
            trovati.append(f"{percorso.relative_to(ROOT)}: URL javascript:")
        # Anche l'HTML costruito dagli script non deve contenere gestori in linea.
        for blocco in _BLOCCO_SCRIPT.finditer(_COMMENTI.sub("", testo)):
            for m in re.finditer(r"""(?<![\w.$-])on[a-z]+=\\?["']""", blocco.group(2)):
                trovati.append(f"{percorso.relative_to(ROOT)} (script): {blocco.group(2)[m.start():m.start() + 50]!r}")
    assert trovati == []


def test_script_in_linea_con_nonce():
    senza = []
    for percorso, testo in _template():
        for m in _BLOCCO_SCRIPT.finditer(_COMMENTI.sub("", testo)):
            attributi = m.group(1).lower()
            if "src=" in attributi or re.search(r"type\s*=\s*[\"'](application/(ld\+)?json|text/template)", attributi):
                continue
            if 'nonce="{{ csp_nonce() }}"' not in m.group(1):
                senza.append(str(percorso.relative_to(ROOT)))
    assert senza == []


def test_gestori_registrati_e_registro_valido():
    registro = conv.carica_registro()
    usati = conv.chiavi_usate([testo for _p, testo in _template()])
    assert usati and usati <= set(registro)
    runtime = (ROOT / "web" / "static" / "js" / "iu-gestori.js").read_text(encoding="utf-8")
    assert "el['on' + p[0]]" in runtime and "MutationObserver" in runtime
    node = shutil.which("node")
    if not node:
        pytest.skip("node non disponibile")
    for nome in ("iu-gestori.js", "iu-gestori-registro.js"):
        copia = Path(ROOT / "web" / "static" / "js" / nome).read_text(encoding="utf-8")
        esito = subprocess.run([node, "--check", "--input-type=commonjs"], input=copia, text=True, capture_output=True)
        assert esito.returncode == 0, esito.stderr


def test_conversione_valori_jinja():
    codice, valori = conv.codice_e_valori("return confirm('Eliminare {{ c.numero }}?')")
    assert codice == "return confirm('Eliminare ' + __v[0] + '?')"
    assert valori == ["{{ c.numero }}"]
    codice, valori = conv.codice_e_valori("aggiorna({{ elenco|length }}, &quot;x&quot;)")
    assert codice == 'aggiorna(JSON.parse(__v[0]), "x")'
    assert valori == ["{{ (elenco|length) | forceescape }}"]
    testo, n, problemi = conv.converti_testo(
        '<button class="b" onclick="apri(\'{{ f.id }}\')" ondblclick="x()">A</button>', {}, "prova"
    )
    assert n == 2 and problemi == []
    assert "onclick" not in testo and 'data-iu-v-click-0="{{ f.id }}"' in testo
    assert re.search(r'data-iu-on="click:g[0-9a-f]{10} dblclick:g[0-9a-f]{10}"', testo)


def test_pagina_resa_con_nonce_coerente(tmp_path):
    from tests.test_revisione_2410_sicurezza import _app

    app = _app(tmp_path, ENABLE_SECURITY_HEADERS=True, SECURITY_HEADERS_ENABLED=True, CSP_REPORT_ONLY=False)
    with app.test_client() as client:
        risposta = client.get("/login?_legacy=1")
        assert risposta.status_code == 200
        # In prova la CSP è «Report-Only» (CSP_REPORT_ONLY predefinito nei test): stesso testo.
        csp = risposta.headers.get("Content-Security-Policy") or risposta.headers["Content-Security-Policy-Report-Only"]
        script_src = next(p for p in csp.split(";") if p.strip().startswith("script-src"))
        assert "'unsafe-inline'" not in script_src
        nonce = re.search(r"'nonce-([^']+)'", script_src).group(1)
        html = risposta.get_data(as_text=True)
        for m in _BLOCCO_SCRIPT.finditer(html):
            attributi = m.group(1)
            if "src=" in attributi or "application/json" in attributi or "application/ld+json" in attributi:
                continue
            assert f'nonce="{nonce}"' in attributi, attributi
        assert not _ATTRIBUTO_EVENTO.search(_senza_contenuto_script(html))
        assert "/static/js/iu-gestori.js" in html


def test_shell_react_nonce_stabile_con_304(tmp_path):
    """La shell React si rivalida con ETag: nonce stabile per sessione, uguale nel 304."""
    from tests.test_revisione_2410_sicurezza import _app
    from tests.test_topbar_operational_api import _login

    app = _app(tmp_path, ENABLE_SECURITY_HEADERS=True, SECURITY_HEADERS_ENABLED=True)
    with app.test_client() as client:
        _login(client, "operatore", "Operatore123!")
        prima = client.get("/fascicoli")
        assert prima.status_code == 200
        html = prima.get_data(as_text=True)
        csp = prima.headers.get("Content-Security-Policy") or prima.headers["Content-Security-Policy-Report-Only"]
        nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
        assert "iuCspNonceSegnaposto" not in html and f'nonce="{nonce}"' in html
        ripetuta = client.get("/fascicoli", headers={"If-None-Match": prima.headers["ETag"]})
        assert ripetuta.status_code == 304
        csp_304 = ripetuta.headers.get("Content-Security-Policy") or ripetuta.headers["Content-Security-Policy-Report-Only"]
        assert f"'nonce-{nonce}'" in csp_304
