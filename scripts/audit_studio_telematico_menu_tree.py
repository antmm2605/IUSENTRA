from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(r"D:\tmp\qo-decomp-codex-20260812")
DEFAULT_JSON = ROOT / "artifacts" / "react-migration" / "audit-menu-funzioni-studio-telematico.json"
DEFAULT_MARKDOWN = ROOT / "artifacts" / "react-migration" / "audit-menu-funzioni-studio-telematico.md"

TOOL_DECLARATION_RE = re.compile(
    r"(?:Infragistics\.Win\.UltraWinToolbars\.)?"
    r"(?P<kind>[A-Za-z]+Tool)\s+(?P<variable>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"new\s+(?:Infragistics\.Win\.UltraWinToolbars\.)?[A-Za-z]+Tool\(\"(?P<key>[^\"]*)\"",
)
TOOL_CHILDREN_RE = re.compile(
    r"(?P<parent>[A-Za-z_][A-Za-z0-9_]*)\.(?:Tools|NonInheritedTools)\.AddRange\("
    r"new\s+Infragistics\.Win\.UltraWinToolbars\.ToolBase\[[^\]]+\]\s*"
    r"\{(?P<children>.*?)\}\s*\);",
    re.DOTALL,
)
TOOLBAR_DECLARATION_RE = re.compile(
    r"(?:Infragistics\.Win\.UltraWinToolbars\.)?UltraToolbar\s+"
    r"(?P<variable>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"new\s+(?:Infragistics\.Win\.UltraWinToolbars\.)?UltraToolbar\(\"(?P<key>[^\"]*)\"\)",
)
WINFORMS_TOOL_DECLARATION_RE = re.compile(
    r"(?:this\.)?(?P<variable>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*new\s+"
    r"(?:System\.Windows\.Forms\.)?"
    r"(?P<kind>ToolStripMenuItem|ContextMenuStrip|MenuStrip|ToolStrip|ToolStripDropDownButton|ToolStripButton)\s*\("
)
WINFORMS_TEXT_RE = re.compile(
    r"this\.(?P<variable>[A-Za-z_][A-Za-z0-9_]*)\.Text\s*=\s*\"(?P<caption>(?:\\.|[^\"\\])*)\";"
)
INTERACTIVE_EVENT_RE = re.compile(
    r"(?:this\.)?(?P<variable>[A-Za-z_][A-Za-z0-9_]*)\."
    r"(?P<event>Click|DoubleClick|ButtonClick|ItemClick|LinkClicked)\s*\+=\s*"
    r"(?:new\s+(?:System\.)?[A-Za-z0-9_.]+\s*\(\s*)?"
    r"(?P<handler>[A-Za-z_][A-Za-z0-9_]*)"
)
ACCESSIBLE_NAME_RE = re.compile(
    r"this\.(?P<variable>[A-Za-z_][A-Za-z0-9_]*)\.AccessibleName\s*=\s*"
    r"\"(?P<caption>(?:\\.|[^\"\\])*)\";"
)
TOOLTIP_RE = re.compile(
    r"(?:this\.)?[A-Za-z_][A-Za-z0-9_]*\.SetToolTip\(this\."
    r"(?P<variable>[A-Za-z_][A-Za-z0-9_]*),\s*\"(?P<caption>(?:\\.|[^\"\\])*)\"\);"
)
WINFORMS_CHILDREN_RE = re.compile(
    r"this\.(?P<parent>[A-Za-z_][A-Za-z0-9_]*)\."
    r"(?:Items|DropDownItems)\.AddRange\(new\s+(?:System\.Windows\.Forms\.)?ToolStripItem\[[^\]]+\]\s*"
    r"\{(?P<children>.*?)\}\s*\);",
    re.DOTALL,
)
RIBBON_GROUP_DECLARATION_RE = re.compile(
    r"(?:Infragistics\.Win\.UltraWinToolbars\.)?RibbonGroup\s+"
    r"(?P<variable>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"new\s+(?:Infragistics\.Win\.UltraWinToolbars\.)?RibbonGroup\(\"(?P<key>[^\"]*)\"\)",
)
CAPTION_RE = re.compile(
    r"(?P<variable>[A-Za-z_][A-Za-z0-9_]*)\.SharedPropsInternal\.Caption\s*=\s*\"(?P<caption>(?:\\.|[^\"\\])*)\";"
)
CONTAINER_TEXT_RE = re.compile(
    r"(?P<variable>(?:ultraToolbar|ribbonGroup)[A-Za-z0-9_]*)\.Text\s*=\s*\"(?P<caption>(?:\\.|[^\"\\])*)\";"
)
MANAGER_TOOLBARS_RE = re.compile(
    r"this\.(?P<manager>[A-Za-z_][A-Za-z0-9_]*)\.Toolbars\.AddRange\("
    r"new\s+Infragistics\.Win\.UltraWinToolbars\.UltraToolbar\[[^\]]+\]\s*"
    r"\{(?P<children>.*?)\}\s*\);",
    re.DOTALL,
)
FILTER_METHOD_RE = re.compile(
    r"private void BtnFiltraRubricaPer_(?P<name>[^\(]+)_ToolClick(?P<body>.*?)"
    r"(?=\n\s*private void |\Z)",
    re.DOTALL,
)
FILTER_LABEL_RE = re.compile(r"FilterLabel\s*=\s*\"(?P<label>(?:\\.|[^\"\\])*)\"")
FILTER_FIELD_RE = re.compile(
    r"SharedProps\.Tag\s*=\s*\"\(?\s*(?P<field>[A-Za-z_][A-Za-z0-9_]*)"
)
PRATICHE_SELECT_RE = re.compile(
    r"SELECT (?P<columns>.*?) FROM PRATICHE WHERE \(NUMEROPRATICA = \?\)",
    re.DOTALL,
)


def _source_file(source_root: Path, relative: str) -> Path:
    path = source_root / relative
    if not path.is_file():
        raise FileNotFoundError(f"File sorgente non trovato: {path}")
    return path


def _read_decompiled(path: Path) -> str:
    payload = path.read_bytes()
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload.decode("cp1252")


def _repair_text(value: str) -> str:
    text = str(value or "")
    if any(marker in text for marker in ("\u00c3", "\u00c2", "\u00e2")):
        try:
            repaired = text.encode("latin1").decode("utf-8")
            if repaired.count("\ufffd") <= text.count("\ufffd"):
                text = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return text


def _decode_csharp_string(value: str) -> str:
    return _repair_text(
        value.replace(r"\r\n", " ")
        .replace(r"\n", " ")
        .replace(r"\t", " ")
        .replace(r'\"', '"')
        .replace("&&", "&")
        .strip()
    )


def _variables(value: str) -> list[str]:
    return re.findall(
        r"(?<![A-Za-z0-9_])(?:this\.)?"
        r"((?:[A-Za-z]+Tool|ultraToolbar|ribbonGroup)[A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*)",
        value,
    )


def _initialise_component(source: str) -> str:
    marker = "\tprivate void InitializeComponent()"
    start = source.find(marker)
    if start < 0:
        raise ValueError("InitializeComponent non trovato")
    return source[start:]


def _component_source(source: str) -> str:
    try:
        return _initialise_component(source)
    except ValueError:
        return source


def _tool_nodes(initializer: str) -> dict[str, dict[str, str]]:
    nodes: dict[str, dict[str, str]] = {}
    for match in TOOL_DECLARATION_RE.finditer(initializer):
        nodes[match.group("variable")] = {
            "variable": match.group("variable"),
            "key": _repair_text(match.group("key")),
            "kind": match.group("kind"),
            "caption": "",
        }
    for regex, kind in (
        (TOOLBAR_DECLARATION_RE, "UltraToolbar"),
        (RIBBON_GROUP_DECLARATION_RE, "RibbonGroup"),
    ):
        for match in regex.finditer(initializer):
            nodes[match.group("variable")] = {
                "variable": match.group("variable"),
                "key": _repair_text(match.group("key")),
                "kind": kind,
                "caption": "",
            }
    for match in WINFORMS_TOOL_DECLARATION_RE.finditer(initializer):
        variable = match.group("variable")
        nodes[variable] = {
            "variable": variable,
            "key": variable,
            "kind": match.group("kind"),
            "caption": "",
        }
    for match in CAPTION_RE.finditer(initializer):
        variable = match.group("variable")
        if variable in nodes:
            nodes[variable]["caption"] = _decode_csharp_string(match.group("caption"))
    for match in CONTAINER_TEXT_RE.finditer(initializer):
        variable = match.group("variable")
        if variable in nodes:
            nodes[variable]["caption"] = _decode_csharp_string(match.group("caption"))
    for match in WINFORMS_TEXT_RE.finditer(initializer):
        variable = match.group("variable")
        if variable in nodes:
            nodes[variable]["caption"] = _decode_csharp_string(match.group("caption"))
    for node in nodes.values():
        if not node["caption"]:
            node["caption"] = node["key"].replace("_", " ").strip()
    return nodes


def _relationships(initializer: str, nodes: dict[str, dict[str, str]]) -> tuple[dict[str, list[str]], dict[str, str]]:
    children: dict[str, list[str]] = defaultdict(list)
    manager_for_toolbar: dict[str, str] = {}
    for match in TOOL_CHILDREN_RE.finditer(initializer):
        parent = match.group("parent")
        if parent not in nodes:
            continue
        children[parent].extend(variable for variable in _variables(match.group("children")) if variable in nodes)
    for match in MANAGER_TOOLBARS_RE.finditer(initializer):
        for variable in _variables(match.group("children")):
            if variable in nodes:
                manager_for_toolbar[variable] = match.group("manager")
    for match in WINFORMS_CHILDREN_RE.finditer(initializer):
        parent = match.group("parent")
        if parent not in nodes:
            continue
        children[parent].extend(variable for variable in _variables(match.group("children")) if variable in nodes)
    return dict(children), manager_for_toolbar


def _paths(
    nodes: dict[str, dict[str, str]],
    children: dict[str, list[str]],
    manager_for_toolbar: dict[str, str],
) -> list[dict[str, Any]]:
    referenced = {child for values in children.values() for child in values}
    toolbar_roots = [
        variable
        for variable, node in nodes.items()
        if node["kind"]
        in {"UltraToolbar", "RibbonGroup", "ContextMenuStrip", "MenuStrip", "ToolStrip", "ToolStripDropDownButton"}
    ]
    popup_roots = [
        variable
        for variable, node in nodes.items()
        if node["kind"] == "PopupMenuTool" and variable not in referenced and children.get(variable)
    ]
    roots = toolbar_roots + popup_roots
    rows: list[dict[str, Any]] = []
    seen_paths: set[tuple[str, ...]] = set()

    def walk(variable: str, path: list[str], variables_path: list[str], stack: set[str], root: str) -> None:
        if variable in stack or variable not in nodes:
            return
        node = nodes[variable]
        label = node["caption"] or node["key"]
        next_path = [*path, label]
        next_variables = [*variables_path, variable]
        logical_path = tuple(part for part in next_path if part)
        if logical_path in seen_paths:
            return
        seen_paths.add(logical_path)
        rows.append(
            {
                "path": list(logical_path),
                "path_label": " > ".join(logical_path),
                "depth": len(logical_path),
                "key": node["key"],
                "caption": label,
                "kind": node["kind"],
                "is_menu": bool(children.get(variable)),
                "root_variable": root,
                "manager": manager_for_toolbar.get(root, "menu_contestuale" if root in popup_roots else ""),
                "source_variables": next_variables,
            }
        )
        for child in children.get(variable, []):
            walk(child, next_path, next_variables, {*stack, variable}, root)

    for root in roots:
        walk(root, [], [], set(), root)
    return sorted(rows, key=lambda item: (str(item["manager"]), str(item["path_label"]).casefold()))


def _source_surfaces(source_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_paths: list[dict[str, Any]] = []
    surfaces: list[dict[str, Any]] = []
    for path in sorted(source_root.rglob("*.cs")):
        source = _read_decompiled(path)
        if not any(
            marker in source
            for marker in (
                "PopupMenuTool",
                "UltraToolbar",
                "RibbonGroup",
                "ToolStripMenuItem",
                "ContextMenuStrip",
                "MenuStrip",
            )
        ):
            continue
        component = _component_source(source)
        nodes = _tool_nodes(component)
        if not nodes:
            continue
        children, managers = _relationships(component, nodes)
        rows = _paths(nodes, children, managers)
        if not rows:
            continue
        relative = path.relative_to(source_root).as_posix()
        surface = path.stem
        for row in rows:
            row["source_file"] = relative
            row["surface"] = surface
            row["surface_path"] = [surface, *row["path"]]
            row["surface_path_label"] = " > ".join(row["surface_path"])
        all_paths.extend(rows)
        surfaces.append(
            {
                "surface": surface,
                "source_file": relative,
                "declared_controls": len(nodes),
                "reachable_paths": len(rows),
                "menu_paths": sum(1 for row in rows if row["is_menu"]),
                "action_paths": sum(1 for row in rows if not row["is_menu"]),
            }
        )
    all_paths.sort(key=lambda item: (str(item["source_file"]), str(item["surface_path_label"]).casefold()))
    return all_paths, surfaces


def _interactive_controls(
    source_root: Path,
    menu_paths: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    menu_variables = {
        (str(row["source_file"]), str(variable))
        for row in menu_paths
        for variable in row.get("source_variables", [])
    }
    controls: list[dict[str, Any]] = []
    surfaces: list[dict[str, Any]] = []
    for path in sorted(source_root.rglob("*.cs")):
        source = _read_decompiled(path)
        matches = list(INTERACTIVE_EVENT_RE.finditer(source))
        if not matches:
            continue
        relative = path.relative_to(source_root).as_posix()
        surface = path.stem
        component = _component_source(source)
        captions: dict[str, str] = {}
        for regex in (WINFORMS_TEXT_RE, ACCESSIBLE_NAME_RE, TOOLTIP_RE):
            for match in regex.finditer(component):
                value = _decode_csharp_string(match.group("caption"))
                if value:
                    captions[match.group("variable")] = value
        seen: set[tuple[str, str, str]] = set()
        surface_rows = 0
        for match in matches:
            variable = match.group("variable")
            if (relative, variable) in menu_variables:
                continue
            event = match.group("event")
            handler = match.group("handler")
            signature = (variable, event, handler)
            if signature in seen:
                continue
            seen.add(signature)
            caption = captions.get(variable) or variable.replace("_", " ").strip()
            controls.append(
                {
                    "surface": surface,
                    "source_file": relative,
                    "variable": variable,
                    "event": event,
                    "handler": handler,
                    "caption": caption,
                    "surface_path": [surface, caption],
                    "surface_path_label": f"{surface} > {caption}",
                }
            )
            surface_rows += 1
        if surface_rows:
            surfaces.append(
                {
                    "surface": surface,
                    "source_file": relative,
                    "interactive_controls": surface_rows,
                }
            )
    controls.sort(
        key=lambda item: (
            str(item["source_file"]),
            str(item["surface_path_label"]).casefold(),
            str(item["event"]),
        )
    )
    return controls, surfaces


def _practice_table(source_root: Path, form_main: str) -> dict[str, Any]:
    adapter_path = _source_file(
        source_root,
        "QuickOrganizer.QuickOrganizerDataSetTableAdapters/PRATICHETableAdapter.cs",
    )
    adapter = _read_decompiled(adapter_path)
    match = PRATICHE_SELECT_RE.search(adapter)
    columns = []
    if match:
        columns = [column.strip().strip("[]") for column in match.group("columns").replace("\n", " ").split(",")]
    filters = []
    for item in FILTER_METHOD_RE.finditer(form_main):
        body = item.group("body")
        label_match = FILTER_LABEL_RE.search(body)
        field_match = FILTER_FIELD_RE.search(body)
        if not label_match or not field_match:
            continue
        filters.append(
            {
                "command": f"FiltraRubricaPer_{item.group('name')}",
                "label": _decode_csharp_string(label_match.group("label")).rstrip(":"),
                "field": field_match.group("field"),
            }
        )
    return {
        "table": "PRATICHE",
        "columns": columns,
        "column_count": len(columns),
        "filters": filters,
        "filter_count": len(filters),
        "supports_combined_filters": "text += \" AND \"" in form_main,
        "supports_active_and_archived": all(value in form_main for value in ("Pratiche_Attive", "Pratiche_Archiviate")),
        "supports_groups": all(value in form_main for value in ("NomeGruppo", "Filtra_Pratiche_Per_Gruppo", "Faldoni")),
        "supports_multi_sort": "HeaderClickAction.SortMulti" in form_main,
        "supports_group_by_column": "GroupByBox.Prompt" in form_main,
        "supports_variable_row_height": "Righe ad altezza variabile" in form_main,
        "supports_fixed_row_height": "Righe ad altezza fissa" in form_main,
    }


def build_audit(source_root: Path) -> dict[str, Any]:
    form_path = _source_file(source_root, "QuickOrganizer/FormMain.cs")
    form_main = _read_decompiled(form_path)
    paths, surfaces = _source_surfaces(source_root)
    interactive_controls, interactive_surfaces = _interactive_controls(source_root, paths)
    leaf_paths = [row for row in paths if not row["is_menu"]]
    menu_paths = [row for row in paths if row["is_menu"]]
    manager_counts = Counter(str(row["manager"] or "non_associato") for row in leaf_paths)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds"),
        "source": {
            "path": str(source_root),
            "form_main": str(form_path),
            "form_main_sha256": hashlib.sha256(form_path.read_bytes()).hexdigest(),
        },
        "counts": {
            "source_surfaces": len(surfaces),
            "declared_tool_instances": sum(int(surface["declared_controls"]) for surface in surfaces),
            "reachable_paths": len(paths),
            "menu_paths": len(menu_paths),
            "action_paths": len(leaf_paths),
            "unique_action_keys": len({str(row["key"]) for row in leaf_paths}),
            "toolbar_roots": len({str(row["root_variable"]) for row in paths}),
            "interactive_surfaces": len(interactive_surfaces),
            "interactive_controls": len(interactive_controls),
            "functional_entries": len(leaf_paths) + len(interactive_controls),
        },
        "action_paths_by_manager": dict(sorted(manager_counts.items())),
        "surfaces": surfaces,
        "interactive_surfaces": interactive_surfaces,
        "practice_registry": _practice_table(source_root, form_main),
        "menu_paths": menu_paths,
        "action_paths": leaf_paths,
        "interactive_controls": interactive_controls,
        "scope_note": (
            "L'albero conserva il percorso raggiungibile dichiarato in InitializeComponent, incluse barre e menu contestuali, "
            "e censisce separatamente i controlli associati a eventi cliccabili nelle altre finestre. "
            "La parita IUSENTRA va attestata separatamente per ciascuna azione con dati, API, interfaccia e prova reale."
        ),
    }


def _markdown(audit: dict[str, Any]) -> str:
    counts = audit["counts"]
    practice = audit["practice_registry"]
    lines = [
        "# Audit gerarchico menu e funzioni",
        "",
        f"Generato: {audit['generated_at']} (Europe/Rome).",
        "",
        "## Perimetro estratto",
        "",
        f"- Superfici sorgente con menu o barre: {counts['source_surfaces']}",
        f"- Istanze di controllo dichiarate: {counts['declared_tool_instances']}",
        f"- Percorsi raggiungibili: {counts['reachable_paths']}",
        f"- Percorsi menu: {counts['menu_paths']}",
        f"- Percorsi azione: {counts['action_paths']}",
        f"- Azioni distinte per chiave: {counts['unique_action_keys']}",
        f"- Finestre con controlli cliccabili: {counts['interactive_surfaces']}",
        f"- Controlli cliccabili fuori dai menu: {counts['interactive_controls']}",
        f"- Voci funzionali complessive censite: {counts['functional_entries']}",
        "",
        "## Rubrica pratiche",
        "",
        f"- Campi tabella PRATICHE: {practice['column_count']}",
        f"- Filtri combinabili rilevati: {practice['filter_count']}",
        f"- Pratiche attive e archiviate: {'si' if practice['supports_active_and_archived'] else 'no'}",
        f"- Gruppi di fascicoli: {'si' if practice['supports_groups'] else 'no'}",
        f"- Ordinamento multiplo: {'si' if practice['supports_multi_sort'] else 'no'}",
        f"- Raggruppamento per colonna: {'si' if practice['supports_group_by_column'] else 'no'}",
        f"- Altezza righe fissa e variabile: {'si' if practice['supports_fixed_row_height'] and practice['supports_variable_row_height'] else 'no'}",
        "",
        "### Campi",
        "",
        ", ".join(f"`{column}`" for column in practice["columns"]),
        "",
        "### Filtri",
        "",
    ]
    lines.extend(f"- {item['label']}: `{item['field']}`" for item in practice["filters"])
    lines.extend(["", "## Albero menu", ""])
    current_surface = None
    current_manager = None
    for row in audit["action_paths"]:
        surface = row["surface"]
        if surface != current_surface:
            lines.extend([f"### {surface}", "", f"Sorgente: `{row['source_file']}`", ""])
            current_surface = surface
            current_manager = None
        manager = row["manager"] or "non_associato"
        if manager != current_manager:
            lines.extend([f"#### {manager}", ""])
            current_manager = manager
        lines.append(f"- `{row['key']}`: {row['surface_path_label']}")
    lines.extend(["", "## Controlli delle finestre", ""])
    current_surface = None
    for row in audit["interactive_controls"]:
        if row["surface"] != current_surface:
            lines.extend([f"### {row['surface']}", "", f"Sorgente: `{row['source_file']}`", ""])
            current_surface = row["surface"]
        lines.append(
            f"- `{row['variable']}.{row['event']} -> {row['handler']}`: {row['surface_path_label']}"
        )
    lines.extend(["", "## Nota di verifica", "", audit["scope_note"], ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Estrae l'albero completo di menu e funzioni")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    audit = build_audit(args.source)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(_markdown(audit), encoding="utf-8")
    print(json.dumps(audit["counts"], ensure_ascii=False))
    print(json.dumps({"practice_registry": audit["practice_registry"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
