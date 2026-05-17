from __future__ import annotations

import json

import pytest

from lex.dataset import (
    ChunkingOptions,
    DocumentPage,
    QAGenerationPolicy,
    StudioDatasetBatchOptions,
    StudioDatasetDocument,
    build_studio_dataset_batch,
    build_ingestion_manifest,
    build_qa_generation_tasks,
    build_easy_dataset_external_project_spec,
    build_studio_dataset_pipeline,
    build_llama_factory_dataset_info_entry,
    build_llama_factory_project_spec,
    chunk_document,
    easy_dataset_supported_capabilities,
    export_qa_pairs,
    export_qa_pairs_jsonl,
    generate_mock_qa_pairs,
    load_document_ai_json_documents,
    llama_factory_supported_capabilities,
    mark_qa_pair_reviewed,
)
from scripts.build_lex_studio_dataset import main as build_lex_studio_dataset_main


def _document(**overrides) -> StudioDatasetDocument:
    payload = {
        "tenant_id": "tenant-a",
        "document_id": "doc-1",
        "title": "Memoria autorizzata",
        "text": (
            "La memoria riepiloga la domanda di pagamento e richiama la fattura n. 12/2026. "
            "Il documento indica che la controparte ha ricevuto la diffida e non ha pagato."
        ),
        "source_name": r"C:\studio\riservato\memoria.pdf",
        "mime_type": "application/pdf",
        "source_kind": "pdf",
        "fascicolo_id": "fas-1",
        "sha256": "a" * 64,
    }
    payload.update(overrides)
    return StudioDatasetDocument(**payload)


def test_ingestion_manifest_tenant_aware_e_senza_path_assoluti():
    manifest = build_ingestion_manifest(
        "tenant-a",
        [_document()],
        created_at="2026-05-17T10:00:00Z",
    )

    assert manifest.tenant_id == "tenant-a"
    assert manifest.storage_scope == "tenant:tenant-a"
    assert manifest.fine_tuning_policy["automatic_training"] is False
    assert manifest.fine_tuning_policy["requires_human_review"] is True
    assert manifest.documents[0].source_name == "memoria.pdf"
    assert "studio\\riservato" not in manifest.documents[0].source_name

    with pytest.raises(ValueError):
        build_ingestion_manifest("tenant-a", [_document(tenant_id="tenant-b")])


def test_chunking_testo_e_pdf_con_estrattore_mock_preserva_metadata_fonte():
    text_document = _document(
        source_name="note.txt",
        mime_type="text/plain",
        source_kind="text",
        text=" ".join(f"periodo {index}" for index in range(80)),
    )

    chunks = chunk_document(text_document, options=ChunkingOptions(max_chars=180, overlap_chars=20, min_chars=20))

    assert len(chunks) > 1
    assert all(chunk.tenant_id == "tenant-a" for chunk in chunks)
    assert chunks[0].source.source_name == "note.txt"
    assert chunks[0].source.chunk_id == chunks[0].chunk_id
    assert chunks[0].metadata["rag_use"] == "retrieval_immediato_tenant_aware"

    pdf_document = _document(text="")
    pdf_chunks = chunk_document(
        pdf_document,
        options=ChunkingOptions(max_chars=220, overlap_chars=0, min_chars=20),
        text_extractor=lambda document: "Testo estratto dal PDF per Lex con fonte pagina uno.",
    )

    assert len(pdf_chunks) == 1
    assert "Testo estratto dal PDF" in pdf_chunks[0].text
    assert pdf_chunks[0].source.source_kind == "pdf"


def test_chunking_pagine_conserva_intervallo_pagina():
    document = _document(
        text="",
        pages=(
            DocumentPage(page_number=1, text="Prima pagina con riepilogo del fatto."),
            DocumentPage(page_number=2, text="Seconda pagina con conclusioni e richieste."),
        ),
    )

    chunks = chunk_document(document, options=ChunkingOptions(max_chars=180, overlap_chars=0, min_chars=10))

    assert [chunk.source.page_start for chunk in chunks] == [1, 2]
    assert [chunk.source.page_end for chunk in chunks] == [1, 2]


