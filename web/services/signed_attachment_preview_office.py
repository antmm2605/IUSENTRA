"""Anteprime di lettura per Office, OpenDocument e dati tabellari.

Non esegue macro, formule, script o collegamenti esterni. L'originale resta
invariato; la superficie esplicita i limiti di impaginazione e di dimensione.
"""
from __future__ import annotations

import csv
from html import escape
import io
import json
from pathlib import PurePosixPath
import re
import zipfile

from defusedxml import ElementTree as ET
from pct.formatting import format_datetime_it, format_date_it
from web.services.signed_attachment_preview import (
    AttachmentPreviewPayload, _decode_text, _preview_shell,
    _textual_unavailable, _zip_declared_directory, attachment_mimetype,
)

OFFICE_EXTENSIONS = {"rtf", "odt", "ods", "odp", "xlsx", "xls", "pptx", "msg", "csv", "json"}
MAX_SOURCE = 16 * 1024 * 1024
MAX_OUTPUT = 1_000_000
MAX_ROWS = 500
MAX_COLUMNS = 128


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml(archive: zipfile.ZipFile, name: str):
    return ET.fromstring(archive.read(name), forbid_dtd=True)


def _safe_archive(data: bytes) -> zipfile.ZipFile:
    declared = _zip_declared_directory(data)
    if not declared or declared[0] > 512 or declared[1] > 4 * 1024 * 1024:
        raise ValueError("Struttura del documento non leggibile o troppo estesa.")
    archive = zipfile.ZipFile(io.BytesIO(data))
    try:
        total = 0
        names: set[str] = set()
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            path = PurePosixPath(name)
            if (not name or name.startswith("/") or ".." in path.parts
                    or ":" in path.parts[0] or name in names
                    or info.flag_bits & 1 or (info.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("Il documento contiene elementi interni non sicuri o cifrati.")
            names.add(name)
            total += info.file_size
            if info.file_size > 8 * 1024 * 1024 or total > 32 * 1024 * 1024:
                raise ValueError("Il documento supera il limite di decompressione del lettore.")
            if info.file_size and (not info.compress_size or info.file_size / info.compress_size > 250):
                raise ValueError("Il documento presenta una compressione anomala.")
        return archive
    except Exception:
        archive.close()
        raise


def _paragraphs(root) -> str:
    blocks = []
    size = 0
    for node in root.iter():
        if _local(node.tag) not in {"p", "h"}:
            continue
        text = "".join(node.itertext())
        size += len(text)
        if size > MAX_OUTPUT:
            raise ValueError("Il testo supera il limite previsto per l’anteprima interna.")
        if text.strip():
            blocks.append("<p>" + escape(text) + "</p>")
    return "".join(blocks)


def _table(rows) -> str:
    output = []
    size = 0
    for index, row in enumerate(rows):
        if index >= MAX_ROWS:
            output.append('<tr><td>Anteprima limitata a 500 righe. L’originale conserva tutte le righe.</td></tr>')
            break
        cells = list(row)
        if len(cells) > MAX_COLUMNS:
            raise ValueError("Il foglio supera le 128 colonne previste per l’anteprima.")
        html = "<tr>" + "".join("<td>" + escape(str(cell)) + "</td>" for cell in cells) + "</tr>"
        size += len(html)
        if size > MAX_OUTPUT:
            raise ValueError("Il foglio supera il limite di testo previsto per il lettore.")
        output.append(html)
    return '<div style="overflow:auto"><table><tbody>' + "".join(output) + "</tbody></table></div>"


def _xlsx(data: bytes) -> str:
    with _safe_archive(data) as archive:
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(n.itertext()) for n in _xml(archive, "xl/sharedStrings.xml").findall(ns + "si")]
        relations = {n.get("Id"): n.get("Target", "") for n in _xml(archive, "xl/_rels/workbook.xml.rels")}
        parts = []
        for sheet in _xml(archive, "xl/workbook.xml").iter(ns + "sheet"):
            if len(parts) >= 30:
                raise ValueError("Il documento supera i 30 fogli previsti per l’anteprima.")
            rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = relations.get(rid, "")
            path = target.lstrip("/") if target.startswith("/") else "xl/" + target
            if path not in archive.namelist() or ".." in PurePosixPath(path).parts:
                raise ValueError("Il foglio non ha una fonte interna valida.")
            rows = []
            for row in _xml(archive, path).iter(ns + "row"):
                values = []
                for cell in row.findall(ns + "c"):
                    letters = re.match(r"[A-Z]+", cell.get("r", ""))
                    column = 0
                    for letter in letters.group() if letters else "":
                        column = column * 26 + ord(letter) - 64
                    if column > MAX_COLUMNS:
                        raise ValueError("Il foglio supera il limite di colonne del lettore.")
                    while len(values) < max(0, column - 1):
                        values.append("")
                    value = cell.findtext(ns + "v", "")
                    if cell.get("t") == "s":
                        value = shared[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = "".join(cell.find(ns + "is").itertext())
                    elif cell.find(ns + "f") is not None and not value:
                        value = "Formula senza risultato salvato nell’originale"
                    values.append(value)
                rows.append(values)
                if len(rows) > MAX_ROWS:
                    break
            parts.append("<h2>" + escape(sheet.get("name", "Foglio")) + "</h2>" + _table(rows))
        return "".join(parts)


def _office_body(data: bytes, ext: str) -> str:
    if ext == "csv":
        text = _decode_text(data)
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        return _table(csv.reader(io.StringIO(text), dialect=dialect))
    if ext == "json":
        return "<pre>" + escape(json.dumps(json.loads(_decode_text(data)), ensure_ascii=False, indent=2)) + "</pre>"
    if ext == "rtf":
        from striprtf.striprtf import rtf_to_text
        return "<pre>" + escape(rtf_to_text(_decode_text(data))) + "</pre>"
    if ext == "xlsx":
        return _xlsx(data)
    if ext == "xls":
        import xlrd
        with xlrd.open_workbook(file_contents=data, on_demand=True) as book:
            if book.nsheets > 30:
                raise ValueError("Il documento supera il limite di 30 fogli.")
            return "".join("<h2>" + escape(sheet.name) + "</h2>" + _table(
                ([format_date_it(xlrd.xldate_as_datetime(cell.value, book.datemode)) if cell.ctype == xlrd.XL_CELL_DATE else cell.value for cell in sheet.row(row)] for row in range(min(sheet.nrows, MAX_ROWS + 1)))
            ) for sheet in book.sheets())
    if ext == "msg":
        import extract_msg
        with extract_msg.openMsg(data, delayAttachments=True) as message:
            date = message.date
            date_text = format_datetime_it(date) if date and date.tzinfo else "Data o fuso orario non disponibili nell’originale"
            headers = (("Oggetto", message.subject), ("Mittente", message.sender), ("Destinatari", message.to), ("Data", date_text))
            body = "<dl>" + "".join("<dt>" + label + "</dt><dd>" + escape(str(value or "")) + "</dd>" for label, value in headers) + "</dl>"
            return body + "<pre>" + escape(message.body or "") + "</pre>"
    with _safe_archive(data) as archive:
        if ext == "pptx":
            names = sorted((n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.search(r"slide(\d+)", n).group(1)))
            if len(names) > 200:
                raise ValueError("La presentazione supera il limite di 200 diapositive.")
            return "".join(f"<h2>Diapositiva {i}</h2>" + _paragraphs(_xml(archive, name)) for i, name in enumerate(names, 1))
        root = _xml(archive, "content.xml")
        if ext == "odp":
            pages = [n for n in root.iter() if _local(n.tag) == "page"]
            if len(pages) > 200:
                raise ValueError("La presentazione supera il limite di 200 diapositive.")
            return "".join(f"<h2>Diapositiva {i}</h2>" + _paragraphs(page) for i, page in enumerate(pages, 1))
        if ext == "ods":
            tables = [n for n in root.iter() if _local(n.tag) == "table"]
            if len(tables) > 30:
                raise ValueError("Il documento supera il limite di 30 fogli.")
            output = []
            for table in tables:
                rows = []
                for row in table:
                    if _local(row.tag) != "table-row":
                        continue
                    cells = []
                    for cell in row:
                        if _local(cell.tag) not in {"table-cell", "covered-table-cell"}:
                            continue
                        repeat = int(next((v for k,v in cell.attrib.items() if _local(k)=="number-columns-repeated"), "1"))
                        text = " ".join("".join(n.itertext()) for n in cell.iter() if _local(n.tag) == "p")
                        if not text and not cells and repeat > MAX_COLUMNS:
                            break
                        if len(cells) + repeat > MAX_COLUMNS:
                            if not text: break
                            raise ValueError("Il foglio supera il limite di colonne del lettore.")
                        cells.extend([text] * repeat)
                    if not any(cells): continue
                    repeat = int(next((v for k,v in row.attrib.items() if _local(k)=="number-rows-repeated"), "1"))
                    rows.extend([cells] * min(repeat, MAX_ROWS + 1 - len(rows)))
                    if len(rows) > MAX_ROWS: break
                name = next((v for k,v in table.attrib.items() if _local(k)=="name"), "Foglio")
                output.append("<h2>" + escape(name) + "</h2>" + _table(rows))
            return "".join(output)
        return _paragraphs(root)


def render_office_preview(nome_file: str, data: bytes, *, signed: bool) -> AttachmentPreviewPayload:
    ext = PurePosixPath(nome_file).suffix.lower().lstrip(".")
    try:
        if len(data) > MAX_SOURCE:
            raise ValueError("Il documento supera i 16 MB previsti per l’anteprima di questo formato.")
        body = _office_body(data, ext)
        if len(body) > MAX_OUTPUT:
            raise ValueError("Il contenuto supera il limite previsto per l’anteprima interna.")
        if not body.strip():
            raise ValueError("Il documento non contiene testo o celle leggibili nell’anteprima.")
        note = '<p class="muted">Anteprima di lettura. L’impaginazione, gli oggetti e le formule restano nell’originale scaricabile. Nessuna macro o formula viene eseguita.</p>'
        return AttachmentPreviewPayload(_preview_shell(title=nome_file, subtitle="Documento " + ext.upper(), body=note + body), "text/html; charset=utf-8", nome_file, signed)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, ValueError) else "Il documento non può essere letto in questo formato: verifica integrità, cifratura e compatibilità dell’originale."
        return _textual_unavailable(nome_file=nome_file, data=data, mimetype=attachment_mimetype(nome_file), signed=signed, reason=reason)
