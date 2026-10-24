"""Contabilita' del credito: capitale, pagamenti, residuo, interessi e spese restano voci separate.

Campo facoltativo della scheda:
  "credito": {
    "voci": [{"id": "F88", "descrizione": "fattura n. 88", "centesimi": 1520000, "citazione": "..."}],
    "pagamenti": [{"id": "P1", "centesimi": 500000, "data": "gg/mm/aaaa", "citazione": "...",
                   "imputazione": "voce:F88" | "interessi" | "spese" | "da_imputare", "motivo_imputazione": "..."}],
    "interessi": {"stato": "non_calcolati" | "dichiarati", "motivo": "...", "centesimi": 0},
    "spese": [{"descrizione": "...", "centesimi": 0, "citazione": "..."}]}
Base normativa: artt. 1193 e 1194 c.c. (imputazione del pagamento: prima agli interessi e alle spese salvo consenso
del creditore; tra piu' debiti scelta del debitore, altrimenti criteri legali). Il software non sceglie l'imputazione:
la registra come dichiarata dall'avvocato e segnala quella «da_imputare».
"""
from __future__ import annotations

from .calcolatore import euro


def _spazi(t: str) -> str:
    return " ".join((t or "").split()).lower()


def verifica_credito(credito: dict, fatti: str) -> list[str]:
    e, f = [], _spazi(fatti)
    ids = {v["id"] for v in credito.get("voci", [])}
    for v in credito.get("voci", []) + credito.get("pagamenti", []) + credito.get("spese", []):
        if not v.get("citazione") or _spazi(v["citazione"]) not in f:
            e.append(f"{v.get('id', v.get('descrizione', '?'))}: citazione non trovata nei fatti")
    for p in credito.get("pagamenti", []):
        imp = p.get("imputazione", "")
        if imp.startswith("voce:") and imp[5:] not in ids:
            e.append(f"{p['id']}: imputato a una voce inesistente")
        elif not (imp.startswith("voce:") or imp in ("interessi", "spese", "da_imputare")):
            e.append(f"{p['id']}: imputazione non ammessa")
    return e


def prospetto(credito: dict) -> dict:
    residui = {v["id"]: int(v["centesimi"]) for v in credito.get("voci", [])}
    non_imputati, a_interessi, a_spese = [], 0, 0
    for p in credito.get("pagamenti", []):
        imp, c = p["imputazione"], int(p["centesimi"])
        if imp.startswith("voce:"):
            residui[imp[5:]] -= c
        elif imp == "interessi":
            a_interessi += c
        elif imp == "spese":
            a_spese += c
        else:
            non_imputati.append(p["id"])
    capitale = sum(int(v["centesimi"]) for v in credito.get("voci", []))
    residuo = sum(residui.values())
    spese = sum(int(s["centesimi"]) for s in credito.get("spese", []))
    return {"capitale": euro(capitale), "pagamenti": euro(sum(int(p["centesimi"]) for p in credito.get("pagamenti", []))),
            "residuo_capitale": euro(residuo), "residui_per_voce": {k: euro(v) for k, v in residui.items()},
            "pagato_a_interessi": euro(a_interessi), "pagato_a_spese": euro(a_spese), "spese": euro(spese),
            "interessi": credito.get("interessi", {"stato": "non_calcolati"}),
            "pagamenti_da_imputare": non_imputati, "voci_negative": [k for k, v in residui.items() if v < 0]}
