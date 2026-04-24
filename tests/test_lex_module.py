import json
from pathlib import Path

from lex.contracts import LexRequest
from lex.context.builder import LexContextBuilder
from lex.context.document_context import load_document_context
from lex.providers.deterministic_provider import DeterministicProvider
from lex.retrieval.orchestrator import RetrievalOrchestrator
from lex.retrieval.sources.compliance import ComplianceSource
from lex.retrieval.sources.agenda import AgendaSource
from lex.retrieval.sources.scadenziario import ScadenziarioSource
from lex.context.studio_context import build_lex_studio_context
from lex.memory.conversation_state import (
    messages_with_effective_question,
    resolve_current_and_previous_user_messages,
)
from lex.retrieval.documenti import search_document_sources
from lex.retrieval.fascicoli import search_fascicolo_sources
from pct.clienti import GestioneClienti, Indirizzo, Recapiti, TipoCliente
from pct.fascicoli import EsitoDepositoPCT, GestioneFascicoli, TipoAttivita, TipoDocumento, TipoFascicolo
from pct.fatturazione import GestioneFatturazione, StatoParcella, VoceParcella
from pct.preventivi import GestionePreventivi, TipoVoce, VocePreventivo
from pct.soggetti import GestioneSoggetti, RuoloSoggetto, TipoSoggetto
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
        "CALENDAR_SYNC_DB": str(tmp_path / "calendar_sync.json"),
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
        "REDACTION_ASSISTANT_DB": str(tmp_path / "intelligence" / "assistente_redazionale.json"),
        "PREVENTIVI_DB": str(tmp_path / "preventivi" / "preventivi.json"),
        "FATTURAZIONE_DB": str(tmp_path / "fatturazione" / "parcelle.json"),
        "LOCAL_AI_DB": str(tmp_path / "intelligence" / "local_ai.db"),
        "LOCAL_AI_POLICY": str(REPO_ROOT / "config" / "ai-policy.json"),
        "LOCAL_AI_MODELS_DIR": str(tmp_path / "intelligence" / "models"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "UFFICI_GIUDIZIARI_DB": str(tmp_path / "uffici" / "uffici_giudiziari.json"),
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
    assert set(payload["structured_context"].keys()) >= {
        "fascicolo",
        "documenti",
        "fascicolo_sezioni",
        "agenda",
        "scadenze",
        "anagrafica",
        "mode",
    }


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


def _seed_lex_fascicolo_workspace(tmp_path: Path) -> tuple[object, str]:
    from pct.agenda import TipoAppuntamento
    from pct.scadenziario import TipoTermine
    from web.helpers import get_agenda, get_scadenziario

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    gestione_fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fascicolo = gestione_fascicoli.nuovo("RG 250/2026", TipoFascicolo.CIVILE)
    fascicolo.nome_cliente = "Mario Rossi"
    fascicolo.oggetto = "Opposizione a decreto ingiuntivo"
    fascicolo.tribunale = "Tribunale di Milano"
    gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "comparsa.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-1.4\n%%EOF",
        caricato_da="admin",
        data_documento="2026-04-01",
    )
    gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "istanza-rinvio.pdf",
        TipoDocumento.ALLEGATO,
        b"%PDF-1.4\n%%EOF",
        caricato_da="admin",
        data_documento="2026-04-02",
        note="Istanza di rinvio udienza",
    )
    gestione_fascicoli.aggiungi_attivita(
        fascicolo.id,
        TipoAttivita.DEPOSITO_ATTI,
        "2026-04-03",
        "Deposito comparsa",
        descrizione="Deposito telematico comparsa di risposta",
    )
    gestione_fascicoli.aggiungi_attivita(
        fascicolo.id,
        TipoAttivita.COMUNICAZIONE_CANCELLERIA,
        "2026-04-04",
        "Comunicazione esito",
        descrizione="Comunicazione di cancelleria ricevuta via PEC",
    )
    gestione_fascicoli.aggiungi_attivita(
        fascicolo.id,
        TipoAttivita.UDIENZA,
        "2026-05-10",
        "Udienza istruttoria",
        descrizione="Comparizione parti",
    )
    fascicolo.depositi_pct.extend(
        [
            EsitoDepositoPCT(
                id="DEP-COMM-01",
                timestamp="2026-04-05T09:00:00",
                stato="ACCETTATO_CANCELLERIA",
                tipo_atto="COMUNICAZIONE_CANCELLERIA",
                pec_destinatario="tribunale@example.it",
                messaggio="Comunicazione cancelleria su esito controlli",
                note="Comunicazione cancelleria acquisita da PST",
            ),
            EsitoDepositoPCT(
                id="DEP-IST-01",
                timestamp="2026-04-06T11:30:00",
                stato="ACCETTATO_CANCELLERIA",
                tipo_atto="ISTANZA",
                pec_destinatario="tribunale@example.it",
                messaggio="Istanza di rinvio",
                note="Istanza di rinvio depositata",
            ),
        ]
    )
    gestione_fascicoli._salva()

    with app.app_context():
        get_agenda().aggiungi(
            "Udienza istruttoria",
            TipoAppuntamento.UDIENZA,
            "2026-05-10T10:00:00",
            procedimento=fascicolo.id,
            tribunale="Tribunale di Milano",
            luogo="Aula 12",
            note="Preparare fascicolo e note d'udienza",
        )
        get_scadenziario().nuova(
            titolo="Termine note autorizzate",
            tipo=TipoTermine.ALTRO,
            data_scadenza="2026-05-08",
            id_fascicolo=fascicolo.id,
            descrizione="Deposito note autorizzate",
        )

    return app, fascicolo.id


