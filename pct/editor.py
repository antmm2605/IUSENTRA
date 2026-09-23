"""
pct/editor.py — Conversione documenti per l'editor web.

Funzionalità:
  - docx_to_html()  : .docx → HTML con mammoth (fedele ai formati Word)
  - pdf_to_html()   : .pdf → HTML con pdfplumber (testo + struttura)
  - html_to_docx()  : HTML → .docx con python-docx + lxml
  - html_to_pdf()   : HTML → PDF con reportlab
  - txt_to_html()   : .txt → HTML semplice

Tutte le funzioni lavorano su bytes già decifrati.
Le dipendenze (mammoth, python-docx, reportlab) sono opzionali:
se non presenti, si solleva ImportError con messaggio chiaro.

Nota sul supporto PDF:
  Il PDF è un formato di presentazione, non di editing. La conversione
  PDF → HTML preserva testo e struttura di base (titoli, paragrafi,
  grassetto) ma non layout complessi, immagini o tabelle grafiche.
  Per PDF scansionati viene usato Tesseract OCR (lingua italiana).
"""
from __future__ import annotations

import base64
import io
import os
import re
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional

# Estensioni supportate dall'editor
ESTENSIONI_EDITABILI = {".docx", ".txt", ".html", ".htm", ".pdf"}
_CID_TOKEN_RE = re.compile(r"\(cid:\s*\d+\)", re.IGNORECASE)


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


# ─────────────────────────────────────────────── pdf → HTML

# ─────────────────────────────────────────────── pdf → HTML

def pdf_to_html(data: bytes) -> tuple[str, list[str], bool, int]:
    """
    Converte un file PDF in HTML per l'editing.

    Strategia:
      1. Prova estrazione testo nativo con pdfplumber (PDF digitali)
      2. Se una pagina è vuota (PDF scansionato), usa Tesseract OCR
      3. Usa la dimensione del font per rilevare titoli (H1/H2/H3)
      4. Preserva grassetto/corsivo dai font names
      5. Estrae tabelle con formattazione HTML
      6. Raggruppa il testo in paragrafi per riga

    Returns:
        (html, avvisi, is_scanned, n_pagine)
        - html       : contenuto HTML pronto per TipTap
        - avvisi     : lista di messaggi informativi
        - is_scanned : True se almeno una pagina è stata processata via OCR
        - n_pagine   : numero totale di pagine nel PDF
    """
    try:
        import pdfplumber
    except ImportError:
        return (
            "<p><em>pdfplumber non disponibile.</em></p>",
            ["pdfplumber non installato"],
            False,
            0
        )

    avvisi: list[str] = []
    html_parti: list[str] = []
    is_scanned = False
    n_pagine = 0

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            n_pagine = len(pdf.pages)
            motivi_layout = _motivi_layout_pdf_non_fedele(pdf.pages)
            if motivi_layout:
                motivo = "; ".join(motivi_layout[:3])
                if len(motivi_layout) > 3:
                    motivo += f"; altre {len(motivi_layout) - 3} pagine con layout complesso"
                avvisi.append(
                    "Il PDF contiene elementi grafici o impaginazione non lineare "
                    f"({motivo}). L'editor usa l'anteprima originale per preservare "
                    "la resa del documento."
                )
                html_parti.append(_html_pdf_non_modificabile(1, "layout PDF complesso", visuale=True))
                return "\n".join(html_parti), avvisi, is_scanned, n_pagine
            
            for i, pagina in enumerate(pdf.pages):
                # ── Estrae tabelle con formattazione ──────────────
                tabelle = pagina.extract_tables()
                if tabelle:
                    for tabella in tabelle:
                        html_tabella = _estrai_tabella_html(tabella)
                        if html_tabella:
                            html_parti.append(html_tabella)

                # ── Raccoglie caratteri con font info ──────────────
                chars = pagina.chars
                testo_plain = pagina.extract_text() or ""

                if not testo_plain.strip() or not _testo_pdf_affidabile(testo_plain):
                    motivo = (
                        "font CID senza mappa Unicode"
                        if testo_plain.strip()
                        else "pagina priva di testo nativo"
                    )
                    testo_fallback = ""
                    if testo_plain.strip():
                        testo_alternativo = _estrai_testo_secondo_motore(data, i)
                        if _testo_pdf_affidabile(testo_alternativo):
                            testo_fallback = testo_alternativo
                            avvisi.append(
                                f"Pagina {i+1}: testo nativo non affidabile ({motivo}), "
                                "estratto con motore PDF alternativo."
                            )
                    if not testo_fallback:
                        testo_ocr = _ocr_pagina(data, i, pagina)
                        if _testo_pdf_affidabile(testo_ocr):
                            testo_fallback = testo_ocr
                            is_scanned = True
                            avvisi.append(
                                f"Pagina {i+1}: testo nativo non affidabile ({motivo}), estratto via OCR."
                            )
                    if testo_fallback:
                        for blocco in _splitta_paragrafi(testo_fallback):
                            html_parti.append(f"<p>{_escape_html(blocco)}</p>")
                    else:
                        html_parti.append(_html_pdf_non_modificabile(i + 1, motivo))
                        avvisi.append(
                            f"Pagina {i+1}: testo PDF non leggibile automaticamente. "
                            "Apri l'anteprima originale o importa una versione DOCX/testo prima di modificare."
                        )
                    if n_pagine > 1 and i < n_pagine - 1:
                        html_parti.append('<hr class="page-break">')
                    continue

                # ── Estrae righe con dimensione font media ─────────
                righe = _estrai_righe_con_font(chars, pagina.extract_text_lines() or [])

                if not righe:
                    # Fallback: testo piano
                    for blocco in _splitta_paragrafi(testo_plain):
                        html_parti.append(f"<p>{_escape_html(blocco)}</p>")
                else:
                    html_parti.extend(_righe_to_html(righe))

                # Separatore di pagina visivo (tranne dopo l'ultima)
                if n_pagine > 1 and i < n_pagine - 1:
                    html_parti.append('<hr class="page-break">')

    except Exception as e:
        avvisi.append(f"Errore estrazione PDF: {e}")
        html_parti.append(f"<p><em>Errore: {_escape_html(str(e))}</em></p>")

    html = "\n".join(html_parti) if html_parti else "<p></p>"
    return html, avvisi, is_scanned, n_pagine


def _estrai_tabella_html(tabella: list) -> str:
    """
    Converte una tabella pdfplumber in HTML con formattazione.
    """
    if not tabella:
        return ""
    
    html = '<table class="pdf-table" style="border-collapse:collapse;width:100%;margin:1rem 0;">\n'
    
    for ri, riga in enumerate(tabella):
        html += '  <tr>\n'
        for cella in riga:
            if cella is not None and str(cella).strip():
                tag = 'th' if ri == 0 else 'td'
                contenuto = _escape_html(str(cella).strip())
                html += f'    <{tag} style="border:1px solid #999;padding:6px 8px;">{contenuto}</{tag}>\n'
        html += '  </tr>\n'
    
    html += '</table>\n'
    return html


def _testo_pdf_affidabile(testo: str) -> bool:
    """Riconosce estrazioni PDF inutilizzabili, in particolare token CID."""
    pulito = (testo or "").strip()
    if not pulito:
        return False
    cid_count = len(_CID_TOKEN_RE.findall(pulito))
    if cid_count >= 3:
        return False
    senza_cid = _CID_TOKEN_RE.sub("", pulito)
    lettere = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]", senza_cid))
    if lettere < 8 and len(pulito) > 40:
        return False
    return True


def _motivi_layout_pdf_non_fedele(pagine: list) -> list[str]:
    """Identifica pagine PDF che non possono essere rese fedelmente come HTML editabile."""
    motivi: list[str] = []
    for indice, pagina in enumerate(pagine, start=1):
        motivo = _motivo_layout_pagina_non_fedele(pagina)
        if motivo:
            motivi.append(f"pagina {indice}: {motivo}")
    return motivi


def _motivo_layout_pagina_non_fedele(pagina) -> str:
    """Rileva immagini, timbri, testo ruotato e disegni che richiedono preview nativa."""
    chars = list(getattr(pagina, "chars", []) or [])
    testo_chars = [c for c in chars if str(c.get("text", "")).strip()]
    non_upright = sum(1 for c in testo_chars if not c.get("upright", True))
    immagini = len(getattr(pagina, "images", []) or [])
    rects = len(getattr(pagina, "rects", []) or [])
    curves = len(getattr(pagina, "curves", []) or [])
    lines = len(getattr(pagina, "lines", []) or [])
    elementi_vettoriali = rects + curves + lines

    ragioni: list[str] = []
    if immagini:
        ragioni.append("immagini/stemmi")
    if non_upright >= 12 or (testo_chars and non_upright / max(1, len(testo_chars)) >= 0.03):
        ragioni.append("testo ruotato o laterale")
    if elementi_vettoriali >= 12:
        ragioni.append("riquadri, timbri o segni grafici")
    return ", ".join(ragioni)


def _estrai_testo_secondo_motore(data: bytes, page_index: int) -> str:
    """Secondo motore di estrazione testo, utile su alcuni PDF con font embedded.

    Il lettore principale e' pdfplumber. Quando il suo risultato non supera il
    controllo di affidabilita' serve un motore costruito diversamente, non lo
    stesso interrogato due volte: qui PDFium.
    """
    from pct.lettura_pdf import leggi_testo_pagina_alternativo

    return leggi_testo_pagina_alternativo(data, page_index)


