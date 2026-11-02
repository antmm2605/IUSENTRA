"""Bozza strutturata del contratto dalla libreria di clausole.

Base normativa: art. 1325 c.c. (requisiti) e art. 1346 c.c. (oggetto); i
testi delle clausole citano la propria norma in ``dati/_clausole.json``.
Fail-closed sui dati: ogni elemento non fornito resta un segnaposto
``[DA COMPLETARE: …]`` visibile, mai un valore inventato. La nota per
l'avvocato (punti aperti, adempimenti, forma) è separata dal testo.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from pct.contratti.catalogo import DATI, clausole_della_famiglia, famiglia, libreria_clausole
from pct.contratti.selezione import valuta

CAMPI = {
    "oggetto": "oggetto del contratto", "corrispettivo": "corrispettivo", "durata": "durata",
    "decorrenza": "data di decorrenza", "foro": "foro competente", "luogo": "luogo",
    "termine_pagamento": "termine di pagamento", "preavviso": "preavviso di recesso",
    "durata_riservatezza": "durata dell'obbligo di riservatezza", "parte_spese": "parte che sostiene le spese",
    "giorno_pagamento": "giorno di pagamento del canone", "deposito": "mensilità di deposito",
    "termine_collaudo": "termine di collaudo", "durata_garanzia": "durata della garanzia",
    "periodo_migrazione": "periodo di assistenza alla migrazione",
}
# Clausole che, se predisposte da una parte, richiedono approvazione specifica (art. 1341, comma 2, c.c.).
ONEROSE = {
    "recesso": "facoltà di recesso", "recesso_conduttore": "recesso del conduttore", "risoluzione": "clausola risolutiva espressa",
    "sw_responsabilita": "limitazione di responsabilità", "legge_foro": "deroga alla competenza dell'autorità giudiziaria",
    "sublocazione_divieto": "divieto di sublocazione e cessione",
    "recesso_conduttore_diverso": "recesso del conduttore", "sublocazione_diverso": "limiti alla sublocazione e alla cessione",
    "cessione_contratto": "divieto di cessione del contratto", "agenzia_non_concorrenza": "patto di non concorrenza",
    "agenzia_zona": "esclusiva", "sw_garanzia": "limitazioni della garanzia", "riservatezza": "obblighi di riservatezza post-contrattuali",
    "fideiussione_escussione": "rinuncia all'eccezione di preventiva escussione", "incarico_recesso": "recesso dall'incarico",
}
_SEGNAPOSTO = re.compile(r"\{([a-z_]+)\}")


@lru_cache(maxsize=1)
def _ruoli() -> dict:
    return json.loads((DATI / "_ruoli.json").read_text(encoding="utf-8"))


def ruoli(contratto_id: str) -> list[str]:
    dati = _ruoli()
    return list(dati["per_contratto"].get(contratto_id, dati["predefiniti"]))


def _mancante(campo: str) -> str:
    return f"[DA COMPLETARE: {CAMPI.get(campo, campo.replace('_', ' '))}]"


def _comparente(parte: dict, ruolo: str) -> str:
    nome = (parte.get("nome") or "").strip()
    if not nome:
        return f"{_mancante('dati del ' + ruolo.lower())}, di seguito «{ruolo}»"
    pezzi = [nome]
    if parte.get("codice_fiscale"):
        pezzi.append(f"C.F./P.IVA {parte['codice_fiscale']}")
    if parte.get("sede"):
        pezzi.append(f"con sede/residenza in {parte['sede']}")
    if parte.get("pec"):
        pezzi.append(f"PEC {parte['pec']}")
    if parte.get("rappresentante"):
        pezzi.append(f"in persona di {parte['rappresentante']}, munito dei necessari poteri")
    return ", ".join(pezzi) + f", di seguito «{ruolo}»"


def _compila(testo: str, valori: dict[str, str]) -> tuple[str, list[str]]:
    mancanti: list[str] = []

    def sostituisci(match: re.Match) -> str:
        chiave = match.group(1)
        valore = (valori.get(chiave) or "").strip()
        if valore:
            return valore
        mancanti.append(chiave)
        return _mancante(chiave)

    return _SEGNAPOSTO.sub(sostituisci, testo), mancanti


def componi(contratto_id: str, dati: dict | None = None, fatti: dict | None = None) -> dict:
    """Bozza: comparenti, articoli numerati, firme, approvazione specifica e nota per l'avvocato."""
    dati = dict(dati or {})
    contratto = famiglia(contratto_id)
    valutazione = valuta(contratto_id, fatti or {})
    nomi_ruoli = ruoli(contratto_id)
    parti = list(dati.get("parti") or [])[:2] + [{}] * max(0, 2 - len(dati.get("parti") or []))
    valori = {k: str(v) for k, v in (dati.get("campi") or {}).items() if isinstance(v, (str, int, float))}
    valori.setdefault("parte_a", nomi_ruoli[0])
    valori.setdefault("parte_b", nomi_ruoli[1])
    if parti[0].get("nome"):
        valori["parte_a"] = f"{nomi_ruoli[0]} {parti[0]['nome']}"
    if parti[1].get("nome"):
        valori["parte_b"] = f"{nomi_ruoli[1]} {parti[1]['nome']}"

    if "deposito" not in valori and (fatti or {}).get("deposito_mensilita") not in (None, ""):
        valori["deposito"] = str((fatti or {})["deposito_mensilita"])
    libreria = libreria_clausole()["clausole"]
    chiavi = clausole_della_famiglia(contratto)
    onerose = [f"art. {i} ({ONEROSE[c]})" for i, c in enumerate(chiavi, start=1) if c in ONEROSE]
    if not onerose:
        # Nessuna clausola onerosa (art. 1341, comma 2, c.c.): niente articolo di approvazione specifica vuoto.
        chiavi = tuple(c for c in chiavi if c != "approvazione_specifica")
    articoli, da_completare = [], []
    for numero, chiave in enumerate(chiavi, start=1):
        clausola = libreria[chiave]
        modello = clausola["testo"]
        if chiave == "approvazione_specifica":
            modello = ("Ai sensi degli artt. 1341 e 1342 c.c. le parti dichiarano di aver letto e di approvare specificamente "
                       f"le seguenti clausole: {'; '.join(onerose) or '[CLAUSOLE ONEROSE]'}.")
        testo, mancanti = _compila(modello, valori)
        segnaposti = [CAMPI.get(m, m.replace('_', ' ')) for m in mancanti] + re.findall(r"\[([A-Z][A-Z /']+)\]", modello)
        da_completare.extend(segnaposti)
        articoli.append({"numero": numero, "chiave": chiave, "titolo": clausola["titolo"],
                         "testo": testo, "norma": clausola["norma"], "da_completare": bool(segnaposti)})

    variante = valutazione["variante"]
    titolo = contratto.nome.upper() + (f" — {variante['nome']}" if variante else "")
    return {
        "titolo": titolo,
        "contratto_id": contratto.id,
        "luogo_data": f"{valori.get('luogo') or _mancante('luogo')}, {valori.get('data') or _mancante('data di sottoscrizione')}",
        "comparenti": [{"ruolo": r, "testo": _comparente(p, r)} for r, p in zip(nomi_ruoli, parti)],
        "premesse": [p for p in dati.get("premesse", []) if isinstance(p, str) and p.strip()],
        "articoli": articoli,
        "firme": nomi_ruoli,
        "approvazione_specifica": any(a["chiave"] == "approvazione_specifica" for a in articoli),
        "allegati": [a for a in dati.get("allegati", []) if isinstance(a, str) and a.strip()],
        "da_completare": sorted(set(da_completare)),
        "nota_avvocato": {
            "forma": valutazione["forma"],
            "bloccanti": valutazione["bloccanti"],
            "punti_avvocato": valutazione["punti_avvocato"],
            "adempimenti": valutazione["adempimenti"],
            "domande_aperte": valutazione["domande_aperte"],
            "riferimenti": valutazione["scheda"]["normativa"],
            "avvertenza": "Bozza generata dal catalogo dello studio: testo da rivedere e approvare dall'avvocato; "
                          "riferimenti da verificare sulla fonte ufficiale vigente.",
        },
        "pronta": valutazione["pronto_per_redazione"] and not da_completare,
    }


def campi_richiesti(contratto_id: str) -> list[dict[str, str]]:
    """Campi da raccogliere per compilare le clausole della famiglia (ordine di comparsa)."""
    libreria = libreria_clausole()["clausole"]
    chiavi: dict[str, None] = {"luogo": None, "data": None}
    for chiave in clausole_della_famiglia(famiglia(contratto_id)):
        for campo in _SEGNAPOSTO.findall(libreria[chiave]["testo"]):
            if campo not in ("parte_a", "parte_b"):
                chiavi[campo] = None
    etichette = {**CAMPI, "data": "data di sottoscrizione"}
    return [{"id": c, "etichetta": etichette.get(c, c.replace("_", " ")).capitalize()} for c in chiavi]
