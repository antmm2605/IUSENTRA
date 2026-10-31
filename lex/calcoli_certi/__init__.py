"""Calcoli certi di Lex con i calcolatori di Strumenti legali (V37).

Il modello non calcola: per importi, tassi, scaglioni e date Lex chiede al software.
Flusso:

1. ``riconoscimento``: quale calcolatore serve, solo se univoco e se si chiede un calcolo;
2. collaudo normativo (``pct.calcolatori.collaudo``): solo i calcolatori i cui casi di
   riferimento coincidono con la norma rispondono al posto del modello; gli altri
   vengono indicati con il collegamento alla pagina, senza risultato;
3. ``estrazione``: i dati dalla domanda; le scelte non indicate sono dichiarate come ipotesi;
4. il calcolatore stesso dice cosa manca (messaggio del dominio): Lex lo chiede;
5. ``presentazione``: risultato, dettaglio, note, avvertenze e fonti ufficiali.

Base: art. 13 D.P.R. 115/2002, art. 1284 c.c. e le altre norme dichiarate da ogni
calcolatore nelle sue fonti; regola delle fonti certe (AGENTS.md).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from lex.calcoli_certi import presentazione
from lex.calcoli_certi.estrazione import estrai
from lex.calcoli_certi.riconoscimento import scegli_strumento
from lex.risposte_certe import RispostaCerta

_COLLAUDATI: dict[int, frozenset[str]] = {}


def _collaudati(gestore: Any) -> frozenset[str]:
    """Il collaudo si esegue una volta per processo (pochi millisecondi) e resta in memoria."""
    from pct.calcolatori.collaudo import strumenti_collaudati

    chiave = id(type(gestore))
    if chiave not in _COLLAUDATI:
        try:
            _COLLAUDATI[chiave] = strumenti_collaudati(gestore)
        except Exception:
            _COLLAUDATI[chiave] = frozenset()
    return _COLLAUDATI[chiave]


def _campi(tool: str, opzioni: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    from pct.calcolatori.schema import schema_calcolatore

    campi: list[dict[str, Any]] = []
    for campo in (schema_calcolatore(tool) or {}).get("campi", []):
        risolto = dict(campo)
        sorgente = str(risolto.pop("options_from", "") or "")
        if sorgente:
            risolto["options"] = [
                {"value": str(v.get("value")), "label": str(v.get("label") or v.get("value"))}
                for v in opzioni.get(sorgente, []) if v.get("value")
            ]
        campi.append(risolto)
    return campi


def _collegamento(tool: str) -> str:
    return f"/strumenti-legali/?tool={quote(tool)}"


def risposta_calcolatore(domanda: str, gestore_factory: Callable[[], Any]) -> RispostaCerta | None:
    from pct.calcolatori.metodi import TOOL_METHODS, sorgenti_opzioni
    from pct.strumenti_legali import GestioneStrumentiLegali

    titoli = {voce["id"]: voce["title"] for voce in GestioneStrumentiLegali.catalogo_moduli() if voce["id"] in TOOL_METHODS}
    tool = scegli_strumento(domanda, titoli)
    if not tool:
        return None
    titolo = titoli[tool]
    gestore = gestore_factory()
    if tool not in _collaudati(gestore):
        return RispostaCerta(
            f"Per questo calcolo c'è lo strumento «{titolo}» in Strumenti legali ({_collegamento(tool)}). "
            "Non è ancora tra i calcolatori collaudati sulla norma per le risposte di Lex: aprilo dalla pagina "
            "e verifica i dati; non ti do un numero che non posso garantire.",
            [], f"calcolatore_non_collaudato:{tool}",
        )
    try:
        opzioni = sorgenti_opzioni(gestore)
    except Exception:
        opzioni = {}
    campi = _campi(tool, opzioni)
    dati = estrai(domanda, campi)
    try:
        risultato = getattr(gestore, TOOL_METHODS[tool])(dict(dati.valori))
    except ValueError as exc:
        etichette = ", ".join(str(c.get("label") or c["name"]) for c in campi if c["name"] not in dati.valori)
        return RispostaCerta(
            f"Per il calcolo «{titolo}» mi manca un dato: {exc}"
            + (f"\nDati che posso usare: {etichette}." if etichette else "")
            + f"\nPuoi scriverli qui o compilarli in Strumenti legali ({_collegamento(tool)}).",
            [], f"calcolatore_dati_mancanti:{tool}",
        )
    except Exception:
        return None
    if not isinstance(risultato, dict):
        return None
    righe = [f"**{titolo}** — calcolo del software con le tabelle normative vigenti:", ""]
    righe += presentazione.righe_sintetiche(risultato)
    dettaglio = presentazione.tabella_dettaglio(risultato)
    if dettaglio:
        righe += ["", *dettaglio]
    if dati.ipotesi:
        righe += ["", "Ho considerato (correggimi se diverso): " + "; ".join(dati.ipotesi) + "."]
    note = presentazione.testi(risultato, "notes")[:4]
    avvertenze = presentazione.testi(risultato, "warnings")[:4]
    if note:
        righe += ["", "Note:", *[f"- {n}" for n in note]]
    if avvertenze:
        righe += ["", "Avvertenze:", *[f"- {a}" for a in avvertenze]]
    righe += ["", f"Dettaglio e modifica dei dati: Strumenti legali ({_collegamento(tool)})."]
    return RispostaCerta("\n".join(righe), presentazione.fonti(risultato), f"calcolatore:{tool}")


__all__ = ["risposta_calcolatore"]
