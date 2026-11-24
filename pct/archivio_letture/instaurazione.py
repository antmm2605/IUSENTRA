"""Le date dell'atto introduttivo confermate dal riscontro fra fonti diverse dello stesso fascicolo.

La data di deposito del ricorso, di iscrizione a ruolo o di notifica della citazione decide quale testo del
codice si applica (art. 35, comma 1, d.lgs. 149/2022: procedimenti instaurati dopo il 28/02/2023). Letta con
l'OCR resta una proposta («plausibile»); diventa certa quando un'altra fonte del fascicolo, indipendente, dice
lo stesso giorno per lo stesso campo e nessuna fonte dice un giorno diverso. Fra le fonti concordi ce ne deve
essere almeno una del procedimento (provvedimento, copia attestata o PolisWeb, relata): l'indice del deposito
redatto dall'avvocato è solo un riscontro.

Modulo puro: riceve i fatti già in archivio e restituisce quelli da rendere verificati, con la prova.
"""
from __future__ import annotations

import copy
from typing import Any, Iterable

from .date_campi_modello import CAMPI_INSTAURAZIONE

#: fonti che da sole non rendono certa la data (redatte dall'avvocato che deposita)
FONTI_DI_RISCONTRO = {"indice_deposito"}
_UTILI = {"verificata", "plausibile", "corretta"}


def _tipo_fonte(fatto: Any) -> str:
    for prova in getattr(fatto, "prove", None) or []:
        if prova.get("codice") == "tipo_fonte":
            return str(prova.get("dettaglio") or "")
    # Letture precedenti alla regola: nascevano solo da provvedimenti e copie attestate.
    return "provvedimento"


def date_concordi(fatti: Iterable[Any]) -> list[Any]:
    """I fatti «plausibili» dell'atto introduttivo che il riscontro di un'altra fonte rende verificati."""
    per_campo: dict[str, list[Any]] = {}
    for fatto in fatti:
        if (getattr(fatto, "categoria", "") == "metadato_fascicolo" and getattr(fatto, "campo", "") in CAMPI_INSTAURAZIONE
                and getattr(fatto, "verifica", "") in _UTILI and str(getattr(fatto, "valore", ""))[:10]):
            per_campo.setdefault(fatto.campo, []).append(fatto)
    esito = []
    for campo, elenco in per_campo.items():
        giorni = {str(f.valore)[:10] for f in elenco}
        if len(giorni) != 1:
            continue  # fonti discordanti: nessuna data diventa certa
        da_promuovere = [f for f in elenco if f.verifica == "plausibile"]
        if not da_promuovere:
            continue
        fonti = {(f.tipo, f.oggetto_id, f.sha256) for f in elenco}
        certa = [f for f in elenco if f.verifica in {"verificata", "corretta"} and _tipo_fonte(f) not in FONTI_DI_RISCONTRO]
        del_procedimento = [f for f in elenco if _tipo_fonte(f) not in FONTI_DI_RISCONTRO]
        if not certa and (len(fonti) < 2 or not del_procedimento):
            continue
        giorno = next(iter(giorni))
        descrizione = "; ".join(sorted({f"{_tipo_fonte(f).replace('_', ' ')} (documento {f.oggetto_id})" for f in elenco}))
        for fatto in da_promuovere:
            altre = {(f.tipo, f.oggetto_id, f.sha256) for f in elenco} - {(fatto.tipo, fatto.oggetto_id, fatto.sha256)}
            if not altre:
                continue  # la stessa fonte non si conferma da sola
            nuovo = copy.copy(fatto)
            nuovo.prove = [p for p in fatto.prove if p.get("codice") != "concordanza_fonti"] + [{
                "codice": "concordanza_fonti", "esito": "ok",
                "dettaglio": f"Stessa data {giorno[8:10]}/{giorno[5:7]}/{giorno[:4]} in {len(fonti)} fonti, nessuna discordante: {descrizione}.",
            }]
            nuovo.verifica = "verificata"
            esito.append(nuovo)
    return esito


__all__ = ["FONTI_DI_RISCONTRO", "date_concordi"]
