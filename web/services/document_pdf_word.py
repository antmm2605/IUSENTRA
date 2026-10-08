"""Conversione PDF in DOCX modificabile, isolata e senza invii esterni."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from web.services.document_tools import DocumentToolError, UploadedDocument, _pdf_reader, validate_uploads

DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def convert_pdf_to_word(document: UploadedDocument, review: str = '') -> tuple[bytes, int, bytes]:
    document = validate_uploads([document])[0]
    reader = _pdf_reader(document)
    pages = len(reader.pages)
    if not 1 <= pages <= 100:
        raise DocumentToolError('La conversione in Word accetta PDF da 1 a 100 pagine per operazione.')
    with tempfile.TemporaryDirectory(prefix='iusentra-pdf-word-') as temporary:
        root = Path(temporary)
        source, result = root / 'source.pdf', root / 'result.docx'
        source.write_bytes(document.data)
        source.chmod(0o600)
        arguments = [sys.executable, str(Path(__file__).with_name('document_pdf_word_worker.py')), str(source), str(result)]
        if review:
            if len(review) > 2_000_000:
                raise DocumentToolError('La revisione è troppo lunga per questa operazione.')
            review_file = root / 'review.json'
            review_file.write_text(review, encoding='utf-8')
            review_file.chmod(0o600)
            arguments.append(str(review_file))
        try:
            run = subprocess.run(
                arguments,
                check=False, capture_output=True, timeout=110,
            )
        except subprocess.TimeoutExpired as exc:
            raise DocumentToolError('La conversione richiede troppo tempo. Il documento originale è conservato.') from exc
        if run.returncode == 20:
            raise DocumentToolError('Questo PDF contiene pagine scansionate: occorre riconoscere il testo prima della conversione modificabile.')
        if run.returncode == 21:
            raise DocumentToolError('La conversione ha cambiato l’impaginazione. La copia Word non è stata consegnata e il PDF originale è conservato.')
        if run.returncode == 22:
            raise DocumentToolError('Il Word generato non riproduce tutto il testo del PDF. La copia non è stata consegnata e l’originale è conservato.')
        if run.returncode == 23:
            raise DocumentToolError('Non è stato possibile applicare tutta la revisione conservando la struttura del documento. Il Word non è stato consegnato: il testo corretto resta nella revisione.')
        if run.returncode or not result.is_file():
            raise DocumentToolError('La conversione in Word non è riuscita. Il documento originale è conservato.')
        data = result.read_bytes()
        if not data.startswith(b'PK'):
            raise DocumentToolError('Il documento Word generato non è valido.')
        preview = result.with_suffix('.pdf')
        if not preview.is_file() or not preview.read_bytes().startswith(b'%PDF-'):
            raise DocumentToolError('Non è stato possibile verificare l’impaginazione del Word generato.')
        return data, pages, preview.read_bytes()
