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
import pct.document_intelligence.catalog_resolver as catalog_resolver
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


def test_pipeline_riconosce_note_per_la_trattazione_anche_se_citano_ctu(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-NOTE-TRATTAZIONE"
    source = _ready_source(
        repo,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        document_id="DOC-NOTE-CTU",
        filename="documento-generico.pdf",
        sha256="e" * 64,
        tipo_documento="MEMORIA",
        text=(
            "TRIBUNALE ORDINARIO. Note per la trattazione scritta. "
            "La consulenza tecnica d'ufficio ha concluso la propria perizia."
        ),
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
        },
    )

    result = FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True,
    )

    assignment = repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-NOTE-CTU")
    assert result.proposed == 1
    assert assignment is not None
    assert assignment.document_label == "Note di trattazione scritta"
    assert assignment.document_nature == "atto_difensivo"
    evidence = repo.list_catalog_evidence(assignment.id)
    assert any(item.evidence_type == "document_identity" for item in evidence)


def test_pipeline_riconosce_identita_dal_contenuto_per_istanze_depositi_e_decreti(tmp_path):
    """Le formule nel testo prevalgono su file generici e richiami CTU."""

    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-IDENTITA-ATTI"
    sources = [
        _ready_source(
            repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            document_id="DOC-ISTANZA", filename="documento-1.pdf", sha256="f" * 64,
            text=(
                "GIUDICE DI PACE. ISTANZA PER LA SOSTITUZIONE DELL'UDIENZA "
                "IN PRESENZA CON IL DEPOSITO DI NOTE SCRITTE. Si richiama la CTU."
            ),
        ),
        _ready_source(
            repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            document_id="DOC-DEPOSITO", filename="documento-2.pdf", sha256="g" * 64,
            text="GIUDICE DI PACE. NOTA DI DEPOSITO. Si deposita l'atto di nomina del CTP.",
        ),
        _ready_source(
            repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            document_id="DOC-DECRETO-UDIENZA", filename="documento-3.pdf", sha256="h" * 64,
            text=(
                "DECRETO DI FISSAZIONE UDIENZA. Il giudice rinvia la causa "
                "per l'esame della CTU."
            ),
        ),
        _ready_source(
            repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            document_id="DOC-ISTANZE-CONCLUSIONI", filename="documento-4.pdf", sha256="i" * 64,
            text="ISTANZE E CONCLUSIONI. Risposta al primo quesito tecnico.",
        ),
    ]
    fascicolo = SimpleNamespace(
        id=fascicolo_id,
        area_pratica="Civile",
        tribunale="Giudice di Pace",
        tipo_procedimento="Ordinario",
        canale_operativo="PCT",
        source="PST",
        profilo_deposito={"area": "Civile", "branca": "Civile ordinario", "sottobranca": "Introduttivi e difensivi"},
    )

    result = FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id, fascicolo=fascicolo, sources=sources, actor="operatore", process=True,
    )

    assert result.proposed == 4
    assignments = {
        source.source_id: repo.get_catalog_assignment(tenant_id, fascicolo_id, source.source_id)
        for source in sources
    }
    assert assignments["DOC-ISTANZA"].document_label == "Istanza di trattazione scritta"  # type: ignore[union-attr]
    assert assignments["DOC-ISTANZA"].document_nature == "atto_difensivo"  # type: ignore[union-attr]
    assert assignments["DOC-DEPOSITO"].document_label == "Nota di deposito"  # type: ignore[union-attr]
    assert assignments["DOC-DEPOSITO"].deposit_candidate is False  # type: ignore[union-attr]
    assert assignments["DOC-DECRETO-UDIENZA"].document_label == "Decreto di fissazione udienza"  # type: ignore[union-attr]
    assert assignments["DOC-DECRETO-UDIENZA"].deposit_candidate is False  # type: ignore[union-attr]
    assert assignments["DOC-ISTANZE-CONCLUSIONI"].document_label == "Istanze e conclusioni"  # type: ignore[union-attr]
    for assignment in assignments.values():
        assert assignment is not None
        evidence = repo.list_catalog_evidence(assignment.id)
        assert any(item.evidence_type == "document_identity" for item in evidence)


