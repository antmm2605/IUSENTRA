"""Calcolatore della procedura atti: termini con il motore dello scadenziario di IUSENTRA, importi in centesimi interi.

Termine dichiarato nella scheda:
  {"id", "descrizione", "evento": {"data": "gg/mm/aaaa", "citazione_fatti": "..."} oppure {"da_termine": "T1"},
   "durata": {"valore": N, "unita": "giorni|mesi|anni"}, "direzione": "avanti|ritroso",
   "natura": "processuale|sostanziale|penale", "sospensione_feriale": bool, "motivo_sospensione": "...",
   "regola": {"fonte": n, "citazione": "frase della Fonte con la durata"}, "motivazione": "..."}
Regole di calcolo (pct.schede_termini / pct.termini_processuali): art. 155 c.p.c. per i processuali (proroga se
sabato o festivo); per sostanziali (art. 2963 c.c.) e penali (art. 172 c.p.p.) il sabato non proroga; L. 742/1969
solo se la scheda la dichiara. Gli anni si contano come 12 mesi.

Importo: {"id", "descrizione", "operazione": "somma|differenza|prodotto",
          "operandi": [{"centesimi": int, "provenienza": "fatti", "citazione": "..."} | {"provenienza": "importo:<id>"}
                       | {"valore": 2, "provenienza": "moltiplicatore"}]}
Nel prodotto il moltiplicatore e' un intero (non in centesimi). Nessun arrotondamento nascosto.
"""
from __future__ import annotations

from datetime import date, datetime

from pct.schede_termini import calcola


def euro(centesimi: int) -> str:
    segno = "-" if centesimi < 0 else ""
    c = abs(int(centesimi))
    intero = f"{c // 100:,}".replace(",", ".")
    return f"{segno}{intero},{c % 100:02d}"


def calcola_termine(t: dict, precedenti: dict[str, str] | None = None) -> dict:
    """``evento`` e' una data dei fatti oppure {"da_termine": "T1"}: decorre dalla scadenza di un termine gia' calcolato
    (es. appello dal quindicesimo giorno per il deposito della motivazione)."""
    ev = t["evento"]
    data = (precedenti or {})[ev["da_termine"]] if ev.get("da_termine") else ev["data"]
    base = datetime.strptime(data, "%d/%m/%Y").date()
    unita, n = t["durata"]["unita"], int(t["durata"]["valore"])
    dich = {"base": "evento", "direzione": t["direzione"], "feriale": bool(t["sospensione_feriale"]),
            "sabato": t["natura"] == "processuale"}
    dich.update({"giorni": n} if unita == "giorni" else {"mesi": n * 12 if unita == "anni" else n})
    r = calcola(dich, base)
    return {"id": t["id"], "descrizione": t["descrizione"], "scadenza": date.fromisoformat(r["scadenza"]).strftime("%d/%m/%Y"),
            "spiegazione": r["spiegazione"], "regola": t.get("regola"), "per_agire": t.get("per_agire"), "verifica_avvocato": r["verifica_avvocato"]}


def calcola_importi(importi: list[dict]) -> list[dict]:
    fatti: dict[str, int] = {}
    out = []
    for imp in importi:
        valori = []
        for o in imp["operandi"]:
            p = o["provenienza"]
            if p.startswith("importo:"):
                valori.append(fatti[p.split(":", 1)[1]])
            elif p == "moltiplicatore":
                valori.append(int(o["valore"]))
            else:
                valori.append(int(o["centesimi"]))
        op = imp["operazione"]
        if op == "somma":
            tot = sum(valori)
        elif op == "differenza":
            tot = valori[0] - sum(valori[1:])
        elif op == "prodotto":  # primo operando in centesimi, gli altri moltiplicatori interi
            tot = valori[0]
            for v in valori[1:]:
                tot *= v
        else:
            raise ValueError(f"operazione non ammessa: {op}")
        fatti[imp["id"]] = tot
        out.append({"id": imp["id"], "descrizione": imp["descrizione"], "centesimi": tot, "euro": euro(tot)})
    return out


def calcola_scheda(scheda: dict) -> dict:
    fatti: dict[str, str] = {}
    termini = []
    for t in scheda.get("termini") or []:
        r = calcola_termine(t, fatti)
        fatti[t["id"]] = r["scadenza"]
        termini.append(r)
    return {"termini": termini,
            "importi": calcola_importi(scheda.get("importi") or [])}
