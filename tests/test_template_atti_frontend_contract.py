from __future__ import annotations

import re
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


def test_editor_professionale_rimuove_flusso_rumore_e_placeholder_inglesi():
    source = (ROOT / "frontend/src/components/TemplateAttiPage.tsx").read_text(encoding="utf-8")

    assert 'className="iu-template-pro-flow"' not in source
    assert "iu-template-pro-page-boundary" not in source
    assert "iu-template-pro-page-marker" not in source
    assert "[NOME_STUDIO]" not in source
    assert "[INDIRIZZO_STUDIO]" not in source
    for token in (
        "[RECIPIENT_OR_COURT]",
        "[TITLE]",
        "[CLIENT_OR_SENDER]",
        "[COUNTERPARTY_OR_RECIPIENT]",
        "[FACTS]",
        "[REQUESTS_OR_CONCLUSIONS]",
        "[PLACE]",
        "[DOCUMENT_DATE]",
        "[LAWYER]",
    ):
        assert token not in source


def test_editor_professionale_placeholder_italiani_con_compatibilita_storica():
    source = (ROOT / "frontend/src/components/TemplateAttiPage.tsx").read_text(encoding="utf-8")

    assert "PLACEHOLDER_LABELS_IT" in source
    assert "recipient_or_court: 'DESTINATARIO_O_UFFICIO'" in source
    assert "title: 'TITOLO_ATTO'" in source
    assert "client_or_sender: 'CLIENTE_O_MITTENTE'" in source
    assert "requests_or_conclusions: 'RICHIESTE_E_CONCLUSIONI'" in source
    assert "function legacyPlaceholderName" in source
    assert "function placeholderTokens" in source
    assert "localiseDraftPlaceholderTokens" in source
    assert "placeholderTokens(field).forEach" in source
    assert "fields.flatMap(placeholderTokens)" in source
    assert "ACCORDO TRANSATTIVO" in source
    assert "ATTO DI APPELLO" in source
    assert "APPELLO CAUTELARE" in source
    assert "ATTESTAZIONE DI CONFORMITA E RELATA DI NOTIFICA" in source
    assert "MEMORIA O ISTANZA PENALE" in source
    assert "INVITO ALLA MEDIAZIONE" in source


def test_editor_professionale_font_size_solo_su_selezione():
    source = (ROOT / "frontend/src/components/TemplateAttiPage.tsx").read_text(encoding="utf-8")
    font_body = re.search(r"const applyFontSelection = \(fontKey: string\) => \{(?P<body>.*?)\n  \}", source, re.S)
    size_body = re.search(r"const applySizeSelection = \(size: number\) => \{(?P<body>.*?)\n  \}", source, re.S)

    assert font_body
    assert size_body
    assert "setDocumentFont(fontKey)" not in font_body.group("body")
    assert "onBodyFontSizeChange(size)" not in size_body.group("body")
    assert "Seleziona il testo da modificare, poi scegli il font." in source
    assert "Seleziona il testo da modificare, poi scegli la dimensione." in source
    assert "FONT_SIZE_OPTIONS = [4, 5, 6, 7, 8" in source
    assert "24, 26, 28]" in source


def test_editor_professionale_pagine_stampa_margini_orientamento():
    source = (ROOT / "frontend/src/components/TemplateAttiPage.tsx").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/components/TemplateAttiPage.css").read_text(encoding="utf-8")
    data = (ROOT / "frontend/src/templateAttiData.ts").read_text(encoding="utf-8")
    editor_dir = ROOT / "frontend/src/components/templateEditor"
    geometry = (editor_dir / "pageGeometry.ts").read_text(encoding="utf-8")
    pagination = (editor_dir / "pagination.ts").read_text(encoding="utf-8")
    canvas = (editor_dir / "PagedDocumentCanvas.tsx").read_text(encoding="utf-8")
    artifacts = (editor_dir / "editorArtifacts.ts").read_text(encoding="utf-8")
    editor_styles = (editor_dir / "templateEditor.css").read_text(encoding="utf-8")

    # Pagina fisica A4 in millimetri reali: su mobile si scala, non si restringe.
    assert "CSS_PX_PER_MM = 96 / 25.4" in geometry
    assert "orientation === 'orizzontale' ? { width: 297, height: 210 } : { width: 210, height: 297 }" in geometry
    assert "export function fitWidthZoom" in geometry
    assert "transform: scale(var(--iu-ted-zoom, 1));" in editor_styles
    assert "iu-template-pro-paper {" not in styles
    assert "padding: 5.4rem 1.1rem 2rem;" not in styles

    # Impaginazione: righe e blocchi mai nei margini, nell'intestazione o tra i fogli.
    assert "writableTop(page, metrics)" in pagination
    assert "writableBottom(page, metrics)" in pagination
    assert "function insertLineSpacer" in pagination
    assert "Riga orfana" in pagination and "Riga vedova" in pagination
    assert "Il titolo non resta da solo in fondo alla pagina" in pagination
    assert "effectiveTop(unit, frame)" in pagination
    assert "layoutCache" in pagination
    assert "clearPaginationArtifacts" in artifacts
    assert "cleanEditorHtml" in artifacts
    assert "stripLeadingStampBlocks" in artifacts
    assert "PAGE_BREAK_ATTR = 'data-iu-page-break'" in artifacts
    assert "display: inline-block;" in editor_styles and "width: 100%;" in editor_styles
    assert "[data-iu-page-push]::before" in editor_styles
    assert "overflow-anchor: none;" in editor_styles

    # Timbro ripetuto su ogni foglio, testo sotto il timbro, stampa fedele.
    assert "data-iu-sheet-index" in canvas
    assert "iu-ted-stamp--copy" in canvas
    assert "headerReservePx" in canvas
    assert "beforeprint" in canvas and "afterprint" in canvas
    assert "@page { size: A4" in canvas
    assert "flushSync(() => setPrinting(true))" in canvas
    assert "deleteContentBackward" in canvas
    assert "sanitizePastedHtml" in canvas
    assert "@media print" in editor_styles
    assert "--iu-ted-stamp-font-size" in editor_styles
    assert "--iu-ted-stamp-line-height" in editor_styles
    assert "window.print()" in source
    assert "PagedDocumentCanvas" in source
    assert "pageOrientation" in source
    assert "pageMargins" in source
    assert "Verticale" in source and "Orizzontale" in source
    assert "stamp_anchor: 'page_margin'" in source
    assert "iu-template-pro-margin-grid" in styles
    assert "pageOrientation?: string" in data


