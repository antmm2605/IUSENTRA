"""Consultazione delle schede di istituto: catalogo per materia, ricerca testuale senza embeddings, riconvalida dal
vivo delle dipendenze, scheda della regola usata da Lex, passaggio della norma citata."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import deposito
from .generatore import pronunce_per_norma, testi_ricerca
from .istituti import carica


@lru_cache(maxsize=2)
def _archivio(percorso: str, mtime: float) -> dict[str, Any]:
    return deposito.leggi_archivio(Path(percorso))


def schede(percorso: Path | None = None, *, anche_ritirate: bool = False) -> list[dict[str, Any]]:
    p = percorso or deposito.ARCHIVIO
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return []
    tutte = list(_archivio(str(p), mtime).get("schede", {}).values())
    return tutte if anche_ritirate else [s for s in tutte if s.get("stato_ciclo") != "ritirata"]


def scheda(ident: str, percorso: Path | None = None) -> dict[str, Any] | None:
    return next((s for s in schede(percorso, anche_ritirate=True) if s["id"] == ident), None)


# --------------------------------------------------------------------------------------------- riconvalida
def versione_attuale(dipendenza: str) -> str | None:
    """Versione di oggi di una fonte: impronta del testo vigente della norma o del testo letto della pronuncia.
    None se la fonte non è più leggibile (da distinguere da «cambiata»)."""
    tipo, _, chiave = dipendenza.partition(":")
    if tipo == "norma":
        from .generatore import fonte_norma

        f = fonte_norma(chiave)
        return f["versione"] if f else None
    if tipo == "pronuncia":
        organo, _, estremi = chiave.partition("|")
        for norma_p in _norme_delle_pronunce().get(chiave, []):
            for p in pronunce_per_norma(norma_p):
                if p["organo"] == organo and f"{p['numero']}/{p['anno']}" == estremi:
                    return p.get("versione", "")
        return None
    return None


@lru_cache(maxsize=1)
def _norme_delle_pronunce() -> dict[str, list[str]]:
    from .generatore import _passaggi

    out: dict[str, list[str]] = {}
    for norma, elenco in (_passaggi().get("norme") or {}).items():
        for p in elenco:
            out.setdefault(f"{p['organo']}|{p['numero']}/{p['anno']}", []).append(norma)
    return out


def stato_attuale(s: dict[str, Any], versioni=versione_attuale) -> dict[str, Any]:
    """Lo stato di oggi: se una fonte da cui dipende la scheda è cambiata o non è più leggibile dopo la generazione,
    la scheda è «da riesaminare» finché non viene rigenerata (scripts/conoscenza_schede_istituto.py genera)."""
    cambiate, sparite = [], []
    for dip, vers in (s.get("dipendenze") or {}).items():
        ora = versioni(dip)
        if ora is None:
            sparite.append(dip)
        elif vers and ora != vers:
            cambiate.append(dip)
    motivi = [f"fonte cambiata dopo la revisione {s.get('revisione')}: {d.split(':', 1)[1]}" for d in cambiate]
    motivi += [f"fonte non più leggibile nell'archivio: {d.split(':', 1)[1]}" for d in sparite]
    stato = "da_riesaminare" if motivi else s.get("stato_verifica", "lacune")
    if s.get("stato_ciclo") == "ritirata":
        stato, motivi = "da_riesaminare", ["istituto non più nel catalogo: scheda conservata come storico"] + motivi
    return {"stato": stato, "motivi": motivi, "fonti_cambiate": cambiate, "fonti_non_leggibili": sparite}


# --------------------------------------------------------------------------------------------- catalogo e ricerca
def catalogo(percorso: Path | None = None) -> dict[str, Any]:
    ordine, _ = carica()
    elenco = schede(percorso)
    per: dict[str, list[dict[str, Any]]] = {}
    for s in elenco:
        per.setdefault(s["materia"], []).append(voce_indice(s))
    materie = [m for m in ordine if m in per] + sorted(m for m in per if m not in ordine)
    return {"materie": [{"materia": m, "schede": sorted(per[m], key=lambda x: x["titolo"].lower()),
                         "conteggi": _conteggi(per[m])} for m in materie],
            "totale": len(elenco), "conteggi": _conteggi([voce_indice(s) for s in elenco]),
            "aggiornato_il": deposito.leggi_archivio(percorso).get("aggiornato_il", "")}


def _conteggi(voci: list[dict[str, Any]]) -> dict[str, int]:
    out = {"verificata": 0, "lacune": 0, "da_riesaminare": 0}
    for v in voci:
        out[v["stato"]] = out.get(v["stato"], 0) + 1
    return out


def voce_indice(s: dict[str, Any]) -> dict[str, Any]:
    return {"id": s["id"], "titolo": s["titolo"], "materia": s["materia"], "sintesi": s.get("sintesi", ""),
            "fonti_dirette": s.get("fonti_dirette", 0), "stato": s.get("stato_verifica", "lacune"),
            "sezioni_compilate": s.get("sezioni_compilate", 0), "sezioni_mancanti": s.get("sezioni_mancanti", []),
            "revisione": s.get("revisione", 0), "ultimo_controllo": s.get("ultimo_controllo", "")}


def _norm(testo: str) -> str:
    from lex.harness.norme import piano

    return piano(testo)


_VUOTE = frozenset("a ad al alla alle agli ai il lo la le gli i un una uno di da del della dei delle degli in con su per "
                   "tra fra e o che come cosa quale quali quando si non ne nel nella nei nelle sul sulla".split())


def cerca(q: str, *, materia: str = "", limite: int = 30, percorso: Path | None = None) -> list[dict[str, Any]]:
    """Ricerca testuale nelle schede (titolo, sintesi, voci, citazioni delle fonti): funziona senza embeddings.
    Ogni parola della domanda deve comparire (anche come inizio di parola: «licenzia» trova «licenziamento»); a parità
    contano il titolo e le fonti. Nessun limite che nasconda le schede meno recenti: si ordina per pertinenza."""
    parole = [p for p in _norm(q).split() if p not in _VUOTE and len(p) > 1]
    if not parole:
        return []
    risultati = []
    for s in schede(percorso):
        if materia and s["materia"] != materia:
            continue
        titolo = _norm(s["titolo"] + " " + s["istituto"].replace("_", " "))
        corpo = _norm(testi_ricerca(s))
        parole_corpo = set(corpo.split())
        punteggio = 0
        for p in parole:
            radice = p[:6] if len(p) > 7 else p
            in_titolo = any(w.startswith(radice) for w in titolo.split())
            in_corpo = p in parole_corpo or any(w.startswith(radice) for w in parole_corpo)
            if not (in_titolo or in_corpo):
                break
            punteggio += 3 if in_titolo else 1
        else:
            frammento = _frammento(s, parole)
            risultati.append({**voce_indice(s), "punteggio": punteggio, "frammento": frammento})
    risultati.sort(key=lambda r: (-r["punteggio"], r["titolo"].lower()))
    return risultati[:limite]


def _frammento(s: dict[str, Any], parole: list[str]) -> str:
    for sez in s["sezioni"].values():
        for v in sez["voci"]:
            t = _norm(v["testo"])
            if any(p in t for p in parole):
                return v["testo"][:220]
    return s.get("sintesi", "")[:220]


# --------------------------------------------------------------------------------------------- Lex e fonti
def scheda_per_regola(regola: str, percorso: Path | None = None) -> dict[str, Any] | None:
    """La scheda dell'istituto trattato da una regola di Lex (prima quella con lo stesso nome)."""
    candidate = [s for s in schede(percorso) if regola in (s.get("regole") or [])]
    if not candidate:
        return None
    return next((s for s in candidate if s["istituto"] == regola), candidate[0])


