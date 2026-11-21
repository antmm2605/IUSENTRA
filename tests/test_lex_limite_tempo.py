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
