import json
from pathlib import Path

from lex.context.builder import LexContextBuilder
from lex.context.document_context import load_document_context
from lex.memory.conversation_state import (
    messages_with_effective_question,
    resolve_current_and_previous_user_messages,
)
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from web.app import create_app


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {
                    "nome": "Studio Lex Test",
                    "avvocato": "Avv. Lex",
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
                    "from_name": "Studio Lex Test",
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
        "MULTI_TENANT": False,
        "STORAGE_MODE_DEFAULT": "json",
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


def test_lex_blueprint_keeps_assistente_endpoints(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    rules = {rule.rule: rule.endpoint for rule in app.url_map.iter_rules()}

    assert "/api/assistente/context" in rules
    assert rules["/api/assistente/context"] == "assistente.assistente_context"
    assert "/api/assistente/chat" in rules
    assert rules["/api/assistente/chat"] == "assistente.assistente_chat"


def test_lex_memory_rewrites_last_user_message_only_when_needed():
    current, previous, history = resolve_current_and_previous_user_messages(
        explicit_question="",
        messages=[
            {"role": "user", "content": "ultime sentenze civili recenti di Cassazione"},
            {"role": "assistant", "content": "Controllo le pronunce piu' recenti."},
            {"role": "user", "content": "la puoi scaricare in pdf"},
        ],
    )

    rewritten = messages_with_effective_question(
        history + [{"role": "user", "content": current}],
        effective_question="ultime sentenze civili recenti di Cassazione la puoi scaricare in pdf",
        original_question=current,
    )

    assert current == "la puoi scaricare in pdf"
    assert previous == "ultime sentenze civili recenti di Cassazione"
    assert rewritten[-1]["content"] == "ultime sentenze civili recenti di Cassazione la puoi scaricare in pdf"


def test_lex_context_builder_adds_structured_sections():
    builder = LexContextBuilder()

    payload = builder.build(
        question="udienze di oggi",
        mode="general",
        pratica_id="",
        fascicolo_id="",
        history_messages=[],
        routing=type("Routing", (), {"is_daily_overview": False})(),
        build_studio_context=lambda *args, **kwargs: {"prompt_block": "", "sources": []},
        build_today_summary=lambda **kwargs: {"prompt_block": "", "sources": []},
    )

    assert "structured_context" in payload
    assert set(payload["structured_context"].keys()) >= {"fascicolo", "documenti", "agenda", "scadenze", "anagrafica", "mode"}


def test_lex_document_context_marca_p7m_detached_come_ai_readable_se_esiste_originale(tmp_path: Path):
    from asn1crypto import algos, cms

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    gestione_fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fascicolo = gestione_fascicoli.nuovo("RG 188/2026", TipoFascicolo.CIVILE)
    pdf_bytes = b"%PDF-1.4\n% lex\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    documento = gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "comparsa.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        pdf_bytes,
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
    gestione_fascicoli.sostituisci_documento(
        fascicolo.id,
        documento.id,
        nome_file="comparsa.pdf.p7m",
        contenuto=cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump(),
        caricato_da="admin",
    )
    gestione_fascicoli.segna_firmato(fascicolo.id, documento.id)

    with app.app_context():
        rows = load_document_context(pratica_id=fascicolo.id, fascicolo_id=fascicolo.id)

    assert rows
    assert rows[0]["signed_status"]["detached_signature"] is True
    assert rows[0]["ai_readable"] is True