def passaggio_norma(chiave: str, ancora: str = "") -> dict[str, Any] | None:
    """Il testo vigente della norma e la posizione dell'ancora (spazi e accenti tollerati)."""
    from lex.harness.norme import NORME, testo_norma

    t = testo_norma(chiave)
    if chiave not in NORME or t is None:
        return None
    testo = " ".join(t.testo.split())
    inizio = fine = -1
    if ancora:
        parole = [re.escape(p) for p in ancora.split()]
        m = re.search(r"\W*".join(parole), testo, re.I) if parole else None
        if m is None:
            # Normattiva scrive gli accenti con l'apostrofo («e'»): si confronta senza accenti né apostrofi.
            m = re.search(r"[\W']*".join(re.escape(_norm(p)) for p in ancora.split()), _norm(testo)) if parole else None
            if m is not None:
                inizio, fine = _posizione_originale(testo, m.start(), m.end())
        else:
            inizio, fine = m.start(), m.end()
    return {"chiave": chiave, "citazione": NORME[chiave].citazione, "rubrica": NORME[chiave].rubrica, "testo": testo,
            "inizio": inizio, "fine": fine, "url": t.url, "aggiornamento": t.aggiornamento, "vigente": t.vigente,
            "origine": t.origine}


def _posizione_originale(testo: str, a: int, b: int) -> tuple[int, int]:
    """Riporta un intervallo del testo normalizzato sul testo originale contando i caratteri alfanumerici."""
    norm = _norm(testo)
    conta_a = sum(1 for c in norm[:a] if c.isalnum())
    conta_b = sum(1 for c in norm[:b] if c.isalnum())
    pos_a = pos_b = -1
    n = 0
    for i, c in enumerate(testo):
        if _norm(c).isalnum():
            if n == conta_a and pos_a < 0:
                pos_a = i
            n += 1
            if n == conta_b:
                pos_b = i + 1
                break
    return pos_a, pos_b
