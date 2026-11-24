"""Ingresso HTTP dell'harness: la domanda giuridica passa dall'harness prima delle ricerche operative.

Ordine: 1) harness (redazione, parere, termine con fattispecie, testo di un articolo del catalogo);
2) se l'harness non ha una regola per una domanda di termine, calcolo o norma, i motori certi di Lex
   (``risposta_certa``: termini, contributo unificato, articoli e sentenze dagli archivi), con la nota sulla materia;
3) altrimenti None: la domanda prosegue nel percorso ordinario, ma i router operativi non la deviano più su PEC,
   scadenze o anagrafiche perché riconoscono la richiesta giuridica.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable

from . import comprendi, rispondi
from .norme import normalizza

_log = logging.getLogger(__name__)

_NOTA_LAVORO = ("Se la sentenza è resa in una controversia di lavoro o previdenza, il termine breve per l'appello è di "
                "trenta giorni dalla notificazione e la sospensione feriale non si applica (art. 434 c.p.c.; art. 3 "
                "l. 742/1969): dimmi se è una causa di lavoro e ricalcolo.")


_SUL_FASCICOLO = (r"entro quando|quando scade|scadenz|termine|prossim\w* (?:udienz|pass|adempiment)|udienz|"
                  r"cosa (?:devo|dobbiamo) fare|che cosa resta|note scritte|memori")


def _domanda_sul_fascicolo(domanda: str) -> bool:
    return re.search(_SUL_FASCICOLO, normalizza(domanda)) is not None


def _etichetta(valore: float) -> str:
    return "alta" if valore >= 0.8 else "media" if valore >= 0.55 else "bassa"


def payload_harness(domanda: str, *, risposta_certa: Callable[[str], str] | None = None, fascicolo_id: str = "",
                    causa: Callable[[str], Any] | None = None) -> dict[str, Any] | None:
    try:
        c = comprendi(domanda)
    except Exception:
        _log.exception("harness: comprensione della domanda non riuscita")
        return None
    if not c.per_harness and not (fascicolo_id and _domanda_sul_fascicolo(domanda)):
        return None
    try:
        esito = rispondi(domanda, comprensione=c)
    except Exception as exc:
        # Domanda giuridica riconosciuta ma regola in errore: si dichiara, non si devia in silenzio sui router operativi.
        _log.exception("harness: errore nella regola per una domanda di tipo %s", c.tipo)
        return _payload(domanda, "**Analisi non completata**\n- La domanda è stata riconosciuta come richiesta giuridica "
                        f"({c.tipo}), ma il passo di analisi si è interrotto per un errore interno ({type(exc).__name__}). "
                        "Non do una risposta parziale: l'errore è registrato nel log e va corretto; nel frattempo la "
                        "questione va esaminata senza Lex.", 0.0, f"Errore interno dell'harness: {type(exc).__name__}.",
                        [], "errore_harness", {"rule": "errore_harness", "errore": type(exc).__name__})
    # Dentro un fascicolo i fatti vengono dal modello della causa (pct/ragionamento), con documento e data.
    from .causa import fatti_del_fascicolo

    dal_fascicolo = fatti_del_fascicolo(fascicolo_id, costruttore=causa) if fascicolo_id else None
    if esito is None and dal_fascicolo is not None and (c.tipo in {"termine", "parere"} or _domanda_sul_fascicolo(domanda)):
        return _payload(domanda, "**Cosa ho capito**\n- Domanda sul fascicolo aperto: rispondo con il modello della causa, "
                        "che ha già letto atti, notifiche, udienze e termini.\n\n" + dal_fascicolo.sezione()
                        + "\n\n_Fonte: modello della causa di IUSENTRA; ogni punto indica il documento e la data da cui è "
                        "letto. Nessun atto è stato salvato, firmato o inviato._", 0.85,
                        "Modello della causa del fascicolo (pct/ragionamento).", [], "modello_causa",
                        {"rule": "modello_causa", "2_fatti": {"origine": "modello_causa", **dal_fascicolo.to_dict()}})
    if esito is None:
        if c.tipo not in {"termine", "norma", "parere", "calcolo"} or risposta_certa is None:
            return None
        testo = risposta_certa(domanda)
        if not testo:
            return _risposta_da_rubrica(domanda, c)
        t = normalizza(domanda)
        if re.search(r"\bappell", t) and not re.search(r"lavor|previdenz|penal|tar\b|tributar", t):
            testo += "\n\n" + _NOTA_LAVORO
        return _payload(domanda, testo, 0.9, "Calcolo e testo dai motori certi di IUSENTRA (termini, archivio Normattiva).",
                        [], "motori_certi")
    if esito.regola in {"chiarimento_strumento", "fuori_materia"} and dal_fascicolo is None and not c.racconto:
        # Domanda di diritto senza fatti: se la rubrica ufficiale trova la norma, la norma vigente vale più di una scelta.
        da_rubrica = _risposta_da_rubrica(domanda, c)
        if da_rubrica is not None:
            return da_rubrica
    if dal_fascicolo is not None:
        esito.testo = esito.testo.replace("**Norme applicate**", dal_fascicolo.sezione() + "\n\n**Norme applicate**", 1) \
            if "**Norme applicate**" in esito.testo else esito.testo + "\n\n" + dal_fascicolo.sezione()
        esito.registro.setdefault("2_fatti", {})["dal_fascicolo"] = dal_fascicolo.to_dict()
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


def _risposta_da_rubrica(domanda: str, c) -> dict[str, Any] | None:
    """Domanda di diritto senza fatti e senza regola dedicata: la norma vigente trovata dalla rubrica ufficiale."""
    if c.racconto:
        return None
    from .rubriche import rispondi_da_rubrica

    try:
        esito = rispondi_da_rubrica(domanda, c.tipo)
    except Exception:
        _log.exception("harness: ricerca della norma per rubrica non riuscita")
        return None
    if esito is None:
        return None
    return _payload(domanda, esito.testo, 0.9, f"Norma trovata dalla rubrica ufficiale e letta nel testo vigente "
                    f"({len(esito.norme)} articolo/i dall'archivio Normattiva).", esito.fonti, "norma_per_rubrica",
                    {"rule": "norma_per_rubrica", "kind": c.tipo, "verified_norms": esito.norme, "deterministic": True})


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
