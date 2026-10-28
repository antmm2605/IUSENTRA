"""Applicabilità temporale: evidenze e regole approvate, mai deduzioni del modello.

Il chiamante fornisce date/eventi confermati e impronte delle sole regole approvate
lette dal repository autorizzato. Una data non classificata, una versione incompleta
o una regola contraddittoria restano da verificare, senza eliminare la fonte.
Questo modulo non acquisisce testi e non certifica correttezza giuridica.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import re


def impronta(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def data_iso(value: str) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("Data macchina richiesta in formato ISO completo")
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError("Data non canonica")
    return result


@dataclass(frozen=True)
class Applicabilita:
    stato: str  # applicabile / non_applicabile / da_verificare
    motivi: tuple[str, ...]
    regole: tuple[str, ...] = ()


def data_evento_confermato(eventi: dict, nome: str) -> date | None:
    if not isinstance(eventi, dict) or not isinstance(nome, str) or not nome:
        return None
    value = eventi.get(nome)
    if not isinstance(value, dict) or value.get("confermato") is not True:
        return None
    if not isinstance(value.get("fonte_sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value["fonte_sha256"]):
        return None
    try:
        int(value["fonte_sha256"], 16)
        return data_iso(value["data"])
    except (KeyError, TypeError, ValueError):
        return None


def valuta_applicabilita(fonte: dict, eventi: dict, regole: list[dict],
                         impronte_approvate: frozenset[str]) -> Applicabilita:
    """Le impronte approvate provengono dal repository fidato, non dal payload AI.

    Ogni regola riguarda un atto identificato, un ambito (sostanziale/processuale),
    un evento nominato, intervallo [dal, al_escluso), esito e fonte con SHA/estratto.
    Nessuna corrispondenza di numeri senza tipo/anno e nessuna data odierna implicita.
    """
    identity, scope = fonte.get("atto_id"), fonte.get("ambito")
    if not identity or scope not in {"sostanziale", "processuale"}:
        return Applicabilita("da_verificare", ("Identità o ambito della norma mancanti",))
    pertinent = [r for r in regole if r.get("atto_id") == identity and r.get("ambito") == scope]
    applicable, missing, used = [], [], []
    for rule in pertinent:
        digest = impronta(rule)
        if digest not in impronte_approvate:
            missing.append("Regola transitoria non approvata o modificata")
            continue
        proof = rule.get("fonte")
        if not isinstance(proof, dict):
            missing.append("Fonte della regola transitoria mancante")
            continue
        text = proof.get("testo", "")
        if (not isinstance(text, str) or not text.strip() or not proof.get("url")
                or not proof.get("versione") or not proof.get("acquisita_il")
                or hashlib.sha256(text.encode()).hexdigest() != proof.get("sha256")
                or not proof.get("estratto") or proof["estratto"] not in text):
            missing.append("Fonte della regola transitoria incompleta o alterata")
            continue
        when = data_evento_confermato(eventi, rule.get("evento", ""))
        if when is None:
            missing.append("Evento richiesto non confermato: " + str(rule.get("evento")))
            continue
        try:
            start = data_iso(rule["dal"]) if rule.get("dal") else date.min
            end = data_iso(rule["al_escluso"]) if rule.get("al_escluso") else date.max
            if end <= start or rule.get("esito") not in {"applicabile", "non_applicabile"}:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            missing.append("Intervallo o esito della regola non valido")
            continue
        if start <= when < end:
            applicable.append(rule["esito"])
            used.append(digest)
    if missing:
        return Applicabilita("da_verificare", tuple(dict.fromkeys(missing)), tuple(used))
    if len(set(applicable)) > 1:
        return Applicabilita("da_verificare", ("Regole temporali discordanti",), tuple(used))
    if applicable and applicable[0] == "non_applicabile":
        return Applicabilita("non_applicabile", ("Esito di regole temporali approvate",), tuple(used))
    if pertinent and not applicable:
        return Applicabilita("da_verificare", ("Nessuna regola copre l'evento del caso",))
    # Senza transitoria nota servono comunque una data pertinente e la copertura
    # effettiva della versione acquisita. VIGENTE e data download non bastano.
    when = data_evento_confermato(eventi, fonte.get("evento_riferimento", ""))
    version = fonte.get("copertura_versione")
    if not isinstance(version, dict):
        version = {}
    if when is None or version.get("confermata") is not True or not version.get("dal"):
        return Applicabilita("da_verificare", ("Data pertinente o copertura della versione non confermata",))
    try:
        start = data_iso(version["dal"])
        end = data_iso(version["al_escluso"]) if version.get("al_escluso") else None
        if end is not None and end <= start:
            raise ValueError()
    except (ValueError, TypeError):
        return Applicabilita("da_verificare", ("Intervallo della versione non valido",))
    if when < start or (end is not None and when >= end):
        return Applicabilita("da_verificare", ("Acquisire la versione corrispondente alla data del caso",))
    # Una transitoria positiva ammette l'atto, non qualsiasi sua edizione.
    # Anche quel percorso richiede il testo riscontrato alla data pertinente.
    motivi = (("Esito di regole temporali approvate",) if applicable else ())
    return Applicabilita("applicabile", motivi + ("Versione riscontrata alla data dell'evento confermato",), tuple(used))
