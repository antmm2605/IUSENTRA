"""Danno da premorienza — tabella dell'Osservatorio di Milano, edizione 2024.

Il danneggiato subisce una menomazione permanente e muore prima della
liquidazione per una causa esterna e indipendente dalla lesione: il pregiudizio
si e' prodotto in un intervallo chiuso fra l'illecito e la morte e si liquida
per quell'intervallo, con maggior peso ai primi anni.

Base: Osservatorio sulla giustizia civile di Milano, edizione 2024; criterio
approvato dall'Assemblea nazionale degli Osservatori (Roma, maggio 2017), nel
solco di Cass. civ. n. 679/2016 e n. 10897/2016. Liquidazione equitativa ex
art. 1226 c.c.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import parse_date, safe_float, safe_int
from pct.calcolatori.danno_biologico import premorienza, tabelle


def _anni_sopravvivenza(payload: Mapping[str, Any]) -> tuple:
    """Anni di sopravvivenza, dalle date se ci sono, altrimenti dal campo diretto."""
    data_lesione = parse_date(payload.get("pm_data_lesione"))
    data_decesso = parse_date(payload.get("pm_data_decesso"))
    if data_lesione and data_decesso:
        if data_decesso < data_lesione:
            raise ValueError("La data del decesso non puo' precedere la data dell'evento lesivo.")
        giorni = (data_decesso - data_lesione).days
        anni = max(1, -(-giorni // 365))  # anno iniziato = anno computato
        return anni, f"dal {data_lesione.strftime('%d/%m/%Y')} al {data_decesso.strftime('%d/%m/%Y')} ({giorni} giorni)"
    anni = safe_int(payload.get("pm_anni"))
    if anni <= 0:
        raise ValueError("Indica gli anni di sopravvivenza, oppure la data dell'evento lesivo e quella del decesso.")
    return anni, f"{anni} anni indicati"


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    punti = safe_int(payload.get("pm_perc_ip"))
    if not premorienza.PUNTO_MINIMO <= punti <= premorienza.PUNTO_MASSIMO:
        raise ValueError("La percentuale di invalidita' permanente deve essere compresa tra 1 e 100.")
    anni, dettaglio_periodo = _anni_sopravvivenza(payload)

    riga = premorienza.riga_punto(punti)
    esito = premorienza.liquida(punti, anni)

    dettaglio: List[Dict[str, Any]] = []
    if anni == 1:
        base = riga["primo_anno"]
        dettaglio.append({
            "voce": "Primo anno dall'evento lesivo",
            "importo": float(base["totale"]),
            "criterio": f"colonna 1 della tabella ({base['biologico']} € biologico + {base['sofferenza']} € sofferenza)",
        })
    else:
        base = riga["primo_e_secondo_anno"]
        dettaglio.append({
            "voce": "Primo e secondo anno dall'evento lesivo",
            "importo": float(base["totale"]),
            "criterio": f"colonna 2 della tabella ({base['biologico']} € biologico + {base['sofferenza']} € sofferenza)",
        })
        if esito["anni_ulteriori"]:
            successivo = riga["anno_successivo"]
            dettaglio.append({
                "voce": f"Anni successivi al secondo ({esito['anni_ulteriori']})",
                "importo": float(successivo["totale"] * esito["anni_ulteriori"]),
                "criterio": f"colonna 3 della tabella, {successivo['totale']} € per ciascun anno",
            })

    massimo = premorienza.personalizzazione_massima()
    richiesta = max(0.0, safe_float(payload.get("pm_personalizzazione")))
    avvisi: List[str] = []
    if richiesta > massimo:
        avvisi.append(
            f"La personalizzazione richiesta ({richiesta:.0f}%) supera il {massimo}% previsto "
            "dalla tabella: e' stata ridotta al massimo consentito."
        )
        richiesta = float(massimo)
    importo_personalizzazione = round(esito["totale"] * richiesta / 100.0, 2)
    if importo_personalizzazione:
        dettaglio.append({
            "voce": f"Personalizzazione {richiesta:.0f}%",
            "importo": importo_personalizzazione,
            "criterio": f"aumento motivato fino al {massimo}% previsto dalla tabella",
        })

    totale = round(esito["totale"] + importo_personalizzazione, 2)
    fonte = tabelle.fonte(tabelle.MILANO_2024_PREMORIENZA)
    return {
        "perc_ip": punti,
        "anni_sopravvivenza": anni,
        "periodo": dettaglio_periodo,
        "danno_biologico": esito["biologico"],
        "danno_sofferenza": esito["sofferenza"],
        "subtotale": esito["totale"],
        "personalizzazione_pct": richiesta,
        "personalizzazione_massima_pct": massimo,
        "importo_personalizzazione": importo_personalizzazione,
        "totale": totale,
        "dettaglio": dettaglio,
        "tabelle_applicate": [fonte.come_dizionario()],
        "notes": [
            "Il danno si liquida per l'intervallo fra l'evento lesivo e la morte, non con il "
            "valore pieno della permanente: la tabella riconosce piu' peso ai primi anni e poi "
            "una quota annua costante.",
            "Ogni anno iniziato conta come anno intero: il computo arrotonda per eccesso.",
            str(tabelle.carica(tabelle.MILANO_2024_PREMORIENZA)["nota_totali"]),
        ],
        "warnings": avvisi,
        "sources": [fonte.come_sorgente()],
    }
