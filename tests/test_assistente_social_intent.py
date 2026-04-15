import json
from pathlib import Path

from lex.context.today_summary import build_today_operational_summary
from lex.memory.social_intent import (
    build_daily_overview_lead,
    build_relational_reply,
    build_social_only_reply,
    prepend_social_prefix,
    resolve_social_and_operational_intent,
)
from web.app import create_app


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {
                    "nome": "Studio Intent Test",
                    "avvocato": "Avv. Intent",
                    "indirizzo": "Via Roma 12",
                    "city": "Taurianova",
                    "province": "RC",
                    "telefono": "0966 123456",
                    "email": "studio@example.it",
                },
                "pec": {
                    "indirizzo": "studio@pec.example.it",
                    "password": "segreta",
                    "smtp_host": "smtp.pec.aruba.it",
                    "smtp_port": 465,
                    "imap_host": "imaps.pec.aruba.it",
                    "imap_port": 993,
                    "use_ssl": True,
                },
                "smtp": {
                    "host": "smtp.office365.com",
                    "port": 587,
                    "username": "studio@example.it",
                    "from_address": "studio@example.it",
                    "from_name": "Studio Intent Test",
                    "use_tls": True,
                },
                "ai": {
                    "enabled": True,
                    "base_url": "http://127.0.0.1:11434/api",
                    "auto_bootstrap": True,
                    "chat_model": "gemma3:1b",
                    "embed_model": "embeddinggemma:300m",
                    "keep_alive": "10m",
                    "auto_index_documents": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH": str(tmp_path / "bootstrap_admin.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json"),
        "NORMATIVE_TABLES_DB": str(tmp_path / "intelligence" / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(tmp_path / "intelligence" / "giurisprudenza.json"),
        "WORKSPACE_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "workspace_intelligence.json"),
        "TEMPLATE_ATTI_DB": str(tmp_path / "template_atti" / "templates.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(tmp_path / "template_atti" / "editor_layout.json"),
        "PREVENTIVI_DB": str(tmp_path / "preventivi" / "preventivi.json"),
        "FATTURAZIONE_DB": str(tmp_path / "fatturazione" / "parcelle.json"),
        "LOCAL_AI_DB": str(tmp_path / "intelligence" / "local_ai.db"),
        "LOCAL_AI_POLICY": str(REPO_ROOT / "config" / "ai-policy.json"),
        "LOCAL_AI_MODELS_DIR": str(tmp_path / "intelligence" / "models"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
        "PORTALE_DB": str(tmp_path / "portale" / "portali.json"),
        "PORTALE_UPLOADS": str(tmp_path / "portale" / "uploads"),
    }


def test_social_intent_riconosce_saluto_semplice_e_saluto_con_richiesta():
    simple = resolve_social_and_operational_intent("buongiorno")
    mixed = resolve_social_and_operational_intent("buongiorno oggi cosa dobbiamo fare")

    assert simple.is_social_only is True
    assert simple.social_kind == "greeting"
    assert build_social_only_reply(simple.social_kind, simple.raw_text) == "Buongiorno. Dimmi pure."

    assert mixed.is_social_with_request is True
    assert mixed.social_prefix == "Buongiorno."
    assert mixed.is_daily_overview is True
    assert mixed.effective_query == "oggi cosa dobbiamo fare"


def test_social_intent_riusa_il_tema_precedente_per_followup_breve():
    routing = resolve_social_and_operational_intent(
        "e oggi?",
        previous_user_text="udienze imminenti",
    )

    assert routing.is_followup is True
    assert routing.reused_previous_topic is True
    assert routing.is_daily_overview is False
    assert routing.effective_query == "udienze imminenti e oggi?"


def test_social_intent_tratta_come_stai_oggi_come_messaggio_relazionale():
    routing = resolve_social_and_operational_intent(
        "come stai oggi",
        previous_user_text="ultime sentenze civili recenti",
    )

    assert routing.is_social_only is True
    assert routing.social_kind == "smalltalk"
    assert routing.is_followup is False
    assert routing.reused_previous_topic is False
    assert build_relational_reply("come stai oggi") == "Bene, grazie. Dimmi pure."
    assert build_social_only_reply(routing.social_kind, routing.raw_text) == "Bene, grazie. Dimmi pure."


def test_build_daily_overview_lead_e_prepend_social_prefix_restano_sobri():
    assert build_daily_overview_lead("Buongiorno.") == "Buongiorno. Ti faccio subito il quadro operativo di oggi."
    assert prepend_social_prefix("Buongiorno.", "Ti faccio subito il quadro operativo di oggi.") == "Buongiorno. Ti faccio subito il quadro operativo di oggi."


def test_today_operational_summary_costruisce_un_quadro_professionale(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_request_context("/"):
        summary = build_today_operational_summary(question="oggi cosa dobbiamo fare")

    assert summary["focus_label"] == "quadro operativo di oggi"
    assert summary["focus_topic"] == "today_operational_overview"
    assert summary["effective_question"] == "oggi cosa dobbiamo fare"
    assert summary["lead_text"] == "Ti faccio subito il quadro operativo di oggi."
    assert "=== QUADRO OPERATIVO ===" in summary["prompt_block"]
    assert "=== AGENDA ===" in summary["prompt_block"]
    assert "=== SCADENZIARIO ===" in summary["prompt_block"]
    assert "=== FASCICOLI ===" in summary["prompt_block"]
    assert "=== FATTURAZIONE ===" in summary["prompt_block"]
    assert "=== APPLICAZIONI ===" in summary["prompt_block"]


def test_assistente_context_gestisce_overview_giornaliera_con_apertura_professionale(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/context",
            json={"question": "buongiorno oggi cosa dobbiamo fare"},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["routing"]["is_daily_overview"] is True
    assert payload["routing"]["is_social_with_request"] is True
    assert payload["daily_overview_lead"] == "Buongiorno. Ti faccio subito il quadro operativo di oggi."
    assert payload["focus_label"] == "quadro operativo di oggi"
    assert "Apertura iniziale da mantenere:" in payload["prompt"]
