"""Anteprima MIME con corpo limitato e allegati conservati soltanto per nome.

Il contenuto binario non viene copiato né decodificato. Gli originali restano
nel documento sorgente; questa proiezione serve esclusivamente al lettore.
"""
from __future__ import annotations

from email import policy
from email.parser import BytesHeaderParser

MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_HEADER_BYTES = 64 * 1024
MAX_DEPTH = 16


def bounded_mime_message(data: bytes, *, max_parts: int, max_body_bytes: int):
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("Il messaggio supera il limite di consultazione interna.")
    remaining = max_body_bytes
    parts = 0
    abbreviated = False

    def parse(start: int, end: int, depth: int):
        nonlocal remaining, parts, abbreviated
        parts += 1
        if parts > max_parts or depth > MAX_DEPTH:
            raise ValueError("Il messaggio contiene troppe parti o annidamenti.")
        cap = min(end, start + MAX_HEADER_BYTES)
        separators = [(data.find(sep, start, cap), sep) for sep in (b"\r\n\r\n", b"\n\n")]
        found = [(position, sep) for position, sep in separators if position >= 0]
        if not found:
            raise ValueError("Intestazioni MIME incomplete o troppo grandi.")
        header_end, separator = min(found, key=lambda item: item[0])
        body_start = header_end + len(separator)
        message = BytesHeaderParser(policy=policy.default).parsebytes(data[start:body_start])
        if message.get_filename() or message.get_content_disposition() == "attachment":
            message.set_payload("")
            message._preview_omitted_attachment = True
            return message
        boundary = message.get_boundary()
        if message.get_content_maintype() == "multipart":
            if not boundary or len(boundary) > 200:
                raise ValueError("Delimitatore MIME assente o non valido.")
            marker = b"--" + boundary.encode("ascii", errors="strict")
            message.set_payload([])
            cursor = body_start
            previous = None
            closed = False
            while cursor < end:
                position = data.find(marker, cursor, end)
                if position < 0:
                    break
                cursor = position + len(marker)
                if position != body_start and data[position - 1:position] != b"\n":
                    continue
                tail_end = min(end, cursor + 1024)
                newline = data.find(b"\n", cursor, tail_end)
                line_end = end if newline < 0 and end <= tail_end else newline
                if line_end < 0:
                    continue
                tail = data[cursor:line_end].strip()
                if tail not in (b"", b"--"):
                    continue
                if previous is not None:
                    part_end = position
                    if data[part_end - 2:part_end] == b"\r\n":
                        part_end -= 2
                    elif data[part_end - 1:part_end] == b"\n":
                        part_end -= 1
                    message.attach(parse(previous, part_end, depth + 1))
                if tail == b"--":
                    closed = True
                    break
                previous = line_end + 1
            if not closed:
                raise ValueError("Il messaggio MIME è incompleto: manca la chiusura.")
        else:
            # Conserva soltanto un corpo testuale entro il budget totale,
            # comprese codifica di trasferimento e parti alternative.
            if message.get_content_type() not in ("text/plain", "text/html"):
                message.set_payload("")
                message._preview_omitted_attachment = True
                return message
            length = min(end - body_start, remaining)
            message.set_payload(data[body_start:body_start + length])
            remaining -= length
            abbreviated |= length < end - body_start
        return message

    root = parse(0, len(data), 0)
    if root.get_content_maintype() != "multipart":
        raise ValueError("Il messaggio grande non contiene parti MIME separate.")
    return root, abbreviated
