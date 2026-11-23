"""Limite di tempo e di carico lato server per una richiesta a Lex.

Con il worker gthread un thread bloccato (archivio lento, disco saturo) restava occupato fino a 7 minuti. Il calcolo
della risposta gira in un esecutore dedicato e limitato:
- dopo ``LEX_RICHIESTA_SECONDI`` (60 s) la richiesta riceve un messaggio chiaro e il thread del server torna libero;
- i posti dell'esecutore sono contati da un semaforo (``LEX_RICHIESTE_PARALLELE``, 4) acquisito senza attesa e
  rilasciato quando il calcolo finisce davvero: un calcolo scaduto continua a occupare il suo posto finché termina,
  quindi i calcoli in sfondo non possono superare il limite;
- ogni utente o sessione ha al massimo ``LEX_RICHIESTE_PER_UTENTE`` (2) calcoli in corso: un solo utente non riempie
  il pool;
- il testo in ingresso oltre ``LEX_TESTO_MASSIMO`` (20.000 caratteri) non si elabora: un calcolo non può crescere con
  l'ingresso oltre quel limite.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _Scaduto
from typing import Any, Callable

_log = logging.getLogger(__name__)
_PARALLELE = int(os.environ.get("LEX_RICHIESTE_PARALLELE", "4"))
_PER_UTENTE = int(os.environ.get("LEX_RICHIESTE_PER_UTENTE", "2"))
TESTO_MASSIMO = int(os.environ.get("LEX_TESTO_MASSIMO", "20000"))
_ESECUTORE = ThreadPoolExecutor(max_workers=_PARALLELE, thread_name_prefix="lex-richiesta")
_POSTI = threading.BoundedSemaphore(_PARALLELE)
_UTENTI: dict[str, int] = {}
_BLOCCO_UTENTI = threading.Lock()

MESSAGGIO_TEMPO = ("**Lex non ha completato la risposta entro {secondi} secondi.**\n- Il server è sotto carico o un archivio "
                   "consultato non risponde. La richiesta è stata interrotta per non bloccare l'applicazione: riprova fra "
                   "qualche minuto. Nessun atto è stato salvato, firmato o inviato.")
MESSAGGIO_PIENO = ("**Lex è occupato da altre richieste.**\n- Riprova fra qualche istante. Nessun atto è stato salvato, firmato "
                   "o inviato.")
MESSAGGIO_UTENTE = ("**Hai già altre richieste a Lex in corso.**\n- Attendi che finiscano prima di inviarne un'altra. Nessun "
                    "atto è stato salvato, firmato o inviato.")
MESSAGGIO_LUNGO = ("**Il testo inviato a Lex è troppo lungo ({lunghezza} caratteri, massimo {massimo}).**\n- Riassumi i fatti "
                   "essenziali o allega i documenti al fascicolo: Lex li legge dal fascicolo.")


def risposta_messaggio(testo: str, motivo: str):
    from flask import Response

    payload = {"ok": False, "query_type": "lex_limite_tempo", "answer": testo, "sources": [], "citations": [],
               "confidence": 0.0, "confidence_label": "bassa", "confidence_reason": motivo, "disable_exports": True}

    def genera():
        yield f"data: {json.dumps({'payload': payload})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(genera(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def lunghezza_ingresso(dati: dict[str, Any]) -> int:
    """Caratteri del testo inviato a Lex: domanda e contenuti dei messaggi."""
    totale = len(str((dati or {}).get("question") or ""))
    for m in (dati or {}).get("messages") or []:
        if isinstance(m, dict):
            totale += len(str(m.get("content") or ""))
    return totale


def _prendi_utente(chiave: str) -> bool:
    with _BLOCCO_UTENTI:
        if _UTENTI.get(chiave, 0) >= _PER_UTENTE:
            return False
        _UTENTI[chiave] = _UTENTI.get(chiave, 0) + 1
        return True


def _rilascia_utente(chiave: str) -> None:
    with _BLOCCO_UTENTI:
        resto = _UTENTI.get(chiave, 1) - 1
        if resto > 0:
            _UTENTI[chiave] = resto
        else:
            _UTENTI.pop(chiave, None)


def _materializza(risposta: Any) -> Any:
    """Una risposta in streaming si consuma qui, nel thread del calcolo e nel suo contesto di richiesta.

    Il generatore di ``stream_with_context`` creato nel thread dell'esecutore conserva il contesto copiato: consumato
    poi dal thread del server lo rimetteva in cima e ne eseguiva di nuovo la chiusura (teardown ripetuti, connessioni
    SQLite chiuse da un thread diverso, ``LookupError`` sul contesto con il client di prova). Consumarlo qui fa anche
    rientrare la generazione del testo nel tempo massimo, che altrimenti proseguiva dopo la risposta.
    """
    from flask import Response

    if not isinstance(risposta, Response) or not risposta.is_streamed:
        return risposta
    try:
        corpo = b"".join(parte if isinstance(parte, bytes) else str(parte).encode("utf-8") for parte in risposta.response)
    finally:
        risposta.close()
    intestazioni = [(nome, valore) for nome, valore in risposta.headers.items()
                    if nome.lower() not in {"content-length", "transfer-encoding"}]
    return Response(corpo, status=risposta.status_code, headers=intestazioni)


def con_limite(calcolo: Callable[[], Any], *, secondi: float | None = None, chiave: str = "", dati: dict | None = None):
    """Esegue ``calcolo`` nel contesto della richiesta corrente, entro tempo, posti e lunghezza massimi."""
    from flask import copy_current_request_context, g

    secondi = float(os.environ.get("LEX_RICHIESTA_SECONDI", "60")) if secondi is None else secondi
    if dati is not None and lunghezza_ingresso(dati) > TESTO_MASSIMO:
        return risposta_messaggio(MESSAGGIO_LUNGO.format(lunghezza=lunghezza_ingresso(dati), massimo=TESTO_MASSIMO),
                                  "testo oltre il massimo")
    chiave = chiave or "anonimo"
    if not _prendi_utente(chiave):
        return risposta_messaggio(MESSAGGIO_UTENTE, "richieste dell'utente già in corso")
    if not _POSTI.acquire(blocking=False):
        _rilascia_utente(chiave)
        return risposta_messaggio(MESSAGGIO_PIENO, "esecutore di Lex pieno")
    stato_g = dict(vars(g))

    @copy_current_request_context
    def esegui():
        for nome, valore in stato_g.items():
            setattr(g, nome, valore)
        return _materializza(calcolo())

    def finito(_):
        _POSTI.release()
        _rilascia_utente(chiave)

    try:
        futuro = _ESECUTORE.submit(esegui)
    except Exception:
        finito(None)
        raise
    futuro.add_done_callback(finito)
    try:
        return futuro.result(timeout=secondi)
    except _Scaduto:
        _log.warning("Lex: richiesta oltre %.0f s, risposta di cortesia (il calcolo termina in sfondo)", secondi)
        return risposta_messaggio(MESSAGGIO_TEMPO.format(secondi=int(secondi)), f"oltre {int(secondi)} s")
