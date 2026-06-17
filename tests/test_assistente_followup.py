import json
from pathlib import Path

from lex.contracts import LexResponse
from lex.memory.followup import (
    resolve_followup_query,
    should_trigger_web_search,
)
from web.app import create_app


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {
                    "nome": "Studio Followup Test",
                    "avvocato": "Avv. Followup",
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
                    "from_name": "Studio Followup Test",
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


def _stub_fast_assistente_route(monkeypatch) -> None:
    class _FastLexService:
        def ask(self, request):
            return LexResponse(
                answer="Risposta governata per test follow-up.",
                confidence=0.78,
                answer_mode="grounded",
                metadata={
                    "workflow": getattr(request, "workflow_hint", None) or "question_answering",
                    "provider": "deterministic",
                },
                evidence_summary={
                    "evidence_count": 1,
                    "evidence_sufficient": True,
                },
            )

    def _fake_cached_section_payload(title, question, builder):
        slug = str(title).lower().replace(" ", "-")
        return (
            [f"{title}: contesto sintetico per test."],
            [
                {
                    "id": f"test:{slug}",
                    "title": title,
                    "citation": f"Fonte test - {title}",
                    "text": f"Contesto sintetico per {title}.",
                }
            ],
        )

    monkeypatch.setattr(
        "web.services.assistente_studio_context._cached_section_payload",
        _fake_cached_section_payload,
    )
    monkeypatch.setattr(
        "web.services.assistente_studio_context.build_live_official_web_context",
        lambda question, **kwargs: {
            "lines": [
                "Cassazione: risorsa live raggiunta, titolo 'Sentenza civile recente', URL https://www.cortedicassazione.it/.",
            ],
            "sources": [
                {
                    "id": "live-web:cassazione",
                    "title": "Cassazione",
                    "citation": "Fonte ufficiale live - Cassazione",
                    "text": "Sentenza civile recente. URL ufficiale: https://www.cortedicassazione.it/.",
                }
            ],
            "citations": ["Fonte ufficiale live - Cassazione"],
            "source_ids": ["cassazione"],
        },
    )
    monkeypatch.setattr(
        "lex.http_bounded_bridge._application_lex_service",
        lambda: _FastLexService(),
    )


def test_resolve_followup_query_riusa_il_tema_precedente_per_richiesta_web_breve():
    followup = resolve_followup_query(
        "puoi controllare tu sul web",
        previous_user_text="ultime sentenze sul civile tutti gli ambienti",
    )

    assert followup.is_followup is True
    assert followup.is_web_request is True
    assert followup.reused_previous_topic is True
    assert followup.effective_query == "ultime sentenze sul civile tutti gli ambienti"
    assert followup.reason == "web_request_reuses_previous_topic"


def test_resolve_followup_query_fonde_il_referente_precedente():
    followup = resolve_followup_query(
        "e quelle di oggi",
        previous_user_text="mostrami le udienze imminenti",
    )

    assert followup.is_followup is True
    assert followup.reused_previous_topic is True
    assert followup.effective_query == "mostrami le udienze imminenti e quelle di oggi"
    assert followup.reason == "referential_followup_merged_with_previous"


def test_resolve_followup_query_aggancia_richiesta_pdf_al_tema_precedente():
    followup = resolve_followup_query(
        "la puoi scaricare in pdf",
        previous_user_text="ultime sentenze civili recenti di Cassazione",
    )

    assert followup.is_followup is True
    assert followup.reused_previous_topic is True
    assert followup.effective_query == "ultime sentenze civili recenti di Cassazione la puoi scaricare in pdf"
    assert followup.reason == "download_followup_merged_with_previous"


def test_should_trigger_web_search_esclude_le_richieste_solo_interne():
    assert should_trigger_web_search("udienze di oggi") is False
    assert should_trigger_web_search("ultime sentenze cassazione civile") is True


def test_assistente_context_espone_followup_resolution_quando_eredita_il_tema(tmp_path: Path, monkeypatch):
    _stub_fast_assistente_route(monkeypatch)
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/context",
            json={
                "messages": [
                    {"role": "user", "content": "ultime sentenze sul civile tutti gli ambienti"},
                    {"role": "assistant", "content": "Controllo le pronunce piu' recenti."},
                    {"role": "user", "content": "puoi controllare tu sul web"},
                ]
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["effective_question"] == "ultime sentenze sul civile tutti gli ambienti"
    assert payload["followup_resolution"]["is_followup"] is True
    assert payload["followup_resolution"]["is_web_request"] is True
    assert payload["followup_resolution"]["reused_previous_topic"] is True
    assert payload["followup_resolution"]["effective_query"] == "ultime sentenze sul civile tutti gli ambienti"


def test_assistente_context_guida_l_apertura_su_ricerca_web_sentenze_civili(tmp_path: Path, monkeypatch):
    _stub_fast_assistente_route(monkeypatch)
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/context",
            json={"question": "ricerca web sentenze civili"},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["language_mode"] == "civil_case_law_web"
    assert payload["opening_line"].startswith("Controllo io sul web.")
    assert "Cassazione" in payload["opening_line"]
    assert payload["execution_policy"]["llm_role"] == "voce_e_ragionamento_locale"
    assert payload["execution_policy"]["truth_strategy"] == "fonti_ufficiali_verificate"
    assert payload["execution_policy"]["requires_verified_legal_reference"] is True


def test_assistente_context_copre_l_area_economica_di_studio(tmp_path: Path, monkeypatch):
    _stub_fast_assistente_route(monkeypatch)
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/context",
            json={"question": "mi controlli preventivi, fatturazione e pagamenti"},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["focus_topic"] == "economico"
    assert "Tariffario, preventivi, fatturazione e pagamenti" in payload["competence_labels"]
