from types import SimpleNamespace
import sqlite3
from pathlib import Path

from pct.document_intelligence import (
    DocumentAIPageText,
    DocumentAIRecord,
    DocumentAIText,
    DocumentAIVersion,
    DocumentAIRepository,
)
from pct.document_intelligence.models import utc_now
from pct.document_intelligence.catalog_pipeline import FascicoloDocumentCatalogPipeline
from pct.document_intelligence.catalog_resolver import (
    FAMILY_PROFILE_BY_CONTEXT,
    PROFILE_SOURCES,
    REGISTRY_VERSION,
    RESOLVER_VERSION,
    assert_full_family_matrix,
    profile_source_rows,
)
from pct.document_intelligence.sources import DocumentAISource
from pct.template_atti_catalogo import build_builtin_templates


def _ready_source(
    repo: DocumentAIRepository,
    *,
    tenant_id: str,
    fascicolo_id: str,
    document_id: str,
    filename: str,
    sha256: str,
    text: str = "RICORSO introduttivo con conclusioni e procura alle liti.",
    tipo_documento: str = "RICORSO",
):
    now = utc_now()
    document_ai_id = f"docai-{document_id.casefold()}"
    version_id = f"version-{document_id.casefold()}"
    record = DocumentAIRecord(
        id=document_ai_id, tenant_id=tenant_id, fascicolo_id=fascicolo_id,
        original_filename=filename, safe_filename=filename, file_type="pdf", mime_type="application/pdf",
        size_bytes=128, sha256=sha256, status="ready", current_version_id=version_id, page_count=1,
        created_by="test", created_at=now, updated_at=now,
    )
    repo.create_document(record)
    repo.create_version(DocumentAIVersion(
        id=version_id, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id=record.id,
        version_number=1, source="upload", storage_path="tenant/fascicolo/documento.pdf",
        extracted_text_path=None, pdf_preview_path=None, sha256=sha256, created_by="test", created_at=now,
    ))
    repo.save_extracted_text(DocumentAIText(
        document_id=record.id, version_id=version_id, tenant_id=tenant_id, fascicolo_id=fascicolo_id,
        text=text,
        pages=[DocumentAIPageText(page_number=1, text=text)],
        extraction_engine="test", created_at=now,
    ))
    return DocumentAISource(
        tenant_id=tenant_id, fascicolo_id=fascicolo_id, source_id=document_id,
        source_type="documenti_fascicolo", filename=filename, safe_filename=filename,
        file_type="pdf", mime_type="application/pdf", size_bytes=128, sha256=sha256,
        updated_at=now, metadata={"documento_id": document_id, "tipo_documento": tipo_documento},
        content_bytes=b"%PDF-test",
    )


def test_resolver_copre_tutte_le_47_famiglie_e_le_triadi():
    templates = build_builtin_templates()

    assert len(templates) == 708
    assert len(FAMILY_PROFILE_BY_CONTEXT) == 47
    assert assert_full_family_matrix(templates) == []
    assert len(PROFILE_SOURCES) == 25
    assert all(len(sources) >= 3 for sources in PROFILE_SOURCES.values())


