"""La fase della causa, dalla sequenza degli atti e delle conclusioni, secondo il percorso del rito.

Ogni fase si dimostra con l'atto che la apre (prova citata): non si deduce dallo stato dichiarato del
fascicolo. Percorsi: cognizione e lavoro (introduttivo → udienza fissata → istruttoria → decisione →
impugnazione o giudicato), monitorio (ricorso → decreto → notifica → esecutorietà → precetto, artt. 633-656
c.p.c.), esecuzione (pignoramento → udienza davanti al giudice dell'esecuzione → assegnazione o vendita).
"""

from __future__ import annotations

from typing import Any

from .modello import Conclusione
from .regole.contesto import Contesto
from .regole.monitorio import decreto_esecutivo, istanza_esecutorieta
from .testo import data_it, semplice


def _stato(conclusioni: list[Conclusione], codice: str) -> str:
    return next((c.stato for c in conclusioni if c.codice == codice), "")


def determina_fase(ctx: Contesto, conclusioni: list[Conclusione]) -> dict[str, Any]:
    causa = ctx.della_causa()
    prove: list[str] = []
    rito = ctx.rito.codice
    future = sorted(u.data for u in ctx.udienze if u.data >= ctx.oggi.isoformat())
    if rito == "monitorio":
        if _stato(conclusioni, "precetto") == "fatto":
            return {"codice": "precetto_notificato", "descrizione": "precetto notificato: si procede al pignoramento", "prove": prove}
        if titolo := decreto_esecutivo(ctx):
            return {"codice": "decreto_esecutivo", "descrizione": "il giudice ha dichiarato esecutivo il decreto",
                    "prove": [titolo.nome]}
        if istanza := istanza_esecutorieta(ctx):
            return {"codice": "istanza_esecutorieta", "descrizione": "istanza di esecutorietà presente, verificare il provvedimento",
                    "prove": [istanza.nome]}
        notifica = next((c for c in conclusioni if c.codice == "notifica_decreto_ingiuntivo"), None)
        if notifica and notifica.stato == "fatto":
            return {"codice": "decreto_notificato", "descrizione": "consegna del ricorso e del decreto verificata",
                    "prove": [notifica.prova_o_motivo]}
        if notifica and notifica.stato == "dubbio":
            return {"codice": "notifica_decreto_da_verificare", "descrizione": "notifica del decreto da riscontrare con la prova di consegna",
                    "prove": [notifica.letto.nome] if notifica.letto else []}
        if notifica and notifica.letto:
            return {"codice": "decreto_emesso", "descrizione": "decreto ingiuntivo emesso, verificare la notifica",
                    "prove": [notifica.letto.nome]}
        return {"codice": "monitorio_in_preparazione", "descrizione": "decreto ingiuntivo da acquisire", "prove": []}
    sentenze = [a for a in causa if a.sentenza]
    if sentenze:
        if _stato(conclusioni, "giudicato") == "da_fare":
            return {"codice": "giudicato_da_verificare", "descrizione": "termine breve maturato, verificare l’impugnazione e il passaggio in giudicato", "prove": [sentenze[0].nome]}
        return {"codice": "decisa", "descrizione": "sentenza presente, verificare decorrenza e stato delle impugnazioni", "prove": [sentenze[0].nome]}
    if rito.startswith("esecuzione"):
        descrizione = "processo esecutivo davanti al giudice dell'esecuzione"
        if future:
            descrizione += f", prossima udienza il {data_it(future[0])}"
        return {"codice": "esecutiva", "descrizione": descrizione, "prove": [a.nome for a in causa if "pignoramento" in semplice(a.etichetta)][:1]}
    udienze_fissate = [u for u in ctx.udienze if u.fonte and u.data >= ctx.oggi.isoformat()]
    if udienze_fissate:
        udienza = min(udienze_fissate, key=lambda u: u.data)
        return {"codice": "udienza_fissata", "descrizione": f"udienza fissata per il {data_it(udienza.data)}",
                "prove": [udienza.fonte.nome]}
    provvedimenti = [a for a in causa if a.autore == "giudice"]
    if provvedimenti:
        return {"codice": "provvedimenti_presenti", "descrizione": "provvedimenti del giudice presenti nel fascicolo",
                "prove": [p.nome for p in provvedimenti[:3]]}
    introduttivo = next((a for a in causa if a.natura == "atto_principale"), None)
    if introduttivo:
        deposito = next((d for d in ctx.depositi if d.accettato and d.fonte_id
                         and set((introduttivo.id, *introduttivo.copie)).intersection(d.documenti_ids)), None)
        if deposito:
            return {"codice": "atto_introduttivo_depositato", "descrizione": "deposito dell’atto introduttivo accettato",
                    "prove": [introduttivo.nome, f"deposito {deposito.fonte_id}"]}
        return {"codice": "atto_introduttivo_presente", "descrizione": "atto introduttivo presente, verificare il deposito",
                "prove": [introduttivo.nome]}
    return {"codice": "preparatoria", "descrizione": "nessun atto introduttivo nel fascicolo", "prove": prove}


__all__ = ["determina_fase"]
