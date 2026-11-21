"""Widget Lex nelle pagine React: componente LexWidget con lo stesso contratto DOM del template classico."""

from __future__ import annotations

import re
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
COMPONENTE = RADICE / "frontend/src/components/lex/LexWidget.tsx"
TEMPLATE = RADICE / "web/templates/components/pct_ai_widget.html"


def _id(testo: str) -> set[str]:
    return set(re.findall(r'\bid="([^"{]+)"', testo))


def test_componente_ha_gli_stessi_id_e_attributi_del_controllore():
    componente = COMPONENTE.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    assert _id(template) <= _id(componente)
    for attributo in re.findall(r"\b(data-[a-z-]+)=", template):
        assert f"{attributo}=" in componente, attributo
    for percorso in (
        "/api/assistente/chat", "/api/assistente/stato", "/api/assistente/context",
        "/api/assistente/warmup", "/api/assistente/attachments", "/api/assistente/documento",
    ):
        assert percorso in componente
    for testo in ("Ciao, sono Lex.", "Carica documenti", "Cerca sul web", "Ridimensiona la finestra di Lex"):
        assert testo in componente
    assert "style=" not in componente


def test_shell_react_monta_il_widget_e_il_controllore_si_avvia_anche_dopo_il_caricamento():
    shell = (RADICE / "web/templates/react_shell.html").read_text(encoding="utf-8")
    entry = (RADICE / "frontend/src/reactEntry.tsx").read_text(encoding="utf-8")
    controllore = (RADICE / "web/static/js/pct-lex-assistant.js").read_text(encoding="utf-8")
    assert 'include "components/pct_ai_widget.html"' not in shell
    assert '<div id="lex-widget-root" data-versione="{{ app_version }}"></div>' in shell
    assert "{% if not iusentra_embedded_source_view and g.utente_corrente %}" in shell
    assert "import('./components/lex/LexWidget')" in entry
    assert "window.addEventListener('iusentra:lex-widget-montato', init);" in controllore
    assert "if (avviato) return;" in controllore
    assert "iusentra:lex-widget-montato" in COMPONENTE.read_text(encoding="utf-8")


def test_shell_react_senza_widget_nelle_viste_incorporate_e_senza_utente(tmp_path):
    from tests.test_applicazioni import _crea_operatore, _login
    from tests.test_react_shell import _app

    app = _app(tmp_path)
    _crea_operatore(app)
    with app.test_client() as client:
        _login(client)
        pagina = client.get("/fascicoli").get_data(as_text=True)
        incorporata = client.get("/fascicoli?embed=source").get_data(as_text=True)
    assert pagina.count('id="lex-widget-root"') == 1
    assert 'id="pct-ai-widget"' not in pagina
    assert 'id="lex-widget-root"' not in incorporata


def test_finestra_di_lex_senza_diciture_tecniche_e_mai_offline_senza_modello():
    """Collaudo 21/11: senza modello la finestra diceva «Offline» e «Motore AI non disponibile»."""
    componente = COMPONENTE.read_text(encoding="utf-8")
    controllore = (RADICE / "web/static/js/pct-lex-assistant.js").read_text(encoding="utf-8")
    for testo in ("Web libero", "Assistente PCT"):
        assert testo not in componente
    for testo in ("Web libero", "Lex Operativo", "Motore AI non disponibile", "updateBadge(false, 'Offline')"):
        assert testo not in controllore
    assert "motore delle fonti certe" in controllore
