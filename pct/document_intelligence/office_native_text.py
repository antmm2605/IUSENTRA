"""Testo integrale delle parti native ODS/ODP/PPTX, senza recupero binario.

Legge tutte le parti testuali entro i limiti di sicurezza: il superamento
produce un errore esplicito, mai un indice pronto con testo troncato.
Non esegue formule, macro o riferimenti esterni.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
import re
import struct
import zipfile

from defusedxml import ElementTree


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def extract_office_native_text(content: bytes, extension: str):
    from .extraction import ExtractionResult
    from .models import DocumentAIPageText

    engine = f"{extension}.native-xml-v1"
    try:
        if len(content) > 25 * 1024 * 1024:
            raise ValueError("Documento oltre il limite di lettura configurato.")
        end = content.rfind(b"PK\x05\x06", max(0, len(content)-65557))
        if end < 0 or len(content)-end < 22:
            raise ValueError("Directory interna del documento assente.")
        _magic, disk, start_disk, disk_count, count, size, offset, comment = struct.unpack_from("<4s4H2IH", content, end)
        if disk or start_disk or disk_count != count or count > 4096 or size > 4*1024*1024 or offset + size > end or end + 22 + comment != len(content):
            raise ValueError("Directory interna troppo estesa o non compatibile.")
        with zipfile.ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > 4096:
                raise ValueError("Il documento contiene troppe parti interne.")
            names: set[str] = set()
            total = 0
            for member in members:
                name = member.filename.replace("\\", "/")
                path = PurePosixPath(name)
                if (not name or name.startswith("/") or ".." in path.parts
                        or ":" in path.parts[0] or name in names or member.flag_bits & 1
                        or (member.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError("Struttura interna non sicura o cifrata.")
                names.add(name)
                total += member.file_size
                if (member.file_size > 32 * 1024 * 1024 or total > 128 * 1024 * 1024
                        or member.file_size and (not member.compress_size or member.file_size / member.compress_size > 250)):
                    raise ValueError("Il documento supera i limiti di decompressione sicura.")
            if extension == "pptx":
                parts = sorted((name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
                               key=lambda name: int(re.search(r"slide(\d+)", name).group(1)))
            else:
                parts = ["content.xml"]
            if not parts:
                raise ValueError("Parti testuali del documento assenti.")
            pages = []
            blocks = []
            output_size = 0
            for part in parts:
                root = ElementTree.fromstring(archive.read(part), forbid_dtd=True)
                paragraphs = []
                for node in root.iter():
                    kind = _local(node.tag)
                    if kind == "table-cell" and not any(_local(child.tag) == "p" and "".join(child.itertext()).strip() for child in node.iter()):
                        values = {_local(key): value for key, value in node.attrib.items()}
                        text = next((values[key] for key in ("string-value", "date-value", "time-value", "boolean-value", "value") if key in values), "")
                    elif kind in {"p", "h"}:
                        text = "".join(node.itertext()).strip()
                    else:
                        continue
                    if not text:
                        continue
                    output_size += len(text)
                    if output_size > 16 * 1024 * 1024:
                        raise ValueError("Testo oltre il limite di lettura sicura: indice non creato.")
                    paragraphs.append(text)
                text = "\n".join(paragraphs)
                if text:
                    blocks.append(text)
                if extension == "pptx":
                    pages.append(DocumentAIPageText(page_number=len(pages) + 1, text=text))
            full_text = "\n\n".join(blocks)
            if not full_text.strip():
                raise ValueError("Il documento non contiene testo nativo leggibile.")
            return ExtractionResult(ok=True, text=full_text, pages=pages,
                                    extraction_engine=engine, warnings=[])
    except Exception as exc:
        reason = str(exc) if isinstance(exc, ValueError) else "Parti native del documento non leggibili."
        return ExtractionResult(ok=False, text="", pages=[], extraction_engine=engine,
                                warnings=[reason], error_code="office_native_extraction_failed", error_message=reason)
