from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exercised by CLI failures
        raise SystemExit(f"OpenAPI non leggibile: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("OpenAPI non e' un oggetto YAML.")
    return payload


def _resolve_ref(document: dict[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise AssertionError(f"Ref esterno non ammesso in questa fase: {ref}")
    current: Any = document
    for part in ref[2:].split("/"):
        if not isinstance(current, dict) or part not in current:
            raise AssertionError(f"Ref mancante: {ref}")
        current = current[part]
    return current


def _walk_refs(value: Any):
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            yield ref
        for child in value.values():
            yield from _walk_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_refs(child)


def validate(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if document.get("openapi") != "3.0.3":
        errors.append("openapi deve essere 3.0.3.")
    for key in ("info", "paths", "components"):
        if key not in document:
            errors.append(f"chiave obbligatoria mancante: {key}.")
    paths = document.get("paths")
    components = document.get("components")
    if not isinstance(paths, dict) or not paths:
        errors.append("paths vuoto o non valido.")
        return errors
    if not isinstance(components, dict):
        errors.append("components non valido.")
        return errors
    if "ErrorResponse" not in ((components.get("schemas") or {}) if isinstance(components.get("schemas"), dict) else {}):
        errors.append("components.schemas.ErrorResponse mancante.")

    for ref in _walk_refs(document):
        try:
            _resolve_ref(document, ref)
        except AssertionError as exc:
            errors.append(str(exc))

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            errors.append(f"{path}: path item non valido.")
            continue
        expected_params = set(re.findall(r"{([^}]+)}", path))
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete", "options"}:
                continue
            if not isinstance(operation, dict):
                errors.append(f"{method.upper()} {path}: operation non valida.")
                continue
            responses = operation.get("responses")
            if not isinstance(responses, dict) or "401" not in responses or "200" not in responses:
                errors.append(f"{method.upper()} {path}: responses 200/401 obbligatorie.")
            if "security" not in operation:
                errors.append(f"{method.upper()} {path}: security mancante.")
            for extension in ("x-rbac-permission", "x-tenant-scope", "x-priority", "x-provider-verification"):
                if extension not in operation:
                    errors.append(f"{method.upper()} {path}: {extension} mancante.")
            declared = {
                param.get("name")
                for param in operation.get("parameters", [])
                if isinstance(param, dict) and param.get("in") == "path"
            }
            missing_params = expected_params - declared
            if missing_params:
                errors.append(f"{method.upper()} {path}: path params non dichiarati: {sorted(missing_params)}.")
            if operation.get("x-priority") in {"P0", "P1"}:
                status = operation.get("x-contract-status")
                if status not in {"complete", "verified"}:
                    errors.append(f"{method.upper()} {path}: P0/P1 senza contratto complete/verified.")
                for status_code in ("400", "403", "404", "422"):
                    if status_code not in (responses or {}):
                        errors.append(f"{method.upper()} {path}: errore {status_code} non documentato.")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida la struttura OpenAPI IUSENTRA.")
    parser.add_argument("path", nargs="?", default="docs/openapi.yaml")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    document = _load(path)
    errors = validate(document)
    if errors:
        for error in errors:
            print(f"ERRORE | {error}", file=sys.stderr)
        return 1
    print(f"OK | OpenAPI valido | {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
