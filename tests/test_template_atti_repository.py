from pathlib import Path

from flask import Flask

from pct.template_atti import GestioneTemplateAtti
from web.services.assistente_studio_context import _template_atti_lines


def test_template_repository_sincronizza_builtin_e_seleziona_il_template_migliore(tmp_path: Path):
    db_path = tmp_path / "template_atti" / "templates.json"
    gestore = GestioneTemplateAtti(str(db_path))

    stats = gestore.statistiche_repository()
    selection = gestore.select_best_templates(
        "ricorso per decreto ingiuntivo",
        area="Civile",
        limit=3,
    )

    assert Path(gestore.repository_db_path).exists()
    assert Path(gestore.repository_json_path).exists()
    assert stats["template_repository"] >= 100
    assert stats["template_fields"] > 0
    best = selection["best_template"]
    assert best is not None
    assert best["titolo"] == "Ricorso per decreto ingiuntivo"
    assert best["campi_guidati"]
    assert best["allegati_obbligatori"]
    assert best["controlli_conformita"]
    assert any(binding["binding_value"] == "CIV_RDI_001" for binding in best["bindings"])


def test_template_repository_aggiorna_anche_i_template_custom(tmp_path: Path):
    db_path = tmp_path / "template_atti" / "templates.json"
    gestore = GestioneTemplateAtti(str(db_path))

    custom = gestore.crea(
        titolo="Memoria personalizzata ATP",
        categoria="Civile ordinario",
        corpo="Corpo personalizzato {{ oggetto_atto }}",
        area="Civile",
        branca="Civile ordinario",
        sottobranca="Istruttoria",
        fase="Trattazione",
        rito="Ordinario",
        canale_telematico="PCT",
        profilo_deposito="atto_successivo",
        parole_chiave=["ATP", "memoria tecnica"],
        campi_guidati=[
            {
                "name": "oggetto_atto",
                "label": "Oggetto atto",
                "type": "text",
                "section": "Intestazione",
                "placeholder": "Oggetto",
                "help_text": "Sintesi dell'istanza",
                "rows": 1,
            }
        ],
        allegati_obbligatori=["Verbale ATP", "Documentazione tecnica"],
        controlli_conformita=["Controllo richiamo ATP", "Controllo allegati tecnici"],
    )

    selection = gestore.select_best_templates(
        "memoria personalizzata atp",
        area="Civile",
        fase="Trattazione",
        limit=3,
    )
    payload = gestore.repository_payload()

    assert selection["best_template"] is not None
    assert selection["best_template"]["template_id"] == custom.id
    assert selection["best_template"]["builtin"] == 0
    assert any(item["template_id"] == custom.id for item in payload["templates"])


def test_template_atti_lines_usa_repository_strutturato(tmp_path: Path):
    app = Flask(__name__)
    app.config["TEMPLATE_ATTI_DB"] = str(tmp_path / "template_atti" / "templates.json")

    with app.app_context():
        lines, sources = _template_atti_lines("ricorso per decreto ingiuntivo")

    assert any("Repository strutturato:" in line for line in lines)
    assert any("Template consigliato:" in line for line in lines)
    assert any("Campi da completare:" in line for line in lines)
    assert any(source["id"].startswith("template:") for source in sources)
    main_source = next(source for source in sources if source["id"].startswith("template:"))
    assert main_source["template_fields"]
    assert main_source["template_checks"]
    assert main_source["template_required_attachments"]