def _seed_lex_operational_runtime(tmp_path: Path) -> tuple[object, str]:
    from pct.agenda import TipoAppuntamento
    from pct.scadenziario import TipoTermine
    from web.helpers import get_agenda, get_scadenziario

    cfg = _cfg_web(tmp_path)
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(cfg)

    clienti = GestioneClienti(db_path=cfg["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501Z",
    )
    clienti.aggiorna(
        cliente.id,
        indirizzo_residenza=Indirizzo(via="Via Roma 12", comune="Milano"),
        recapiti=Recapiti(email="mario.rossi@example.it"),
    )

    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "RG 410/2026",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Milano",
        numero_rg="410",
        anno_rg=2026,
        controparte="Beta S.r.l.",
        oggetto="Atto di citazione per recupero crediti",
        data_prima_udienza="2026-06-10",
        data_notifica_citazione="2026-04-03",
    )
    fascicolo.avvocato_referente = "Avv. Lex"
    fascicoli.aggiungi_documento(
        fascicolo.id,
        "atto_citazione.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-1.4\n%%EOF",
        caricato_da="admin",
        data_documento="2026-04-02",
    )
    fascicoli._salva()

    soggetti = GestioneSoggetti(
        soggetti_path=cfg["SOGGETTI_DB"],
        parti_path=cfg["SOGGETTI_PARTI_DB"],
    )
    assistito = soggetti.crea(
        TipoSoggetto.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501Z",
        id_cliente=cliente.id,
    )
    controparte = soggetti.crea(
        TipoSoggetto.PERSONA_GIURIDICA,
        ragione_sociale="Beta S.r.l.",
        partita_iva="01234567890",
    )
    soggetti.aggiungi_parte(fascicolo.id, assistito.id, RuoloSoggetto.ASSISTITO, note="Parte attrice")
    soggetti.aggiungi_parte(fascicolo.id, controparte.id, RuoloSoggetto.CONTROPARTE, note="Controparte convenuta")

    preventivi = GestionePreventivi(cfg["PREVENTIVI_DB"])
    preventivo = preventivi.crea_preventivo(
        id_cliente=cliente.id,
        id_fascicolo=fascicolo.id,
        oggetto="Atto di citazione recupero crediti",
        voci=[VocePreventivo(descrizione="Compenso introduttivo", importo=1200.0, tipo=TipoVoce.ONORARIO)],
        creato_da="admin",
        id_pratica="atto_citazione",
        area_pratica="Civile",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
    )
    preventivi.crea_conferimento(
        id_cliente=cliente.id,
        id_preventivo=preventivo.id,
        id_fascicolo=fascicolo.id,
        oggetto="Conferimento incarico recupero crediti",
        avvocato_referente="Avv. Lex",
        creato_da="admin",
        compenso_pattuito=preventivo.totale,
        id_pratica="atto_citazione",
        area_pratica="Civile",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
    )

    fatturazione = GestioneFatturazione(cfg["FATTURAZIONE_DB"])
    parcella = fatturazione.crea(
        id_cliente=cliente.id,
        id_fascicolo=fascicolo.id,
        id_preventivo=preventivo.id,
        creato_da="admin",
        data_scadenza="2026-05-20",
        voci=[VoceParcella(descrizione="Acconto professionale", prezzo_unitario=600.0)],
        id_pratica="atto_citazione",
        area_pratica="Civile",
    )
    fatturazione.cambia_stato(parcella.id, StatoParcella.EMESSA)

    with app.app_context():
        procedimento = getattr(fascicolo, "rg_completo", "") or f"{fascicolo.numero_rg}/{fascicolo.anno_rg}"
        get_agenda().aggiungi(
            "Udienza comparizione parti",
            TipoAppuntamento.UDIENZA,
            "2026-06-10T09:30:00",
            procedimento=procedimento,
            id_cliente=cliente.id,
            tribunale="Tribunale di Milano",
            luogo="Aula 4",
            note="Preparare fascicolo e note finali",
        )
        get_scadenziario().nuova(
            titolo="Deposita prova notifica",
            tipo=TipoTermine.DEPOSITO_MEMORIA,
            data_scadenza="2026-05-18",
            id_fascicolo=fascicolo.id,
            descrizione="Produzione prova notificatoria",
        )

    return app, fascicolo.id