def test_generazione_task_e_qa_mock_richiede_revisione_e_non_salva_ragionamento_interno():
    chunks = chunk_document(_document(), options=ChunkingOptions(max_chars=220, overlap_chars=0, min_chars=20))
    policy = QAGenerationPolicy(max_pairs_per_chunk=1, min_chunk_chars=20)

    tasks = build_qa_generation_tasks(chunks, policy=policy)
    pairs = generate_mock_qa_pairs(tasks, policy=policy)

    assert tasks[0].requires_human_review is True
    assert tasks[0].metadata["automatic_training"] is False
    assert pairs[0].review_status == "pending_human_review"
    assert pairs[0].requires_human_review is True
    assert pairs[0].source.document_id == "doc-1"
    assert pairs[0].source.chunk_id == chunks[0].chunk_id
    assert "fattura" in pairs[0].answer
    assert "ragionamento" not in json.dumps(pairs[0].to_dict(), ensure_ascii=False).lower()

    with pytest.raises(ValueError):
        QAGenerationPolicy(external_training_allowed=True)

    with pytest.raises(ValueError):
        QAGenerationPolicy(save_internal_reasoning=True)


def test_export_jsonl_alpaca_sharegpt_con_review_e_metadata_fonte():
    chunks = chunk_document(_document(), options=ChunkingOptions(max_chars=220, overlap_chars=0, min_chars=20))
    pairs = generate_mock_qa_pairs(build_qa_generation_tasks(chunks, policy=QAGenerationPolicy(min_chunk_chars=20)))

    assert export_qa_pairs_jsonl(pairs, dataset_format="alpaca") == ""

    approved = mark_qa_pair_reviewed(pairs[0], approved=True, reviewer_id="avv-1", note="Verificato su documento.")
    alpaca_jsonl = export_qa_pairs_jsonl([approved], dataset_format="alpaca")
    alpaca_row = json.loads(alpaca_jsonl)

    assert alpaca_row["instruction"] == approved.question
    assert alpaca_row["output"] == approved.answer
    assert alpaca_row["metadata"]["review_status"] == "approved"
    assert alpaca_row["metadata"]["source"]["document_id"] == "doc-1"
    assert alpaca_row["metadata"]["automatic_training"] is False
    assert alpaca_row["metadata"]["external_training"] is False

    sharegpt_jsonl = export_qa_pairs_jsonl([approved], dataset_format="sharegpt")
    sharegpt_row = json.loads(sharegpt_jsonl)

    assert sharegpt_row["conversations"][0]["from"] == "human"
    assert sharegpt_row["conversations"][1]["from"] == "gpt"
    assert sharegpt_row["metadata"]["source"]["chunk_id"] == chunks[0].chunk_id

    with pytest.raises(ValueError):
        export_qa_pairs_jsonl([approved], external_training=True)


def test_export_multilingual_json_e_csv_per_interoperabilita_dataset():
    chunks = chunk_document(_document(), options=ChunkingOptions(max_chars=220, overlap_chars=0, min_chars=20))
    pairs = generate_mock_qa_pairs(build_qa_generation_tasks(chunks, policy=QAGenerationPolicy(min_chunk_chars=20)))
    approved = mark_qa_pair_reviewed(pairs[0], approved=True, reviewer_id="avv-1")

    multilingual_json = export_qa_pairs([approved], dataset_format="multilingual", file_type="json")
    rows = json.loads(multilingual_json)
    assert rows[0]["language"] == "it"
    assert rows[0]["dataset_type"] == "single_turn_qa"
    assert rows[0]["messages"][0]["role"] == "user"
    assert "ragionamento" not in multilingual_json.lower()

    csv_payload = export_qa_pairs([approved], dataset_format="multilingual", file_type="csv")
    assert "question,answer,format,dataset_kind,metadata_json" in csv_payload
    assert "multilingual" in csv_payload


