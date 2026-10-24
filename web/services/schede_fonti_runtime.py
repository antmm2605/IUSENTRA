"""Dati della pagina «Norme dei modelli d'atto»: rapporto notturno, proposte aperte, norme di una scheda.

La biblioteca e' quella condivisa dei codici e delle leggi (``codici_leggi.sqlite``); stato del presidio e rapporto
stanno accanto (``schede_fonti.sqlite``, ``schede_fonti_rapporto.json``), scritti dal passaggio notturno
``tools/schede_fonti.py notturno``. Le decisioni dell'avvocato si registrano qui, con il suo nome.
"""
from __future__ import annotations

import json
from pathlib import Path

from lex.normativa.biblioteca.fabbisogno import CARTELLA_SCHEDE
from pct.schede_fonti.proposte import approva_scheda
from pct.schede_fonti.repository import RepositorySchedeFonti
from pct.schede_fonti.verifica import verifica_schede

TIPI = {"norma_cambiata": "Norma cambiata", "norma_abrogata": "Norma abrogata", "norma_assente": "Norma assente",
        "fonte_suggerita": "Fonte da valutare"}


def repository(biblioteca: Path) -> RepositorySchedeFonti:
    return RepositorySchedeFonti(Path(biblioteca).with_name("schede_fonti.sqlite"))


def _titoli() -> dict[str, str]:
    out = {}
    for f in Path(CARTELLA_SCHEDE).glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[str(d.get("id") or f.stem)] = str(d.get("titolo") or "")
    return out


def riepilogo(biblioteca: Path) -> dict:
    percorso = Path(biblioteca).with_name("schede_fonti_rapporto.json")
    rapporto = json.loads(percorso.read_text(encoding="utf-8")) if percorso.is_file() else {}
    proposte = repository(biblioteca).proposte()
    per_tipo: dict[str, int] = {}
    for p in proposte:
        per_tipo[p["tipo"]] = per_tipo.get(p["tipo"], 0) + 1
    verifica = rapporto.get("verifica") or {}
    acquisiti = [e for e in (rapporto.get("acquisizione") or {}).get("esiti", []) if e.get("stato") == "importato"]
    return {"eseguito_il": rapporto.get("eseguito_il", ""), "norme": verifica.get("norme", 0),
            "stati": verifica.get("stati", {}), "commi_abrogati": verifica.get("con_commi_abrogati", 0),
            "acquisiti": [{"chiave": e["chiave"], "articoli": e.get("articoli", 0), "url": e.get("url", "")} for e in acquisiti],
            "proposte_aperte": len(proposte), "per_tipo": [{"tipo": k, "etichetta": TIPI.get(k, k), "numero": v}
                                                          for k, v in sorted(per_tipo.items())]}


def proposte(biblioteca: Path, *, stato: str = "aperta", tipo: str = "", scheda: str = "", limite: int = 200) -> list[dict]:
    titoli = _titoli()
    righe = [p for p in repository(biblioteca).proposte(stato=stato, scheda=scheda) if not tipo or p["tipo"] == tipo]
    return [{"id": p["id"], "tipo": p["tipo"], "etichetta": TIPI.get(p["tipo"], p["tipo"]), "scheda": p["scheda"],
             "titolo_scheda": titoli.get(p["scheda"], ""), "atto": p["atto"], "articolo": p["articolo"],
             "motivo": p["motivo"], "differenze": p["differenze"], "creata_il": p["creata_il"],
             "decisa_da": p["decisa_da"], "decisa_il": p["decisa_il"], "nota": p["nota"]} for p in righe[:limite]]


def decidi(biblioteca: Path, proposta_id: int, esito: str, avvocato: str, nota: str = "") -> None:
    repository(biblioteca).decidi_proposta(proposta_id, esito, avvocato=avvocato, nota=nota)


def scheda(biblioteca: Path, scheda_id: str) -> dict | None:
    if not (Path(CARTELLA_SCHEDE) / f"{scheda_id}.json").is_file():
        return None
    repo = repository(biblioteca)
    stati = {(r["atto"], r["articolo"]): r for r in repo.norme_scheda(scheda_id)}
    from lex.normativa.biblioteca.fabbisogno import norm_articolo

    norme, visti = [], set()
    for e in verifica_schede(Path(biblioteca), solo_scheda=scheda_id):
        k = (e.atto, norm_articolo(e.articolo))
        if k in visti:
            continue
        visti.add(k)
        r = stati.get(k, {})
        norme.append({"atto": e.atto, "articolo": e.articolo, "perche": e.perche, "origine": e.origine, "stato": e.stato,
                      "url": e.url, "aggiornato_al": e.aggiornato_al, "commi_abrogati": e.commi_abrogati,
                      "approvata": bool(r.get("sha256_approvato")) and r.get("sha256_approvato") == e.sha256,
                      "approvata_da": r.get("approvato_da", ""), "approvata_il": r.get("approvato_il", "")})
    return {"id": scheda_id, "titolo": _titoli().get(scheda_id, ""), "norme": norme,
            "proposte": proposte(Path(biblioteca), scheda=scheda_id)}


def approva(biblioteca: Path, scheda_id: str, avvocato: str) -> int:
    return approva_scheda(repository(biblioteca), verifica_schede(Path(biblioteca), solo_scheda=scheda_id), scheda_id, avvocato)
