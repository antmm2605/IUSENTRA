"""Osservazioni pubbliche in sola lettura; decisioni nel SQL dello studio autenticato."""
from __future__ import annotations

import json
import difflib
import re
import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from lex.normativa.biblioteca.fabbisogno import CARTELLA_SCHEDE, norm_articolo
from pct.schede_fonti.decisioni import DecisioniStudio, chiave, impronta
from pct.schede_fonti.verifica import verifica_schede

TIPI = {"norma_cambiata": "Norma cambiata", "norma_abrogata": "Norma abrogata",
        "norma_assente": "Norma assente", "fonte_suggerita": "Fonte da valutare"}


class RevisioneCambiata(ValueError):
    pass


@lru_cache(maxsize=1)
def _modelli():
    return sorted([{"id": str(d.get("id") or p.stem), "titolo": str(d.get("titolo") or "")}
                   for p in Path(CARTELLA_SCHEDE).glob("*.json")
                   for d in [json.loads(p.read_text(encoding="utf-8"))]], key=lambda x: x["titolo"])


def _pubblico(biblioteca, tabella):
    assert tabella in {"norme", "proposte"}
    p = Path(biblioteca).with_name("schede_fonti.sqlite")
    if not p.is_file():
        return []
    with closing(sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True)) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute("SELECT * FROM " + tabella)]


def _norme_scheda(biblioteca, sid):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", sid) or not (Path(CARTELLA_SCHEDE) / (sid + ".json")).is_file():
        return None
    out, viste = [], set()
    for e in verifica_schede(Path(biblioteca), solo_scheda=sid):
        k = (e.atto, norm_articolo(e.articolo))
        if k in viste:
            continue
        viste.add(k)
        out.append({"atto": e.atto, "articolo": e.articolo, "perche": e.perche, "origine": e.origine,
                    "stato": e.stato, "url": e.url, "aggiornato_al": e.aggiornato_al,
                    "commi_abrogati": e.commi_abrogati, "testo": e.testo, "sha256": e.sha256})
    return out


def _rif(sid, n):
    return sid + ":" + n["atto"] + ":" + norm_articolo(n["articolo"])


def _digest_norma(n):
    return impronta({k: n[k] for k in ("atto", "articolo", "stato", "url", "aggiornato_al", "sha256", "testo")})


def scheda(biblioteca, scheda_id, *, studio_db):
    norme = _norme_scheda(biblioteca, scheda_id)
    if norme is None:
        return None
    digest = impronta(norme)
    approvazioni = DecisioniStudio(studio_db).leggi("norma")
    for n in norme:
        e = approvazioni.get(chiave("norma", _rif(scheda_id, n), _digest_norma(n)), {})
        precedenti = sorted((v for v in approvazioni.values() if v["riferimento"] == _rif(scheda_id, n)),
                            key=lambda v: v["creato_il"], reverse=True)
        differenze = ""
        if not e and precedenti:
            prima = precedenti[0]["norma"]
            differenze = "\n".join(difflib.unified_diff(prima["testo"].splitlines(), n["testo"].splitlines(),
                                                       "testo approvato", "testo corrente", lineterm=""))
            if not differenze:
                differenze = "Testo identico; provenienza o versione della fonte cambiate. Occorre riesaminare la fonte."
        n.update(approvata=bool(e), approvata_da=e.get("attore", ""), approvata_il=e.get("creato_il", ""), differenze=differenze)
    return {"id": scheda_id, "titolo": next((m["titolo"] for m in _modelli() if m["id"] == scheda_id), ""),
            "norme": norme, "impronta": digest}


def approva(biblioteca, scheda_id, avvocato, digest, *, studio_db):
    norme = _norme_scheda(biblioteca, scheda_id)
    if norme is None:
        raise KeyError("Modello d'atto non trovato.")
    if not digest or impronta(norme) != digest:
        raise RevisioneCambiata("Le norme sono cambiate o non sono state esaminate: riapri il modello prima di approvare.")
    eventi = [(_rif(scheda_id, n), _digest_norma(n), {"scheda": scheda_id, "norma": n})
              for n in norme if n["stato"] == "presente"]
    if not eventi:
        raise ValueError("Nessun testo presente in biblioteca da approvare.")
    DecisioniStudio(studio_db).registra("norma", eventi, avvocato)
    return len(eventi)


