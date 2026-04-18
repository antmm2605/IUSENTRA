import base64
import io
import json
import sqlite3
import zipfile
from pathlib import Path
from types import SimpleNamespace

from lex.prompts.prompt_builder import build_assistente_prompt
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.local_ai import LocalAIService
from pct.local_ai_runtime import OllamaRuntimeProvisioner
from web.app import create_app
from web.services.storage_runtime import get_request_studio_db


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_studio_config(path: Path, enabled: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {
                    "nome": "Studio Test",
                    "avvocato": "Avv. Test",
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
                    "from_name": "Studio Test",
                    "use_tls": True,
                },
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
        "MULTI_TENANT": False,
        "SECRET_KEY": "test",
        "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH": str(tmp_path / "auth" / "bootstrap_admin.json"),
        "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
        "CONDIVISIONI_DB": str(tmp_path / "clienti" / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(tmp_path / "fascicoli" / "archivio"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi" / "storico.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_path / "search" / "index.db"),
        "OCR_QUEUE_DB": str(tmp_path / "search" / "ocr_jobs.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti" / "anagrafica.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "soggetti" / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "intelligence" / "validation_runs.json"),
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


def _gestione_fascicoli_runtime(cfg: dict[str, str]) -> GestioneFascicoli:
    return GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
        studio_db=get_request_studio_db(cfg["CLIENTI_DB"]),
    )


def test_local_ai_bootstrap_disabled_is_non_blocking(tmp_path: Path):
    service = _service(tmp_path, enabled=False)

    result = service.bootstrap_runtime()
    snapshot = service.health_snapshot()

    assert result["status"] == "disabled"
    assert snapshot["runtime"]["status"] == "disabled"


def test_assistente_prompt_separa_voce_e_regole_tecniche():
    prompt = build_assistente_prompt(
        question="Verifica l'ultima sentenza civile e un problema di firma digitale",
        fascicolo_id="",
    )

    assert "=== IDENTITA' E VOCE DI LEX ===" in prompt
    assert "=== STILE DI RISPOSTA ===" in prompt
    assert "=== COMPORTAMENTO OPERATIVO ===" in prompt
    assert "=== ARCHITETTURA DECISIONALE DI LEX ===" in prompt
    assert "presenza operativa di studio" in prompt
    assert "Il LLM serve per tono umano, scrittura, sintesi, follow-up, riformulazione e spiegazioni operative." in prompt
    assert "Il LLM non e' il cervello unico del sistema e non decide da solo cosa e' vero." in prompt
    assert "richiesta breve ma chiaramente tematizzata" in prompt
    assert "Le domande brevi successive vanno interpretate in continuita' con il turno precedente." in prompt
    assert "Non riaprire ogni risposta con \"Ciao, sono Lex.\"" in prompt
    assert "Quando l'utente chiede di cercare, controllare, verificare o guardare qualcosa sul web" in prompt
    assert "In questi casi esegui la ricerca e usa le fonti ufficiali pertinenti" in prompt
    assert "Se il tema e' gia' chiaro dal turno precedente, Lex deve unire i due elementi e agire su quel tema" in prompt
    assert "Se la richiesta riguarda solo dati interni di studio, non aprire una ricerca web." in prompt
    assert "ricerca web sentenze civili" in prompt
    assert "Controllo io. Parto dalle sentenze civili piu' recenti e rilevanti" in prompt
    assert "Non usare mai testo-segnaposto o placeholder artificiali" in prompt
    assert "=== AFFIDABILITA' DEI RIFERIMENTI LEGALI ===" in prompt
    assert "Lex non deve mai inventare estremi specifici di sentenze" in prompt
    assert "Non ho ancora una pronuncia verificata da citare con numero e PDF." in prompt
    assert "I messaggi relazionali come \"come stai\", \"come va\", \"tutto bene\" e \"come stai oggi\"" in prompt
    assert "=== GESTIONE DELLA RELAZIONE QUOTIDIANA ===" in prompt
    assert "Se il messaggio e' solo sociale o relazionale" in prompt
    assert "Se il messaggio combina cortesia e richiesta operativa" in prompt
    assert "Quando l'utente chiede cosa fare oggi, da dove partire o qual e' il quadro della giornata" in prompt
    assert "Se l'utente fa un follow-up breve come \"cosa dobbiamo fare\", \"e oggi?\" o \"da dove partiamo?\"" in prompt
    assert "=== AGGIORNAMENTI E FONTI UFFICIALI ===" in prompt
    assert "=== REGOLE TECNICHE PEC E FIRMA ===" in prompt


def test_assistente_prompt_aggiunge_apertura_relazionale_quando_serve():
    prompt = build_assistente_prompt(
        question="mi controlli le udienze di oggi?",
        fascicolo_id="",
        social_prefix="Buongiorno.",
        social_kind="greeting_with_request",
    )

    assert "Apertura relazionale da mantenere:" in prompt
    assert "- Apri in modo breve e naturale con: Buongiorno." in prompt
    assert "Segnale sociale rilevato: greeting_with_request." in prompt


def test_assistente_prompt_supporta_apertura_iniziale_guidata():
    prompt = build_assistente_prompt(
        question="oggi cosa dobbiamo fare",
        fascicolo_id="",
        opening_line="Buongiorno. Ti faccio subito il quadro operativo di oggi.",
    )

    assert "Apertura iniziale da mantenere:" in prompt
    assert "- Apri esattamente con: Buongiorno. Ti faccio subito il quadro operativo di oggi." in prompt


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


def test_local_ai_index_file_supporta_p7m_con_payload_estratto(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    document_path = tmp_path / "memoria.pdf.p7m"
    document_path.write_bytes(b"fake-p7m")
    monkeypatch.setattr(
        "pct.local_ai.inspect_signed_document_bytes",
        lambda **kwargs: SimpleNamespace(
            status=SimpleNamespace(
                payload_available=True,
                payload_mime="application/pdf",
                detached_signature=False,
                to_dict=lambda: {
                    "payload_available": True,
                    "payload_mime": "application/pdf",
                    "detached_signature": False,
                },
            ),
            payload_bytes=b"%PDF-1.4 test",
        ),
    )

    indexed = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-P7M",
        practice_id="P1",
        file_path=str(document_path),
        title="Memoria firmata",
    )

    assert indexed["status"] == "indexed"
    assert indexed["mime_type"] == "application/pdf"
    assert indexed["outer_mime_type"] == "application/pkcs7-mime"


def test_local_ai_index_fascicolo_supporta_p7m_detached_con_versione_originale(tmp_path: Path):
    from asn1crypto import algos, cms

    service = _service(tmp_path)
    cfg = _cfg_web(tmp_path)
    gestione_fascicoli = _gestione_fascicoli_runtime(cfg)
    fascicolo = gestione_fascicoli.nuovo("RG 701/2026", TipoFascicolo.CIVILE)
    originale = b"%PDF-1.4\n% originale\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    documento = gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "memoria.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        originale,
        caricato_da="admin",
    )
    signed = cms.SignedData(
        {
            "version": "v1",
            "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
            "encap_content_info": {"content_type": "data"},
            "signer_infos": [],
        }
    )
    p7m_detached = cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump()
    gestione_fascicoli.sostituisci_documento(
        fascicolo.id,
        documento.id,
        nome_file="memoria.pdf.p7m",
        contenuto=p7m_detached,
        caricato_da="admin",
        note="Versione firmata",
    )
    gestione_fascicoli.segna_firmato(fascicolo.id, documento.id)

    outcome = service.index_fascicolo_documents(fascicolo, cfg["FASCICOLI_DOCS"])

    assert outcome["indexed"] == 1
    assert outcome["unsupported"] == 0
    assert outcome["indexed_items"][0]["mime_type"] == "application/pdf"
    assert outcome["indexed_items"][0]["signed_status"]["detached_signature"] is True


def test_prepare_workspace_query_restituisce_snapshot(tmp_path: Path):
    service = _service(tmp_path)

    prepared = service.prepare_workspace_query(
        question="Qual e la prossima azione giusta di oggi?",
        overview={
            "actions": [{"title": "Presidiare scadenza urgente", "description": "Termine entro 48 ore"}],
            "summary": {"scadenze_urgenti": 1, "fascicoli_attenzionati": 2},
            "fascicoli_hot": [{"titolo": "Opposizione banca", "azioni": ["Preparare deposito memoria"]}],
        },
    )

    assert prepared["ok"] is True
    assert prepared["snapshot"]["summary"]["scadenze_urgenti"] == 1
    assert prepared["snapshot"]["actions"][0]["title"] == "Presidiare scadenza urgente"


def test_local_ai_health_snapshot_exposes_installer_and_resolved_models(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)

    class DummyProvisioner:
        def installer_snapshot(self, *, live_version=None):
            return {
                "strategy_label": "Runtime locale gestito sullo stesso host di IUSENTRA",
                "summary_title": "Provisioning automatico disponibile",
                "summary_body": "Runtime installato e avviato sulla stessa macchina di IUSENTRA.",
                "managed_runtime_dir": str(tmp_path / "bin" / "ollama"),
            }

    monkeypatch.setattr(service, "_runtime_provisioner", lambda: DummyProvisioner())

    snapshot = service.health_snapshot()

    assert snapshot["installer"]["strategy_label"] == "Runtime locale gestito sullo stesso host di IUSENTRA"
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
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)

    gf = _gestione_fascicoli_runtime(cfg)
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
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)

    gf = _gestione_fascicoli_runtime(cfg)
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
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)

    gf = _gestione_fascicoli_runtime(cfg)
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
    assert "Fascicolo attivo:" in payload["prompt"]
    assert "Memoria di sessione:" in payload["prompt"]
    assert "=== PROFILO STUDIO ===" not in payload["prompt"]
    assert "=== IMPOSTAZIONI STUDIO ===" not in payload["prompt"]
    assert "=== PEC E CANALI EMAIL ===" not in payload["prompt"]
    assert "=== FASCICOLI ===" in payload["prompt"]
    assert "=== AGENDA ===" in payload["prompt"] or "=== SCADENZIARIO ===" in payload["prompt"]
    assert "=== IDENTITA' E VOCE DI LEX ===" in payload["prompt"]
    assert "=== STILE DI RISPOSTA ===" in payload["prompt"]
    assert "=== COMPORTAMENTO OPERATIVO ===" in payload["prompt"]
    assert "=== GESTIONE DEL CONTESTO E DEI FOLLOW-UP ===" in payload["prompt"]
    assert "presenza operativa di studio" in payload["prompt"]
    assert "studio@pec.example.it" not in payload["prompt"]
    assert "smtp.pec.aruba.it" not in payload["prompt"]
    assert "assistente consultivo e operativo di IUSENTRA" in payload["prompt"]
    assert "CONVERSAZIONE RECENTE" not in payload["prompt"]
    assert payload["focus_label"] == "procedimenti attivi"


