"""Ingresso HTTP dell'harness: la domanda giuridica passa dall'harness prima delle ricerche operative.

Ordine: 1) harness (redazione, parere, termine con fattispecie, testo di un articolo del catalogo);
2) se l'harness non ha una regola per una domanda di termine, calcolo o norma, i motori certi di Lex
   (``risposta_certa``: termini, contributo unificato, articoli e sentenze dagli archivi), con la nota sulla materia;
3) altrimenti None: la domanda prosegue nel percorso ordinario, ma i router operativi non la deviano più su PEC,
   scadenze o anagrafiche perché riconoscono la richiesta giuridica.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from . import comprendi, rispondi
from .norme import normalizza

_NOTA_LAVORO = ("Se la sentenza è resa in una controversia di lavoro o previdenza, il termine breve per l'appello è di "
                "trenta giorni dalla notificazione e la sospensione feriale non si applica (art. 434 c.p.c.; art. 3 "
                "l. 742/1969): dimmi se è una causa di lavoro e ricalcolo.")


def _etichetta(valore: float) -> str:
    return "alta" if valore >= 0.8 else "media" if valore >= 0.55 else "bassa"


def payload_harness(domanda: str, *, risposta_certa: Callable[[str], str] | None = None) -> dict[str, Any] | None:
    try:
        c = comprendi(domanda)
        if not c.per_harness:
            return None
        esito = rispondi(domanda, comprensione=c)
    except Exception:
        return None
    if esito is None:
        if c.tipo not in {"termine", "norma", "parere", "calcolo"} or risposta_certa is None:
            return None
        testo = risposta_certa(domanda)
        if not testo:
            return None
        t = normalizza(domanda)
        if re.search(r"\bappell", t) and not re.search(r"lavor|previdenz|penal|tar\b|tributar", t):
            testo += "\n\n" + _NOTA_LAVORO
        return _payload(domanda, testo, 0.9, "Calcolo e testo dai motori certi di IUSENTRA (termini, archivio Normattiva).",
                        [], "motori_certi")
    from .scrittura import scrivi

    stesura = scrivi(esito.testo)
    if stesura.scrittore != "deterministico":
        esito.testo = stesura.testo
    motivo = (f"Regola «{esito.regola}»: {len(esito.norme_verificate)} norme confrontate con il testo vigente"
              + (f"; stesura di {stesura.scrittore} controllata" if stesura.accettata and stesura.scrittore != "deterministico" else "")
              + (f"; {len(esito.affermazioni_tolte)} affermazioni non verificate escluse" if esito.affermazioni_tolte else "")
              + (f"; {len(esito.citazioni_non_verificate)} riferimenti da controllare" if esito.citazioni_non_verificate else "")
              + ".")
    return _payload(domanda, esito.testo, esito.affidabilita, motivo, esito.fonti, esito.regola, esito.to_dict())


def _payload(domanda: str, testo: str, affidabilita: float, motivo: str, fonti: list[dict[str, str]], regola: str,
             dettaglio: dict[str, Any] | None = None) -> dict[str, Any]:
    from lex.formatting.ui_payloads import direct_answer_payload

    payload = direct_answer_payload(domanda, testo, query_type="lex_harness", sources=fonti,
                                    citations=[f["title"] for f in fonti], legal_reference_guard_active=True)
    payload.update({
        "confidence": affidabilita, "confidence_label": _etichetta(affidabilita), "confidence_reason": motivo,
        "engine": "Lex — harness passo per passo", "focus_topic": "harness_giuridico",
        "focus_label": "Analisi giuridica e redazione", "lex_harness": dettaglio or {"rule": regola},
    })
    payload["execution_policy"]["summary_label"] = "harness deterministico: norme vigenti e regole del software"
    return payload
