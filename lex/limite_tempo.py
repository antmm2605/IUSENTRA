"""Limite di tempo lato server per una richiesta a Lex.

Con il worker gthread un thread bloccato (archivio lento, disco saturo) restava occupato fino a 7 minuti. Il calcolo
della risposta gira in un esecutore dedicato e limitato: dopo ``LEX_RICHIESTA_SECONDI`` (60 s) la richiesta riceve un
messaggio chiaro e il thread del server torna libero. Se l'esecutore è pieno la richiesta non si accoda all'infinito.
"""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _Scaduto
from typing import Any, Callable

_log = logging.getLogger(__name__)
_ESECUTORE = ThreadPoolExecutor(max_workers=int(os.environ.get("LEX_RICHIESTE_PARALLELE", "4")), thread_name_prefix="lex-richiesta")
_IN_CORSO = 0

MESSAGGIO_TEMPO = ("**Lex non ha completato la risposta entro {secondi} secondi.**\n- Il server è sotto carico o un archivio "
                   "consultato non risponde. La richiesta è stata interrotta per non bloccare l'applicazione: riprova fra "
                   "qualche minuto. Nessun atto è stato salvato, firmato o inviato.")
MESSAGGIO_PIENO = ("**Lex è occupato da altre richieste.**\n- Riprova fra qualche istante. Nessun atto è stato salvato, firmato "
                   "o inviato.")


def risposta_messaggio(testo: str, motivo: str):
    from flask import Response

    payload = {"ok": False, "query_type": "lex_limite_tempo", "answer": testo, "sources": [], "citations": [],
               "confidence": 0.0, "confidence_label": "bassa", "confidence_reason": motivo, "disable_exports": True}

    def genera():
        yield f"data: {json.dumps({'payload': payload})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(genera(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def con_limite(calcolo: Callable[[], Any], *, secondi: float | None = None):
    """Esegue ``calcolo`` nel contesto della richiesta corrente, entro il tempo massimo."""
    global _IN_CORSO
    from flask import copy_current_request_context, g

    secondi = float(os.environ.get("LEX_RICHIESTA_SECONDI", "60")) if secondi is None else secondi
    if _IN_CORSO >= _ESECUTORE._max_workers:
        return risposta_messaggio(MESSAGGIO_PIENO, "esecutore di Lex pieno")
    stato_g = dict(vars(g))

    @copy_current_request_context
    def esegui():
        for chiave, valore in stato_g.items():
            setattr(g, chiave, valore)
        return calcolo()

    def finito(_):
        global _IN_CORSO
        _IN_CORSO -= 1

    _IN_CORSO += 1
    futuro = _ESECUTORE.submit(esegui)
    futuro.add_done_callback(finito)
    try:
        return futuro.result(timeout=secondi)
    except _Scaduto:
        _log.warning("Lex: richiesta oltre %.0f s, risposta di cortesia (il calcolo prosegue in sfondo)", secondi)
        return risposta_messaggio(MESSAGGIO_TEMPO.format(secondi=int(secondi)), f"oltre {int(secondi)} s")
