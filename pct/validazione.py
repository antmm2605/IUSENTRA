"""
Validazione conformità documenti per il Processo Civile Telematico.

- PDF/A:  verifica i marcatori XMP (pdfaid:part / pdfaid:conformance) e lo stato
          di cifratura nel file PDF — senza dipendenze aggiuntive (solo lettura raw bytes).
- Conversione PDF/A: usa Ghostscript (gs) per convertire PDF standard in PDF/A-2B.
- Dimensione busta: verifica che l'allegato non superi 30 MB (limite PST).

Norma di riferimento:
  D.M. 44/2011 art. 12 c.1 — gli atti devono essere in formato PDF/A (ISO 19005).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


# Dimensione massima per allegato (PST — D.M. 44/2011 art. 14 c.4)
MAX_BYTES_ALLEGATO = 30 * 1024 * 1024  # 30 MB


# ---------------------------------------------------------------------------
#  PDF/A
# ---------------------------------------------------------------------------

# Regex per estrarre i marcatori XMP dal byte stream grezzo
_RE_PDFA_PART = re.compile(
    rb'<(?:pdfaid:part|ns\d+:part)[^>]*>(\d+)</(?:pdfaid:part|ns\d+:part)>'
)
_RE_PDFA_CONF = re.compile(
    rb'<(?:pdfaid:conformance|ns\d+:conformance)[^>]*>([A-Za-z]+)</(?:pdfaid:conformance|ns\d+:conformance)>'
)
# Marcatori semplificati che alcuni tool scrivono
_RE_PDFA_SCHEMA = re.compile(rb'pdfaid:part\s*=\s*["\'](\d+)["\']')
_RE_PDFA_CONF2  = re.compile(rb'pdfaid:conformance\s*=\s*["\']([A-Za-z]+)["\']')
# Cifratura PDF
_RE_ENCRYPT = re.compile(rb'/Encrypt\s+\d+\s+\d+\s+R')


def verifica_pdfa(percorso: str) -> dict:
    """
    Verifica la conformità PDF/A di un file PDF.

    Legge i primi 256 KB del file (dove risiede l'XMP header) e gli ultimi
    64 KB (dove alcuni tool inseriscono l'XMP update) cercando i marcatori:
      - pdfaid:part       → numero versione PDF/A (1, 2, 3)
      - pdfaid:conformance → livello (A, B, U)

    Non dipende da pdfplumber: opera solo sui byte grezzi.

    Returns:
        dict con chiavi:
          conforme    (bool)   — True se PDF/A rilevato
          versione    (str)    — es. "PDF/A-2B", "PDF/A-1B", "" se non rilevato
          parte       (str)    — "1", "2", "3" o ""
          livello     (str)    — "A", "B", "U" o ""
          cifrato     (bool)   — True se il PDF è cifrato (non ammesso da PST)
          messaggio   (str)    — descrizione leggibile
          avvisi      (list)   — lista di stringhe con avvertimenti
    """
    path = Path(percorso)
    avvisi: list[str] = []

    # Estensione
    if path.suffix.lower() not in (".pdf", ".p7m"):
        return {
            "conforme": False,
            "versione": "",
            "parte": "",
            "livello": "",
            "cifrato": False,
            "messaggio": f"File non PDF (estensione: {path.suffix})",
            "avvisi": [f"Formato atteso: .pdf o .pdf.p7m — trovato {path.suffix}"],
        }

    if not path.exists():
        return {
            "conforme": False,
            "versione": "",
            "parte": "",
            "livello": "",
            "cifrato": False,
            "messaggio": "File non trovato.",
            "avvisi": ["Percorso file non valido o file mancante."],
        }

    # Leggi intestazione + coda
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            head = fh.read(min(262144, size))   # 256 KB
            if size > 262144:
                fh.seek(max(0, size - 65536))
                tail = fh.read(65536)
            else:
                tail = b""
    except OSError as exc:
        return {
            "conforme": False,
            "versione": "",
            "parte": "",
            "livello": "",
            "cifrato": False,
            "messaggio": f"Impossibile leggere il file: {exc}",
            "avvisi": [str(exc)],
        }

    blob = head + tail

    # Verifica header PDF
    if not head[:8].startswith(b"%PDF-"):
        # Potrebbe essere un .p7m (CAdES) — non facciamo validazione interna
        return {
            "conforme": None,   # None = non verificabile (wrapper firma)
            "versione": "",
            "parte": "",
            "livello": "",
            "cifrato": False,
            "messaggio": "File firmato (.p7m) — validazione PDF/A non applicabile al wrapper CAdES.",
            "avvisi": [
                "La conformità PDF/A va verificata sul PDF originale prima della firma.",
                "Dopo la firma CAdES il contenuto interno rimane invariato.",
            ],
        }

    # Controlla cifratura
    cifrato = bool(_RE_ENCRYPT.search(head))
    if cifrato:
        avvisi.append("PDF cifrato: i PDF cifrati non sono ammessi dal PST (D.M. 44/2011 art. 12).")

    # Cerca XMP pdfaid markers (stile element: <pdfaid:part>2</pdfaid:part>)
    parte: Optional[str] = None
    livello: Optional[str] = None

    m_p = _RE_PDFA_PART.search(blob)
    m_c = _RE_PDFA_CONF.search(blob)

    # Stile attributo: pdfaid:part="2"
    if not m_p:
        m_p = _RE_PDFA_SCHEMA.search(blob)
    if not m_c:
        m_c = _RE_PDFA_CONF2.search(blob)

    if m_p:
        parte = m_p.group(1).decode("ascii", errors="ignore").strip()
    if m_c:
        livello = m_c.group(1).decode("ascii", errors="ignore").strip().upper()

    conforme = bool(parte)
    versione = f"PDF/A-{parte}{livello}" if parte and livello else (f"PDF/A-{parte}" if parte else "")

    # Messaggi
    if conforme:
        msg = f"Documento conforme PDF/A ({versione})."
        if cifrato:
            conforme = False
            msg = f"Documento PDF/A-{parte}{livello} ma cifrato — non ammesso dal PST."
    else:
        msg = (
            "Documento non conforme PDF/A: marcatori XMP pdfaid non trovati. "
            "Riconvertire il file in PDF/A prima del deposito (D.M. 44/2011 art. 12)."
        )
        avvisi.append(
            "Convertire in PDF/A con LibreOffice (Esporta → PDF/A-2), "
            "Microsoft Word (Salva come → PDF → Opzioni → ISO 19005-1), "
            "o strumento dedicato (es. PDF24, iLovePDF, Acrobat Pro)."
        )

    return {
        "conforme": conforme,
        "versione": versione,
        "parte": parte or "",
        "livello": livello or "",
        "cifrato": cifrato,
        "messaggio": msg,
        "avvisi": avvisi,
    }


# ---------------------------------------------------------------------------
#  PDF/A Conversion via Ghostscript
# ---------------------------------------------------------------------------

def converti_pdfa(percorso_input: str, percorso_output: str | None = None) -> dict:
    """
    Converte un PDF in PDF/A-2B usando Ghostscript.

    Ghostscript è lo strumento standard per la conversione PDF/A conforme
    a ISO 19005-2 (PDF/A-2B) — usato da LibreOffice, Acrobat e altri tool.

    Args:
        percorso_input:  percorso del PDF sorgente
        percorso_output: percorso del PDF/A risultante (se None → sovrascrive input)

    Returns:
        dict con chiavi:
          ok          (bool)   — True se conversione riuscita
          percorso    (str)    — percorso file output (se ok=True)
          messaggio   (str)    — descrizione risultato
          ghostscript (bool)   — True se Ghostscript era disponibile
    """
    path_in = Path(percorso_input)
    if not path_in.exists():
        return {"ok": False, "percorso": "", "messaggio": "File sorgente non trovato.", "ghostscript": False}

    # Verifica disponibilità Ghostscript
    gs_bin = shutil.which("gs") or shutil.which("gswin64c") or shutil.which("gswin32c")
    if not gs_bin:
        return {
            "ok": False,
            "percorso": "",
            "messaggio": (
                "Ghostscript non disponibile. "
                "Convertire manualmente il file in PDF/A con LibreOffice "
                "(Esporta → PDF/A-2) o con PDF24 / iLovePDF."
            ),
            "ghostscript": False,
        }

    # Output: sovrascrive in place usando un file temporaneo intermedio
    overwrite = percorso_output is None
    if overwrite:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=path_in.parent)
        import os; os.close(tmp_fd)
        out_path = tmp_path
    else:
        out_path = percorso_output

    # Ghostscript: converti a PDF/A-2B
    # -dPDFA=2         → PDF/A-2B (ISO 19005-2, compatibile con la maggior parte dei portali)
    # -dPDFACompatibilityPolicy=1 → gestisce elementi non PDF/A senza errore fatale
    # -dCompressFonts=true → riduce dimensione file
    cmd = [
        gs_bin,
        "-dBATCH", "-dNOPAUSE", "-dQUIET",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.7",
        "-dPDFA=2",
        "-dPDFACompatibilityPolicy=1",
        "-dCompressFonts=true",
        "-dEmbedAllFonts=true",
        f"-sOutputFile={out_path}",
        str(path_in),
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
    except subprocess.TimeoutExpired:
        if overwrite and Path(out_path).exists():
            Path(out_path).unlink(missing_ok=True)
        return {"ok": False, "percorso": "", "messaggio": "Timeout conversione PDF/A (>120s).", "ghostscript": True}
    except Exception as exc:
        return {"ok": False, "percorso": "", "messaggio": f"Errore Ghostscript: {exc}", "ghostscript": True}

    if result.returncode != 0:
        if overwrite and Path(out_path).exists():
            Path(out_path).unlink(missing_ok=True)
        stderr = (result.stderr or "")[:400]
        return {"ok": False, "percorso": "", "messaggio": f"Ghostscript errore ({result.returncode}): {stderr}", "ghostscript": True}

    # Rimpiazza il file originale (in-place)
    if overwrite:
        import os
        os.replace(out_path, str(path_in))
        out_path = str(path_in)

    # Verifica post-conversione
    esito = verifica_pdfa(out_path)

    return {
        "ok": True,
        "percorso": out_path,
        "messaggio": f"Conversione completata. {esito.get('messaggio', '')}",
        "ghostscript": True,
    }


# ---------------------------------------------------------------------------
#  Dimensione busta
# ---------------------------------------------------------------------------

def verifica_dimensione(percorso: str, max_bytes: int = MAX_BYTES_ALLEGATO) -> dict:
    """
    Verifica che il file non superi il limite PST.

    Returns:
        dict con chiavi: ok (bool), bytes (int), limite_bytes (int), messaggio (str)
    """
    path = Path(percorso)
    if not path.exists():
        return {"ok": False, "bytes": 0, "limite_bytes": max_bytes,
                "messaggio": "File non trovato."}
    sz = path.stat().st_size
    ok = sz <= max_bytes
    mb = round(sz / 1048576, 2)
    lim_mb = round(max_bytes / 1048576, 1)
    return {
        "ok": ok,
        "bytes": sz,
        "limite_bytes": max_bytes,
        "messaggio": (
            f"Dimensione {mb} MB — entro il limite {lim_mb} MB."
            if ok
            else f"File troppo grande: {mb} MB — limite PST {lim_mb} MB."
        ),
    }


# ---------------------------------------------------------------------------
#  Validazione completa documento per deposito
# ---------------------------------------------------------------------------

def valida_documento_deposito(percorso: str, atto_principale: bool = False) -> dict:
    """
    Esegue validazione completa di un documento per il deposito PST.

    Combina: verifica_pdfa + verifica_dimensione.

    Returns:
        dict con chiavi:
          ok          (bool)   — True se tutti i controlli superati
          pdfa        (dict)   — esito verifica_pdfa
          dimensione  (dict)   — esito verifica_dimensione
          avvisi      (list)   — avvisi aggregati (non bloccanti)
          errori      (list)   — errori bloccanti
    """
    pdfa = verifica_pdfa(percorso)
    dim  = verifica_dimensione(percorso)

    errori: list[str] = []
    avvisi: list[str] = list(pdfa.get("avvisi", []))

    # PDF/A: bloccante solo per l'atto principale (gli allegati possono essere non-PDF)
    if atto_principale and pdfa["conforme"] is False:
        errori.append(pdfa["messaggio"])
    elif pdfa["conforme"] is False:
        avvisi.append(f"PDF/A: {pdfa['messaggio']}")

    if pdfa.get("cifrato"):
        errori.append("PDF cifrato non ammesso dal PST.")

    if not dim["ok"]:
        errori.append(dim["messaggio"])

    return {
        "ok": len(errori) == 0,
        "pdfa": pdfa,
        "dimensione": dim,
        "avvisi": avvisi,
        "errori": errori,
    }
