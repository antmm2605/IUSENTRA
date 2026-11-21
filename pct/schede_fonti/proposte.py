"""Dalle verifiche alle proposte di revisione per l'avvocato. Nessuna scheda viene modificata automaticamente.

Tipi di proposta:
- ``norma_cambiata``: il testo vigente differisce da quello approvato (differenze riga per riga);
- ``norma_abrogata``: l'articolo risulta abrogato per intero (con l'atto abrogante se indicato nel testo);
- ``norma_assente``: atto o articolo non presenti nella biblioteca anche dopo l'acquisizione automatica;
- ``fonte_suggerita``: il registro delle fonti ufficiali per il modello (``template_atti_legal_sources``) indica come
  specifico un articolo dei codici che la scheda non cita.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from lex.normativa.biblioteca.fabbisogno import CARTELLA_SCHEDE, norm_articolo

from .repository import RepositorySchedeFonti
from .verifica import EsitoNorma

SIGLE_CODICI = {"c.p.c.": "codice_procedura_civile", "c.c.": "codice_civile", "c.p.p.": "codice_procedura_penale",
                "c.p.a.": "codice_processo_amministrativo", "c.p.": "codice_penale"}


def differenze(prima: str, dopo: str) -> str:
    def frasi(t: str) -> list[str]:
        return [s.strip() for s in re.split(r"(?<!Art\.)(?<!art\.)(?<=[.;])\s+(?=\d+\.\s|[A-Z(])", t or "") if s.strip()]
    return "\n".join(list(difflib.unified_diff(frasi(prima), frasi(dopo), "testo approvato", "testo vigente", lineterm=""))[:200])


def registra_esiti(repo: RepositorySchedeFonti, esiti: list[EsitoNorma]) -> dict:
    conta = {"verificate": 0, "proposte_nuove": 0, "da_approvare": 0, "approvate_invariate": 0}
    for e in esiti:
        art = norm_articolo(e.articolo)
        precedente = repo.norma(e.scheda, e.atto, art)
        repo.registra_verifica(e.scheda, e.atto, art, stato=e.stato, sha256=e.sha256, url=e.url, aggiornato_al=e.aggiornato_al)
        conta["verificate"] += 1
        nuova = None
        if e.stato == "abrogato":
            motivo = f"Art. {e.articolo} ({e.atto}) risulta abrogato" + (f" dal {e.abrogato_da}" if e.abrogato_da else "") + \
                     f". La scheda {e.scheda} lo cita ({e.origine}: {e.perche}): indicare la norma che lo sostituisce."
            nuova = repo.apri_proposta(e.scheda, e.atto, art, tipo="norma_abrogata", motivo=motivo, sha256=e.sha256)
        elif e.stato in ("atto_assente", "articolo_assente"):
            motivo = (f"{e.atto} art. {e.articolo} non e' nella biblioteca neppure dopo l'acquisizione automatica: "
                      f"verificare il riferimento della scheda {e.scheda} ({e.origine}).")
            nuova = repo.apri_proposta(e.scheda, e.atto, art, tipo="norma_assente", motivo=motivo)
        elif precedente and precedente.get("sha256_approvato"):
            if precedente["sha256_approvato"] != e.sha256:
                motivo = (f"Il testo vigente di art. {e.articolo} ({e.atto}) e' cambiato rispetto a quello approvato il "
                          f"{precedente['approvato_il'][:10]} da {precedente['approvato_da']}: verificare la scheda {e.scheda} "
                          f"({e.origine}: {e.perche}).")
                nuova = repo.apri_proposta(e.scheda, e.atto, art, tipo="norma_cambiata", motivo=motivo,
                                           differenze=differenze(precedente["testo_approvato"], e.testo), sha256=e.sha256)
            else:
                conta["approvate_invariate"] += 1
        else:
            conta["da_approvare"] += 1
        conta["proposte_nuove"] += 1 if nuova else 0
    return conta


def _riferimento_sigla(articolo: str) -> tuple[str, str] | None:
    m = re.match(r"\s*art\.?\s*([\w\-]+)\s+(c\.p\.c\.|c\.c\.|c\.p\.p\.|c\.p\.a\.|c\.p\.)\s*$", str(articolo or ""), re.I)
    if not m:
        return None
    return SIGLE_CODICI[m.group(2).lower()], norm_articolo(m.group(1))


def _suggerimenti(cartella: Path = CARTELLA_SCHEDE) -> dict[tuple[str, str, str], tuple[str, dict]]:
    """Norme specifiche che il registro indica per l'atto di ogni scheda e che la scheda non cita.

    La proposta nasce dall'atto (nome della scheda e codice del modello): le fonti d'articolo assegnate a un intero
    prefisso non bastano, perché ``template_atti_sources_for_model`` richiede il riscontro nel nome dell'atto.
    """
    from pct.template_atti_legal_sources import template_atti_sources_for_model

    out: dict[tuple[str, str, str], tuple[str, dict]] = {}
    for f in sorted(Path(cartella).glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        sid = str(d.get("id") or f.stem)
        citate = {(r["atto"], norm_articolo(r["articolo"])) for r in d.get("base_normativa") or []}
        citate |= {(r["atto"], norm_articolo(r["articolo"])) for c in d.get("campi") or [] for r in c.get("norma") or []}
        for codice in d.get("template") or [sid]:
            for s in template_atti_sources_for_model(model_code=str(codice), model_name=str(d.get("titolo") or "")):
                rif = _riferimento_sigla(s.get("article", ""))
                if not rif or s.get("coverage_role") != "specifica" or s.get("deprecated") or rif in citate:
                    continue
                out.setdefault((sid, *rif), (str(codice), s))
    return out


def fonti_suggerite(repo: RepositorySchedeFonti, cartella: Path = CARTELLA_SCHEDE) -> int:
    nuove = 0
    for (sid, atto, articolo), (codice, s) in _suggerimenti(cartella).items():
        motivo = (f"Il registro delle fonti ufficiali indica per il modello {codice} l'art. {articolo} ({atto}) "
                  f"come fonte specifica («{s.get('title', '')}»), ma la scheda {sid} non lo cita: valutare se aggiungerlo.")
        nuove += 1 if repo.apri_proposta(sid, atto, articolo, tipo="fonte_suggerita", motivo=motivo,
                                         differenze=s.get("official_url", "")) else 0
    return nuove


AUTORE_RITIRO = "IUSENTRA (revisione automatica delle fonti per atto)"


def ritira_suggerimenti_superati(repo: RepositorySchedeFonti, cartella: Path = CARTELLA_SCHEDE, *,
                                 simula: bool = False) -> list[dict]:
    """Ritira le proposte «fonte da valutare» ancora aperte che la logica per atto non produce più.

    Tocca solo proposte ``fonte_suggerita`` aperte e mai decise (nessun nome dell'avvocato): le approvate e le
    respinte restano come sono, e restano intatte le decisioni registrate dagli studi. Ogni ritiro scrive il motivo
    nella nota. Idempotente: una seconda esecuzione non trova più nulla da ritirare.
    """
    attese = _suggerimenti(cartella)
    ritirate = []
    for p in repo.proposte(stato="aperta"):
        if p["tipo"] != "fonte_suggerita" or str(p.get("decisa_da") or "").strip():
            continue
        if (p["scheda"], p["atto"], norm_articolo(p["articolo"])) in attese:
            continue
        motivo = (f"Proposta ritirata: l'art. {p['articolo']} ({p['atto']}) era suggerito alla scheda {p['scheda']} solo "
                  "per il prefisso del codice del modello, non per il nome o il tipo dell'atto; la norma tipica dell'atto "
                  "è già citata dalla scheda o non è pertinente.")
        if not simula:
            repo.ritira_proposta(int(p["id"]), autore=AUTORE_RITIRO, motivo=motivo)
        ritirate.append({"id": p["id"], "scheda": p["scheda"], "atto": p["atto"], "articolo": p["articolo"], "motivo": motivo})
    return ritirate


def approva_scheda(repo: RepositorySchedeFonti, esiti: list[EsitoNorma], scheda: str, avvocato: str) -> int:
    """L'avvocato approva in blocco le norme correnti di una scheda (solo quelle presenti e non abrogate)."""
    fatte: set[tuple[str, str]] = set()
    for e in esiti:
        k = (e.atto, norm_articolo(e.articolo))
        if e.scheda == scheda and e.stato == "presente" and k not in fatte:
            repo.approva_norma(scheda, k[0], k[1], avvocato=avvocato, testo=e.testo, sha256=e.sha256)
            fatte.add(k)
    return len(fatte)