def test_export_blocca_sensibili_finche_non_autorizzati_per_dataset_locale():
    sensitive_document = _document(
        text=(
            "Il cliente RSSMRA80A01H501U ha inviato email mario.rossi@example.com. "
            "La risposta deve restare in revisione prima del dataset locale."
        )
    )
    chunks = chunk_document(sensitive_document, options=ChunkingOptions(max_chars=240, overlap_chars=0, min_chars=20))
    pairs = generate_mock_qa_pairs(build_qa_generation_tasks(chunks, policy=QAGenerationPolicy(min_chunk_chars=20)))
    approved = mark_qa_pair_reviewed(pairs[0], approved=True, reviewer_id="privacy")

    assert approved.privacy_classification == "sensitive"
    assert "RSSMRA80A01H501U" not in approved.answer
    assert "mario.rossi@example.com" not in approved.answer
    assert export_qa_pairs_jsonl([approved], dataset_format="alpaca") == ""

    exported = export_qa_pairs_jsonl([approved], dataset_format="alpaca", allow_sensitive=True)
    assert "[CODICE_FISCALE_OSCURATO]" in exported
    assert "[EMAIL_OSCURATA]" in exported


def test_pipeline_completa_distingue_manifest_chunk_task_e_coppie_qa():
    result = build_studio_dataset_pipeline(
        "tenant-a",
        [_document()],
        created_at="2026-05-17T10:00:00Z",
        chunking_options=ChunkingOptions(max_chars=220, overlap_chars=0, min_chars=20),
        qa_policy=QAGenerationPolicy(min_chunk_chars=20),
    )

    assert result.manifest.tenant_id == "tenant-a"
    assert result.chunks
    assert result.qa_tasks
    assert result.qa_pairs
    payload = result.to_dict(include_chunk_text=False)
    assert "text" not in payload["chunks"][0]
    assert payload["manifest"]["rag_policy"]["mode"] == "rag_immediate"


def test_easy_dataset_resta_tool_esterno_opzionale_senza_copia_codice_agpl():
    manifest = build_ingestion_manifest("tenant-a", [_document()], created_at="2026-05-17T10:00:00Z")
    capabilities = easy_dataset_supported_capabilities()
    spec = build_easy_dataset_external_project_spec(
        manifest,
        domain_label_tree=[{"label": "Recupero crediti", "children": [{"label": "Diffida"}]}],
    )

    assert capabilities["reference"]["repository"] == "https://github.com/ConardLi/easy-dataset"
    assert capabilities["reference"]["license"] == "AGPL-3.0"
    assert capabilities["iusentra_policy"]["no_agpl_code_import"] is True
    assert "EPUB" in capabilities["input_formats"]
    assert "multi_turn_dialogue" in capabilities["dataset_types"]
    assert "csv" in capabilities["export_formats"]
    assert spec["license_boundary"]["copy_agpl_code_into_iusentra"] is False
    assert spec["dataset_targets"]["rag"]["fine_tuning_required"] is False
    assert spec["dataset_targets"]["fine_tuning"]["human_review_required"] is True
    assert spec["model_policy"]["ollama_local"].startswith("consentito")


