"""Read-only presentation of stored public decisions; no OCR or external reads."""
import hashlib
import re
from pathlib import Path

from pct.sentenzeweb_corpus import configured_corpus, source_text_status, text_provenance

HEADINGS = re.compile(r"(?<!\w)(?:RILEVATO\s+CHE:|CONSIDERATO\s+CHE:|FATTI DI CAUSA|RAGIONI DELLA DECISIONE|SVOLGIMENTO DEL PROCESSO|MOTIVI DELLA DECISIONE|P\s*\.\s*Q\s*\.\s*M\s*\.?)(?!\w)", re.I)
PARAGRAPH = re.compile(r"(?<!\S)(?=\d{1,2}\.(?:-)?\s+[A-ZÀ-Ü])")


def text_blocks(text):
    """Only insert visual boundaries; all non-whitespace source characters survive."""
    blocks = []
    offset = 0
    for match in HEADINGS.finditer(text):
        before = text[offset:match.start()]
        for line in before.splitlines():
            for paragraph in PARAGRAPH.split(line):
                if paragraph.strip():
                    blocks.append({"kind": "paragraph", "text": paragraph.strip()})
        blocks.append({"kind": "heading", "text": " ".join(match.group().split()), "anchor": "sezione-" + str(len(blocks))})
        offset = match.end()
    for line in text[offset:].splitlines():
        for paragraph in PARAGRAPH.split(line):
            if paragraph.strip():
                blocks.append({"kind": "paragraph", "text": paragraph.strip()})
    if re.sub(r"\s+", "", "".join(item["text"] for item in blocks)) != re.sub(r"\s+", "", text):
        raise ValueError("Reader formatting changed stored content")
    return blocks


def reader_document(config, record_id, document_id=None):
    corpus = configured_corpus(config)
    record = corpus.get_sentenza(int(record_id)) if corpus else None
    if not record:
        return None
    document = None
    display_text = None
    if document_id is not None:
        document = next((row for row in record.get("documenti", []) if int(row["id"]) == int(document_id)), None)
        if not document:
            return None
        text = str(document.get("testo_estratto") or "")
        relative = str(document.get("path_locale") or "")
        if re.fullmatch(r"recuperi/[0-9a-f]{64}\.txt", relative):
            root = Path(corpus.db_path).resolve().parent
            artifact = root / relative
            if artifact.is_symlink() or artifact.parent.is_symlink() or artifact.stat().st_size > 8 * 1024 * 1024:
                raise ValueError("Unexpected preserved source file")
            raw = artifact.read_bytes()
            if hashlib.sha256(raw).hexdigest() != document.get("sha256"):
                raise ValueError("Preserved source digest differs")
            original = raw.decode("utf-8")
            if " ".join(original.split()) != " ".join(text.split()):
                raise ValueError("Preserved source differs from stored text")
            text = original
            # Restore HTML paragraph boundaries, not newlines inserted around inline citation links.
            from bs4 import BeautifulSoup
            from pct.sentenzeweb_recovery import parse_alternative
            from contextlib import closing
            with closing(corpus._connect()) as connection:
                receipt = connection.execute("""SELECT html_path,html_sha256 FROM sentenzeweb_recovery_receipts
                    WHERE native_id=? AND text_sha256=? AND source_url=? ORDER BY acquired_at DESC LIMIT 1""",
                    (int(record_id), document["sha256"], document["url_origine"])).fetchone()
            if receipt:
                relative_html = str(receipt["html_path"])
                if not re.fullmatch(r"recuperi/[0-9a-f]{64}\.html", relative_html):
                    raise ValueError("Unexpected preserved HTML path")
                html_file = root / relative_html
                if html_file.is_symlink() or html_file.stat().st_size > 8 * 1024 * 1024:
                    raise ValueError("Unexpected preserved HTML file")
                html = html_file.read_bytes()
                if hashlib.sha256(html).hexdigest() != receipt["html_sha256"]:
                    raise ValueError("Preserved HTML digest differs")
                proof = parse_alternative(html, identity=record, source_url=document["url_origine"])
                if proof["text"] != original:
                    raise ValueError("Preserved HTML differs from source text")
                soup = BeautifulSoup(html, "html.parser")
                heading = soup.find("h1")
                card = next(node for node in heading.parent.find_all("div", recursive=False)
                            if "card" in (node.get("class") or []))
                paragraphs = "\n".join(node.get_text(" ", strip=True) for node in card.find_all("p"))
                if re.sub(r"\s+", "", paragraphs) == re.sub(r"\s+", "", original):
                    display_text = paragraphs
    else:
        text = str(record.get("testo_integrale") or "")
    if not text:
        return None
    provenance = text_provenance(" ".join(text.split()), [document] if document else record.get("documenti", []))
    return {"title": record.get("titolo") or "Provvedimento della Cassazione",
            "authority": record.get("organo_giudicante"), "section": record.get("sezione"),
            "number": record.get("numero_sentenza"), "year": record.get("anno_sentenza"),
            "date": record.get("data_deposito"), "text": text, "blocks": text_blocks(display_text if display_text is not None else text),
            "status": source_text_status(text), "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "original_sha256": document.get("sha256") if document else "",
            **provenance}
