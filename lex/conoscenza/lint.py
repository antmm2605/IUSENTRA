"""Controllo della wiki delle schede di istituto (lint): controlli deterministici, nessuna valutazione semantica.

Categorie:
- «senza_fonti»: scheda senza alcuna norma con testo vigente fra le fonti;
- «norma_abrogata»: norma abrogata usata come norma di riferimento o in una voce che non dichiara l'abrogazione;
- «collegamento_rotto»: regola di Lex, modello d'atto, procedura guidata, norma o pronuncia a cui la scheda rimanda
  e che il software non ha più, oppure pagina della vista Markdown mancante;
- «riesame_scaduto»: scheda «da riesaminare» da più di 30 giorni.

Ogni segnalazione ha un ID stabile (categoria, scheda, oggetto): la stessa segnalazione ripetuta nelle notti successive
resta la stessa finché il problema persiste. Il rapporto entra nel registro della conoscenza come evento «lint».
Non si corregge e non si cancella nulla: le segnalazioni propongono l'azione.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import deposito

GIORNI_RIESAME = 30
GRAVITA = {"senza_fonti": "alta", "norma_abrogata": "alta", "collegamento_rotto": "media", "riesame_scaduto": "media"}


def _segnalazione(categoria: str, scheda: str, oggetto: str, descrizione: str, azione: str,
                  evidenze: list[str] | None = None) -> dict[str, Any]:
    ident = hashlib.sha256(f"{categoria}|{scheda}|{oggetto}".encode()).hexdigest()[:16]
    return {"id": ident, "categoria": categoria, "gravita": GRAVITA[categoria], "scheda": scheda, "oggetto": oggetto,
            "descrizione": descrizione, "evidenze": evidenze or [], "azione_proposta": azione, "stato": "aperta"}


def _esistenti() -> dict[str, set[str]]:
    from lex.harness.fattispecie import REGOLE
    from lex.harness.norme import NORME

    from .generatore import RADICE, _passaggi

    procedure: set[str] = set()
    try:
        from lex.legal_skills.prompt_library.pathways import get_pathway_catalog

        procedure = {p.percorso_id for p in get_pathway_catalog().percorsi()}
    except Exception:  # noqa: BLE001 - catalogo non caricabile: le procedure risultano rotte e lo si segnala
        procedure = set()
    pronunce = {f"{p['organo']}|{p['numero']}/{p['anno']}" for v in (_passaggi().get("norme") or {}).values() for p in v}
    modelli = {p.stem for p in (RADICE / "pct" / "template_atti_schede").glob("*.json")}
    return {"regola_lex": {r[0] for r in REGOLE}, "modello_atto": modelli, "procedura_guidata": procedure,
            "norma": set(NORME), "pronuncia": pronunce}


def controlla(*, archivio: Path | None = None, viste: Path | None = None, adesso: datetime | None = None,
              esistenti: dict[str, set[str]] | None = None, versioni=None) -> dict[str, Any]:
    from .consultazione import stato_attuale, versione_attuale

    adesso = adesso or datetime.now(deposito.ROMA)
    esistenti = esistenti or _esistenti()
    schede = list(deposito.leggi_archivio(archivio)["schede"].values())
    segnalazioni: list[dict[str, Any]] = []
    for s in schede:
        if s.get("stato_ciclo") == "ritirata":
            continue
        sid = s["id"]
        norme = [f for f in s.get("fonti", []) if f.get("tipo") == "norma"]
        if not norme:
            segnalazioni.append(_segnalazione("senza_fonti", sid, "fonti", "La scheda non ha alcuna norma con testo vigente.",
                                              "aggiungere le norme dell'istituto al catalogo o al registro delle norme di Lex"))
        for f in norme:
            if f.get("stato") == "abrogata":
                usata = [v["testo"][:120] for sez in s["sezioni"].values() for v in sez["voci"]
                         if any(g.get("chiave") == f["chiave"] for g in v["fonti"]) and "abrog" not in v["testo"].lower()]
                if f.get("stato_biblioteca") is not None or usata:
                    segnalazioni.append(_segnalazione(
                        "norma_abrogata", sid, f["chiave"], f"{f['citazione']} è abrogato ({f.get('nota_abrogazione', '')}) "
                        "ma è usato come norma della scheda.", "sostituire con la sede vigente o spostarlo fra le norme "
                        "abrogate (storico)", usata))
        for x in s.get("strumenti", []):
            if x["tipo"] in esistenti and x["id"] not in esistenti[x["tipo"]]:
                segnalazioni.append(_segnalazione("collegamento_rotto", sid, f"{x['tipo']}:{x['id']}",
                                                  f"{x['titolo']}: non esiste più nel software.", "aggiornare il collegamento"))
        for f in s.get("fonti", []):
            insieme = esistenti.get(f.get("tipo", ""))
            if insieme is not None and f["chiave"] not in insieme:
                segnalazioni.append(_segnalazione("collegamento_rotto", sid, f"{f['tipo']}:{f['chiave']}",
                                                  f"{f['citazione']}: fonte non più presente negli archivi del software.",
                                                  "rigenerare la scheda o ripristinare la fonte"))
        if viste is not None and not (viste / deposito.slug(s["materia"]) / f"{sid}.md").is_file():
            segnalazioni.append(_segnalazione("collegamento_rotto", sid, "pagina", "La pagina della vista Markdown manca.",
                                              "rigenerare le viste (scripts/conoscenza_schede_istituto.py viste)"))
        st = stato_attuale(s, versioni=versioni or versione_attuale)
        if st["stato"] == "da_riesaminare":
            dal = s.get("da_riesaminare_dal") or s.get("ultimo_controllo") or ""
            try:
                giorni = (adesso - datetime.fromisoformat(dal)).days
            except (TypeError, ValueError):
                giorni = 0
            if giorni > GIORNI_RIESAME:
                segnalazioni.append(_segnalazione("riesame_scaduto", sid, "stato",
                                                  f"Da riesaminare da {giorni} giorni.", "rigenerare la scheda o chiudere il "
                                                  "motivo del riesame", st["motivi"]))
    conteggi = {c: sum(1 for x in segnalazioni if x["categoria"] == c) for c in GRAVITA}
    return {"eseguito_il": adesso.isoformat(timespec="seconds"), "schede": len(schede), "conteggi": conteggi,
            "segnalazioni": segnalazioni}


def registra(rapporto: dict[str, Any], *, registro: Path | None = None, ora: str | None = None) -> None:
    """Il rapporto del controllo come evento «lint» del registro della conoscenza (append-only)."""
    import json

    ora = ora or deposito.adesso()
    evento = deposito._evento("lint", None, ora, schede=rapporto["schede"], **rapporto["conteggi"],
                              segnalazioni=[{k: x[k] for k in ("id", "categoria", "gravita", "scheda", "oggetto", "descrizione",
                                                               "azione_proposta", "stato")} for x in rapporto["segnalazioni"]][:200])
    evento["titolo"] = "controllo della wiki"
    p = registro or deposito.REGISTRO
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False, sort_keys=True) + "\n")
