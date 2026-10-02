"""Catalogo condiviso della ricerca: tracciabilità e consultazione, senza auto-conferme.

La ricerca fornita dallo studio è materiale interno da confrontare con la norma:
non è una fonte ufficiale e non può da sola creare o chiudere un obbligo.
Il catalogo versionato è conoscenza di prodotto; gli adempimenti del tenant
continuano a risiedere nei repository SQL dei presidi e dello scadenziario.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

CATALOGO = Path(__file__).parent / "data" / "notifiche_legali_ricerca_20260930.json"
FONTI = Path(__file__).parent / "data" / "notifiche_legali_fonti_20260930.json"


@lru_cache(maxsize=1)
def fonti() -> dict:
    return {f["id"]: f for f in json.loads(FONTI.read_text(encoding="utf-8"))["fonti"]}


def fonte_regola(regola: str) -> list[dict]:
    codice = {"lavoro_415": "cpc_415", "semplificato_281undecies": "cpc_281undecies", "ricorso_tar_41": "cpa_45", "ottemperanza_114": "cpa_45"}.get(regola)
    return [dict(fonti()[codice])] if codice else []


def _normalizza(testo: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", testo.casefold()) if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def _catalogo() -> dict:
    dati = json.loads(CATALOGO.read_text(encoding="utf-8"))
    for scheda in dati["sections"]:
        # Riferimenti conversazionali non risolvibili non sono citazioni.
        scheda["research_text"] = re.sub(r':chatgpt-content-reference\{[^}]*\}', '', scheda["research_text"])
        correzioni = []
        testo = scheda["research_text"].casefold()
        if "controricorso deve essere notificato" in testo:
            correzioni.append({"testo": "Nel regime vigente l’art. 370 c.p.c. prevede il deposito del controricorso entro 40 giorni dalla notificazione del ricorso. Non generare un obbligo generalizzato di notifica: verifica il regime temporale e l’eventuale ricorso incidentale.", "fonte": fonti()["cpc_370"]})
        if "ultima_rac" in testo:
            correzioni.append({"testo": "Per il deposito PAT ex art. 45 c.p.a. la decorrenza è il perfezionamento dell’ultima notificazione anche per il destinatario. La sola RAC attesta il perfezionamento per il mittente e non è la base del termine di deposito.", "fonte": fonti()["cpa_45"]})
        if "669-terdecies" in testo and "739 richiamato" in testo:
            correzioni.append({"testo": "Il reclamo cautelare ex art. 669-terdecies c.p.c. ha un termine perentorio di 15 giorni dalla pronuncia in udienza, oppure dalla comunicazione o dalla notificazione se anteriore. La disposizione richiama gli artt. 737 e 738 per il procedimento.", "fonte": fonti()["cpc_669terdecies"]})
        scheda["correzioni"] = correzioni
    return dati


def consulta(ricerca: str = "", *, pagina: int = 1, dimensione: int = 15) -> dict:
    dati = _catalogo()
    parole = _normalizza(ricerca[:240]).split()
    sezioni = [s for s in dati["sections"] if s["research_text"].strip()]
    risultati = [s for s in sezioni if all(p in _normalizza(s["title"] + " " + s["research_text"]) for p in parole)]
    dimensione = max(1, min(dimensione, 25))
    pagine = max(1, (len(risultati) + dimensione - 1) // dimensione)
    pagina = max(1, min(pagina, pagine))
    return {"ok": True, "versione": dati["version"], "source_sha256": dati["source_sha256"],
            "origine": "Ricerca fornita dallo studio il 30/09/2026",
            "avvertenza": "Materiale di ricerca: confronta la singola indicazione con il testo vigente e il provvedimento del caso. La consultazione non crea scadenze e non conferma una notifica.",
            "totale": len(risultati), "pagina": pagina, "pagine": pagine,
            "schede": risultati[(pagina - 1) * dimensione:pagina * dimensione]}


__all__ = ["consulta", "fonti", "fonte_regola"]
