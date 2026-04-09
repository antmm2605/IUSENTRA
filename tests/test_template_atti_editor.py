import tempfile
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.clienti import GestioneClienti, TipoCliente
from pct.editor import html_to_pdf
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.soggetti import GestioneSoggetti, RuoloSoggetto, TipoSoggetto
from pct.template_atti import (
    DEFAULT_EDITOR_LAYOUT,
    GestionePreferenzeTemplateAtti,
    GestioneTemplateAtti,
    normalizza_editor_layout,
    percorso_preferenze_editor,
)
from web.app import create_app


def _cfg_web(tmp_path):
    return {
        "TESTING": True,
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "REDACTION_ASSISTANT_DB": str(tmp_path / "assistente_redazionale.json"),
        "TEMPLATE_ATTI_DB": str(tmp_path / "template_atti" / "templates.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(tmp_path / "template_atti" / "editor_layout.json"),
    }


def test_preferenze_editor_salvano_e_resettano_layout():
    with tempfile.TemporaryDirectory() as tmp:
        prefs_path = Path(tmp) / "template_atti" / "editor_layout.json"
        gestore = GestionePreferenzeTemplateAtti(str(prefs_path))

        custom = gestore.salva(
            {
                "font_family": "inter",
                "font_size_pt": 13,
                "line_height": 1.75,
                "margin_left_mm": 28,
                "paragraph_spacing_pt": 10,
            }
        )

        assert custom["font_family"] == "inter"
        assert custom["font_size_pt"] == 13
        assert gestore.carica()["margin_left_mm"] == 28

        ripristinato = gestore.reset()
        assert ripristinato == normalizza_editor_layout(DEFAULT_EDITOR_LAYOUT)
        assert gestore.carica()["font_family"] == DEFAULT_EDITOR_LAYOUT["font_family"]


def test_percorso_preferenze_editor_riusa_cartella_template():
    db_path = str(Path("D:/tmp/hacs/template_atti/templates.json"))
    prefs_path = Path(percorso_preferenze_editor(db_path))
    assert prefs_path.name == "editor_layout.json"
    assert prefs_path.parent.name == "template_atti"


def test_html_to_pdf_accetta_layout_editor_personalizzato():
    pdf_bytes = html_to_pdf(
        "<h1>Atto di prova</h1><p>Testo formattato per verifica.</p>",
        "Atto di prova",
        layout={
            "font_family": "inter",
            "font_size_pt": 11,
            "line_height": 1.6,
            "text_align": "left",
            "margin_left_mm": 26,
            "margin_right_mm": 18,
            "margin_top_mm": 22,
            "margin_bottom_mm": 20,
            "paragraph_spacing_pt": 6,
        },
    )
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_form_template_atti_renderizza_modal_importazione_con_variabili(tmp_path):
    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get("/template-atti/nuovo")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="btn-importa-aggiungi"' in html
    assert 'id="btn-importa-sostituisci"' in html
    assert 'contenteditable="true"' in html
    assert "Associa variabili al documento importato" in html
    assert 'data-import-variable="{{ studio_nome }}"' in html
    assert 'data-template-variable="{{ parti.controparte_principale.nome_completo }}"' in html
    assert 'for="importa-doc-input"' in html


def test_template_custom_rende_disponibili_soggetti_e_parti_fascicolo(tmp_path):
    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    clienti = GestioneClienti(db_path=cfg["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Elisabetta",
        cognome="Montagnese",
        codice_fiscale="MNTLBT80A41H501X",
    )

    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Vendita di cose immobili",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        numero_rg="1025",
        tribunale="Tribunale di Palmi",
    )

    soggetti = GestioneSoggetti(
        soggetti_path=cfg["SOGGETTI_DB"],
        parti_path=cfg["SOGGETTI_PARTI_DB"],
    )
    controparte = soggetti.crea(
        TipoSoggetto.PERSONA_FISICA,
        nome="Francesco",
        cognome="Stillitano",
        codice_fiscale="STLFNC80A01H224A",
    )
    soggetti.aggiungi_parte(fascicolo.id, controparte.id, RuoloSoggetto.CONTROPARTE)

    gt = GestioneTemplateAtti(db_path=cfg["TEMPLATE_ATTI_DB"])
    template = gt.crea(
        titolo="Test soggetti",
        categoria="Atti giudiziari",
        corpo="Controparte: {{ parti.controparte_principale.nome_completo }}",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/template-atti/{template.id}/usa",
            data={
                "id_cliente": cliente.id,
                "id_fascicolo": fascicolo.id,
            },
            follow_redirects=True,
        )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Controparte: Stillitano Francesco" in html
