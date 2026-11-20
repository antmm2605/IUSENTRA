"""Processo amministrativo, tributario e penale: i termini principali che grava sullo studio, dal testo degli atti.

Gli atti si riconoscono dal testo (formula dell'atto impugnabile o del provvedimento) e il termine decorre dalla data
di notificazione o comunicazione **scritta negli atti** («notificato il …», «comunicata in data …»). Senza quella
data il termine non si inventa: la conclusione dice che cosa manca. Il computo è quello del motore unico dei termini
(``pct/termini_riti.py`` in ``pct/termini_processuali.py``): sospensione feriale (art. 1 l. 742/1969; art. 54 c.p.a.),
niente proroga del sabato nel penale (art. 172 c.p.p.).

Norme: artt. 29, 45, 92, 120 c.p.a.; artt. 21, 22, 51 D.Lgs. 546/1992; art. 6 D.Lgs. 218/1997; artt. 408, 461 c.p.p.
(testi letti nell'archivio Normattiva del software il 19-20/11/2026).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator

from ..modello import Conclusione, Dubbio, Fonte
from ..norme import norme
from ..testo import data_it, date_nel_testo, pulito, semplice
from .calcolo import esito
from .contesto import Contesto

_CALCOLATORE = ItalianDeadlineCalculator()
_MODELLI = {t.code: t for t in DEFAULT_TEMPLATES}
_NOTIFICA = re.compile(r"(?:notificat[oaie]|comunicat[oaie]|ricevut[oaie])(?:\s+a\s+mezzo\s+pec)?(?:\s+in\s+data|\s+il|\s+in)?\s*$")


@dataclass(frozen=True)
class Regola:
    rito: str
    codice: str
    riconosce: str  # espressione sul testo dell'atto
    modello: str
    cosa: str
    come: str
    perche: str
    norme: tuple[str, ...]
    escludi: str = ""


REGOLE: tuple[Regola, ...] = (
    Regola("tributario", "ricorso_tributario", r"avviso di accertamento|avviso di rettifica|cartella di pagamento|atto di recupero|avviso di liquidazione",
           "TRIB_RICORSO_21", "Proporre ricorso alla Corte di giustizia tributaria di primo grado",
           "notifica del ricorso all'ente impositore e, entro trenta giorni, costituzione in giudizio (art. 22)",
           "oltre il termine il ricorso è inammissibile e l'atto diventa definitivo", ("dlgs546_art21", "dlgs546_art22")),
    Regola("tributario", "appello_tributario", r"\bsentenza\b.{0,400}corte di giustizia tributaria|corte di giustizia tributaria.{0,400}\bsentenza\b",
           "TRIB_APPELLO_51", "Valutare l'appello alla Corte di giustizia tributaria di secondo grado",
           "ricorso in appello notificato alla controparte (art. 53 D.Lgs. 546/1992)",
           "scaduto il termine la sentenza passa in giudicato", ("dlgs546_art51",)),
    Regola("amministrativo", "ricorso_tar_appalti", r"aggiudicazion\w*|procedura di affidamento|codice dei contratti",
           "AMM_APPALTI_120", "Proporre ricorso al TAR contro l'aggiudicazione",
           "ricorso notificato all'amministrazione e ad almeno un controinteressato, poi deposito entro trenta giorni (art. 45)",
           "il termine è di decadenza: scaduto, l'atto non si può più impugnare", ("cpa_120", "cpa_45"), escludi=r"\bsentenza\b"),
    Regola("amministrativo", "ricorso_tar", r"\b(?:provvedimento|ordinanza|determina\w*|decreto)\b.{0,200}\b(?:si comunica|si notifica|notificat\w*)",
           "AMM_RICORSO_29", "Proporre ricorso al TAR per l'annullamento",
           "ricorso notificato all'amministrazione e ad almeno un controinteressato, poi deposito entro trenta giorni (art. 45)",
           "il termine è di decadenza: scaduto, l'atto non si può più impugnare", ("cpa_29", "cpa_45"),
           escludi=r"\bsentenza\b|aggiudicazion"),
    Regola("amministrativo", "appello_consiglio_di_stato", r"\bsentenza\b.{0,600}tribunale amministrativo regionale|tribunale amministrativo regionale.{0,600}\bsentenza\b",
           "AMM_APPELLO_92", "Valutare l'appello al Consiglio di Stato",
           "ricorso in appello notificato alle parti e depositato (artt. 94 e 45 c.p.a.)",
           "scaduto il termine la sentenza diventa definitiva", ("cpa_92",)),
    Regola("penale", "opposizione_decreto_penale", r"decreto penale di condanna",
           "PEN_OPPOSIZIONE_DECRETO_461", "Valutare l'opposizione al decreto penale di condanna",
           "dichiarazione di opposizione nella cancelleria del giudice che ha emesso il decreto (art. 461 c.p.p.)",
           "senza opposizione il decreto diventa esecutivo", ("cpp_461",)),
    Regola("penale", "opposizione_archiviazione", r"richiesta di archiviazione",
           "PEN_OPPOSIZIONE_ARCHIVIAZIONE_408", "Valutare l'opposizione alla richiesta di archiviazione",
           "atto di opposizione con l'oggetto dell'investigazione suppletiva e i relativi elementi di prova (art. 410 c.p.p.)",
           "senza opposizione il giudice può archiviare senza udienza", ("cpp_408",)),
)


def _data_notifica(testo: str) -> date | None:
    for inizio, _fine, valore in date_nel_testo(testo):
        if _NOTIFICA.search(semplice(testo[max(0, inizio - 60):inizio])):
            return valore
    return None


def _scadenza(regola: Regola, dal: date, testo: str) -> tuple[date | None, str]:
    modello = _MODELLI[regola.modello]
    if regola.codice == "opposizione_archiviazione" and re.search(r"violenza alla persona|624-bis", semplice(testo)):
        modello = _MODELLI["PEN_OPPOSIZIONE_ARCHIVIAZIONE_408_VIOLENZA"]
    calcolo = _CALCOLATORE.calculate_template(dal, modello)
    return date.fromisoformat(calcolo["deadline"]), f"{modello.base_value} {'mesi' if modello.period_type == 'months' else 'giorni'} " \
        f"dal {data_it(dal.isoformat())}; {calcolo.get('explanation', '')[:300]}"


def conclusioni_riti_non_civili(ctx: Contesto) -> list[Conclusione]:
    if ctx.rito.codice not in {"amministrativo", "tributario", "penale"}:
        return []
    esiti: list[Conclusione] = []
    visti: set[str] = set()
    # Il ricorso già proposto dallo studio chiude il termine per proporlo: non si chiede di nuovo.
    ricorso_proposto = any(a.dello_studio and a.natura == "atto_principale" for a in ctx.della_causa())
    for atto in sorted(ctx.della_causa(), key=lambda a: a.data or ""):
        if atto.dello_studio or atto.natura in {"atto_principale", "atto_difensivo"}:
            continue  # gli atti di parte citano l'atto impugnato: non sono l'atto da cui decorre il termine
        testo = semplice(atto.testo or "")
        for regola in REGOLE:
            if regola.rito != ctx.rito.codice or regola.codice in visti or not re.search(regola.riconosce, testo):
                continue
            if ricorso_proposto and regola.codice.startswith("ricorso_"):
                continue
            if regola.escludi and re.search(regola.escludi, testo):
                continue
            visti.add(regola.codice)
            fonte = Fonte(atto.id, atto.nome, pulito((atto.testo or "")[:400]), atto.data)
            dal = _data_notifica(atto.testo or "")
            if dal is None:
                esiti.append(Conclusione(
                    regola.codice, regola.cosa, fonte, norme(*regola.norme), regola.come, regola.perche, "dubbio",
                    onerato="noi", motivo_senza_termine="manca la data di notificazione o comunicazione dell'atto",
                    dubbi=[Dubbio("decorrenza_ignota", "Il termine decorre dalla notificazione o comunicazione dell'atto.",
                                  "la data di notificazione (relata, ricevuta PEC, avviso di ricevimento)", fonte)]))
                continue
            scadenza, computo = _scadenza(regola, dal, atto.testo or "")
            termine = esito(scadenza, oggi=ctx.oggi, perentorio=True, decorrenza=dal.isoformat(),
                            evento="notificazione o comunicazione dell'atto", computo=computo, rito=ctx.rito,
                            conseguenze=regola.perche)
            esiti.append(Conclusione(regola.codice, regola.cosa, fonte, norme(*regola.norme), regola.come, regola.perche,
                                     "da_fare", onerato="noi", termine=termine))
    return esiti


__all__ = ["REGOLE", "conclusioni_riti_non_civili"]
