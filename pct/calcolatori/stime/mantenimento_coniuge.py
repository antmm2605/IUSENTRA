"""Mantenimento del coniuge separato e assegno divorzile: bilancio guidato e scheda dei criteri.

Separazione — art. 156 c.c.: il giudice stabilisce a vantaggio del coniuge cui non sia addebitabile la
separazione il diritto di ricevere quanto necessario al suo mantenimento, qualora non abbia adeguati
redditi propri; l'entità si determina in relazione alle circostanze e ai redditi dell'obbligato.

Divorzio — art. 5, comma 6, L. 898/1970: il tribunale tiene conto delle condizioni dei coniugi, delle
ragioni della decisione, del contributo personale ed economico dato da ciascuno alla conduzione
familiare e alla formazione del patrimonio, del reddito di entrambi, anche in rapporto alla durata del
matrimonio, quando il richiedente non ha mezzi adeguati o non può procurarseli per ragioni oggettive.
Cass. SS.UU. 11/07/2018 n. 18287: funzione assistenziale e, in pari misura, compensativo-perequativa;
non la conservazione del precedente tenore di vita.

Metodo (versione 2026.10): il codice calcola soltanto la differenza fra il fabbisogno assunto e le
risorse del richiedente e lo squilibrio fra i redditi; non la trasforma nell'assegno spettante e non
usa coefficienti (anni di matrimonio, percentuali del divario) che la legge non prevede. Nel divorzio la
componente compensativa è una valutazione dell'avvocato, voce per voce e con la prova.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_bool, safe_float, safe_int
from pct.calcolatori.stime.scheda import SchedaDiCalcolo, importo_o_intervallo, righe_testo

VERSIONE = "2026.10"
FONTI_SEPARAZIONE = [
    {"title": "Art. 156 c.c. (Normattiva)", "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262~art156"},
]
FONTI_DIVORZIO = [
    {"title": "Art. 5, comma 6, L. 1 dicembre 1970, n. 898 (Normattiva)", "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1970-12-01;898~art5"},
    {"title": "Cass. civ., Sez. Un., 11/07/2018, n. 18287 (funzione assistenziale e compensativo-perequativa)", "url": "https://www.italgiure.giustizia.it/sncass/"},
]
VALUTAZIONI_SEPARAZIONE = (
    ("mc_val_tenore", "Tenore di vita matrimoniale e sua prova"),
    ("mc_val_capacita", "Capacità lavorativa e reddituale del richiedente"),
    ("mc_val_circostanze", "Altre circostanze e redditi dell'obbligato (art. 156, c. 2)"),
)
VALUTAZIONI_DIVORZIO = (
    ("mc_val_condizioni", "Condizioni dei coniugi ed età"),
    ("mc_val_contributo", "Contributo personale ed economico alla conduzione familiare e al patrimonio"),
    ("mc_val_prospettive", "Prospettive reddituali e rinunce professionali"),
    ("mc_val_ragioni", "Ragioni della decisione"),
)


def _intervallo(payload: Mapping[str, Any], chiave: str):
    return importo_o_intervallo(payload.get(chiave))


def _compensative(testo: Any) -> tuple[List[Dict[str, Any]], List[str]]:
    """Righe «descrizione; importo mensile proposto; prova» scritte dall'avvocato."""
    voci, scartate = [], []
    for descrizione, importo, prova in righe_testo(testo, 3):
        intervallo = importo_o_intervallo(importo)
        if not descrizione or intervallo is None:
            scartate.append(f"«{descrizione or importo}»: importo non leggibile")
            continue
        if not prova:
            scartate.append(f"«{descrizione}»: manca la prova o l'elemento su cui si fonda")
            continue
        voci.append({"voce": descrizione, "minimo": intervallo[0], "massimo": intervallo[1], "prova": prova})
    return voci, scartate


