"""Percorso «il codice decide, Lex scrive».

1. ``prepara``: verifica la scheda (coerenza e provenienza da fatti e Fonti), calcola termini e importi, controlla la
   validazione dell'avvocato legata alle impronte e costruisce il messaggio di stesura per Lex.
2. ``valuta``: dopo la stesura, controlla requisiti del modello d'atto, revisione indipendente dalla scheda (bozza
   contro fascicolo, Fonti e calcolatore) e assegna uno dei tre stati della consegna.

Nessuno stato significa «atto giuridicamente corretto»: il migliore e' «pronta per la revisione dell'avvocato».
Misura di riferimento (banco v7, 60 casi, valutazione cieca esplorativa, schede non validate): con la scheda gli esiti
sbagliati scendono da circa 35 a circa 5-10 su 60 rispetto alla stesura diretta. Non e' una garanzia di accuratezza.

Formato del caso: {"fatti", "richiesta", "oggi" (gg/mm/aaaa), "parte_assistita": {"nome", "ruolo"},
"controparte": {"nome", "ruolo"}, "fonti": {n: testo}, "fonti_ref": [{"n", "atto", "articolo", "sigla", "provenienza"}]}; provenienza obbligatoria (provenienza.py).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .calcolatore import calcola_scheda
from .contabilita import prospetto, verifica_credito
from .impronte import impronta_fascicolo, impronta_fonti, impronta_scheda
from .provenienza import verifica_provenienza
from .requisiti_atti import modello_per, requisiti_mancanti
from .revisione_indipendente import rivedi
from .stato_consegna import stato
from .verifica_scheda import verifica

CAMPI_AL_MODELLO = ["forma_risposta", "parte_assistita", "controparte", "obiettivo_cliente", "rimedio", "domande",
                    "punti_da_trattare", "avvertenze", "norme_mancanti", "dati_mancanti"]
ISTRUZIONI = ("Scrivi la risposta seguendo la SCHEDA DECISA dall'avvocato. Le conclusioni contengono tutte e sole le "
              "domande della scheda. Scadenze e importi: solo quelli dei Risultati del calcolatore o dei fatti, identici. "
              "Norme: solo le Fonti, con [n]. Se la scheda ti sembra in contrasto con i fatti o con le Fonti, o contraria "
              "alla parte assistita, non adeguarti: segnalalo all'inizio e spiega perche'. Tratta ogni avvertenza della scheda.")


class SchedaNonUtilizzabile(ValueError):
    """La scheda non supera la verifica software o non risulta validata per le impronte correnti."""

    def __init__(self, motivi: list[str]):
        super().__init__("; ".join(motivi[:3]))
        self.motivi = motivi


@dataclass
class Preparazione:
    calcoli: dict
    prospetto_credito: dict | None
    impronte: dict
    messaggio: str
    avvisi: list[str] = field(default_factory=list)


def impronte(scheda: dict, caso: dict) -> dict:
    return {"scheda_sha256": impronta_scheda(scheda), "fonti_sha256": impronta_fonti(caso),
            "fascicolo_sha256": impronta_fascicolo(caso)}


def validazione_valida(validazione: dict | None, scheda: dict, caso: dict) -> list[str]:
    """Motivi per cui la validazione dell'avvocato non vale (lista vuota = valida). Vale solo se «approvata» e se
    impronte di scheda, Fonti e fascicolo coincidono con quelle approvate."""
    if not validazione or validazione.get("esito") != "approvata":
        return ["scheda non approvata dall'avvocato"]
    attese = impronte(scheda, caso)
    return [f"impronta cambiata dopo l'approvazione: {k}" for k, h in attese.items() if validazione.get(k) != h]


def prepara(scheda: dict, caso: dict, validazione: dict | None, *, consenti_non_validata: bool = False) -> Preparazione:
    errori = verifica_provenienza(caso) + verifica(scheda, caso, caso["fonti"])
    if scheda.get("credito"):
        errori += verifica_credito(scheda["credito"], caso["fatti"])
    if errori:
        raise SchedaNonUtilizzabile(errori)
    avvisi = validazione_valida(validazione, scheda, caso)
    if avvisi and not consenti_non_validata:
        raise SchedaNonUtilizzabile(avvisi)
    calc = calcola_scheda(scheda)
    pr = prospetto(scheda["credito"]) if scheda.get("credito") else None
    righe = [f"- {t['descrizione']}: {t['scadenza']} ({t['spiegazione']})" for t in calc["termini"]]
    righe += [f"- {i['descrizione']}: {i['euro']} euro" for i in calc["importi"]]
    if pr:
        righe.append(f"- Prospetto del credito (voci separate): capitale {pr['capitale']}, pagamenti {pr['pagamenti']}, "
                     f"residuo capitale {pr['residuo_capitale']} (per voce: {pr['residui_per_voce']}), "
                     f"interessi: {pr['interessi'].get('stato')}, spese {pr['spese']}")
    decisa = {k: scheda[k] for k in CAMPI_AL_MODELLO if k in scheda}
    messaggio = ("SCHEDA DECISA:\n" + json.dumps(decisa, ensure_ascii=False, indent=1)
                 + "\n\nRisultati del calcolatore (riportali identici):\n" + ("\n".join(righe) or "- nessun calcolo")
                 + "\n\n" + ISTRUZIONI)
    return Preparazione(calc, pr, impronte(scheda, caso), messaggio, avvisi)


def valuta(bozza: str, scheda: dict, caso: dict, preparazione: Preparazione) -> dict:
    rq = requisiti_mancanti(bozza, modello_per(scheda))
    rv = rivedi(bozza, caso, preparazione.calcoli)
    esito = stato(bozza, rq, rv, scheda, preparazione.prospetto_credito)
    if preparazione.avvisi:
        esito["motivi"] = [f"scheda non validata: {a}" for a in preparazione.avvisi] + esito["motivi"]
        if esito["stato"] == "pronta_per_revisione_avvocato":
            esito["stato"] = "bozza_con_verifiche_pendenti"
    return {"requisiti_mancanti": rq, "revisione_indipendente": rv, "stato_consegna": esito}
