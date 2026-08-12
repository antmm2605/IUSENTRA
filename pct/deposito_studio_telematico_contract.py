"""Contratto operativo estratto dal deposito di Studio Telematico.

Il modulo legge soltanto il JSON generato dal decompilato e non introduce
regole proprie. Messaggi, esiti, tipi allegato e applicabilita' restano quelli
dei metodi ``VerificaCampi*`` della sorgente analizzata.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


CONTRACT_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "cataloghi"
    / "quickorganizer_deposito_validazioni.json"
)

DOCUMENT_LABELS = {
    "RicevutaPagamento": "Ricevuta di pagamento",
    "ProcessoVerbale": "Processo verbale",
    "TitoloEsecutivo": "Titolo esecutivo",
    "Precetto": "Atto di precetto",
    "AttoCitazione": "Atto di citazione del terzo",
    "Pignoramento": "Atto di pignoramento",
    "CopiaProvvedimento": "Copia autentica del provvedimento impugnato",
    "Procura": "Procura su foglio separato",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


@lru_cache(maxsize=1)
def load_studio_telematico_contract() -> dict[str, Any]:
    if not CONTRACT_PATH.is_file() or CONTRACT_PATH.stat().st_size == 0:
        return {"rules": [], "deposit_types": []}
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {"rules": [], "deposit_types": []}


@lru_cache(maxsize=1)
def _rules_by_id() -> dict[str, dict[str, Any]]:
    return {
        _text(rule.get("id")): rule
        for rule in load_studio_telematico_contract().get("rules") or []
        if isinstance(rule, dict) and _text(rule.get("id"))
    }


@lru_cache(maxsize=1)
def _types_by_key() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in load_studio_telematico_contract().get("deposit_types") or []:
        if not isinstance(item, dict):
            continue
        for key in (_text(item.get("key")), _text(item.get("source_key"))):
            if key:
                rows[key] = item
    return rows


def studio_telematico_type_contract(key: str) -> dict[str, Any] | None:
    return _types_by_key().get(_text(key))


def studio_telematico_rule(rule_id: str) -> dict[str, Any] | None:
    """Restituisce una regola identificata dalla riga del decompilato."""

    return _rules_by_id().get(_text(rule_id))


def studio_telematico_rules_for(key: str) -> list[dict[str, Any]]:
    contract = studio_telematico_type_contract(key)
    if not contract:
        return []
    rules = _rules_by_id()
    return [
        rules[rule_id]
        for rule_id in contract.get("validation_rule_ids") or []
        if rule_id in rules
    ]


def studio_telematico_document_requirements(key: str) -> list[dict[str, Any]]:
    """Restituisce soltanto gli allegati controllati dalla sorgente Studio."""

    contract = studio_telematico_type_contract(key)
    if not contract:
        return []
    requirements: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for rule in studio_telematico_rules_for(key):
        outcome = _text(rule.get("outcome"))
        for document_type in rule.get("document_types") or []:
            code = _text(document_type)
            marker = (code, outcome)
            if not code or marker in seen:
                continue
            seen.add(marker)
            requirements.append(
                {
                    "code": code,
                    "label": DOCUMENT_LABELS.get(code, code),
                    "required": outcome == "blocco",
                    "outcome": outcome,
                    "message": _text(rule.get("message")),
                    "ruleId": _text(rule.get("id")),
                }
            )

    flags = contract.get("flags") if isinstance(contract.get("flags"), dict) else {}
    if flags.get("needProcura"):
        procurement_rule = next(
            (
                rule
                for rule in studio_telematico_rules_for(key)
                if _text(rule.get("id")) == "VerificaCampiAttoDaDepositare:17929"
            ),
            None,
        )
        requirements.append(
            {
                "code": "Procura",
                "label": DOCUMENT_LABELS["Procura"],
                "required": False,
                "outcome": "conferma_avvocato",
                "message": _text((procurement_rule or {}).get("message")),
                "ruleId": _text((procurement_rule or {}).get("id")),
            }
        )
    return requirements


def studio_telematico_runtime_payload(key: str) -> dict[str, Any]:
    contract = studio_telematico_type_contract(key) or {}
    rules = studio_telematico_rules_for(key)
    outcomes: dict[str, int] = {}
    for rule in rules:
        outcome = _text(rule.get("outcome"))
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    return {
        "source": "Studio Telematico 2026 Rel. 021 decompilato",
        "validationMethods": list(contract.get("validation_methods") or []),
        "validationRuleIds": list(contract.get("validation_rule_ids") or []),
        "outcomes": outcomes,
        "controls": dict(contract.get("controls") or {}),
        "documents": studio_telematico_document_requirements(key),
    }
