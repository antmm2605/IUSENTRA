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
    """Usa la Lettura salvata per il profilo corrente."""
    try:
        from web.services.riscontri_processuali_runtime import lettura_materializzata

        return lettura_materializzata(fascicolo_id)
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
    passi = [p for p in lettura.get("prossimi_passi") or [] if isinstance(p, dict) and p.get("azione")]
    ragionamento = lettura.get("ragionamento") or {}
    if isinstance(percorso, dict):
        payload["percorso"] = percorso
    if ragionamento.get("conclusioni"):
        conclusioni: dict[str, list[dict[str, Any]]] = {}
        for voce in ragionamento["conclusioni"]:
            if voce.get("cosa"):
                conclusioni.setdefault(voce["cosa"], []).append(voce)
        operativi = []
        for passo in passi:
            candidati = [voce for voce in conclusioni.get(passo["azione"], [])
                         if ((voce.get("termine") or {}).get("scadenza") or "") == (passo.get("entro") or "")]
            voce = candidati[0] if len(candidati) == 1 else {}
            fonte = voce.get("letto") or {}
            modello = voce.get("template") if (
                voce.get("stato") == "da_fare" and voce.get("onerato_codice") in {"noi", "tutte_le_parti"}
                and fonte.get("documento_id") and not passo.get("scaduto") and not voce.get("dubbi")
            ) else ""
            operativi.append({
                **passo,
                "documento": fonte,
                "modello_atto": modello or "",
                "come": voce.get("come", ""),
                "perche": voce.get("perche", ""),
                "riscontri_mancanti": list(dict.fromkeys(
                    dubbio["manca"] for dubbio in voce.get("dubbi") or [] if dubbio.get("manca")
                )),
            })
        payload["passi_operativi"] = operativi
        payload["motivo_stato_passi"] = (lettura.get("stato_passi") or {}).get("motivo", "")
        if operativi:
            guida.setdefault("quick_help", {})["prima_cosa_da_fare"] = operativi[0]["azione"]
    elif isinstance(percorso, dict):
        primo = (percorso.get("passi") or percorso.get("rimedi") or [{}])[0]
        testo = primo.get("passo") or (f"Valutare: {primo.get('rimedio', '').lower()} — {primo.get('termine', '')}" if primo.get("rimedio") else "")
        if testo:
            guida.setdefault("quick_help", {})["prima_cosa_da_fare"] = testo
    elif fase.get("codice") not in {"stragiudiziale", "preparatoria", ""}:
        if passi:
            guida.setdefault("quick_help", {})["prima_cosa_da_fare"] = passi[0]["azione"]
    payload["guida"] = guida
    return payload


def _calcola_fase(fascicolo_id: str) -> dict[str, Any]:
    risultato = applica_fase_reale({"guida": {}, "checklist": {"nota_fase": "scheda"}}, lettura_pronta(fascicolo_id))
    if risultato["checklist"].get("nota_fase") == "scheda":
        risultato["checklist"]["nota_fase"] = ""
    fase = {
        "ok": True,
        "nota_fase": risultato["checklist"].get("nota_fase", ""),
        "fase": risultato["checklist"].get("fase_lettura", ""),
        "percorso": risultato.get("percorso"),
        "prima_cosa_da_fare": (risultato["guida"].get("quick_help") or {}).get("prima_cosa_da_fare", ""),
    }
    for chiave in ("passi_operativi", "motivo_stato_passi"):
        if chiave in risultato:
            fase[chiave] = risultato[chiave]
    return fase


def fase_per_la_guida(fascicolo_id: str, *, in_sfondo: bool = True) -> dict[str, Any]:
    """Espone la fase disponibile; la Lettura viene preparata dai suoi job."""
    risultato = _calcola_fase(fascicolo_id)
    if in_sfondo and not risultato.get("fase"):
        return {"ok": True, "in_preparazione": True}
    return risultato


__all__ = ["applica_fase_reale", "fase_per_la_guida", "lettura_pronta"]
