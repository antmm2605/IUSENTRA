import json
from pathlib import Path
from types import SimpleNamespace

from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.local_ai import LocalAIService
from pct.local_ai_runtime import OllamaRuntimeProvisioner
from web.app import create_app


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_studio_config(path: Path, enabled: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {"nome": "Studio Test"},
                "ai": {
                    "enabled": enabled,
                    "base_url": "http://127.0.0.1:11434/api",
                    "auto_bootstrap": True,
                    "chat_model": "",
                    "embed_model": "",
                    "keep_alive": "10m",
                    "auto_index_documents": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _service(tmp_path: Path, *, enabled: bool = True) -> LocalAIService:
    config_path = tmp_path / "config" / "studio.json"
    _write_studio_config(config_path, enabled=enabled)
    return LocalAIService(
        db_path=str(tmp_path / "intelligence" / "local_ai.db"),
        policy_path=str(REPO_ROOT / "config" / "ai-policy.json"),
        config_path=str(config_path),
        app_root=str(REPO_ROOT),
        models_path=str(tmp_path / "intelligence" / "models"),
    )


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
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
        "LOCAL_AI_DB": str(tmp_path / "intelligence" / "local_ai.db"),
        "LOCAL_AI_POLICY": str(REPO_ROOT / "config" / "ai-policy.json"),
        "LOCAL_AI_MODELS_DIR": str(tmp_path / "intelligence" / "models"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
        "PORTALE_DB": str(tmp_path / "portale" / "portali.json"),
        "PORTALE_UPLOADS": str(tmp_path / "portale" / "uploads"),
    }


def test_local_ai_bootstrap_disabled_is_non_blocking(tmp_path: Path):
    service = _service(tmp_path, enabled=False)

    result = service.bootstrap_runtime()
    snapshot = service.health_snapshot()

    assert result["status"] == "disabled"
    assert snapshot["runtime"]["status"] == "disabled"


def test_local_ai_index_and_hybrid_search(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    document_path = tmp_path / "atto.txt"
    document_path.write_text(
        "TRIBUNALE DI PALERMO\n\nIN DIRITTO\n\nOpposizione a decreto ingiuntivo con contestazione estratti conto.",
        encoding="utf-8",
    )

    indexed = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC1",
        practice_id="P1",
        file_path=str(document_path),
        title="Atto di opposizione",
    )
    assert indexed["status"] == "indexed"
    assert indexed["chunk_count"] >= 1

    class DummyClient:
        def embed_texts(self, model_name, inputs):
            return {"embeddings": [[1.0, 0.0]], "load_duration": 1, "prompt_eval_count": 3}

    monkeypatch.setattr(service, "bootstrap_runtime", lambda force=False: {"status": "ready", "embed_model": "embeddinggemma:300m"})
    monkeypatch.setattr(service, "_ollama_client", lambda settings=None: DummyClient())
    monkeypatch.setattr(service, "_active_model", lambda role: "embeddinggemma:300m" if role == "embed" else "gemma3:1b")
    embedded = service.embed_pending_chunks(limit=20)
    assert embedded["embedded"] >= 1

    results = service.hybrid_search("decreto ingiuntivo opposizione", practice_id="P1", top_k=3)

    assert results
    assert results[0]["document_id"]
    assert "Atto di opposizione" in results[0]["citation"]


def test_local_ai_health_snapshot_exposes_installer_and_resolved_models(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)

    class DummyProvisioner:
        def installer_snapshot(self, *, live_version=None):
            return {
                "strategy_label": "Runtime locale gestito sullo stesso host di HACS",
                "summary_title": "Provisioning automatico disponibile",
                "summary_body": "Runtime installato e avviato sulla stessa macchina di HACS.",
                "managed_runtime_dir": str(tmp_path / "bin" / "ollama"),
            }

    monkeypatch.setattr(service, "_runtime_provisioner", lambda: DummyProvisioner())

    snapshot = service.health_snapshot()

    assert snapshot["installer"]["strategy_label"] == "Runtime locale gestito sullo stesso host di HACS"
    assert snapshot["resolved_models"]["chat"]
    assert snapshot["resolved_models"]["embed"]


def test_local_ai_health_snapshot_fallback_su_modello_installato_disponibile(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)

    class DummyProvisioner:
        def installer_snapshot(self, *, live_version=None):
            return {"strategy_label": "Runtime locale gestito"}

    class DummyClient:
        def list_models(self):
            return [{"name": "gemma3:1b"}, {"name": "embeddinggemma:300m"}]

        def list_running_models(self):
            return [{"name": "gemma3:1b"}]

    monkeypatch.setattr(service, "_runtime_provisioner", lambda: DummyProvisioner())
    monkeypatch.setattr(
        service,
        "_detect_hardware",
        lambda: {
            "profile": "strong",
            "ram_gb": 32.0,
            "disk_free_gb": 60.0,
            "cpu_name": "CPU Test",
            "gpu_vendor": "",
            "gpu_name": "",
            "os_version": "Windows 11",
        },
    )
    monkeypatch.setattr(service, "_resolve_live_runtime", lambda settings: (DummyClient(), "0.20.5", settings.base_url))

    snapshot = service.health_snapshot()

    assert snapshot["preferred_models"]["chat"] == "gemma3:4b"
    assert snapshot["resolved_models"]["chat"] == "gemma3:1b"
    assert snapshot["resolved_models"]["embed"] == "embeddinggemma:300m"


def test_local_ai_active_model_fallback_su_runtime_disponibile(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)

    class DummyClient:
        def list_models(self):
            return [{"name": "gemma3:1b"}, {"name": "embeddinggemma:300m"}]

        def list_running_models(self):
            return [{"name": "gemma3:1b"}]

    monkeypatch.setattr(
        service,
        "_detect_hardware",
        lambda: {
            "profile": "strong",
            "ram_gb": 32.0,
            "disk_free_gb": 60.0,
            "cpu_name": "CPU Test",
            "gpu_vendor": "",
            "gpu_name": "",
            "os_version": "Windows 11",
        },
    )
    monkeypatch.setattr(service, "_resolve_live_runtime", lambda settings: (DummyClient(), "0.20.5", settings.base_url))

    assert service._active_model("chat") == "gemma3:1b"
    assert service._active_model("embed") == "embeddinggemma:300m"


def test_local_ai_ask_fascicolo_builds_context_and_returns_answer(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    captured: dict[str, str] = {}

    class DummyClient:
        def generate(self, model_name, prompt, keep_alive="10m"):
            captured["prompt"] = prompt
            return {
                "response": "Risposta operativa.\n\nFonti\n- Atto di opposizione",
                "load_duration": 1,
                "prompt_eval_count": 4,
                "eval_count": 12,
            }

    monkeypatch.setattr(service, "bootstrap_runtime", lambda force=False: {"status": "ready", "chat_model": "gemma3:1b"})
    monkeypatch.setattr(service, "index_fascicolo_documents", lambda *args, **kwargs: {"indexed": 1, "skipped": 0, "unsupported": 0, "errors": []})
    monkeypatch.setattr(service, "embed_pending_chunks", lambda *args, **kwargs: {"status": "ready", "embedded": 1})
    monkeypatch.setattr(
        service,
        "hybrid_search",
        lambda *args, **kwargs: [
            {
                "id": "chunk-1",
                "document_id": "doc-1",
                "practice_id": "F1",
                "section_type": "diritto",
                "page_from": 1,
                "page_to": 1,
                "text": "Opposizione a decreto ingiuntivo fondata su contestazione degli estratti conto.",
                "citation": "Atto di opposizione, p. 1 · diritto · chunk chunk-1",
            }
        ],
    )
    monkeypatch.setattr(service, "_ollama_client", lambda settings=None: DummyClient())

    fascicolo = SimpleNamespace(
        id="F1",
        titolo="Opposizione DI",
        oggetto="Opposizione a decreto ingiuntivo",
        tribunale="Tribunale di Palermo",
        numero_rg="123",
        anno_rg=2026,
        controparte="Beta Srl",
        stato=SimpleNamespace(value="APERTO"),
        tipo=SimpleNamespace(value="CIVILE"),
        documenti=[],
    )

    result = service.ask_fascicolo(
        fascicolo=fascicolo,
        documents_dir=str(tmp_path / "docs"),
        question="Quali sono i prossimi rischi processuali?",
        apps=[],
        scadenze=[],
        workspace={"prossime_azioni": ["Verificare comparsa conclusionale"]},
        intelligenza={"evidenze": ["Scadenza memoria 183 in arrivo"]},
    )

    assert result["ok"] is True
    assert "Opposizione DI" in captured["prompt"]
    assert "Atto di opposizione" in captured["prompt"]
    assert "Scadenza memoria 183 in arrivo" in captured["prompt"]
    assert result["answer"].startswith("Risposta operativa")


def test_api_local_ai_status_and_fascicolo_ai(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fascicolo = gf.nuovo("Pratica opposizione", TipoFascicolo.CIVILE)

    monkeypatch.setattr(
        LocalAIService,
        "ask_fascicolo",
        lambda self, **kwargs: {"ok": True, "status": "ready", "answer": "Analisi fascicolo", "citations": ["Fonte A"], "sources": []},
    )

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)

        status_response = client.get("/api/local-ai/status")
        fascicolo_response = client.post(
            f"/api/fascicoli/{fascicolo.id}/ai",
            json={"question": "Che cosa presidio oggi?"},
        )

    assert status_response.status_code == 200
    assert "runtime" in status_response.get_json()
    assert fascicolo_response.status_code == 200
    assert fascicolo_response.get_json()["ok"] is True
    assert fascicolo_response.get_json()["answer"] == "Analisi fascicolo"


def test_api_local_ai_context_endpoints_prepare_payloads(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fascicolo = gf.nuovo("Pratica contesto AI", TipoFascicolo.CIVILE)

    monkeypatch.setattr(
        LocalAIService,
        "prepare_fascicolo_query",
        lambda self, **kwargs: {
            "ok": True,
            "query_type": "fascicolo_ai",
            "question": kwargs["question"],
            "prompt": "Contesto fascicolo pronto",
            "sources": [{"id": "chunk-fascicolo"}],
            "citations": ["Fonte fascicolo"],
        },
    )
    monkeypatch.setattr(
        LocalAIService,
        "prepare_workspace_query",
        lambda self, **kwargs: {
            "ok": True,
            "query_type": "workspace_ai",
            "question": kwargs["question"],
            "prompt": "Contesto workspace pronto",
            "sources": [{"id": "chunk-workspace"}],
            "citations": ["Fonte workspace"],
        },
    )

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        fascicolo_response = client.post(
            f"/api/fascicoli/{fascicolo.id}/ai/context",
            json={"question": "Quale memoria devo preparare?"},
        )
        workspace_response = client.post(
            "/api/workspace-intelligente/ai/context",
            json={"question": "Quali priorita' operative ho oggi?", "giorni": 7},
        )

    assert fascicolo_response.status_code == 200
    assert fascicolo_response.get_json()["ok"] is True
    assert fascicolo_response.get_json()["prompt"] == "Contesto fascicolo pronto"
    assert fascicolo_response.get_json()["citations"] == ["Fonte fascicolo"]

    assert workspace_response.status_code == 200
    assert workspace_response.get_json()["ok"] is True
    assert workspace_response.get_json()["prompt"] == "Contesto workspace pronto"
    assert workspace_response.get_json()["citations"] == ["Fonte workspace"]


def test_api_assistente_context_prepara_prompt_per_companion_locale(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fascicolo = gf.nuovo("Opposizione a decreto ingiuntivo", TipoFascicolo.CIVILE)

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/context",
            json={
                "question": "Qual e' la prossima attivita' operativa?",
                "fascicolo_id": fascicolo.id,
                "messages": [
                    {"role": "user", "content": "Ho appena aperto il fascicolo."},
                    {"role": "assistant", "content": "Perfetto, possiamo impostare le prossime azioni."},
                ],
            },
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["query_type"] == "assistente_chat"
    assert payload["question"] == "Qual e' la prossima attivita' operativa?"
    assert "CONTESTO FASCICOLO ATTIVO" in payload["prompt"]
    assert "CONVERSAZIONE RECENTE" in payload["prompt"]
    assert fascicolo.id in payload["prompt"]
    assert payload["sources"] == []


def test_impostazioni_template_contains_ai_locale_tab():
    html = (REPO_ROOT / "web" / "templates" / "impostazioni" / "index.html").read_text(encoding="utf-8")

    assert "AI Locale" in html
    assert "Prepara runtime automatico" in html
    assert "runLocalAiBootstrap" in html
    assert "Companion locale sul dispositivo cliente" in html
    assert "127.0.0.1:27272" in html
    assert "ai-installer-summary" in html
    assert "http://host.docker.internal:11434/api" in html
    assert "/api/version" in html


def test_ollama_runtime_provisioner_selects_windows_zip_asset(tmp_path: Path):
    provisioner = OllamaRuntimeProvisioner(
        app_root=tmp_path,
        models_path=tmp_path / "models",
        platform_name="windows",
        machine_name="AMD64",
    )

    release = {
        "version": "v0.20.6",
        "assets": [
            {
                "name": "ollama-windows-amd64.zip",
                "browser_download_url": "https://example.test/ollama-windows-amd64.zip",
                "size": 781000000,
                "updated_at": "2026-04-12T22:13:20Z",
            },
            {
                "name": "ollama-windows-arm64.zip",
                "browser_download_url": "https://example.test/ollama-windows-arm64.zip",
                "size": 650000000,
                "updated_at": "2026-04-12T22:13:20Z",
            },
        ],
    }

    asset = provisioner.select_download_asset(release)

    assert asset is not None
    assert asset["name"] == "ollama-windows-amd64.zip"


def test_ollama_runtime_provisioner_prefers_host_bridge_strategy_on_windows_host_container(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PCT_HOST_PLATFORM", "Windows_NT")
    monkeypatch.setenv("PCT_HOST_MACHINE", "AMD64")
    monkeypatch.setattr(OllamaRuntimeProvisioner, "_detect_execution_platform_name", lambda self: "linux")
    monkeypatch.setattr(OllamaRuntimeProvisioner, "_detect_containerized", lambda self: True)
    monkeypatch.setattr(
        OllamaRuntimeProvisioner,
        "fetch_latest_release",
        lambda self, **kwargs: {
            "version": "v0.20.6",
            "html_url": "https://example.test/releases/v0.20.6",
            "published_at": "2026-04-13T00:59:00Z",
            "assets": [
                {
                    "name": "ollama-windows-amd64.zip",
                    "browser_download_url": "https://example.test/ollama-windows-amd64.zip",
                    "size": 781000000,
                    "updated_at": "2026-04-13T00:59:00Z",
                }
            ],
        },
    )

    provisioner = OllamaRuntimeProvisioner(
        app_root=tmp_path,
        models_path=tmp_path / "models",
    )

    snapshot = provisioner.installer_snapshot()

    assert snapshot["host_platform"] == "windows"
    assert snapshot["execution_platform"] == "linux"
    assert snapshot["strategy_code"] == "host_bridge_windows"
    assert snapshot["asset_name"] == "ollama-windows-amd64.zip"


def test_local_ai_settings_env_override_runtime_url(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PCT_LOCAL_AI_BASE_URL", "http://ollama:11434/api")
    service = _service(tmp_path)

    settings = service._load_settings()

    assert settings.base_url == "http://ollama:11434/api"
