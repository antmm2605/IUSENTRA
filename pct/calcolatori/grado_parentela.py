"""Grado di parentela e affinità — computo civilistico.

Base normativa:
- Art. 74 c.c. (parentela), art. 75 c.c. (linee), art. 76 c.c. (computo dei
  gradi): nella linea retta si computano tanti gradi quante sono le
  generazioni, escluso lo stipite; nella linea collaterale i gradi si
  computano dalle generazioni, salendo da uno dei parenti fino allo stipite
  comune e da questo discendendo all'altro parente, sempre restando escluso
  lo stipite.
- Art. 77 c.c.: la legge non riconosce il vincolo di parentela oltre il
  sesto grado, salvo effetti specialmente determinati.
- Art. 78 c.c. (affinità): l'affine è nel grado in cui il coniuge è parente.

Il tool offre le relazioni tipiche precalcolate e il computo manuale per
generazioni; segnala la rilevanza successoria (art. 572 c.c., successione
dei collaterali entro il sesto grado).
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from pct.calcolatori._base import clean_text, safe_int

_FONTE_CC = {
    "code": "cc_artt_74_78",
    "title": "Artt. 74-78 c.c. — parentela e affinità",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262",
}

# Relazioni tipiche: (linea, generazioni dal primo allo stipite, dal secondo allo stipite).
_RELAZIONI_TIPICHE: Dict[str, Dict[str, Any]] = {
    "genitore_figlio": {"label": "Genitore e figlio", "linea": "retta", "su": 1, "giu": 0},
    "nonno_nipote": {"label": "Nonno e nipote (di figlio)", "linea": "retta", "su": 2, "giu": 0},
    "bisnonno_pronipote": {"label": "Bisnonno e pronipote", "linea": "retta", "su": 3, "giu": 0},
    "fratelli": {"label": "Fratelli / sorelle", "linea": "collaterale", "su": 1, "giu": 1},
    "zio_nipote": {"label": "Zio e nipote (di fratello)", "linea": "collaterale", "su": 2, "giu": 1},
    "cugini": {"label": "Cugini (figli di fratelli)", "linea": "collaterale", "su": 2, "giu": 2},
    "prozio_pronipote": {"label": "Prozio e pronipote", "linea": "collaterale", "su": 3, "giu": 1},
    "cugini_secondi": {"label": "Cugini di secondo grado (figli di cugini)", "linea": "collaterale", "su": 3, "giu": 3},
    "figlio_cugino": {"label": "Uno e il figlio del proprio cugino", "linea": "collaterale", "su": 2, "giu": 3},
}


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    relazione = clean_text(payload.get("par_relazione"))
    affinita = clean_text(payload.get("par_affinita")) == "1"

    if relazione and relazione != "manuale":
        voce = _RELAZIONI_TIPICHE.get(relazione)
        if not voce:
            raise ValueError("Relazione tipica non riconosciuta.")
        linea = voce["linea"]
        gen_su = int(voce["su"])
        gen_giu = int(voce["giu"])
        etichetta = voce["label"]
    else:
        linea = clean_text(payload.get("par_linea")) or "collaterale"
        gen_su = safe_int(payload.get("par_generazioni_su"))
        gen_giu = safe_int(payload.get("par_generazioni_giu"))
        etichetta = "Computo manuale"
        if linea not in ("retta", "collaterale"):
            raise ValueError("Linea ammessa: retta o collaterale.")
        if linea == "retta":
            if gen_su <= 0 and gen_giu <= 0:
                raise ValueError("Nella linea retta indica il numero di generazioni tra i due parenti.")
            gen_su, gen_giu = max(gen_su, gen_giu), 0
        else:
            if gen_su <= 0 or gen_giu <= 0:
                raise ValueError(
                    "Nella linea collaterale servono le generazioni di entrambi i rami "
                    "fino allo stipite comune (es. fratelli: 1 e 1)."
                )
        if gen_su > 10 or gen_giu > 10:
            raise ValueError("Computo gestito fino a 10 generazioni per ramo.")

    grado = gen_su + gen_giu

    notes = [
        "Computo ex art. 76 c.c.: tante generazioni quanti i gradi, escluso lo stipite.",
    ]
    warnings = []
    if affinita:
        rilevanza = "nessuna: gli affini non sono successibili (art. 565 c.c.)"
        notes.append(
            "Affinità (art. 78 c.c.): l'affine è nel grado in cui il coniuge è parente; "
            "il grado indicato vale come grado di affinità. L'affinità non attribuisce "
            "diritti successori, ma rileva ad altri fini (es. obbligo alimentare ex "
            "art. 433, nn. 4-5, c.c., astensione e ricusazione, incompatibilità)."
        )
    elif grado > 6:
        rilevanza = "oltre il 6° grado — irrilevante"
        warnings.append(
            "Oltre il sesto grado la legge non riconosce il vincolo di parentela, "
            "salvo effetti specialmente determinati (art. 77 c.c.); nessun diritto "
            "successorio (art. 572, ultimo comma, c.c.)."
        )
    else:
        rilevanza = "entro il 6° grado"
        if linea == "collaterale":
            if grado == 2:
                notes.append(
                    "Fratelli e sorelle succedono ex artt. 570-571 c.c.; i loro "
                    "discendenti subentrano per rappresentazione (art. 468 c.c.)."
                )
            else:
                notes.append(
                    "Collaterale dal 3° al 6° grado: rileva nella successione degli "
                    "altri parenti (art. 572 c.c.) in mancanza di parenti più prossimi; "
                    "per i discendenti di fratelli opera anche la rappresentazione "
                    "(art. 468 c.c.)."
                )

    return {
        "relazione": etichetta,
        "linea": "Linea retta" if linea == "retta" else "Linea collaterale",
        "grado": grado,
        "generazioni_primo_ramo": gen_su,
        "generazioni_secondo_ramo": gen_giu,
        "affinita": "Sì (art. 78 c.c.)" if affinita else "No",
        "rilevanza_successoria": rilevanza,
        "notes": notes,
        "warnings": warnings,
        "sources": [_FONTE_CC],
    }


def opzioni_relazioni() -> list[dict]:
    voci = [{"value": "manuale", "label": "Computo manuale per generazioni"}]
    voci.extend({"value": chiave, "label": voce["label"]} for chiave, voce in _RELAZIONI_TIPICHE.items())
    return voci
