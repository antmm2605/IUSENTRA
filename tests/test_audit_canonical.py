from __future__ import annotations

import pytest

from audit.canonical import canonical_text, canonicalize
from audit.exceptions import AuditValidationError


def test_canonicalization_is_stable_for_key_order() -> None:
    left = {"b": 2, "a": {"d": True, "c": None}}
    right = {"a": {"c": None, "d": True}, "b": 2}
    assert canonicalize(left) == canonicalize(right)
    assert canonical_text(left) == '{"a":{"c":null,"d":true},"b":2}'


def test_canonicalization_rejects_non_string_keys() -> None:
    with pytest.raises(AuditValidationError):
        canonicalize({1: "not-jcs"})


def test_canonicalization_rejects_non_finite_numbers() -> None:
    with pytest.raises(AuditValidationError):
        canonicalize({"value": float("nan")})
