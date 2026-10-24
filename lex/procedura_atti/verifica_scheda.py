"""Verifica software della scheda: COERENZA e PROVENIENZA, non correttezza giuridica.

Passare questa verifica non valida la scheda: una durata scritta nella Fonte puo' essere applicata all'evento
sbagliato, un rimedio coerente puo' essere quello sbagliato. La validazione e' solo dell'avvocato.
"""
from __future__ import annotations

import re

CAMPI = ["forma_risposta", "parte_assistita", "controparte", "obiettivo_cliente", "rimedio", "domande",
         "punti_da_trattare", "termini", "importi", "norme_mancanti", "dati_mancanti"]
CONTRARIA = re.compile(r"(rigettar\w*|respinger\w*|dichiarar\w*\s+(?:infondat\w*|inammissibil\w*|improcedibil\w*))\s+(?:il|la|l['’]|le|i)?\s*(?:presente\s+|propria\s+)?(ricorso|domanda|opposizione|reclamo|appello|istanza|impugnazione)", re.I)
ALTRUI = re.compile(r"(propost[oa] da|di controparte|avversari|del creditore|della controparte|dell[ae]? (resistente|convenut|opposto|creditore|appellat))", re.I)
UNITA_IT = ["", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci", "undici", "dodici",
            "tredici", "quattordici", "quindici", "sedici", "diciassette", "diciotto", "diciannove"]
DECINE_IT = {20: "venti", 30: "trenta", 40: "quaranta", 50: "cinquanta", 60: "sessanta", 70: "settanta", 80: "ottanta", 90: "novanta"}


def in_lettere(n: int) -> str:
    """Numero in lettere come nei testi normativi (1-999): centottanta, novanta, ventuno, trecentosessantacinque."""
    if n < 20:
        return UNITA_IT[n]
    if n < 100:
        d, u = divmod(n, 10)
        base = DECINE_IT[d * 10]
        if u in (1, 8):
            base = base[:-1]
        return base + (UNITA_IT[u] if u else "")
    c, r = divmod(n, 100)
    testa = "cento" if c == 1 else UNITA_IT[c] + "cento"
    if r and in_lettere(r).startswith(("o", "ott")) and r // 10 == 8:
        testa = testa[:-1]
    return testa + (in_lettere(r) if r else "")


def _spazi(t: str) -> str:
    return " ".join((t or "").replace("’", "'").split()).lower()


def _durata_in(citazione: str, valore: int, unita: str) -> bool:
    c = _spazi(citazione)
    u = {"giorni": "giorn", "mesi": "mes", "anni": "ann"}[unita]
    parole = [str(valore), in_lettere(valore)] + (["un", "una"] if valore == 1 else [])
    if unita == "giorni" and valore > 10:
        parole.append(in_lettere(valore)[:-1] + "esimo")  # «quindicesimo giorno», «trentesimo giorno»
    for p in parole:
        if re.search(r"\b" + p + r"\s+(?:\w+\s+)?" + u, c) or re.search(r"\b" + u + r"\w*\s+" + p + r"\b", c):
            return True  # «sessanta giorni» e «giorni sessanta»
    return False


def contraria(frase: str) -> bool:
    for m in CONTRARIA.finditer(frase):
        coda = re.split(r"\s+e\s+|[;,.]", frase[m.end(): m.end() + 80], maxsplit=1)[0]
        if not ALTRUI.search(coda):
            return True
    return False


def verifica(scheda: dict, caso: dict, fonti: dict[int, str]) -> list[str]:
    e = [f"campo mancante: {k}" for k in CAMPI if k not in scheda]
    if e:
        return e
    if scheda["forma_risposta"] not in ("atto", "consulenza"):
        e.append("forma_risposta deve essere atto o consulenza")
    if _spazi(scheda["parte_assistita"].get("nome")) != _spazi(caso["parte_assistita"]["nome"]):
        e.append("parte assistita diversa dal fascicolo")
    if not scheda["domande"]:
        e.append("nessuna domanda/conclusione")
    for d in scheda["domande"]:
        if contraria(d):
            e.append(f"domanda contraria alla parte assistita: {d[:80]}")
    fatti = _spazi(caso["fatti"] + " " + caso["richiesta"])
    visti: set[str] = set()
    for t in scheda["termini"]:
        tid = t.get("id", "?")
        visti.add(tid)
        ev = t.get("evento", {})
        if ev.get("da_termine"):
            if ev["da_termine"] not in visti or ev["da_termine"] == tid:
                e.append(f"termine {tid}: decorre da un termine non dichiarato prima ({ev['da_termine']})")
        elif _spazi(ev.get("citazione_fatti")) not in fatti or not ev.get("citazione_fatti"):
            e.append(f"termine {tid}: citazione dell'evento non trovata nei fatti")
        elif ev.get("data") != caso["oggi"] and ev.get("data", "") not in ev.get("citazione_fatti", ""):
            e.append(f"termine {tid}: la data dell'evento non compare nella citazione dei fatti")
        r = t.get("regola", {})
        testo = _spazi(fonti.get(int(r.get("fonte", 0) or 0), ""))
        if not r.get("citazione") or _spazi(r["citazione"]) not in testo:
            e.append(f"termine {tid}: citazione della regola non trovata nella Fonte [{r.get('fonte')}]")
        elif not _durata_in(r["citazione"], int(t["durata"]["valore"]), t["durata"]["unita"]):
            e.append(f"termine {tid}: la durata non compare nella citazione della regola")
        if t.get("natura") not in ("processuale", "sostanziale", "penale"):
            e.append(f"termine {tid}: natura non indicata")
        if t.get("sospensione_feriale") and not t.get("motivo_sospensione"):
            e.append(f"termine {tid}: sospensione feriale senza motivo")
        if not t.get("motivazione"):
            e.append(f"termine {tid}: manca la motivazione della scelta della regola")
    ids = set()
    for imp in scheda["importi"]:
        for o in imp.get("operandi", []):
            p = o.get("provenienza", "")
            if p == "fatti":
                cit = _spazi(o.get("citazione"))
                cifra = f"{int(o['centesimi']) // 100:,}".replace(",", ".")
                if not cit or cit not in fatti or (cifra not in cit and cifra.replace(".", "") not in cit):
                    e.append(f"importo {imp.get('id')}: operando {o.get('centesimi')} senza citazione dai fatti")
            elif p.startswith("importo:"):
                if p.split(":", 1)[1] not in ids:
                    e.append(f"importo {imp.get('id')}: rimanda a un importo non ancora calcolato")
            elif p == "moltiplicatore":
                v = int(o.get("valore", 0))
                cit = _spazi(o.get("citazione"))
                fonti_tutte = " ".join(_spazi(x) for x in fonti.values())
                citato = cit and (cit in fatti or cit in fonti_tutte) and (str(v) in cit or in_lettere(v) in cit)
                if imp.get("operazione") != "prodotto" or v < 1 or (v > 10 and not citato):
                    e.append(f"importo {imp.get('id')}: moltiplicatore {v} non ammesso (oltre 10 serve la citazione da fatti o Fonti)")
            else:
                e.append(f"importo {imp.get('id')}: provenienza sconosciuta")
        ids.add(imp.get("id"))
    return e