def test_llama_factory_ollama_resta_training_governato_e_non_automatico():
    manifest = build_ingestion_manifest("tenant-a", [_document()], created_at="2026-05-17T10:00:00Z")

    alpaca_entry = build_llama_factory_dataset_info_entry(
        dataset_name="iusentra_lex",
        file_name="iusentra_lex_alpaca.jsonl",
        dataset_format="alpaca",
    )
    sharegpt_entry = build_llama_factory_dataset_info_entry(
        dataset_name="iusentra_lex_chat",
        file_name="iusentra_lex_sharegpt.jsonl",
        dataset_format="sharegpt",
    )
    capabilities = llama_factory_supported_capabilities()
    spec = build_llama_factory_project_spec(
        manifest,
        dataset_name="iusentra_lex",
        file_name="iusentra_lex_alpaca.jsonl",
        base_model="qwen2.5:7b-instruct",
    )

    assert alpaca_entry["iusentra_lex"]["columns"]["prompt"] == "instruction"
    assert alpaca_entry["iusentra_lex"]["columns"]["response"] == "output"
    assert sharegpt_entry["iusentra_lex_chat"]["formatting"] == "sharegpt"
    assert sharegpt_entry["iusentra_lex_chat"]["tags"]["assistant_tag"] == "gpt"
    assert capabilities["reference"]["repository"] == "https://github.com/hiyouga/LLaMA-Factory"
    assert capabilities["reference"]["license"] == "Apache-2.0"
    assert capabilities["recommended_stage_for_lex"] == "sft"
    assert capabilities["ollama"]["preferred_runtime"] is True
    assert capabilities["ollama"]["automatic_import"] is False
    assert "ollama show <nome-modello-lex>" in capabilities["ollama"]["manual_commands"]
    assert capabilities["iusentra_policy"]["no_automatic_llama_factory_training"] is True
    assert capabilities["iusentra_policy"]["no_automatic_ollama_import"] is True
    assert capabilities["iusentra_policy"]["approved_pairs_only"] is True
    assert spec["dataset_info_json_entry"] == alpaca_entry
    assert spec["dataset_registration"]["target_file"] == "data/dataset_info.json"
    assert spec["dataset_registration"]["manual_edit_required"] is True
    assert spec["dataset_registration"]["preview_required_before_training"] is True
    assert spec["manual_llama_factory_commands"] == ["llamafactory-cli webui"]
    assert spec["recommended_training"]["stage"] == "sft"
    assert spec["recommended_training"]["finetuning_type"] == "lora"
    assert spec["ollama_plan"]["base_model"] == "qwen2.5:7b-instruct"
    assert spec["ollama_plan"]["automatic_import"] is False
    assert "ollama create" in spec["ollama_plan"]["manual_commands_after_export"][0]
    assert "ollama show" in spec["ollama_plan"]["manual_commands_after_export"][1]
    assert spec["acceptance_gate"]["required_before_studio_use"] is True
    assert any("Preview dataset" in check for check in spec["acceptance_gate"]["minimum_manual_checks"])
    assert "import Ollama automatico" in spec["acceptance_gate"]["reject_if"]
    assert spec["privacy_policy"]["tenant_id"] == "tenant-a"
    assert spec["privacy_policy"]["approved_pairs_only"] is True
    assert spec["privacy_policy"]["source_paths_exported"] is False
    assert spec["privacy_policy"]["external_upload_default"] is False
    assert spec["automation_policy"]["starts_llama_factory_training"] is False
    assert spec["automation_policy"]["starts_ollama_import"] is False
    assert spec["automation_policy"]["executes_shell_commands"] is False
    assert spec["safety"]["chain_of_thought_saved"] is False
    assert spec["safety"]["automatic_training"] is False
    assert spec["safety"]["automatic_ollama_import"] is False
    assert spec["sources"]["video"] == "https://www.youtube.com/watch?v=8T9epgWmaNI"

    with pytest.raises(ValueError):
        build_llama_factory_dataset_info_entry(
            dataset_name="iusentra_lex",
            file_name="dataset.exe",
            dataset_format="alpaca",
        )
    with pytest.raises(ValueError):
        build_llama_factory_dataset_info_entry(
            dataset_name="iusentra_lex",
            file_name="dataset.jsonl",
            dataset_format="unsupported",  # type: ignore[arg-type]
        )


def _document_ai_json(tmp_path):
    payload = {
        "documents": [
            {
                "id": "docai-1",
                "tenant_id": "tenant-a",
                "fascicolo_id": "fas-1",
                "original_filename": r"C:\studio\atti\diffida.pdf",
                "safe_filename": "diffida.pdf",
                "mime_type": "application/pdf",
                "sha256": "b" * 64,
                "status": "ready",
            },
            {
                "id": "docai-2",
                "tenant_id": "tenant-b",
                "fascicolo_id": "fas-2",
                "original_filename": "altro.pdf",
                "safe_filename": "altro.pdf",
                "mime_type": "application/pdf",
                "sha256": "c" * 64,
                "status": "ready",
            },
        ],
        "texts": [
            {
                "document_id": "docai-1",
                "version_id": "ver-1",
                "tenant_id": "tenant-a",
                "fascicolo_id": "fas-1",
                "text": (
                    "La diffida autorizzata riguarda la fattura insoluta e indica "
                    "che il debitore non ha pagato dopo il sollecito."
                ),
                "pages": [{"page_number": 1, "text": "La diffida autorizzata riguarda la fattura insoluta."}],
                "extraction_engine": "pdfplumber",
            },
            {
                "document_id": "docai-2",
                "version_id": "ver-2",
                "tenant_id": "tenant-b",
                "fascicolo_id": "fas-2",
                "text": "Documento di altro tenant da non leggere.",
                "pages": [],
                "extraction_engine": "pdfplumber",
            },
        ],
        "versions": [],
        "audit_events": [],
    }
    path = tmp_path / "documenti_ai.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_batch_carica_documenti_ai_tenant_aware_e_dry_run(tmp_path):
    source = _document_ai_json(tmp_path)
    documents = load_document_ai_json_documents(source, tenant_id="tenant-a", fascicolo_ids=["fas-1"])

    assert len(documents) == 1
    assert documents[0].tenant_id == "tenant-a"
    assert documents[0].fascicolo_id == "fas-1"
    assert documents[0].title == "diffida.pdf"
    assert documents[0].source_name == "diffida.pdf"
    assert "studio\\atti" not in documents[0].title
    assert documents[0].pages[0].page_number == 1

    result = build_studio_dataset_batch(
        documents,
        StudioDatasetBatchOptions(
            tenant_id="tenant-a",
            dry_run=True,
            chunking_options=ChunkingOptions(max_chars=220, overlap_chars=0, min_chars=20),
            qa_policy=QAGenerationPolicy(min_chunk_chars=20),
        ),
        output_dir=tmp_path / "out",
    )

    summary = result.summary()
    assert summary["documents_count"] == 1
    assert result.pipeline.manifest.documents[0].title == "diffida.pdf"
    assert summary["chunks_count"] == 1
    assert summary["qa_pairs_count"] == 1
    assert summary["dry_run"] is True
    assert summary["automatic_training"] is False
    assert not (tmp_path / "out").exists()