def test_editor_professionale_pannelli_collassabili_e_timbro_uniforme():
    source = (ROOT / "frontend/src/components/TemplateAttiPage.tsx").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/components/TemplateAttiPage.css").read_text(encoding="utf-8")
    data = (ROOT / "frontend/src/templateAttiData.ts").read_text(encoding="utf-8")
    backend = (ROOT / "pct/template_atti.py").read_text(encoding="utf-8")

    assert "catalogCollapsed" in source
    assert "fieldsCollapsed" in source
    assert "iu-template-pro-layout--catalog-collapsed" in source
    assert "iu-template-pro-layout--fields-collapsed" in source
    assert "Apri catalogo template" in source
    assert "Chiudi pannello editor" in source
    assert "stampFontSize" in source
    assert "stampLineHeight" in source
    assert "Dimensione timbro impostata" in source
    assert "Font timbro applicato a tutte le righe" in source
    toolbar = (ROOT / "frontend/src/components/templateEditor/DocumentToolbar.tsx").read_text(encoding="utf-8")
    assert "useSelectionFormats(editorRef)" in source
    assert "setTextAlign(align)" in source
    assert "aria-pressed={tool.active === undefined ? undefined : Boolean(tool.active)}" in toolbar
    assert "className={tool.active ? 'is-active' : ''}" in toolbar
    assert "placeholdersActive={activeTab === 'Campi' && !fieldsCollapsed}" in source
    assert "Stile paragrafo" in toolbar and "Interruzione di pagina" in toolbar
    assert "iu-template-pro-sidebar.is-collapsed" in styles
    assert "iu-template-pro-fields.is-collapsed" in styles
    assert ".iu-template-pro-editor .iu-template-pro-list .iu-template-pro-card" in styles
    assert "min-height: 5.55rem;" in styles
    assert "row-gap: .22rem;" in styles
    assert '.iu-template-pro-toolbar button[aria-pressed="true"]' in styles
    assert "iu-template-pro-stamp-metrics" in styles
    assert "stampFontSize?: number" in data
    assert "stampFontSize: 8" in data
    assert '"stamp_font_size_pt": 8' in backend


def test_editor_libero_ha_route_link_e_payload_dedicato():
    source = (ROOT / "frontend/src/components/TemplateAttiPage.tsx").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/components/TemplateAttiPage.css").read_text(encoding="utf-8")
    data = (ROOT / "frontend/src/templateAttiData.ts").read_text(encoding="utf-8")
    backend = (ROOT / "web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
    routes = (ROOT / "web/blueprints/template_atti.py").read_text(encoding="utf-8")

    assert "FREE_EDITOR_URL = '/template-atti/editor'" in source
    assert "Editor libero" in source
    assert "const freeEditorMode = isFreeEditorRoute()" in source
    assert "freeEditorMode ? '' : current" in source
    assert "freeEditorMode && (item.code || '').trim()" in source
    assert "buildFreeEditorFallbackPage" in data
    assert "const freeEditorRoute = route === '/template-atti/editor'" in data
    assert "freeEditorRoute ? buildFreeEditorFallbackPage()" in data
    assert "timeoutSignal(10000)" in data
    assert "Documento libero" in source
    assert "Foglio indipendente dai modelli" in source
    assert "Scrivi qui il documento libero" in source
    assert "showTemplateFields ? fieldGroups.map" in source
    editor_styles = (ROOT / "frontend/src/components/templateEditor/templateEditor.css").read_text(encoding="utf-8")
    assert ".iu-ted-body[data-placeholder]:empty::before" in editor_styles
    assert ".iu-ted-body[data-placeholder]:has(> p:only-child > br:only-child)::before" in editor_styles
    assert ".iu-template-pro-free-editor-note" in styles
    assert "editor_libero" in data
    assert "Documento libero" in backend
    assert "@template_atti.route(\"/editor\"" in routes
    assert "render_react_shell_response(request.path.lstrip(\"/\"))" in routes
    assert '"/template-atti/editor", "/template-atti/editor-libero"' in (
        ROOT / "web/blueprints/react_shell.py"
    ).read_text(encoding="utf-8")
    assert '"/template-atti/editor": "/app-v2/template-atti/editor"' in (
        ROOT / "web/services/app_v2_routing.py"
    ).read_text(encoding="utf-8")


def test_catalogo_laterale_usa_catalogo_compilatore_se_archivio_vuoto():
    backend = (ROOT / "web/blueprints/api_v1_react.py").read_text(encoding="utf-8")

    assert "catalogo_compilatore" in backend
    assert "BASE_REQUIRED_FIELDS" in backend
    assert "HIDDEN_BASE_FIELDS" in backend
    assert "compiler_category" in backend
    assert "required_extra_fields" in backend