def _elenco(biblioteca, studio_db):
    titoli = {m["id"]: m["titolo"] for m in _modelli()}
    correnti = {(n["scheda"], n["atto"], norm_articolo(n["articolo"])): n for n in _pubblico(biblioteca, "norme")}
    out = []
    for p in _pubblico(biblioteca, "proposte"):
        current = correnti.get((p["scheda"], p["atto"], norm_articolo(p["articolo"])), {})
        if p["tipo"] == "norma_assente" and current.get("stato") not in {"atto_assente", "articolo_assente"}:
            continue
        if p["tipo"] == "norma_abrogata" and current.get("stato") != "abrogato":
            continue
        if p["tipo"] == "norma_cambiata":
            continue  # Il confronto con un'approvazione privata si fa solo per il proprio studio.
        # Non esporre nomi, note o approvazioni dello stato CLI condiviso.
        x = {"id": str(p["id"]), "tipo": p["tipo"], "scheda": p["scheda"], "atto": p["atto"],
             "articolo": p["articolo"], "differenze": p["differenze"], "creata_il": p["creata_il"],
             "motivo": f"{TIPI.get(p['tipo'], p['tipo'])}: art. {p['articolo']} ({p['atto']}). Verificare il riferimento del modello."}
        x["impronta"] = impronta([x, current.get("sha256", ""), current.get("url", ""), current.get("aggiornato_al", "")])
        out.append(x)
    # Il controllo notturno alimenta le impronte pubbliche; qui si confrontano
    # soltanto le approvazioni del proprio studio con quella proiezione SQL.
    viste = set()
    approvazioni = list(DecisioniStudio(studio_db).leggi("norma").values())
    attuali = {(e["scheda"], e["norma"]["atto"], norm_articolo(e["norma"]["articolo"]),
                e["norma"]["sha256"], e["norma"]["url"], e["norma"]["aggiornato_al"]) for e in approvazioni}
    for e in approvazioni:
        sid, n = e["scheda"], e["norma"]
        k = (sid, n["atto"], norm_articolo(n["articolo"]))
        current = correnti.get(k)
        if not current or current["stato"] != "presente":
            continue
        if current["verificato_il"][:19] < e["creato_il"][:19]:
            continue  # Osservazione pubblica precedente all'approvazione esaminata.
        if (*k, current["sha256"], current["url"], current["aggiornato_al"]) in attuali:
            continue
        if (current["sha256"], current["url"], current["aggiornato_al"]) == (n["sha256"], n["url"], n["aggiornato_al"]):
            continue
        digest = impronta([k, current["sha256"], current["url"], current["aggiornato_al"]])
        if digest in viste:
            continue
        viste.add(digest)
        out.append({"id": "norma-" + digest, "tipo": "norma_cambiata", "scheda": sid, "atto": n["atto"],
                    "articolo": n["articolo"], "differenze": "", "creata_il": current["verificato_il"], "impronta": digest,
                    "motivo": "Il testo o la provenienza sono cambiati rispetto all'approvazione dello studio. Aprire il modello per esaminare il nuovo testo."})
    decisioni = DecisioniStudio(studio_db).leggi("proposta")
    for p in out:
        e = decisioni.get(chiave("proposta", p["id"], p["impronta"]), {})
        p.update(etichetta=TIPI.get(p["tipo"], p["tipo"]), titolo_scheda=titoli.get(p["scheda"], ""),
                 stato=e.get("esito", "aperta"), decisa_da=e.get("attore", ""), decisa_il=e.get("creato_il", ""), nota=e.get("nota", ""))
    return out


def proposte(biblioteca, *, studio_db, stato="aperta", tipo="", scheda="", limite=None, righe=None):
    return [p for p in (righe if righe is not None else _elenco(biblioteca, studio_db)) if p["stato"] == stato
            and (not tipo or p["tipo"] == tipo) and (not scheda or p["scheda"] == scheda)][:limite]


def riepilogo(biblioteca, *, studio_db, righe=None):
    path = Path(biblioteca).with_name("schede_fonti_rapporto.json")
    rapporto = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    aperte = [p for p in (righe if righe is not None else _elenco(biblioteca, studio_db)) if p["stato"] == "aperta"]
    counts = {}
    for p in aperte:
        counts[p["tipo"]] = counts.get(p["tipo"], 0) + 1
    v = rapporto.get("verifica") or {}
    acquisiti = [e for e in (rapporto.get("acquisizione") or {}).get("esiti", []) if e.get("stato") == "importato"]
    return {"eseguito_il": rapporto.get("eseguito_il", ""), "norme": v.get("norme", 0), "stati": v.get("stati", {}),
            "commi_abrogati": v.get("con_commi_abrogati", 0), "acquisiti": acquisiti, "proposte_aperte": len(aperte),
            "per_tipo": [{"tipo": k, "etichetta": TIPI.get(k, k), "numero": n} for k, n in ((k, counts.get(k, 0)) for k in TIPI)]}


def decidi(biblioteca, proposta_id, esito, avvocato, nota="", digest="", *, studio_db):
    if esito not in {"approvata", "respinta"}:
        raise ValueError("Scegli approvata o respinta.")
    p = next((p for p in _elenco(biblioteca, studio_db) if p["id"] == str(proposta_id)), None)
    if p is None:
        raise KeyError("Proposta non trovata.")
    if not digest or p["impronta"] != digest:
        raise RevisioneCambiata("La proposta è cambiata: ricarica l'elenco.")
    if p["stato"] != "aperta":
        if p["stato"] == esito and p["nota"] == nota:
            return False
        raise RevisioneCambiata("La proposta è già stata decisa: ricarica l'elenco.")
    DecisioniStudio(studio_db).registra("proposta", [(p["id"], digest, {"esito": esito, "nota": nota})], avvocato)
    return True
