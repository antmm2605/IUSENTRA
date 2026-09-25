"""Regole dei file per il deposito nel PTT.

Fonti: decreto direttoriale 4/8/2015 art. 10 come modificato dal d.d.
21/4/2023 (in vigore dal 15/5/2023); pagina DGT «Formato degli atti e
codifica delle anomalie»; Istruzioni operative PTT maggio 2023; Circolare
1/DF del 4/7/2019; notizia DGT del 4/6/2026 sui nuovi limiti.

- Atti processuali (ricorso, appello, controdeduzioni, altri atti): PDF/A-1a o
  1b nativo digitale, senza restrizioni, con firma digitale CAdES (.pdf.p7m) o
  PAdES (.pdf) a pena di inammissibilità (art. 18 D.Lgs. 546/1992).
- Allegati: firma facoltativa; formati BMP, EML, XML, GIF, JPEG, XLS/XLSX,
  DOC/DOCX, ODT, PDF, PNG, TIFF. ZIP non ammesso.
- Limiti: 50 MB per file (oltre si divide in più file), 100 MB per deposito,
  50 file, nome del file fino a 100 caratteri.
- Controlli dopo la trasmissione: elementi attivi e collegamenti ipertestuali
  sono anomalie bloccanti; il formato non PDF/A è un'anomalia non bloccante
  (F1/F2).

I controlli sul contenuto dei PDF si fanno solo quando l'avvocato prepara il
deposito (pulsante «Controlla i file»), non a ogni apertura del fascicolo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

ESTENSIONI_ALLEGATI = frozenset({"bmp", "eml", "xml", "gif", "jpg", "jpeg", "xls", "xlsx", "doc", "docx", "odt", "pdf", "png",
                                 "tif", "tiff"})
LIMITE_FILE = 50 * 1024 * 1024
LIMITE_DEPOSITO = 100 * 1024 * 1024
MASSIMO_FILE = 50
LIMITE_NOME = 100
LIMITE_DESCRIZIONE = 70  # «ALTRI DOCUMENTI»: descrizione fino a 70 caratteri
_ESTENSIONE = re.compile(r"\.([A-Za-z0-9]{1,5})$")
_ATTIVI = (b"/JavaScript", b"/JS ", b"/JS(", b"/Launch", b"/RichMedia")
_COLLEGAMENTI = (b"/URI",)


def estensione(nome: str) -> str:
    trovata = _ESTENSIONE.search((nome or "").strip())
    return trovata.group(1).casefold() if trovata and trovata.start() > 0 else ""


def formato(nome: str) -> str:
    """Il formato del documento, con la firma CAdES che aggiunge «.p7m» all'estensione del file firmato."""
    nome = (nome or "").strip()
    base = nome
    while estensione(base) == "p7m":
        base = base[: -4]
    return estensione(base)


def con_estensione(nome: str, *riserve: str) -> str:
    if estensione(nome):
        return nome
    ext = next((estensione(r) for r in riserve if estensione(r or "")), "")
    return f"{nome.strip()}.{ext}" if ext else nome


def tipo_firma(nome: str, firmato: bool) -> str:
    if estensione(nome) == "p7m":
        return "cades"
    if firmato:
        return "pades" if formato(nome) == "pdf" else "cades"
    return "assente"


@dataclass
class Esito:
    codice: str
    livello: str  # errore | avviso
    messaggio: str

    def to_dict(self) -> dict[str, str]:
        return {"codice": self.codice, "livello": self.livello, "messaggio": self.messaggio}


@dataclass
class Controllo:
    esiti: list[Esito] = field(default_factory=list)

    @property
    def bloccante(self) -> bool:
        return any(e.livello == "errore" for e in self.esiti)


def controlla_metadati(nome: str, dimensione: int, ruolo: str, firmato: bool) -> Controllo:
    """Controlli che il SIGIT fa al caricamento, dai soli dati del documento."""
    controllo = Controllo()
    ext = formato(nome)
    firma = tipo_firma(nome, firmato)
    if len(nome) > LIMITE_NOME:
        controllo.esiti.append(Esito("NOME_LUNGO", "errore", f"Nome oltre {LIMITE_NOME} caratteri: il SIGIT non lo carica."))
    if dimensione > LIMITE_FILE:
        controllo.esiti.append(Esito("DIMENSIONE", "avviso", "Oltre 50 MB: dividilo in più file con «Aggiungi un altro file»."))
    if ruolo == "atto":
        if ext != "pdf":
            controllo.esiti.append(Esito("FORMATO_ATTO", "errore", "L'atto va depositato in PDF/A nativo digitale."))
        if firma == "assente":
            controllo.esiti.append(Esito("FIRMA", "errore", "L'atto va firmato digitalmente (CAdES o PAdES): art. 18 D.Lgs. 546/1992."))
    elif ruolo != "escludi":
        if ext == "zip":
            controllo.esiti.append(Esito("ZIP", "errore", "Il PTT non accetta archivi ZIP: carica i file uno per uno."))
        elif not ext:
            controllo.esiti.append(Esito("FORMATO", "avviso", "Il nome non dice il formato: controlla che sia un PDF/A."))
        elif ext not in ESTENSIONI_ALLEGATI:
            controllo.esiti.append(Esito("FORMATO", "errore", f"Formato .{ext} non ammesso dal PTT."))
        elif ext not in {"pdf", "tif", "tiff", "eml"}:
            controllo.esiti.append(Esito("CONSERVAZIONE", "avviso", "Accettato ma solo protocollato: si conservano a norma PDF/A, TIFF ed EML."))
    return controllo


