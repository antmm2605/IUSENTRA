"""Gli altri formati in ingresso: DOCX e il punto d'ingresso unico.

`converti_file` e' la sola funzione che il resto dell'applicazione chiama."""

from __future__ import annotations

import os
import shutil
import tempfile
from html import escape

from .conversione import converti
from .modello import DocumentoConvertito

# ===========================================================================
# 8. Altri formati in ingresso
# ===========================================================================

def converti_docx(percorso: str) -> DocumentoConvertito:
    """DOCX: letto direttamente, senza passare per un programma esterno.

    Prima si chiamava LibreOffice per fare DOCX -> PDF e poi si rileggeva il
    PDF. Funzionava, ma richiede mezzo giga di programma sul server — che sul
    server di IUSENTRA non c'e' — e butta via la struttura del documento per
    poi riscoprirla dalla geometria: i paragrafi tornano dalla posizione delle
    righe, gli elenchi dai pallini disegnati. Il DOCX quella struttura ce
    l'ha gia' scritta dentro, e leggerla li' rende anche meglio: misurato su
    un atto con tredici cose da conservare, la via diretta le tiene tutte e
    tredici, quella per LibreOffice undici — perde il giustificato e il
    rientro di prima riga, che dopo la stampa in PDF non sono piu' dichiarati
    da nessuna parte.
    """
    from .da_docx import converti_docx as leggi_docx

    return leggi_docx(percorso)


def converti_documento_datato(percorso: str) -> DocumentoConvertito:
    """`.doc`, `.odt`, `.rtf`: formati che solo un convertitore esterno apre.

    Sono vecchi o di altri programmi, e la libreria che legge i DOCX non li
    tocca. Se sul sistema c'e' LibreOffice si passa di li'; altrimenti si dice
    chiaramente che non si puo', invece di restituire una pagina vuota.
    """
    import subprocess

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise ValueError(
            f"per leggere {os.path.splitext(percorso)[1]} serve LibreOffice, "
            "che non e' installato: converti il documento in .docx o in .pdf"
        )
    with tempfile.TemporaryDirectory() as cartella:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", cartella, percorso],
            check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        prodotti = [f for f in os.listdir(cartella) if f.lower().endswith(".pdf")]
        if not prodotti:
            raise ValueError(f"conversione non riuscita: {os.path.basename(percorso)}")
        return converti(os.path.join(cartella, prodotti[0]))


def converti_file(percorso: str, **kwargs) -> DocumentoConvertito:
    """Punto d'ingresso unico: sceglie in base all'estensione."""
    estensione = os.path.splitext(percorso)[1].lower()
    if estensione == ".pdf":
        return converti(percorso, **kwargs)
    kwargs.pop("avanzamento", None)
    kwargs.pop("max_pagine_ocr", None)
    kwargs.pop("modo", None)
    kwargs.pop("lingua_ocr", None)
    if estensione == ".docx":
        return converti_docx(percorso)
    if estensione in (".doc", ".odt", ".rtf"):
        return converti_documento_datato(percorso)
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


__all__ = ["ESTENSIONI", "converti_bytes", "converti_docx",
           "converti_documento_datato", "converti_file"]
