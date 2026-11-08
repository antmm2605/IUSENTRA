"""Rilevanza professionale di una notizia: regola dichiarata su tipo dell'atto ed emittente.

Tre livelli, mostrati in quest'ordine (a parità di livello, la più recente prima):
- ALTA: atti normativi primari (legge, decreto-legge, decreto legislativo, D.P.R.,
  atti del Ministero della Giustizia), pronunce (Corte costituzionale, Cassazione,
  Corte di giustizia UE, Corte EDU), direttive e regolamenti UE del Parlamento e
  del Consiglio, circolari, risoluzioni e risposte a interpello, avvisi del
  processo telematico;
- UTILE: decreti ministeriali e altri atti di autorità, D.P.C.M., delibere del
  Consiglio dei ministri, atti delegati UE, messaggi INPS, notizie del CNF, della
  Cassa Forense e del Garante, atti di promovimento davanti alla Consulta;
- SERVIZIO (nascosti se non si chiede «Mostra anche i comunicati di servizio»):
  comunicati degli enti in Gazzetta Ufficiale (tassi e cambi, autorizzazioni di
  medicinali, …), atti dell'Agenzia italiana del farmaco, regolamenti e decisioni
  di esecuzione UE, D.P.R. di scioglimento dei consigli comunali.

Per la Gazzetta Ufficiale il titolo del feed ha la forma ufficiale del sommario,
«[EMITTENTE - ]TIPO DELL'ATTO data[, n. numero]»: la regola legge emittente e tipo
da lì, mai parole sparse del testo. Per EUR-Lex si legge la denominazione dell'atto
nel titolo ufficiale («Regolamento di esecuzione (UE) …», «Direttiva (UE) … del
Parlamento europeo e del Consiglio»).
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from pct.notiziario import fonti as f

ALTA = 3
UTILE = 2
SERVIZIO = 1
ETICHETTE = {ALTA: "Rilevanza alta", UTILE: "Utile", SERVIZIO: "Comunicato di servizio"}

_GU_TIPO = re.compile(r"^(?P<tipo>[A-Z][A-Z'’\- ]*?)(?:\s+\d{1,2}\b.*)?$")
_GU_PRIMARI = {
    "LEGGE", "LEGGE COSTITUZIONALE", "DECRETO-LEGGE", "DECRETO LEGISLATIVO",
    "DECRETO DEL PRESIDENTE DELLA REPUBBLICA", "TESTO COORDINATO DEL DECRETO-LEGGE",
}
_GU_EMITTENTI_ALTI = ("MINISTERO DELLA GIUSTIZIA",)
_GU_EMITTENTI_SERVIZIO = ("AGENZIA ITALIANA DEL FARMACO",)
# Formula ufficiale del sommario per gli scioglimenti dei consigli comunali (D.P.R. di servizio).
_GU_DPR_SERVIZIO = re.compile(r"^Scioglimento del consiglio comunale|^Sostituzione del commissario straordinario", re.IGNORECASE)

_UE_ESECUZIONE = re.compile(r"^(?:Regolamento|Decisione) di esecuzione\b", re.IGNORECASE)
_UE_PRIMARI = re.compile(r"^(?:Regolamento|Direttiva|Decisione)\s*\(UE(?:,\s*Euratom)?\)\s*\d{4}/\d+\s+del Parlamento europeo e del Consiglio", re.IGNORECASE)
_UE_DIRETTIVA = re.compile(r"^Direttiva\b", re.IGNORECASE)
_ENTRATE_ALTA = re.compile(r"^(?:Interpello|Risposta|Circolare|Risoluzione|Principio di diritto)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Rilevanza:
    livello: int
    regola: str

    @property
    def etichetta(self) -> str:
        return ETICHETTE[self.livello]


def emittente_e_tipo(titolo: str) -> tuple[str, str]:
    """«PRESIDENZA … - DIPARTIMENTO … - COMUNICATO» → (emittente, «COMUNICATO»): il tipo è l'ultimo segmento."""
    parti = " ".join(str(titolo or "").split()).split(" - ")
    trovato = _GU_TIPO.match(parti[-1])
    tipo = (trovato.group("tipo") if trovato else parti[-1]).strip().upper()
    return " - ".join(parti[:-1]).strip().upper(), tipo


def _gazzetta(titolo: str, sintesi: str) -> Rilevanza:
    emittente, tipo = emittente_e_tipo(titolo)
    if any(emittente.startswith(e) for e in _GU_EMITTENTI_SERVIZIO):
        return Rilevanza(SERVIZIO, f"Gazzetta Ufficiale: atto di {emittente.title()}")
    if tipo == "COMUNICATO" or tipo.startswith("COMUNICATO "):
        return Rilevanza(SERVIZIO, "Gazzetta Ufficiale: comunicato di un ente")
    if not emittente and tipo in _GU_PRIMARI:
        if tipo == "DECRETO DEL PRESIDENTE DELLA REPUBBLICA" and _GU_DPR_SERVIZIO.search(sintesi.strip()):
            return Rilevanza(SERVIZIO, "Gazzetta Ufficiale: D.P.R. di scioglimento o commissariamento")
        return Rilevanza(ALTA, f"Gazzetta Ufficiale: {tipo.lower()}")
    if any(emittente.startswith(e) for e in _GU_EMITTENTI_ALTI):
        return Rilevanza(ALTA, "Gazzetta Ufficiale: atto del Ministero della Giustizia")
    return Rilevanza(UTILE, "Gazzetta Ufficiale: decreto o atto di un'autorità")


def _eurlex(titolo: str) -> Rilevanza:
    if _UE_ESECUZIONE.search(titolo):
        return Rilevanza(SERVIZIO, "EUR-Lex: atto di esecuzione della Commissione")
    if _UE_PRIMARI.search(titolo) or _UE_DIRETTIVA.search(titolo):
        return Rilevanza(ALTA, "EUR-Lex: atto legislativo dell'Unione")
    return Rilevanza(UTILE, "EUR-Lex: altro atto della Gazzetta UE")


def rilevanza(fonte_id: str, tipo: str, titolo: str, sintesi: str = "") -> Rilevanza:
    titolo = titolo or ""
    if fonte_id == "gu_serie_generale":
        return _gazzetta(titolo, sintesi or "")
    if fonte_id == "eurlex_gu_l":
        return _eurlex(titolo)
    if fonte_id == "entrate_prassi":
        if _ENTRATE_ALTA.search(titolo):
            return Rilevanza(ALTA, "Agenzia delle Entrate: circolare, risoluzione o interpello")
        return Rilevanza(UTILE, "Agenzia delle Entrate: provvedimento")
    if fonte_id == "inps_circolari":
        return Rilevanza(ALTA, "INPS: circolare")
    if tipo == f.PRONUNCIA:
        return Rilevanza(ALTA, "Pronuncia di una corte")
    if tipo == f.AVVISO_PCT:
        return Rilevanza(ALTA, "Avviso del processo telematico")
    if fonte_id == "giustizia":
        return Rilevanza(ALTA, "Ministero della Giustizia: decreto, circolare o provvedimento")
    return Rilevanza(UTILE, "Notizia o prassi di un ente istituzionale")


__all__ = ["ALTA", "ETICHETTE", "Rilevanza", "SERVIZIO", "UTILE", "rilevanza"]