def test_api_assistente_context_integra_fonti_ufficiali_web_live(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

    monkeypatch.setattr(
        "web.services.assistente_studio_context.build_live_official_web_context",
        lambda question, **kwargs: {
            "lines": [
                "Verifica live web: Lex ha consultato una fonte ufficiale per aggiornare il contesto.",
                "Normattiva: risorsa live raggiunta, titolo 'Testo vigente del decreto', URL https://www.normattiva.it/.",
            ],
            "sources": [
                {
                    "id": "live-web:normattiva",
                    "title": "Normattiva",
                    "citation": "Fonte ufficiale live - Normattiva",
                    "text": "Testo vigente del decreto. URL ufficiale: https://www.normattiva.it/.",
                }
            ],
            "citations": ["Fonte ufficiale live - Normattiva"],
            "source_ids": ["normattiva"],
        },
    )

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/context",
            json={
                "question": "Verifica la normativa sulla fatturazione elettronica",
                "messages": [{"role": "user", "content": "Verifica la normativa sulla fatturazione elettronica"}],
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert "=== VERIFICA LIVE FONTI UFFICIALI WEB ===" in payload["prompt"]
    assert "Normattiva: risorsa live raggiunta" in payload["prompt"]
    assert payload["web_fallback_used"] is True
    assert any(citation == "Fonte ufficiale live - Normattiva" for citation in payload["citations"])
    assert any(source["id"] == "live-web:normattiva" for source in payload["sources"])


def test_api_assistente_context_espone_profilo_richiesta_e_policy_fonti(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/context",
            json={
                "question": "Verifica la normativa vigente sul consenso privacy",
                "messages": [{"role": "user", "content": "Verifica la normativa vigente sul consenso privacy"}],
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["request_profile"]["intent"] == "normativa"
    assert payload["request_profile"]["source_mode"] == "strict"
    assert payload["source_policy_summary"]["mode_used"] == "strict"
    assert "=== POLICY FONTI E AFFIDABILITA ===" in payload["prompt"]
    assert "Profilo richiesta: verifica normativa." in payload["prompt"]
    assert all("source_policy_tier" in source for source in payload["sources"])


def test_api_assistente_context_eredita_tema_precedente_per_verifica_web(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

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

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/context",
            json={
                "messages": [
                    {"role": "user", "content": "Ultime sentenze sul civile tutti gli ambienti"},
                    {"role": "assistant", "content": "Controllo le sentenze civili piu' recenti."},
                    {"role": "user", "content": "Puoi controllare tu sul web"},
                ],
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["effective_question"] == "Ultime sentenze sul civile tutti gli ambienti"
    assert payload["web_execution_requested"] is True
    assert payload["web_fallback_used"] is True
    assert "Richiesta web presa in carico" in payload["prompt"]
    assert "Cassazione: risorsa live raggiunta" in payload["prompt"]


def test_api_assistente_attachments_parse_documenti_locali(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

    file_payload = {
        "name": "memo.txt",
        "mime_type": "text/plain",
        "content_base64": "data:text/plain;base64," + base64.b64encode(
            "Promemoria udienza e deposito memoria ex art. 183".encode("utf-8")
        ).decode("ascii"),
    }

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post("/api/assistente/attachments", json={"files": [file_payload]})

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["attachments"][0]["name"] == "memo.txt"
    assert "DOCUMENTI CARICATI DALL'UTENTE" in payload["prompt_block"]


def test_api_assistente_documento_esporta_docx(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/documento",
            json={
                "title": "Bozza memoria conclusionale",
                "question": "Preparami una bozza di memoria conclusionale",
                "answer": "# Bozza memoria conclusionale\n\n- Primo punto operativo\n- Secondo punto operativo",
                "citations": ["Tariffario forense", "Fonte ufficiale - Normattiva"],
                "context_label": "Contesto fascicolo attivo",
            },
        )

    assert response.status_code == 200
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert "attachment;" in response.headers.get("Content-Disposition", "")
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    assert "Bozza memoria conclusionale" in xml
    assert "Tariffario forense" in xml
    assert "Contesto fascicolo attivo" in xml


def test_api_assistente_context_integra_documenti_caricati(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/context",
            json={
                "question": "Quali documenti devo controllare prima del deposito?",
                "attachments": [
                    {
                        "id": "doc-1",
                        "name": "memo.txt",
                        "mime_type": "text/plain",
                        "text_excerpt": "Promemoria per controllare procura, nota di iscrizione e allegati firmati.",
                        "text_chars": 72,
                        "truncated": False,
                    }
                ],
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert "DOCUMENTI CARICATI DALL'UTENTE" in payload["prompt"]
    assert "Promemoria per controllare procura" in payload["prompt"]


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


def test_ollama_runtime_provisioner_selects_windows_installer_asset_per_l_utente(tmp_path: Path):
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
                "name": "OllamaSetup.exe",
                "browser_download_url": "https://example.test/OllamaSetup.exe",
                "size": 812000000,
                "updated_at": "2026-04-12T22:13:20Z",
            },
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
    assert asset["name"] == "OllamaSetup.exe"


def test_ollama_runtime_provisioner_selects_windows_zip_asset_per_bootstrap_tecnico(tmp_path: Path):
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
                "name": "OllamaSetup.exe",
                "browser_download_url": "https://example.test/OllamaSetup.exe",
                "size": 812000000,
                "updated_at": "2026-04-12T22:13:20Z",
            },
            {
                "name": "ollama-windows-amd64.zip",
                "browser_download_url": "https://example.test/ollama-windows-amd64.zip",
                "size": 781000000,
                "updated_at": "2026-04-12T22:13:20Z",
            },
        ],
    }

    asset = provisioner.select_download_asset(release, purpose="runtime")

    assert asset is not None
    assert asset["name"] == "ollama-windows-amd64.zip"


def test_ollama_runtime_provisioner_prefers_host_bridge_strategy_on_windows_host_container(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PCT_HOST_PLATFORM", "Windows_NT")
    monkeypatch.setenv("PCT_HOST_MACHINE", "AMD64")
    monkeypatch.setattr(OllamaRuntimeProvisioner, "_detect_execution_platform_name", lambda self: "linux")
    monkeypatch.setattr(OllamaRuntimeProvisioner, "_detect_containerized", lambda self: True)
    monkeypatch.setattr(OllamaRuntimeProvisioner, "discover_executable", lambda self: None)
    monkeypatch.setattr(
        OllamaRuntimeProvisioner,
        "fetch_latest_release",
        lambda self, **kwargs: {
            "version": "v0.20.6",
            "html_url": "https://example.test/releases/v0.20.6",
            "published_at": "2026-04-13T00:59:00Z",
            "assets": [
                {
                    "name": "OllamaSetup.exe",
                    "browser_download_url": "https://example.test/OllamaSetup.exe",
                    "size": 812000000,
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
    assert snapshot["asset_name"] == "OllamaSetup.exe"
    assert snapshot["asset_label"] == "Installer Windows consigliato"
    assert "profilo hardware" in snapshot["summary_body"]
    assert "profilo hardware" in snapshot["post_install_note"]


def test_local_ai_settings_env_override_runtime_url(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PCT_LOCAL_AI_BASE_URL", "http://ollama:11434/api")
    service = _service(tmp_path)

    settings = service._load_settings()

    assert settings.base_url == "http://ollama:11434/api"


def test_local_ai_connect_fallback_su_journal_delete_quando_wal_non_disponibile(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)

    class FakeConnection:
        def __init__(self):
            self.row_factory = None
            self.commands: list[str] = []

        def execute(self, sql: str, *args, **kwargs):
            self.commands.append(sql)
            if sql == "PRAGMA journal_mode = WAL":
                raise sqlite3.OperationalError("WAL non disponibile")
            return self

    fake = FakeConnection()
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: fake)

    conn = service._connect()

    assert conn is fake
    assert "PRAGMA journal_mode = WAL" in fake.commands
    assert "PRAGMA journal_mode = DELETE" in fake.commands


def test_get_local_ai_service_riusa_singleton_applicativo_su_richieste_multiple(tmp_path: Path):
    from lex.providers.local_ai_service import get_local_ai_service

    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

    with app.test_request_context("/"):
        first = get_local_ai_service()

    with app.test_request_context("/"):
        second = get_local_ai_service()

    assert first is second
    assert len(app.extensions.get("local_ai_services") or {}) == 1


def test_resolved_ollama_runtime_cache_evita_health_snapshot_ripetuti(tmp_path: Path, monkeypatch):
    from lex.providers.ollama_runtime import (
        clear_ollama_runtime_resolution_cache,
        resolved_ollama_api_base_url,
        resolved_ollama_chat_model,
        resolved_ollama_keep_alive,
    )
    from lex.providers.local_ai_service import get_local_ai_service

    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

    with app.app_context():
        service = get_local_ai_service()
        with service._connect() as conn:
            conn.execute(
                """
                UPDATE local_ai_runtime
                SET api_base_url = ?, updated_at = ?, status = ?
                WHERE id = 1
                """,
                ("http://host.docker.internal:11434/api", "2026-04-14T12:00:00Z", "ready"),
            )
            conn.execute("DELETE FROM local_ai_models")
            conn.execute(
                """
                INSERT INTO local_ai_models (
                    id, role, model_name, install_state, is_active, last_verified_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "chat-gemma3-1b",
                    "chat",
                    "gemma3:1b",
                    "ready",
                    1,
                    "2026-04-14T12:00:00Z",
                    "",
                ),
            )
            conn.commit()

        monkeypatch.setattr(
            service,
            "health_snapshot",
            lambda: (_ for _ in ()).throw(AssertionError("health_snapshot non deve stare nel percorso chat")),
        )
        clear_ollama_runtime_resolution_cache()
        assert resolved_ollama_api_base_url() == "http://host.docker.internal:11434/api"
        assert resolved_ollama_chat_model("mistral") == "gemma3:1b"
        assert resolved_ollama_keep_alive("7m") == "10m"
        monkeypatch.setattr(
            service,
            "_connect",
            lambda: (_ for _ in ()).throw(AssertionError("la cache chat non deve rileggere il database a ogni messaggio")),
        )
        assert resolved_ollama_api_base_url() == "http://host.docker.internal:11434/api"
        assert resolved_ollama_chat_model("mistral") == "gemma3:1b"
        assert resolved_ollama_keep_alive("7m") == "10m"


def test_assistente_chat_non_duplica_cronologia_nel_system_prompt_e_usa_keep_alive(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))

    class FakeStreamResponse:
        def iter_lines(self):
            yield json.dumps({"message": {"content": "Ciao"}, "done": False}).encode("utf-8")
            yield json.dumps({"done": True}).encode("utf-8")

    captured: dict[str, object] = {}

    def fake_post(url, json=None, stream=None, timeout=None):
        captured["url"] = url
        captured["json"] = json or {}
        captured["stream"] = stream
        captured["timeout"] = timeout
        return FakeStreamResponse()

    monkeypatch.setattr(
        "lex.runtime_dependencies.resolved_ollama_runtime",
        lambda: {
            "api_base_url": "http://host.docker.internal:11434/api",
            "base_url": "http://host.docker.internal:11434",
            "chat_model": "gemma3:1b",
            "keep_alive": "12m",
        },
    )
    monkeypatch.setattr("lex.runtime_dependencies.requests.post", fake_post)

    messages = [
        {"role": "user", "content": "Apri il fascicolo Rossi."},
        {"role": "assistant", "content": "Perfetto, lo sto leggendo."},
        {"role": "user", "content": "Qual e' il prossimo adempimento?"},
    ]

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post("/api/assistente/chat", json={"messages": messages})

    payload = captured["json"]
    system_prompt = payload["messages"][0]["content"]

    assert response.status_code == 200
    assert captured["url"] == "http://host.docker.internal:11434/api/chat"
    assert payload["model"] == "gemma3:1b"
    assert payload["keep_alive"] == "12m"
    assert "=== IDENTITA' E VOCE DI LEX ===" in system_prompt
    assert "=== STILE DI RISPOSTA ===" in system_prompt
    assert "Memoria di sessione:" not in system_prompt
    assert "CONVERSAZIONE RECENTE" not in system_prompt
    assert payload["messages"][1:] == messages


def test_api_local_ai_bootstrap_aggiorna_cache_runtime_chat(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json", enabled=True)
    app = create_app(_cfg_web(tmp_path))
    calls = {"refresh": 0}

    class FakeService:
        def bootstrap_runtime(self, force=False):
            return {"status": "ready", "force": force}

        def health_snapshot(self):
            return {"runtime": {"status": "ready"}}

    monkeypatch.setattr("web.blueprints.impostazioni.get_local_ai_service", lambda: FakeService())
    monkeypatch.setattr(
        "web.blueprints.impostazioni.refresh_live_ollama_runtime",
        lambda: calls.__setitem__("refresh", calls["refresh"] + 1) or {"chat_model": "gemma3:1b"},
    )

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post("/api/local-ai/bootstrap", json={"force": True})

    assert response.status_code == 200
    assert response.get_json()["result"]["status"] == "ready"
    assert calls["refresh"] == 1