def test_snapshot_fonti_immutato_non_scrive_di_nuovo(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    rule_set_id = repo.ensure_catalog_rule_set(
        tenant_id=tenant_id,
        resolver_version=RESOLVER_VERSION,
        registry_version=REGISTRY_VERSION,
        description="Test snapshot fonti",
    )
    source = profile_source_rows("CIV-PCT")[0]
    kwargs = {
        "tenant_id": tenant_id,
        "rule_set_id": rule_set_id,
        "profile_id": "CIV-PCT",
        "source_id": str(source["id"]),
        "official_url": str(source["official_url"]),
        "verification_status": str(source["verification_status"]),
        "snapshot_sha256": str(source.get("snapshot_sha256") or "") or None,
        "last_verified_at": str(source.get("last_verified_at") or "") or None,
        "source_metadata": {"source_type": source.get("source_type"), "registry_version": REGISTRY_VERSION},
    }
    repo.upsert_catalog_source_snapshot(**kwargs)
    before = repo.structured_db.conn.total_changes
    repo.upsert_catalog_source_snapshot(**kwargs)

    assert repo.structured_db.conn.total_changes == before


def test_pipeline_catalogo_sql_persistente_e_revisionabile(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-1"
    source = _ready_source(
        repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-1",
        filename="ricorso-introduttivo.pdf", sha256="a" * 64,
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id,
        area_pratica="Civile",
        tribunale="Tribunale di Roma",
        tipo_procedimento="Ordinario",
        canale_operativo="PCT",
        source="PST",
        profilo_deposito={
            "area": "Civile", "branca": "Civile ordinario", "sottobranca": "Introduttivi e difensivi",
            "rito": "Ordinario", "canale_telematico": "PCT",
        },
    )

    result = FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True,
    )

    assert result.processed == 1
    assert result.proposed == 1
    assignment = repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-1")
    assert assignment is not None
    assert assignment.profile_id == "CIV-PCT"
    assert assignment.status == "proposed"
    assert assignment.document_nature == "atto_principale"
    assert len(repo.list_catalog_evidence(assignment.id)) >= 6
    assert len(repo.list_catalog_candidates(assignment.id)) == 1
    assert repo.catalog_summary(tenant_id, fascicolo_id)["total"] == 1
    table_names = {row[0] for row in repo.structured_db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"document_catalog_assignments", "document_catalog_jobs", "document_catalog_evidence", "document_catalog_reviews"} <= table_names


def test_correzione_catalogo_avvocato_rimane_sql_e_conserva_evidenze(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-CORREZIONE"
    source = _ready_source(
        repo,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        document_id="DOC-CORREZIONE",
        filename="ricorso-introduttivo.pdf",
        sha256="c" * 64,
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id,
        area_pratica="Civile",
        tribunale="Tribunale di Roma",
        tipo_procedimento="Ordinario",
        canale_operativo="PCT",
        source="PST",
        profilo_deposito={
            "area": "Civile",
            "branca": "Civile ordinario",
            "sottobranca": "Introduttivi e difensivi",
            "rito": "Ordinario",
            "canale_telematico": "PCT",
        },
    )
    FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id,
        fascicolo=fascicolo,
        sources=[source],
        actor="operatore",
        process=True,
    )
    before = repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-CORREZIONE")
    assert before is not None
    evidence_before = repo.list_catalog_evidence(before.id)
    candidates_before = repo.list_catalog_candidates(before.id)

    corrected = repo.override_catalog_assignment(
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        document_id="DOC-CORREZIONE",
        actor="avvocato",
        document_label="Comparsa di costituzione e risposta",
        document_section="atti",
        document_nature="atto_processuale",
        deposit_role="atto_principale",
        deposit_candidate=True,
        note="Verificato sul contenuto del documento.",
    )

    assert corrected is not None
    assert corrected.id == before.id
    assert corrected.status == "confirmed"
    assert corrected.source_state == "manual_override"
    assert corrected.document_label == "Comparsa di costituzione e risposta"
    assert corrected.document_section == "atti"
    assert corrected.document_nature == "atto_processuale"
    assert corrected.deposit_role == "atto_principale"
    assert corrected.deposit_candidate is True
    assert len(repo.list_catalog_evidence(corrected.id)) == len(evidence_before)
    assert len(repo.list_catalog_candidates(corrected.id)) == len(candidates_before)


def test_migrazione_sqlite_catalogo_esistente_ammette_correzione_manuale(tmp_path):
    database = tmp_path / "studio-esistente.db"
    legacy_schema = (
        (Path(__file__).resolve().parents[1] / "pct" / "sql" / "20260824_fascicolo_document_catalog.sql")
        .read_text(encoding="utf-8")
        .replace(", 'manual_override'", "")
    )
    legacy = sqlite3.connect(database)
    legacy.executescript(legacy_schema)
    legacy.execute(
        """
        INSERT INTO document_catalog_assignments (
            id, tenant_id, fascicolo_id, document_id, document_sha256,
            document_nature, document_label, document_section, deposit_role,
            status, confidence, source_state, resolver_version, reason,
            created_by, created_at, updated_by, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "assignment-esistente", "studio-test", "FASC-ESISTENTE", "DOC-ESISTENTE", "d" * 64,
            "allegato", "Allegato", "allegati", "allegato", "proposed", 60,
            "verified_snapshot", "resolver-test", "Catalogazione precedente.",
            "operatore", "2026-08-24T10:00:00+00:00", "operatore", "2026-08-24T10:00:00+00:00",
        ),
    )
    legacy.commit()
    legacy.close()

    repo = DocumentAIRepository.from_sqlite_db(database)
    migrated = repo.get_catalog_assignment("studio-test", "FASC-ESISTENTE", "DOC-ESISTENTE")
    assert migrated is not None
    assert migrated.document_label == "Allegato"
    create_sql = repo.structured_db.conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'document_catalog_assignments'"
    ).fetchone()[0]
    assert "manual_override" in create_sql

    corrected = repo.override_catalog_assignment(
        tenant_id="studio-test",
        fascicolo_id="FASC-ESISTENTE",
        document_id="DOC-ESISTENTE",
        actor="avvocato",
        document_label="Procura alle liti",
        document_section="procure",
        document_nature="procura",
        deposit_role="procura",
        deposit_candidate=True,
    )
    assert corrected is not None
    assert corrected.source_state == "manual_override"


def test_pipeline_iniziale_usa_un_solo_commit_sql(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-BATCH"
    source = _ready_source(
        repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-BATCH",
        filename="ricorso-batch.pdf", sha256="f" * 64,
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id,
        area_pratica="Civile",
        tribunale="Tribunale di Roma",
        tipo_procedimento="Ordinario",
        canale_operativo="PCT",
        source="PST",
        profilo_deposito={
            "area": "Civile", "branca": "Civile ordinario", "sottobranca": "Introduttivi e difensivi",
            "rito": "Ordinario", "canale_telematico": "PCT",
        },
    )
    statements: list[str] = []
    repo.structured_db.conn.set_trace_callback(statements.append)
    result = FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True,
    )
    repo.structured_db.conn.set_trace_callback(None)

    assert result.processed == 1
    assert sum(statement.strip().upper() == "COMMIT" for statement in statements) == 1


def test_pipeline_non_classifica_in_silenzio_senza_profilo_fascicolo(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-2"
    source = _ready_source(
        repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-2",
        filename="ricorso-non-profilato.pdf", sha256="b" * 64,
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id, area_pratica="", tribunale="", tipo_procedimento="", canale_operativo="",
        source="", profilo_deposito={},
    )

    result = FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True,
    )

    assignment = repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-2")
    assert result.review_required == 1
    assert assignment is not None
    assert assignment.status == "review_required"
    assert assignment.source_state == "review_required"
    assert repo.list_catalog_reviews(tenant_id, fascicolo_id)[0].reason_code == "missing_fascicolo_profile"


def test_pipeline_inferisce_rcd_da_due_documenti_concordanti(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-RCD"
    decree = _ready_source(
        repo,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        document_id="DOC-DECRETO",
        filename="decretoGenerico.pdf",
        sha256="1" * 64,
        tipo_documento="ATTO_GIUDIZIARIO",
        text=(
            "UFFICIO DEL GIUDICE DI PACE DI PALMI. DECRETO. "
            "Nella causa per risarcimento danni da sinistro stradale, il Giudice liquida il compenso del CTU."
        ),
    )
    notes = _ready_source(
        repo,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        document_id="DOC-NOTE",
        filename="note-udienza.pdf",
        sha256="2" * 64,
        tipo_documento="MEMORIA",
        text=(
            "Oggetto: risarcimento danni sinistro stradale. "
            "Si depositano note per l'udienza nel procedimento davanti al Giudice di Pace."
        ),
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id, area_pratica="", tribunale="Giudice di Pace di Palmi",
        tipo_procedimento="", canale_operativo="SIGP", source="PST", profilo_deposito={},
    )

    result = FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id, fascicolo=fascicolo, sources=[decree, notes], actor="operatore", process=True,
    )

    assert result.processed == 2
    assert result.proposed == 2
    decree_assignment = repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-DECRETO")
    notes_assignment = repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-NOTE")
    assert decree_assignment is not None
    assert notes_assignment is not None
    for assignment in (decree_assignment, notes_assignment):
        assert assignment.profile_id == "RCD"
        assert assignment.legal_area == "Diritto civile"
        assert assignment.legal_branch == "Responsabilità civile e danni"
        assert assignment.legal_subfamily == "Risarcimento danni da circolazione stradale"
        assert assignment.status == "proposed"
        assert len([item for item in repo.list_catalog_evidence(assignment.id) if item.evidence_type == "legal_source"]) >= 5
        assert any(item.locator == "contenuto indicizzato concordante del fascicolo" for item in repo.list_catalog_evidence(assignment.id))
    assert decree_assignment.document_label == "Decreto di liquidazione CTU"
    assert decree_assignment.deposit_candidate is False


def test_pipeline_non_cataloga_dal_nome_senza_contenuto_sql(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-CONTENUTO-MANCANTE"
    source = _ready_source(
        repo,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        document_id="DOC-DECRETO-SENZA-OCR",
        filename="decretoGenerico.pdf",
        sha256="8" * 64,
        tipo_documento="ATTO_GIUDIZIARIO",
        text="",
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id,
        area_pratica="Civile",
        tribunale="Giudice di Pace di Palmi",
        tipo_procedimento="Ordinario",
        canale_operativo="SIGP",
        source="PST",
        profilo_deposito={
            "area": "Diritto civile",
            "branca": "Responsabilità civile e danni",
            "sottobranca": "Risarcimento danni da circolazione stradale",
        },
    )

    result = FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True,
    )

    assignment = repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-DECRETO-SENZA-OCR")
    assert result.review_required == 1
    assert assignment is not None
    assert assignment.status == "review_required"
    assert assignment.source_state == "review_required"
    assert assignment.document_label == "Contenuto da indicizzare"
    assert assignment.document_nature == "da_verificare"
    assert assignment.deposit_candidate is False
    assert "nome del file non è usato per catalogare" in assignment.reason


def test_pipeline_non_usa_nome_file_quando_il_testo_non_basta_a_definire_l_atto(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-CONTENUTO-INSUFFICIENTE"
    source = _ready_source(
        repo,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        document_id="DOC-DECRETO-GENERICO",
        filename="decretoGenerico.pdf",
        sha256="a" * 64,
        tipo_documento="ATTO_GIUDIZIARIO",
        text="UFFICIO DEL GIUDICE DI PACE DI PALMI. Documento acquisito nel fascicolo.",
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id,
        area_pratica="Civile",
        tribunale="Giudice di Pace di Palmi",
        tipo_procedimento="Ordinario",
        canale_operativo="SIGP",
        source="PST",
        profilo_deposito={
            "area": "Diritto civile",
            "branca": "Responsabilità civile e danni",
            "sottobranca": "Risarcimento danni da circolazione stradale",
        },
    )

    result = FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True,
    )

    assignment = repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-DECRETO-GENERICO")
    assert result.review_required == 1
    assert assignment is not None
    assert assignment.status == "review_required"
    assert assignment.document_label == "Contenuto da verificare"
    assert assignment.document_nature == "da_verificare"
    assert assignment.deposit_role == "fuori_busta"
    assert assignment.deposit_candidate is False
    assert "nome del file non è usato per catalogare" in assignment.reason


def test_pipeline_non_sovrascrive_correzione_manuale_neppure_con_retry(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-MANUALE"
    source = _ready_source(
        repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-MANUALE",
        filename="ricorso-manuale.pdf", sha256="9" * 64,
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id, area_pratica="Civile", tribunale="Tribunale di Roma",
        tipo_procedimento="Ordinario", canale_operativo="PCT", source="PST",
        profilo_deposito={"area": "Civile", "branca": "Civile ordinario", "sottobranca": "Introduttivi e difensivi"},
    )
    pipeline = FascicoloDocumentCatalogPipeline(repo)
    pipeline.run(tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True)
    repo.override_catalog_assignment(
        tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-MANUALE", actor="avvocato",
        document_label="Atto corretto dall'avvocato", document_section="atti", document_nature="atto_processuale",
        deposit_role="atto_principale", deposit_candidate=True,
    )

    result = pipeline.run(
        tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True, retry=True,
    )

    assignment = repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-MANUALE")
    assert result.processed == 0
    assert result.skipped_current == 1
    assert assignment is not None
    assert assignment.source_state == "manual_override"
    assert assignment.document_label == "Atto corretto dall'avvocato"


def test_pipeline_conserva_lo_storico_di_revisioni_ripetute(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-3"
    source = _ready_source(
        repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-3",
        filename="documento-senza-profilo.pdf", sha256="c" * 64,
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id, area_pratica="", tribunale="", tipo_procedimento="", canale_operativo="",
        source="", profilo_deposito={},
    )
    pipeline = FascicoloDocumentCatalogPipeline(repo)

    pipeline.run(tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True)
    repo.resolve_catalog_assignment(
        tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-3",
        actor="avvocato", status="review_required", note="Profilo da completare.",
    )
    pipeline.run(tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True)
    repo.resolve_catalog_assignment(
        tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-3",
        actor="avvocato", status="review_required", note="Seconda revisione registrata.",
    )

    reviews = repo.list_catalog_reviews(tenant_id, fascicolo_id, include_resolved=True)
    assert len(reviews) == 2
    assert {review.state for review in reviews} == {"resolved"}


def test_pipeline_non_riestrae_documento_immutato_senza_retry(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-IMMUTABILE"
    source = _ready_source(
        repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-IMMUTABILE",
        filename="ricorso-immutato.pdf", sha256="e" * 64,
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id,
        area_pratica="Civile",
        tribunale="Tribunale di Roma",
        tipo_procedimento="Ordinario",
        canale_operativo="PCT",
        source="PST",
        profilo_deposito={
            "area": "Civile", "branca": "Civile ordinario", "sottobranca": "Introduttivi e difensivi",
            "rito": "Ordinario", "canale_telematico": "PCT",
        },
    )
    pipeline = FascicoloDocumentCatalogPipeline(repo)
    pipeline.run(tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True)

    def extracted_text_must_not_be_read(*_args, **_kwargs):
        raise AssertionError("Il refresh idempotente non deve riestrarre il documento invariato.")

    repo.get_extracted_text = extracted_text_must_not_be_read  # type: ignore[method-assign]
    result = pipeline.run(tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True)

    assert result.processed == 0
    assert result.skipped_current == 1


def test_migrazione_sqlite_conserva_revisione_storica_da_vecchio_vincolo(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-4"
    source = _ready_source(
        repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-4",
        filename="documento-da-rivedere.pdf", sha256="d" * 64,
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id, area_pratica="", tribunale="", tipo_procedimento="", canale_operativo="",
        source="", profilo_deposito={},
    )
    FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True,
    )
    assignment = repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-4")
    assert assignment is not None
    conn = repo.structured_db.conn
    conn.execute("DROP TABLE document_catalog_reviews")
    conn.execute(
        """
        CREATE TABLE document_catalog_reviews (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, fascicolo_id TEXT NOT NULL,
            assignment_id TEXT NOT NULL, state TEXT NOT NULL, reason_code TEXT NOT NULL,
            reason TEXT NOT NULL, resolved_by TEXT, resolution_note TEXT,
            created_at TEXT NOT NULL, resolved_at TEXT,
            UNIQUE (assignment_id, state)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO document_catalog_reviews (
            id, tenant_id, fascicolo_id, assignment_id, state, reason_code, reason, created_at
        ) VALUES (?, ?, ?, ?, 'resolved', 'legacy', 'Storico precedente', ?)
        """,
        ("legacy-review", tenant_id, fascicolo_id, assignment.id, utc_now()),
    )
    conn.commit()

    repo._ensure_sql_schema()
    conn.execute(
        """
        INSERT INTO document_catalog_reviews (
            id, tenant_id, fascicolo_id, assignment_id, state, reason_code, reason, created_at
        ) VALUES (?, ?, ?, ?, 'resolved', 'seconda', 'Seconda revisione', ?)
        """,
        ("second-review", tenant_id, fascicolo_id, assignment.id, utc_now()),
    )
    conn.commit()

    assert len(repo.list_catalog_reviews(tenant_id, fascicolo_id, include_resolved=True)) == 2
