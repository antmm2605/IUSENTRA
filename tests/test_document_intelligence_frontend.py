from pathlib import Path

FRONTEND = Path("frontend/src")


def test_documenti_ai_frontend_componenti_e_contratti():
    page = (FRONTEND / "components" / "DocumentiAIPage.tsx").read_text(encoding="utf-8")
    data = (FRONTEND / "documentiAiData.ts").read_text(encoding="utf-8")
    fascicoli = (FRONTEND / "components" / "FascicoliPage.tsx").read_text(encoding="utf-8")
    fascicoli_data = (FRONTEND / "fascicoliData.ts").read_text(encoding="utf-8")

    assert "Documenti AI" in page
    assert "react_operational_partial" in page
    assert "/api/v1/ui/fascicoli/" in data
    assert "mock_fallback: false" in data
    assert "DocumentAIFileType = 'pdf' | 'docx' | 'doc' | 'txt' | 'eml'" in data
    assert "DocumentiAIPage" not in fascicoli
    assert 'id="documenti-ai"' not in fascicoli
    assert 'href="#documenti-ai"' not in fascicoli
    assert "Indicizzazione Lex" in fascicoli
    assert "Lex può leggere i documenti del fascicolo." in fascicoli
    assert 'context="fascicolo-dettaglio"' in fascicoli
    assert 'context="fascicolo-quadro"' in fascicoli
    assert 'contextType="case"' in fascicoli
    assert "caseId={f.id || id}" in fascicoli
    assert "activeContext={{ context_type: 'case', case_id: f.id || id, client_id: clientId }}" in fascicoli
    assert "Documenti da verificare" in fascicoli
    assert "lexIndexing" in fascicoli_data
    assert "warnings: string[]" in fascicoli_data


def test_documenti_ai_frontend_senza_href_placeholder():
    files = [
        "DocumentiAIPage.tsx",
        "DocumentUploadPanel.tsx",
        "DocumentListPanel.tsx",
        "DocumentDetailPanel.tsx",
        "DocumentTextPanel.tsx",
        "DocumentSearchPanel.tsx",
        "DocumentAIEmptyState.tsx",
    ]
    for filename in files:
        source = (FRONTEND / "components" / filename).read_text(encoding="utf-8")
        assert 'href="#"' not in source


def test_documenti_ai_upload_accetta_txt_ed_eml():
    upload = (FRONTEND / "components" / "DocumentUploadPanel.tsx").read_text(encoding="utf-8")

    assert ".txt" in upload
    assert ".eml" in upload
    assert "TXT, EML" in upload


def test_catalogo_fascicolo_mostra_prova_del_contenuto_e_mantiene_il_lettore_interno():
    fascicoli = (FRONTEND / "components" / "FascicoliPage.tsx").read_text(encoding="utf-8")

    assert "function CatalogEvidenceDisclosure" in fascicoli
    assert "Prova e fonti della catalogazione" in fascicoli
    assert "Segnalazioni procedurali" in fascicoli
    assert "Fonti ufficiali del profilo" in fascicoli
    assert "Apri la prova nel lettore" in fascicoli
    assert "catalogProfileLabel(assignment)" in fascicoli
    assert "assignment.profile_id}" not in fascicoli


def test_catalogo_fascicolo_richiede_la_lettura_della_prova_prima_della_conferma():
    fascicoli = (FRONTEND / "components" / "FascicoliPage.tsx").read_text(encoding="utf-8")

    assert "reviewedEvidenceDocumentIds" in fascicoli
    assert "Prima apri “Prova e fonti”" in fascicoli
    assert "evidence_acknowledged: evidenceAcknowledged" in fascicoli
    assert "disabled={busy || !evidenceReviewed}" in fascicoli
    assert "confirm(item.document_id, 'confirmed', true)" in fascicoli


def test_correzione_catalogo_normalizza_la_natura_automatica_in_un_valore_salvabile():
    fascicoli = (FRONTEND / "components" / "FascicoliPage.tsx").read_text(encoding="utf-8")

    assert "catalogNatureForManualCorrection" in fascicoli
    assert "document_nature: catalogNatureForManualCorrection(assignment.document_nature)" in fascicoli
    assert "return 'atto_processuale'" in fascicoli


def test_catalogo_fascicolo_non_comprime_il_titolo_per_fare_spazio_alle_azioni():
    styles = (FRONTEND / "components" / "FascicoliPage.css").read_text(encoding="utf-8")
    catalog_row_rule = styles.split(".iu-fas-catalog__row{", 1)[1].split("}", 1)[0]

    assert ".iu-fas-catalog__row{display:grid;grid-template-columns:24px minmax(0,1fr)" in styles
    assert ".iu-fas-catalog__badges,.iu-fas-catalog__actions{grid-column:2;" in styles
    assert "auto auto" not in catalog_row_rule
