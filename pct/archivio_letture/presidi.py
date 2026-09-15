"""Le viste dell'archivio per i presìdi: udienze e termini, prove di notifica, ruoli, riassunto.

I presìdi non rileggono i documenti: chiedono all'archivio i fatti utili
(verificati, plausibili, corretti) e li usano nella forma che già conoscono.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from pct.registro_letture.fatti_repository import Fatto, VERIFICHE_UTILI

FORZA_PROVA = {"deposito_prova": 6, "rdac": 5, "rac": 4, "relata": 3, "attestazione": 2, "atto_notificato": 1, "comunicazione_cancelleria": 0, "errore_consegna": 0}
_ETICHETTA_VERIFICA = {"verificata": "verificata dal software", "plausibile": "da confermare", "corretta": "corretta dall'avvocato", "respinta": "respinta", "ignorata": "ignorata"}


def _giorno(valore: str) -> date | None:
    from pct.registro_letture.verifica_date import interpreta_data

    return interpreta_data(str(valore or "").split("T")[0])


def etichetta_verifica(verifica: str) -> str:
    return _ETICHETTA_VERIFICA.get(verifica, verifica)


def udienze_e_termini(fatti: Iterable[Fatto], *, oggi: date | None = None) -> list[dict[str, Any]]:
    """Le date di udienza e i termini letti, nella forma delle azioni del presidio documentale."""
    oggi = oggi or date.today()
    azioni: list[dict[str, Any]] = []
    visti: set[tuple[str, str, str]] = set()
    for fatto in fatti:
        if fatto.categoria != "data" or fatto.campo not in {"udienza", "termine", "costituzione"} or fatto.verifica not in VERIFICHE_UTILI:
            continue
        giorno = _giorno(fatto.valore)
        if giorno is None:
            continue
        chiave = (fatto.campo, fatto.oggetto_id, giorno.isoformat())
        if chiave in visti:
            continue
        visti.add(chiave)
        tipo = "udienza_documento" if fatto.campo == "udienza" else "termine_documento"
        ora = fatto.valore.split("T")[1] if "T" in fatto.valore else ""
        azioni.append({
            "id": f"{tipo}-{fatto.oggetto_id}-{giorno.isoformat()}",
            "type": tipo,
            "title": "Udienza letta dai documenti del fascicolo" if tipo == "udienza_documento" else "Termine processuale letto dai documenti del fascicolo",
            "description": f"{fatto.etichetta}: {fatto.contesto[:160]}" if fatto.contesto else fatto.etichetta,
            "dateIso": giorno.isoformat(),
            "date": giorno.strftime("%d/%m/%Y"),
            "time": ora,
            "rawDate": fatto.valore_letto,
            "documentId": fatto.oggetto_id,
            "objectType": fatto.tipo,
            "source": fatto.origine,
            "tone": "warning" if fatto.verifica != "plausibile" else "neutral",
            "priority": "important" if fatto.verifica != "plausibile" else "normal",
            "verifica": fatto.verifica,
            "verificaLabel": etichetta_verifica(fatto.verifica),
            "prove": list(fatto.prove),
            "overdue": giorno < oggi,
            "dateCorrected": fatto.verifica == "corretta",
            "requiresConfirmation": fatto.verifica == "plausibile",
        })
    azioni.sort(key=lambda voce: (voce["dateIso"], voce["type"]))
    return azioni


def prove_notifica_per_oggetto(fatti: Iterable[Fatto]) -> dict[str, dict[str, Any]]:
    """Per ogni documento o PEC la prova di notifica che ne dice la natura.

    Vince la prova menzionata per prima (l'intestazione «RELATA DI NOTIFICA»
    dice che cos'è il documento anche se poi cita le ricevute); a parità di
    posizione, la più forte. Tutte le prove lette restano in `tutte`.
    """
    esito: dict[str, dict[str, Any]] = {}
    for fatto in fatti:
        if fatto.categoria != "prova_notifica" or fatto.verifica not in VERIFICHE_UTILI:
            continue
        corrente = esito.get(fatto.oggetto_id)
        forza = FORZA_PROVA.get(fatto.campo, -1)
        chiave = (fatto.posizione, -forza)
        if corrente is None:
            esito[fatto.oggetto_id] = {"kind": fatto.campo, "forza": forza, "posizione": fatto.posizione, "etichetta": fatto.etichetta, "verifica": fatto.verifica, "origine": fatto.origine, "tipo": fatto.tipo, "contesto": fatto.contesto, "tutte": [fatto.campo]}
        else:
            corrente["tutte"].append(fatto.campo)
            if chiave < (corrente["posizione"], -corrente["forza"]):
                corrente.update({"kind": fatto.campo, "forza": forza, "posizione": fatto.posizione, "etichetta": fatto.etichetta, "verifica": fatto.verifica, "origine": fatto.origine, "contesto": fatto.contesto})
    return esito


def ruoli_letti(fatti: Iterable[Fatto]) -> list[dict[str, Any]]:
    visti: dict[str, dict[str, Any]] = {}
    for fatto in fatti:
        if fatto.categoria != "ruolo" or fatto.verifica not in VERIFICHE_UTILI:
            continue
        voce = visti.setdefault(fatto.valore, {"valore": fatto.valore, "campo": fatto.campo, "verifica": fatto.verifica, "oggetti": []})
        if fatto.oggetto_id not in voce["oggetti"]:
            voce["oggetti"].append(fatto.oggetto_id)
        if fatto.verifica == "verificata":
            voce["verifica"] = "verificata"
    return sorted(visti.values(), key=lambda voce: (0 if voce["verifica"] == "verificata" else 1, voce["valore"]))


def riassunto_archivio(fatti: Iterable[Fatto]) -> dict[str, Any]:
    """Il riassunto per il pannello: quanti fatti per verdetto, udienze, termini, prove, ruoli, plausibili da confermare."""
    elenco = list(fatti)
    per_verifica = {"verificata": 0, "plausibile": 0, "respinta": 0, "corretta": 0, "ignorata": 0}
    for fatto in elenco:
        per_verifica[fatto.verifica] = per_verifica.get(fatto.verifica, 0) + 1
    utili = [fatto for fatto in elenco if fatto.verifica in VERIFICHE_UTILI]
    da_confermare = [
        {"id": fatto.id, "campo": fatto.campo, "etichetta": fatto.etichetta, "valore": fatto.valore, "valore_letto": fatto.valore_letto, "oggetto_id": fatto.oggetto_id, "tipo": fatto.tipo, "contesto": fatto.contesto, "prove": list(fatto.prove)}
        for fatto in elenco if fatto.verifica == "plausibile" and fatto.categoria == "data" and fatto.campo in {"udienza", "termine", "costituzione"}
    ]
    return {
        "totale": len(elenco),
        "per_verifica": per_verifica,
        "udienze": sum(1 for fatto in utili if fatto.categoria == "data" and fatto.campo == "udienza"),
        "termini": sum(1 for fatto in utili if fatto.categoria == "data" and fatto.campo in {"termine", "costituzione", "decorrenza"}),
        "notifiche": sum(1 for fatto in utili if fatto.categoria == "data" and fatto.campo in {"notifica", "accettazione", "consegna"}),
        "prove_notifica": sum(1 for fatto in utili if fatto.categoria == "prova_notifica"),
        "ruoli": len(ruoli_letti(utili)),
        "eventi": sum(1 for fatto in utili if fatto.categoria == "evento"),
        "per_motore": {"documenti": sum(1 for fatto in utili if fatto.motore == "documenti"), "pec": sum(1 for fatto in utili if fatto.motore == "pec")},
        "da_confermare": da_confermare[:12],
    }


__all__ = ["FORZA_PROVA", "etichetta_verifica", "prove_notifica_per_oggetto", "riassunto_archivio", "ruoli_letti", "udienze_e_termini"]
