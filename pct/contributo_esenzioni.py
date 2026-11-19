"""Le esenzioni dal contributo unificato nella volontaria giurisdizione, prima dell'importo dell'art. 13.

L'art. 13, comma 1, lett. b), D.P.R. 115/2002 (€ 98 per la volontaria giurisdizione) si applica solo se il processo non
è esente. Testi vigenti nell'archivio Normattiva del software, letti il 18/11/2026:

- art. 10, comma 1, D.P.R. 115/2002: non è soggetto al contributo il processo già esente, per legge, dall'imposta di
  bollo o da ogni spesa, tassa o diritto. Vi rientrano la procedura della tutela (art. 46 disp. att. c.c.: «Tutti gli
  atti della procedura della tutela … sono esenti da tasse di bollo e di registro») e le procedure di adozione dei
  minori (art. 82 L. 184/1983: esenti «da ogni spesa, tassa e diritto»);
- art. 10, comma 2: non è soggetto al contributo il processo «comunque riguardante» la prole: le istanze al giudice
  tutelare per i figli minori (art. 320 c.c.), secondo la circolare del Ministero della Giustizia DAG del 16/05/2024,
  prot. m_dg.DAG.16/05/2024.0104395.U («Istanze rivolte al giudice tutelare ai sensi degli artt. 320 e 374 c.c. –
  pagamento importo forfettario ex art. 30»);
- art. 10, comma 3 (testo del D.Lgs. 164/2024, per i procedimenti introdotti dopo il 28/02/2023): non sono soggetti
  al contributo i processi del libro II, titolo IV-bis, capo III, sezioni III, IV e V c.p.c.: interdizione,
  inabilitazione e amministrazione di sostegno (artt. 473-bis.52 – 473-bis.58), assenza e morte presunta
  (artt. 473-bis.59 – 473-bis.63), provvedimenti relativi ai minori, agli interdetti e agli inabilitati
  (artt. 473-bis.64 – 473-bis.66);
- art. 46-bis disp. att. c.c.: i procedimenti del titolo XII del libro I c.c. (amministrazione di sostegno,
  interdizione, inabilitazione) sono esenti dal contributo unificato;
- art. 10, comma 6: la ragione dell'esenzione deve risultare da apposita dichiarazione nelle conclusioni dell'atto
  introduttivo;
- art. 30: l'anticipazione forfettaria di € 27 la versa chi deposita il ricorso introduttivo, anche nei processi esenti
  dal contributo. Per la circolare DAG del 16/05/2024 è dovuta quando l'istanza investe il giudice tutelare ex novo
  con un procedimento autonomo (art. 320 c.c.), non quando è incidentale a una tutela già aperta (art. 374 c.c.).

La natura del procedimento viene dal codice oggetto PST (catalogo ministeriale XSD) e, per le voci generiche
(«Altri procedimenti», «Altri istituti di competenza del giudice tutelare»), dal testo dell'istanza. Modulo puro.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

NORMA_PROLE = "art. 10, comma 2, D.P.R. 115/2002"
NORMA_TUTELA = "art. 10, comma 1, D.P.R. 115/2002 e art. 46 disp. att. c.c."
NORMA_ADOZIONE = "art. 10, comma 1, D.P.R. 115/2002 e art. 82 L. 184/1983"
NORMA_PROTEZIONE = "art. 10, comma 3, D.P.R. 115/2002 e art. 46-bis disp. att. c.c."
NORMA_ASSENZA = "art. 10, comma 3, D.P.R. 115/2002"
CIRCOLARE_DAG = "circolare del Ministero della Giustizia DAG del 16/05/2024, prot. m_dg.DAG.16/05/2024.0104395.U"

# Anticipazione forfettaria (art. 30): dovuta per il ricorso che apre un procedimento autonomo, non per l'istanza
# incidentale a una tutela già aperta (circolare DAG del 16/05/2024).
DOVUTA, NON_DOVUTA = "dovuta", "non_dovuta"


@dataclass(frozen=True)
class Esenzione:
    norma: str
    motivo: str
    anticipazione: str  # dovuta, non_dovuta
    motivo_anticipazione: str
    dichiarazione: bool | None = None  # art. 10, comma 6: True letta, False assente nei testi letti, None senza testi


_PROLE = {
    "413001": "rappresentanza e atti di straordinaria amministrazione dei beni dei figli minori (art. 320 c.c.)",
    "413002": "nomina del curatore speciale del minore (artt. 320 e 321 c.c.)",
    "413003": "vigilanza del giudice tutelare sull'amministrazione dei beni dei figli (art. 337 c.c.)",
    "413018": "vigilanza sui minori",
    "411688": "nomina del curatore speciale del minore",
    "411689": "cognome del figlio minorenne (art. 262 c.c.)",
    "412502": "cognome del figlio minorenne (art. 262 c.c.)",
    "412501": "ammissione al matrimonio del minore (art. 84 c.c.)",
    "412421": "affidamento dei minori",
    "413020": "interruzione volontaria di gravidanza della minore (art. 12 L. 194/1978)",
    "413030": "affidamento familiare del minore (art. 4 L. 184/1983)",
    "412701": "autorizzazione dei genitori a seguito del minore (art. 31 D.Lgs. 286/1998)",
    "412702": "accertamento dell'età del minore (art. 19-bis D.Lgs. 142/2015)",
}
# Procedura della tutela: l'apertura è il procedimento autonomo; gli atti successivi sono incidentali.
_TUTELA_APERTURA = {"413010": "apertura della tutela (art. 343 c.c.)"}
_TUTELA_INCIDENTALI = {
    "413011": "provvedimenti urgenti prima dell'assunzione delle funzioni del tutore (art. 361 c.c.)",
    "413012": "nomina per la formazione dell'inventario della tutela (art. 363 c.c.)",
    "413013": "provvedimenti sull'educazione e sui beni del minore in tutela (art. 371 c.c.)",
    "413014": "autorizzazioni del giudice tutelare nella tutela (artt. 372, 373 e 374 c.c.)",
}
_PROTEZIONE = {
    "413061": "amministrazione di sostegno (artt. 404 ss. c.c.)",
    "412601": "interdizione o inabilitazione (artt. 414 ss. c.c.)",
}
_ASSENZA = {"400220": "dichiarazione di assenza o di morte presunta", "411682": "dichiarazione di assenza o di morte presunta"}

_RE_ADOZIONE_MINORI = re.compile(r"\bL\.?\s*n?\.?\s*184/1983\b|adottabilit|affidamento preadottivo|adozione", re.I)
_RE_GENITORI = re.compile(r"genitor\w*\s+esercent\w*|responsabilit[aà]\s+genitoriale|potest[aà]\s+(?:genitoriale\s+)?sul\s+(?:figlio\s+)?minor|art\.?\s*320\s*c\.?\s*c", re.I)
_RE_GT = re.compile(r"giudice\s+tutelare", re.I)
_RE_MINORE = re.compile(r"\bminor[ei]\w*\b|\bfigli[oa]?\s+minor|art\.?\s*320\s*c\.?\s*c|\bprole\b", re.I)
_RE_PROTEZIONE = re.compile(r"amministra(?:zione|tore|trice)\s+di\s+sostegno|\binterdizion|\binabilitazion|\binterdett|\binabilitat", re.I)
_RE_TUTELA_APERTA = re.compile(r"\btutor[ei]\b|\btutela\s+(?:n\.|r\.?g\.?|aperta|del\s+minore)", re.I)
_RE_DICHIARAZIONE = re.compile(
    r"(?:esent\w*|esenzion\w*|non\s+(?:è\s+|e'\s+)?(?:soggett\w+|dovut\w*)|art\.?\s*10)[^.]{0,120}contributo\s+unificato"
    r"|contributo\s+unificato[^.]{0,120}(?:esent\w*|esenzion\w*|non\s+(?:è\s+|e'\s+)?dovut\w*|art\.?\s*10)", re.I)


def _dichiarazione(testi: list[str]) -> bool | None:
    letti = [t for t in testi if t]
    if not letti:
        return None
    return any(_RE_DICHIARAZIONE.search(" ".join(t.split())) for t in letti)


def esenzione_volontaria(*, codice_oggetto: str = "", descrizione: str = "", testi: Iterable[str] = ()) -> Esenzione | None:
    """L'esenzione dal contributo del procedimento di volontaria giurisdizione, o None se il contributo è dovuto.

    ``descrizione`` è la voce del catalogo PST; ``testi`` sono i testi già letti degli atti della causa (istanza,
    ricorso): servono per le voci generiche e per la dichiarazione dell'art. 10, comma 6.
    """
    codice = str(codice_oggetto or "").strip()
    voce = " ".join(str(descrizione or "").split())
    testi = [str(t or "") for t in testi]
    dichiarazione = _dichiarazione(testi)
    autonomo = ("il ricorso apre un procedimento autonomo davanti al giudice: l'anticipazione forfettaria è dovuta "
                f"(art. 30 D.P.R. 115/2002; {CIRCOLARE_DAG})")
    incidentale = ("l'istanza è incidentale a una procedura già aperta: l'anticipazione forfettaria non è dovuta "
                   f"({CIRCOLARE_DAG})")
    unito = " ".join(" ".join(t.split()) for t in testi)
    if _RE_GENITORI.search(unito) and _RE_MINORE.search(unito):
        # I genitori che chiedono al giudice tutelare di compiere atti per il figlio minore agiscono ex art. 320 c.c.,
        # qualunque voce del catalogo abbiano scelto: processo riguardante la prole, procedimento autonomo.
        return Esenzione(NORMA_PROLE, "processo riguardante la prole: istanza dei genitori al giudice tutelare per il "
                         "figlio minore (art. 320 c.c.)", DOVUTA, autonomo, dichiarazione)
    if codice in _PROLE:
        return Esenzione(NORMA_PROLE, f"processo riguardante la prole: {_PROLE[codice]}", DOVUTA, autonomo, dichiarazione)
    if codice in _TUTELA_APERTURA:
        return Esenzione(NORMA_TUTELA, f"procedura della tutela: {_TUTELA_APERTURA[codice]}", DOVUTA, autonomo, dichiarazione)
    if codice in _TUTELA_INCIDENTALI:
        return Esenzione(NORMA_TUTELA, f"procedura della tutela: {_TUTELA_INCIDENTALI[codice]}", NON_DOVUTA, incidentale,
                         dichiarazione)
    if codice in _PROTEZIONE:
        return Esenzione(NORMA_PROTEZIONE, f"misura di protezione: {_PROTEZIONE[codice]}", DOVUTA, autonomo, dichiarazione)
    if codice in _ASSENZA:
        return Esenzione(NORMA_ASSENZA, f"{_ASSENZA[codice]} (artt. 473-bis.59 ss. c.p.c.)", DOVUTA, autonomo, dichiarazione)
    if codice.startswith("4123") and _RE_ADOZIONE_MINORI.search(voce):
        return Esenzione(NORMA_ADOZIONE, f"procedura di adozione di minori: {voce}", DOVUTA, autonomo, dichiarazione)
    # Voci generiche o assenti: decide il testo dell'istanza, solo se è inequivoco.
    if _RE_PROTEZIONE.search(voce) or (_RE_GT.search(unito) and _RE_PROTEZIONE.search(unito)):
        aperta = bool(re.search(r"\bnominat\w*\s+amministrat\w+\s+di\s+sostegno|\bamministratore\s+di\s+sostegno\s+(?:del|della)\b",
                                unito, re.I))
        return Esenzione(NORMA_PROTEZIONE, "misura di protezione (amministrazione di sostegno, interdizione o inabilitazione)",
                         NON_DOVUTA if aperta else DOVUTA, incidentale if aperta else autonomo, dichiarazione)
    if re.search(r"\bminor|\bfigli|\bprole\b", voce, re.I) or (_RE_GT.search(unito) and _RE_MINORE.search(unito)):
        if _RE_TUTELA_APERTA.search(unito) and not re.search(r"art\.?\s*320", unito, re.I):
            return Esenzione(NORMA_TUTELA, "istanza nella tutela del minore", NON_DOVUTA, incidentale, dichiarazione)
        return Esenzione(NORMA_PROLE, "processo riguardante la prole: istanza al giudice tutelare per il minore", DOVUTA,
                         autonomo, dichiarazione)
    return None


@lru_cache(maxsize=1)
def _descrizioni_pst() -> dict[str, str]:
    percorso = Path(__file__).resolve().parent / "data" / "cataloghi" / "codici_oggetto_pst.json"
    try:
        voci = json.loads(percorso.read_text(encoding="utf-8")).get("records") or []
    except (OSError, ValueError, AttributeError):
        return {}
    return {str(v.get("codice")): str(v.get("descrizione") or "") for v in voci if isinstance(v, dict) and v.get("codice")}


def descrizione_codice(codice: str) -> str:
    """La voce del catalogo ministeriale dei codici oggetto PST (XSD versionati)."""
    return _descrizioni_pst().get(str(codice or "").strip(), "")


def _euro(valore: float) -> str:
    testo = f"{valore:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"€ {testo}"


def confronto_esente(esenzione: Esenzione, versati: Iterable[object]) -> dict[str, object]:
    """Il confronto del contributo quando il processo è esente: che cosa è dovuto e che cosa risulta versato.

    Esito ``esente_per_legge``; ``dubbio`` è il dubbio vero che resta (dichiarazione dell'art. 10, comma 6, assente
    nei testi letti; anticipazione dovuta senza ricevuta), stringa vuota se tutto torna.
    """
    letti = sorted({round(float(v), 2) for v in versati if v not in (None, "") and float(v) > 0})
    anticipazione = 27.0 in letti
    altri = [v for v in letti if v != 27.0]
    parti = [f"Contributo unificato non dovuto ({esenzione.norma}): {esenzione.motivo}"]
    dubbi = []
    if esenzione.anticipazione == DOVUTA:
        if anticipazione:
            parti.append("versati € 27,00 = anticipazione forfettaria dovuta (art. 30 D.P.R. 115/2002), corretto")
        else:
            parti.append("anticipazione forfettaria di € 27,00 dovuta (art. 30 D.P.R. 115/2002)")
            dubbi.append("non risulta la ricevuta dell'anticipazione forfettaria di € 27,00 (art. 30 D.P.R. 115/2002)")
    else:
        parti.append("anticipazione forfettaria non dovuta: " + esenzione.motivo_anticipazione)
        if anticipazione:
            parti.append("i € 27,00 versati non erano dovuti")
    if altri:
        parti.append(f"risultano versati anche {', '.join(_euro(v) for v in altri)}, non dovuti come contributo")
    if esenzione.dichiarazione is False:
        dubbi.append("la ragione dell'esenzione non risulta dichiarata nelle conclusioni dell'atto introduttivo "
                     "(art. 10, comma 6, D.P.R. 115/2002)")
    return {"esito": "esente_per_legge", "norma": esenzione.norma, "versato": 27.0 if anticipazione else None,
            "dovuto": 0.0, "motivo": esenzione.motivo, "anticipazione": esenzione.anticipazione,
            "dettaglio": "; ".join(parti) + ".", "dubbio": "; ".join(dubbi)}


__all__ = ["CIRCOLARE_DAG", "confronto_esente", "descrizione_codice", "DOVUTA", "Esenzione", "NON_DOVUTA", "NORMA_PROLE", "esenzione_volontaria"]
