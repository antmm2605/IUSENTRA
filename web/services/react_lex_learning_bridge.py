"""Bridge React per la superficie "Apprendimento Lex" (read-only).

Costruisce il payload di `/api/v1/ui/lex-learning`: fotografia della memoria
durevole del ciclo autonomo (`lex.autonomy.memory_inspection`, mai side-effect)
più lo stato del job notturno delegato dal registro pianificazioni. La
superficie NON offre azioni dispositive: l'attivazione del job resta nella
console Pianificazioni (`/admin/pianificazioni`) e le proposte si applicano
solo con revisione umana fuori da questa pagina.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

CONSOLE_PIANIFICAZIONI_PATH = "/admin/pianificazioni"


def _stato_job_notturno(config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Stato del job `lex_autonomous_learning_nightly`, fail-closed sulle letture."""

    stato: dict[str, Any] = {
        "job_id": "",
        "abilitato": False,
        "stato": "sconosciuto",
        "pianificazione": "",
        "console": CONSOLE_PIANIFICAZIONI_PATH,
        # La console Pianificazioni è della piattaforma (solo superamministratore): all'amministratore dello studio
        # si mostra qui l'ultimo giro, senza un collegamento che risponderebbe 403.
        "console_visibile": _superamministratore(),
        "ultimo_giro": {},
    }
    try:
        from lex.autonomy.nightly import JOB_ID

        stato["job_id"] = JOB_ID
        from pct.scheduler_registry import scheduler_registry_repository

        row = scheduler_registry_repository(dict(config or {})).get_job(JOB_ID)
    except Exception:
        stato["stato"] = "registro pianificazioni non leggibile"
        return stato
    if not row:
        stato["stato"] = "mai abilitato dalla console"
        return stato
    stato["ultimo_giro"] = _ultimo_giro(config, JOB_ID)
    stato["abilitato"] = bool(row.get("enabled"))
    stato["stato"] = "attivo" if stato["abilitato"] else "in pausa (disattivato dalla console)"
    hour = str(row.get("hour") or "").strip()
    minute = str(row.get("minute") or "").strip()
    if hour:
        stato["pianificazione"] = f"ogni notte alle {int(hour):02d}:{int(minute or 0):02d}" if hour.isdigit() else ""
    return stato


def _superamministratore() -> bool:
    try:
        from flask import g

        return bool(getattr(getattr(g, "utente_corrente", None), "is_superadmin", False))
    except Exception:
        return False


def _ultimo_giro(config: Mapping[str, Any] | None, job_id: str) -> dict[str, Any]:
    """Ultima esecuzione del lavoro: data, esito e messaggio in italiano."""
    try:
        from pct.scheduler_registry import scheduler_registry_repository

        giro = scheduler_registry_repository(dict(config or {})).latest_runs_by_job().get(job_id) or {}
    except Exception:
        return {}
    if not giro:
        return {}
    esiti = {"completed": "Completato", "failed": "Non riuscito", "cancelled": "Annullato", "running": "In corso",
             "requested": "Richiesto", "dispatched": "Avviato"}
    stato = str(giro.get("status") or "")
    return {"data": str(giro.get("finished_at") or giro.get("started_at") or ""), "esito": esiti.get(stato, stato),
            "riuscito": stato == "completed",
            "messaggio": str(giro.get("error") or giro.get("message") or "").strip()}


_TIPI_PROPOSTA = {
    "ontologia": "Vocabolario giuridico",
    "pattern_citazione": "Riconoscimento delle citazioni",
    "estrattore_citazioni": "Riconoscimento delle citazioni",
    "source_policy": "Fonti ammesse",
    "connettore_dedicato": "Nuovo canale ufficiale",
    "area_keywords": "Materie",
}
_FONTI = {
    "archivio_locale:gazzetta_ufficiale": "Archivio della Gazzetta Ufficiale",
    "archivio_locale:normattiva": "Archivio Normattiva",
    "corpus_locale:giurisprudenza": "Archivio della giurisprudenza",
}


def _tra_apici(testo: str) -> str:
    m = re.search(r"'([^']{2,120})'", testo)
    return m.group(1) if m else ""


def proposta_per_lo_studio(row: Mapping[str, Any]) -> dict[str, Any]:
    """La proposta detta all'avvocato, senza nomi di file, costanti o sigle interne."""
    tipo = str(row.get("tipo") or "")
    titolo, descrizione = str(row.get("titolo") or ""), str(row.get("descrizione") or "")
    oggetto = _tra_apici(titolo) or _tra_apici(descrizione)
    volte = re.search(r"ricorre (\d+) volte", descrizione)
    area = re.search(r"\(area ([^)]+)\)", descrizione)
    if tipo == "ontologia" and oggetto:
        titolo = f"Aggiungere «{oggetto}» al vocabolario giuridico di Lex"
        descrizione = (f"Il termine «{oggetto}» compare" + (f" {volte.group(1)} volte" if volte else "")
                       + " nei testi letti" + (f" (materia: {area.group(1)})" if area else "")
                       + ", ma Lex non lo conosce ancora: va valutato con i sinonimi e le fonti primarie verificate.")
    elif tipo in {"pattern_citazione", "estrattore_citazioni"} and oggetto:
        titolo = f"Riconoscere il riferimento «{oggetto}»"
        descrizione = f"Il riferimento «{oggetto}» compare nelle fonti lette ma Lex non lo riconosce ancora come citazione."
    elif tipo == "connettore_dedicato":
        sito = re.search(r"per ([\w.-]+\.[a-z]{2,})", titolo)
        titolo = f"Leggere {sito.group(1)} dal suo canale ufficiale" if sito else "Leggere un sito dal suo canale ufficiale"
        descrizione = "Il sito non consente la lettura automatica delle pagine: serve il suo canale ufficiale di dati."
    elif tipo == "source_policy" and oggetto:
        titolo = f"Ammettere {oggetto} tra le fonti"
        descrizione = f"Il sito {oggetto} è ufficiale ma non è ancora tra le fonti ammesse per questa materia."
    elif tipo == "area_keywords":
        titolo = "Riconoscere la materia di alcune domande"
        descrizione = "Alcune domande di ricerca non hanno una materia riconosciuta: servono parole chiave per riconoscerla."
    return {**row, "titolo": titolo, "descrizione": descrizione, "tipo": _TIPI_PROPOSTA.get(tipo, "Proposta"),
            "modulo": ""}


def lettura_per_lo_studio(row: Mapping[str, Any]) -> dict[str, Any]:
    fonte = str(row.get("fonte") or "")
    return {**row, "fonte": _FONTI.get(fonte, "Sito ufficiale" if fonte else "")}


def build_react_lex_learning_payload(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    from lex.autonomy.memory_inspection import inspect_memory

    try:
        snapshot = inspect_memory()
    except Exception:
        snapshot = {
            "directory": "",
            "memoria_presente": False,
            "conteggi": {},
            "proposte": [],
            "letture": [],
        }
    snapshot = {**snapshot, "directory": "",
                "proposte": [proposta_per_lo_studio(p) for p in snapshot.get("proposte") or []],
                "letture": [lettura_per_lo_studio(r) for r in snapshot.get("letture") or []]}
    return {
        "ok": True,
        "source": "memoria_apprendimento",
        **snapshot,
        "job_notturno": _stato_job_notturno(config),
    }


__all__ = ["build_react_lex_learning_payload", "CONSOLE_PIANIFICAZIONI_PATH"]
