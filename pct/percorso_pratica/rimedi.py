"""Dopo la sentenza: rimedi possibili, ipotesi difensive e, se la causa è vinta, la strada per ottenere quanto deciso.

Ogni voce cita la norma vigente letta il 06/11/2026 nell'archivio Normattiva del software (art. 59 L. 69/2009 su
Normattiva). Giurisdizione e grado (amministrativo, tributario, penale; appello e cassazione) scelgono il mezzo
d'impugnazione: ``pct/percorso_pratica/giurisdizioni.py``. Le ipotesi sono spunti per l'avvocato, agganciati alla ragione della decisione: non sostituiscono la
valutazione dei motivi sul testo della sentenza.
"""

from __future__ import annotations

from typing import Any


from pct.percorso_pratica.giurisdizioni import (
    ALTRI_RIMEDI,
    CASSAZIONE,
    CIVILE,
    IMPUGNAZIONI_PER_GRADO,
    REALIZZAZIONE_PER_GIURISDIZIONE,
)


def _rimedio(nome: str, termine: str, norme: list[str], quando: str, template: str = "") -> dict[str, Any]:
    return {"rimedio": nome, "termine": termine, "norme": norme, "quando": quando, "template": template}


CORREZIONE = _rimedio("Correzione dell'errore materiale o di calcolo", "finché la sentenza non è appellata; con ricorso allo stesso giudice",
                      ["art. 287 c.p.c.", "art. 288 c.p.c."], "omissioni o errori materiali o di calcolo nel testo della sentenza")
REVOCAZIONE = _rimedio("Revocazione", "30 giorni dalla notifica (art. 325); per i nn. 1, 2, 3 e 6 dell'art. 395 dalla scoperta (art. 326)",
                       ["art. 395 c.p.c.", "art. 398 c.p.c."], "dolo, prove false, documenti decisivi recuperati, errore di fatto, contrasto con giudicato")

IMPUGNAZIONI = {
    "lavoro": [
        _rimedio("Appello alla corte d'appello, sezione lavoro", "30 giorni dalla notificazione della sentenza; senza notifica sei mesi dalla pubblicazione",
                 ["art. 433 c.p.c.", "art. 434 c.p.c.", "art. 327 c.p.c."], "sentenza di primo grado sfavorevole in tutto o in parte",
                 "CIV_APPELLO_BREVE"),
    ],
    "ordinario": [
        _rimedio("Appello", "30 giorni dalla notificazione della sentenza; senza notifica sei mesi dalla pubblicazione",
                 ["art. 325 c.p.c.", "art. 326 c.p.c.", "art. 327 c.p.c."], "sentenza di primo grado sfavorevole in tutto o in parte",
                 "CIV_APPELLO_BREVE"),
    ],
    "appello": [
        _rimedio("Ricorso per cassazione", "60 giorni dalla notificazione della sentenza; senza notifica sei mesi dalla pubblicazione",
                 ["art. 360 c.p.c.", "art. 325 c.p.c.", "art. 327 c.p.c.", "art. 366 c.p.c."], "sentenza d'appello: solo per i motivi dell'art. 360 c.p.c.",
                 "CIV_CASSAZIONE_BREVE"),
    ],
}
IMPUGNAZIONI["semplificato"] = IMPUGNAZIONI["ordinario"]

# Ragione della decisione -> ipotesi da verificare per l'impugnazione o per riproporre la domanda.
IPOTESI = {
    "prescrizione": [{"ipotesi": "Verificare se c'erano atti interruttivi non valutati: domanda giudiziale, atto di costituzione in mora, riconoscimento del debito",
                      "norme": ["art. 2943 c.c."]}],
    "onere_prova": [{"ipotesi": "Nel rito del lavoro in appello sono ammessi nuovi mezzi di prova solo se il collegio li ritiene indispensabili: individuare la prova decisiva e motivarne l'indispensabilità",
                     "norme": ["art. 437, secondo comma, c.p.c."], "riti": ["lavoro"]},
                    {"ipotesi": "Verificare se il giudice ha omesso di pronunciare su prove o istanze ritualmente proposte", "norme": ["art. 112 c.p.c."]}],
    "incompetenza": [{"ipotesi": "Riassumere la causa davanti al giudice dichiarato competente nel termine fissato o, in mancanza, entro tre mesi: altrimenti il processo si estingue",
                      "norme": ["art. 50 c.p.c."], "termine": "3 mesi dalla comunicazione dell'ordinanza"}],
    "difetto_giurisdizione": [{"ipotesi": "Riproporre la domanda al giudice indicato entro tre mesi dal passaggio in giudicato: si conservano gli effetti sostanziali e processuali della domanda",
                               "norme": ["art. 59, comma 2, L. 69/2009"], "termine": "3 mesi dal passaggio in giudicato"}],
    "infondatezza": [{"ipotesi": "Confrontare ogni punto della motivazione con le difese svolte: motivi specifici su capi e punti, non riproposizione generica",
                      "norme": ["art. 342 c.p.c.", "art. 434 c.p.c."]}],
    "genericita": [{"ipotesi": "Valutare se la genericità contestata riguarda la domanda (riproponibile con atto completo) o i soli mezzi di prova", "norme": ["art. 414 c.p.c.", "art. 163 c.p.c."]}],
    "spese_compensate": [{"ipotesi": "Con la vittoria piena la compensazione è ammessa solo per soccombenza reciproca, novità della questione o mutamento della giurisprudenza: verificare la motivazione sulle spese",
                          "norme": ["art. 92, secondo comma, c.p.c."]}],
}

