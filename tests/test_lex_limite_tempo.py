"""Limite di tempo lato server per una richiesta a Lex: messaggio chiaro, thread del server libero."""
from __future__ import annotations

import json
import time

from flask import Flask, g


def test_richiesta_lenta_riceve_il_messaggio_entro_il_limite():
    from lex.limite_tempo import con_limite

    app = Flask(__name__)
    with app.test_request_context("/api/assistente/chat", method="POST"):
        g.utente_corrente = "avv"
        t = time.time()
        r = con_limite(lambda: time.sleep(3) or "tardi", secondi=0.5)
        assert time.time() - t < 2
        corpo = "".join(x.decode() if isinstance(x, bytes) else x for x in r.response)
        payload = json.loads(corpo.split("data: ", 1)[1].split("\n\n")[0])["payload"]
        assert "non ha completato la risposta" in payload["answer"]


def test_richiesta_veloce_e_g_disponibile():
    from lex.limite_tempo import con_limite

    app = Flask(__name__)
    with app.test_request_context("/"):
        g.utente_corrente = "avv"
        assert con_limite(lambda: g.utente_corrente, secondi=5) == "avv"


def test_richieste_concorrenti_non_superano_il_limite_e_un_utente_non_riempie_il_pool(monkeypatch):
    import threading

    import lex.limite_tempo as L

    monkeypatch.setattr(L, "_POSTI", threading.BoundedSemaphore(3))
    monkeypatch.setattr(L, "_PER_UTENTE", 2)
    monkeypatch.setattr(L, "_UTENTI", {})
    app = Flask(__name__)
    attivi, massimo, blocco, via = [0], [0], threading.Lock(), threading.Event()
    esiti = []

    def lavoro():
        with blocco:
            attivi[0] += 1
            massimo[0] = max(massimo[0], attivi[0])
        via.wait(2)
        with blocco:
            attivi[0] -= 1
        return "fatto"

    def richiesta(utente):
        with app.test_request_context("/"):
            r = L.con_limite(lavoro, secondi=5, chiave=utente)
            esiti.append((utente, r if isinstance(r, str) else "messaggio"))

    fili = [threading.Thread(target=richiesta, args=(u,)) for u in ("a", "a", "a", "b", "b", "c", "d")]
    for t in fili:
        t.start()
    time.sleep(0.5)
    via.set()
    for t in fili:
        t.join(10)
    assert massimo[0] <= 3                                     # mai oltre i posti del semaforo
    assert sum(1 for u, e in esiti if u == "a" and e == "fatto") <= 2   # al massimo 2 per utente
    assert L._UTENTI == {} and L._POSTI.acquire(blocking=False)         # posti e contatori rilasciati


def test_testo_troppo_lungo_ha_un_messaggio_chiaro():
    from lex.limite_tempo import TESTO_MASSIMO, con_limite

    app = Flask(__name__)
    with app.test_request_context("/"):
        r = con_limite(lambda: "mai", dati={"messages": [{"role": "user", "content": "x" * (TESTO_MASSIMO + 1)}]})
        corpo = "".join(x.decode() if isinstance(x, bytes) else x for x in r.response)
        assert "troppo lungo" in corpo


def test_risposta_in_streaming_si_consuma_nel_calcolo_senza_rompere_il_contesto():
    """Collaudo 23/11/2026: lo stream creato nel thread di Lex rimetteva il contesto copiato nel thread del server.

    Con il client di prova la chiusura falliva (LookupError su flask.app_ctx) e il teardown girava di nuovo su un
    contesto già chiuso; ora lo stream si consuma nel calcolo, entro il tempo massimo, e torna una risposta normale.
    """
    from flask import Response, request, stream_with_context

    from lex.limite_tempo import con_limite

    app = Flask(__name__)
    chiusure = []

    @app.teardown_request
    def _chiudi(_exc):
        chiusure.append(1)

    def risposta():
        def genera():
            yield "data: " + request.path + "\n\n"
            yield "data: [DONE]\n\n"
        return Response(stream_with_context(genera()), mimetype="text/event-stream", headers={"X-Accel-Buffering": "no"})

    @app.post("/api/assistente/chat")
    def chat():
        return con_limite(risposta, chiave="avv")

    with app.test_client() as client:
        r = client.post("/api/assistente/chat")
        assert r.status_code == 200
        assert r.get_data(as_text=True) == "data: /api/assistente/chat\n\ndata: [DONE]\n\n"
        assert r.mimetype == "text/event-stream"
        assert r.headers.get("X-Accel-Buffering") == "no"
    assert len(chiusure) <= 3
