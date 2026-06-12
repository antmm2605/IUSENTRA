import base64
import io
import json
import sqlite3
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from lex.prompts.prompt_builder import build_assistente_prompt
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.local_ai import LocalAIService, _strip_html
from pct.local_ai_runtime import OllamaRuntimeProvisioner
from pct.runtime_resilience import CircuitBreakerOpenError, clear_runtime_circuit_breakers
from web.app import create_app
from web.services.storage_runtime import get_request_studio_db

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_strip_html_rimuove_script_e_style_con_tag_di_chiusura_spaziato():
    raw = "<p>Testo utile</p><script>alert('x')</script\t\n bar><style>.x{}</style\t\n bar>"

    cleaned = _strip_html(raw)

    assert "Testo utile" in cleaned
    assert "alert" not in cleaned
    assert ".x" not in cleaned


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


def test_local_ai_embedding_provider_gemini_usa_client_autorizzato(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    document_path = tmp_path / "atto-gemini.txt"
    document_path.write_text(
        "TRIBUNALE DI PALERMO\n\nIN DIRITTO\n\nRicorso con prova documentale e allegati.",
        encoding="utf-8",
    )
    indexed = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-GEMINI",
        practice_id="P-GEMINI",
        file_path=str(document_path),
        title="Ricorso con allegati",
    )
    assert indexed["status"] == "indexed"

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [{"values": [0.1, 0.2, 0.3]}]}

    captured: dict[str, object] = {}

    def fake_post(url, *, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("LEX_EXTERNAL_ALLOWED", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("IUSENTRA_GEMINI_EMBEDDING_DIMENSIONS", "768")
    monkeypatch.setattr("pct.local_ai.requests.post", fake_post)

    embedded = service.embed_pending_chunks(limit=20)

    assert embedded["status"] == "ready"
    assert embedded["embedded"] >= 1
    assert embedded["embedding_provider"] == "gemini"
    assert embedded["embedding_model"] == "gemini-embedding-001"
    assert embedded["vector_dimensions"] == 3
    assert "gemini-embedding-001:batchEmbedContents" in str(captured["url"])
    assert captured["json"]["requests"][0]["outputDimensionality"] == 768
    assert (captured["headers"] or {}).get("x-goog-api-key") == "test-key"

    with service._connect() as conn:
        row = conn.execute(
            "SELECT embedding_provider, embedding_model, embedding_dimensions FROM rag_chunks WHERE document_id = ?",
            (indexed["document_id"],),
        ).fetchone()
    assert row["embedding_provider"] == "gemini"
    assert row["embedding_model"] == "gemini-embedding-001"
    assert row["embedding_dimensions"] == 3


def test_local_ai_embedding_provider_gemini_bloccato_senza_autorizzazione(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    document_path = tmp_path / "atto-gemini-bloccato.txt"
    document_path.write_text("TRIBUNALE\nDocumento da indicizzare.", encoding="utf-8")
    service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-GEMINI-BLOCK",
        practice_id="P-GEMINI",
        file_path=str(document_path),
        title="Documento",
    )
    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER", "gemini")
    monkeypatch.delenv("LEX_EXTERNAL_ALLOWED", raising=False)
    monkeypatch.delenv("IUSENTRA_EXTERNAL_EMBEDDINGS_ALLOWED", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    embedded = service.embed_pending_chunks(limit=20)

    assert embedded["status"] == "error"
    assert embedded["embedding_provider"] == "gemini"
    assert "provider esterni" in embedded["error"]


def test_local_ai_embed_all_pending_chunks_elabora_tutto_il_fascicolo(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    for index in range(3):
        document_path = tmp_path / f"atto-{index + 1}.txt"
        document_path.write_text(
            f"TRIBUNALE DI PALERMO\nDocumento {index + 1} del fascicolo esteso.",
            encoding="utf-8",
        )
        indexed = service.index_file(
            source_type="fascicolo_documento",
            source_id=f"DOC-{index + 1}",
            practice_id="FASC-1",
            file_path=str(document_path),
            title=f"Documento {index + 1}",
        )
        assert indexed["status"] == "indexed"

    class DummyClient:
        def embed_texts(self, model_name, inputs):
            return {"embeddings": [[1.0, 0.0] for _ in inputs], "load_duration": 1, "prompt_eval_count": len(inputs)}

    monkeypatch.setattr(service, "bootstrap_runtime", lambda force=False: {"status": "ready", "embed_model": "embeddinggemma:300m"})
    monkeypatch.setattr(service, "_ollama_client", lambda settings=None: DummyClient())
    monkeypatch.setattr(service, "_active_model", lambda role: "embeddinggemma:300m" if role == "embed" else "gemma3:1b")

    embedded = service.embed_all_pending_chunks(practice_id="FASC-1", batch_size=1, max_batches=10)

    assert embedded["embedded_total"] >= 3
    assert embedded["batches"] >= 3
    assert embedded["pending_remaining"] == 0


def test_prepare_fascicolo_query_include_inventari_completi_e_top_k_dinamico(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    captured: dict[str, int] = {}

    monkeypatch.setattr(service, "index_fascicolo_documents", lambda *args, **kwargs: {"indexed": 0, "skipped": 12, "unsupported": 0, "errors": []})
    monkeypatch.setattr(service, "embed_all_pending_chunks", lambda *args, **kwargs: {"status": "ready", "embedded_total": 0, "pending_remaining": 0})

    def fake_hybrid_search(query, *, practice_id=None, document_id=None, top_k=8):
        captured["top_k"] = top_k
        return []

    monkeypatch.setattr(service, "hybrid_search", fake_hybrid_search)
    docs = [
        SimpleNamespace(
            id=f"DOC-{index}",
            nome=f"Documento {index}.pdf",
            titolo="",
            tipo=SimpleNamespace(value="ALLEGATO"),
            data_documento=f"2026-04-{index:02d}",
            data_caricamento="",
            id_deposito_pct=f"DEP-{index}",
        )
        for index in range(1, 13)
    ]
    fascicolo = SimpleNamespace(
        id="FASC-2",
        titolo="Fascicolo esteso",
        oggetto="Lettura completa del fascicolo",
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        controparte="Controparte",
        stato=SimpleNamespace(value="APERTO"),
        tipo=SimpleNamespace(value="CIVILE"),
        documenti=docs,
    )

    prepared = service.prepare_fascicolo_query(
        fascicolo=fascicolo,
        documents_dir=str(tmp_path / "docs"),
        question="Leggi tutto il fascicolo",
        apps=[SimpleNamespace(titolo="Udienza istruttoria", data_ora="2026-05-10T10:00:00", luogo="Aula 1")],
        scadenze=[SimpleNamespace(titolo="Termine note", data_scadenza="2026-05-08", stato="APERTO")],
        workspace={
            "counts": {"documenti": 12, "attivita": 2, "udienze_scadenze": 2, "comunicazioni": 1, "istanze": 1},
            "attivita_processuali": [SimpleNamespace(titolo="Deposito comparsa", data="2026-04-01")],
            "comunicazioni_depositi": [SimpleNamespace(tipo_atto="Comunicazione cancelleria", timestamp="2026-04-02")],
            "istanze_documenti": [SimpleNamespace(nome="Istanza rinvio.pdf", data_documento="2026-04-03")],
        },
        intelligenza={},
    )

    assert captured["top_k"] == 48
    assert "Inventario documenti fascicolo (12):" in prepared["prompt"]
    assert "Documento 12.pdf" in prepared["prompt"]
    assert "Inventario sezioni del fascicolo:" in prepared["prompt"]
    assert "Comunicazioni cancelleria da depositi (1):" in prepared["prompt"]


def test_prepare_fascicolo_query_impone_analisi_professionale_e_fonti_compatte(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    monkeypatch.setattr(service, "index_fascicolo_documents", lambda *args, **kwargs: {"indexed": 0, "skipped": 3, "unsupported": 0, "errors": []})
    monkeypatch.setattr(service, "embed_all_pending_chunks", lambda *args, **kwargs: {"status": "ready", "embedded_total": 0, "pending_remaining": 0})

    def fake_hybrid_search(query, *, practice_id=None, document_id=None, top_k=8):
        return [
            {
                "id": f"chunk-{index}",
                "document_id": "DOC-CIT",
                "title": "Citazione_28139218.pdf",
                "section_type": "corpo",
                "page_from": 1,
                "page_to": 16,
                "text": "Domanda di risoluzione contrattuale e rilascio dell'immobile con richiesta danni.",
                "citation": f"Citazione_28139218.pdf, pp. 1-16 · corpo · chunk chunk-{index}",
            }
            for index in range(1, 8)
        ] + [
            {
                "id": "sentenza-1",
                "document_id": "DOC-SENT",
                "title": "SentenzaDefinitiva_33581101.pdf",
                "section_type": "dispositivo",
                "page_from": 7,
                "page_to": 7,
                "text": "Il dispositivo definisce l'esito della controversia.",
                "citation": "SentenzaDefinitiva_33581101.pdf, p. 7 · dispositivo · chunk sentenza",
            }
        ]

    monkeypatch.setattr(service, "hybrid_search", fake_hybrid_search)
    fascicolo = SimpleNamespace(
        id="FASC-PRO",
        titolo="Montagnese / Stillitano",
        oggetto="Risoluzione preliminare e restituzione immobile",
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        controparte="Stillitano Antonella",
        stato=SimpleNamespace(value="APERTO"),
        tipo=SimpleNamespace(value="CIVILE"),
        documenti=[
            SimpleNamespace(id="DOC-CIT", nome="Citazione_28139218.pdf", titolo="", tipo=SimpleNamespace(value="CITAZIONE"), data_documento="05/09/2024", data_caricamento="", id_deposito_pct="DEP-1"),
            SimpleNamespace(id="DOC-SENT", nome="SentenzaDefinitiva_33581101.pdf", titolo="", tipo=SimpleNamespace(value="SENTENZA"), data_documento="08/01/2026", data_caricamento="", id_deposito_pct="DEP-2"),
        ],
    )

    prepared = service.prepare_fascicolo_query(
        fascicolo=fascicolo,
        documents_dir=str(tmp_path / "docs"),
        question="Analizza il fascicolo e dimmi cosa dobbiamo fare",
        apps=[],
        scadenze=[],
        workspace={"counts": {"documenti": 2, "attivita": 1}},
        intelligenza={},
    )

    prompt = prepared["prompt"]
    assert "Schema obbligatorio per l'analisi del fascicolo:" in prompt
    assert "1. Quadro del fascicolo" in prompt
    assert "Fatti provati dagli atti" in prompt
    assert "Non aprire con frasi meta come 'Ok, ecco'" in prompt
    assert "non emerge dagli estratti disponibili" in prompt
    assert "Estratti RAG selezionati: 8 chunk da 2 documenti." in prompt
    assert prepared["citations"] == [
        "Citazione_28139218.pdf, pp. 1-16 · corpo · chunk chunk-1",
        "SentenzaDefinitiva_33581101.pdf, p. 7 · dispositivo · chunk sentenza",
    ]


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


def test_local_ai_ask_fascicolo_rimuove_meta_risposta_generica(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)

    class DummyClient:
        def generate(self, model_name, prompt, keep_alive="10m"):
            return {
                "response": (
                    "Ok, ecco una revisione della struttura e del contenuto della risposta.\n\n"
                    "**1. Quadro del fascicolo**\n"
                    "Da Citazione_28139218.pdf risulta una domanda di risoluzione e rilascio.\n\n"
                    "---\n\n"
                    "**Modifiche Principali e Ragionamenti:**\n"
                    "Ho migliorato la struttura.\n\n"
                    "Spero che questa revisione sia utile."
                ),
                "load_duration": 1,
                "prompt_eval_count": 4,
                "eval_count": 12,
            }

    monkeypatch.setattr(service, "bootstrap_runtime", lambda force=False: {"status": "ready", "chat_model": "gemma3:1b"})
    monkeypatch.setattr(service, "index_fascicolo_documents", lambda *args, **kwargs: {"indexed": 0, "skipped": 0, "unsupported": 0, "errors": []})
    monkeypatch.setattr(service, "embed_all_pending_chunks", lambda *args, **kwargs: {"status": "ready", "embedded_total": 0, "pending_remaining": 0})
    monkeypatch.setattr(service, "hybrid_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(service, "_ollama_client", lambda settings=None: DummyClient())

    fascicolo = SimpleNamespace(
        id="F1",
        titolo="Fascicolo test",
        oggetto="Risoluzione contratto",
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        controparte="Stillitano",
        stato=SimpleNamespace(value="APERTO"),
        tipo=SimpleNamespace(value="CIVILE"),
        documenti=[],
    )

    result = service.ask_fascicolo(
        fascicolo=fascicolo,
        documents_dir=str(tmp_path / "docs"),
        question="Analizza il fascicolo",
        apps=[],
        scadenze=[],
        workspace={},
        intelligenza={},
    )

    assert result["ok"] is True
    assert result["answer"].startswith("**1. Quadro del fascicolo**")
    assert "Ok, ecco" not in result["answer"]
    assert "Modifiche Principali" not in result["answer"]
    assert "Spero che" not in result["answer"]


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


def test_api_assistente_context_prepara_prompt_per_companion_locale(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "0")
    monkeypatch.setenv("LEX_RAW_CHAT_ENABLED", "1")
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
                "allow_unbounded_generation": True,
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
            b"Promemoria udienza e deposito memoria ex art. 183"
        ).decode("ascii"),
    }

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post("/api/assistente/attachments", json={"files": [file_payload]})

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["attachments"][0]["name"] == "memo.txt"
    assert "Promemoria udienza" in payload["attachments"][0]["text_excerpt"]
    assert payload["prompt_block"] == ""
    assert payload["evidence_mode"] == "attachment_evidence"


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


def test_api_assistente_context_integra_documenti_caricati(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "1")
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
    assert payload["query_type"] == "workflow_answer"
    assert "DOCUMENTI CARICATI DALL'UTENTE" not in payload["prompt"]
    assert any("Allegato caricato: memo.txt" in citation for citation in payload["citations"])
    assert payload["evidence_summary"]["evidence_count"] >= 1


def test_impostazioni_template_contains_ai_locale_tab():
    html = (REPO_ROOT / "web" / "templates" / "impostazioni" / "index.html").read_text(encoding="utf-8")

    assert "AI Locale" in html
    assert "Prepara il motore locale" in html
    assert "runLocalAiBootstrap" in html
    assert "Indirizzo del motore locale" in html
    assert "Servizio locale sul dispositivo cliente" in html
    assert "127.0.0.1:27272" in html
    assert "ai-runtime-summary" in html
    assert "http://host.docker.internal:11434/api" in html
    assert "/api/version" in html
    assert "openLocalAiVersionCheck" in html


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


def test_local_ai_monitoring_snapshot_usa_runtime_locale_live_se_db_stale(tmp_path: Path, monkeypatch):
    clear_runtime_circuit_breakers()
    service = _service(tmp_path)

    with service._connect() as conn:
        conn.execute(
            """
            UPDATE local_ai_runtime
            SET status = ?, api_base_url = ?, last_error = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                "missing",
                "http://127.0.0.1:11434/api",
                "Ollama non raggiungibile",
                "2026-04-13T12:43:59",
            ),
        )
        conn.commit()

    class DummyClient:
        pass

    observed: dict[str, float] = {}

    def _resolve_live_runtime(settings, *, version_timeout=5.0, use_circuit_breaker=True):
        observed["timeout"] = version_timeout
        observed["use_circuit_breaker"] = use_circuit_breaker
        return DummyClient(), "0.20.5", "http://host.docker.internal:11434/api"

    monkeypatch.setattr(service, "_resolve_live_runtime", _resolve_live_runtime)

    snapshot = service.monitoring_snapshot()

    assert observed["timeout"] == 1.0
    assert observed["use_circuit_breaker"] is False
    assert snapshot["runtime_online"] is True
    assert snapshot["runtime"]["status"] == "ready"
    assert snapshot["runtime"]["api_base_url"] == "http://host.docker.internal:11434/api"
    assert snapshot["runtime"]["api_base_url_live"] == "http://host.docker.internal:11434/api"
    assert snapshot["runtime"]["runtime_version_live"] == "0.20.5"
    assert snapshot["runtime"]["stored_status"] == "missing"
    assert snapshot["runtime"]["stored_api_base_url"] == "http://127.0.0.1:11434/api"
    assert snapshot["runtime"]["last_error"] == ""
    assert snapshot["settings"]["base_url"] == "http://127.0.0.1:11434/api"
    assert "host.docker.internal:11434" in snapshot["circuit_breaker"]["name"]


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
    from lex.providers.local_ai_service import get_local_ai_service
    from lex.providers.ollama_runtime import (
        clear_ollama_runtime_resolution_cache,
        resolved_ollama_api_base_url,
        resolved_ollama_chat_model,
        resolved_ollama_keep_alive,
    )

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


def test_resolved_ollama_runtime_ignora_runtime_db_non_ready(tmp_path: Path, monkeypatch):
    from lex.providers.local_ai_service import get_local_ai_service
    from lex.providers.ollama_runtime import (
        clear_ollama_runtime_resolution_cache,
        resolved_ollama_api_base_url,
        resolved_ollama_chat_model,
    )

    monkeypatch.setenv("PCT_LOCAL_AI_BASE_URL", "http://ollama:11434/api")
    monkeypatch.setenv("PCT_LOCAL_AI_CHAT_MODEL", "gemma3:1b")
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
                ("http://127.0.0.1:11434/api", "2026-05-05T12:00:00Z", "missing"),
            )
            conn.commit()

        clear_ollama_runtime_resolution_cache()

        assert resolved_ollama_api_base_url() == "http://ollama:11434/api"
        assert resolved_ollama_chat_model("mistral") == "gemma3:1b"


def test_ollama_http_client_apre_circuit_breaker_dopo_errori_ripetuti(monkeypatch):
    from pct.local_ai import OllamaHttpClient

    clear_runtime_circuit_breakers()
    monkeypatch.setenv("PCT_OLLAMA_CIRCUIT_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("PCT_OLLAMA_CIRCUIT_TIMEOUT", "120")

    osservato = {"chiamate": 0}

    def _fake_request(*args, **kwargs):
        osservato["chiamate"] += 1
        raise RuntimeError("Runtime Ollama non raggiungibile")

    monkeypatch.setattr("pct.local_ai.requests.request", _fake_request)

    client = OllamaHttpClient("http://127.0.0.1:11434/api", timeout=5)
    with pytest.raises(RuntimeError):
        client.list_models()
    with pytest.raises(RuntimeError):
        client.list_models()
    with pytest.raises(CircuitBreakerOpenError):
        client.list_models()

    assert osservato["chiamate"] == 2


def test_assistente_chat_non_duplica_cronologia_nel_system_prompt_e_usa_keep_alive(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "0")
    monkeypatch.setenv("LEX_RAW_CHAT_ENABLED", "1")
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
        response = client.post(
            "/api/assistente/chat",
            json={"messages": messages, "allow_unbounded_generation": True},
        )

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


def test_local_ai_index_file_incrementale_non_rilegge_file_invariati(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    document_path = tmp_path / "memoria.txt"
    document_path.write_text(
        "TRIBUNALE DI MILANO\n\nMemoria difensiva con eccezioni preliminari.",
        encoding="utf-8",
    )

    first = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-INCR",
        practice_id="P1",
        file_path=str(document_path),
        title="Memoria difensiva",
    )
    assert first["status"] == "indexed"

    read_calls = {"count": 0}
    original_read = service._read_document_file

    def counting_read(path):
        read_calls["count"] += 1
        return original_read(path)

    monkeypatch.setattr(service, "_read_document_file", counting_read)

    second = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-INCR",
        practice_id="P1",
        file_path=str(document_path),
        title="Memoria difensiva",
    )
    assert second["status"] == "skipped"
    assert second["document_id"] == first["document_id"]
    assert read_calls["count"] == 0, "file invariato: non deve essere riletto in RAM"

    document_path.write_text(
        "TRIBUNALE DI MILANO\n\nMemoria difensiva integrata con nuove difese e documenti.",
        encoding="utf-8",
    )
    third = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-INCR",
        practice_id="P1",
        file_path=str(document_path),
        title="Memoria difensiva",
    )
    assert third["status"] == "indexed", "file modificato: deve essere re-indicizzato"
    assert read_calls["count"] >= 1

    with service._connect() as conn:
        fts_rows = conn.execute(
            "SELECT text FROM rag_chunks_fts WHERE document_id = ?",
            (first["document_id"],),
        ).fetchall()
        chunk_total = int(
            conn.execute(
                "SELECT COUNT(*) AS totale FROM rag_chunks WHERE document_id = ?",
                (first["document_id"],),
            ).fetchone()["totale"]
        )
    joined = " ".join(str(row["text"]) for row in fts_rows)
    assert fts_rows and len(fts_rows) == chunk_total, "FTS allineato ai chunk dopo la re-indicizzazione"
    assert "integrata" in joined, "il testo nuovo deve essere ricercabile"
    assert "eccezioni preliminari" not in joined, "il testo vecchio non deve restare nell'indice"

    forced = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-INCR",
        practice_id="P1",
        file_path=str(document_path),
        title="Memoria difensiva",
        force=True,
    )
    assert forced["status"] == "indexed", "force=True deve bypassare il fast-path"


def test_local_ai_index_file_migra_righe_legacy_al_fast_path(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    document_path = tmp_path / "ricorso.txt"
    document_path.write_text(
        "TRIBUNALE DI ROMA\n\nRicorso per decreto ingiuntivo con allegati contabili.",
        encoding="utf-8",
    )
    first = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-LEGACY",
        practice_id="P1",
        file_path=str(document_path),
        title="Ricorso",
    )
    assert first["status"] == "indexed"
    with service._connect() as conn:
        conn.execute(
            "UPDATE rag_documents SET source_file_size = NULL, source_file_mtime_ns = NULL WHERE id = ?",
            (first["document_id"],),
        )
        conn.commit()

    read_calls = {"count": 0}
    original_read = service._read_document_file

    def counting_read(path):
        read_calls["count"] += 1
        return original_read(path)

    monkeypatch.setattr(service, "_read_document_file", counting_read)

    second = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-LEGACY",
        practice_id="P1",
        file_path=str(document_path),
        title="Ricorso",
    )
    assert second["status"] == "skipped"
    assert read_calls["count"] == 1, "riga legacy: una sola rilettura per riallineare l'impronta"

    third = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-LEGACY",
        practice_id="P1",
        file_path=str(document_path),
        title="Ricorso",
    )
    assert third["status"] == "skipped"
    assert read_calls["count"] == 1, "impronta riallineata: dal secondo giro nessuna rilettura"
