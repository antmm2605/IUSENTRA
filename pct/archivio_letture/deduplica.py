"""Fusione dei fatti equivalenti letti da documenti e PEC.

I motori conservano i fatti grezzi per audit: documento e PEC restano due
fonti distinte. I presidi, invece, devono vedere un fatto solo quando
raccontano la stessa informazione, con tutte le fonti raccolte nelle prove.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Iterable

from pct.registro_letture.fatti_repository import Fatto
from .identita_eventi import ambito_fatto

_ORDINE_VERIFICA = {"corretta": 0, "verificata": 1, "plausibile": 2, "respinta": 3, "ignorata": 4}
_ORDINE_TIPO = {"documento": 0, "allegato_pec": 1, "pec": 2}
_ORDINE_MOTORE = {"documenti": 0, "pec": 1}


def _testo(valore: object) -> str:
    return " ".join(str(valore or "").split()).strip()


def _giorno_ora(fatto: Fatto) -> tuple[str, str]:
    valore = _testo(fatto.valore)
    giorno = valore[:10] if len(valore) >= 10 else valore
    ora = valore[11:16] if len(valore) >= 16 and valore[10] == "T" else ""
    return giorno, ora


def _compatibile(gruppo: list[Fatto], fatto: Fatto) -> bool:
    primo = gruppo[0]
    if _testo(primo.fascicolo_id) != _testo(fatto.fascicolo_id):
        return False
    if (primo.verifica in {"respinta", "ignorata"}) != (fatto.verifica in {"respinta", "ignorata"}):
        return False
    if primo.categoria != fatto.categoria or primo.campo != fatto.campo:
        return False
    if ambito_fatto(primo) != ambito_fatto(fatto):
        return False
    if ambito_fatto(fatto).startswith("fonte:") and not (fatto.id and primo.id == fatto.id):
        return False
    if fatto.campo == "natura_documentale" and primo.oggetto_id != fatto.oggetto_id:
        return False
    if fatto.categoria == "data":
        giorno, ora = _giorno_ora(fatto)
        giorno_gruppo, _ = _giorno_ora(primo)
        if not giorno or giorno != giorno_gruppo:
            return False
        ore = {_giorno_ora(voce)[1] for voce in gruppo if _giorno_ora(voce)[1]}
        return not ora or not ore or ora in ore
    return _testo(primo.valore).casefold() == _testo(fatto.valore).casefold()


def _identita(gruppo: list[Fatto]) -> tuple[str, ...]:
    primo = gruppo[0]
    if primo.categoria == "data":
        giorno, _ = _giorno_ora(primo)
        ore = sorted({_giorno_ora(voce)[1] for voce in gruppo if _giorno_ora(voce)[1]})
        identity = (_testo(primo.fascicolo_id), primo.categoria, primo.campo, giorno, ore[0] if ore else "")
        return (*identity, ambito_fatto(primo)) if ambito_fatto(primo) else identity
    oggetto = _testo(primo.oggetto_id) if primo.campo == "natura_documentale" else ""
    return (_testo(primo.fascicolo_id), primo.categoria, primo.campo, _testo(primo.valore).casefold(), oggetto)


def _migliore(gruppo: list[Fatto]) -> Fatto:
    return sorted(
        gruppo,
        key=lambda fatto: (
            _ORDINE_VERIFICA.get(fatto.verifica, 9),
            -len(_giorno_ora(fatto)[1]),
            _ORDINE_TIPO.get(fatto.tipo, 9),
            _ORDINE_MOTORE.get(fatto.motore, 9),
            -len(_testo(fatto.contesto)),
            _testo(fatto.id),
        ),
    )[0]


def _fonti(gruppo: list[Fatto]) -> list[str]:
    viste: set[str] = set()
    esito: list[str] = []
    for fatto in gruppo:
        fonte = f"{_testo(fatto.tipo) or 'fonte'}:{_testo(fatto.oggetto_id) or 'senza-id'}"
        dettaglio = f"{fonte} ({_testo(fatto.motore) or _testo(fatto.origine) or 'motore non indicato'})"
        if dettaglio not in viste:
            viste.add(dettaglio)
            esito.append(dettaglio)
    return esito


def _unisci(gruppo: list[Fatto]) -> Fatto:
    if len(gruppo) == 1:
        return gruppo[0]
    base = _migliore(gruppo)
    identita = _identita(gruppo)
    identita = (*identita, "esclusa" if base.verifica in {"respinta", "ignorata"} else "utile")
    identificativo = "canon-" + hashlib.sha256("|".join(identita).encode("utf-8")).hexdigest()[:24]
    fonti = _fonti(gruppo)
    prove: list[dict[str, object]] = []
    viste: set[str] = set()
    for fatto in gruppo:
        for prova in fatto.prove:
            chiave = repr(sorted(dict(prova).items()))
            if chiave in viste:
                continue
            viste.add(chiave)
            prove.append(dict(prova))
    from .adempimenti import perentorieta_documentata
    for fatto in gruppo:
        if perentorieta_documentata(fatto):
            prove.append({"codice": "perentorieta_documentata", "esito": "ok", "dettaglio": fatto.contesto, "fatto_id": fatto.id, "sha256": fatto.sha256})
    prove.append({"codice": "fonti_unite", "esito": "ok", "dettaglio": "; ".join(fonti),
                  "fonti": [{"fatto_id": f.id, "tipo": f.tipo, "oggetto_id": f.oggetto_id,
                             "sha256": f.sha256, "valore": f.valore, "verifica": f.verifica,
                             "motore": f.motore, "estratto": f.contesto, "posizione": f.posizione}
                            for f in sorted(gruppo, key=lambda f: (f.tipo, f.oggetto_id, f.id))]})
    motori = "+".join(voce for voce in ("documenti", "pec") if any(fatto.motore == voce for fatto in gruppo))
    origini = "+".join(sorted({_testo(fatto.origine) for fatto in gruppo if _testo(fatto.origine)}))[:40]
    contesti: list[str] = []
    for fatto in gruppo:
        contesto = _testo(fatto.contesto)
        if contesto and contesto not in contesti:
            contesti.append(contesto)
    return replace(
        base,
        id=identificativo,
        motore=motori or base.motore,
        origine=origini or base.origine,
        contesto=" | ".join(contesti)[:300] or base.contesto,
        prove=prove,
    )


def _secchio(fatto: Fatto) -> tuple[str, ...]:
    """Partizione economica che conserva esattamente le regole di compatibilità.

    I fatti di secchi diversi non possono mai essere uniti da ``_compatibile``;
    dentro il singolo secchio resta il confronto ordinato, necessario soltanto
    per distinguere orari incompatibili dello stesso giorno.
    """
    esclusa = "esclusa" if fatto.verifica in {"respinta", "ignorata"} else "utile"
    oggetto = _testo(fatto.oggetto_id) if fatto.campo == "natura_documentale" else ""
    valore = _giorno_ora(fatto)[0] if fatto.categoria == "data" else _testo(fatto.valore).casefold()
    return (_testo(fatto.fascicolo_id), esclusa, fatto.categoria, fatto.campo, oggetto, valore, ambito_fatto(fatto))


def fatti_canonici(fatti: Iterable[Fatto]) -> list[Fatto]:
    """Restituisce fatti senza duplicati semantici, preservando tutte le fonti.

    L'ordine dei gruppi e la scelta della fonte migliore restano quelli storici;
    l'indice evita soltanto di confrontare ogni fatto con gruppi certamente
    incompatibili appartenenti ad altri fascicoli, campi, giorni o valori.
    """
    elenco = list(fatti)
    ore_per_secchio: dict[tuple[str, ...], set[str]] = {}
    for fatto in elenco:
        if fatto.categoria == "data" and _giorno_ora(fatto)[1]:
            ore_per_secchio.setdefault(_secchio(fatto), set()).add(_giorno_ora(fatto)[1])
    gruppi: list[list[Fatto]] = []
    per_secchio: dict[tuple[str, ...], list[int]] = {}
    for fatto in elenco:
        secchio = _secchio(fatto)
        # Una fonte senza ora non sceglie arbitrariamente fra orari discordanti.
        if fatto.categoria == "data" and not _giorno_ora(fatto)[1] and len(ore_per_secchio.get(secchio, set())) > 1:
            secchio = (*secchio, "ora_da_verificare")
        candidati = per_secchio.setdefault(secchio, [])
        for indice in candidati:
            if _compatibile(gruppi[indice], fatto):
                gruppi[indice].append(fatto)
                break
        else:
            candidati.append(len(gruppi))
            gruppi.append([fatto])
    return [_unisci(gruppo) for gruppo in gruppi]


__all__ = ["fatti_canonici"]
