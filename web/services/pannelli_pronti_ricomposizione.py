"""Le parti di un pannello pronto che dipendono dall'utente e dal momento dell'apertura.

Il pannello «Letture» dice che cosa è nuovo dall'ultima apertura dell'utente e registra la vista: è una
proiezione personale che cambia a ogni apertura. Il resto del pannello si serve dal salvato; le novità si
ricompongono con la stessa funzione del motore (``novita_letture``) e la vista si registra come prima, salvo
``visto=0``.
"""

from __future__ import annotations

import json

from flask import request


def novita_letture(corpo: bytes, fascicolo_id: str) -> bytes:
    from web.services.registro_letture_runtime import novita_letture as calcola

    dati = json.loads(corpo.decode("utf-8"))
    letture = dati.get("letture") if isinstance(dati, dict) else None
    if not isinstance(letture, dict):
        return corpo
    segna = str(request.args.get("visto") or "1").strip().lower() not in {"0", "false", "no"}
    try:
        from web.blueprints.api_v1_react import _public_json_payload  # stessa sanificazione della risposta del motore

        letture["novita"] = _public_json_payload(calcola(fascicolo_id, segna_visto=segna), "novita")
    except Exception:
        # Come nel motore: le novità che non si leggono non fanno sparire il pannello, si dichiarano.
        letture.setdefault("degradato", []).append({"passo": "novità dall'ultima apertura",
                                                     "motivo": "Novità non disponibili in questo momento."})
    return json.dumps(dati, ensure_ascii=False).encode("utf-8")
