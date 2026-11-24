"""Lato della parte assistita: chi agisce (creditore, locatore, attore, lavoratore, condomino, danneggiato, consumatore)
o chi subisce (debitore, esecutato, conduttore intimato, ingiunto, terzo, datore convenuto, condominio convenuto,
responsabile del sinistro, venditore, locatore a cui si chiede la restituzione).

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
# Famiglie in cui il lato è un ruolo (lavoratore o datore, condomino o condominio, danneggiato o responsabile, consumatore
# o venditore, conduttore o locatore): lo strumento cambia solo dove cambia il rimedio, il termine o il giudice.
FAMIGLIE.update({
    # Lavoratore: impugnazione (60 + 180 giorni, art. 6 l. 604/1966), ricorso e crediti; datore: memoria dell'art. 416 c.p.c.
    "lavoro": {ATTIVO: ("impugnazione_licenziamento", "crediti_lavoro", "lav_crediti", "lav_tfr", "lav_ricorso_414",
                        "lav_mobbing_demansionamento"),
               PASSIVO: ("difesa_datore_lavoro",)},
    # Condomino: impugnazione della delibera (art. 1137 c.c.); condominio convenuto: art. 1131 c.c. e mediazione.
    "condominio": {ATTIVO: ("impugnazione_delibera", "dr_revoca_amministratore"), PASSIVO: ("difesa_condominio",)},
    # Danneggiato: richiesta all'assicuratore (artt. 145 e 148 d.lgs. 209/2005); responsabile: artt. 1913 e 1917 c.c.
    "sinistro": {ATTIVO: ("sinistro_stradale", "rc_sinistro", "rc_negoziazione_sinistri"), PASSIVO: ("sinistro_responsabile",)},
    # Consumatore: rimedi dell'art. 135-bis cod. consumo; venditore: regresso entro un anno (art. 134 cod. consumo).
    "garanzia": {ATTIVO: ("garanzia_conformita", "cons_garanzia"), PASSIVO: ("garanzia_venditore",)},
    # Conduttore: restituzione entro sei mesi dalla riconsegna (art. 13 l. 431/1998); locatore: eccezione di decadenza.
    "canone": {ATTIVO: ("restituzione_canone_non_registrato", "loc_canone_nero"), PASSIVO: ("locatore_canone_nero",)},
})
_FAMIGLIA_DI = {r: (fam, lato) for fam, lati in FAMIGLIE.items() for lato, regole in lati.items() for r in regole}

# Ruoli per famiglia (testo senza accenti e apostrofi, come da piano()): (chi agisce, chi subisce).
_CLIENTE = r"(?:il |la )?(?:mio |mia |nostro |nostra )?(?:client\w*|assistit\w*)"
RUOLI: dict[str, tuple[str, str]] = {
    "lavoro": (
        r"\b(?:sono|ero|e|era) (?:un[ao]? |una )?(?:lavorat|dipendent|operai|impiegat|commess|camerier|badante|colf|"
        r"apprendist|autista|magazzinier)|mi (?:hanno|ha) licenziat|sono stat[oa] licenziat|" + _CLIENTE + r" (?:e stat[oa] "
        r"licenziat|e (?:un[ao]? |una )?(?:lavorat|dipendent|operai|impiegat))|(?:il|la) (?:mio|mia) (?:ex )?(?:datore|"
        r"datrice|titolare|capo|azienda)|assisto (?:il|la|un|una) (?:lavorat|dipendent)|non mi (?:pagano|hanno pagato|paga|ha "
        r"pagato) (?:lo stipendio|gli (?:ultimi )?stipendi|il tfr|gli straordinari|la tredicesima)|(?:il|l) (?:ex )?datore"
        r"(?: di lavoro)? (?:non )?mi\b|mi (?:deve|devono) (?:lo stipendio|gli stipendi|il tfr)|(?:mi sono|sono) dimess",
        r"assisto (?:il|la|l) (?:datore|datrice|azienda|societa datrice|impresa)|(?:sono|siamo) (?:il|la|i|l) "
        r"(?:datore|datrice|titolar|amministrator\w* unic|legale rappresentant)|(?:ho|abbiamo|ha) licenziato (?:un|una|il|la|l)|"
        r"(?:un|una|il|la|l|un mio|una mia|il mio|la mia|un nostro|una nostra) (?:ex )?(?:dipendent|lavorat|operai|commess|"
        r"impiegat|camerier|apprendist|autista|magazzinier)\w*[^.]{0,80}(?:mi|ci|gli|le) (?:ha|hanno) (?:impugnat|fatto "
        r"causa|notificat|citat|chiest|contestat|denunciat|mandat|inviat)|(?:ricorso|impugnazione|lettera)[^.]{0,30}(?:del|di "
        r"un|di una|della|dell) (?:mio |mia |nostro |nostra )?(?:ex )?(?:dipendent|lavorat|operai|camerier|commess)"),
    "condominio": (
        r"\b(?:sono|e) (?:un[ao]? |una )?condomin|assisto (?:un|una|il|la) condomin|" + _CLIENTE + r",? (?:e )?condomin|"
        r"(?:ho|ha|abbiamo) votato contro|(?:ero|era|eravamo) assent\w* all assemblea|(?:mi sono|si e) astenut",
        r"(?:sono|faccio) l amministrat|amministro (?:il|un|lo|questo) (?:condomin|stabile|palazzo)|assisto (?:il|l) "
        r"(?:condominio|amministrat)|(?:un|il|la|una|alcuni) condomin\w*[^.]{0,80}(?:ha|hanno) (?:impugnat|fatto causa|citat|"
        r"notificat|avviato la mediazione|chiesto la revoca|depositato)|citazione contro il condominio|contro il condominio|"
        r"(?:il|al) condominio (?:e stato citato|ha ricevuto|e convenuto)"),
    "sinistro": (
        r"(?:sono|e) stat[oa] (?:tamponat|investit|urtat)|mi (?:hanno|ha) (?:tamponat|investit|urtat)|" + _CLIENTE +
        r" (?:e stat[oa] (?:tamponat|investit|urtat)|ha subito)|ho subito (?:un|il) (?:sinistro|incidente|tamponamento|danno)|"
        r"assisto il danneggiat|(?:voglio|vogliamo|vuole) (?:chiedere|ottenere) (?:il )?risarciment",
        r"\b(?:ho|abbiamo) (?:tamponat|investit|urtat)|(?:ho|abbiamo|ha) causato (?:un|l|il) (?:incidente|sinistro|"
        r"tamponamento)|per colpa mia|" + _CLIENTE + r" ha (?:tamponat|investit|urtat|causato)|assisto (?:il|la) "
        r"(?:responsabil|conducente responsabil|assicurat)|(?:mi|ci|gli|le) (?:chiede|chiedono|ha chiesto|hanno chiesto|"
        r"pretende) (?:il |un )?(?:risarciment|i danni|danni|\d)"),
    "garanzia": (
        r"\b(?:ho|abbiamo) (?:comprato|acquistato)|" + _CLIENTE + r" ha (?:comprato|acquistato)|(?:sono|e) (?:un[ao]? |una )?"
        r"consumator|assisto (?:il|un|la|una) consumator|\b(?:comprat|acquistat)[oaie] (?:da|dal|dalla|dallo|in|nel|nella|al|"
        r"alla|online|on line|su)\b",
        r"(?:il|nel|al|dal) (?:mio|nostro) (?:negozio|punto vendita|e commerce|sito|concessionari)|(?:ho|abbiamo) (?:un|una) "
        r"(?:negozio|punto vendita|concessionari|ferramenta|rivendita)|(?:ho|abbiamo) vendut|(?:sono|siamo) (?:il|la|i) "
        r"(?:venditor|rivenditor)|assisto (?:il|la|un|una) (?:venditor|rivenditor|negozio|concessionari)|(?:un|una) "
        r"(?:cliente|acquirente|consumator\w*)[^.]{0,80}(?:\bpretende\b|\breclama\b|\bcontesta\b|(?:ci|mi|ce lo|me lo) "
        r"(?:chiede|ha chiesto)\b)"),
    "canone": (
        r"\b(?:sono|ero) (?:l |il |la |un |una )?(?:ex )?(?:inquilin|conduttor|affittuari)|" + _CLIENTE + r",? (?:ex )?"
        r"(?:inquilin|conduttor)|assisto (?:il|la|l) (?:ex )?(?:conduttor|inquilin)|(?:ho|abbiamo) pagato (?:in nero|oltre)|"
        r"pagavo|pagavamo",
        r"\b(?:sono|ero) (?:il|la) (?:proprietari|locator|padron)|assisto (?:il|la) (?:locator|proprietari)|(?:l|il|la|un|una) "
        r"(?:ex )?(?:inquilin|conduttor)\w*[^.]{0,80}(?:mi|ci|gli|le) (?:chiede|chiedono|ha chiesto|pretende|reclama|ha fatto "
        r"causa|ha citato|ha notificato)|(?:ho|abbiamo) affittat|(?:il )?(?:mio|nostro) (?:ex )?inquilin"),
}
# Ruoli di chi agisce o subisce nella locazione, usati per lo sfratto quando le formule generali non bastano.
_SFRATTO = (r"assisto (?:il|la) (?:locator|proprietari)|\b(?:sono|siamo) (?:il|la|i) (?:proprietari|locator)|(?:il )?(?:mio|"
            r"nostro) inquilin|(?:ho|abbiamo) affittat",
            r"\b(?:sono|siamo) (?:l |il |la |un |una |gli )?(?:inquilin|conduttor|affittuari)|assisto (?:il|la|l) "
            r"(?:conduttor|inquilin)|(?:il|la) (?:mio|mia) (?:proprietari|padron)\w* di casa|(?:il|la) (?:proprietari|"
            r"locator|padron)\w*[^.]{0,40}(?:mi|ci|gli|le) (?:ha|hanno) (?:intimat|notificat|citat|mandat)")


def _ruolo(t: str, attivo: str, passivo: str) -> str | None:
    p, a = re.search(passivo, t) is not None, re.search(attivo, t) is not None
    if p and not a:
        return PASSIVO
    if a and not p:
        return ATTIVO
    return None


def lato_della_parte(testo: str, fam: str | None = None) -> str | None:
    """Lato della parte assistita. Nelle famiglie a ruoli (RUOLI) decidono solo le formule del ruolo: «ho ricevuto la
    lettera di licenziamento» è il lavoratore che agisce, non chi subisce la causa."""
    t = piano(testo)
    if fam in RUOLI:
        return _ruolo(t, *RUOLI[fam])
    generale = _ruolo(t, _ATTIVO, _PASSIVO)
    if generale is None and fam == "sfratto":
        return _ruolo(t, *_SFRATTO)
    return generale


def famiglia(regola: str) -> tuple[str, str] | None:
    return _FAMIGLIA_DI.get(regola)


def regole_del_lato(fam: str, lato: str) -> tuple[str, ...]:
    return FAMIGLIE[fam][lato]


_GENERICA = r"cosa (?:fare|faccio|facciamo|possiamo fare|posso fare|devo fare|dobbiamo fare)|come (?:procedere|procedo|procediamo|ci muoviamo|mi muovo|agire|agiamo)|che fare|rimedi|quali (?:strade|azioni)|che (?:possibilita|tutele)"
_SCELTA = {"monitorio": ("assisto il creditore che ha chiesto o vuole chiedere il decreto ingiuntivo",
                         "assisto il debitore che ha ricevuto il decreto ingiuntivo"),
           "precetto": ("assisto il creditore che ha notificato il precetto", "assisto il debitore che ha ricevuto il precetto"),
           "pignoramento": ("assisto il creditore che vuole pignorare", "assisto il debitore o il terzo che ha subito il pignoramento"),
           "sfratto": ("assisto il locatore che agisce", "assisto il conduttore che si difende"),
           "lavoro": ("assisto il lavoratore", "assisto il datore di lavoro"),
           "condominio": ("assisto un condomino", "assisto il condominio, cioè l'amministratore"),
           "sinistro": ("assisto il danneggiato", "assisto il conducente responsabile del sinistro"),
           "garanzia": ("assisto il consumatore che ha comprato il bene", "assisto il venditore del bene"),
           "canone": ("assisto il conduttore che ha pagato oltre il canone", "assisto il locatore a cui si chiede la restituzione")}


def scelte_sul_lato(domanda: str, regola: str) -> list[str] | None:
    """Due domande complete (lato attivo e lato passivo) se il lato non si capisce e la domanda è generica."""
    fam = famiglia(regola)
    # Le regole di difesa si riconoscono già da parole della difesa (opposizione tardiva, sanatoria): si chiede solo
    # quando ha vinto lo strumento di chi agisce senza che il testo dica chi si assiste.
    if fam is None or fam[1] == PASSIVO or lato_della_parte(domanda, fam[0]) is not None or not re.search(_GENERICA, piano(domanda)):
        return None
    attivo, passivo = _SCELTA[fam[0]]
    base = domanda.strip()
    return [f"{base} ({attivo})", f"{base} ({passivo})"]
