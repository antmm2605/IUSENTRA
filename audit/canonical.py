"""RFC 8785 JSON Canonicalization Scheme helpers.

The serializer intentionally rejects values that are not stable enough for a
forensic signature. Event payloads should be made from dict/list/str/int/bool
and null; finite floats are supported only when unavoidable.
"""

from __future__ import annotations

import json
import math
from decimal import Decimal
from typing import Any

from .exceptions import AuditValidationError


CANONICALIZATION = "RFC8785-JCS"


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _float_to_jcs(value: float) -> str:
    if not math.isfinite(value):
        raise AuditValidationError("Numeri non finiti non ammessi nel payload audit.")
    if value == 0:
        return "0"
    if value.is_integer() and abs(value) <= 9007199254740991:
        return str(int(value))
    rendered = format(value, ".15g")
    if "E" in rendered:
        rendered = rendered.replace("E", "e")
    if "e" in rendered:
        mantissa, exponent = rendered.split("e", 1)
        sign = ""
        if exponent.startswith(("+", "-")):
            sign, exponent = exponent[:1], exponent[1:]
        exponent = exponent.lstrip("0") or "0"
        rendered = f"{mantissa}e{sign if sign == '-' else ''}{exponent}"
    return rendered


def _canonical(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return _float_to_jcs(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise AuditValidationError("Decimal non finito non ammesso nel payload audit.")
        return _float_to_jcs(float(value)) if value % 1 else str(int(value))
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        rendered: list[str] = []
        for key in sorted(value.keys(), key=lambda item: str(item)):
            if not isinstance(key, str):
                raise AuditValidationError("Le chiavi JSON canoniche devono essere stringhe.")
            raw = value[key]
            if raw is _UNSET:
                continue
            rendered.append(_quote(key) + ":" + _canonical(raw))
        return "{" + ",".join(rendered) + "}"
    raise AuditValidationError(f"Tipo non serializzabile in audit canonico: {type(value).__name__}.")


class _Unset:
    pass


_UNSET = _Unset()


def canonicalize(value: Any) -> bytes:
    """Return UTF-8 JCS canonical JSON bytes."""

    return _canonical(value).encode("utf-8")


def canonical_text(value: Any) -> str:
    return canonicalize(value).decode("utf-8")
