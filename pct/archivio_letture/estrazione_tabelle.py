"""I prospetti a tabella dei documenti: voci, importi e la prova dei conti.

Una nota spese, un decreto di liquidazione, una proforma, un precetto o un
prospetto di interessi portano gli importi in tabella. Letti come testo
lineare, gli importi perdono la voce a cui appartengono; letti come struttura
(`legal_ocr.tabelle`) ogni importo resta nella sua riga, e i conti si possono
rifare: le voci sommate danno il totale scritto?

Il motore documenti ne ricava un fatto per prospetto (categoria «importo»,
campo «prospetto_tabellare»), con la tabella intera come prova e l'esito della
somma. Un prospetto i cui conti non tornano resta «da verificare» con il
motivo: è un errore del documento o della lettura, e in entrambi i casi
l'avvocato lo deve vedere prima di usarlo.

Base normativa degli importi tipici: D.M. 55/2014 art. 2 (rimborso forfettario
delle spese generali), art. 11 L. 576/1980 (contributo integrativo alla Cassa
forense), D.P.R. 633/1972 (IVA), art. 480 c.p.c. (precetto), art. 1284 c.c.
(interessi legali), art. 52 D.P.R. 115/2002 e D.M. 30/05/2002 (compensi degli
ausiliari del giudice).
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from pct.registro_letture.fatti_repository import Fatto

VERSIONE_ESTRAZIONE_TABELLE = "2026.09.26.tabelle.v1"
CAMPO = "prospetto_tabellare"

_TOTALE = re.compile(r"^(?:totale|tot\.|netto|saldo|imponibile(?:\s+iva)?|importo\s+complessivo|somma\s+complessiva|complessivo)\b", re.IGNORECASE)
_SOTTRAZIONE = re.compile(r"ritenuta|acconto\s+(?:gi[aà]\s+)?versat|detrazion|sconto|riduzion|a\s+dedurre", re.IGNORECASE)
_INTESTAZIONE = re.compile(r"^(?:voce|descrizione|importo|rata|periodo|data)\b", re.IGNORECASE)

NORME = (
    (re.compile(r"spese\s+generali|cassa|c\.?p\.?a\.?|contributo\s+integrativo|fase\s+(?:di\s+)?(?:studio|introduttiva|istruttoria|decisionale)", re.I),
     "D.M. 55/2014 art. 2; art. 11 L. 576/1980"),
    (re.compile(r"onorario|consulente|c\.?t\.?u\.?|ausiliari", re.I), "art. 52 D.P.R. 115/2002; D.M. 30/05/2002"),
    (re.compile(r"sorte\s+capitale|precetto", re.I), "art. 480 c.p.c."),
    (re.compile(r"interess", re.I), "art. 1284 c.c."),
    (re.compile(r"\biva\b|imponibile", re.I), "D.P.R. 633/1972"),
)


def importo(valore: str) -> Decimal | None:
    """«€ 1.215,00» → 1215.00; «-460,00» → -460.00."""
    testo = re.sub(r"[^\d,.\-]", "", str(valore or ""))
    negativo = testo.startswith("-")
    testo = testo.lstrip("-")
    if not re.search(r"\d", testo):
        return None
    if "," in testo:
        testo = testo.replace(".", "").replace(",", ".")
    elif testo.count(".") == 1 and len(testo.rpartition(".")[2]) in {1, 2}:
        pass
    else:
        testo = testo.replace(".", "")
    try:
        numero = Decimal(testo).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None
    return -numero if negativo else numero


def _euro(numero: Decimal) -> str:
    return f"€ {numero:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")


def prospetto(tabella: Any) -> dict[str, Any] | None:
    """Voci, totali e verifica dei conti di una tabella con una colonna di importi."""
    righe: list[dict[str, Any]] = []
    for indice, riga in enumerate(getattr(tabella, "righe", ()) or ()):
        celle = [c for c in riga if str(c).strip()]
        if not celle:
            continue
        valore = importo(celle[-1]) if len(celle) >= 2 else None
        voce = " ".join(celle[:-1]).strip() if valore is not None else " ".join(celle)
        if valore is None:
            if indice == 0 and _INTESTAZIONE.match(voce):
                continue
            continue
        if _SOTTRAZIONE.search(voce) and valore > 0:
            valore = -valore
        # Un «totale» senza voci sopra (l'imponibile in prima riga) è una voce.
        righe.append({"voce": voce[:120], "importo": valore, "totale": bool(_TOTALE.match(voce)) and any(not r["totale"] for r in righe)})
    voci = [r for r in righe if not r["totale"]]
    if len(righe) < 3 or not voci:
        return None
    controlli: list[str] = []
    errori: list[str] = []
    dall_ultimo: list[Decimal] = []
    ultimo_totale: Decimal | None = None
    for riga in righe:
        if not riga["totale"]:
            dall_ultimo.append(riga["importo"])
            continue
        parziale = sum(dall_ultimo, Decimal("0"))
        attese = {parziale}
        if ultimo_totale is not None:
            attese.add(ultimo_totale + parziale)
        if any(abs(riga["importo"] - atteso) <= Decimal("0.01") for atteso in attese):
            controlli.append(f"«{riga['voce']}» {_euro(riga['importo'])}: la somma delle voci torna")
        else:
            vicina = min(attese, key=lambda atteso: abs(riga["importo"] - atteso))
            errori.append(f"«{riga['voce']}» {_euro(riga['importo'])}: le voci sommano {_euro(vicina)}")
        ultimo_totale = riga["importo"]
        dall_ultimo = []
    totale = righe[-1]["importo"] if righe[-1]["totale"] else sum((r["importo"] for r in voci), Decimal("0"))
    testo_righe = " ".join(r["voce"] for r in righe)
    norma = next((n for schema, n in NORME if schema.search(testo_righe)), "prospetto del documento")
    esito = "errore" if errori else "ok" if controlli else "attenzione"
    return {
        "righe": [{"voce": r["voce"], "importo": f"{r['importo']:.2f}", "totale": r["totale"]} for r in righe],
        "totale": totale,
        "somma": esito,
        "dettaglio": "; ".join(errori or controlli) or "nessuna riga di totale: i conti non si possono rifare",
        "norma": norma,
    }


def fatti_prospetti(testo: str, *, origine: str) -> list[Fatto]:
    """Un fatto per ogni prospetto a tabella del documento, con la tabella come prova."""
    from legal_ocr.tabelle import tabelle_del_testo

    fatti: list[Fatto] = []
    for tabella in tabelle_del_testo(testo):
        letto = prospetto(tabella)
        if letto is None or letto["totale"] <= 0:
            continue
        prima = letto["righe"][0]["voce"]
        fatti.append(Fatto(
            categoria="importo", campo=CAMPO, valore=f"{letto['totale']:.2f}",
            valore_letto=f"{prima} … {letto['righe'][-1]['voce']}"[:200],
            etichetta=f"Prospetto a tabella: {letto['righe'][-1]['voce']} {_euro(letto['totale'])}"[:200],
            contesto=getattr(tabella, "testo")()[:300], origine=origine,
            prove=[
                {"codice": "tabella", "esito": "ok", "dettaglio": json.dumps(
                    {"pagina": tabella.pagina, "origine": tabella.origine, "righe": letto["righe"]}, ensure_ascii=False)},
                {"codice": "somma", "esito": letto["somma"], "dettaglio": letto["dettaglio"]},
                {"codice": "norma", "esito": "ok", "dettaglio": letto["norma"]},
            ],
        ))
    return fatti


__all__ = ["CAMPO", "VERSIONE_ESTRAZIONE_TABELLE", "fatti_prospetti", "importo", "prospetto"]
