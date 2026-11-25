"""Normalizzazione tollerante della domanda prima della scelta dello strumento.

Riusa ``lex.harness.normalizzazione`` dell'agente di Lex quando c'è (accenti, refusi sul lessico giuridico delle regole,
linguaggio comune affiancato al termine tecnico); in ogni caso corregge i refusi sulle parole degli strumenti (titoli dei
calcolatori, schede, usi), con la stessa prudenza: si corregge una parola lunga solo se UNA sola parola del lessico è
abbastanza vicina, con la stessa iniziale, per lettera mancante, in più o scambiata. Nomi propri, date, importi e numeri
non si toccano.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import get_close_matches
from functools import lru_cache


def senza_accenti(testo: str) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "").replace("’", "'").replace("`", "'"))
    return "".join(c for c in base if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def lessico() -> frozenset[str]:
    """Le parole intere (6+ lettere) dei testi della mappa: titoli, contenuti, esempi, etichette dei calcolatori."""
    from .mappa import mappa

    m = mappa()
    testi = [s["titolo"] + " " + s["contenuto"] + " " + s["esempio"] for s in m["strumenti"]]
    testi += [v["titolo"] + " " + " ".join(c["etichetta"] for c in v["campi"].values()) for v in m["calcolatori"].values()]
    testi += ["sentenza sentenze cassazione costituzionale consiglio tribunale udienza scadenza scadenze termine termini "
              "notifica notificata notificazione ricevuta ricevute deposito depositare telematico fascicolo pratica cliente "
              "parcella parcelle pagamento pagamenti preventivo fattura fatturato circolare risoluzione gazzetta ufficiale "
              "modello modelli procedura articolo comma codice civile procedura penale interessi rivalutazione contributo "
              "unificato compenso compensi avvocato appello impugnazione opposizione decreto ingiuntivo precetto "
              "prescrizione licenziamento mantenimento successione eredita testamento invalidita risarcimento danno "
              "quando quanto quanti entro appellare appella appellato notificato notificata notificate depositata "
              "depositato pubblicata pubblicato sentenza ordinanza decreto scaduto scaduta scadenza calcola calcolami "
              "articolo articoli codice civile penale costituzione tributario amministrativo condominiale condominio "
              "delibera assemblea locazione inquilino conduttore locatore canone sfratto pignoramento stipendio pensione "
              "codice testo norma legge sezioni unite prefetto prefettura questura procura precetto ricorso ricorsi "
              "verbale verbali multa contravvenzione sanzione sanzioni velocita patente veicolo infrazione autovelox "
              "assemblea condomino condomini amministratore perito periti consulente consulenti vacazioni legittima "
              "legittimari mantenimento assegno divorzio separazione coniuge figli eredi erede donazione donazioni "
              "archiviazione querela imputato indagato condanna assoluzione riesame custodia arresti domiciliari"]
    parole: set[str] = set()
    for t in testi:
        parole.update(w for w in re.findall(r"[a-z]{5,}", senza_accenti(t).lower()))
    return frozenset(parole)


def _parola_nota(parola: str) -> bool:
    if parola in lessico():
        return True
    try:
        from legal_ocr.lessico.italiano import conosce

        return bool(conosce(parola))
    except Exception:
        return False


def _vocabolario_completo() -> bool:
    """Senza il dizionario italiano di sistema non si corregge: una parola vera non dichiarata nel repository
    («saltato», «quarta») sembrerebbe un refuso e diventerebbe un'altra parola («saldato», «quaranta»)."""
    try:
        from legal_ocr.lessico.italiano import vocabolario_completo

        return bool(vocabolario_completo())
    except Exception:
        return False


@lru_cache(maxsize=8192)
def _corretta(parola: str) -> str:
    """Solo refusi evidenti e con una sola correzione possibile: lettere scambiate, una lettera mancante (non in fondo),
    una lettera raddoppiata per errore, una lettera sbagliata nelle parole lunghe. Le desinenze diverse non si toccano."""
    if len(parola) < 5 or _parola_nota(parola) or not _vocabolario_completo():
        return parola
    candidati = []
    for s in get_close_matches(parola, lessico(), n=5, cutoff=0.8):
        if s[0] != parola[0]:
            continue
        scambiate = len(s) == len(parola) and sorted(s) == sorted(parola) and sum(a != b for a, b in zip(s, parola, strict=False)) == 2
        mancante = len(s) == len(parola) + 1 and any(s[:i] + s[i + 1:] == parola for i in range(1, len(s) - 1))
        doppia = len(parola) == len(s) + 1 and any(parola[:i] + parola[i + 1:] == s and parola[i] == parola[i - 1]
                                                   for i in range(1, len(parola)))
        sbagliata = len(s) == len(parola) >= 9 and sum(a != b for a, b in zip(s, parola, strict=False)) == 1 and s[-2:] == parola[-2:]
        if scambiate or mancante or doppia or sbagliata:
            candidati.append(s)
    return candidati[0] if len(candidati) == 1 else parola


def correggi_refusi(testo: str) -> str:
    def sost(m: re.Match) -> str:
        w = m.group(0)
        if w[0].isupper() or len(w) < 5:
            return w
        return _corretta(w)

    return re.sub(r"[A-Za-z]+", sost, testo)


def normalizza_domanda(testo: str) -> str:
    """Domanda pronta per la scelta: accenti tolti, refusi corretti, linguaggio comune affiancato al termine tecnico."""
    t = senza_accenti(str(testo or ""))
    try:  # normalizzazione dell'harness di Lex (lex/harness/normalizzazione.py), se presente in questo ramo
        from lex.harness.normalizzazione import normalizza_richiesta

        t = normalizza_richiesta(t)
    except Exception:
        pass
    t = correggi_refusi(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


__all__ = ["correggi_refusi", "lessico", "normalizza_domanda", "senza_accenti"]