def _struttura_pdf(dati: bytes) -> tuple[bool, bool, bytes]:
    """Elementi attivi, collegamenti e metadati XMP letti con pypdf (anche negli oggetti compressi)."""
    import io

    from pypdf import PdfReader

    lettore = PdfReader(io.BytesIO(dati), strict=False)
    radice = lettore.trailer["/Root"]
    nomi = radice.get("/Names") or {}
    attivi = "/JavaScript" in nomi or "/AA" in radice
    azione = radice.get("/OpenAction")
    if azione is not None and hasattr(azione, "get_object"):
        azione = azione.get_object()
    if isinstance(azione, dict) and str(azione.get("/S")) in {"/JavaScript", "/Launch"}:
        attivi = True
    collegamenti = False
    for pagina in lettore.pages:
        for annotazione in pagina.get("/Annots") or []:
            voce = annotazione.get_object()
            a = voce.get("/A")
            a = a.get_object() if a is not None and hasattr(a, "get_object") else a
            tipo = str(a.get("/S")) if isinstance(a, dict) else ""
            collegamenti = collegamenti or tipo == "/URI"
            attivi = attivi or tipo in {"/JavaScript", "/Launch"} or str(voce.get("/Subtype")) == "/RichMedia"
    metadati = radice.get("/Metadata")
    xmp = metadati.get_object().get_data() if metadati is not None else b""
    return attivi, collegamenti, xmp


def controlla_contenuto(dati: bytes) -> list[Esito]:
    """Controlli sul PDF che il SIGIT esegue dopo la trasmissione: PDF/A, elementi attivi, collegamenti."""
    esiti: list[Esito] = []
    if not dati.startswith(b"%PDF"):
        return esiti
    try:
        attivi, collegamenti, xmp = _struttura_pdf(dati)
    except Exception:
        attivi = any(marcatore in dati for marcatore in _ATTIVI)
        collegamenti = any(marcatore in dati for marcatore in _COLLEGAMENTI)
        xmp = dati
    if attivi:
        esiti.append(Esito("ELEMENTI_ATTIVI", "errore", "Il PDF contiene elementi attivi (script o azioni automatiche): anomalia bloccante."))
    if collegamenti:
        esiti.append(Esito("COLLEGAMENTI", "errore", "Il PDF contiene collegamenti ipertestuali: anomalia bloccante, rimuovili."))
    parte = re.search(rb"pdfaid:part(?:>|=[\"'])\s*(\d)", xmp)
    livello = re.search(rb"pdfaid:conformance(?:>|=[\"'])\s*([ABUabu])", xmp)
    if not parte:
        esiti.append(Esito("PDFA", "avviso", "Non è un PDF/A: il SIGIT lo accetta con anomalia F1/F2. Convertilo in PDF/A-1b."))
    elif parte.group(1) != b"1" or (livello and livello.group(1).upper() not in {b"A", b"B"}):
        esiti.append(Esito("PDFA", "avviso", "PDF/A diverso da 1a/1b: il SIGIT richiede PDF/A-1a o 1b (anomalia F2)."))
    return esiti


def controlla_deposito(file: list[dict[str, Any]]) -> list[Esito]:
    esiti: list[Esito] = []
    attivi = [f for f in file if f.get("ruolo") != "escludi"]
    if len(attivi) > MASSIMO_FILE:
        esiti.append(Esito("NUMERO_FILE", "errore", f"Più di {MASSIMO_FILE} file in un deposito: dividi in più depositi."))
    if sum(int(f.get("dimensione") or 0) for f in attivi) > LIMITE_DEPOSITO:
        esiti.append(Esito("DIMENSIONE_DEPOSITO", "errore", "Deposito oltre 100 MB: sposta alcuni documenti in una «Nota di deposito documenti»."))
    if not any(f.get("ruolo") == "atto" for f in attivi):
        esiti.append(Esito("ATTO", "errore", "Manca l'atto principale firmato."))
    return esiti


__all__ = ["ESTENSIONI_ALLEGATI", "LIMITE_DEPOSITO", "LIMITE_DESCRIZIONE", "LIMITE_FILE", "LIMITE_NOME", "MASSIMO_FILE",
           "con_estensione", "controlla_contenuto", "controlla_deposito", "controlla_metadati", "estensione", "formato", "tipo_firma"]
