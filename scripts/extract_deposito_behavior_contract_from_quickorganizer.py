"""Estrae il contratto di validazione del deposito da Studio Telematico.

La fonte resta FormSentMailBee.cs decompilato. Lo script non interpreta la
normativa e non aggiunge regole: conserva condizioni, messaggi, esito e azione
UI dei metodi VerificaCampi* e li collega ai 270 tipi del menu originale.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
FORM = Path(os.environ["TEMP"]) / "quickorganizer_decompiled_full" / "FormSentMailBee.cs"
CATALOG = ROOT / "pct" / "data" / "cataloghi" / "quickorganizer_depositi_studio_telematico.json"
OUTPUT = (
    ROOT
    / "artifacts"
    / "deposito-telematico"
    / "contratto-comportamentale-studio-telematico-270.json"
)
RUNTIME_OUTPUT = (
    ROOT
    / "pct"
    / "data"
    / "cataloghi"
    / "quickorganizer_deposito_validazioni.json"
)

VALIDATION_METHOD_TABS = {
    "VerificaCampiAttoDaDepositare": "AttoDaDepositare",
    "VerificaCampiAnagraficaProcedimento": "AnagraficaProcedimento",
    "VerificaCampiIntroduttiviCassazione": "IntroduttiviCassazione",
    "VerificaCampiSanzioniGDP": "SanzioniGDP",
    "VerificaCampiProcessoEsecutivo": "ProcessoEsecutivo",
    "VerificaCampiEreditàSuccessioni": "EreditàSuccessioni",
    "VerificaCampiTipoOrgano": "TipoOrgano",
    "VerificaCampiIscrizioneRuolo": "IscrizioneRuolo",
}

SOURCE_KEY_REPAIRS = {
    "Professionista_ESECUZIONI_SIECIC::Progett369oDistribuzione": (
        "Professionista_ESECUZIONI_SIECIC::ProgettoDistribuzione"
    ),
}
CURATORE_SOURCE_KEY = "Curatore_CONCORSUALI_SIECIC::DepositoRelazioneIniziale"

CONTROL_RE = re.compile(
    r"\b(?:cbo|txt|dtp|data|Grid|UltraGrid|UltraCurrencyEditor|checkBox|"
    r"lbl|btn|grp)[A-Za-zÀ-ÿ_][A-Za-z0-9À-ÿ_]*"
)


def _clean(value: str) -> str:
    text = value
    for _ in range(2):
        if not any(marker in text for marker in ("\u00c3", "\u00c2", "\u00e2", "\ufffd")):
            break
        try:
            fixed = text.encode("latin-1").decode("utf-8")
        except UnicodeError:
            break
        if fixed == text:
            break
        text = fixed
    return text.replace("\ufffd", "?")


def _source_key(entry: dict[str, Any]) -> str:
    key = str(entry.get("key") or "").strip()
    if key in SOURCE_KEY_REPAIRS:
        return SOURCE_KEY_REPAIRS[key]
    if (
        not key
        and str(entry.get("macro") or "").strip() == "Procedimenti concorsuali"
        and str(entry.get("categoria") or "").strip() == "Atti del Curatore"
    ):
        return CURATORE_SOURCE_KEY
    return key


def _matching_delimiter(text: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    index = start
    state = "code"
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if state == "line_comment":
            if char == "\n":
                state = "code"
        elif state == "block_comment":
            if char == "*" and nxt == "/":
                state = "code"
                index += 1
        elif state in {"string", "char"}:
            if char == "\\":
                index += 1
            elif (state == "string" and char == '"') or (state == "char" and char == "'"):
                state = "code"
        elif char == "/" and nxt == "/":
            state = "line_comment"
            index += 1
        elif char == "/" and nxt == "*":
            state = "block_comment"
            index += 1
        elif char == '"':
            state = "string"
        elif char == "'":
            state = "char"
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ValueError(f"Delimitatore {opening}{closing} non chiuso da posizione {start}")


def _method_body(source: str, name: str) -> tuple[str, int]:
    match = re.search(rf"\bprivate\s+bool\s+{re.escape(name)}\s*\(\s*\)", source)
    if not match:
        raise RuntimeError(f"Metodo non trovato: {name}")
    opening = source.find("{", match.end())
    closing = _matching_delimiter(source, opening, "{", "}")
    return source[opening + 1 : closing], source[: opening + 1].count("\n") + 1


def _void_method_body(source: str, name: str) -> tuple[str, int]:
    match = re.search(rf"\bprivate\s+void\s+{re.escape(name)}\s*\(\s*\)", source)
    if not match:
        raise RuntimeError(f"Metodo non trovato: {name}")
    opening = source.find("{", match.end())
    closing = _matching_delimiter(source, opening, "{", "}")
    return source[opening + 1 : closing], source[: opening + 1].count("\n") + 1


def _split_arguments(call: str) -> list[str]:
    arguments: list[str] = []
    start = 0
    depths = {"(": 0, "[": 0, "{": 0}
    state = "code"
    index = 0
    while index < len(call):
        char = call[index]
        if state == "string":
            if char == "\\":
                index += 1
            elif char == '"':
                state = "code"
        elif char == '"':
            state = "string"
        elif char in depths:
            depths[char] += 1
        elif char == ")":
            depths["("] -= 1
        elif char == "]":
            depths["["] -= 1
        elif char == "}":
            depths["{"] -= 1
        elif char == "," and not any(depths.values()):
            arguments.append(call[start:index].strip())
            start = index + 1
        index += 1
    arguments.append(call[start:].strip())
    return arguments


def _message_calls(body: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in re.finditer(r"MessageBox\.Show\s*\(", body):
        opening = body.find("(", match.start())
        closing = _matching_delimiter(body, opening, "(", ")")
        args = _split_arguments(body[opening + 1 : closing])
        if len(args) < 2:
            continue
        button = next(
            (
                token
                for arg in args
                for token in re.findall(r"MessageBoxButtons\.([A-Za-z]+)", arg)
            ),
            "OK",
        )
        calls.append(
            {
                "start": match.start(),
                "end": closing + 1,
                "message_expression": args[1],
                "buttons": button,
                "call": body[match.start() : closing + 1],
            }
        )
    return calls


def _if_regions(body: str) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    for match in re.finditer(r"\bif\s*\(", body):
        opening = body.find("(", match.start())
        try:
            condition_end = _matching_delimiter(body, opening, "(", ")")
        except ValueError:
            continue
        cursor = condition_end + 1
        while cursor < len(body) and body[cursor].isspace():
            cursor += 1
        if cursor < len(body) and body[cursor] == "{":
            try:
                end = _matching_delimiter(body, cursor, "{", "}") + 1
            except ValueError:
                continue
            block = body[cursor + 1 : end - 1]
        else:
            semicolon = body.find(";", cursor)
            end = semicolon + 1 if semicolon >= 0 else cursor
            block = body[cursor:end]
        regions.append(
            {
                "start": match.start(),
                "condition_start": opening + 1,
                "condition_end": condition_end,
                "end": end,
                "condition": body[opening + 1 : condition_end].strip(),
                "block": block,
            }
        )
    return regions


def _decode_csharp_literal(value: str) -> str:
    return (
        value.replace(r"\r\n", "\n")
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
        .replace(r'\"', '"')
        .replace(r"\\", "\\")
    )


def _message_template(expression: str) -> str:
    literals = [
        _decode_csharp_literal(match.group(1))
        for match in re.finditer(r'"((?:\\.|[^"\\])*)"', expression)
    ]
    text = "".join(literals).strip()
    dynamic = re.sub(r'"(?:\\.|[^"\\])*"', "", expression)
    dynamic = re.sub(r"^[\s+]+|[\s+]+$", "", dynamic)
    if dynamic:
        text = f"{text} [valore dinamico: {dynamic}]".strip()
    return _clean(text)


def _document_flag_map(body: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    pattern = re.compile(
        r'Cells\[3\]\.Text\s*==\s*"(?P<tipo>[^"]+)"\s*\)\s*\{(?P<block>.*?)\}',
        re.S,
    )
    for match in pattern.finditer(body):
        for flag in re.findall(r"\b(flag\d*)\s*=\s*true\s*;", match.group("block")):
            mapping[flag] = _clean(match.group("tipo"))
    return mapping


def _applicable_keys(condition: str, keys: list[str]) -> list[str]:
    positive_tests: list[tuple[str, str]] = []
    negative_tests: list[tuple[str, str]] = []
    patterns = (
        ("equals", r'AttoDaInviareKey\s*==\s*"([^"]+)"'),
        ("contains", r'AttoDaInviareKey\.Contains\(\s*"([^"]+)"\s*\)'),
        ("starts", r'AttoDaInviareKey\.StartsWith\(\s*"([^"]+)"\s*\)'),
    )
    for kind, pattern in patterns:
        for match in re.finditer(pattern, condition):
            prefix = condition[max(0, match.start() - 2) : match.start()]
            target = negative_tests if "!" in prefix else positive_tests
            target.append((kind, _clean(match.group(1))))

    def matches(key: str, test: tuple[str, str]) -> bool:
        kind, value = test
        if kind == "equals":
            return key == value
        if kind == "starts":
            return key.startswith(value)
        return value in key

    selected = []
    for key in keys:
        if positive_tests and not any(matches(key, test) for test in positive_tests):
            continue
        if any(matches(key, test) for test in negative_tests):
            continue
        selected.append(key)
    return selected


def _active_methods(flags: dict[str, Any]) -> list[str]:
    methods = ["VerificaCampiAttoDaDepositare"]
    if flags.get("VisualizzaAnagraficaProcedimento"):
        methods.append("VerificaCampiAnagraficaProcedimento")
    optional = (
        ("VisualizzaIntroduttiviCassazione", "VerificaCampiIntroduttiviCassazione"),
        ("VisualizzaSanzioniGDP", "VerificaCampiSanzioniGDP"),
        ("isProcessoEsecutivo", "VerificaCampiProcessoEsecutivo"),
        ("isEreditàSuccessioni", "VerificaCampiEreditàSuccessioni"),
        ("TipoOrganoRequired", "VerificaCampiTipoOrgano"),
    )
    for flag, method in optional:
        if flags.get(flag):
            methods.append(method)
    if any(
        flags.get(flag)
        for flag in (
            "needNotaIscrizioneRuolo",
            "needContributoUnificato",
            "VisualizzaIntroduttiviCassazione",
            "VisualizzaSanzioniGDP",
            "isProcessoEsecutivo",
            "isEreditàSuccessioni",
            "TipoOrganoRequired",
        )
    ):
        methods.append("VerificaCampiIscrizioneRuolo")
    return methods


def _control_state(entry: dict[str, Any]) -> dict[str, dict[str, str]]:
    state: dict[str, dict[str, str]] = {}
    for item in entry.get("deposit_controls") or []:
        if not isinstance(item, dict):
            continue
        control = _clean(str(item.get("control") or "").strip())
        if not control:
            continue
        values = {
            str(name): _clean(str(value))
            for name, value in item.items()
            if name != "control" and value is not None
        }
        if values:
            state.setdefault(control, {}).update(values)
    return state


def _effective_states_from_source(
    source: str,
    source_keys: list[str],
) -> dict[str, dict[str, Any]]:
    """Applica le assegnazioni di ``QualeTipologiaDeposito`` alle 270 chiavi.

    Lo stato non viene dedotto dai nomi dei tipi: viene ricostruito seguendo,
    nell'ordine sorgente, defaults e rami ``AttoDaInviareKey`` del decompilato.
    """

    body, _ = _void_method_body(source, "QualeTipologiaDeposito")
    regions = _if_regions(body)
    flag_names = {
        "VisualizzaAnagraficaProcedimento",
        "VisualizzaIntroduttiviCassazione",
        "VisualizzaSanzioniGDP",
        "needProcura",
        "needContributoUnificato",
        "needNotaIscrizioneRuolo",
        "isProcessoEsecutivo",
        "isEredit\u00c3\u00a0Successioni",
        "TipoOrganoRequired",
        "SingleSelect",
    }
    target_pattern = (
        r"(?:cbo|txt|dtp|data|Grid|UltraGrid|UltraCurrencyEditor|checkBox|"
        r"lbl|btn|grp)\w+"
    )
    assignment_re = re.compile(
        rf"\b(?P<target>{target_pattern}|{'|'.join(sorted(flag_names))})"
        r"(?:\.(?P<property>Enabled|Visible|Text|SelectedIndex|Value))?"
        r"\s*=\s*(?P<value>[^;]+);"
    )
    states = {
        key: {"controls": {}, "flags": {}}
        for key in source_keys
        if key
    }
    for match in assignment_re.finditer(body):
        target = _clean(match.group("target"))
        prop = str(match.group("property") or "")
        value = _clean(" ".join(str(match.group("value") or "").split()))
        containers = [
            region
            for region in regions
            if region["start"] <= match.start() <= region["end"]
        ]
        guards = [
            _clean(" ".join(str(region.get("condition") or "").split()))
            for region in containers
        ]
        combined = " && ".join(f"({guard})" for guard in guards if guard)
        if combined and "AttoDaInviareKey" not in combined:
            continue
        applicable = _applicable_keys(combined, source_keys) if combined else list(source_keys)
        for key in applicable:
            if not key or key not in states:
                continue
            if target in flag_names and not prop:
                states[key]["flags"][target] = value.casefold() == "true"
            elif prop:
                states[key]["controls"].setdefault(target, {})[prop] = value
    return states


def extract_contract() -> dict[str, Any]:
    source = _clean(FORM.read_text(encoding="utf-8", errors="replace"))
    catalog_payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    entries = catalog_payload.get("entries") or []
    if len(entries) != 270:
        raise RuntimeError(f"Catalogo inatteso: {len(entries)} tipi invece di 270")
    source_keys = [_source_key(entry) for entry in entries]
    source_states = _effective_states_from_source(source, source_keys)
    rules: list[dict[str, Any]] = []
    method_rules: dict[str, list[str]] = {}

    for method, tab in VALIDATION_METHOD_TABS.items():
        body, line_offset = _method_body(source, method)
        regions = _if_regions(body)
        document_flags = _document_flag_map(body)
        method_rules[method] = []
        for call in _message_calls(body):
            containers = [
                region
                for region in regions
                if region["start"] <= call["start"] <= region["end"]
            ]
            containers.sort(key=lambda item: (item["start"], -item["end"]))
            region = min(containers, key=lambda item: item["end"] - item["start"]) if containers else None
            condition = str(region.get("condition") if region else "")
            guard_conditions = []
            for container in containers:
                guard = _clean(" ".join(str(container.get("condition") or "").split()))
                if guard and guard not in guard_conditions:
                    guard_conditions.append(guard)
            combined_condition = " && ".join(f"({guard})" for guard in guard_conditions)
            block = str(region.get("block") if region else body[call["end"] : call["end"] + 500])
            enclosing_blocks = [str(container.get("block") or "") for container in containers]
            source_line = line_offset + body[: call["start"]].count("\n")
            buttons = str(call["buttons"])
            if buttons == "YesNo":
                outcome = "conferma_avvocato"
            elif any(
                re.search(r"\bAvviso[A-Za-zÀ-ÿ_]*\s*=\s*false\s*;", candidate)
                for candidate in enclosing_blocks or [block]
            ):
                outcome = "avviso_con_presa_visione"
            elif any("return false;" in candidate for candidate in enclosing_blocks or [block]):
                outcome = "blocco"
            else:
                outcome = "informativo"
            focus = re.findall(r"\b([A-Za-zÀ-ÿ_][A-Za-z0-9À-ÿ_]*)\.Focus\s*\(\s*\)", block)
            tab_match = re.findall(r'UltraTabControl1\.Tabs\["([^"]+)"\]', block)
            controls = sorted(set(CONTROL_RE.findall(condition + "\n" + block)))
            document_types = sorted(
                {
                    document_flags[flag]
                    for flag in re.findall(r"\bflag\d*\b", condition)
                    if flag in document_flags
                }
            )
            rule_id = f"{method}:{source_line}"
            rule = {
                "id": rule_id,
                "method": method,
                "tab": tab_match[0] if tab_match else tab,
                "source_line": source_line,
                "condition": _clean(" ".join(condition.split())),
                "guard_conditions": guard_conditions,
                "combined_condition": combined_condition,
                "outcome": outcome,
                "buttons": buttons,
                "message": _message_template(str(call["message_expression"])),
                "message_expression": _clean(" ".join(str(call["message_expression"]).split())),
                "focus_control": focus[0] if focus else "",
                "controls": controls,
                "document_types": document_types,
                "applicable_source_keys": _applicable_keys(combined_condition or condition, source_keys),
            }
            rules.append(rule)
            method_rules[method].append(rule_id)

    per_type: list[dict[str, Any]] = []
    for entry, source_key in zip(entries, source_keys):
        source_state = source_states.get(source_key) or {"controls": {}, "flags": {}}
        flags = dict(source_state.get("flags") or {})
        flags.update(dict(entry.get("deposit_menu_flags") or {}))
        active_methods = _active_methods(flags)
        active_rule_ids = [
            rule_id
            for method in active_methods
            for rule_id in method_rules.get(method, [])
            if source_key
            in next(rule["applicable_source_keys"] for rule in rules if rule["id"] == rule_id)
        ]
        controls = {
            control: dict(values)
            for control, values in (source_state.get("controls") or {}).items()
        }
        for control, values in _control_state(entry).items():
            controls.setdefault(control, {}).update(values)
        per_type.append(
            {
                "key": entry.get("key") or "",
                "source_key": source_key,
                "macroarea": entry.get("macro") or "",
                "categoria": entry.get("categoria") or "",
                "flags": flags,
                "controls": controls,
                "validation_methods": active_methods,
                "validation_rule_ids": active_rule_ids,
            }
        )

    outcome_counts: dict[str, int] = {}
    for rule in rules:
        outcome = str(rule["outcome"])
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
    return {
        "schema_version": 1,
        "generated_at": datetime.now(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y %H:%M"),
        "source": {
            "application": "Studio Telematico 2026 Rel. 021",
            "file": str(FORM),
            "sha256": hashlib.sha256(FORM.read_bytes()).hexdigest(),
        },
        "scope": {
            "deposit_types": len(entries),
            "validation_methods": len(VALIDATION_METHOD_TABS),
            "validation_rules": len(rules),
            "outcomes": outcome_counts,
        },
        "method_rule_ids": method_rules,
        "rules": rules,
        "deposit_types": per_type,
    }


def main() -> int:
    contract = extract_contract()
    rendered = json.dumps(contract, ensure_ascii=False, indent=2) + "\n"
    for output in (OUTPUT, RUNTIME_OUTPUT):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(json.dumps(contract["scope"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
