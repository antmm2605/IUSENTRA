"""La consultazione del modello non crea registrazioni di analisi."""
import importlib

from flask import Flask


def test_consultazione_non_apre_registro_scrivibile_ma_post_conserva_audit(monkeypatch):
    routes = importlib.import_module("web.blueprints.template_atti")
    assistant = importlib.import_module("pct.assistente_redazionale")
    captured = []
    monkeypatch.setattr(assistant, "AssistenteRedazionale", lambda **kwargs: captured.append(kwargs) or kwargs)
    monkeypatch.setattr(routes, "_cfg_path", lambda *args: "/governato/tenant/registro.json")
    app = Flask(__name__)
    with app.test_request_context("/api/v1/ui/template-atti/compila/LAV_RIC_001", method="GET"):
        routes._get_assistente_redazionale()
    assert captured[-1]["audit_db_path"] == ""
    with app.test_request_context("/template-atti/api/assistente-redazionale/LAV_RIC_001", method="POST"):
        routes._get_assistente_redazionale()
    assert captured[-1]["audit_db_path"] == "/governato/tenant/registro.json"


def test_bozza_conserva_html_misure_e_avvertenza_del_gate():
    routes = importlib.import_module("web.blueprints.template_atti")
    from pct.editor import misure_del_documento

    text = "Fatti dimostrativi\nConclusioni"
    builder = routes._compiled_editor_html_builder(
        text, '<h2 style="text-align:center">Ricorso</h2><p><strong>Fatti dimostrativi</strong></p>'
        '<p>Conclusioni</p><script>non eseguire</script>',
        {"font_family": "times_new_roman", "font_size_pt": 12, "line_height": 1.6,
         "margin_left_mm": 28, "margin_right_mm": 24},
    )
    result = builder("DA REVISIONARE\n\n" + text)
    assert '<strong>Fatti dimostrativi</strong>' in result
    assert 'style="text-align:center"' in result
    assert "DA REVISIONARE" in result
    assert "non eseguire" not in result
    layout = misure_del_documento(result)
    assert layout["margin_left_mm"] == 28
    assert layout["margin_right_mm"] == 24
    assert "Times New Roman" in layout["font_family_documento"]
    assert layout["font_size_pt"] == 12
    assert layout["line_height"] == 1.6


def test_testo_nativo_resta_disponibile_anche_senza_guida_pratica(monkeypatch):
    api = importlib.import_module("web.blueprints.api_v1_react")
    monkeypatch.setattr(api, "url_for", lambda endpoint, **kwargs: "/" + endpoint)
    app = Flask(__name__)
    with app.test_request_context("/api/v1/ui/template-atti/compila/LAV_RIC_001"):
        result = api._react_template_guide_preview_payload(
            model_code="LAV_RIC_001", model_name="Ricorso lavoro", selected_fascicolo=None,
            selected_cliente=None, guidance={}, stamp={}, initial_text="TESTO DEL MOTORE NATIVO",
        )
    assert result["enabled"] is False
    assert result["initialText"] == "TESTO DEL MOTORE NATIVO"
