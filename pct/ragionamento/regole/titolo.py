"""Il titolo esecutivo dell'esecuzione forzata (art. 474 c.p.c.), anche quando sta nel fascicolo del monitorio.

L'esecuzione forzata non può avere luogo che in virtù di un titolo esecutivo (art. 474 c.p.c.); il precetto lo indica
(art. 480 c.p.c.). Se il titolo è il decreto ingiuntivo pronunciato in un altro fascicolo dello studio per lo stesso
cliente, e gli atti dell'esecuzione lo citano con numero, anno e ufficio, il titolo risulta presente: la prova è il
decreto nel fascicolo collegato (con il provvedimento di esecutorietà, art. 647 c.p.c.) e la citazione nell'atto.
"""

from __future__ import annotations

from ..collegamenti import descrizione, titolo_nei_collegati
from ..modello import Conclusione, Fonte
from ..norme import norme
from ..testo import data_it
from .contesto import Contesto


def conclusioni_titolo(ctx: Contesto) -> tuple[list[Conclusione], list[dict]]:
    if not ctx.rito.codice.startswith("esecuzione") or not ctx.collegati:
        return [], []
    citanti = [a for a in ctx.della_causa() if a.testo]
    trovato = titolo_nei_collegati(citanti, ctx.collegati)
    if not trovato:
        return [], []
    citato = trovato["citato_in"]
    esecutorieta = trovato.get("esecutorieta") or {}
    decreto = trovato.get("decreto") or {}
    prova = (f"Decreto ingiuntivo n. {trovato['decreto_numero']} («{decreto.get('nome', '')}»"
             + (f" del {data_it(decreto.get('data'))}" if decreto.get("data") else "") + ")"
             + (f", dichiarato esecutivo con «{esecutorieta.get('nome')}»" + (f" del {data_it(esecutorieta.get('data'))}" if esecutorieta.get("data") else "")
                if esecutorieta else "")
             + f", nel {descrizione(trovato)}; citato in «{citato['nome']}»")
    conclusione = Conclusione(
        "titolo_esecutivo", f"Titolo esecutivo presente: decreto ingiuntivo n. {trovato['decreto_numero']}"
        + (" dichiarato esecutivo" if esecutorieta else ""),
        Fonte(citato["id"], citato["nome"], citato["brano"], citato.get("data") or ""), norme("cpc_474", "cpc_480"),
        "il titolo è nel fascicolo collegato: per un nuovo deposito se ne usa la copia attestata conforme",
        "l'esecuzione forzata si fonda sul titolo esecutivo indicato nel precetto (artt. 474 e 480 c.p.c.)",
        "fatto", prova, onerato="noi", motivo_senza_termine="Il titolo non ha un termine: è il presupposto dell'esecuzione.",
    )
    return [conclusione], [trovato]


__all__ = ["conclusioni_titolo"]
