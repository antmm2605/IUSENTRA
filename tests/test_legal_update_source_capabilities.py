from __future__ import annotations

from pathlib import Path

from pct.legal_context_questions import generate_context_questions
from pct.legal_reference_extractor import extract_references
from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS, build_legal_update_pipeline
from pct.legal_update_source_capabilities import (
    capability_required_source_codes,
    get_source_capability,
    source_exclusion_reason,
)


def test_capability_registry_copre_fonti_catalogo_e_secondarie():
    expected = {str(row["code"]) for row in DEFAULT_SOURCE_ROWS}
    expected.update(
        {
            "studiocataldi_codice_civile",
            "avvocatoandreani_codice_procedura_civile",
            "studiocataldi_codice_penale",
            "avvocatoandreani_codice_strada",
        }
    )

    missing = expected - capability_required_source_codes()

    assert missing == set()
    for code in expected:
        capability = get_source_capability(code)
        assert capability.source_code == code
        assert capability.item_strategy
        assert capability.detail_strategy
        assert capability.attachment_strategy
        assert capability.publication_destination
        assert capability.rag_destination
        assert capability.relevance_policy
        assert capability.exclusion_policy


def test_capability_filtri_scartano_noise_e_tengono_contesto_legale():
    agcom = {"code": "agcom_provvedimenti", "source_type": "web", "parser_type": "html", "category": "prassi"}
    openga = {"code": "openga_sentenze", "source_type": "open_data", "parser_type": "ckan_json", "category": "giurisprudenza"}
    pst = {"code": "pst_giustizia_download", "source_type": "web", "parser_type": "html", "category": "telematico"}
    secondary = {"code": "studiocataldi_codice_civile", "source_type": "web", "parser_type": "html", "category": "normativa"}

    assert "Consultazione" in source_exclusion_reason(
        agcom,
        title="02 Assoradio",
        body_text="Contributo alla consultazione pubblica AGCOM sulla pianificazione frequenze DAB+.",
    )
    assert source_exclusion_reason(
        agcom,
        title="Delibera AGCOM n. 123/26/CONS",
        body_text="Procedimento sanzionatorio, tutela utenti e obblighi regolamentari.",
    ) == ""
    assert "Atto contabile" in source_exclusion_reason(
        openga,
        title="Liquidazione fattura fornitore",
        body_text="Mandato di pagamento e DURC senza gara o contenzioso.",
    )
    assert source_exclusion_reason(
        openga,
        title="Sentenza TAR Lazio n. 1234/2026",
        body_text="Ricorso in materia di appalti e affidamento.",
    ) == ""
    assert source_exclusion_reason(
        pst,
        title="Manuale deposito telematico",
        body_text="Specifiche PCT e schema busta deposito telematico.",
    ) == ""
    assert "Fonte secondaria" in source_exclusion_reason(secondary, title="Art. 2043 codice civile", body_text="")


def test_reference_extractor_espone_schema_dedicato_senza_link_inventati():
    refs = extract_references(
        (
            "Sentenza Cassazione n. 11417 del 27/04/2026: richiamati art. 606 c.p.p., "
            "art. 2946 c.c., D.Lgs. 150/2022, Regolamento UE 2016/679 e R.G. 9926/2026."
        ),
        source_url="https://www.cortedicassazione.it/it/penale_dettaglio.page?contentId=SZP1",
        attachment_url="https://www.cortedicassazione.it/doc.pdf",
    )

    assert any(row["reference_type"] == "article" and "art. 606 c.p.p." in row["normalized_text"] for row in refs)
    assert any(row["reference_type"] == "act" and "D.Lgs." in row["normalized_text"] for row in refs)
    assert any(row["reference_type"] == "eu_act" for row in refs)
    assert any(row["reference_type"] == "rg" and "9926/2026" in row["normalized_text"] for row in refs)
    assert all(row["source_url"].startswith("https://www.cortedicassazione.it") for row in refs)
    assert all(row["attachment_url"].endswith("doc.pdf") for row in refs)
    assert all(row["official_url"] == "" for row in refs)
    assert all(row["raw_text"] and row["snippet"] and row["confidence"] > 0 for row in refs)


def test_context_questions_generano_domande_da_avvocato_con_ragione():
    refs = [
        {"reference_type": "article", "normalized_text": "art. 606 c.p.p."},
        {"reference_type": "rg", "normalized_text": "R.G. 9926/2026"},
    ]

    questions = generate_context_questions(
        source_code="cassazione_ultime_sent_ord_questioni",
        title="Questione Penale Pendente del ricorso R.G. 9926/2026",
        body="Scheda ufficiale Cassazione.",
        pdf_text="PDF OCR con art. 606 c.p.p.",
        references=refs,
        classification="giurisprudenza",
        attachment_url="https://www.cortedicassazione.it/qsp.pdf",
        has_rg_discrepancy=True,
    )

    assert any(row["type"] == "pdf_allegato" for row in questions)
    assert any(row["type"] == "articoli_pdf" for row in questions)
    assert any(row["type"] == "discrepanza_rg" for row in questions)
    assert all(row["question"] and row["reason"] and row["source"] for row in questions)


def test_pipeline_chiude_catalogo_openga_ma_non_perde_documento_giuridico(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("openga_sentenze")
    assert source is not None

    def fake_analyze(normalized, source_row, **_kwargs):
        title = str(normalized.get("title") or "")
        if "Sentenza TAR" in title:
            return {
                "classification_type": "GIURISPRUDENZA",
                "confidence_score": 0.93,
                "impact_level": "medio",
                "court_name": "TAR Lazio",
                "decision_number": "1234",
                "decision_year": "2026",
                "decision_date": "2026-05-12",
                "summary_short": "Sentenza TAR in materia di appalti.",
                "summary_long": "Sentenza TAR in materia di appalti.",
                "what_changes": "Documento giurisprudenziale concreto.",
                "matter_slug": "appalti_contratti_pubblici",
            }
        return {
            "classification_type": "NEWS",
            "confidence_score": 0.7,
            "impact_level": "basso",
            "summary_short": "Dataset tecnico.",
            "summary_long": "Dataset tecnico.",
            "what_changes": "Catalogo open data.",
            "matter_slug": "diritto_amministrativo",
        }

    monkeypatch.setattr("pct.legal_update_pipeline.analyze_document", fake_analyze)

    catalog = pipeline.process_document(
        source,
        {
            "external_id": "openga-catalogo",
            "source_url": "https://openga.giustizia-amministrativa.it/dataset/catalogo",
            "title": "Catalogo sentenze",
            "raw_text": "Dataset OpenGA in formato CSV senza documento giuridico concreto.",
            "content_hash": "hash-catalogo",
            "fetch_status": "fetched",
            "http_status": 200,
        },
    )
    document = pipeline.process_document(
        source,
        {
            "external_id": "openga-sentenza-tar",
            "source_url": "https://openga.giustizia-amministrativa.it/sentenza.pdf",
            "title": "Sentenza TAR Lazio n. 1234/2026",
            "raw_text": "Sentenza TAR Lazio n. 1234/2026 su ricorso in materia di appalti.",
            "content_hash": "hash-sentenza",
            "fetch_status": "fetched",
            "http_status": 200,
        },
    )

    assert catalog["review"]["status"] == "closed"
    assert catalog["review"]["proposed_action"] == "OUT_OF_SCOPE"
    assert document["review"]["proposed_action"] == "NEW_CASE_LAW"
    assert document["review"]["status"] in {"pending", "approved"}