def test_lex_document_context_non_taglia_fascicolo_con_piu_di_otto_documenti(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    gestione_fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fascicolo = gestione_fascicoli.nuovo("RG 300/2026", TipoFascicolo.CIVILE)
    for index in range(10):
        gestione_fascicoli.aggiungi_documento(
            fascicolo.id,
            f"allegato-{index + 1:02d}.pdf",
            TipoDocumento.ALLEGATO,
            b"%PDF-1.4\n%%EOF",
            caricato_da="admin",
            data_documento=f"2026-04-{index + 1:02d}",
        )

    with app.app_context():
        rows = load_document_context(pratica_id=fascicolo.id, fascicolo_id=fascicolo.id)

    assert len(rows) == 10
    assert rows[-1]["nome"] == "allegato-10.pdf"


def test_lex_fascicolo_sections_context_censisce_tutte_le_sezioni_del_workspace(tmp_path: Path):
    app, fascicolo_id = _seed_lex_fascicolo_workspace(tmp_path)
    builder = LexContextBuilder()
    request = LexRequest(
        tenant_id="tenant-test",
        user_id="admin",
        session_id="sess-lex",
        query="fammi il quadro completo del fascicolo",
        fascicolo_id=fascicolo_id,
    )

    with app.app_context():
        context = builder.build_request_context(request, "fascicolo")

    sections = context["fascicolo_sezioni"]
    assert sections["counts"]["documenti"] == 2
    assert sections["counts"]["attivita"] == 1
    assert sections["counts"]["udienze_scadenze"] == 3
    assert sections["counts"]["comunicazioni"] == 2
    assert sections["counts"]["istanze"] == 2
    assert len(sections["documenti_fascicolo"]) == 2
    assert len(sections["attivita_processuali"]) == 1
    assert len(sections["udienze_scadenze"]) == 3
    assert len(sections["comunicazioni_cancelleria"]) == 2
    assert len(sections["istanze"]) == 2


def test_lex_retrieval_fascicolo_esporta_sommari_sezioni_e_tutti_i_documenti(tmp_path: Path):
    app, fascicolo_id = _seed_lex_fascicolo_workspace(tmp_path)
    builder = LexContextBuilder()
    request = LexRequest(
        tenant_id="tenant-test",
        user_id="admin",
        session_id="sess-lex",
        query="mostrami comunicazioni di cancelleria e istanze del fascicolo",
        fascicolo_id=fascicolo_id,
    )

    with app.app_context():
        context = builder.build_request_context(request, "fascicolo")
        document_evidence = search_document_sources(
            fascicolo_id,
            "",
            context,
        )
        fascicolo_sources = search_fascicolo_sources(
            fascicolo_id,
            "comunicazioni di cancelleria e istanze",
            context,
        )

    section_titles = {row.title for row in fascicolo_sources}
    assert len([row for row in document_evidence if row.source_type == "documento"]) == 2
    assert any(row.source_type == "documento_manifesto" for row in document_evidence)
    assert "Comunicazioni di cancelleria" in section_titles
    assert "Istanze" in section_titles


def test_lex_retrieval_fascicolo_non_taglia_sezioni_estese():
    context = {
        "fascicolo_sezioni": {
            "counts": {
                "documenti": 12,
                "attivita": 7,
                "udienze_scadenze": 6,
                "comunicazioni": 5,
                "istanze": 4,
            },
            "documenti_fascicolo": [
                {"id": f"DOC-{idx}", "nome": f"Documento {idx}", "tipo": "ALLEGATO", "data_documento": f"2026-04-{idx:02d}"}
                for idx in range(1, 13)
            ],
            "attivita_processuali": [
                {"id": f"ATT-{idx}", "titolo": f"Attivita processuale {idx}", "data": f"2026-03-{idx:02d}"}
                for idx in range(1, 8)
            ],
            "udienze_scadenze": [
                {"id": f"UD-{idx}", "titolo": f"Udienza o scadenza {idx}", "data_ora": f"2026-05-{idx:02d}T10:00:00"}
                for idx in range(1, 7)
            ],
            "comunicazioni_cancelleria": [
                {"id": f"COM-{idx}", "titolo": f"Comunicazione cancelleria {idx}", "data": f"2026-02-{idx:02d}"}
                for idx in range(1, 6)
            ],
            "istanze": [
                {"id": f"IST-{idx}", "titolo": f"Istanza {idx}", "data": f"2026-01-{idx:02d}"}
                for idx in range(1, 5)
            ],
        }
    }

    sources = search_fascicolo_sources("FASC-ESTESO", "fammi il quadro completo del fascicolo", context)

    document_items = [row for row in sources if row.source_type == "fascicolo_documenti_fascicolo"]
    assert len(document_items) == 12
    assert any(row.title == "Documento 12" for row in document_items)
    summary = next(row for row in sources if row.source_type == "sezione_fascicolo" and row.metadata["section"] == "documenti_fascicolo")
    assert "Documento 12" in summary.excerpt


def test_lex_sources_agenda_scadenziario_non_tagliano_a_tre():
    agenda_rows = [{"titolo": f"Udienza {idx}", "descrizione": "Discussione"} for idx in range(1, 7)]
    scadenze_rows = [{"titolo": f"Scadenza {idx}", "descrizione": "Deposito"} for idx in range(1, 7)]

    agenda_sources = AgendaSource().search([], None, {"agenda": agenda_rows})
    scadenze_sources = ScadenziarioSource().search([], None, {"scadenziario": scadenze_rows})

    assert len(agenda_sources) == 6
    assert len(scadenze_sources) == 6
    assert agenda_sources[-1].title == "Udienza 6"
    assert scadenze_sources[-1].title == "Scadenza 6"


def test_lex_orchestrator_usa_budget_esteso_per_fascicoli():
    orchestrator = RetrievalOrchestrator()

    assert orchestrator._selection_limit("fascicolo") == 48
    assert orchestrator._selection_limit("documento") == 48
    assert orchestrator._selection_limit("general") == 12


def test_lex_studio_context_espone_dashboard_motori_legali(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.app_context():
        payload = build_lex_studio_context("normattiva aggiornata", mode="chat")

    assert any(
        source.get("id") == "legal-intelligence:dashboard-headline"
        for source in payload["sources"]
    )
    assert payload["legal_dashboard_headline"]["motori_attivi"] >= 1
    assert payload["legal_dashboard_headline"]["riferimenti_normativi"] >= 8


def test_lex_anagrafica_context_risolve_cliente_e_soggetti_del_fascicolo(tmp_path: Path):
    app, fascicolo_id = _seed_lex_operational_runtime(tmp_path)
    request = LexRequest(
        tenant_id="tenant-test",
        user_id="admin",
        session_id="sess-anagrafica",
        query="chi sono cliente e parti del fascicolo",
        fascicolo_id=fascicolo_id,
    )

    with app.app_context():
        context = LexContextBuilder().build_request_context(request, "fascicolo")

    assert context["anagrafica"]["clienti"]
    assert context["anagrafica"]["clienti"][0]["cf"] == "RSSMRA80A01H501Z"
    assert context["anagrafica"]["soggetti"]
    assert {row["ruolo"] for row in context["anagrafica"]["soggetti"]} >= {"ASSISTITO", "CONTROPARTE"}


def test_lex_context_builder_aggrega_workspace_conformita_ed_economico(tmp_path: Path):
    app, fascicolo_id = _seed_lex_operational_runtime(tmp_path)
    request = LexRequest(
        tenant_id="tenant-test",
        user_id="admin",
        session_id="sess-operativo",
        query="fammi il quadro operativo completo del fascicolo con economico e conformita",
        fascicolo_id=fascicolo_id,
    )

    with app.app_context():
        context = LexContextBuilder().build_request_context(request, "cabina")

    assert context["agenda"]
    assert context["studio_operativo"]["domains"]["preventivi"]["total"] == 1
    assert context["economico"]["scope"] == "fascicolo"
    assert context["economico"]["summary"]["parcelle_count"] == 1
    assert context["fascicolo_intelligence"]["next_actions"]
    assert context["conformita_fascicolo"]["available"] is True
    assert context["conformita_fascicolo"]["missing_documents"]


def test_lex_compliance_source_e_provider_usano_dati_reali_del_fascicolo(tmp_path: Path):
    app, fascicolo_id = _seed_lex_operational_runtime(tmp_path)
    request = LexRequest(
        tenant_id="tenant-test",
        user_id="admin",
        session_id="sess-compliance",
        query="il fascicolo e conforme per il deposito?",
        fascicolo_id=fascicolo_id,
    )

    with app.app_context():
        context = LexContextBuilder().build_request_context(request, "compliance")
        evidence_items = ComplianceSource().search([request.query], request, context)
        draft = DeterministicProvider().generate(
            request=request,
            context=context,
            evidence={"items": evidence_items},
            workflow="compliance",
        )

    assert evidence_items
    assert evidence_items[0].metadata["authority"] == "responsabile_conformita"
    assert "Responsabile di conformita'" in draft.text
    assert "Pre-deposito" in draft.text
    assert "procura" in draft.text.lower() or "notifica" in draft.text.lower()
