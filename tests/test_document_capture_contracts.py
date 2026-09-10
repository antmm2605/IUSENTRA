"""Guardrail di collegamento UI; non attestano acquisizione da hardware reale."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / "frontend/src" / path).read_text(encoding="utf-8")


def test_pdf_originale_fullscreen_e_zoom_non_rimontano_i_campi():
    pdf = source("components/mediazione/PdfModulo.tsx")
    css = source("components/mediazione/mediazione.css")
    assert "Apri il modulo a tutto schermo" in pdf
    assert "Torna alla vista normale del modulo" in pdf
    assert "aria-pressed={expanded}" in pdf
    assert "requestFullscreen()" in pdf and "fullscreenchange" in pdf
    assert "event.key === 'Escape'" in pdf
    assert "focus({ preventScroll: true })" in pdf
    assert "setZoom(Math.max(50, zoom - 25))" in pdf
    assert "setZoom(Math.min(200, zoom + 25))" in pdf
    assert "width: `${8 * zoom}px`" in pdf
    toggle = pdf.split("const toggleExpanded =", 1)[1].split("useEffect", 1)[0]
    assert "setValues" not in toggle and "setPage" not in toggle
    assert "height: 100dvh" in css and "container-type: inline-size" in css
    assert "min-width: 850px" not in css


def test_acquisizione_richiede_anteprima_conferma_e_id_fascicolo_attuale():
    capture = source("components/documentCapture/DocumentCapture.tsx")
    page = source("components/FascicoliPage.tsx")
    assert 'key={data.fascicolo.id} fascicoloId={data.fascicolo.id}' in page
    upload_workspace = page.split('function DocumentUploadWorkspace', 1)[1].split('function documentCatalogMethodLabel', 1)[0]
    assert upload_workspace.index("<DocumentCapture") < upload_workspace.index('<form className={`iu-fas-doc-upload')
    assert "Scanner / webcam / fotocamera" in capture
    assert "Acquisizione da dispositivo" in capture
    assert "if (!result || !reviewed) return" in capture
    assert "saveGeneratedDocument(fascicoloId, result)" in capture
    assert 'title="Anteprima del PDF da salvare nel fascicolo"' in capture
    assert 'disabled={!reviewed || Boolean(busy)}' in capture
    assert 'capture="environment"' in capture
    assert "beforeunload" in capture and "revokeObjectURL" in capture
    assert "location.reload" not in capture and "download=" not in capture


def test_fotocamera_non_registra_audio_e_spegne_le_tracce():
    camera = source("components/documentCapture/CaptureCamera.tsx")
    assert "audio: false" in camera
    assert "MediaRecorder" not in camera
    assert "track.stop()" in camera
    assert "if (!current)" in camera
    assert "visibilitychange" in camera and "!details.open" in camera
    assert "NotAllowedError" in camera and "NotFoundError" in camera