def test_resolver_non_promuove_un_solo_presidio_a_identita_documentale(monkeypatch):
    procedural_result = catalog_resolver.DocumentCatalogClassification(
        role="atp_ctu",
        label="ATP previdenziale / CTU",
        section="udienze",
        confidence=88,
        evidence="nome o OCR: regola presidio atp_previdenziale_ctu",
        tipo_documento=catalog_resolver.TipoDocumento.ALLEGATO,
        deposit_role="allegato",
        deposit_candidate=True,
    )
    monkeypatch.setattr(catalog_resolver, "_classify_indexed_content", lambda _text: procedural_result)

    resolution = catalog_resolver.resolve_document_catalog(
        tenant_id="studio-test",
        fascicolo_id="FASC-PRESIDIO",
        document_id="DOC-PRESIDIO",
        document_sha256="p" * 64,
        filename="documento-generico.pdf",
        extracted_text="Il fascicolo richiama un controllo CTU senza intestazione dell'atto.",
        document_metadata={},
        fascicolo_context={
            "area": "Civile",
            "branca": "Civile ordinario",
            "sottobranca": "Introduttivi e difensivi",
        },
    )

    assert resolution.status == "review_required"
    assert resolution.source_state == "review_required"
    assert resolution.document_label == "Contenuto da verificare"
    assert resolution.document_nature == "da_verificare"
    assert resolution.deposit_candidate is False
    assert "segnalazione processuale" in resolution.reason


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


def test_migrazione_sqlite_estende_evidenze_identita_e_presidio(tmp_path):
    database = tmp_path / "studio-evidenze-esistente.db"
    schema_path = Path(__file__).resolve().parents[1] / "pct" / "sql" / "20260824_fascicolo_document_catalog.sql"
    legacy_schema = schema_path.read_text(encoding="utf-8").replace(
        ", 'document_identity', 'procedural_signal'", ""
    )
    legacy = sqlite3.connect(database)
    legacy.executescript(legacy_schema)
    legacy.commit()
    legacy.close()

    repo = DocumentAIRepository.from_sqlite_db(database)
    create_sql = repo.structured_db.conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'document_catalog_evidence'"
    ).fetchone()[0]

    assert "document_identity" in create_sql
    assert "procedural_signal" in create_sql


