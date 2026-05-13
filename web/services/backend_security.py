"""Guardrail backend per endpoint React/API.

La fase 5 blocca parametri che provano a scegliere contesto studio, tenant,
token generici o redirect liberi dal client. I flussi amministrativi restano
governati dai permessi dominio, percio' campi come ``ruolo`` o
``extraPermissions`` non sono filtrati qui.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from flask import jsonify


MAX_SECURITY_VIOLATIONS = 16
MAX_COLLECTION_ITEMS = 40


UNSAFE_BACKEND_CONTROL_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "authorization",
        "data_root",
        "dataroot",
        "id_token",
        "is_admin",
        "isadmin",
        "next",
        "redirect",
        "refresh_token",
        "return_url",
        "returnurl",
        "root_path",
        "rootpath",
        "studio",
        "studio_id",
        "studio_slug",
        "studioid",
        "studioslug",
        "superadmin",
        "tenant",
        "tenant_id",
        "tenant_slug",
        "tenantid",
        "tenantslug",
        "token",
        "user_id",
        "userid",
    }
)


@dataclass(frozen=True)
class BackendSecurityViolation:
    source: str
    key: str
    path: str

    def to_payload(self) -> dict[str, str]:
        return {"source": self.source, "key": self.key, "path": self.path}


def normalise_control_key(key: Any) -> str:
    return str(key or "").strip().lower().replace("-", "_")


def is_unsafe_backend_control_key(key: Any) -> bool:
    return normalise_control_key(key) in UNSAFE_BACKEND_CONTROL_KEYS


def collect_backend_control_violations(
    value: Any,
    *,
    source: str,
    prefix: str = "",
    limit: int = MAX_SECURITY_VIOLATIONS,
) -> list[BackendSecurityViolation]:
    violations: list[BackendSecurityViolation] = []

    def visit(node: Any, path: str) -> None:
        if len(violations) >= limit:
            return
        if isinstance(node, Mapping):
            for raw_key, raw_value in node.items():
                key = str(raw_key)
                child_path = f"{path}.{key}" if path else key
                if is_unsafe_backend_control_key(key):
                    violations.append(BackendSecurityViolation(source=source, key=normalise_control_key(key), path=child_path))
                    if len(violations) >= limit:
                        return
                visit(raw_value, child_path)
                if len(violations) >= limit:
                    return
        elif isinstance(node, (list, tuple)):
            for index, item in enumerate(node[:MAX_COLLECTION_ITEMS]):
                visit(item, f"{path}[{index}]")
                if len(violations) >= limit:
                    return

    visit(value, prefix)
    return violations


def backend_control_violations_for_request(req: Any) -> list[BackendSecurityViolation]:
    violations: list[BackendSecurityViolation] = []
    args = getattr(req, "args", None)
    if args is not None:
        query_payload = {key: True for key in args.keys()}
        violations.extend(collect_backend_control_violations(query_payload, source="query"))

    if len(violations) >= MAX_SECURITY_VIOLATIONS:
        return violations[:MAX_SECURITY_VIOLATIONS]

    if getattr(req, "is_json", False):
        body = req.get_json(silent=True)
        if isinstance(body, (dict, list)):
            violations.extend(
                collect_backend_control_violations(
                    body,
                    source="json",
                    limit=MAX_SECURITY_VIOLATIONS - len(violations),
                )
            )
    else:
        form = getattr(req, "form", None)
        if form is not None:
            form_payload = {key: True for key in form.keys()}
            violations.extend(
                collect_backend_control_violations(
                    form_payload,
                    source="form",
                    limit=MAX_SECURITY_VIOLATIONS - len(violations),
                )
            )

    return violations[:MAX_SECURITY_VIOLATIONS]


def backend_security_error_payload(violations: Iterable[BackendSecurityViolation]) -> dict[str, Any]:
    return {
        "ok": False,
        "message": "Richiesta non consentita.",
        "errors": {
            "security": (
                "La richiesta contiene parametri riservati al controllo server. "
                "Rimuovili e ripeti l'operazione."
            )
        },
        "code": "backend_security_control_param",
        "violations": [violation.to_payload() for violation in violations],
    }


def backend_security_error_response(violations: Iterable[BackendSecurityViolation]):
    return jsonify(backend_security_error_payload(violations)), 400
