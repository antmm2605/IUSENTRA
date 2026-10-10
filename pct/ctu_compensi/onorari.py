"""Compenso dell'ausiliario del magistrato (D.P.R. 115/2002, artt. 49-58).

- art. 49: spettano onorari, indennità di viaggio e rimborso delle spese sostenute;
- art. 50: onorari fissi, variabili e a tempo secondo le tabelle (D.M. 30/05/2002);
- art. 51: negli onorari variabili il giudice sceglie fra minimo e massimo secondo difficoltà,
  completezza e pregio della prestazione (qui la «posizione nella forbice»);
- art. 52: aumento fino al doppio per le prestazioni di eccezionale importanza, complessità e
  difficoltà; riduzione di un terzo se la prestazione non è completata nel termine;
- art. 53: incarico collegiale, compenso del singolo aumentato del 40% per ciascun altro componente,
  salvo che il giudice disponga che ognuno svolga l'incarico per intero;
- art. 55-56: indennità di viaggio e spese documentate, fuori dagli onorari.
Patrocinio a spese dello Stato: le riduzioni degli artt. 106-bis (penale, un terzo) e 130 (civile,
metà) non si applicano all'ausiliario finché le tabelle non sono adeguate ex art. 54 (Corte cost.
192/2015 e 166/2022): le tabelle del 2002 non lo sono, quindi qui nessuna riduzione.
Il calcolo prepara la richiesta: la misura la decide il giudice con il decreto (art. 168).
"""

from __future__ import annotations

from typing import Any

from pct.ctu_compensi.tabella_dm_2002 import DECRETO, NOTA_ART_29, VOCI
from pct.ctu_compensi.vacazioni import onorario_vacazioni
from pct.formatting import format_euro_it

TABELLE_ADEGUATE_ART_54 = False
FONTI = ["D.P.R. 115/2002, artt. 49-58, 71, 168-170", f"{DECRETO} (tabella degli onorari)", "L. 319/1980, art. 4",
         "Corte cost. 16/2025 (vacazioni successive)", "Corte cost. 192/2015 e 166/2022 (patrocinio a spese dello Stato)"]


def _num(valore: Any, predefinito: float = 0.0) -> float:
    try:
        return float(str(valore).replace(",", ".")) if str(valore).strip() else predefinito
    except (TypeError, ValueError):
        return predefinito


def euro(valore: float) -> str:
    return format_euro_it(valore)


def forbice_voce(codice: str, valore: float = 0.0, quantita: int = 1) -> dict[str, Any]:
    voce = VOCI.get(str(codice))
    if voce is None:
        raise ValueError("Voce della tabella non riconosciuta.")
    note: list[str] = [voce["nota"]] if voce.get("nota") else []
    quantita = max(int(quantita or 1), 1)
    if voce["tipo"] == "scaglioni":
        if valore <= 0:
            raise ValueError(f"{voce['titolo']}: indica il valore ({voce['base']}).")
        minimo = massimo = precedente = 0.0
        for limite, pmin, pmax in voce["scaglioni"]:
            if valore <= precedente:
                break
            quota = min(valore, limite) - precedente
            minimo += quota * pmin / 100
            massimo += quota * pmax / 100
            precedente = limite
        if valore > voce["scaglioni"][-1][0]:
            note.append(f"La tabella si ferma a {euro(voce['scaglioni'][-1][0])}: l'eccedenza non ha una percentuale propria.")
        minimo, massimo = minimo * voce["fattore"], massimo * voce["fattore"]
        if minimo < voce["minimo"]:
            note.append(f"Applicato il compenso minimo della voce ({euro(voce['minimo'])}).")
        minimo, massimo = max(minimo, voce["minimo"]), max(massimo, voce["minimo"])
    else:
        minimo, massimo = voce["minimo"], voce["massimo"]
        successivi = voce.get("successivi")
        if quantita > 1:
            fmin, fmax = successivi if successivi else (1.0, 1.0)
            minimo += (quantita - 1) * voce["minimo"] * fmin
            massimo += (quantita - 1) * voce["massimo"] * fmax
            if successivi:
                note.append(f"{quantita - 1} {voce['unita']} successivi al primo con la riduzione prevista dalla tabella.")
    return {"codice": str(codice), "titolo": voce["titolo"], "valore": round(valore, 2), "quantita": quantita,
            "minimo": round(minimo, 2), "massimo": round(massimo, 2), "note": note}


