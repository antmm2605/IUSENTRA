from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup
from lxml import etree


def extract_text(path: Path, content_type: str = "") -> str:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"} or "html" in content_type:
        return extract_html(path.read_text(encoding="utf-8", errors="ignore"))
    if suffix in {".xml", ".xsd"} or "xml" in content_type:
        return extract_xml(path.read_bytes())
    if suffix == ".pdf" or "pdf" in content_type:
        return extract_pdf(path)
    if suffix == ".zip" or "zip" in content_type or "octet-stream" in content_type:
        return extract_zip_summary(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return normalize(soup.get_text(" "))


def extract_xml(data: bytes) -> str:
    try:
        root = etree.fromstring(data)
        return normalize(" ".join(root.xpath(".//text()")))
    except Exception:
        return normalize(data.decode("utf-8", errors="ignore"))


def extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return normalize("\n".join(page.extract_text() or "" for page in reader.pages))
    except Exception as exc:
        return f"[PDF non estratto automaticamente: {exc}]"


def extract_zip_summary(path: Path) -> str:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            preview = []
            for name in names[:100]:
                preview.append(name)
            return "Archivio ZIP. File contenuti:\n" + "\n".join(preview)
    except Exception as exc:
        return f"[ZIP non leggibile: {exc}]"


def split_chunks(text: str, max_chars: int = 3500, overlap: int = 250) -> list[str]:
    text = normalize(text)
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
