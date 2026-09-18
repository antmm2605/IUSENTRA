"""Gli altri formati in ingresso: DOCX e il punto d'ingresso unico.

`converti_file` e' la sola funzione che il resto dell'applicazione chiama."""

from __future__ import annotations

import os
import shutil
import tempfile
from html import escape

from .modello import DocumentoConvertito
from .conversione import converti


# ===========================================================================
# 8. Altri formati in ingresso
# ===========================================================================

def converti_docx(percorso: str) -> DocumentoConvertito:
    """DOCX: si passa per PDF quando c'e' LibreOffice, altrimenti conversione diretta."""
    import shutil
    import subprocess
    import tempfile

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        with tempfile.TemporaryDirectory() as cartella:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", cartella, percorso],
                check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            prodotti = [f for f in os.listdir(cartella) if f.lower().endswith(".pdf")]
            if prodotti:
                return converti(os.path.join(cartella, prodotti[0]))

    from docx import Document as Docx   # ripiego senza LibreOffice
    doc = Docx(percorso)
    pezzi = []
    for p in doc.paragraphs:
        if not p.text.strip():
            continue
        allinea = {0: "left", 1: "center", 2: "right", 3: "justify"}.get(
            int(p.alignment) if p.alignment is not None else 0, "left")
        tratti = []
        for run in p.runs:
            testo = escape(run.text)
            if run.bold:
                testo = f"<strong>{testo}</strong>"
            if run.italic:
                testo = f"<em>{testo}</em>"
            if run.underline:
                testo = f"<u>{testo}</u>"
            tratti.append(testo)
        pezzi.append(f'<p style="text-align:{allinea}">{"".join(tratti)}</p>')
    for t in doc.tables:
        righe = []
        for r in t.rows:
            celle = "".join(f"<td>{escape(c.text)}</td>" for c in r.cells)
            righe.append(f"<tr>{celle}</tr>")
        pezzi.append(f'<table class="iu-doc-tabella"><tbody>{"".join(righe)}</tbody></table>')

    esito = DocumentoConvertito()
    esito.html = f'<section class="iu-doc-pagina" data-pagina="1">{"".join(pezzi)}</section>'
    esito.avvisi.append("DOCX convertito senza LibreOffice: impaginazione approssimata")
    return esito


def converti_file(percorso: str, **kwargs) -> DocumentoConvertito:
    """Punto d'ingresso unico: sceglie in base all'estensione."""
    estensione = os.path.splitext(percorso)[1].lower()
    if estensione == ".pdf":
        return converti(percorso, **kwargs)
    kwargs.pop("avanzamento", None)
    kwargs.pop("max_pagine_ocr", None)
    kwargs.pop("modo", None)
    kwargs.pop("lingua_ocr", None)
    if estensione in (".docx", ".doc", ".odt", ".rtf"):
        return converti_docx(percorso)
    if estensione in (".txt", ".md"):
        with open(percorso, encoding="utf-8", errors="replace") as f:
            testo = f.read()
        paragrafi = "".join(
            f"<p>{escape(p)}</p>" for p in testo.split("\n\n") if p.strip()
        )
        esito = DocumentoConvertito()
        esito.html = f'<section class="iu-doc-pagina" data-pagina="1">{paragrafi}</section>'
        return esito
    raise ValueError(f"formato non gestito: {estensione}")


#: estensioni che la conversione fedele sa leggere
ESTENSIONI = (".pdf", ".docx", ".doc", ".odt", ".rtf", ".txt", ".md")


def converti_bytes(dati: bytes, nome: str, **kwargs) -> DocumentoConvertito:
    """La stessa conversione, partendo dal contenuto caricato dall'avvocato.

    L'applicazione riceve un file caricato, non un percorso: la conversione ha
    bisogno di un file vero sul disco (PyMuPDF legge a pagine, non a byte), che
    viene scritto in una cartella temporanea e cancellato comunque, anche se la
    conversione fallisce — un atto lasciato in `/tmp` e' un documento di
    studio fuori dal fascicolo.
    """
    estensione = os.path.splitext(nome or "")[1].lower() or ".pdf"
    cartella = tempfile.mkdtemp(prefix="iusentra-docfedele-")
    percorso = os.path.join(cartella, f"documento{estensione}")
    try:
        with open(percorso, "wb") as destinazione:
            destinazione.write(dati)
        return converti_file(percorso, **kwargs)
    finally:
        shutil.rmtree(cartella, ignore_errors=True)


__all__ = ["ESTENSIONI", "converti_bytes", "converti_docx", "converti_file"]
