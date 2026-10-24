"""Revisione della bozza direttamente contro fascicolo, Fonti e calcolatore, SENZA guardare la scheda.

Serve a non approvare una bozza solo perche' ripete fedelmente una scheda sbagliata. Rileva:
- norme fuori dalle Fonti, richiami [n] sbagliati o inesistenti (controlla_atto);
- conclusioni o domande contrarie alla parte assistita;
- date e importi che non vengono dai fatti, dalle Fonti o dal calcolatore;
- pagamenti/acconti presenti nei fatti e ignorati dalla bozza;
- termini che il calcolatore da' per scaduti e che la bozza non segnala.
Non certifica la correttezza giuridica.
"""
from __future__ import annotations

import re
from datetime import datetime

from .controlla_atto import controlla
from .verifica_scheda import contraria

DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
EURO = re.compile(r"(?:€\s*|euro\s+)(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)|(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)\s*(?:€|euro\b)", re.I)
PAGAMENTO = re.compile(r"(acconto|versat\w*|pagat\w*|bonific\w*|corrispost\w*|saldat\w*)[^.\n]{0,60}?(\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2})?\s*(?:euro|€)|(\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2})?\s*(?:euro|€)[^.\n]{0,40}?(acconto|versat\w*|pagat\w*|bonific\w*)", re.I)


def _centesimi(s: str) -> int | None:
    t = s.replace(".", "").replace(",", ".")
    try:
        return round(float(t) * 100)
    except ValueError:
        return None


def _date(t: str) -> set[str]:
    return {f"{int(g):02d}/{int(m):02d}/{a}" for g, m, a in DATA.findall(t or "")}


def _importi(t: str) -> set[int]:
    out = set()
    for m in re.finditer(r"\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?", t or ""):
        v = _centesimi(m.group(0))
        if v is not None:
            out.add(v)
    return out


ASSENTE = re.compile(r"non\s+fornit|non\s+(?:è|e'|sono|risulta\w*|presente|present\w*|compres\w*|inclus\w*|tra)\b[^.\n]{0,25}(?:fonti|fornit)|da verificare|fuori dalle fonti|norm\w* mancant|mancant\w* (?:nelle|tra le) fonti|non disponibil|da acquisire|non (?:è|e') (?:tra|nelle) le fonti", re.I)


def _dichiarata_assente(bozza: str, frammento: str) -> bool:
    art = re.escape(frammento.split()[1]) if len(frammento.split()) > 1 else ""
    for m in re.finditer(r"art\.\s*" + art, bozza or "", re.I):
        if ASSENTE.search(bozza[m.start(): m.end() + 90]):
            return True
    return False


def _per_agire(t: dict) -> bool:
    """Solo i termini entro cui la parte assistita deve agire; le scadenze di pagamento o i termini della controparte no."""
    if t.get("per_agire") is not None:
        return bool(t["per_agire"])
    return not re.search(r"pagament|decorrenza|interess|titolare|controparte|debitore|scadenza (?:della|delle) fattur", t.get("descrizione", ""), re.I)


def rivedi(bozza: str, caso: dict, calcoli: dict) -> dict:
    gravi, pendenti = [], []
    fonti_txt = "\n\n".join(f"[{n}] {t}" for n, t in sorted(caso["fonti"].items()))
    base = {"fonti_ref": caso["fonti_ref"], "fonti": fonti_txt, "scheda_risolta": caso["fatti"] + " " + caso["richiesta"],
            "scadenze": [], "oggi": caso["oggi"], "assistito": caso["parte_assistita"], "controparte": caso["controparte"],
            "dati_mancanti": False}
    v = controlla(bozza, base, caso["fatti"])
    for g in v["gravi"]:
        if g[0] in ("data_inventata", "dati_inventati"):
            continue
        if g[0] == "norma_fuori_fonti" and _dichiarata_assente(bozza, g[1]):
            pendenti.append(("norma_dichiarata_assente_dalle_fonti", g[1]))  # la bozza la segnala come da verificare
            continue
        gravi.append(g)
    for riga in (bozza or "").splitlines():
        if contraria(riga):
            gravi.append(("conclusione_contraria_assistito", riga.strip()[:100]))
    origine = caso["fatti"] + " " + caso["richiesta"] + " " + caso["oggi"]
    date_ok = _date(origine) | _date(fonti_txt) | {t["scadenza"] for t in calcoli.get("termini", [])}
    for d in sorted(_date(bozza) - date_ok):
        if d[:5] not in ("01/08", "31/08"):
            pendenti.append(("data_senza_provenienza", d))
    imp_ok = _importi(origine) | _importi(fonti_txt) | {i["centesimi"] for i in calcoli.get("importi", [])}
    for m in EURO.finditer(bozza or ""):
        c = _centesimi(m.group(1) or m.group(2))
        if c is not None and c not in imp_ok:
            pendenti.append(("importo_senza_provenienza", m.group(0).strip()))
    for m in PAGAMENTO.finditer(caso["fatti"]):
        cifra = m.group(2) or m.group(3)
        c = _centesimi(cifra)
        if c and c not in _importi(bozza):
            gravi.append(("pagamento_ignorato", m.group(0).strip()[:80]))
    oggi = datetime.strptime(caso["oggi"], "%d/%m/%Y").date()
    for t in calcoli.get("termini", []):
        if not _per_agire(t):
            continue
        if datetime.strptime(t["scadenza"], "%d/%m/%Y").date() < oggi and not re.search(
                r"scadut|decors|decadenz|decaduto|tardiv|spirat|precluso|inutilmente|prescritt", bozza or "", re.I):
            gravi.append(("termine_scaduto_non_segnalato", f"{t['descrizione'][:60]}: {t['scadenza']}"))
    if caso["parte_assistita"]["nome"].split()[-1].lower() not in (bozza or "").lower():
        pendenti.append(("assistito_non_nominato", caso["parte_assistita"]["nome"]))
    return {"gravi": gravi, "pendenti": pendenti, "avvisi": v["avvisi"]}
