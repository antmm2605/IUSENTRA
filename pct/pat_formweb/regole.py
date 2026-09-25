"""Regole sui file del Formweb del Portale dell'Avvocato (PAT, nuovo SIGA).

Fonte: il Portale dell'Avvocato v. 1.15.0 consultato in sola lettura il
25/09/2026 (controlli che il portale esegue sul file prima del caricamento) e
il Manuale Portali Esterni nuovo SIGA-PAT (cap. 6.2). Il portale:

- accetta nel nome del file (estensione esclusa) solo lettere A-Z/a-z, cifre,
  «_», spazi e le lettere tedesche ÄäÖöÜüß (sede bilingue di Bolzano); con
  altri caratteri blocca il caricamento;
- per atto, procura e riepilogo accetta PDF (e .txt/.rtf/.zip/.rar); per gli
  allegati avvisa che formati diversi da quelli ordinari sono ammessi solo se
  una norma li richiede;
- avvisa se il nome supera 150 caratteri e limita a 150 caratteri la
  descrizione della natura del documento;
- carica al massimo 5 documenti per volta; numero e peso complessivo del
  deposito li verifica il server durante la bozza.

Il ricorso e gli atti di parte sono PDF nativi sottoscritti con firma digitale
(art. 136 c.p.a.; regole tecnico-operative d.P.C.S. 2025): il presidio
IUSENTRA del canale ``pat_siga`` richiede PAdES.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

NOME_VALIDO = re.compile(r"^[A-Za-z0-9_ ÄäÖöÜüß]+$")
ESTENSIONI_ALLEGATI = frozenset({"pdf", "txt", "xml", "jpg", "jpeg", "gif", "tiff", "tif", "eml", "msg", "zip", "rar"})
ESTENSIONI_ATTO = frozenset({"pdf", "txt", "rtf", "zip", "rar"})
LIMITE_NOME = 150
LIMITE_DESCRIZIONE = 150
LIMITE_OGGETTO = 16000
FILE_PER_CARICAMENTO = 5
_TEDESCHE = "ÄäÖöÜüß"


def estensione(nome: str) -> str:
    return nome.rsplit(".", 1)[-1].casefold() if "." in nome.strip(".") else ""


def radice(nome: str) -> str:
    punto = nome.rfind(".")
    return nome[:punto] if punto > 0 else nome


def nome_valido(nome: str) -> bool:
    """Lo stesso controllo del portale sul nome del file (estensione esclusa)."""
    return bool(NOME_VALIDO.match(radice(nome or "")))


def nome_formweb(nome: str, riserva: str = "documento") -> str:
    """Il nome più vicino all'originale che il Formweb accetta, estensione compresa.

    Le lettere accentate perdono l'accento, punteggiatura e trattini diventano
    spazi, gli spazi doppi si riducono; l'estensione resta in minuscolo.
    """
    ext = estensione(nome)
    base = []
    for carattere in radice(nome or ""):
        if carattere in _TEDESCHE:
            base.append(carattere)
            continue
        if carattere == ".":  # «T.A.R.» diventa «TAR», non «T A R»
            continue
        semplice = unicodedata.normalize("NFKD", carattere).encode("ascii", "ignore").decode()
        base.append(semplice if semplice and NOME_VALIDO.match(semplice) else " ")
    pulito = re.sub(r"\s+", " ", "".join(base)).strip() or riserva
    massimo = LIMITE_NOME - (len(ext) + 1 if ext else 0)
    pulito = pulito[:massimo].rstrip()
    return f"{pulito}.{ext}" if ext else pulito


def nomi_unici(nomi: list[str]) -> list[str]:
    """Nomi Formweb senza doppioni: il secondo «Allegato.pdf» diventa «Allegato 2.pdf»."""
    visti: dict[str, int] = {}
    esito = []
    for nome in nomi:
        proposta = nome_formweb(nome)
        chiave = proposta.casefold()
        if chiave in visti:
            visti[chiave] += 1
            ext = estensione(proposta)
            proposta = f"{radice(proposta)} {visti[chiave]}" + (f".{ext}" if ext else "")
        else:
            visti[chiave] = 1
        esito.append(proposta)
    return esito


@dataclass
class EsitoFile:
    codice: str
    livello: str  # errore | avviso
    messaggio: str

    def to_dict(self) -> dict[str, str]:
        return {"codice": self.codice, "livello": self.livello, "messaggio": self.messaggio}


@dataclass
class ControlloFile:
    nome: str
    ruolo: str
    dimensione: int
    sha256: str
    firma: str  # pades | cades | assente | non_verificabile
    nome_proposto: str
    esiti: list[EsitoFile] = field(default_factory=list)

    @property
    def bloccante(self) -> bool:
        return any(e.livello == "errore" for e in self.esiti)

    def to_dict(self) -> dict[str, Any]:
        return {"nome": self.nome, "ruolo": self.ruolo, "dimensione": self.dimensione, "sha256": self.sha256,
                "firma": self.firma, "nomeProposto": self.nome_proposto, "bloccante": self.bloccante,
                "esiti": [e.to_dict() for e in self.esiti]}


def tipo_firma(dati: bytes, nome: str = "") -> str:
    """«pades» se il PDF contiene una firma, «cades» per la busta .p7m, altrimenti «assente»."""
    if dati[:5] == b"%PDF-":
        return "pades" if b"/ByteRange" in dati and (b"/Sig" in dati or b"/adbe.pkcs7" in dati) else "assente"
    if estensione(nome) == "p7m" or dati[:1] == b"\x30":
        return "cades"
    return "non_verificabile"


def controlla_file(nome: str, dati: bytes, ruolo: str) -> ControlloFile:
    """Controlla un file come farebbe il Formweb, più la firma richiesta per atto e procura."""
    firma = tipo_firma(dati, nome)
    esito = ControlloFile(nome, ruolo, len(dati), hashlib.sha256(dati).hexdigest().upper(), firma, nome_formweb(nome))
    ext = estensione(nome)
    if not nome_valido(nome):
        esito.esiti.append(EsitoFile("NOME_NON_VALIDO", "errore",
                                     f"Il Formweb rifiuta questo nome: caricalo come «{esito.nome_proposto}»."))
    if len(nome) > LIMITE_NOME:
        esito.esiti.append(EsitoFile("NOME_LUNGO", "avviso", "Nome oltre 150 caratteri: il Formweb lo segnala."))
    principale = ruolo in {"atto", "procura", "riepilogo"}
    ammesse = ESTENSIONI_ATTO if principale else ESTENSIONI_ALLEGATI
    if ext == "p7m":
        esito.esiti.append(EsitoFile("CADES", "errore" if principale else "avviso",
                                     "File .p7m (firma CAdES): nel PAT atti e procura si depositano come PDF firmati PAdES."))
    elif ext not in ammesse:
        esito.esiti.append(EsitoFile("FORMATO", "errore" if principale else "avviso",
                                     f"Formato .{ext or '?'} non ordinario: il Formweb lo accetta solo se una norma lo richiede."))
    if principale and ext == "pdf" and firma != "pades":
        esito.esiti.append(EsitoFile("FIRMA_MANCANTE", "errore", "Manca la firma digitale PAdES del difensore."))
    if dati[:5] == b"%PDF-" and b"/Encrypt" in dati[-4096:] + dati[:4096]:
        esito.esiti.append(EsitoFile("PROTETTO", "errore", "PDF protetto: il portale non può leggerlo."))
    if not dati:
        esito.esiti.append(EsitoFile("VUOTO", "errore", "File vuoto o non leggibile."))
    return esito


__all__ = [
    "ControlloFile", "ESTENSIONI_ALLEGATI", "ESTENSIONI_ATTO", "EsitoFile", "FILE_PER_CARICAMENTO", "LIMITE_DESCRIZIONE",
    "LIMITE_NOME", "LIMITE_OGGETTO", "controlla_file", "estensione", "nome_formweb", "nome_valido", "nomi_unici",
    "tipo_firma",
]
