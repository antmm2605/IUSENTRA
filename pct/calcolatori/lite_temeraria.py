"""Responsabilità aggravata — art. 96 c.p.c.: quattro rami tenuti separati (stima motivata).

- commi 1 e 2: risarcimento dei danni (mala fede o colpa grave; cautela, trascrizione, esecuzione senza
  la normale prudenza): prospetto delle voci scritto dall'avvocato, ciascuna con metodo, prova,
  collegamento con la condotta e stato; un danno non quantificabile non diventa zero;
- comma 3: somma equitativamente determinata a favore della controparte, di natura indennitaria e
  sanzionatoria (Corte cost. 152/2016; Cass. SS.UU. 16601/2017), «con l'unico limite della
  ragionevolezza» (Cass. 21570/2012). Criterio orientativo scelto espressamente: Osservatorio sulla
  giustizia civile di Milano, edizione 2024 (Milano, 4 giugno 2024, pagg. 137-139): «importo all'incirca
  pari al compenso defensionale, riducibile sino alla metà ed aumentabile della metà», sul solo compenso
  di avvocato al netto di rimborso forfettario e accessori. Tre scenari, non minimo/importo/massimo di legge;
- comma 4: somma da 500 a 5.000 euro a favore della Cassa delle ammende, aggiunta dall'art. 3, c. 6,
  D.Lgs. 149/2022 e applicabile ai procedimenti instaurati dopo il 28/02/2023 (art. 35 D.Lgs. 149/2022,
  sostituito dall'art. 1, c. 380, L. 197/2022). Non è un credito della parte.

Il calcolo non si attiva per la sola soccombenza: i presupposti dell'abuso restano dell'avvocato e del giudice.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, parse_date, safe_bool, safe_float, safe_int
from pct.calcolatori.stime.scheda import SchedaDiCalcolo, importo_o_intervallo, righe_testo

VERSIONE = "2026.10"
FONTE_MILANO = {
    "title": "Osservatorio sulla giustizia civile di Milano — Tabelle milanesi edizione 2024, criteri ex art. 96, terzo comma, c.p.c. (pagg. 137-139)",
    "url": "https://tribunale-milano.giustizia.it/cmsresources/cms/documents/P._7599_24.pdf",
}
FONTE_COMMA4 = {
    "title": "D.Lgs. 10 ottobre 2022, n. 149, art. 3, c. 6 (art. 96, quarto comma, c.p.c.) e art. 35 come sostituito dall'art. 1, c. 380, L. 197/2022",
    "url": "https://www.gazzettaufficiale.it/atto/vediMenuHTML?atto.dataPubblicazioneGazzetta=2022-10-17&atto.codiceRedazionale=22G00158&tipoSerie=serie_generale&tipoVigenza=originario",
}
FONTE_ART96 = {"title": "Art. 96 c.p.c. (Normattiva)", "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art96"}
COMMA4_DAL = date(2023, 3, 1)  # procedimenti instaurati successivamente al 28/02/2023
COMMA4_MINIMO, COMMA4_MASSIMO = 500.0, 5000.0
SCENARI = (("ridotto", 0.5), ("base", 1.0), ("elevato", 1.5))
INDICI = (
    ("lt_valore_elevato", "Valore della causa"),
    ("lt_processo_lungo", "Durata del processo"),
    ("lt_piu_parti", "Numero delle parti vittoriose abusate"),
    ("lt_dolo", "Intensità dell'elemento soggettivo dell'abusante"),
    ("lt_affaticamento", "Affaticamento della parte abusata"),
)
_STATI_DANNO = {"incluso": "incluso", "escluso": "escluso"}


def _danni(testo: Any) -> tuple[List[Dict[str, Any]], List[str]]:
    """Righe «descrizione; importo|non quantificabile; metodo; prova; collegamento; stato»."""
    voci, scartate = [], []
    for descrizione, importo, metodo, prova, collegamento, stato in righe_testo(testo, 6):
        if not descrizione:
            continue
        intervallo = importo_o_intervallo(importo)
        voce = {
            "voce": descrizione,
            "importo": None if intervallo is None else round((intervallo[0] + intervallo[1]) / 2, 2),
            "quantificazione": "non quantificabile con i dati disponibili" if intervallo is None else (metodo or "metodo non indicato"),
            "prova": prova or "da indicare",
            "collegamento_con_la_condotta": collegamento or "da indicare",
            "stato": _STATI_DANNO.get(stato.lower(), "da verificare"),
        }
        if voce["stato"] == "incluso" and (not prova or not collegamento):
            voce["stato"] = "da verificare"
            scartate.append(f"«{descrizione}»: inclusa solo con prova e collegamento con la condotta")
        voci.append(voce)
    return voci, scartate


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    presupposti = clean_text(payload.get("lt_presupposti")) or "da_verificare"
    compenso = safe_float(payload.get("lt_compenso"))
    origine = clean_text(payload.get("lt_compenso_origine")) or "liquidato"
    parti = max(1, safe_int(payload.get("lt_parti"), 1))
    scheda = SchedaDiCalcolo(
        metodo="Art. 96 c.p.c., rami separati; comma 3 con il criterio dell'Osservatorio di Milano 2024",
        versione=VERSIONE, fonti=[FONTE_ART96, FONTE_MILANO, FONTE_COMMA4],
        validata=safe_bool(payload.get("lt_validata")),
        motivazione_avvocato=clean_text(payload.get("lt_motivazione")),
        dati={"compenso_di_riferimento": round(compenso, 2), "origine_del_compenso": origine, "parti_abusate": parti},
    )
    avvisi: List[str] = []
    if presupposti == "non_sussistono":
        avvisi.append("Presupposti dell'abuso non sussistenti: nessuna somma ex art. 96 da prospettare.")
    elif presupposti != "sussistono":
        scheda.mancanti.append("Presupposti: mala fede o colpa grave (o normale prudenza per il comma 2), non la sola soccombenza")
    if origine != "liquidato":
        scheda.ipotesi.append("Compenso ipotizzato per la simulazione, non quello liquidato dal giudice nel provvedimento.")

    risultato: Dict[str, Any] = {"label": "Responsabilità aggravata (art. 96 c.p.c.)",
                                 "presupposti": {"sussistono": "sussistono", "non_sussistono": "non sussistono"}.get(presupposti, "da verificare")}
    # Comma 3
    attivo = presupposti != "non_sussistono" and compenso > 0 and clean_text(payload.get("lt_metodo") or "osservatorio_milano_2024") == "osservatorio_milano_2024"
    if attivo:
        scenari = [{"scenario": nome, "coefficiente": k, "importo_per_parte": round(compenso * k, 2),
                    "importo_tutte_le_parti": round(compenso * k * parti, 2)} for nome, k in SCENARI]
        indici = [{"indice": etichetta, "indicato": "sì" if safe_bool(payload.get(campo)) else "no"} for campo, etichetta in INDICI]
        scelto = clean_text(payload.get("lt_scenario"))
        risultato["comma_3"] = {
            "metodo": "Osservatorio di Milano 2024: compenso × 0,5 / 1 / 1,5",
            "scenari": scenari,
            "indici_di_graduazione": indici,
            "scenario_scelto_dall_avvocato": scelto if scelto in {n for n, _ in SCENARI} else "non scelto",
        }
        if scelto not in {n for n, _ in SCENARI}:
            scheda.mancanti.append("Scelta motivata dello scenario del comma 3")
        risultato["somme_a_favore_della_parte_comma_3"] = next(
            (s["importo_tutte_le_parti"] for s in scenari if s["scenario"] == scelto), None)
    elif compenso <= 0 and presupposti != "non_sussistono":
        scheda.mancanti.append("Compenso difensivo di riferimento (solo compenso, senza forfettario e accessori)")
    # Commi 1 e 2
    danni, scartate = _danni(payload.get("lt_danni"))
    risultato["prospetto_danni_commi_1_2"] = danni
    inclusi = [d for d in danni if d["stato"] == "incluso" and d["importo"] is not None]
    risultato["importo_danni_inclusi_documentati"] = round(sum(d["importo"] for d in inclusi), 2)
    if any(d["importo"] is None for d in danni):
        avvisi.append("Alcuni danni non sono quantificabili con i dati disponibili: non valgono zero, restano da quantificare.")
    if scartate:
        avvisi.append("Voci di danno riportate «da verificare»: " + "; ".join(scartate) + ".")
    # Comma 4
    instaurato = parse_date(payload.get("lt_data_instaurazione"))
    if instaurato is None:
        comma4 = {"applicabile": "da verificare", "motivo": "indica la data di instaurazione del procedimento"}
    elif instaurato < COMMA4_DAL:
        comma4 = {"applicabile": "no", "motivo": "procedimento instaurato entro il 28/02/2023 (art. 35 D.Lgs. 149/2022)"}
    else:
        comma4 = {"applicabile": "sì, se ricorre uno dei commi precedenti", "da": COMMA4_MINIMO, "a": COMMA4_MASSIMO,
                  "beneficiario": "Cassa delle ammende, non la parte"}
    risultato["comma_4_cassa_delle_ammende"] = comma4
    risultato["spese_di_lite"] = "liquidate a parte dal giudice: non sono sommate a questi importi"
    calcolabile = attivo or bool(inclusi)
    risultato.update(scheda.to_dict(calcolabile=calcolabile))
    risultato["notes"] = [
        "Gli scenari del comma 3 derivano dal criterio orientativo dell'Osservatorio di Milano 2024, scelto "
        "espressamente: non sono minimo, importo e massimo previsti dalla legge.",
        "Somme a favore della parte, somme a favore della Cassa delle ammende e spese di lite restano separate: "
        "il software non le somma.",
        "Il comma 3 non è il risarcimento dei commi 1 e 2: verificare le possibili duplicazioni prima di prospettarli insieme.",
    ]
    risultato["warnings"] = avvisi + risultato.pop("avvisi_validazione")
    risultato["sources"] = [FONTE_ART96, FONTE_MILANO, FONTE_COMMA4]
    return risultato


__all__ = ["COMMA4_DAL", "SCENARI", "VERSIONE", "calcola"]
