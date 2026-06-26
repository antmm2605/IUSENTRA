from pathlib import Path
from types import SimpleNamespace

from pct.document_intelligence.models import DocumentAIRecord, DocumentAIText, DocumentAIVersion
from pct.document_intelligence.repository import DocumentAIRepository
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.fascicolo_document_catalog import (
    catalog_tipo_documento_per_nome,
    classify_fascicolo_document,
    document_ai_texts_for_catalog,
    should_apply_catalog_type,
)
from scripts.reclassify_fascicolo_document_catalog import run_reclassification


def test_ricorso_e_sempre_atto_principale():
    classification = classify_fascicolo_document(filename="Ricorso introduttivo.pdf")

    assert classification.role == "atto_principale"
    assert classification.tipo_documento == TipoDocumento.RICORSO
    assert classification.deposit_role == "atto_principale"
    assert classification.section == "atti"
    assert catalog_tipo_documento_per_nome("Ricorso introduttivo.pdf") == TipoDocumento.RICORSO


def test_autocertificazione_ricorso_resta_allegato_di_supporto():
    classification = classify_fascicolo_document(
        filename="Autocertificazione ricorso.PDF",
        tipo=TipoDocumento.RICORSO,
    )

    assert classification.role == "allegato"
    assert classification.tipo_documento == TipoDocumento.ALLEGATO
    assert classification.deposit_role == "allegato"
    assert classification.deposit_candidate is True
    assert should_apply_catalog_type(TipoDocumento.RICORSO, classification) is True


def test_sentenza_ocr_non_resta_atto_giudiziario_principale():
    classification = classify_fascicolo_document(
        filename="atto.pdf",
        tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        extracted_text="REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO SENTENZA nella causa iscritta al ruolo.",
    )

    assert classification.role == "provvedimento"
    assert classification.tipo_documento == TipoDocumento.SENTENZA
    assert classification.deposit_role == "allegato"
    assert should_apply_catalog_type(TipoDocumento.ATTO_GIUDIZIARIO, classification) is True


def test_contributo_pagopa_non_diventa_atto_principale():
    classification = classify_fascicolo_document(
        filename="atto.pdf",
        tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        extracted_text="Ricevuta pagamento PagoPA contributo unificato. Importo versato euro 49,00.",
    )

    assert classification.role == "contributo_unificato"
    assert classification.section == "pagamenti"
    assert classification.deposit_role == "contributo_unificato"
    assert classification.tipo_documento == TipoDocumento.DEPOSITO_PCT


def test_iniziali_cu_senza_pagamento_non_generano_contributo():
    classification = classify_fascicolo_document(
        filename="sentenza-carta-docente.pdf",
        extracted_text="La signora C.U. chiede il riconoscimento della carta elettronica pari a euro 500,00.",
    )

    assert classification.role != "contributo_unificato"


def test_note_di_trattazione_non_restano_verbale():
    doc = SimpleNamespace(
        nome="note_di_trattazione_scritta_ZURICH_udienza_del_19-03-2025.pdf.p7m",
        tipo=TipoDocumento.VERBALE,
    )

    classification = classify_fascicolo_document(
        doc,
        extracted_text="Verbale di udienza. Le parti depositano note di trattazione scritta.",
    )

    assert classification.role == "atto_difensivo"
    assert classification.section == "atti"
    assert classification.tipo_documento == TipoDocumento.MEMORIA
    assert should_apply_catalog_type(TipoDocumento.VERBALE, classification) is True


def test_nome_verbale_prevale_su_ocr_sentenza_generica():
    doc = SimpleNamespace(nome="verbaleAttoGenerico.pdf", tipo=TipoDocumento.VERBALE)

    classification = classify_fascicolo_document(
        doc,
        extracted_text="Il giudice richiama la sentenza citata dalle parti nel corso dell'udienza.",
    )

    assert classification.role == "provvedimento"
    assert classification.label == "Verbale"
    assert classification.tipo_documento == TipoDocumento.VERBALE
    assert classification.deposit_role == "allegato"


