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
