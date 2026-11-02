"""Caricamento e validazione del catalogo contratti da ``dati/*.json``.

Base normativa: art. 1322 c.c.; ogni voce dichiara i propri riferimenti.
Il caricamento è fail-closed: una voce senza riferimenti normativi, con forma
o qualificazione sconosciute o con id duplicato blocca il catalogo.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pct.contratti.modelli import FORME, QUALIFICAZIONI, Contratto, Controllo, Domanda, Variante

DATI = Path(__file__).with_name("dati")
ESITI = ("blocco", "valutazione_avvocato", "adempimento", "avviso")


class CatalogoContrattiNonValido(ValueError):
    """Il catalogo contiene una voce priva di base normativa o malformata."""


def _leggi(nome: str) -> object:
    return json.loads((DATI / nome).read_text(encoding="utf-8"))


def _contratto(area: str, voce: dict) -> Contratto:
    if not voce.get("rif"):
        raise CatalogoContrattiNonValido(f"{voce.get('id')}: nessun riferimento normativo")
    forma = voce.get("forma", "scritta")
    qual = voce.get("qual", "tipico")
    if forma not in FORME or qual not in QUALIFICAZIONI:
        raise CatalogoContrattiNonValido(f"{voce['id']}: forma o qualificazione sconosciuta")
    controlli = tuple(Controllo(**c) for c in voce.get("controlli", ()))
    for c in controlli:
        if c.esito not in ESITI or not c.norma:
            raise CatalogoContrattiNonValido(f"{voce['id']}.{c.id}: esito o norma non validi")
    return Contratto(
        id=voce["id"], nome=voce["nome"], area=area, riferimenti=tuple(voce["rif"]),
        qualificazione=qual, forma=forma, note=voce.get("note", ""),
        varianti=tuple(
            Variante(id=v["id"], nome=v["nome"], riferimenti=tuple(v["rif"]),
                     quando=v.get("quando", {}), forma=v.get("forma", forma))
            for v in voce.get("varianti", ())
        ),
        domande=tuple(
            Domanda(id=d["id"], testo=d["testo"], tipo=d.get("tipo", "si_no"),
                    opzioni=tuple(d.get("opzioni", ())))
            for d in voce.get("domande", ())
        ),
        controlli=controlli,
        clausole=tuple(voce.get("clausole", ())),
    )


@lru_cache(maxsize=1)
def libreria_clausole() -> dict:
    return _leggi("_clausole.json")


def clausole_della_famiglia(contratto: Contratto) -> tuple[str, ...]:
    """Chiavi delle clausole della bozza: proprie della famiglia o predefinite, più le finali."""
    lib = libreria_clausole()
    base = contratto.clausole or tuple(lib["predefinite"])
    if contratto.id in lib.get("foro_immobile_per", ()):
        # Locazione, comodato di immobili e affitto d'azienda: giudice del luogo dell'immobile (art. 21 c.p.c.)
        # e clausole di deroga alla competenza nulle (art. 447-bis, comma 2, c.p.c.).
        base = tuple("foro_immobile" if chiave == "legge_foro" else chiave for chiave in base)
    return tuple(dict.fromkeys((*base, *lib["finali"])))


@lru_cache(maxsize=1)
def _comuni() -> dict:
    return _leggi("_domande_comuni.json")


def domande_comuni() -> tuple[Domanda, ...]:
    return tuple(Domanda(id=d["id"], testo=d["testo"]) for d in _comuni()["domande"])


def controlli_comuni() -> tuple[Controllo, ...]:
    return tuple(Controllo(**c) for c in _comuni()["controlli"])


@lru_cache(maxsize=1)
def _indice() -> dict[str, Contratto]:
    meta = _leggi("_aree.json")
    indice: dict[str, Contratto] = {}
    for area in meta["aree"]:
        for voce in _leggi(f"{area}.json"):
            if voce["id"] in indice:
                raise CatalogoContrattiNonValido(f"id duplicato: {voce['id']}")
            indice[voce["id"]] = _contratto(area, voce)
    note = set(libreria_clausole()["clausole"])
    for contratto in indice.values():
        mancanti = set(contratto.clausole) - note
        if mancanti:
            raise CatalogoContrattiNonValido(f"{contratto.id}: clausole senza testo {sorted(mancanti)}")
    return indice


def famiglia(contratto_id: str) -> Contratto:
    try:
        return _indice()[contratto_id]
    except KeyError:
        raise LookupError(f"Contratto non presente nel catalogo: {contratto_id}") from None


@lru_cache(maxsize=1)
def regole_comuni() -> dict:
    return _leggi("_regole_comuni.json")


def carica_catalogo() -> dict:
    """Catalogo per la UI: aree con le voci in forma sintetica."""
    meta = _leggi("_aree.json")
    aree = []
    for chiave, titolo in meta["aree"].items():
        voci = [
            {"id": c.id, "nome": c.nome, "qualificazione": c.qualificazione, "forma": c.forma,
             "riferimenti": list(c.riferimenti), "guidato": bool(c.domande),
             "pubblico_ufficiale": c.forma in ("scrittura_autenticata", "atto_pubblico")}
            for c in _indice().values() if c.area == chiave
        ]
        aree.append({"id": chiave, "titolo": titolo, "voci": voci})
    return {
        "data_ricognizione": meta["data_ricognizione"],
        "stato_verifica": meta["stato_verifica"],
        "fonte_ufficiale_consultazione": meta["fonte_ufficiale_consultazione"],
        "aree": aree,
        "totale": len(_indice()),
    }