def _ocr_pagina(data: bytes, page_index: int, pagina=None) -> str:
    """OCR di una pagina PDF con il motore unico dello studio (`legal_ocr.motore`)."""
    try:
        from legal_ocr.motore.testo import testo_da_immagine, testo_da_pdf
    except ImportError:
        return ""

    if pagina is not None:
        try:
            img = pagina.to_image(resolution=300).original
            testo = testo_da_immagine(img, raddrizza=False).testo.strip()
            if testo:
                return testo
        except Exception:
            pass

    try:
        pagine = testo_da_pdf(data, solo_immagini=True)
    except Exception:
        return ""
    for voce in pagine:
        if voce.numero == page_index + 1:
            return voce.testo.strip()
    return ""


def _html_pdf_non_modificabile(numero_pagina: int, motivo: str, *, visuale: bool = False) -> str:
    if visuale:
        testo = (
            f"Pagina {numero_pagina}: il PDF contiene {motivo}. Per non alterare "
            "intestazioni, stemmi, timbri, testo verticale o spaziature, l'editor "
            "mostra l'anteprima originale e blocca il salvataggio inline. Per "
            "modificare il contenuto importa una versione DOCX/testo verificata."
        )
    else:
        testo = (
            f"Pagina {numero_pagina}: il testo del PDF non e' modificabile automaticamente "
            f"perche' l'estrazione ha restituito {motivo}. Apri l'anteprima originale, "
            "oppure importa una versione DOCX/testo verificata prima di salvare modifiche."
        )
    return (
        f'<section data-editor-disabled="true" data-editor-disabled-reason="{_escape_html(motivo)}">'
        "<p><strong>Testo PDF non modificabile automaticamente.</strong></p>"
        f"<p>{_escape_html(testo)}</p>"
        "</section>"
    )


def _estrai_righe_con_font(chars: list, lines_raw: list) -> list[dict]:
    """
    Costruisce lista di righe con testo, dimensione media font e flag bold/italic.
    Ogni dict: {testo, size, bold, italic}
    """
    if not chars:
        return []

    # Raggruppa chars per y (riga)
    riga_map: dict[float, list] = {}
    for c in chars:
        y = round(c.get("top", 0), 1)
        riga_map.setdefault(y, []).append(c)

    righe = []
    for y in sorted(riga_map.keys()):
        gruppo = sorted(riga_map[y], key=lambda c: c.get("x0", 0))
        testo = "".join(c.get("text", "") for c in gruppo).strip()
        if not testo:
            continue
        sizes = [c.get("size", 10) for c in gruppo if c.get("size")]
        avg_size = sum(sizes) / len(sizes) if sizes else 10
        fonts = [c.get("fontname", "").lower() for c in gruppo]
        is_bold = any("bold" in f or "black" in f for f in fonts)
        is_italic = any("italic" in f or "oblique" in f for f in fonts)
        righe.append({
            "testo": testo,
            "size": avg_size,
            "bold": is_bold,
            "italic": is_italic
        })

    return righe


def _righe_to_html(righe: list[dict]) -> list[str]:
    """
    Converte righe con font info in tag HTML.
    Usa dimensione relativa per classificare titoli:
      size > 1.4x media → H1
      size > 1.2x media → H2
      size > 1.05x media → H3
      altrimenti → <p>
    Preserva grassetto e corsivo.
    """
    if not righe:
        return []

    sizes = [r["size"] for r in righe]
    media = sum(sizes) / len(sizes)

    html: list[str] = []
    paragrafo: list[str] = []

    def _flush_paragrafo():
        if paragrafo:
            html.append("<p>" + " ".join(_escape_html(t) for t in paragrafo) + "</p>")
            paragrafo.clear()

    for r in righe:
        testo = r["testo"]
        size = r["size"]
        bold = r.get("bold", False)
        italic = r.get("italic", False)

        # Formatta testo con grassetto/corsivo
        testo_format = _escape_html(testo)
        if bold and italic:
            testo_format = f"<strong><em>{testo_format}</em></strong>"
        elif bold:
            testo_format = f"<strong>{testo_format}</strong>"
        elif italic:
            testo_format = f"<em>{testo_format}</em>"

        if size >= media * 1.4:
            _flush_paragrafo()
            html.append(f"<h1>{testo_format}</h1>")
        elif size >= media * 1.2:
            _flush_paragrafo()
            html.append(f"<h2>{testo_format}</h2>")
        elif size >= media * 1.05:
            _flush_paragrafo()
            html.append(f"<h3>{testo_format}</h3>")
        elif bold and len(testo) < 120:
            _flush_paragrafo()
            html.append(f"<h4>{testo_format}</h4>")
        elif testo == "":
            _flush_paragrafo()
        else:
            paragrafo.append(testo_format)

    _flush_paragrafo()
    return html


def _splitta_paragrafi(testo: str) -> list[str]:
    """Divide testo plain in paragrafi su righe vuote."""
    blocchi, buf = [], []
    for riga in testo.splitlines():
        if riga.strip():
            buf.append(riga.strip())
        elif buf:
            blocchi.append(" ".join(buf))
            buf = []
    if buf:
        blocchi.append(" ".join(buf))
    return blocchi or [testo.strip()]