def test_document_ai_texts_for_catalog_abbina_per_hash(tmp_path: Path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )
    fascicolo = gf.nuovo("Test catalogo", TipoFascicolo.CIVILE)
    doc = gf.aggiungi_documento(
        fascicolo.id,
        "atto-generico.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-1.4\nsentenza\n%%EOF",
    )
    storage_root = tmp_path / "fascicoli" / "documenti_ai"
    repo = DocumentAIRepository(storage_root / "documenti_ai.json", storage_root)
    record = DocumentAIRecord(
        id="docai-1",
        tenant_id="tenant-test",
        fascicolo_id=fascicolo.id,
        original_filename="nome-diverso.pdf",
        safe_filename="nome-diverso.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        size_bytes=10,
        sha256=doc.hash_sha256,
        status="ready",
        current_version_id="v1",
        page_count=1,
        created_by="test",
        created_at="2026-06-25T10:00:00Z",
        updated_at="2026-06-25T10:00:00Z",
    )
    repo.create_document(record)
    repo.create_version(
        DocumentAIVersion(
            id="v1",
            tenant_id="tenant-test",
            fascicolo_id=fascicolo.id,
            document_id="docai-1",
            version_number=1,
            source="upload",
            storage_path="tenant-test/fascicoli/test/documenti_ai/docai-1/v1/atto.pdf",
            extracted_text_path=None,
            pdf_preview_path=None,
            sha256=doc.hash_sha256,
            created_by="test",
            created_at="2026-06-25T10:00:00Z",
        )
    )
    repo.save_extracted_text(
        DocumentAIText(
            document_id="docai-1",
            version_id="v1",
            tenant_id="tenant-test",
            fascicolo_id=fascicolo.id,
            text="SENTENZA del Tribunale",
            pages=[],
            extraction_engine="test",
            created_at="2026-06-25T10:00:00Z",
        )
    )

    texts = document_ai_texts_for_catalog(
        tenant_ids=["tenant-test"],
        fascicolo_id=fascicolo.id,
        documents=gf.get(fascicolo.id).documenti,
        fascicoli_db_path=tmp_path / "fascicoli" / "fascicoli.json",
        storage_root=storage_root,
    )

    assert texts[doc.id] == "SENTENZA del Tribunale"


def test_reclassify_catalog_apply_corregge_atti_esistenti(tmp_path: Path):
    data_root = tmp_path / "data"
    tenant_root = data_root / "tenants" / "tenant-test"
    registry = data_root / "tenants.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text('{"tenant-test": {"slug": "tenant-test", "storage_key": "tenant-test"}}', encoding="utf-8")
    gf = GestioneFascicoli(
        db_path=str(tenant_root / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tenant_root / "fascicoli" / "documenti"),
        archive_dir=str(tenant_root / "fascicoli" / "archivio"),
    )
    fascicolo = gf.nuovo("Test catalogo", TipoFascicolo.CIVILE)
    sentenza = gf.aggiungi_documento(
        fascicolo.id,
        "atto-generico.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-1.4\nsentenza\n%%EOF",
    )
    gf.aggiungi_documento(
        fascicolo.id,
        "Ricorso introduttivo.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-1.4\nricorso\n%%EOF",
    )
    extracted = (
        tenant_root
        / "fascicoli"
        / "documenti_ai"
        / "tenant-test"
        / "fascicoli"
        / fascicolo.id
        / "documenti_ai"
        / "docai-sentenza"
        / "v1"
        / "extracted_text.json"
    )
    extracted.parent.mkdir(parents=True, exist_ok=True)
    extracted.write_text(
        '{"tenant_id":"tenant-test","fascicolo_id":"%s","document_id":"%s","filename":"atto-generico.pdf","sha256":"%s","text":"REPUBBLICA ITALIANA SENTENZA"}'
        % (fascicolo.id, "docai-sentenza", sentenza.hash_sha256),
        encoding="utf-8",
    )

    report = run_reclassification(data_root=data_root, registry=registry, tenants={"tenant-test"}, apply=True)
    updated = GestioneFascicoli(
        db_path=str(tenant_root / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tenant_root / "fascicoli" / "documenti"),
        archive_dir=str(tenant_root / "fascicoli" / "archivio"),
    ).get(fascicolo.id)
    by_name = {doc.nome: doc for doc in updated.documenti}

    assert report["ok"] is True
    assert by_name["atto-generico.pdf"].tipo == TipoDocumento.SENTENZA
    assert by_name["Ricorso introduttivo.pdf"].tipo == TipoDocumento.RICORSO
