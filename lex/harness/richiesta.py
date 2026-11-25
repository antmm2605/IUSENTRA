"""La richiesta pesa più del preambolo nella scelta dello strumento.

Un racconto comincia spesso con parole di contesto estranee alla domanda («lavoro da vent'anni…», «sono amministratore di
condominio…», «al Tribunale di Napoli…») e solo dopo arriva la richiesta vera («voglio…», «posso…», «come faccio…»). Le
regole dell'harness si riconoscono sul testo intero: una parola del preambolo può far vincere uno strumento che con la
domanda non c'entra. Qui si separano:

- la **richiesta**: le frasi che chiedono qualcosa (domanda con il punto interrogativo, comando a Lex, «voglio»,
  «posso», «devo», «come faccio»…);
- la **zona della richiesta**: la richiesta con il fatto che la precede, oppure tutto ciò che segue un segnale di
  cambio di argomento («detto questo», «a parte questo», «il problema però…», «un'altra cosa»).

Se la regola migliore sul testo intero si riconosce anche sulla zona della richiesta, resta: i suoi fatti non vengono
dal preambolo. Altrimenti lo strumento si sceglie fra le regole riconosciute sulla sola richiesta e, se nessuna, fra
quelle riconosciute sulla zona della richiesta; se nessuna si riconosce lì decide il testo intero. Il preambolo non viene
ignorato: le regole scelte devono riconoscersi anche sul testo intero, da cui prendono i fatti per l'analisi. Senza
preambolo (il fatto e la domanda sono tutto il racconto) non cambia nulla; senza un segnale di cambio di argomento,
un inizio con date o importi è il racconto della causa e resta decisivo.
"""
from __future__ import annotations

import re

from .fatti import Fatti, leggi_fatti
from .norme import piano

_FRASI = re.compile(r"(?<=[.?!])\s+(?=\S)")
# Verbi e formule della richiesta, ovunque nella frase («la mia cliente vuole sapere…», «come posso…»).
_CHIEDE = re.compile(
    r"\?|^(?:prepar|redig|scriv|predispon|stend|fammi|dimmi|indica|valuta|spiega|aiutami)|"
    r"\b(?:voglio|vogliamo|vorrei|vorremmo|vuole (?:sapere|fare|chiedere|presentare|proporre|impugnare|opporsi|agire)|"
    r"posso|possiamo|puo|devo|dobbiamo|come faccio|come facciamo|come mi muovo|come ci muoviamo|come procedo|"
    r"mi chiede|ci chiede|chiede se|intendo|intendiamo|mi serve|ci serve|e possibile|si puo)\b")
_CAMBIO = re.compile(
    r"\b(?:detto questo|a parte questo|ad ogni modo|comunque sia|il (?:mio |vero )?problema (?:pero|e un altro|e che)|"
    r"la vera urgenza|un altra cosa|una questione diversa|questione diversa|altra questione|oggi pero|ora pero|"
    r"adesso pero|veniamo al punto|il punto e|mi rivolgo a te per|ti scrivo per|la domanda e)\b")
_FATTO_DATATO = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b|\d[\d.,]*\s*(?:euro|€)|(?:euro|€)\s*\d")
_DATA_DI_OGGI = re.compile(r"^(?:oggi e il|oggi e|data di oggi|in data odierna)\b")


def frasi(testo: str) -> list[str]:
    return [x.strip() for x in _FRASI.split(" ".join(str(testo or "").split())) if x.strip()]


def separa(testo: str) -> tuple[str, str]:
    """(richiesta, zona della richiesta) del testo libero; stringhe vuote se non c'è un preambolo da separare."""
    elenco = [x for x in frasi(testo) if not _DATA_DI_OGGI.match(piano(x))]
    if len(elenco) < 2:
        return "", ""
    chieste = [i for i, x in enumerate(elenco) if _CHIEDE.search(piano(x))]
    if not chieste or chieste[0] == 0:
        return "", ""
    inizio, cambio = max(0, chieste[0] - 1), False
    for i in range(chieste[0], 0, -1):
        if _CAMBIO.search(piano(elenco[i])):
            inizio, cambio = i, True
            break
    if inizio == 0:
        return "", ""                                # nessun preambolo: il fatto e la domanda sono tutto il testo
    if not cambio and _FATTO_DATATO.search(" ".join(elenco[:inizio])):
        # Senza un segnale di cambio di argomento, un inizio con date o importi è il racconto della causa, non un preambolo.
        return "", ""
    return " ".join(elenco[i] for i in chieste), " ".join(elenco[inizio:])


def fatti_parziali(f: Fatti) -> list[Fatti]:
    """I fatti letti dalla sola zona della richiesta e dalla sola richiesta (in quest'ordine); vuoto senza preambolo."""
    if re.search(r"richiesta dell avvocato", piano(f.testo)):
        return []                                    # formato dell'avvocato: la richiesta è già dichiarata a parte
    richiesta, zona = separa(f.testo)
    out = []
    for parte in (zona, richiesta):
        if parte and len(parte) < len(f.testo):
            parziali = leggi_fatti(parte, oggi=f.oggi)
            # Le parti del racconto restano quelle del testo intero (chi assiste chi non cambia col preambolo).
            if not parziali.assistita.nome and not parziali.assistita.ruolo:
                parziali.assistita = f.assistita
            if not parziali.controparte.nome and not parziali.controparte.ruolo:
                parziali.controparte = f.controparte
            out.append(parziali)
    return out
