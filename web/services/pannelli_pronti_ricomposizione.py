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


def obblighi_da_lettura(corpo: bytes, fascicolo_id: str) -> bytes:
    from web.blueprints.api_v1_react import _con_riscontri_processuali, _public_json_payload

    dati = json.loads(corpo)
    risultato = _con_riscontri_processuali(dati, fascicolo_id, "notifiche")
    return json.dumps(_public_json_payload(risultato), ensure_ascii=False).encode("utf-8")

def redazione_dal_conto(corpo: bytes, fascicolo_id: str) -> bytes:
    """Completa una proiezione di Redazione salvata prima dell'esito economico."""
    from web.services.react_redazione_guidata_bridge import contributo_per_redazione
    from web.services.riscontri_processuali_runtime import contesto_operativo_da_lettura, lettura_materializzata

    dati = json.loads(corpo)
    economia = (dati.get("contesto") or {}).get("economia")
    if not isinstance(economia, dict) or (economia.get("contributoUnificato") or {}).get("disponibile"):
        return corpo
    comune = contesto_operativo_da_lettura(lettura_materializzata(fascicolo_id), fascicolo_id)
    if not comune.get("contributo"):
        return corpo
    economia["contributoUnificato"] = contributo_per_redazione(comune["contributo"])
    return json.dumps(dati, ensure_ascii=False).encode("utf-8")
