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