# Se la causa è vinta: i passi per ottenere quanto deciso. «urgenza» 1 = subito, 2 = dopo i passi precedenti.
REALIZZAZIONE = [
    {"passo": "Notificare la sentenza alla controparte: fa decorrere il termine breve d'impugnazione per entrambe le parti",
     "norme": ["art. 285 c.p.c.", "art. 326 c.p.c."]},
    {"passo": "Contro un'amministrazione dello Stato: notificare presso l'Avvocatura dello Stato del distretto e attendere 120 giorni dalla notifica del titolo prima del precetto",
     "norme": ["art. 11 R.D. 1611/1933", "art. 14 D.L. 669/1996"], "solo_pa": True},
    {"passo": "Se il pagamento non arriva: notificare titolo e precetto con almeno dieci giorni per adempiere",
     "urgenza": 2, "norme": ["art. 479 c.p.c.", "art. 480 c.p.c."]},
    {"passo": "Per gli obblighi di fare della pubblica amministrazione, o in alternativa all'esecuzione: giudizio di ottemperanza sulla sentenza passata in giudicato",
     "urgenza": 2, "norme": ["art. 112 c.p.a.", "art. 113 c.p.a.", "art. 114 c.p.a."], "solo_pa": True},
    {"passo": "Spese liquidate con distrazione: il difensore antistatario le chiede direttamente alla controparte",
     "urgenza": 2, "norme": ["art. 93 c.p.c."], "solo_distrazione": True},
    {"passo": "Informare il cliente dell'esito, dei termini e dei costi e chiudere la pratica dopo il pagamento o il giudicato", "norme": []},
]


def _impugnazioni(giurisdizione: str, grado: str, rito: str) -> list[dict[str, Any]]:
    """Il mezzo d'impugnazione del grado e della giurisdizione, poi i rimedi davanti allo stesso giudice."""
    if giurisdizione == CIVILE and grado != CASSAZIONE:
        principali = IMPUGNAZIONI["appello"] if grado == "appello" else IMPUGNAZIONI.get(rito, IMPUGNAZIONI["ordinario"])
        return [*principali, REVOCAZIONE, CORREZIONE]
    principali = IMPUGNAZIONI_PER_GRADO.get((giurisdizione, grado), [])
    if grado == CASSAZIONE:
        return list(principali)
    return [*principali, *ALTRI_RIMEDI.get(giurisdizione, [])]


def rimedi(esito: dict[str, Any], *, rito: str = "ordinario", grado: str = "primo", controparte_pa: bool = False,
           giurisdizione: str = CIVILE) -> dict[str, Any]:
    """Che cosa fare dopo la sentenza, secondo l'esito per il cliente, la giurisdizione e il grado della sentenza."""
    per_noi = esito.get("per_il_cliente")
    civile = giurisdizione == CIVILE
    if per_noi == "favorevole":
        if civile:
            passi = [p for p in REALIZZAZIONE if (controparte_pa or not p.get("solo_pa")) and (esito.get("spese", {}).get("distrazione") or not p.get("solo_distrazione"))]
        else:
            passi = list(REALIZZAZIONE_PER_GIURISDIZIONE.get(giurisdizione, []))
        ipotesi = IPOTESI["spese_compensate"] if civile and esito.get("spese", {}).get("regolazione") == "compensazione" else []
        correzione = [CORREZIONE] if civile and grado != CASSAZIONE else [r for r in ALTRI_RIMEDI.get(giurisdizione, []) if "Correzione" in r["rimedio"]]
        return {"strada": "realizzazione", "passi": passi, "ipotesi": ipotesi, "rimedi": correzione,
                "giurisdizione": giurisdizione, "grado": grado}
    ragioni = [voce["ragione"] for voce in esito.get("ragioni", [])]
    if esito.get("esito") in {"incompetenza", "difetto_giurisdizione"}:
        ragioni.insert(0, esito["esito"])
    # Le ipotesi citano il processo civile (artt. 342, 434, 437 c.p.c.): fuori da quello non si propongono.
    ipotesi = [voce for chiave in dict.fromkeys(ragioni) for voce in IPOTESI.get(chiave, []) if rito in voce.get("riti", [rito])] if civile else []
    return {"strada": "impugnazione" if per_noi in {"sfavorevole", "parziale"} else "da_valutare",
            "rimedi": _impugnazioni(giurisdizione, grado, rito), "ipotesi": ipotesi, "passi": [],
            "giurisdizione": giurisdizione, "grado": grado}
