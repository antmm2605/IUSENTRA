from pathlib import Path


FRONTEND = Path("frontend/src")


def test_documenti_ai_non_compare_nella_navigazione_standard_fascicolo():
    fascicoli = (FRONTEND / "components" / "FascicoliPage.tsx").read_text(encoding="utf-8")

    assert "DocumentiAIPage" not in fascicoli
    assert 'id="documenti-ai"' not in fascicoli
    assert 'href="#documenti-ai"' not in fascicoli
    assert "/documenti-ai" not in fascicoli


def test_indicizzazione_lex_integrata_nei_documenti_fascicolo():
    fascicoli = (FRONTEND / "components" / "FascicoliPage.tsx").read_text(encoding="utf-8")
    data = (FRONTEND / "fascicoliData.ts").read_text(encoding="utf-8")
    bridge = Path("web/services/react_fascicoli_bridge.py").read_text(encoding="utf-8")

    assert "Indicizzazione Lex" in fascicoli
    assert "Lex può leggere i documenti del fascicolo." in fascicoli
    assert "Alcuni documenti sono in indicizzazione. Lex li userà appena pronti." in fascicoli
    assert "Alcuni documenti non sono stati indicizzati." in fascicoli
    assert "Aggiorna indice" in fascicoli
    assert "Riprova errori" in fascicoli
    assert "lexIndexing" in data
    assert '"lex_indexing"' in bridge


def test_documenti_ai_upload_non_e_cta_standard():
    fascicoli = (FRONTEND / "components" / "FascicoliPage.tsx").read_text(encoding="utf-8")

    assert "uploadDocumentAI" not in fascicoli
    assert "documenti-ai/upload" not in fascicoli
