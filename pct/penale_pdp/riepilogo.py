"""Riepilogo dei procedimenti penali dello studio per la pagina PDP e il Centro telematico.

Poche interrogazioni sulle tabelle del deposito penale (nessuna per
fascicolo) e la prossima azione per ciascun procedimento, derivata dagli
stati ufficiali del PDP (art. 7 provv. DGSIA 11/07/2023): un deposito
rigettato o in errore tecnico va rifatto, uno pronto va inviato dal portale,
uno inviato attende l'esito; senza procedimento autorizzato si parte dalla
nomina (art. 6).
"""

from __future__ import annotations

import sqlite3
from typing import Any

IN_PREPARAZIONE = frozenset({"BOZZA", "PRONTO"})
IN_ATTESA = frozenset({"INVIATO", "IN_TRANSITO", "IN_FASE_DI_VERIFICA"})
DA_RIFARE = frozenset({"RIGETTATO", "ERRORE_TECNICO"})

# (codice, testo, tono, priorità: più bassa = prima)
AZIONI = {
    "RIFARE": ("Deposito rigettato o in errore: preparalo di nuovo", "danger", 0),
    "INVIARE": ("Pronto: invialo dal PDP e carica la ricevuta", "info", 1),
    "COMPLETARE": ("Bozza da completare", "warning", 2),
    "REGISTRO": ("Indica ufficio, registro e soggetti rappresentati", "warning", 3),
    "NOMINA": ("Procedimento non autorizzato: deposita la nomina", "warning", 4),
    "ESITO": ("In attesa dell'esito sul PDP", "neutral", 5),
    "NESSUNA": ("Nessuna azione in sospeso", "success", 6),
}


def _tabelle_presenti(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='criminal_deposits'").fetchone() is not None


def riepilogo(conn: sqlite3.Connection, oggi_iso: str) -> dict[str, dict[str, Any]]:
    """Per ogni fascicolo (practice_id) con un caso penale attivo: registro, depositi, udienza, azione."""
    conn.row_factory = sqlite3.Row
    if not _tabelle_presenti(conn):
        return {}
    casi = {r["id"]: dict(r) for r in conn.execute(
        "SELECT id, practice_id, pdp_office_code, authorized FROM criminal_cases WHERE COALESCE(archived, 0) = 0")}
    per_caso: dict[str, dict[str, Any]] = {
        cid: {"casoId": cid, "fascicoloId": c["practice_id"], "ufficio": c["pdp_office_code"] or "", "autorizzato": bool(c["authorized"]),
              "registro": None, "conteggi": {}, "ultimo": None, "prossimaUdienza": ""}
        for cid, c in casi.items()
    }
    for r in conn.execute("SELECT criminal_case_id, office_code, register_type, register_number, register_year FROM criminal_case_registers "
                          "ORDER BY is_current DESC, created_at"):
        voce = per_caso.get(r["criminal_case_id"])
        if voce is not None and voce["registro"] is None:
            voce["registro"] = dict(r)
    for r in conn.execute("SELECT criminal_case_id, id, act_name, status, sending_id, sent_at, rejection_reason, updated_at "
                          "FROM criminal_deposits ORDER BY COALESCE(NULLIF(sent_at, ''), created_at) DESC"):
        voce = per_caso.get(r["criminal_case_id"])
        if voce is None:
            continue
        voce["conteggi"][r["status"]] = voce["conteggi"].get(r["status"], 0) + 1
        if voce["ultimo"] is None:
            voce["ultimo"] = dict(r)
    for r in conn.execute("SELECT criminal_case_id, MIN(starts_at) AS quando FROM criminal_hearings WHERE starts_at >= ? "
                          "GROUP BY criminal_case_id", (oggi_iso,)):
        voce = per_caso.get(r["criminal_case_id"])
        if voce is not None:
            voce["prossimaUdienza"] = r["quando"]
    risultato: dict[str, dict[str, Any]] = {}
    for voce in per_caso.values():
        voce["azione"] = prossima_azione(voce)
        precedente = risultato.get(voce["fascicoloId"])
        if precedente is None or voce["azione"][2] < precedente["azione"][2]:
            risultato[voce["fascicoloId"]] = voce
    return risultato


def prossima_azione(voce: dict[str, Any]) -> tuple[str, str, int]:
    conteggi = voce.get("conteggi") or {}
    ultimo = voce.get("ultimo") or {}
    if ultimo.get("status") in DA_RIFARE:
        codice = "RIFARE"
    elif conteggi.get("PRONTO"):
        codice = "INVIARE"
    elif conteggi.get("BOZZA"):
        codice = "COMPLETARE"
    elif not voce.get("registro"):
        codice = "REGISTRO"
    elif any(conteggi.get(s) for s in IN_ATTESA):
        codice = "ESITO"
    elif not voce.get("autorizzato"):
        codice = "NOMINA"
    else:
        codice = "NESSUNA"
    return codice, AZIONI[codice][0], AZIONI[codice][2]


__all__ = ["AZIONI", "DA_RIFARE", "IN_ATTESA", "IN_PREPARAZIONE", "prossima_azione", "riepilogo"]
