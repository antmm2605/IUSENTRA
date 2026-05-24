from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO_ROOT / "artifacts" / "notifiche-legali"
DEFAULT_INPUT = ARTIFACT_DIR / "notifiche-legali-ui-demo-report.json"
DEFAULT_SCREENSHOTS = ARTIFACT_DIR / "ui-demo-screenshots"
DEFAULT_OUTPUT = ARTIFACT_DIR / "notifiche-legali-guida-avvocato-screenshot.pdf"


def _register_unicode_fonts() -> tuple[str, str]:
    regular_candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ]
    bold_candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    regular = next((path for path in regular_candidates if path.exists()), None)
    bold = next((path for path in bold_candidates if path.exists()), None)
    if regular:
        pdfmetrics.registerFont(TTFont("IusentraUnicode", str(regular)))
    if bold:
        pdfmetrics.registerFont(TTFont("IusentraUnicodeBold", str(bold)))
    return ("IusentraUnicode" if regular else "Helvetica", "IusentraUnicodeBold" if bold else "Helvetica-Bold")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Report UI non trovato: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_datetime(value: str | None) -> str:
    if not value:
        return datetime.now().strftime("%d/%m/%Y %H:%M")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%d/%m/%Y %H:%M")


def _para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _image(path: Path, max_width: float, max_height: float) -> Image:
    reader = ImageReader(str(path))
    width, height = reader.getSize()
    scale = min(max_width / width, max_height / height, 1.0)
    return Image(str(path), width=width * scale, height=height * scale)


def _status_table(report: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    checks = report.get("checks", [])
    rows: list[list[Any]] = [[_para("Esito", styles["TableHead"]), _para("Verifica", styles["TableHead"]), _para("Dettaglio", styles["TableHead"])]]
    for check in checks:
        rows.append(
            [
                _para("OK" if check.get("ok") else "KO", styles["TableText"]),
                _para(str(check.get("name", "")), styles["TableText"]),
                _para(str(check.get("detail", "")), styles["TableText"]),
            ]
        )
    table = Table(rows, colWidths=[18 * mm, 54 * mm, 112 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173a67")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fbfcfe")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8dee9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _build_story(report: dict[str, Any], screenshots_dir: Path) -> list[Any]:
    base = getSampleStyleSheet()
    regular_font, bold_font = _register_unicode_fonts()
    styles: dict[str, ParagraphStyle] = {
        "Title": ParagraphStyle(
            "GuideTitle",
            parent=base["Title"],
            fontName=bold_font,
            fontSize=24,
            leading=28,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#173a67"),
            spaceAfter=12,
        ),
        "Subtitle": ParagraphStyle(
            "GuideSubtitle",
            parent=base["BodyText"],
            fontName=regular_font,
            fontSize=10.5,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#526173"),
            spaceAfter=16,
        ),
        "Heading": ParagraphStyle(
            "GuideHeading",
            parent=base["Heading2"],
            fontName=bold_font,
            fontSize=14,
            leading=17,
            textColor=colors.HexColor("#173a67"),
            spaceBefore=8,
            spaceAfter=6,
        ),
        "Body": ParagraphStyle("GuideBody", parent=base["BodyText"], fontName=regular_font, fontSize=10, leading=13.5, spaceAfter=7),
        "Small": ParagraphStyle("GuideSmall", parent=base["BodyText"], fontName=regular_font, fontSize=8.2, leading=10.5, textColor=colors.HexColor("#526173")),
        "TableHead": ParagraphStyle("GuideTableHead", parent=base["BodyText"], fontName=bold_font, fontSize=8, leading=10, textColor=colors.white),
        "TableText": ParagraphStyle("GuideTableText", parent=base["BodyText"], fontName=regular_font, fontSize=7.5, leading=9.2),
    }

    generated = _fmt_datetime(report.get("generatedAt"))
    summary = report.get("summary", {})
    story: list[Any] = [
        Spacer(1, 24),
        _para("Guida operativa Relata notifica", styles["Title"]),
        _para("Demo verificata con schermate reali del software IUSENTRA", styles["Subtitle"]),
        _para(
            "Questa guida documenta il comportamento corretto: la notifica del provvedimento parte dalla PEC dell'ufficio giudiziario, non dai documenti già presenti nel fascicolo. L'avvocato viene avvisato, apre il Portale Servizi già compilato, scarica il singolo provvedimento indicato e lo collega ai Documenti e atti senza duplicazioni.",
            styles["Body"],
        ),
        _para(f"Generata il {generated}. Ambiente demo isolato, nessun invio PEC reale e nessun accesso automatico con credenziali dell'avvocato.", styles["Small"]),
        Spacer(1, 8),
        _para(
            f"Esito demo: {summary.get('passed', 0)}/{summary.get('total', 0)} verifiche superate.",
            styles["Heading"],
        ),
        _status_table(report, styles),
        PageBreak(),
    ]

    steps = report.get("steps", [])
    if not steps:
        story.append(_para("Nessuna schermata registrata nel report UI.", styles["Body"]))
        return story

    for index, step in enumerate(steps, start=1):
        screenshot = screenshots_dir / str(step.get("screenshot", ""))
        story.append(_para(f"{index}. {step.get('title', 'Passaggio')}", styles["Heading"]))
        story.append(_para(str(step.get("description", "")), styles["Body"]))
        if step.get("lawyerAction"):
            story.append(_para(f"Azione dell'avvocato: {step['lawyerAction']}", styles["Body"]))
        if step.get("systemCheck"):
            story.append(_para(f"Controllo del software: {step['systemCheck']}", styles["Body"]))
        if screenshot.exists():
            story.append(Spacer(1, 5))
            story.append(KeepTogether([_image(screenshot, 184 * mm, 150 * mm), Spacer(1, 4), _para(f"Schermata reale: {screenshot.name}", styles["Small"])]))
        else:
            story.append(_para(f"Schermata non trovata: {screenshot}", styles["Small"]))
        if index != len(steps):
            story.append(PageBreak())

    story.extend(
        [
            PageBreak(),
            _para("Chiusura operativa", styles["Heading"]),
            _para(
                "Il flusso è considerato pronto quando la PEC dell'ufficio è stata rilevata, il link al portale è compilato con fascicolo, R.G., ufficio e documento, il download riguarda un solo provvedimento, il documento viene collegato ai Documenti e atti e la relata viene generata solo dopo questa acquisizione.",
                styles["Body"],
            ),
            _para(
                "La guida può essere usata dall'avvocato come promemoria digitale: mostra dove leggere l'avviso, quale pulsante usare, cosa controllare nel portale e come evitare duplicati nel fascicolo.",
                styles["Body"],
            ),
        ]
    )
    return story


def build_pdf(input_json: Path, screenshots_dir: Path, output_pdf: Path) -> dict[str, Any]:
    report = _load_json(input_json)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Guida operativa Relata notifica",
        author="IUSENTRA",
    )
    doc.build(_build_story(report, screenshots_dir))
    return {
        "ok": output_pdf.exists() and output_pdf.stat().st_size > 0,
        "pdf": str(output_pdf),
        "size": output_pdf.stat().st_size if output_pdf.exists() else 0,
        "screenshots": len(report.get("steps", [])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera la guida PDF con screenshot reali della demo Relata notifica.")
    parser.add_argument("--input-json", default=str(DEFAULT_INPUT))
    parser.add_argument("--screenshots", default=str(DEFAULT_SCREENSHOTS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    result = build_pdf(Path(args.input_json), Path(args.screenshots), Path(args.output))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
