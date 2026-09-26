"""Il PDF su cui lavora l'editor «Modifica» quando il documento è una prova da non alterare.

L'editor PDF aggiunge testo, evidenziazioni e coperture come overlay sulle
pagine. Sui PDF caricati dallo studio il risultato può diventare una nuova
versione. Sui documenti che fanno prova — PDF arrivati da portali e PEC,
PDF firmati, buste .pdf.p7m, email — l'originale non si tocca mai: si lavora
su una **copia** PDF che entra nel fascicolo come documento nuovo (o si
scarica), e l'originale resta com'è, con la sua firma e la sua impronta
(art. 20 e 22 CAD: la copia informatica non sostituisce l'originale).

Forme PDF riconosciute:

- un PDF, qualunque sia il nome del file;
- una busta firmata .p7m (DER o Base64): si usa il PDF contenuto;
- un'email (.eml o messaggio riconosciuto dalle intestazioni) e i documenti
  DOCX, TXT e HTML, impaginati in PDF.
"""

from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.parser import BytesHeaderParser
from pathlib import Path
from typing import Any

from pct.document_signature_state import document_has_real_digital_signature


class DocumentoNonConvertibile(ValueError):
    """Il documento non ha una forma PDF (per esempio un archivio ZIP)."""


@dataclass(frozen=True)
class PdfDiLavoro:
    dati: bytes
    origine: str  # pdf | busta_firmata | convertito
    solo_copia: bool
    nome_copia: str


def _e_email(dati: bytes, nome: str, tags: list[str]) -> bool:
    if nome.endswith(".eml") or "email" in {str(t).casefold() for t in tags}:
        return True
    intestazioni = BytesHeaderParser(policy=policy.default).parsebytes(dati[:65536])
    return bool(intestazioni.get("From") and intestazioni.get("Subject") and (intestazioni.get("MIME-Version") or intestazioni.get("Date")))


def nome_pdf(nome: str) -> str:
    base = Path(nome or "documento").name
    for coda in (".p7m", ".pm7"):
        if base.lower().endswith(coda):
            base = base[: -len(coda)]
    if base.lower().endswith(".pdf"):
        radice = base[:-4]
    elif Path(base).suffix.lower() in {".eml", ".docx", ".txt", ".html", ".htm"}:
        radice = Path(base).stem
    else:
        radice = base
    return f"{radice.strip() or 'documento'}.pdf"


def _impagina(html: str, titolo: str, studio_timbro: Any) -> bytes:
    from pct.editor import html_to_pdf

    return html_to_pdf(html, titolo=titolo, studio_timbro=studio_timbro)


def pdf_di_lavoro(documento: Any, dati: bytes, *, originale_modificabile: bool, studio_timbro: Any = None) -> PdfDiLavoro:
    """Il PDF da mostrare e modificare per `documento` (dati già decifrati).

    `originale_modificabile` dice se il documento è un PDF dello studio che può
    ricevere una nuova versione; negli altri casi il risultato va solo in copia.
    """
    nome = str(getattr(documento, "nome", "") or "")
    minuscolo = nome.casefold()
    firmato = bool(getattr(documento, "firmato_digitalmente", False)) or document_has_real_digital_signature(documento)
    copia = nome_pdf(nome)
    contenuto = dati
    busta = False
    testa = dati.lstrip()[:16]
    if minuscolo.endswith((".p7m", ".pm7")) or dati[:1] == b"\x30" or testa.startswith((b"MI", b"-----BEGIN")):
        from pct.firme_cades import der_da_base64, extract_signed_payload

        estratto = extract_signed_payload(der_da_base64(dati))
        if estratto:
            contenuto, busta = estratto, True
    solo_copia = busta or firmato or not originale_modificabile or not minuscolo.endswith(".pdf")
    inizio = contenuto.find(b"%PDF-", 0, 1024)
    if inizio >= 0:
        return PdfDiLavoro(contenuto[inizio:], "busta_firmata" if busta else "pdf", solo_copia, copia)
    interno = minuscolo[:-4] if busta and minuscolo.endswith(".p7m") else minuscolo
    tags = list(getattr(documento, "tags", []) or [])
    titolo = Path(copia).stem
    if _e_email(contenuto, interno, tags):
        from pct.editor import eml_to_html

        html, _avvisi, _meta = eml_to_html(contenuto)
        return PdfDiLavoro(_impagina(html, titolo, studio_timbro), "convertito", True, copia)
    suffisso = Path(interno).suffix
    if suffisso in {".docx", ".txt", ".html", ".htm"}:
        from pct.editor import documento_to_html

        html, _avvisi, _meta = documento_to_html(contenuto, interno)
        return PdfDiLavoro(_impagina(html, titolo, studio_timbro), "convertito", True, copia)
    raise DocumentoNonConvertibile(f"Il documento «{nome}» non ha una forma PDF da modificare: scaricalo e aprilo con il suo programma.")


def modificabile_come_pdf(documento: Any) -> bool:
    """Senza aprire il file: il documento ha (quasi certamente) una forma PDF su cui lavorare."""
    nome = str(getattr(documento, "nome", "") or "").casefold()
    tags = {str(t).casefold() for t in getattr(documento, "tags", []) or []}
    if nome.endswith((".pdf", ".p7m", ".eml", ".docx", ".txt", ".html", ".htm")) or "email" in tags:
        return True
    # Nomi senza estensione (l'oggetto della PEC come nome del file): il contenuto si riconosce all'apertura.
    suffisso = Path(nome).suffix
    return suffisso == "" or not suffisso[1:].isalnum()


__all__ = ["DocumentoNonConvertibile", "PdfDiLavoro", "modificabile_come_pdf", "nome_pdf", "pdf_di_lavoro"]
