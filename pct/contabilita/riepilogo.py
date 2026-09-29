"""Riepilogo annuale per cassa dalla prima nota.

- Art. 54 TUIR: il reddito di lavoro autonomo è la differenza fra compensi percepiti e spese sostenute
  nell'anno (principio di cassa). Le anticipazioni in nome e per conto del cliente (art. 15 D.P.R.
  633/1972) non sono compensi né spese.
- Regime forfettario (art. 1 c. 54-89 L. 190/2014): reddito = compensi incassati × 78% (attività
  professionali, Allegato 4) meno i contributi previdenziali versati; imposta sostitutiva 15% (5% per i
  primi cinque anni di nuova attività). Il calcolo riusa ``pct.calcolatori.fiscale_regimi``.
- Gli storni si imputano alla categoria del movimento stornato, nell'anno dello storno.

Stima di supporto: ammortamenti, deduzioni forfettarie e spese a deducibilità limitata (art. 54 c. 5
TUIR) non sono ricostruiti e restano al commercialista.
"""

from __future__ import annotations

from typing import Any

COMPENSI = ("onorari", "altri_incassi")
SPESE_DEDUCIBILI = ("spese_studio", "compensi_terzi", "altri_pagamenti")
MESI = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")


def _per_categoria(movimenti: list[Any], tutti: dict[str, Any]) -> dict[str, float]:
    somme: dict[str, float] = {}
    for m in movimenti:
        if m.storno_di and m.storno_di in tutti:
            originale = tutti[m.storno_di]
            somme[originale.categoria] = somme.get(originale.categoria, 0.0) - float(m.importo)
        else:
            somme[m.categoria] = somme.get(m.categoria, 0.0) + float(m.importo)
    return {k: round(v, 2) for k, v in somme.items()}


def riepilogo_annuale(registro: Any, anno: int, *, regime: str = "RF01", startup: bool = False) -> dict[str, Any]:
    if not 2000 <= int(anno) <= 2100:
        raise ValueError("Anno non valido.")
    movimenti = registro.registro(dal=f"{anno}-01-01", al=f"{anno}-12-31")
    tutti = {m.id: m for m in registro.registro()}
    categorie = _per_categoria(movimenti, tutti)
    compensi = round(sum(categorie.get(c, 0.0) for c in COMPENSI), 2)
    spese = round(sum(categorie.get(c, 0.0) for c in SPESE_DEDUCIBILI), 2)
    contributi = round(categorie.get("contributi_previdenziali", 0.0), 2)
    mesi = []
    for indice, nome in enumerate(MESI, start=1):
        del_mese = [m for m in movimenti if m.data[5:7] == f"{indice:02d}"]
        mesi.append({
            "mese": nome,
            "incassi": round(sum(m.importo for m in del_mese if m.tipo == "INCASSO"), 2),
            "pagamenti": round(sum(m.importo for m in del_mese if m.tipo == "PAGAMENTO"), 2),
        })
    esito: dict[str, Any] = {
        "anno": int(anno),
        "regime": "forfettario" if regime == "RF19" else "ordinario",
        "compensi_incassati": compensi,
        "anticipazioni_rimborsate": round(categorie.get("anticipazioni_rimborsate", 0.0), 2),
        "anticipazioni_per_clienti": round(categorie.get("anticipazioni_clienti", 0.0), 2),
        "spese_deducibili": spese,
        "contributi_previdenziali_versati": contributi,
        "imposte_versate": round(categorie.get("imposte_contributi", 0.0), 2),
        "mesi": mesi,
        "note": [
            "Principio di cassa (art. 54 TUIR): contano incassi e pagamenti avvenuti nell'anno.",
            "Le anticipazioni per conto dei clienti (art. 15 D.P.R. 633/1972) sono escluse da compensi e spese.",
        ],
        "avvisi": [],
    }
    if regime == "RF19":
        from pct.calcolatori.fiscale_regimi import calcola_forfettario

        if compensi > 0:
            forf = calcola_forfettario({"forf_ricavi": compensi, "forf_gruppo": "professionali",
                                        "forf_contributi": contributi, "forf_startup": "1" if startup else "0"})
            esito["stima"] = {
                "reddito_forfettario": forf["reddito_forfettario"], "contributi_dedotti": forf["contributi_dedotti"],
                "imponibile": forf["imponibile"], "aliquota": forf["aliquota"],
                "imposta_sostitutiva": forf["imposta_sostitutiva"], "norma": "art. 1 c. 64 L. 190/2014",
            }
            esito["avvisi"] += list(forf.get("warnings") or [])
        esito["note"].append("Forfettario: compensi × 78% meno i contributi previdenziali versati; imposta sostitutiva "
                             "15% (5% nei primi cinque anni di nuova attività).")
    else:
        esito["stima"] = {"reddito_lavoro_autonomo": round(compensi - spese, 2), "norma": "art. 54 TUIR",
                          "spese_considerate": ", ".join(SPESE_DEDUCIBILI)}
        esito["avvisi"].append("Stima del reddito: non comprende ammortamenti, deduzioni a percentuale e spese a "
                               "deducibilità limitata (art. 54 c. 5 TUIR), che restano al commercialista.")
    if not movimenti:
        esito["avvisi"].append(f"Nessun movimento registrato nel {anno}.")
    return esito


__all__ = ["riepilogo_annuale"]