def test_pipeline_separa_identita_documentale_e_segnali_di_presidio(tmp_path):
    """Un richiamo CTU non può trasformare memorie o sentenze in ATP/decreto."""

    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-test"
    fascicolo_id = "FASC-IDENTITA"
    sources = [
        _ready_source(
            repo,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            document_id="DOC-MEMORIA",
            filename="documento-1.pdf",
            sha256="1" * 64,
            tipo_documento="ATTO_GIUDIZIARIO",
            text="MEMORIA CONCLUSIONALE. La parte richiama la relazione del CTU e chiede il rigetto della domanda.",
        ),
        _ready_source(
            repo,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            document_id="DOC-SENTENZA",
            filename="documento-2.pdf",
            sha256="2" * 64,
            tipo_documento="ATTO_GIUDIZIARIO",
            text=(
                "REPUBBLICA ITALIANA. IN NOME DEL POPOLO ITALIANO. SENTENZA. "
                "Il giudice liquida il compenso della CTU nelle spese di lite."
            ),
        ),
        _ready_source(
            repo,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            document_id="DOC-NOTE",
            filename="documento-3.pdf",
            sha256="3" * 64,
            tipo_documento="ATTO_GIUDIZIARIO",
            text="NOTE DI TRATTAZIONE SCRITTA IN SOSTITUZIONE DELL'UDIENZA ex art. 127-ter c.p.c.",
        ),
        _ready_source(
            repo,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            document_id="DOC-NOTE-CONCLUSIVE",
            filename="documento-3bis.pdf",
            sha256="6" * 64,
            tipo_documento="ATTO_GIUDIZIARIO",
            text=(
                "\ufffdNote cocnlusive. R.G. 466/2023. Mario Rossi, c.f. RSSMRA80A01H501U, "
                "rappresentato dall'avv. Bianchi. Le note conclusionali richiamano la relazione del CTU."
            ),
        ),
        _ready_source(
            repo,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            document_id="DOC-CANCELLERIA",
            filename="documento-4.pdf",
            sha256="4" * 64,
            tipo_documento="ATTO_GIUDIZIARIO",
            text="NOTIFICAZIONE DI CANCELLERIA. Si comunica il deposito della relazione del CTU.",
        ),
        _ready_source(
            repo,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            document_id="DOC-CTU",
            filename="documento-5.pdf",
            sha256="5" * 64,
            tipo_documento="ATTO_GIUDIZIARIO",
            text="Il consulente tecnico d'ufficio accetta l'incarico e giura di bene e fedelmente adempiere.",
        ),
    ]
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

    result = FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id,
        fascicolo=fascicolo,
        sources=sources,
        actor="operatore",
        process=True,
    )

    assert result.processed == len(sources)
    assignments = {
        document_id: repo.get_catalog_assignment(tenant_id, fascicolo_id, document_id)
        for document_id in ("DOC-MEMORIA", "DOC-SENTENZA", "DOC-NOTE", "DOC-NOTE-CONCLUSIVE", "DOC-CANCELLERIA", "DOC-CTU")
    }
    assert assignments["DOC-MEMORIA"].document_label == "Memoria conclusionale"  # type: ignore[union-attr]
    assert assignments["DOC-SENTENZA"].document_label == "Sentenza"  # type: ignore[union-attr]
    assert assignments["DOC-NOTE"].document_label == "Note di trattazione scritta"  # type: ignore[union-attr]
    assert assignments["DOC-NOTE-CONCLUSIVE"].document_label == "Note conclusionali"  # type: ignore[union-attr]
    assert assignments["DOC-CANCELLERIA"].document_label == "Comunicazione di cancelleria"  # type: ignore[union-attr]
    assert assignments["DOC-CTU"].document_label == "Accettazione incarico e giuramento CTU"  # type: ignore[union-attr]
    assert assignments["DOC-MEMORIA"].document_nature != "atp_ctu"  # type: ignore[union-attr]
    assert assignments["DOC-SENTENZA"].document_nature == "provvedimento"  # type: ignore[union-attr]
    assert assignments["DOC-SENTENZA"].document_label != "Decreto di liquidazione CTU"  # type: ignore[union-attr]
    assert assignments["DOC-NOTE"].document_nature == "atto_difensivo"  # type: ignore[union-attr]
    assert assignments["DOC-CANCELLERIA"].document_nature == "comunicazione"  # type: ignore[union-attr]
    for assignment in assignments.values():
        assert assignment is not None
        evidence = repo.list_catalog_evidence(assignment.id)
        assert any(item.evidence_type == "document_identity" for item in evidence)
    memoria_evidence = repo.list_catalog_evidence(assignments["DOC-MEMORIA"].id)  # type: ignore[union-attr]
    assert any(item.evidence_type == "procedural_signal" and item.locator == "atp_previdenziale_ctu" for item in memoria_evidence)
    note_evidence = repo.list_catalog_evidence(assignments["DOC-NOTE-CONCLUSIVE"].id)  # type: ignore[union-attr]
    assert all("\ufffd" not in item.excerpt for item in note_evidence)
    assert all("RSSMRA80A01H501U" not in item.excerpt and "Mario Rossi" not in item.excerpt for item in note_evidence)
    assert any(item.evidence_type == "legal_source" and "fonte ufficiale" in item.excerpt for item in note_evidence)


def test_lettura_catalogo_non_crea_job_senza_elaborazione(tmp_path):
    """La GET del catalogo non deve lasciare job queued privi di consumer."""

    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id = "studio-read-only"
    fascicolo_id = "FASC-READ-ONLY"
    source = _ready_source(
        repo,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        document_id="DOC-READ-ONLY",
        filename="memoria.pdf",
        sha256="7" * 64,
        tipo_documento="ATTO_GIUDIZIARIO",
        text="MEMORIA CONCLUSIVA."
    )
    fascicolo = SimpleNamespace(
        id=fascicolo_id,
        area_pratica="Civile",
        tribunale="Tribunale di Roma",
        tipo_procedimento="Ordinario",
        canale_operativo="PCT",
        source="PST",
        profilo_deposito={},
    )

    result = FascicoloDocumentCatalogPipeline(repo).run(
        tenant_id=tenant_id,
        fascicolo=fascicolo,
        sources=[source],
        actor="operatore",
        process=False,
    )

    assert result.queued == 0
    jobs = repo.structured_db.conn.execute(
        "SELECT COUNT(*) FROM document_catalog_jobs WHERE tenant_id = ? AND fascicolo_id = ?",
        (tenant_id, fascicolo_id),
    ).fetchone()[0]
    assert jobs == 0
