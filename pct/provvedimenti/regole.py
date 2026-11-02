"""I termini e gli adempimenti di legge che seguono un provvedimento, dalla tabella versionata.

La tabella ``pct/data/provvedimenti_regole_v2026_11.json`` dice, per ogni tipo di
provvedimento e rito, che cosa la legge impone anche se il provvedimento non lo scrive
(es. art. 415 c.p.c.: notifica di ricorso e decreto; art. 103 disp. att. c.p.c.:
intimazione dei testimoni sette giorni prima). Ogni regola cita le norme del registro
``pct/procedura_fasi/fonti.py``.

Precedenze: se un capo del dispositivo fissa un termine proprio sullo stesso oggetto
(«oggetto» della regola), prevale il termine del giudice e la regola di legge tace.
Un termine di legge già decorso non si propone come scadenza: diventa una verifica.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Any

from .calcolo import calcola
from .dispositivo import Capo
from .modello import Voce
from .riferimenti import Riferimenti
from .testo import estratto

PERCORSO_REGOLE = Path(__file__).resolve().parents[1] / "data" / "provvedimenti_regole_v2026_11.json"
PREFISSO = "legge."
_ANCORE_CON_DATA = {"esplicita", "prima_udienza", "da_evento", "fino_udienza"}


@lru_cache(maxsize=1)
def tabella() -> dict[str, Any]:
    return json.loads(PERCORSO_REGOLE.read_text(encoding="utf-8"))


def regole() -> list[dict[str, Any]]:
    return list(tabella().get("regole") or [])


def _applicabile(regola: dict[str, Any], tipi: tuple[str, ...], materia: str, testo: str, modalita: str) -> bool:
    if materia not in regola.get("materie", ()) or not set(regola.get("tipi", ())) & set(tipi):
        return False
    if any(not re.search(espressione, testo, re.I) for espressione in regola.get("richiede", ())):
        return False
    solo = regola.get("solo_modalita")
    return not solo or modalita in solo


def _decisa_dal_giudice(regola: dict[str, Any], capi_letti: Iterable[Capo]) -> Capo | None:
    oggetto = regola.get("oggetto")
    if not oggetto:
        return None
    for capo in capi_letti:
        if capo.ancora is not None and capo.ancora.tipo in _ANCORE_CON_DATA and re.search(oggetto, capo.testo, re.I):
            return capo
    return None


def _base(regola: dict[str, Any], rif: Riferimenti, tipi: tuple[str, ...], **campi: Any) -> Voce:
    tipo = next((t for t in regola.get("tipi", ()) if t in tipi), "")
    return Voce(
        regola_id=PREFISSO + regola["id"], titolo=regola["titolo"], norme=tuple(regola.get("norme", ())),
        prova=rif.prove_tipo.get(tipo, ""), confidenza=float(regola.get("confidenza", 0.7)), chi=str(regola.get("chi") or ""),
        perentorio=regola.get("perentorio"), facoltativo=bool(regola.get("facoltativo")), nota=str(regola.get("nota") or ""),
        codice=str(regola.get("codice") or ""), tipo_termine=str(regola.get("tipo_termine") or ""), **campi,
    )


def _partenza(regola: dict[str, Any], rif: Riferimenti) -> tuple[Any, tuple[tuple[str, str, str], ...], str]:
    """Il giorno da cui si conta, i dati mostrati e, se manca, la domanda per l'avvocato."""
    ancora = regola.get("ancora")
    if ancora == "udienza":
        if rif.udienza is None:
            return None, (), rif.domanda_udienza(regola["titolo"])
        return rif.udienza, (rif.dato_udienza(),), ""
    giorno, dato = rif.dato_evento(ancora)
    if giorno is None:
        return None, (), Riferimenti.domanda_evento(ancora, regola["titolo"])
    return giorno, (dato,), ""


def voce_di_regola(regola: dict[str, Any], rif: Riferimenti, tipi: tuple[str, ...], materia: str) -> Voce:
    genere = regola.get("genere", "termine")
    ancora = regola.get("ancora", "nessuna")
    if genere in {"adempimento", "attesa"} or ancora == "nessuna":
        return _base(regola, rif, tipi, genere=genere, domanda=str(regola.get("domanda") or ""))
    if genere == "da_verificare" or ancora == "notificazione":
        domanda = str(regola.get("domanda") or Riferimenti.domanda_evento("notificazione", regola["titolo"]))
        return _base(regola, rif, tipi, genere="attesa" if genere == "attesa" else "da_verificare", domanda=domanda)
    dies, dati, domanda = _partenza(regola, rif)
    if dies is None:
        return _base(regola, rif, tipi, genere="da_verificare", domanda=domanda)
    calcolo = calcola(regola.get("termine") or {}, dies, materia=materia)
    if calcolo is None:
        return _base(regola, rif, tipi, genere="da_verificare", dati=dati,
                     domanda=f"{regola['titolo']}: il termine non è calcolabile con certezza, indicarne la data.")
    if calcolo.giorno < rif.oggi:
        decorso = {**regola, "titolo": f"{regola['titolo']}: termine già decorso il {calcolo.giorno:%d/%m/%Y}, verificare"}
        return _base(decorso, rif, tipi, genere="verifica", dati=dati, giorno=calcolo.giorno, calcolo=calcolo.spiegazione)
    campi = {"id_appuntamento": rif.id_appuntamento} if ancora == "udienza" and rif.id_appuntamento else {}
    return _base(regola, rif, tipi, genere="termine", dati=dati, giorno=calcolo.giorno, calcolo=calcolo.spiegazione,
                 dies_a_quo=dies, scadenziario=bool(regola.get("scadenziario")), campi_scadenza=campi,
                 id_appuntamento=campi.get("id_appuntamento", ""))


def voci_di_legge(
    tipi: tuple[str, ...], materia: str, testo: str, capi_letti: list[Capo], rif: Riferimenti, *, escludi: Iterable[str] = (),
) -> tuple[list[Voce], dict[int, dict[str, Any]], frozenset[int]]:
    """Le voci di legge; i capi del giudice che le sostituiscono (con la regola) e i capi che esse già coprono."""
    esclusi = set(escludi)
    voci: list[Voce] = []
    decise: dict[int, dict[str, Any]] = {}
    coperti: set[int] = set()
    for regola in regole():
        if regola["id"] in esclusi or not _applicabile(regola, tipi, materia, testo, rif.modalita):
            continue
        capo = _decisa_dal_giudice(regola, capi_letti)
        if capo is not None:
            decise.setdefault(capo.inizio, regola)
            continue
        voce = voce_di_regola(regola, rif, tipi, materia)
        richiamo = next((m for e in regola.get("richiede", ()) if (m := re.search(e, testo, re.I))), None)
        if richiamo is not None:
            # La prova più precisa è il richiamo della norma nel provvedimento (es. «art. 171-ter c.p.c.»).
            voce = replace(voce, prova=estratto(testo, richiamo.start(), richiamo.end()))
        voci.append(voce)
        if regola.get("copre"):
            coperti.update(c.inizio for c in capi_letti if re.search(regola["copre"], c.testo, re.I))
    return voci, decise, frozenset(coperti)


__all__ = ["PERCORSO_REGOLE", "PREFISSO", "regole", "tabella", "voce_di_regola", "voci_di_legge"]