def test_batch_blocca_scrittura_chunk_sensibili_senza_flag(tmp_path):
    document = _document(
        text=(
            "Il cliente RSSMRA80A01H501U usa mario.rossi@example.com e telefono 3331234567. "
            "Il dato resta confinato al tenant fino ad autorizzazione."
        )
    )
    result = build_studio_dataset_batch(
        [document],
        StudioDatasetBatchOptions(
            tenant_id="tenant-a",
            dry_run=False,
            allow_sensitive_export=False,
            chunking_options=ChunkingOptions(max_chars=260, overlap_chars=0, min_chars=20),
            qa_policy=QAGenerationPolicy(min_chunk_chars=20),
        ),
        output_dir=tmp_path / "dataset",
    )

    assert (tmp_path / "dataset" / "manifest.json").exists()
    assert not (tmp_path / "dataset" / "chunks.jsonl").exists()
    assert result.sensitive_chunks_count == 1
    assert result.blocked_exports


def test_batch_scrive_export_candidate_solo_con_flag_espliciti(tmp_path):
    documents = load_document_ai_json_documents(_document_ai_json(tmp_path), tenant_id="tenant-a")
    result = build_studio_dataset_batch(
        documents,
        StudioDatasetBatchOptions(
            tenant_id="tenant-a",
            dry_run=False,
            allow_sensitive_export=True,
            include_pending_review_export=True,
            dataset_formats=("alpaca", "sharegpt"),
            chunking_options=ChunkingOptions(max_chars=220, overlap_chars=0, min_chars=20),
            qa_policy=QAGenerationPolicy(min_chunk_chars=20),
        ),
        output_dir=tmp_path / "dataset",
    )

    assert not result.blocked_exports
    assert (tmp_path / "dataset" / "chunks.jsonl").exists()
    assert (tmp_path / "dataset" / "qa_review_queue.json").exists()
    alpaca = (tmp_path / "dataset" / "alpaca.jsonl").read_text(encoding="utf-8")
    sharegpt = (tmp_path / "dataset" / "sharegpt.jsonl").read_text(encoding="utf-8")
    assert "pending_human_review" in alpaca
    assert '"from": "human"' in sharegpt
    assert "external_training" in alpaca


def test_cli_build_lex_studio_dataset_dry_run(tmp_path, capsys):
    source = _document_ai_json(tmp_path)
    exit_code = build_lex_studio_dataset_main(
        [
            "--tenant-id",
            "tenant-a",
            "--document-ai-json",
            str(source),
            "--fascicolo-id",
            "fas-1",
            "--max-chars",
            "220",
            "--overlap-chars",
            "0",
            "--min-qa-chars",
            "20",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    summary = json.loads(captured.out)
    assert summary["tenant_id"] == "tenant-a"
    assert summary["dry_run"] is True
    assert summary["documents_count"] == 1
    assert summary["human_review_required"] is True
