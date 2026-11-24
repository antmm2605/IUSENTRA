"""Lato della parte assistita: chi agisce (creditore, locatore, attore) o chi subisce (debitore, esecutato, conduttore
intimato, ingiunto, terzo).

Lo stesso oggetto (decreto ingiuntivo, precetto, pignoramento, sfratto) chiede strumenti opposti secondo il lato: il
creditore notifica il decreto, il debitore si oppone entro quaranta giorni; il creditore pignora, l'esecutato si oppone
(artt. 615, 617, 619 c.p.c.) o chiede la conversione (art. 495 c.p.c.). Qui si legge il lato dal testo e, per ogni famiglia
di strumenti, si sa quale regola risponde per ciascun lato.
"""
from __future__ import annotations

import re

from .norme import piano

ATTIVO, PASSIVO = "attivo", "passivo"

_PASSIVO = (r"(?:mi|ci|gli|le|lo|la) (?:hanno|ha|e stato|e stata|sono stati|sono state) (?:notificat|pignorat|citat|intimat|"
            r"sfrattat|ingiunt|chiest|bloccat|sequestrat)|ho ricevuto|abbiamo ricevuto|ha ricevuto|hanno ricevuto|"
            r"(?:mi|ci|gli|le) e (?:arrivat|stat[oa] notificat)|(?:mi|ci|gli|le) sono arrivat|siamo stati citati|sono stat[oa] citat|"
            r"contro di (?:me|noi|lui|lei)|debitor\w* esecutat|\besecutat[oa]\b|\bconvenut[oa]\b|\bintimat[oa]\b|\bingiunt[oa]\b|"
            r"opporc|oppormi|opporsi|vero proprietari|(?:fare|proporre|presentare|fatto|proposto) (?:l )?opposizion|difender|difenderci|difendermi|terzo proprietari|beni (?:miei|nostri|di mia proprieta)|"
            r"pignoramento subito|che si difende|assisto il debitore|assisto il conduttore|assisto l esecutato|di mia proprieta|"
            r"di nostra proprieta|sono (?:il|la) terz[oa]|(?:i beni|l auto|i mobili|la macchina) (?:sono|e) mi[eao]|sono miei|"
            r"pagare per evitare|evitare (?:la vendita|l asta|la vendita all asta)|conversione del pignoramento|"
            r"pignoramento (?:della|sulla|dello|sullo|del) (?:mia|mio) (?:casa|pensione|stipendio|conto|abitazione)|"
            r"(?:mi|ci|gli|le) (?:stanno|vogliono) pignorar|(?:al|alla) (?:mio |mia |nostro |nostra )?(?:cliente|assistit[oa]|societa) (?:e|sono) (?:arrivat|stat[oa] notificat)|"
            r"e arrivat\w* (?:un|una|il|la|lo) (?:decreto|precetto|pignorament|atto|intimazion|citazion|cartella|sfratt)")
_ATTIVO = (r"recuper\w* (?:il |un |del )?credit|recuper\w* (?:i soldi|le somme|il dovuto|quanto)|come (?:lo |li )?recuper|voglio (?:agire|fare causa|ottenere|chiedere|riavere|pignorare)|vogliamo (?:agire|pignorare|recuperare)|"
           r"possiamo pignorar|pignorargli|pignorarle|(?:non mi|non ci|non gli|non le) (?:paga|ha pagato|restituisce)|"
           r"il (?:mio |nostro )?debitore non|fattur\w* non pagat|non (?:ha|hanno) pagato|insolut|provvisori\w* esecuzion|"
           r"esecuzion\w* provvisori|devo (?:ricevere|incassare)|vant\w* un credito|creditor\w* (?:procedent|assistit)|"
           r"assisto il creditore|assisto il locatore|che agisce|far valere il credito|riavere (?:la casa|l immobile|i soldi)")

# Famiglie di strumenti con la regola di ripiego per ciascun lato (la prima regola dell'elenco che risponde per quel lato).
FAMIGLIE: dict[str, dict[str, tuple[str, ...]]] = {
    "monitorio": {ATTIVO: ("decreto_ingiuntivo", "notifica_decreto_ingiuntivo", "mon_ricorso_credito", "mon_provvisoria_esecuzione"),
                  PASSIVO: ("opposizione_decreto_ingiuntivo", "mon_opposizione_tardiva", "mon_opposizione_di")},
    "precetto": {ATTIVO: ("termini_precetto",),
                 PASSIVO: ("opposizione_precetto", "opposizione_atti_esecutivi", "es_opposizione_esecuzione")},
    "pignoramento": {ATTIVO: ("pignoramento_terzi", "es_pignoramento_terzi", "es_pignoramento_mobiliare",
                              "es_pignoramento_immobiliare", "ricerca_beni", "es_ricerca_beni"),
                     PASSIVO: ("es_opposizione_esecuzione", "opposizione_atti_esecutivi", "es_opposizione_terzo",
                               "es_conversione_pignoramento")},
    "sfratto": {ATTIVO: ("sfratto_morosita", "procedibilita_locazione", "negoziazione_locazione_inadatta", "rilascio",
                         "sfratto_finita_locazione"),
                PASSIVO: ("sanatoria_morosita", "opposizione_convalida", "opposizione_sfratto_commerciale")},
}
_FAMIGLIA_DI = {r: (fam, lato) for fam, lati in FAMIGLIE.items() for lato, regole in lati.items() for r in regole}


def lato_della_parte(testo: str) -> str | None:
    t = piano(testo)
    p, a = re.search(_PASSIVO, t) is not None, re.search(_ATTIVO, t) is not None
    if p and not a:
        return PASSIVO
    if a and not p:
        return ATTIVO
    return None


def famiglia(regola: str) -> tuple[str, str] | None:
    return _FAMIGLIA_DI.get(regola)


def regole_del_lato(fam: str, lato: str) -> tuple[str, ...]:
    return FAMIGLIE[fam][lato]


_GENERICA = r"cosa (?:fare|faccio|facciamo|possiamo fare|posso fare|devo fare|dobbiamo fare)|come (?:procedere|procedo|procediamo|ci muoviamo|mi muovo|agire|agiamo)|che fare|rimedi|quali (?:strade|azioni)|che (?:possibilita|tutele)"
_SCELTA = {"monitorio": ("assisto il creditore che ha chiesto o vuole chiedere il decreto ingiuntivo",
                         "assisto il debitore che ha ricevuto il decreto ingiuntivo"),
           "precetto": ("assisto il creditore che ha notificato il precetto", "assisto il debitore che ha ricevuto il precetto"),
           "pignoramento": ("assisto il creditore che vuole pignorare", "assisto il debitore o il terzo che ha subito il pignoramento"),
           "sfratto": ("assisto il locatore che agisce", "assisto il conduttore che si difende")}


def scelte_sul_lato(domanda: str, regola: str) -> list[str] | None:
    """Due domande complete (lato attivo e lato passivo) se il lato non si capisce e la domanda è generica."""
    fam = famiglia(regola)
    # Le regole di difesa si riconoscono già da parole della difesa (opposizione tardiva, sanatoria): si chiede solo
    # quando ha vinto lo strumento di chi agisce senza che il testo dica chi si assiste.
    if fam is None or fam[1] == PASSIVO or lato_della_parte(domanda) is not None or not re.search(_GENERICA, piano(domanda)):
        return None
    attivo, passivo = _SCELTA[fam[0]]
    base = domanda.strip()
    return [f"{base} ({attivo})", f"{base} ({passivo})"]
