"""La Guida pratica nella fase reale della pratica: fase, percorso dopo la sentenza e prima cosa da fare dalla Lettura.

La Lettura del fascicolo deduce la fase dai fatti (sentenza della causa, udienze, depositi) e, se la causa è decisa,
il percorso secondo l'esito letto dal dispositivo. La guida usa la Lettura già materializzata: nessuna lettura di
documenti nella richiesta. Senza Lettura pronta la guida resta quella della scheda.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def lettura_pronta(fascicolo_id: str) -> dict[str, Any] | None:
    """La Lettura con la stessa chiave del pannello; se non è pronta si prepara e si salva (come in sfondo)."""
    try:
        import json

        from web.blueprints.api_v1_react import _LETTURA_CACHE, _lettura_cache_key, prepara_lettura_in_cache

        chiave = _lettura_cache_key(fascicolo_id)
        dati = _LETTURA_CACHE.get(chiave)
        if dati is None and prepara_lettura_in_cache(fascicolo_id):
            dati = _LETTURA_CACHE.get(chiave)
        if dati is None:
            # Con verifiche in corso la Lettura non si salva: si calcola come fa il pannello (solo archivio, nessuna
            # rilettura dei documenti) e si usa per questa risposta.
            from lex.context.fascicolo_lettura_context import load_fascicolo_lettura_context

            lettura = load_fascicolo_lettura_context(fascicolo_id=fascicolo_id)
            return lettura if isinstance(lettura, dict) else None
        payload = json.loads(dati.decode("utf-8"))
        lettura = payload.get("lettura") if isinstance(payload, dict) else None
        return lettura if isinstance(lettura, dict) else None
    except Exception as exc:  # la guida non si blocca senza Lettura
        logger.warning("Lettura del fascicolo %s non disponibile per la guida: %s", fascicolo_id, exc)
        return None


def applica_fase_reale(payload: dict[str, Any], lettura: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(lettura, dict) or not isinstance(lettura.get("fase"), dict):
        return payload
    fase = lettura["fase"]
    prove = "; ".join(str(p) for p in fase.get("prove") or [] if p)
    checklist = payload.get("checklist") if isinstance(payload.get("checklist"), dict) else {}
    descrizione = str(fase.get("descrizione") or "").strip()
    if descrizione:
        nota = descrizione[:1].upper() + descrizione[1:] + "." + (f" Lo dicono: {prove}." if prove else "")
        if checklist.get("nota_fase"):
            nota += " Campi, allegati e avvertimenti della scheda servono per redigere un nuovo atto della stessa materia."
        checklist["nota_fase"] = nota
        checklist["fase_lettura"] = fase.get("codice")
        payload["checklist"] = checklist
    percorso = lettura.get("percorso")
    guida = payload.get("guida") if isinstance(payload.get("guida"), dict) else {}
    if isinstance(percorso, dict):
        payload["percorso"] = percorso
        primo = (percorso.get("passi") or percorso.get("rimedi") or [{}])[0]
        testo = primo.get("passo") or (f"Valutare: {primo.get('rimedio', '').lower()} — {primo.get('termine', '')}" if primo.get("rimedio") else "")
        if testo:
            guida.setdefault("quick_help", {})["prima_cosa_da_fare"] = testo
    elif fase.get("codice") not in {"stragiudiziale", "preparatoria", ""}:
        passi = [p for p in lettura.get("prossimi_passi") or [] if isinstance(p, dict) and p.get("azione")]
        if passi:
            guida.setdefault("quick_help", {})["prima_cosa_da_fare"] = passi[0]["azione"]
    payload["guida"] = guida
    return payload


_IN_PREPARAZIONE: set[tuple] = set()


def _calcola_fase(fascicolo_id: str) -> dict[str, Any]:
    risultato = applica_fase_reale({"guida": {}, "checklist": {"nota_fase": "scheda"}}, lettura_pronta(fascicolo_id))
    if risultato["checklist"].get("nota_fase") == "scheda":
        risultato["checklist"]["nota_fase"] = ""
    return {"ok": True, "nota_fase": risultato["checklist"].get("nota_fase", ""), "fase": risultato["checklist"].get("fase_lettura", ""),
            "percorso": risultato.get("percorso"), "prima_cosa_da_fare": (risultato["guida"].get("quick_help") or {}).get("prima_cosa_da_fare", "")}


def fase_per_la_guida(fascicolo_id: str, *, in_sfondo: bool = True) -> dict[str, Any]:
    """Quello che la guida mostra della fase reale: nota, percorso e prima cosa da fare.

    Se non è già pronto si prepara in sfondo (la Lettura può richiedere decine di secondi) e la risposta dice
    «in preparazione»: la pagina richiede di nuovo, la richiesta non resta mai appesa.
    """
    import json

    from web.blueprints.api_v1_react import _LETTURA_CACHE, _lettura_cache_key

    chiave = ("guida-fase", *_lettura_cache_key(fascicolo_id)[1:])
    pronto = _LETTURA_CACHE.get(chiave)
    if pronto is not None:
        return json.loads(pronto.decode("utf-8"))
    if not in_sfondo:
        risultato = _calcola_fase(fascicolo_id)
        _LETTURA_CACHE.set(chiave, json.dumps(risultato, ensure_ascii=False).encode("utf-8"))
        return risultato
    if chiave not in _IN_PREPARAZIONE:
        import threading

        from flask import copy_current_request_context, g

        _IN_PREPARAZIONE.add(chiave)
        contesto_studio = dict(vars(g))  # percorsi e studio della richiesta: il thread ha un contesto applicativo nuovo

        @copy_current_request_context
        def prepara() -> None:
            try:
                for nome, valore in contesto_studio.items():
                    setattr(g, nome, valore)
                risultato = _calcola_fase(fascicolo_id)
                if risultato.get("fase"):  # senza Lettura non si conserva nulla: si riproverà
                    _LETTURA_CACHE.set(chiave, json.dumps(risultato, ensure_ascii=False).encode("utf-8"))
            except Exception as exc:  # resta da preparare: la pagina mostra la scheda
                logger.warning("Fase della guida non preparata per %s: %s", fascicolo_id, exc)
            finally:
                _IN_PREPARAZIONE.discard(chiave)

        threading.Thread(target=prepara, name=f"guida-fase-{fascicolo_id}", daemon=True).start()
    return {"ok": True, "in_preparazione": True}


__all__ = ["applica_fase_reale", "fase_per_la_guida", "lettura_pronta"]