def calcola(payload: Mapping[str, Any], *, divorzio: bool) -> Dict[str, Any]:
    fabbisogno = _intervallo(payload, "mc_fabbisogno")
    risorse = safe_float(payload.get("mc_risorse_richiedente"))
    reddito_altro = safe_float(payload.get("mc_reddito_altro"))
    valutazioni = VALUTAZIONI_DIVORZIO if divorzio else VALUTAZIONI_SEPARAZIONE
    fonti = FONTI_DIVORZIO if divorzio else FONTI_SEPARAZIONE
    scheda = SchedaDiCalcolo(
        metodo=("Bilancio assistenziale e scheda dei criteri dell'art. 5, c. 6, L. 898/1970" if divorzio
                else "Bilancio di adeguatezza delle risorse (art. 156 c.c.)"),
        versione=VERSIONE, fonti=list(fonti),
        validata=safe_bool(payload.get("mc_validata")),
        motivazione_avvocato=clean_text(payload.get("mc_motivazione")),
        dati={"risorse_mensili_richiedente": round(risorse, 2), "reddito_mensile_altro_coniuge": round(reddito_altro, 2)},
    )
    avvisi: List[str] = []
    presupposti: List[Dict[str, str]] = []
    if not divorzio:
        addebito = clean_text(payload.get("mc_addebito")) or "da_accertare"
        esito = {"no": "non addebitabile al richiedente", "si": "addebitata al richiedente", "da_accertare": "da accertare"}.get(addebito, "da accertare")
        presupposti.append({"presupposto": "Separazione non addebitabile al richiedente (art. 156, c. 1)", "esito": esito})
        if addebito == "si":
            avvisi.append("Con la separazione addebitata al richiedente il diritto al mantenimento non sorge "
                          "(resta solo l'eventuale assegno alimentare, art. 156, c. 3, e art. 433 c.c.).")
        elif addebito != "no":
            scheda.mancanti.append("Presupposto: addebito della separazione")
    else:
        durata = safe_int(payload.get("mc_durata_matrimonio"))
        if durata:
            scheda.dati["durata_del_matrimonio_anni"] = durata
            scheda.ipotesi.append("La durata del matrimonio è registrata come elemento di valutazione, senza coefficiente numerico.")
    for campo, etichetta in valutazioni:
        testo = clean_text(payload.get(campo))
        scheda.valutazioni.append({"criterio": etichetta, "valutazione": testo or "da valutare"})
        if not testo:
            scheda.mancanti.append(f"Valutazione: {etichetta.lower()}")

    calcolabile = fabbisogno is not None and fabbisogno[1] > 0
    if not calcolabile:
        scheda.mancanti.append("Fabbisogno mensile assunto nel modello")
    risultato: Dict[str, Any] = {
        "percorso": "divorzio" if divorzio else "separazione",
        "label": "Assegno divorzile (stima motivata)" if divorzio else "Mantenimento del coniuge separato (stima motivata)",
        "presupposti": presupposti,
    }
    note = [
        "Il software calcola la differenza fra fabbisogno e risorse: non è l'assegno spettante, che resta una "
        "valutazione sui criteri di legge.",
        "Nessun coefficiente è applicato a durata del matrimonio, età o divario dei redditi: sarebbe una scelta "
        "del programma, non un criterio giuridico.",
    ]
    if calcolabile:
        basso, alto = fabbisogno
        scheda.dati["fabbisogno_mensile_assunto"] = basso if basso == alto else f"{basso:.2f}-{alto:.2f}"
        diff_min, diff_max = max(0.0, basso - risorse), max(0.0, alto - risorse)
        risultato["differenza_economica_da_esaminare"] = round((diff_min + diff_max) / 2, 2)
        if diff_min != diff_max:
            risultato["fascia_di_sensibilita"] = {"da": round(diff_min, 2), "a": round(diff_max, 2),
                                                 "spiegazione": "variazione del solo fabbisogno assunto"}
        risultato["squilibrio_fra_i_redditi_mensili"] = round(reddito_altro - risorse, 2)
        if diff_max <= 0:
            avvisi.append("Le risorse del richiedente coprono il fabbisogno assunto: sul piano assistenziale non "
                          "emerge una differenza." + (" Resta da valutare la componente compensativa." if divorzio else ""))
    if divorzio:
        voci, scartate = _compensative(payload.get("mc_compensative"))
        if scartate:
            avvisi.append("Voci compensative non usate: " + "; ".join(scartate) + ".")
        risultato["componente_compensativa"] = [
            {"voce": v["voce"], "importo_mensile_proposto": v["minimo"] if v["minimo"] == v["massimo"] else f"{v['minimo']:.2f}-{v['massimo']:.2f}", "prova": v["prova"]}
            for v in voci
        ]
        if voci and calcolabile:
            assistenziale = risultato["differenza_economica_da_esaminare"]
            compensativa = round(sum((v["minimo"] + v["massimo"]) / 2 for v in voci), 2)
            risultato["scenario_prospettato_dall_avvocato"] = {
                "assistenziale": assistenziale, "compensativa": compensativa, "totale": round(assistenziale + compensativa, 2),
                "natura": "valutazione discrezionale dello studio, voce per voce con la prova",
            }
        note.append("Nel divorzio la differenza assistenziale non è un tetto: la funzione compensativo-perequativa "
                    "(Cass. SS.UU. 18287/2018) si valuta a parte.")
    if scheda.mancanti and calcolabile:
        avvisi.append("Proposta non completa: mancano " + ", ".join(m.lower() for m in scheda.mancanti) + ".")
    risultato.update(scheda.to_dict(calcolabile=calcolabile))
    risultato["notes"] = note
    risultato["warnings"] = avvisi + risultato.pop("avvisi_validazione")
    risultato["sources"] = list(fonti)
    return risultato


__all__ = ["VERSIONE", "calcola"]