def _escape_html(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


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


def _email_part_bytes(part: Message | EmailMessage) -> bytes:
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        payload = None
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8", errors="replace")
    return b""


def _email_part_text(part: Message | EmailMessage, payload: bytes) -> str:
    try:
        value = part.get_content()
        if isinstance(value, str):
            return value
    except Exception:
        pass
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def eml_to_html(data: bytes) -> tuple[str, list[str], dict[str, Any]]:
    """Converte un file EML in HTML sicuro per consultazione nel fascicolo."""
    try:
        message = BytesParser(policy=policy.default).parsebytes(data)
    except Exception as exc:
        return (
            "<p><em>Email non leggibile.</em></p>",
            [f"Email non letta: {exc}"],
            {"tipo_originale": "eml", "is_scanned": False, "n_caratteri": 0, "allegati": []},
        )

    headers: list[tuple[str, str]] = []
    for key, label in (
        ("Subject", "Oggetto"),
        ("From", "Mittente"),
        ("To", "Destinatari"),
        ("Cc", "Cc"),
        ("Date", "Data"),
        ("Message-ID", "Message-ID"),
    ):
        value = str(message.get(key, "") or "").strip()
        if value:
            headers.append((label, value))

    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[dict[str, Any]] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = str(part.get_filename() or "").strip()
        disposition = str(part.get_content_disposition() or "").lower()
        content_type = str(part.get_content_type() or "").lower()
        payload = _email_part_bytes(part)
        if filename or disposition == "attachment":
            attachments.append(
                {
                    "nome": filename or "allegato",
                    "tipo": content_type or "application/octet-stream",
                    "dimensione": len(payload),
                }
            )
            continue
        if content_type == "text/plain":
            text = _email_part_text(part, payload).strip()
            if text:
                plain_parts.append(text)
        elif content_type == "text/html":
            text = _strip_tags(_email_part_text(part, payload)).strip()
            if text:
                html_parts.append(text)

    body = "\n\n".join(plain_parts or html_parts).strip()
    sections: list[str] = ['<article class="iusentra-eml-preview">', "<h1>Email PEC / EML</h1>"]
    if headers:
        sections.append('<dl class="iusentra-eml-headers">')
        for label, value in headers:
            sections.append(f"<dt>{_escape_html(label)}</dt><dd>{_escape_html(value)}</dd>")
        sections.append("</dl>")
    if body:
        sections.append("<h2>Corpo del messaggio</h2>")
        for block in _splitta_paragrafi(body):
            sections.append(f"<p>{_escape_html(block)}</p>")
    else:
        sections.append("<p><em>Il messaggio non contiene un corpo testuale leggibile.</em></p>")
    if attachments:
        sections.append("<h2>Allegati indicati nel messaggio</h2><ul>")
        for item in attachments:
            size = item["dimensione"]
            sections.append(
                "<li>"
                f"{_escape_html(item['nome'])} "
                f"<small>{_escape_html(item['tipo'])}, {size} byte</small>"
                "</li>"
            )
        sections.append("</ul>")
    sections.append("</article>")
    html = "\n".join(sections)
    return html, [], {
        "tipo_originale": "eml",
        "is_scanned": False,
        "n_caratteri": len(body),
        "allegati": attachments,
    }


# ─────────────────────────────────────────────── bytes → HTML (dispatcher)

def documento_to_html(data: bytes, nome_file: str) -> tuple[str, list[str], dict]:
    """
    Dispatcher: converte il documento in HTML in base all'estensione.

    Returns:
        (html, avvisi, meta)
        meta contiene: {tipo_originale, is_scanned, n_pagine, n_caratteri, ...}
    """
    ext = Path(nome_file).suffix.lower()

    if ext == ".docx":
        html, avvisi = docx_to_html(data)
        return html, avvisi, {
            "tipo_originale": "docx",
            "is_scanned": False,
            "n_pagine": 1,
            "n_caratteri": len(html)
        }

    if ext == ".pdf":
        html = _html_pdf_non_modificabile(1, "anteprima PDF nativa", visuale=True)
        return html, [
            "Il PDF resta in anteprima nativa: l'editor non lo trasforma in HTML per non perdere font, immagini, timbri, firme o impaginazione."
        ], {
            "tipo_originale": "pdf",
            "is_scanned": False,
            "n_pagine": 0,
            "n_caratteri": len(html),
            "layout_preservato": False,
            "testo_affidabile": False,
            "editor_disabled": True,
            "editor_disabled_reason": "anteprima PDF nativa",
            "anteprima_originale_obbligatoria": True,
        }

    if ext in (".txt",):
        html, avvisi = txt_to_html(data)
        return html, avvisi, {
            "tipo_originale": "txt",
            "is_scanned": False,
            "n_caratteri": len(html)
        }

    if ext == ".eml":
        return eml_to_html(data)

    if ext in (".html", ".htm"):
        html = data.decode("utf-8", errors="replace")
        return html, [], {
            "tipo_originale": "html",
            "is_scanned": False,
            "n_caratteri": len(html)
        }

    return (
        "<p><em>Formato non supportato per la modifica inline.</em></p>",
        [],
        {"tipo_originale": ext.lstrip("."), "is_scanned": False, "n_caratteri": 0},
    )


# ─────────────────────────────────────────────── HTML → .docx

def html_to_docx(html: str, titolo: str = "Documento", studio_timbro: Any = None) -> bytes:
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
        if studio_timbro is not None and getattr(studio_timbro, "enabled", False):
            try:
                header = sec.header
                paragraph = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for line in studio_timbro.to_lines():
                    run = paragraph.add_run(str(line.get("text") or ""))
                    run.bold = bool(line.get("bold"))
                    run.italic = bool(line.get("italic"))
                    run.font.size = Pt(int(line.get("size") or 9))
                    paragraph.add_run("\n")
            except Exception:
                pass

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

    # `find()` restituisce un elemento la cui verita' dipende dal numero di
    # figli: usare `or` qui scartava il <body> quando conteneva un solo nodo.
    body = root.find(".//body")
    if body is None:
        body = root.find(".//div")
    if body is None:
        body = root

    TAG_INLINE = {"strong", "b", "em", "i", "u", "span", "a", "code", "sub", "sup", "font", "mark", "small"}
    TAG_CONTENITORE = {"div", "section", "article", "blockquote", "body", "html", "main", "header", "footer"}
    ALLINEAMENTI = {
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
        "left": WD_ALIGN_PARAGRAPH.LEFT,
    }

    def _nome(el) -> str:
        return (el.tag or "").lower().split("}")[-1] if isinstance(el.tag, str) else ""

    def _allinea(paragraph, el) -> None:
        stile = (el.get("style") or "").lower()
        for chiave, valore in ALLINEAMENTI.items():
            if f"text-align:{chiave}" in stile.replace(" ", "") or f"align={chiave}" in stile:
                paragraph.alignment = valore
                return
        allineamento = (el.get("align") or "").lower()
        if allineamento in ALLINEAMENTI:
            paragraph.alignment = ALLINEAMENTI[allineamento]

    def _colore(el):
        m = re.search(r"color:\s*#([0-9a-fA-F]{6})", el.get("style") or "")
        return m.group(1) if m else ""

    def _stato_figlio(stato: dict, el) -> dict:
        tag = _nome(el)
        nuovo_stato = dict(stato)
        if tag in ("strong", "b"):
            nuovo_stato["bold"] = True
        elif tag in ("em", "i"):
            nuovo_stato["italic"] = True
        elif tag == "u":
            nuovo_stato["underline"] = True
        colore = _colore(el)
        if colore:
            nuovo_stato["color"] = colore
        return nuovo_stato

    def _scrivi(paragraph, testo: str, stato: dict) -> None:
        if not testo:
            return
        run = paragraph.add_run(testo)
        run.bold = True if stato.get("bold") else None
        run.italic = True if stato.get("italic") else None
        run.underline = True if stato.get("underline") else None
        colore = stato.get("color")
        if colore:
            valore = int(colore, 16)
            run.font.color.rgb = RGBColor((valore >> 16) & 0xFF, (valore >> 8) & 0xFF, valore & 0xFF)

    def _add_runs(paragraph, el, stato: dict | None = None) -> None:
        """Testo dell'elemento nel paragrafo, conservando la formattazione annidata.

        La ricorsione serve: <strong><em>testo</em></strong> e' normale in un
        atto, e leggendo solo il primo livello il corsivo andrebbe perso.
        """
        corrente = dict(stato or {})
        _scrivi(paragraph, el.text or "", corrente)
        for figlio in el:
            tag = _nome(figlio)
            if tag == "br":
                paragraph.add_run().add_break()
            elif tag in TAG_INLINE or tag in TAG_CONTENITORE:
                _add_runs(paragraph, figlio, _stato_figlio(corrente, figlio))
            else:
                _add_runs(paragraph, figlio, corrente)
            _scrivi(paragraph, figlio.tail or "", corrente)

    def _marcatore_esplicito(el, ordinato: bool, posizione: int) -> str:
        """Il segno della voce quando l'elenco dichiara tipo o numero di partenza.

        Word numera da solo gli elenchi con lo stile «List Number», ma non sa
        ripartire da 3 ne' usare lettere o numeri romani: in quei casi il
        marcatore va scritto nel testo, com'era nell'atto riconosciuto.
        """
        if not ordinato:
            return ""
        tipo = str(el.get("type") or "1").strip()
        try:
            inizio = int(el.get("start") or 1)
        except (TypeError, ValueError):
            inizio = 1
        if tipo == "1" and inizio == 1:
            return ""
        valore = inizio + posizione
        if tipo in ("a", "A"):
            lettera = chr(ord("a") + (valore - 1) % 26)
            return f"{lettera if tipo == 'a' else lettera.upper()})"
        if tipo in ("i", "I"):
            coppie = ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"))
            resto, romano = valore, ""
            for peso, lettere in coppie:
                while resto >= peso:
                    romano += lettere
                    resto -= peso
            return f"{romano if tipo == 'i' else romano.upper()}."
        return f"{valore}."

    def _voci_elenco(el, ordinato: bool, livello: int = 0) -> None:
        stile = "List Number" if ordinato else "List Bullet"
        if livello:
            stile = f"{stile} {min(livello + 1, 3)}"
        posizione = 0
        for voce in el:
            if _nome(voce) != "li":
                continue
            annidati = [figlio for figlio in voce if _nome(figlio) in ("ul", "ol")]
            marcatore = _marcatore_esplicito(el, ordinato, posizione)
            posizione += 1
            if marcatore:
                paragraph = doc.add_paragraph()
                paragraph.paragraph_format.left_indent = Inches(0.35 + 0.25 * livello)
                paragraph.paragraph_format.first_line_indent = Inches(-0.3)
                paragraph.add_run(f"{marcatore}\t")
            else:
                try:
                    paragraph = doc.add_paragraph(style=stile)
                except KeyError:
                    paragraph = doc.add_paragraph(style="List Number" if ordinato else "List Bullet")
            _scrivi(paragraph, voce.text or "", {})
            for figlio in voce:
                if _nome(figlio) in ("ul", "ol"):
                    continue
                _add_runs(paragraph, figlio, _stato_figlio({}, figlio))
                _scrivi(paragraph, figlio.tail or "", {})
            for annidato in annidati:
                _voci_elenco(annidato, _nome(annidato) == "ol", livello + 1)

    def _tabella(el) -> None:
        righe = el.findall(".//tr")
        if not righe:
            return
        colonne = max(len(riga.findall("td") + riga.findall("th")) for riga in righe)
        if colonne < 1:
            return
        tabella = doc.add_table(rows=len(righe), cols=colonne)
        try:
            tabella.style = "Table Grid"
        except KeyError:
            pass
        for indice_riga, riga in enumerate(righe):
            celle = riga.findall("th") + riga.findall("td")
            for indice_cella, cella in enumerate(celle[:colonne]):
                destinazione = tabella.rows[indice_riga].cells[indice_cella]
                destinazione.text = ""
                _add_runs(destinazione.paragraphs[0], cella, {"bold": True} if _nome(cella) == "th" else {})

    def _process_node(el) -> None:
        tag = _nome(el)
        if not tag:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            livello = min(4, int(tag[1]))
            try:
                paragraph = doc.add_paragraph(style=f"Heading {livello}")
            except KeyError:
                paragraph = doc.add_paragraph()
            _allinea(paragraph, el)
            _add_runs(paragraph, el)
            return
        if tag in ("ul", "ol"):
            _voci_elenco(el, tag == "ol")
            return
        if tag == "table":
            _tabella(el)
            return
        if tag == "br":
            doc.add_paragraph()
            return
        if tag == "hr":
            # Stesso marcatore usato dall'editor e riconosciuto dall'export PDF:
            # l'interruzione di pagina e' formato del documento, non decorazione.
            if el.get("data-iu-page-break") is not None or "iu-ted-page-break" in (el.get("class") or "").split():
                doc.add_page_break()
            else:
                doc.add_paragraph()
            return
        if tag in TAG_CONTENITORE:
            # Un contenitore non e' un capoverso: i suoi figli vanno trattati
            # ciascuno per quello che e', altrimenti titoli, elenchi e tabelle
            # finirebbero appiattiti in un unico paragrafo.
            figli = [figlio for figlio in el if _nome(figlio)]
            if figli:
                if (el.text or "").strip():
                    paragraph = doc.add_paragraph()
                    _allinea(paragraph, el)
                    _scrivi(paragraph, el.text, {})
                for figlio in figli:
                    _process_node(figlio)
                    if (figlio.tail or "").strip():
                        coda = doc.add_paragraph()
                        _scrivi(coda, figlio.tail, {})
                return
        paragraph = doc.add_paragraph()
        _allinea(paragraph, el)
        _add_runs(paragraph, el)

    for child in (body if body is not None else []):
        _process_node(child)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────── HTML → PDF
# Usa reportlab (già in requirements) — nessuna dipendenza di sistema aggiuntiva

#: Gli attributi con cui l'importazione scrive le misure della pagina.
_MISURE_PAGINA = {
    "data-margine-alto": "margin_top_mm",
    "data-margine-destro": "margin_right_mm",
    "data-margine-basso": "margin_bottom_mm",
    "data-margine-sinistro": "margin_left_mm",
}


def misure_del_documento(html: str) -> dict:
    """Margini, corpo e interlinea scritti nella prima pagina del documento.

    `pct/documento_fedele` li misura sull'originale e li lascia sulla sezione
    come attributi `data-`. Qui tornano a essere un layout, in millimetri come
    li vuole l'esportazione.

    Se la pagina non li porta — un HTML scritto a mano, un documento vecchio —
    si restituisce un dizionario vuoto e valgono i valori dell'editor.
    """
    aperture = _aperture_di_pagina(html)
    if not aperture:
        return {}
    sezione = aperture[0].group(0)

    fuori: dict = {}
    for attributo, chiave in _MISURE_PAGINA.items():
        trovato = re.search(rf'{attributo}="([0-9.]+)"', sezione)
        if trovato:
            try:
                fuori[chiave] = round(float(trovato.group(1)) * 25.4 / 72, 1)
            except ValueError:
                pass

    for attributo, chiave in (("data-allineamento", "text_align"),):
        trovato = re.search(rf'{attributo}="([a-z]+)"', sezione)
        if trovato and trovato.group(1) in ("left", "center", "right", "justify"):
            fuori[chiave] = trovato.group(1)

    famiglia = re.search(r"font-family:\s*([^;\"]+)", sezione)
    if famiglia:
        fuori["font_family_documento"] = famiglia.group(1).strip()

    corpo = re.search(r"font-size:\s*([0-9.]+)pt", sezione)
    interlinea = re.search(r'data-interlinea="([0-9.]+)"', sezione)
    if corpo:
        try:
            misura = float(corpo.group(1))
            fuori["font_size_pt"] = misura
            if interlinea and misura > 0:
                fuori["line_height"] = round(float(interlinea.group(1)) / misura, 2)
        except ValueError:
            pass

    if fuori:
        # Il documento dichiara gia' la distanza fra le righe: aggiungerci
        # anche lo stacco fra paragrafi raddoppierebbe ogni interruzione.
        fuori.setdefault("paragraph_spacing_pt", 0)
        fuori["prima_riga_pt"] = _corpo_del_primo_blocco(html, fuori.get("font_size_pt", 12))
    return fuori


# Il tag di apertura si cerca con un solo quantificatore su una classe di
# caratteri che esclude '>': ogni posizione ha una sola strada, quindi il
# tempo resta lineare sulla lunghezza dell'HTML. Cercare la classe dentro
# l'espressione — `[^>]*class="[^"]*iu-doc-pagina` — darebbe invece due
# quantificatori sovrapposti, e su un documento costruito apposta il
# motore ci si arrampicherebbe sopra (CodeQL py/polynomial-redos).
_RE_APERTURA_SECTION = re.compile(r"<section\b[^>]*>", re.I)


def _aperture_di_pagina(html: str) -> list[re.Match[str]]:
    """I tag `<section>` che aprono una pagina del documento importato."""
    if not html or "iu-doc-pagina" not in html:
        return []
    return [
        apertura
        for apertura in _RE_APERTURA_SECTION.finditer(html)
        if "iu-doc-pagina" in apertura.group(0)
    ]


def misure_delle_pagine(html: str) -> list[dict]:
    """Le misure di ogni pagina del documento importato, una per una.

    Un atto non ha un solo insieme di margini: la prima pagina porta la carta
    intestata e comincia a un centimetro dal bordo, le altre cominciano a
    cinque; a volte cambia anche il corpo. Dare a tutte le misure della prima
    e' il motivo per cui sedici pagine ne diventano diciotto.
    """
    aperture = _aperture_di_pagina(html)
    if not aperture:
        return []
    fuori: list[dict] = []
    for posto, apertura in enumerate(aperture):
        sezione = apertura.group(0)
        fine = aperture[posto + 1].start() if posto + 1 < len(aperture) else len(html)
        dentro = html[apertura.end():fine]

        def _numero(attributo: str, ripiego: float) -> float:
            trovato = re.search(rf'{attributo}="([0-9.]+)"', sezione)
            if not trovato:
                return ripiego
            try:
                return float(trovato.group(1))
            except ValueError:
                return ripiego

        corpo = 12.0
        trovato = re.search(r"font-size:\s*([0-9.]+)pt", sezione)
        if trovato:
            try:
                corpo = float(trovato.group(1))
            except ValueError:
                corpo = 12.0
        allinea = "justify"
        trovato = re.search(r'data-allineamento="([a-z]+)"', sezione)
        if trovato and trovato.group(1) in ("left", "center", "right", "justify"):
            allinea = trovato.group(1)

        famiglia = ""
        trovato = re.search(r"font-family:\s*([^;\"]+)", sezione)
        if trovato:
            famiglia = trovato.group(1).strip()

        fuori.append({
            "larghezza": _numero("data-larghezza", 595.3),
            "altezza": _numero("data-altezza", 841.9),
            "alto": _numero("data-margine-alto", 56.7),
            "destro": _numero("data-margine-destro", 56.7),
            "basso": _numero("data-margine-basso", 56.7),
            "sinistro": _numero("data-margine-sinistro", 56.7),
            "interlinea": _numero("data-interlinea", round(corpo * 1.2, 1)),
            "corpo": corpo,
            "allineamento": allinea,
            "famiglia": famiglia,
            "prima_riga": _corpo_del_primo_blocco(dentro, corpo),
        })
    return fuori


def _corpo_del_primo_blocco(html: str, ripiego: float) -> float:
    """Con che corpo e' scritta la prima riga della pagina.

    Serve a sapere di quanto reportlab fara' scendere quella riga sotto il
    margine: lo scarto dipende dal corpo, e la prima riga di un atto e' spesso
    l'intestazione, piu' grande del testo.
    """
    primo = re.search(r"<(?:p|h[1-4])\b[^>]*>", html or "")
    if not primo:
        return ripiego
    corpo = re.search(r"font-size:\s*([0-9.]+)pt", primo.group(0))
    if not corpo:
        return ripiego
    try:
        misura = float(corpo.group(1))
    except ValueError:
        return ripiego
    return misura if 4 <= misura <= 40 else ripiego


def html_to_pdf(
    html: str,
    titolo: str = "Documento",
    layout: Optional[dict] = None,
    studio_timbro: Any = None,
    layout_profile: Any = None,
) -> bytes:
    """
    Converte HTML in PDF tramite reportlab (già installato).

    Gestisce: paragrafi, H1-H4, grassetto, corsivo, liste,
    tabelle di base, linee orizzontali e immagini base64.

    Il parametro opzionale ``layout`` permette di allineare font,
    interlinea e margini al preset dell'editor atti.

    Returns:
        bytes del file PDF
    Raises:
        ImportError se reportlab non è installato
    """
    try:
        from reportlab.platypus import (
            BaseDocTemplate, PageTemplate, Frame, NextPageTemplate,
            SimpleDocTemplate, Paragraph, Spacer, PageBreak,
            Table, TableStyle, HRFlowable, ListFlowable, ListItem, Image as RLImage,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_RIGHT, TA_LEFT
        from reportlab.lib.utils import ImageReader
        from pct.pdf_style import pdf_table_header_style
    except ImportError:
        raise ImportError("reportlab non installato. Esegui: pip install reportlab")

    try:
        from lxml import etree
    except ImportError:
        raise ImportError("lxml non installato")

    # Un documento importato porta scritte le proprie misure. Non passano per
    # la normalizzazione dell'editor: quella tiene i margini fra 5 e 60 mm
    # interi e l'interlinea fra 1,2 e 2,6, che sono limiti giusti per un atto
    # scritto qui e sbagliati per uno da riprodurre — un margine di 3,5 mm
    # diventerebbe 5, e tre pagine su sedici cambierebbero di riga.
    layout = dict(layout or {})
    misure_documento = {} if layout.get("stamp_anchor") else misure_del_documento(html)
    misure_pagine = misure_delle_pagine(html) if misure_documento else []

    try:
        from pct.template_atti import font_editor, normalizza_editor_layout
        layout_cfg = normalizza_editor_layout(layout or {})
        font_meta = font_editor(layout_cfg["font_family"])
    except Exception:
        layout_cfg = {
            "font_size_pt": 12,
            "line_height": 1.9,
            "text_align": "justify",
            "margin_top_mm": 25,
            "margin_right_mm": 22,
            "margin_bottom_mm": 25,
            "margin_left_mm": 32,
            "paragraph_spacing_pt": 8,
        }
        layout_cfg.update({c: v for c, v in layout.items() if c in layout_cfg})
        font_meta = {"pdf_family": "times"}

    editor_page_setup = None
    stamp_callback = None
    if layout_cfg.get("stamp_anchor") == "page_margin":
        # Layout dall'editor atti: pagina, margini e timbro come nei fogli dell'editor.
        try:
            from pct.template_atti_page_setup import page_setup_from_layout, stamp_lines_from_timbro
            from pct.template_atti_pdf import make_editor_stamp_callback

            editor_page_setup = page_setup_from_layout(layout_cfg)
            editor_stamp_lines = stamp_lines_from_timbro(studio_timbro)
            stamp_callback = make_editor_stamp_callback(editor_stamp_lines, editor_page_setup)
            layout_cfg["margin_top_mm"] = editor_page_setup.body_top_mm(len(editor_stamp_lines))
        except Exception:
            editor_page_setup = None
            stamp_callback = None
    if editor_page_setup is None:
        try:
            from pct.legal_layout_profiles import make_pdf_stamp_callback, top_margin_with_stamp

            stamp_callback = make_pdf_stamp_callback(studio_timbro, layout_profile, layout_cfg)
            layout_cfg["margin_top_mm"] = top_margin_with_stamp(layout_cfg, studio_timbro)
        except Exception:
            stamp_callback = None

    if misure_documento:
        # il timbro, quando c'e', ha gia' spostato il margine alto: non si tocca
        if stamp_callback is not None:
            misure_documento.pop("margin_top_mm", None)
        layout_cfg.update(misure_documento)

    pdf_family = (font_meta.get("pdf_family") or "times").lower()
    font_bundle = {
        "times": {
            "normal": "Times-Roman",
            "bold": "Times-Bold",
            "italic": "Times-Italic",
            "bold_italic": "Times-BoldItalic",
        },
        "helvetica": {
            "normal": "Helvetica",
            "bold": "Helvetica-Bold",
            "italic": "Helvetica-Oblique",
            "bold_italic": "Helvetica-BoldOblique",
        },
        "courier": {
            "normal": "Courier",
            "bold": "Courier-Bold",
            "italic": "Courier-Oblique",
            "bold_italic": "Courier-BoldOblique",
        },
    }.get(pdf_family, {
        "normal": "Times-Roman",
        "bold": "Times-Bold",
        "italic": "Times-Italic",
        "bold_italic": "Times-BoldItalic",
    })

    if misure_documento:
        # I quattordici caratteri base del PDF sono metriche Adobe: Times non
        # e' Times New Roman e Helvetica non e' Arial, e l'uno per cento di
        # differenza in larghezza, su una riga giustificata, sposta le parole
        # in mezzo di piu' di un millimetro. Se sul sistema ci sono gli
        # equivalenti metrici aperti — Liberation, Carlito, Caladea — si usano
        # quelli: hanno le stesse larghezze, carattere per carattere.
        try:
            from pct.caratteri_reali import tagli_per
            veri = tagli_per(misure_documento.get("font_family_documento") or "")
            if veri:
                font_bundle = dict(veri)
        except Exception:
            pass

    page_size = landscape(A4) if layout_cfg.get("page_orientation") == "orizzontale" else A4
    font_size = layout_cfg["font_size_pt"]
    leading = round(font_size * layout_cfg["line_height"], 1)
    paragraph_spacing = layout_cfg["paragraph_spacing_pt"]
    alignment = {
        "justify": TA_JUSTIFY,
        "left": TA_LEFT,
        "center": TA_CENTER,
        "right": TA_RIGHT,
    }.get(layout_cfg["text_align"], TA_JUSTIFY)

    # ── Stili ────────────────────────────────────────────────
    base = getSampleStyleSheet()
    st_normal = ParagraphStyle(
        "LegalNormal", parent=base["Normal"],
        fontName=font_bundle["normal"], fontSize=font_size, leading=leading,
        spaceAfter=paragraph_spacing, alignment=alignment,
    )
    st_h1 = ParagraphStyle(
        "LegalH1", parent=base["Heading1"],
        fontName=font_bundle["bold"], fontSize=round(font_size * 1.45, 1), leading=round(leading * 1.15, 1),
        spaceBefore=12, spaceAfter=6,
        alignment=TA_CENTER,
    )
    st_h2 = ParagraphStyle(
        "LegalH2", parent=base["Heading2"],
        fontName=font_bundle["bold"], fontSize=round(font_size * 1.2, 1), leading=round(leading * 1.08, 1),
        spaceBefore=10, spaceAfter=4,
    )
    st_h3 = ParagraphStyle(
        "LegalH3", parent=base["Heading3"],
        fontName=font_bundle["bold"], fontSize=round(font_size * 1.08, 1), leading=round(leading * 1.02, 1),
        spaceBefore=8, spaceAfter=4,
    )
    st_h4 = ParagraphStyle(
        "LegalH4", parent=base["Normal"],
        fontName=font_bundle["bold"], fontSize=round(font_size * 1.02, 1), leading=round(leading, 1),
        spaceBefore=6, spaceAfter=4,
        underlineWidth=0.5,
    )
    if misure_documento:
        # Nell'originale ogni andata a capo e' gia' segnata, e la riga che la
        # precede era giustificata da bordo a bordo. Senza questo reportlab la
        # tratta come fine di capoverso e la lascia corta: le parole si
        # stringono a sinistra e l'ultima arriva anche a quattro millimetri da
        # dove stava.
        st_normal.justifyBreaks = 1

        # Il documento importato porta gia' scritto quanto stacca ogni riga e
        # ogni capoverso. Lo stacco che l'editor mette attorno ai titoli si
        # sommerebbe a quello, e ogni titolo spingerebbe giu' tutto il resto
        # della pagina.
        for _stile in (st_h1, st_h2, st_h3, st_h4):
            _stile.spaceBefore = 0
            _stile.spaceAfter = 0

    _stili_paragrafo: dict = {}
    _allineamenti = {"left": TA_LEFT, "center": TA_CENTER,
                     "right": TA_RIGHT, "justify": TA_JUSTIFY}
    _corrente = {"normal": st_normal, "h1": st_h1, "h2": st_h2,
                 "h3": st_h3, "h4": st_h4}
    _stili_di_pagina: dict = {}

    def _stili_della_pagina(misure: dict) -> dict:
        """Gli stili del corpo con cui e' scritta questa pagina.

        Il corpo e l'interlinea non sono uguali in tutto l'atto: la pagina con
        la carta intestata ha righe fitte, quelle dopo no. Un paragrafo che non
        dichiara le proprie misure prende quelle della sua pagina, non quelle
        della prima.
        """
        famiglia_pagina = misure.get("famiglia") or ""
        chiave = (round(misure["corpo"], 2), round(misure["interlinea"], 2),
                  misure["allineamento"], famiglia_pagina)
        if chiave in _stili_di_pagina:
            return _stili_di_pagina[chiave]
        corpo = misure["corpo"]
        passo = misure["interlinea"] or round(corpo * 1.2, 1)
        # Anche il carattere e' della pagina. Una memoria scritta in due
        # riprese cambia famiglia a meta' atto, e scrivere la seconda meta'
        # con quella della prima non sposta solo il disegno: cambia la
        # larghezza delle parole, l'intestazione va a capo dove prima stava
        # su una riga, e da li' in giu' la pagina scivola di ottanta punti.
        tagli = dict(font_bundle)
        if famiglia_pagina:
            try:
                from pct.caratteri_reali import tagli_per
                propri = tagli_per(famiglia_pagina)
                if propri:
                    tagli = dict(propri)
            except Exception:
                pass
        normale = ParagraphStyle(
            f"Pagina{len(_stili_di_pagina)}", parent=st_normal,
            fontName=tagli["normal"], fontSize=corpo, leading=passo,
            alignment=_allineamenti.get(misure["allineamento"], alignment),
        )
        fuori = {"normal": normale}
        for nome, stile, fattore in (("h1", st_h1, 1.45), ("h2", st_h2, 1.2),
                                     ("h3", st_h3, 1.08), ("h4", st_h4, 1.02)):
            fuori[nome] = ParagraphStyle(
                f"Pagina{len(_stili_di_pagina)}{nome}", parent=stile,
                fontName=tagli["bold"],
                fontSize=round(corpo * fattore, 1), leading=passo,
            )
        _stili_di_pagina[chiave] = fuori
        return fuori

    def _stile_del_paragrafo(elemento, partenza=None):
        """Lo stile di questo paragrafo, non quello del documento.

        Un documento importato porta su ogni capoverso quello che era: come e'
        allineato, di quanto rientra, che interlinea ha, con che corpo e'
        scritto. Rendendoli tutti con lo stile del corpo si perde
        l'intestazione compatta, il titolo centrato, la firma a destra — e le
        righe scivolano tutte di qualche millimetro, che su sedici pagine
        diventano quattro pagine in piu'.
        """
        partenza = partenza if partenza is not None else _corrente["normal"]
        dichiarato = (elemento.get("style") or "").strip()
        if not dichiarato:
            return partenza
        chiave = (partenza.name, dichiarato)
        if chiave in _stili_paragrafo:
            return _stili_paragrafo[chiave]

        def _misura(nome: str):
            trovato = re.search(rf"(?:^|;)\s*{nome}\s*:\s*(-?[0-9.]+)\s*pt", dichiarato)
            if not trovato:
                return None
            try:
                return float(trovato.group(1))
            except ValueError:
                return None

        cambi: dict = {}
        allineamenti = {"left": TA_LEFT, "center": TA_CENTER,
                        "right": TA_RIGHT, "justify": TA_JUSTIFY}
        trovato = re.search(r"text-align\s*:\s*([a-z]+)", dichiarato)
        if trovato and trovato.group(1) in allineamenti:
            cambi["alignment"] = allineamenti[trovato.group(1)]

        # l'ultima riga del capoverso era piena da bordo a bordo
        if re.search(r"text-align-last\s*:\s*justify", dichiarato):
            cambi["justifyLastLine"] = 1

        corpo = _misura("font-size")
        if corpo and 4 <= corpo <= 40:
            cambi["fontSize"] = corpo
            cambi["leading"] = round(corpo * layout_cfg["line_height"], 1)

        # l'interlinea puo' essere in punti o un moltiplicatore del corpo
        passo = _misura("line-height")
        if passo is None:
            trovato = re.search(r"line-height\s*:\s*([0-9.]+)\s*(?:;|$)", dichiarato)
            if trovato:
                try:
                    passo = float(trovato.group(1)) * cambi.get("fontSize", partenza.fontSize)
                except ValueError:
                    passo = None
        if passo and passo > 0:
            cambi["leading"] = round(passo, 1)

        for proprieta, attributo in (("text-indent", "firstLineIndent"),
                                     ("margin-left", "leftIndent"),
                                     ("margin-right", "rightIndent"),
                                     ("margin-top", "spaceBefore"),
                                     ("margin-bottom", "spaceAfter")):
            valore = _misura(proprieta)
            if valore is not None:
                cambi[attributo] = valore

        # Il corpo che riproduce la larghezza che la riga aveva. Serve quando
        # il carattere dichiarato non esiste qui: «Patrocinante in Cassazione»
        # in un calligrafico da sedici punti e' stretto, lo stesso testo in
        # Times da sedici e' largo il doppio e sembra una seconda intestazione
        # sopra la prima.
        # Non si tocca il corpo quando il tratto usa il carattere vero del
        # documento: li' la larghezza e' gia' quella giusta, e correggerla
        # significherebbe correggere una misura esatta con una stimata.
        voluta = (elemento.get("data-larghezza") or "").strip()
        if voluta and _con_carattere_incorporato(elemento):
            voluta = ""
        if voluta and cambi.get("alignment", partenza.alignment) != TA_JUSTIFY:
            corpo_ora = cambi.get("fontSize", partenza.fontSize)
            nuovo = _corpo_che_sta_nella_riga(elemento, voluta, corpo_ora)
            if nuovo is not None:
                cambi["fontSize"] = nuovo

        if not cambi:
            _stili_paragrafo[chiave] = partenza
            return partenza
        stile = ParagraphStyle(f"Doc{len(_stili_paragrafo)}", parent=partenza, **cambi)
        _stili_paragrafo[chiave] = stile
        return stile

    def _corpo_che_sta_nella_riga(elemento, voluta: str, corpo: float):
        """Il corpo con cui questo testo torna largo quanto era.

        Si misura con il carattere che verra' usato davvero, non con quello
        dichiarato: se combaciano il rapporto e' uno e non si tocca niente.
        """
        try:
            larga = float(voluta)
        except ValueError:
            return None
        testo = "".join(elemento.itertext()).strip()
        if larga <= 1 or len(testo) < 2:
            return None
        grassetto = any(
            (figlio.tag or "").lower().split("}")[-1] in ("strong", "b")
            for figlio in elemento if isinstance(figlio.tag, str)
        )
        try:
            from reportlab.pdfbase import pdfmetrics
            misurata = pdfmetrics.stringWidth(
                testo, font_bundle["bold" if grassetto else "normal"], corpo
            )
        except Exception:
            return None
        if misurata <= 1:
            return None
        rapporto = larga / misurata
        # sotto il due per cento e' rumore di misura; fuori da questi estremi
        # non e' piu' una sostituzione di carattere ma un errore di lettura
        if abs(rapporto - 1.0) < 0.02 or not (0.45 <= rapporto <= 1.8):
            return None
        return round(corpo * rapporto, 2)

    st_li = ParagraphStyle(
        "LegalLI", parent=st_normal,
        leftIndent=18, spaceAfter=3,
    )
    st_quote = ParagraphStyle(
        "LegalQuote", parent=st_normal,
        leftIndent=36, rightIndent=18,
        fontName=font_bundle["italic"], textColor=colors.HexColor("#555555"),
    )
    st_caption = ParagraphStyle(
        "LegalCaption", parent=base["Normal"],
        fontName=font_bundle["italic"], fontSize=max(font_size - 2, 8), leading=max(leading - 2, 10),
        alignment=TA_CENTER, textColor=colors.HexColor("#64748b"), spaceAfter=6,
    )

    # Mappa tag → stile
    HEADING_STYLES = {"h1": st_h1, "h2": st_h2, "h3": st_h3, "h4": st_h4}

    # ── Caratteri che il documento si porta dentro ───────────
    _incorporati: dict = {}
    if misure_documento:
        try:
            from pct.documento_fedele.caratteri_incorporati import (
                copre as _copre_incorporato,
            )
            from pct.documento_fedele.caratteri_incorporati import (
                leggi_blocco_stile,
                registra as _registra_incorporato,
            )
            for _alias, _dati in leggi_blocco_stile(html).items():
                if _registra_incorporato(_alias, _dati):
                    _incorporati[_alias] = True
        except Exception:
            _incorporati = {}

            def _copre_incorporato(*_):
                return False

    _RE_FACCIA = re.compile(r"font-family:\s*'?(iu-[0-9a-f]+)'?")

    def _con_carattere_incorporato(elemento) -> bool:
        """Vero se almeno un tratto di questo capoverso usa il carattere vero."""
        if not _incorporati:
            return False
        for figlio in elemento.iter():
            if figlio is elemento or not isinstance(figlio.tag, str):
                continue
            if _faccia_incorporata(figlio):
                return True
        return False

    def _faccia_incorporata(elemento) -> str:
        """Il carattere vero del documento per questo tratto, se si puo' usare.

        Si usa solo se contiene **tutte** le lettere da scrivere: quello
        incorporato in un PDF e' un sottoinsieme, e le lettere che non ci sono
        uscirebbero bianche senza dire niente. Quando non bastano, questo
        tratto torna al sostituto: si vede che il carattere e' un altro, ma il
        testo c'e' tutto.
        """
        if not _incorporati:
            return ""
        trovato = _RE_FACCIA.search(elemento.get("style") or "")
        if not trovato or trovato.group(1) not in _incorporati:
            return ""
        alias = trovato.group(1)
        try:
            if not _copre_incorporato(alias, "".join(elemento.itertext())):
                return ""
        except Exception:
            return ""
        return alias

    # ── Parse HTML ───────────────────────────────────────────
    html_clean = f"<div>{html}</div>"
    try:
        root = etree.fromstring(
            html_clean.encode("utf-8"),
            parser=etree.HTMLParser(encoding="utf-8"),
        )
        body = root.find(".//body")
        if body is None:
            body = root
    except Exception:
        body = None

    # ── Conversione nodo → testo reportlab rich text ─────────
    def _rich_text(value: Optional[str]) -> str:
        return (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _node_to_rich(el) -> str:
        """Converte un elemento HTML in markup reportlab (para XML)."""
        parts = [_rich_text(el.text)]
        for child in el:
            child_tag = (child.tag or "").lower().split("}")[-1] if isinstance(child.tag, str) else ""
            if not child_tag:
                if child.tail:
                    parts.append(_rich_text(child.tail))
                continue
            inner = _node_to_rich(child)
            style = (child.get("style") or "").lower().replace(" ", "")
            if child_tag == "br":
                parts.append("<br/>")
            elif child_tag in ("strong", "b") or "font-weight:bold" in style or re.search(r"font-weight:[6-9]00", style):
                parts.append(f"<b>{inner}</b>")
            elif child_tag in ("em", "i") or "font-style:italic" in style:
                parts.append(f"<i>{inner}</i>")
            elif child_tag in ("u",) or "underline" in style:
                parts.append(f"<u>{inner}</u>")
            elif child_tag in ("s", "strike", "del") or "line-through" in style:
                parts.append(f"<strike>{inner}</strike>")
            elif child_tag == "sup":
                parts.append(f"<super>{inner}</super>")
            elif child_tag == "sub":
                parts.append(f"<sub>{inner}</sub>")
            else:
                faccia = _faccia_incorporata(child) if child_tag == "span" else ""
                parts.append(f'<font face="{faccia}">{inner}</font>' if faccia else inner)
            if child.tail:
                parts.append(_rich_text(child.tail))
        return "".join(parts)

    def _image_flowable_from_src(src: str):
        if not src:
            return None
        match = re.match(r"^data:image/[^;]+;base64,(.+)$", src, flags=re.I | re.S)
        if not match:
            return None
        try:
            image_bytes = base64.b64decode(match.group(1))
        except Exception:
            return None
        try:
            img = RLImage(io.BytesIO(image_bytes))
            usable_width = page_size[0] - ((layout_cfg["margin_left_mm"] + layout_cfg["margin_right_mm"]) / 10.0 * cm)
            if img.drawWidth > usable_width:
                ratio = usable_width / float(img.drawWidth)
                img.drawWidth = usable_width
                img.drawHeight = img.drawHeight * ratio
            return img
        except Exception:
            return None

    # ── Costruisce flowables ──────────────────────────────────
    story = []

    def _quota(stile: str, nome: str):
        """Una misura in percentuale dentro uno `style`."""
        trovato = re.search(rf"(?:^|;)\s*{nome}\s*:\s*([0-9.]+)%", stile or "")
        if not trovato:
            return None
        try:
            return float(trovato.group(1))
        except ValueError:
            return None

    def _celle_della_riga(tr):
        """Le celle nell'ordine in cui stanno, non prima le th e poi le td."""
        return [c for c in tr
                if isinstance(c.tag, str)
                and c.tag.lower().split("}")[-1] in ("td", "th")]

    def _tabella_fedele(el):
        """La tabella com'era: larghezze delle colonne, celle unite, bordi.

        La resa dell'editor rifaceva ogni tabella con uno stile suo — griglia
        grigia su tutto, quattro punti di margine dentro ogni cella, colonne
        larghe uguali. Su un modulo del tribunale, dove le colonne hanno
        larghezze decise e i bordi ci sono solo dove l'autore li ha disegnati,
        quello che tornava non era piu' quel modulo.
        """
        try:
            file_tr = el.findall(".//tr")
            if not file_tr:
                return None

            # larghezza della tabella rispetto alla colonna di testo
            quota_tabella = _quota(el.get("style") or "", "width") or 100.0
            larga = _colonna_utile[0] * min(quota_tabella, 100.0) / 100.0

            # le colonne: si prendono dalla riga che ne ha di piu'
            modello = max(file_tr, key=lambda t: len(_celle_della_riga(t)))
            quote = []
            for cella in _celle_della_riga(modello):
                passo = _quota(cella.get("style") or "", "width") or 0.0
                try:
                    passo *= max(1, int(cella.get("colspan") or 1))
                except ValueError:
                    pass
                quote.append(passo)
            colonne = len(quote)
            if not colonne:
                return None
            somma = sum(quote)
            if somma <= 0:
                larghezze = [larga / colonne] * colonne
            else:
                larghezze = [larga * q / somma for q in quote]

            dati, comandi = [], []
            for numero, tr in enumerate(file_tr):
                fila, colonna = [], 0
                for cella in _celle_della_riga(tr):
                    while len(fila) < colonna:
                        fila.append("")
                    try:
                        quante = max(1, int(cella.get("colspan") or 1))
                        alte = max(1, int(cella.get("rowspan") or 1))
                    except ValueError:
                        quante = alte = 1
                    stile_cella = cella.get("style") or ""
                    ricco = _node_to_rich(cella).replace("&nbsp;", " ").strip()
                    fila.append(Paragraph(ricco, _stile_del_paragrafo(cella))
                                if ricco else "")
                    if quante > 1 or alte > 1:
                        comandi.append(("SPAN", (colonna, numero),
                                        (colonna + quante - 1, numero + alte - 1)))
                    for proprieta, comando in (("padding-left", "LEFTPADDING"),
                                               ("padding-top", "TOPPADDING")):
                        dentro = re.search(
                            rf"(?:^|;)\s*{proprieta}\s*:\s*([0-9.]+)pt", stile_cella
                        )
                        if dentro:
                            try:
                                comandi.append((comando, (colonna, numero),
                                                (colonna, numero),
                                                float(dentro.group(1))))
                            except ValueError:
                                pass
                    sfondo = re.search(r"background-color:\s*(#[0-9a-fA-F]{3,8})",
                                       stile_cella)
                    if sfondo:
                        comandi.append(("BACKGROUND", (colonna, numero),
                                        (colonna, numero),
                                        colors.HexColor(sfondo.group(1))))
                    colonna += quante
                while len(fila) < colonne:
                    fila.append("")
                dati.append(fila[:colonne])

            if not dati:
                return None

            # i margini a zero vanno in testa: i valori per singola cella
            # arrivano dopo e devono poterli scavalcare
            comandi = [
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ] + comandi
            if (el.get("data-bordi") or "1") == "1":
                comandi.append(("GRID", (0, 0), (-1, -1), 0.5, colors.black))

            tabella = Table(dati, colWidths=larghezze)
            tabella.setStyle(TableStyle(comandi))
            # Lo stacco sopra e sotto: una tabella dentro il flusso di un atto
            # sta a una distanza dichiarata, come un paragrafo. Senza, reportlab
            # la appoggia alla precedente e tutto quello che viene dopo sale.
            stile_tabella = el.get("style") or ""
            for proprieta, attributo in (("margin-top", "spaceBefore"),
                                         ("margin-bottom", "spaceAfter")):
                misura = re.search(
                    rf"(?:^|;)\s*{proprieta}\s*:\s*([0-9.]+)pt", stile_tabella
                )
                if misura:
                    try:
                        setattr(tabella, attributo, float(misura.group(1)))
                    except ValueError:
                        pass
            return tabella
        except Exception:
            return None

    # La colonna di testo in cui il documento viene davvero impaginato.
    # Parte da quella dichiarata dal documento, ma ogni pagina importata
    # porta i suoi margini e la aggiorna: misurare le righe sulla colonna
    # della prima pagina significa non accorgersi che sulla seconda vanno a
    # capo — e una riga in piu' in testata spinge giu' tutto il resto.
    _colonna_utile = [
        page_size[0]
        - (layout_cfg["margin_left_mm"] / 10.0) * cm
        - (layout_cfg["margin_right_mm"] / 10.0) * cm
    ]

    def _paragrafo_fedele(rich, stile, attese):
        """Il paragrafo nelle righe che aveva nell'originale.

        In un documento importato ogni andata a capo e' gia' scritta: se il
        paragrafo ne aggiunge una, l'ultima parola scende da sola e tutto il
        resto della pagina scala di una riga. Succede per pochi decimi di
        punto, perche' il carattere di arrivo non e' largo esattamente come
        quello di partenza. Qui si allarga la riga quel tanto che basta, un
        passo alla volta, e ci si ferma appena le righe tornano quelle.
        """
        paragrafo = Paragraph(rich, stile)
        if not attese or attese < 1:
            return paragrafo
        for concessione in (0, 2, 5, 9, 14, 20, 28):
            if concessione:
                stile_largo = ParagraphStyle(
                    f"Fedele{concessione}-{stile.name}", parent=stile,
                    rightIndent=stile.rightIndent - concessione,
                )
                paragrafo = Paragraph(rich, stile_largo)
            try:
                paragrafo.wrap(_colonna_utile[0], 1_000_000)
                righe = len(paragrafo.blPara.lines)
            except Exception:
                return paragrafo
            if righe <= attese:
                if os.environ.get("IU_DEBUG_RIGHE") and concessione:
                    print(f"[fedele] +{concessione}pt per {attese} righe", flush=True)
                return paragrafo
        if os.environ.get("IU_DEBUG_RIGHE"):
            print(f"[fedele] NON RIENTRA: attese={attese} righe={righe}", flush=True)
        return paragrafo

    def _righe_dichiarate(el, rich):
        """Quante righe aveva questo paragrafo nel documento di partenza."""
        if not misure_documento:
            return 0
        return len(re.findall(r"<br\s*/?>", rich or "", re.I)) + 1

    _pagine_viste = [0]
    #: le immagini che nell'originale stanno a una posizione precisa: non
    #: entrano nel flusso del testo, si disegnano sulla pagina dove erano
    _immagini_fisse: dict = {}

    #: i piedi di pagina, con l'altezza a cui stavano nell'originale
    _piedi_fissi: dict = {}

    def _piede_fisso(el) -> bool:
        """Il numero di pagina si disegna dov'era, non in coda al testo.

        Sotto l'ultima riga reportlab tiene fermo un intero passo di
        interlinea: un piede che nell'originale sfiora il bordo del foglio, nel
        flusso non ci sta piu' e scivola alla pagina dopo, portandosi dietro
        tutto il resto. Un atto di sei pagine ne faceva undici.
        """
        alto = (el.get("data-alto") or "").strip()
        if not alto or not misure_pagine:
            return False
        try:
            quota = float(alto)
        except ValueError:
            return False
        pezzi = []
        for figlio in el:
            if not isinstance(figlio.tag, str):
                continue
            testo = _node_to_rich(figlio)
            if testo.strip():
                pezzi.append(Paragraph(testo, _stile_del_paragrafo(figlio)))
        if not pezzi:
            return True
        _piedi_fissi.setdefault(max(0, _pagine_viste[0] - 1), []).append((pezzi, quota))
        return True

    def _immagine_fissa(el) -> bool:
        """Disegna l'immagine dov'era, invece di metterla in fila col testo.

        Nella carta intestata il logo sta accanto al nome dello studio, non
        sopra: messo in fila occupa da solo l'altezza che nell'originale ne
        ospitava due, e da li' in giu' la pagina non torna piu'.
        """
        riquadro = (el.get("data-riquadro") or "").strip()
        if not riquadro or not misure_pagine:
            return False
        try:
            x0, y0, x1, y1 = (float(v) for v in riquadro.split(","))
        except ValueError:
            return False
        if x1 - x0 < 1 or y1 - y0 < 1:
            return True   # immagine degenere: si salta comunque
        trovato = re.match(r"^data:image/[^;]+;base64,(.+)$",
                           el.get("src") or "", flags=re.I | re.S)
        if not trovato:
            return False
        try:
            dati = base64.b64decode(trovato.group(1))
        except Exception:
            return False
        posto = max(0, _pagine_viste[0] - 1)
        _immagini_fisse.setdefault(posto, []).append((dati, x0, y0, x1, y1))
        return True

    def _process(el):
        tag = (el.tag or "").lower().split("}")[-1]

        if tag == "section" and "iu-doc-pagina" in (el.get("class") or ""):
            # Una pagina del documento importato e' una pagina del PDF, con i
            # suoi margini e il suo corpo: se si lascia impaginare al flusso,
            # basta una riga di troppo perche' sedici pagine ne diventino
            # diciotto.
            posto = _pagine_viste[0]
            _pagine_viste[0] += 1
            if posto < len(misure_pagine):
                _corrente.update(_stili_della_pagina(misure_pagine[posto]))
                misure_qui = misure_pagine[posto]
                _colonna_utile[0] = max(
                    1.0,
                    misure_qui["larghezza"] - misure_qui["sinistro"] - misure_qui["destro"],
                )
            if posto > 0:
                if posto < len(misure_pagine):
                    story.append(NextPageTemplate(f"iupag{posto}"))
                story.append(PageBreak())
            quanti_prima = len(story)
            for figlio in el:
                try:
                    _process(figlio)
                except Exception:
                    pass
            # L'ultima pagina di un atto porta spesso solo il numero di
            # pagina: il piede si disegna sulla tela, non entra nel flusso, e
            # una pagina che non mette niente nel flusso non viene creata —
            # reportlab chiude il documento sull'ultimo salto pagina e il
            # nove diventa otto. Un segnaposto alto un decimo di punto basta
            # a farla esistere, e non si vede.
            if len(story) == quanti_prima:
                story.append(Spacer(1, 0.1))
            return

        if tag == "footer" and "iu-doc-piede" in (el.get("class") or ""):
            if _piede_fisso(el):
                return

        if tag in HEADING_STYLES:
            rich = _node_to_rich(el)
            story.append(_paragrafo_fedele(
                rich, _stile_del_paragrafo(el, _corrente.get(tag, HEADING_STYLES[tag])),
                _righe_dichiarate(el, rich)))
            return

        if tag in ("p", "div"):
            child_tags = [(child.tag or "").lower().split("}")[-1] for child in el if isinstance(child.tag, str)]
            nested_blocks = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "hr", "blockquote", "figure", "section", "article"}
            if any(child_tag in nested_blocks for child_tag in child_tags):
                # Contenitore di blocchi (es. l'involucro del documento): ogni blocco resta un paragrafo.
                if (el.text or "").strip():
                    story.append(Paragraph(_rich_text(el.text.strip()), st_normal))
                for child in el:
                    if not isinstance(child.tag, str):
                        continue
                    _process(child)
                    if (child.tail or "").strip():
                        story.append(Paragraph(_rich_text(child.tail.strip()), st_normal))
                return
            rich = _node_to_rich(el)
            if any(child_tag in ("img", "figure") for child_tag in child_tags) and not rich.strip():
                for child in el:
                    _process(child)
                return
            if rich.strip():
                story.append(_paragrafo_fedele(
                    rich, _stile_del_paragrafo(el), _righe_dichiarate(el, rich)))
            else:
                story.append(Spacer(1, 0.3 * cm))
            return

        if tag in ("ul", "ol"):
            items = []
            # Tipo e numero di partenza dichiarati dall'elenco: lettere, numeri
            # romani e liste che ripartono da un numero restano com'erano.
            tipo_elenco = "bullet" if tag == "ul" else (str(el.get("type") or "1").strip() or "1")
            if tipo_elenco not in ("bullet", "1", "a", "A", "i", "I"):
                tipo_elenco = "1"
            try:
                inizio_elenco = max(1, int(el.get("start") or 1))
            except (TypeError, ValueError):
                inizio_elenco = 1
            for li in el.findall("li"):
                rich = _node_to_rich(li)
                items.append(ListItem(Paragraph(rich, st_li), bulletType=tipo_elenco))
            if items:
                opzioni = {"bulletType": tipo_elenco, "leftIndent": 18, "bulletFontSize": 10}
                if tipo_elenco != "bullet":
                    opzioni["start"] = inizio_elenco
                    opzioni["bulletFormat"] = "%s."
                story.append(ListFlowable(items, **opzioni))
            return

        if tag == "hr" and (el.get("data-iu-page-break") is not None or "iu-ted-page-break" in (el.get("class") or "").split()):
            story.append(PageBreak())
            return

        if tag == "hr":
            story.append(HRFlowable(width="100%", thickness=0.5,
                                    color=colors.HexColor("#999999"), spaceAfter=6))
            return

        if tag == "blockquote":
            rich = _node_to_rich(el)
            story.append(Paragraph(rich, st_quote))
            return

        if tag == "figure":
            for child in el:
                _process(child)
            story.append(Spacer(1, 0.15 * cm))
            return

        if tag == "figcaption":
            rich = _node_to_rich(el)
            if rich.strip():
                story.append(Paragraph(rich, st_caption))
            return

        if tag == "img":
            if _immagine_fissa(el):
                return
            image = _image_flowable_from_src(el.get("src", ""))
            if image:
                story.append(image)
                story.append(Spacer(1, 0.2 * cm))
            return

        if tag == "table":
            tabella = (_tabella_fedele(el) if misure_documento else None)
            if tabella is not None:
                story.append(tabella)
                return
            rows_data = []
            for tr in el.findall(".//tr"):
                row = []
                for cell in tr.findall("th") + tr.findall("td"):
                    testo_cella = etree.tostring(cell, encoding="unicode", method="text").strip()
                    row.append(Paragraph(testo_cella, st_li))
                if row:
                    rows_data.append(row)
            if rows_data:
                col_n = max(len(r) for r in rows_data)
                for r in rows_data:
                    while len(r) < col_n:
                        r.append(Paragraph("", st_li))
                tbl = Table(rows_data, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ("GRID",      (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
                    *pdf_table_header_style(font_name=font_bundle["bold"]),
                    ("FONTSIZE",  (0, 0), (-1, -1), max(font_size - 1, 9)),
                    ("TOPPADDING",(0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 0.3 * cm))
            return

        # Fallback: processa figli
        for child in el:
            try:
                _process(child)
            except Exception:
                pass

    if body is not None:
        for child in body:
            try:
                _process(child)
            except Exception:
                pass
    else:
        story.append(Paragraph(_strip_tags(html), st_normal))

    if not story:
        story.append(Paragraph(titolo, st_normal))

    # ── Genera PDF ───────────────────────────────────────────
    buf = io.BytesIO()

    if misure_pagine:
        # Ogni pagina ha la sua cornice, presa dalle misure dell'originale.
        # Il riempimento si azzera: la cornice e' gia' il rettangolo del testo,
        # e sei punti per lato basterebbero a far scendere l'ultima parola di
        # ogni capoverso e l'ultima riga di ogni pagina.
        try:
            from reportlab.pdfbase import pdfmetrics
        except Exception:
            pdfmetrics = None

        modelli = []
        for posto, misure in enumerate(misure_pagine):
            larghezza, altezza = misure["larghezza"], misure["altezza"]
            discesa = 0.0
            if pdfmetrics is not None:
                try:
                    discesa = abs(pdfmetrics.getDescent(
                        font_bundle["normal"], misure["prima_riga"] or misure["corpo"]))
                except Exception:
                    discesa = 0.0
            # reportlab posa il bordo alto del primo carattere una discesa
            # sotto la cornice: la cornice parte percio' quella discesa piu' su
            cima = max(0.0, misure["alto"] - discesa)
            # sotto l'ultima riga tiene fermo un intero passo di interlinea,
            # mentre nell'originale quella riga occupa solo il corpo
            respiro = max(0.0, misure["interlinea"] - misure["corpo"])
            fondo = min(altezza, altezza - misure["basso"] + respiro)
            alta = max(20.0, fondo - cima)
            larga = max(40.0, larghezza - misure["sinistro"] - misure["destro"])
            cornice = Frame(
                misure["sinistro"], altezza - cima - alta, larga, alta,
                leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                id=f"iucornice{posto}",
            )
            def _disegna(tela, documento, _posto=posto, _altezza=altezza,
                         _larga=larga, _sinistra=misure["sinistro"],
                         _discesa=discesa):
                for pezzi, quota in _piedi_fissi.get(_posto, ()):
                    scorre = quota
                    for paragrafo in pezzi:
                        try:
                            _, alta = paragrafo.wrapOn(tela, _larga, 1_000_000)
                            paragrafo.drawOn(
                                tela, _sinistra,
                                _altezza - scorre - alta + _discesa,
                            )
                            scorre += alta
                        except Exception:
                            continue
                for dati, x0, y0, x1, y1 in _immagini_fisse.get(_posto, ()):
                    try:
                        tela.drawImage(
                            ImageReader(io.BytesIO(dati)),
                            x0, _altezza - y1, x1 - x0, y1 - y0,
                            mask="auto", preserveAspectRatio=False,
                        )
                    except Exception:
                        continue
                if stamp_callback is not None:
                    stamp_callback(tela, documento)

            modelli.append(PageTemplate(
                id=f"iupag{posto}", frames=[cornice],
                pagesize=(larghezza, altezza), onPage=_disegna,
            ))

        doc = BaseDocTemplate(
            buf, pagesize=(misure_pagine[0]["larghezza"], misure_pagine[0]["altezza"]),
            title=titolo, author="IUSENTRA",
            leftMargin=misure_pagine[0]["sinistro"],
            rightMargin=misure_pagine[0]["destro"],
            topMargin=misure_pagine[0]["alto"],
            bottomMargin=misure_pagine[0]["basso"],
        )
        doc.addPageTemplates(modelli)
        doc.build(story)
        return buf.getvalue()

    margine_alto = (layout_cfg["margin_top_mm"] / 10.0) * cm
    margine_sinistro = (layout_cfg["margin_left_mm"] / 10.0) * cm
    margine_destro = (layout_cfg["margin_right_mm"] / 10.0) * cm
    margine_basso = (layout_cfg["margin_bottom_mm"] / 10.0) * cm
    if misure_documento:
        # La cornice di reportlab tiene sei punti di riempimento per lato: il
        # testo non comincia sul margine ma due millimetri piu' dentro, e la
        # riga e' quattro millimetri piu' corta, quel tanto che basta a far
        # scendere l'ultima parola di ogni capoverso.
        margine_sinistro -= 6.0
        margine_destro -= 6.0
        # Sotto l'ultima riga reportlab tiene fermo un intero passo di
        # interlinea, mentre nell'originale quella riga occupa solo il corpo:
        # senza restituire la differenza l'ultima riga di ogni pagina scivola
        # a quella dopo, e il documento cresce di una pagina ogni poche.
        margine_basso = max(
            0.0,
            (layout_cfg["margin_bottom_mm"] / 10.0) * cm - 6.0 - max(0.0, leading - font_size),
        )
    if misure_documento:
        # Reportlab non posa la prima riga sul margine: la fa scendere di sei
        # punti di riempimento della cornice piu' la discesa del carattere.
        # Su un documento riprodotto quei nove punti spostano tutta la pagina,
        # perche' ogni riga successiva parte da li'.
        try:
            from reportlab.pdfbase import pdfmetrics
            corpo_prima = misure_documento.get("prima_riga_pt") or font_size
            margine_alto -= 6.0 + abs(
                pdfmetrics.getDescent(font_bundle["normal"], corpo_prima)
            )
        except Exception:
            pass
    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        rightMargin=margine_destro,
        leftMargin=margine_sinistro,
        topMargin=margine_alto,
        bottomMargin=margine_basso,
        title=titolo,
        author="IUSENTRA",
    )
    if stamp_callback is not None:
        doc.build(story, onFirstPage=stamp_callback, onLaterPages=stamp_callback)
    else:
        doc.build(story)
    return buf.getvalue()


# ─────────────────────────────────────────────── utility

class _PlainTextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def _strip_tags(html: str) -> str:
    """Rimuove tutti i tag HTML restituendo solo il testo."""
    parser = _PlainTextHTMLParser()
    parser.feed(html or "")
    parser.close()
    return parser.get_text()
