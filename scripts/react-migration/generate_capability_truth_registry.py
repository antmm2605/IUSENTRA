#!/usr/bin/env python3
"""Genera gli artefatti leggibili del Capability Truth Registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = REPOSITORY_ROOT / "artifacts" / "product-readiness"
OUTPUTS = {
    "catalogue": ARTIFACTS_DIR / "capability-truth-registry.json",
    "register": ARTIFACTS_DIR / "capability-truth-registry.md",
    "matrix": ARTIFACTS_DIR / "capability-truth-release-matrix.md",
    "changelog": ARTIFACTS_DIR / "capability-truth-changelog.md",
}

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from pct.capability_truth_registry import registry_catalogue_for_generation  # noqa: E402


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("|", "\\|").strip() or "n.d."


def _table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    header_values = list(headers)
    result = [
        "| " + " | ".join(_md(item) for item in header_values) + " |",
        "| " + " | ".join("---" for _ in header_values) + " |",
    ]
    result.extend("| " + " | ".join(_md(item) for item in row) + " |" for row in rows)
    return "\n".join(result)


def _render_register(payload: dict[str, Any]) -> str:
    entries = list(payload.get("capabilities") or [])
    sections = [
        "# Capability Truth Registry — P0",
        "",
        f"Versione registro: `{_md(payload.get('registryVersion'))}`. Fonte autorevole: catalogo Python versionato.",
        "",
        "Questo documento non attesta che una capability sia completa. Una prova non eseguita resta visibile come tale.",
        "",
        "## Riepilogo",
        "",
        _table(
            ("Capability", "Stato", "Owner", "Route", "API", "Storage", "Ultimo smoke"),
            (
                (
                    item.get("module"),
                    item.get("statusLabel"),
                    item.get("owner"),
                    item.get("route"),
                    item.get("api"),
                    item.get("storage"),
                    (item.get("lastSmoke") or {}).get("label"),
                )
                for item in entries
            ),
        ),
    ]
    for item in entries:
        evidence = list(item.get("evidence") or [])
        sections.extend(
            [
                "",
                f"## {item.get('module')}",
                "",
                _table(
                    ("Campo", "Valore"),
                    (
                        ("Stato", f"{item.get('statusLabel')} — {item.get('statusNote')}"),
                        ("Versione", item.get("version")),
                        ("Owner", item.get("owner")),
                        ("Feature flag", item.get("featureFlag")),
                        ("Route", item.get("route")),
                        ("API", item.get("api")),
                        ("Backend", item.get("backend")),
                        ("Operazioni", ", ".join(item.get("operations") or [])),
                        ("Permessi", ", ".join(item.get("permissions") or [])),
                        ("Storage", item.get("storage")),
                        ("Ambiente locale", (item.get("environment") or {}).get("local")),
                        ("Produzione", (item.get("environment") or {}).get("production")),
                        ("Dipendenze", ", ".join(item.get("dependencies") or [])),
                        ("Limitazioni", item.get("limitations")),
                        ("Rollback", item.get("rollback")),
                        ("Incidenti", (item.get("incidents") or {}).get("label")),
                        ("Prossima azione", item.get("nextAction")),
                        ("Test associati", ", ".join(item.get("tests") or [])),
                    ),
                ),
                "",
                _table(
                    ("Prova", "Stato", "Riferimento", "Nota"),
                    ((row.get("label"), row.get("status"), row.get("reference"), row.get("note")) for row in evidence),
                ),
            ]
        )
    return "\n".join(sections) + "\n"


def _render_matrix(payload: dict[str, Any]) -> str:
    entries = list(payload.get("capabilities") or [])
    return "\n".join(
        [
            "# Matrice di release — Capability Truth P0",
            "",
            "La matrice è generata dal catalogo e non autorizza una release operativa quando una prova obbligatoria è assente.",
            "",
            _table(
                ("Capability", "Stato", "CI", "Browser", "Provider", "Azione richiesta"),
                (
                    (
                        item.get("module"),
                        item.get("statusLabel"),
                        next((row.get("status") for row in item.get("evidence") or [] if row.get("kind") == "ci"), "n.d."),
                        next((row.get("status") for row in item.get("evidence") or [] if row.get("kind") == "browser"), "n.d."),
                        next((row.get("status") for row in item.get("evidence") or [] if row.get("kind") == "provider"), "n.d."),
                        item.get("nextAction"),
                    )
                    for item in entries
                ),
            ),
            "",
        ]
    )


def _render_changelog(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary") or {})
    return "\n".join(
        [
            "# Changelog Capability Truth Registry",
            "",
            f"## {payload.get('registryVersion')} — 23/08/2026",
            "",
            f"- Censite {summary.get('total', 0)} capability P0 richieste.",
            f"- Capability verificate: {summary.get('verified', 0)}; da verificare: {summary.get('pending', 0)}.",
            "- Aggiunti contratto API read-only, matrice di release e azione menu generata.",
            "- Nessun provider, incidente o smoke mancante è rappresentato come positivo.",
            "",
        ]
    )


def render_outputs() -> dict[Path, str]:
    payload = registry_catalogue_for_generation()
    return {
        OUTPUTS["catalogue"]: json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        OUTPUTS["register"]: _render_register(payload),
        OUTPUTS["matrix"]: _render_matrix(payload),
        OUTPUTS["changelog"]: _render_changelog(payload),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fallisce se un artefatto generato non è aggiornato")
    args = parser.parse_args(argv)
    rendered = render_outputs()
    outdated = [path for path, content in rendered.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
    if args.check:
        if outdated:
            print("Artefatti Capability Truth Registry non aggiornati:")
            for path in outdated:
                print(f"- {path.relative_to(REPOSITORY_ROOT).as_posix()}")
            return 1
        print("Artefatti Capability Truth Registry aggiornati.")
        return 0
    for path in outdated:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered[path], encoding="utf-8")
        print(f"Aggiornato {path.relative_to(REPOSITORY_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
