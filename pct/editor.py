"""
pct/editor.py — Conversione documenti per l'editor web.

Funzionalità:
  - docx_to_html()  : .docx → HTML con mammoth (fedele ai formati Word)
  - html_to_docx()  : HTML → .docx con python-docx + lxml
  - html_to_pdf()   : HTML → PDF con xhtml2pdf
  - txt_to_html()   : .txt → HTML semplice

Tutte le funzioni lavorano su bytes già decifrati.
Le dipendenze (mammoth, python-docx, xhtml2pdf) sono opzionali:
se non presenti, si solleva ImportError con messaggio chiaro.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Optional

# Estensioni supportate dall'editor
ESTENSIONI_EDITABILI = {".docx", ".txt", ".html", ".htm"}


def estensione_editabile(nome_file: str) -> bool:
    return Path(nome_file).suffix.lower() in ESTENSIONI_EDITABILI


# ─────────────────────────────────────────────── docx → HTML

def docx_to_html(data: bytes) -> tuple[str, list[str]]:
    """
    Converte un file .docx in HTML tramite mammoth.

    Returns:
        (html, avvisi) — html pronto per TipTap, lista di avvisi di conversione
    """
    try:
        import mammoth
    except ImportError:
        return (
            "<p><em>Libreria mammoth non disponibile. "
            "Esegui: pip install mammoth</em></p>",
            ["mammoth non installato"]
        )
    try:
        result = mammoth.convert_to_html(io.BytesIO(data))
        html = result.value or "<p></p>"
        avvisi = [str(m) for m in result.messages]
        return html, avvisi
    except Exception as e:
        return f"<p><em>Errore conversione .docx: {e}</em></p>", [str(e)]


# ─────────────────────────────────────────────── txt → HTML

def txt_to_html(data: bytes) -> tuple[str, list[str]]:
    """Converte testo plain in HTML con paragrafi."""
    try:
        testo = data.decode("utf-8", errors="replace")
    except Exception:
        testo = ""
    righe = testo.splitlines()
    blocchi: list[str] = []
    buf: list[str] = []
    for riga in righe:
        if riga.strip():
            buf.append(riga)
        else:
            if buf:
                blocchi.append("<p>" + " ".join(buf) + "</p>")
                buf = []
    if buf:
        blocchi.append("<p>" + " ".join(buf) + "</p>")
    html = "\n".join(blocchi) if blocchi else "<p></p>"
    return html, []


# ─────────────────────────────────────────────── bytes → HTML (dispatcher)

def documento_to_html(data: bytes, nome_file: str) -> tuple[str, list[str]]:
    """
    Dispatcher: converte il documento in HTML in base all'estensione.
    """
    ext = Path(nome_file).suffix.lower()
    if ext == ".docx":
        return docx_to_html(data)
    if ext in (".txt",):
        return txt_to_html(data)
    if ext in (".html", ".htm"):
        html = data.decode("utf-8", errors="replace")
        return html, []
    return "<p><em>Formato non supportato per la modifica inline.</em></p>", []


# ─────────────────────────────────────────────── HTML → .docx

def html_to_docx(html: str, titolo: str = "Documento") -> bytes:
    """
    Converte HTML in formato .docx tramite python-docx.

    Supporta: paragrafi, H1–H4, grassetto, corsivo, sottolineato,
              liste puntate/numerate, tabelle (struttura di base).

    Returns:
        bytes del file .docx
    """
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        raise ImportError(
            "python-docx non installato. Esegui: pip install python-docx"
        )
    try:
        from lxml import etree as ET
        from lxml.html import fragment_fromstring, fragments_fromstring
    except ImportError:
        raise ImportError("lxml non disponibile")

    doc = Document()

    # Margini pagina (A4 con margini legali italiani)
    for sec in doc.sections:
        sec.top_margin    = Inches(1.18)   # 3 cm
        sec.bottom_margin = Inches(0.98)   # 2.5 cm
        sec.left_margin   = Inches(1.57)   # 4 cm
        sec.right_margin  = Inches(0.98)   # 2.5 cm

    # Stile default paragrafo
    style_normal = doc.styles["Normal"]
    style_normal.font.name = "Times New Roman"
    style_normal.font.size = Pt(12)

    # Parse HTML
    html_clean = f"<div>{html}</div>"
    try:
        root = ET.fromstring(html_clean.encode("utf-8"),
                             parser=ET.HTMLParser(encoding="utf-8"))
    except Exception:
        p = doc.add_paragraph()
        p.add_run(_strip_tags(html))
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    body = root.find(".//body") or root.find(".//div") or root

    def _process_node(el, paragraph=None):
        tag = (el.tag or "").lower().split("}")[-1]

        if tag in ("h1", "h2", "h3", "h4"):
            level = int(tag[1])
            hdg_style = f"Heading {level}"
            p = doc.add_paragraph(style=hdg_style)
            _add_runs(p, el)
            return

        if tag in ("ul", "ol"):
            for li in el.findall("li"):
                p = doc.add_paragraph(style="List Bullet" if tag == "ul" else "List Number")
                _add_runs(p, li)
            return

        if tag == "table":
            rows = el.findall(".//tr")
            if not rows:
                return
            cols = max(len(r.findall("td") + r.findall("th")) for r in rows)
            tbl = doc.add_table(rows=len(rows), cols=cols)
            tbl.style = "Table Grid"
            for ri, row in enumerate(rows):
                cells = row.findall("th") + row.findall("td")
                for ci, cell in enumerate(cells[:cols]):
                    tbl.rows[ri].cells[ci].text = _strip_tags(
                        ET.tostring(cell, encoding="unicode", method="text")
                    )
            return

        if tag in ("p", "div"):
            p = doc.add_paragraph()
            # allineamento
            align = (el.get("style") or "")
            if "center" in align:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif "right" in align:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            elif "justify" in align:
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            _add_runs(p, el)
            return

        if tag in ("br",):
            doc.add_paragraph()
            return

        # Fallback: processa figli
        for child in el:
            _process_node(child)

    def _add_runs(paragraph, el):
        """Aggiunge runs al paragrafo con formattazione inline."""
        # Testo diretto nell'elemento
        if el.text and el.text.strip():
            r = paragraph.add_run(el.text)
            _apply_inline(r, el.tag.lower())

        for child in el:
            child_tag = (child.tag or "").lower().split("}")[-1]
            if child_tag in ("strong", "b"):
                r = paragraph.add_run(child.text_content() if hasattr(child, 'text_content') else "")
                r.bold = True
            elif child_tag in ("em", "i"):
                r = paragraph.add_run(child.text_content() if hasattr(child, 'text_content') else "")
                r.italic = True
            elif child_tag in ("u",):
                r = paragraph.add_run(child.text_content() if hasattr(child, 'text_content') else "")
                r.underline = True
            elif child_tag == "span":
                r = paragraph.add_run(child.text_content() if hasattr(child, 'text_content') else "")
                # Colore testo da style inline
                style = child.get("style", "")
                m = re.search(r"color:\s*#([0-9a-fA-F]{6})", style)
                if m:
                    rgb = int(m.group(1), 16)
                    r.font.color.rgb = RGBColor(
                        (rgb >> 16) & 0xFF,
                        (rgb >> 8) & 0xFF,
                        rgb & 0xFF
                    )
            else:
                txt = child.text_content() if hasattr(child, 'text_content') else (child.text or "")
                if txt:
                    paragraph.add_run(txt)
            # tail (testo dopo il tag inline)
            if child.tail and child.tail.strip():
                paragraph.add_run(child.tail)

    def _apply_inline(run, tag):
        if tag in ("strong", "b"):
            run.bold = True
        elif tag in ("em", "i"):
            run.italic = True
        elif tag == "u":
            run.underline = True

    # Processa tutti i figli del body
    for child in (body if body is not None else []):
        try:
            _process_node(child)
        except Exception:
            pass

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────── HTML → PDF

_PDF_CSS = """
@page {
  size: A4;
  margin: 3cm 2.5cm 2.5cm 4cm;
  @frame footer {
    -pdf-frame-content: footer;
    bottom: 1cm; margin: 0 1cm;
  }
}
body {
  font-family: "Times New Roman", Times, serif;
  font-size: 12pt;
  line-height: 1.6;
  color: #111;
}
h1 { font-size: 16pt; font-weight: bold; margin-top: 1.2em; }
h2 { font-size: 14pt; font-weight: bold; margin-top: 1em; }
h3 { font-size: 13pt; font-weight: bold; }
h4 { font-size: 12pt; font-weight: bold; text-decoration: underline; }
p  { margin-bottom: 0.6em; text-align: justify; }
table { border-collapse: collapse; width: 100%; margin-bottom: 1em; }
td, th { border: 1px solid #555; padding: 4pt 6pt; }
th { background: #f0f0f0; font-weight: bold; }
ul, ol { margin-left: 1.5em; }
"""


def html_to_pdf(html: str, titolo: str = "Documento") -> bytes:
    """
    Converte HTML in PDF tramite xhtml2pdf.

    Returns:
        bytes del file PDF
    Raises:
        ImportError se xhtml2pdf non è installato
        RuntimeError se la conversione fallisce
    """
    try:
        from xhtml2pdf import pisa
    except ImportError:
        raise ImportError(
            "xhtml2pdf non installato. Esegui: pip install xhtml2pdf"
        )

    full_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>{titolo}</title>
  <style>{_PDF_CSS}</style>
</head>
<body>
  {html}
</body>
</html>"""

    buf = io.BytesIO()
    result = pisa.CreatePDF(full_html.encode("utf-8"), dest=buf)
    if result.err:
        raise RuntimeError(f"Errore generazione PDF: {result.err}")
    return buf.getvalue()


# ─────────────────────────────────────────────── utility

def _strip_tags(html: str) -> str:
    """Rimuove tutti i tag HTML restituendo solo il testo."""
    return re.sub(r"<[^>]+>", "", html or "")