def compenso(dati: dict[str, Any]) -> dict[str, Any]:
    modalita = str(dati.get("modalita") or "tabella")
    note: list[str] = []
    righe: list[dict[str, Any]] = []
    if modalita == "tabella":
        voci = [v for v in (dati.get("voci") or []) if isinstance(v, dict) and v.get("codice")]
        if not voci:
            raise ValueError("Aggiungi almeno una voce della tabella.")
        righe = [forbice_voce(v["codice"], _num(v.get("valore")), int(_num(v.get("quantita"), 1))) for v in voci[:20]]
        posizione = min(max(_num(dati.get("posizione"), 50.0), 0.0), 100.0)
        minimo = round(sum(r["minimo"] for r in righe), 2)
        massimo = round(sum(r["massimo"] for r in righe), 2)
        base = round(minimo + (massimo - minimo) * posizione / 100, 2)
        note.append(f"Onorario proposto al {posizione:g}% della forbice fra minimo e massimo (art. 51: difficoltà, "
                    "completezza e pregio della prestazione).")
        note.append(NOTA_ART_29)
    elif modalita == "vacazioni":
        vacazioni = _num(dati.get("vacazioni"))
        if vacazioni <= 0:
            raise ValueError("Indica le vacazioni o registra le operazioni con la loro durata.")
        esito = onorario_vacazioni(vacazioni, termine_giorni=int(_num(dati.get("termine_giorni"))) or None,
                                   aumento_urgenza=_num(dati.get("aumento_urgenza")) or None)
        minimo = massimo = base = esito["onorario"]
        posizione = 100.0
        righe = [{"codice": "vacazioni", "titolo": f"{vacazioni:g} {'vacazione' if vacazioni == 1 else 'vacazioni'} da {euro(14.68)} (art. 4 L. 319/1980)",
                  "valore": 0, "quantita": vacazioni, "minimo": base, "massimo": base, "note": esito["note"]}]
        note.append(f"Ogni vacazione vale quanto la prima (Corte cost. 16/2025): {euro(14.68)}.")
    else:
        raise ValueError("Scegli il criterio: tabella o vacazioni.")

    passaggi: list[dict[str, Any]] = []
    onorario = base
    aumento = min(max(_num(dati.get("aumento_eccezionale"), 1.0), 1.0), 2.0)
    if aumento > 1:
        if not str(dati.get("motivazione_aumento") or "").strip():
            raise ValueError("L'aumento fino al doppio (art. 52 c. 1) va motivato con l'eccezionale importanza, complessità e difficoltà.")
        onorario = round(onorario * aumento, 2)
        passaggi.append({"voce": f"Aumento per eccezionale importanza ×{aumento:g} (art. 52 c. 1)", "onorario": onorario})
    componenti = max(int(_num(dati.get("componenti_collegio"), 1)), 1)
    if componenti > 1:
        if dati.get("collegio_per_intero"):
            passaggi.append({"voce": f"Collegio di {componenti}: ognuno svolge l'incarico per intero (art. 53)", "onorario": onorario})
            note.append("Incarico collegiale per intero: il compenso indicato spetta a ciascun componente.")
        else:
            onorario = round(onorario * (1 + 0.4 * (componenti - 1)), 2)
            passaggi.append({"voce": f"Collegio di {componenti}: +40% per ciascun altro componente (art. 53)", "onorario": onorario})
    if dati.get("ritardo"):
        onorario = round(onorario * 2 / 3, 2)
        passaggi.append({"voce": "Riduzione di un terzo per prestazione completata oltre il termine (art. 52 c. 2)", "onorario": onorario})

    patrocinio = str(dati.get("patrocinio") or "")
    if patrocinio in {"civile", "penale"}:
        norma = "art. 130 (metà)" if patrocinio == "civile" else "art. 106-bis (un terzo)"
        if TABELLE_ADEGUATE_ART_54:
            raise ValueError("Tabelle adeguate: aggiornare il calcolo della riduzione per il patrocinio a spese dello Stato.")
        note.append(f"Patrocinio a spese dello Stato: la riduzione dell'{norma} non si applica all'ausiliario perché le "
                    "tabelle non sono state adeguate (Corte cost. " + ("166/2022)." if patrocinio == "civile" else "192/2015)."))

    spese_viaggio = round(_num(dati.get("spese_viaggio")), 2)
    spese = round(_num(dati.get("spese_documentate")), 2)
    contributo_perc = min(max(_num(dati.get("contributo_perc"), 0.0), 0.0), 10.0)
    iva_perc = min(max(_num(dati.get("iva_perc"), 22.0), 0.0), 30.0)
    contributo = round(onorario * contributo_perc / 100, 2)
    iva = round((onorario + contributo) * iva_perc / 100, 2)
    totale = round(onorario + contributo + iva + spese + spese_viaggio, 2)
    if spese:
        note.append("Le spese vanno documentate e allegate all'istanza (art. 56).")
    return {"ok": True, "modalita": modalita, "righe": righe, "minimo": minimo, "massimo": massimo, "posizione": posizione,
            "onorario_base": base, "passaggi": passaggi, "onorario": onorario, "contributo_perc": contributo_perc,
            "contributo": contributo, "iva_perc": iva_perc, "iva": iva, "spese_documentate": spese, "spese_viaggio": spese_viaggio,
            "totale": totale, "note": note, "fonti": FONTI}


__all__ = ["FONTI", "TABELLE_ADEGUATE_ART_54", "compenso", "euro", "forbice_voce"]
