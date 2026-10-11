from pathlib import Path

from pct.applicazioni_catalogo import catalogo_applicazioni
from web.services.react_studio_module_bridge import catalogo_utility
from pct.strumenti_legali import GestioneStrumentiLegali
from web.services.react_strumenti_legali_bridge import build_react_strumenti_legali_payload, sorgenti_opzioni


def test_catalogo_non_inizializza_ne_sincronizza_tabelle_normative(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Il caricamento del catalogo non deve inizializzare gli archivi dei calcoli')

    monkeypatch.setattr(GestioneStrumentiLegali, '__init__', forbidden)
    payload = build_react_strumenti_legali_payload(
        catalogo=GestioneStrumentiLegali.catalogo_moduli(),
        form_state=GestioneStrumentiLegali.build_form_state({}),
        opzioni=sorgenti_opzioni(GestioneStrumentiLegali),
    )
    assert payload['totale_in_react'] > 0
    assert any(item['id'] == 'termini_processuali' and item['campi'] for item in payload['strumenti'])


def test_catalogo_unificato_preserva_ogni_destinazione_e_preset_nativo():
    entries = list(catalogo_applicazioni())
    output = catalogo_utility()
    assert {item['id'] for item in output} == {item['id'] for item in entries}
    assert all(item['href'].startswith('/') for item in output)
    assert any(item['type'] == 'lookup' for item in output)
    assert any(item['type'] == 'tool' and item['preset'] for item in output)


def test_catalogo_non_carica_moduli_eseguibili_che_non_vengono_aperti(monkeypatch):
    from web.services import react_applicazioni_bridge

    def forbidden(*args, **kwargs):
        raise AssertionError('Il catalogo deve caricare soltanto i metadati')

    monkeypatch.setattr(react_applicazioni_bridge, 'campi_modulo', forbidden)
    assert all(item['form'] is None for item in catalogo_utility())


def test_alias_catalogo_aprono_unica_superficie_senza_rimuovere_dettagli():
    source = Path('frontend/src/App.tsx').read_text(encoding='utf-8')
    assert "{ label: 'Utility', icon: Wrench, href: '/strumenti-legali/' }" in source
    assert "{ label: 'Strumenti Operativi'," not in source
    assert "!isApplicazionePage && ['/strumenti-legali', '/strumenti-operativi', '/applicazioni'].includes(routeKey)" in source
    assert "new URLSearchParams(window.location.search).get('app_id')" in source
    assert "const isApplicazionePage = /^\\/applicazioni\\/[^/]+$/.test(routeKey)" in source
