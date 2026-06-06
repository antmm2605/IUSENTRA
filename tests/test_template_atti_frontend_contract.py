from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_compilatore_naviga_a_editor_url_e_conferma_warning():
    source = (ROOT / "frontend/src/components/TemplateAttiPage.tsx").read_text(encoding="utf-8")
    assert "result.editor_url" in source
    assert "window.location.assign(editorUrl)" in source
    assert "confirmed_warning" in source
    assert "window.confirm" in source
    assert "overallState" in source


def test_frontend_mostra_card_conformita_complete():
    source = (ROOT / "frontend/src/components/TemplateAttiPage.tsx").read_text(encoding="utf-8")
    for component in (
        "ComplianceStatusCard",
        "NormativeReferencesCard",
        "LayoutProfileCard",
        "StudioStampCard",
        "MissingFieldsCard",
        "MissingDocumentsCard",
        "ReliabilityScoreCard",
        "LexActionCard",
    ):
        assert component in source
    assert "reasonForApplication" in source
    assert "verificationStatus" in source
    assert "coverageRole" in source
    assert "sourceRoleLabel" in source
    assert "officialTemplateSources" in source
    assert "Fonte specifica" in source
    assert "Fonte secondaria collegata" in source
    assert "Presidio deontologico" in source
    assert "Apri fonte ufficiale" in source


def test_compilatore_react_espone_fonti_modello_stabili():
    frontend_data = (ROOT / "frontend/src/templateAttiData.ts").read_text(encoding="utf-8")
    frontend_page = (ROOT / "frontend/src/components/TemplateAttiPage.tsx").read_text(encoding="utf-8")
    backend = (ROOT / "web/blueprints/api_v1_react.py").read_text(encoding="utf-8")

    assert "officialTemplateSources" in backend
    assert "officialTemplateSources" in frontend_data
    assert "officialTemplateSources" in frontend_page
