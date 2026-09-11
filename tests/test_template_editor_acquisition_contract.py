"""Contratti dell'editor atti: colori visibili, zoom a due dita e acquisizione in PDF.

Sono guardrail sul codice sorgente; non sostituiscono la prova con scanner, webcam
e telefono reali.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def source(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def test_campioni_colore_ed_evidenziatore_hanno_colore_e_non_sono_coperti_dal_preset():
    css = source("components/templateEditor/templateEditor.css")
    toolbar = source("components/templateEditor/DocumentToolbar.tsx")
    # I pulsanti della barra (sfondo bianco) e il preset globale (min 44px) coprivano il colore.
    assert ".iu-template-pro-toolbar .iu-ted-color__panel button {" in css
    assert "background: var(--iu-ted-swatch, #ffffff);" in css
    ids = re.findall(r"\{ id: '([a-z-]+)', label", toolbar)
    assert len(ids) == 13
    for swatch in ids:
        if swatch == "none":
            assert ".iu-template-pro-toolbar .iu-ted-color__panel button.iu-ted-swatch--none { background:" in css
        else:
            assert f".iu-template-pro-toolbar .iu-ted-color__panel button.iu-ted-swatch--{swatch} {{ --iu-ted-swatch: #" in css
    assert "@media (pointer: coarse)" in css and "grid-template-columns: repeat(4, 2.75rem);" in css
    assert '>Colore testo</span>' in toolbar and '>Evidenziatore</span>' in toolbar


def test_zoom_a_due_dita_sul_foglio_e_non_sull_intera_interfaccia():
    hook = source("components/templateEditor/usePinchZoom.ts")
    canvas = source("components/templateEditor/PagedDocumentCanvas.tsx")
    css = source("components/templateEditor/templateEditor.css")
    assert "usePinchZoom({ viewportRef, frameRef, zoomRef, onZoom: setManualZoom })" in canvas
    assert "addEventListener('touchmove', onTouchMove, { passive: false })" in hook
    assert "event.touches.length !== 2" in hook and "event.preventDefault()" in hook
    assert "!event.ctrlKey && !event.metaKey" in hook
    assert "gesturestart" in hook
    assert "clampZoom(startZoom * (currentDistance / startDistance))" in hook
    assert "touch-action: pan-x pan-y;" in css


def test_editor_apre_acquisizione_caricata_solo_su_richiesta():
    page = source("components/TemplateAttiPage.tsx")
    assert "lazy(() => import('./documentCapture/DocumentAcquisitionDialog'))" in page
    assert "setAcquisitionMounted(true); setAcquisitionOpen(true)" in page
    assert "Acquisisci\n" in page
    assert "matters={data.selectors.fascicoli}" in page
    assert "defaultMatterId={contextFascicoloId}" in page
    assert "insertEditorHtml(plainTextToParagraphs(paragraphs.join" in page
    # Regole del contratto React per TemplateAttiPage restano rispettate.
    for forbidden in ("style={{", "dangerouslySetInnerHTML"):
        assert forbidden not in page


def test_sorgenti_desktop_scanner_local_signer_e_webcam_mobile_fotocamera():
    dialog = source("components/documentCapture/DocumentAcquisitionDialog.tsx")
    sources = source("components/documentCapture/AcquisitionSources.tsx")
    assert "acquireFromLocalScanner()" in dialog
    assert "(pointer: coarse) and (hover: none)" in dialog
    assert "facingMode={mobile ? 'environment' : 'user'}" in dialog
    assert "source: 'scanner', title: 'Scanner del PC'" in sources
    assert "source: 'webcam', title: 'Webcam del PC'" in sources
    assert "source: 'fotocamera', title: 'Fotocamera del dispositivo'" in sources
    assert 'capture="environment"' in sources
    assert "artt. 15 e 16" in sources


def test_fotocamera_rileva_il_foglio_senza_audio_e_rilascia_le_tracce():
    camera = source("components/documentCapture/useCameraStream.ts")
    smart = source("components/documentCapture/SmartCamera.tsx")
    detection = source("components/documentCapture/useDocumentDetection.ts")
    assert "audio: false" in camera and "MediaRecorder" not in camera + smart
    assert "track.stop()" in camera and "visibilitychange" in camera
    assert "useDocumentDetection(video, camera.ready)" in smart
    assert '<polygon className={detection.stable ? \'is-stable\' : \'is-found\'}' in smart
    assert "window.clearTimeout(timer)" in detection


def test_pdf_a4_ocr_facoltativo_e_salvataggio_solo_dopo_conferma():
    session = source("components/documentCapture/useAcquisitionSession.ts")
    result = source("components/documentCapture/AcquisitionResult.tsx")
    processing = source("components/documentCapture/detection/pageProcessing.ts")
    ocr = source("services/documentOcr.ts")
    assert "generateDocument('multipage'" in session and "'a4')" in session
    assert "recognizeDocument(current, name" in session
    assert "saveGeneratedDocument(fascicoloId, current)" in session
    assert "disabled={busy || !matterId || !reviewed}" in result
    assert "Riconosci testo (OCR)" in result
    assert "PENAL_200_DPI: Size = { width: 1654, height: 2339 }" in processing
    assert "'/api/v1/ui/document-tools/ocr-page'" in ocr
    for name in ("AcquisitionResult.tsx", "DocumentAcquisitionDialog.tsx", "AcquisitionPages.tsx"):
        assert "download=" not in source(f"components/documentCapture/{name}")


def test_nuovi_moduli_rispettano_i_budget_e_la_governance_css():
    budgets = {
        "components/documentCapture/DocumentAcquisitionDialog.tsx": 250,
        "components/documentCapture/SmartCamera.tsx": 250,
        "components/documentCapture/CornerAdjust.tsx": 250,
        "components/documentCapture/AcquisitionSources.tsx": 250,
        "components/documentCapture/AcquisitionPages.tsx": 250,
        "components/documentCapture/AcquisitionResult.tsx": 250,
        "components/documentCapture/useAcquisitionSession.ts": 180,
        "components/documentCapture/useCameraStream.ts": 180,
        "components/documentCapture/useDocumentDetection.ts": 180,
        "components/templateEditor/usePinchZoom.ts": 180,
        "components/documentCapture/detection/documentQuad.ts": 250,
        "components/documentCapture/detection/quadRefine.ts": 250,
        "components/documentCapture/detection/perspective.ts": 250,
        "components/documentCapture/detection/enhance.ts": 250,
        "components/documentCapture/detection/grayImage.ts": 250,
        "components/documentCapture/detection/pageProcessing.ts": 250,
        "services/documentOcr.ts": 250,
    }
    for path, limit in budgets.items():
        text = source(path)
        assert len(text.splitlines()) <= limit, path
        assert "style={{" not in text, path
    governance = json.loads((ROOT / "scripts/react-migration/design-system-governance.json").read_text(encoding="utf-8"))
    assert "frontend/src/components/documentCapture/acquisition.css" in governance["approvedCssFiles"]
    assert (ROOT / "web/services/document_ocr.py").read_text(encoding="utf-8").count("\n") <= 500
