import json
from pathlib import Path

from web.app import create_app
from web.services.assistente_legal_reference_guard import (
    build_case_law_guard_prompt,
    build_unverified_pdf_reply,
    collect_verified_legal_references,
    has_verified_legal_reference,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {
                    "nome": "Studio Guard Test",
                    "avvocato": "Avv. Guard",
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
                    "from_name": "Studio Guard Test",
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


def test_guard_riconosce_fonti_verificate_e_prompt_di_blocco():
    verified_source = {
        "title": "Cassazione civile",
        "citation": "Fonte ufficiale live - Cassazione",
        "official_url": "https://www.cortedicassazione.it/",
        "final_url": "https://www.cortedicassazione.it/decisione.pdf",
        "downloadable_pdf": True,
        "verified_reference": True,
    }
    placeholder_source = {
        "title": "Pronuncia esemplificativa",
        "citation": "Archivio sentenze",
        "text": "Sent. n. 12345/2026",
    }

    assert has_verified_legal_reference(verified_source) is True
    assert has_verified_legal_reference(placeholder_source) is False
    assert len(collect_verified_legal_references([verified_source, placeholder_source])) == 1

    prompt = build_case_law_guard_prompt("ricerca web sentenze civili", [placeholder_source])
    assert "non hai ancora una pronuncia verificata" in prompt
    assert "Non inventare mai estremi specifici di sentenze" in prompt


def test_guard_blocca_download_pdf_su_pronuncia_non_verificata():
    reply = build_unverified_pdf_reply(
        "ultime sentenze civili la puoi scaricare in pdf",
        [],
    )

    assert "non posso scaricarne il PDF" in reply
    assert "link ufficiale" in reply


def test_assistente_context_restituisce_direct_answer_per_pdf_non_verificato(tmp_path: Path, monkeypatch):
    import lex.runtime_dependencies as assistente_runtime_module

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    monkeypatch.setattr(
        assistente_runtime_module,
        "build_lex_studio_context",
        lambda *args, **kwargs: {
            "prompt_block": "",
            "sources": [],
            "citations": [],
            "focus_label": "sentenze civili recenti",
            "focus_topic": "sentenze_civili",
            "competence_labels": [],
            "research_strategy": "auto_narrow_recent_civil_case_law",
            "effective_question": "ultime sentenze civili recenti di Cassazione la puoi scaricare in pdf",
            "web_fallback_used": False,
            "web_execution_requested": True,
            "verified_legal_references": [],
            "legal_reference_guard_active": True,
            "engine_ids": [],
            "source_ids": [],
        },
    )

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/context",
            json={
                "messages": [
                    {"role": "user", "content": "ultime sentenze civili recenti di Cassazione"},
                    {"role": "assistant", "content": "Controllo le pronunce piu' recenti."},
                    {"role": "user", "content": "la puoi scaricare in pdf"},
                ]
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["query_type"] == "direct_answer"
    assert payload["disable_exports"] is True
    assert payload["legal_reference_guard_active"] is True
    assert "non posso scaricarne il PDF" in payload["answer"]
