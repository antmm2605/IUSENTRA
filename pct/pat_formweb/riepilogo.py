"""Verifica del «Riepilogo deposito» generato dal Formweb prima dell'invio.

Con «Genera riepilogo» il portale produce il PDF che l'avvocato firma e carica
con «Invia deposito» (manuale § 6.2; video ufficiale «Form Web»). Il riepilogo
elenca, per atto, procura, notifiche e allegati, il nome del file e il suo
«Codice HASH» (SHA-256 in esadecimale maiuscolo). IUSENTRA confronta quelle
impronte con i file del fascicolo: se un file è cambiato dopo il caricamento,
o nel riepilogo ne compare uno che il fascicolo non ha, lo dice prima
dell'invio. Controlla anche che il riepilogo caricato sia firmato.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .regole import tipo_firma

_ESADECIMALE = re.compile(r"(?<![0-9A-Z])[0-9A-F]{4,64}(?![0-9A-Z.])")
_TITOLO = re.compile(r"Riepilogo\s+Deposito\s+([A-Za-zÀ-ÿ' ]+?)\s*(?:\n|Sede)", re.I)
_SEDE = re.compile(r"Sede\s*:\s*([^\n]+)", re.I)


@dataclass
class EsitoRiepilogo:
    firma: str
    titolo: str
    sede: str
    impronte: list[str]
    documenti: list[dict[str, Any]] = field(default_factory=list)
    estranee: list[str] = field(default_factory=list)
    leggibile: bool = True

    @property
    def conforme(self) -> bool:
        return (self.leggibile and self.firma in {"pades", "cades"} and not self.estranee
                and all(d["nelRiepilogo"] for d in self.documenti if d.get("atteso")))

    def to_dict(self) -> dict[str, Any]:
        return {"firma": self.firma, "titolo": self.titolo, "sede": self.sede, "impronte": self.impronte,
                "documenti": self.documenti, "estranee": self.estranee, "leggibile": self.leggibile,
                "conforme": self.conforme}


def _pdf(dati: bytes, nome: str) -> bytes:
    if dati[:5] == b"%PDF-":
        return dati
    try:
        from pct.firma import estrai_contenuto_cades

        interno = estrai_contenuto_cades(dati) or b""
        return interno if interno[:5] == b"%PDF-" else b""
    except Exception:
        return b""


def testo_pdf(pdf: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join(pagina.extract_text() or "" for pagina in PdfReader(io.BytesIO(pdf)).pages)


def impronte(testo: str) -> list[str]:
    """Le impronte SHA-256 del riepilogo, anche quando la cella le spezza su più righe.

    Si uniscono i gruppi esadecimali separati solo da spazi o a capo; se davanti
    all'impronta c'è un numero (una data, un protocollo) lo si scarta finché i
    gruppi rimasti non fanno esattamente 64 caratteri.
    """
    maiuscolo = testo.upper()
    trovate: list[str] = []
    gruppi: list[str] = []
    fine = -1
    for m in _ESADECIMALE.finditer(maiuscolo):
        if fine < 0 or maiuscolo[fine:m.start()].strip():
            gruppi = []
        gruppi.append(m.group())
        fine = m.end()
        while sum(map(len, gruppi)) > 64:
            gruppi.pop(0)
        unito = "".join(gruppi)
        if len(unito) == 64:
            if re.search(r"[A-F]", unito) and unito not in trovate:
                trovate.append(unito)
            gruppi, fine = [], -1
    return trovate


def verifica(dati: bytes, nome: str, documenti: Iterable[dict[str, Any]]) -> EsitoRiepilogo:
    """``documenti``: [{nome, sha256, atteso}] dei file del fascicolo scelti per il deposito."""
    firma = tipo_firma(dati, nome)
    pdf = _pdf(dati, nome)
    if not pdf:
        return EsitoRiepilogo(firma, "", "", [], leggibile=False)
    try:
        testo = testo_pdf(pdf)
    except Exception:
        return EsitoRiepilogo(firma, "", "", [], leggibile=False)
    trovate = impronte(testo)
    compatto = re.sub(r"\s+", "", testo.upper())
    titolo = (_TITOLO.search(testo) or [None, ""])[1].strip()
    sede = (_SEDE.search(testo) or [None, ""])[1].strip()
    esito = EsitoRiepilogo(firma, titolo, sede, trovate)
    locali = set()
    for doc in documenti:
        impronta = str(doc.get("sha256") or "").upper()
        locali.add(impronta)
        esito.documenti.append({"nome": doc.get("nome", ""), "sha256": impronta, "atteso": bool(doc.get("atteso", True)),
                                "nelRiepilogo": bool(impronta) and impronta in compatto})
    esito.estranee = [h for h in trovate if h not in locali]
    return esito


__all__ = ["EsitoRiepilogo", "impronte", "testo_pdf", "verifica"]
