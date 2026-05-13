from __future__ import annotations

from audit.hashing import sha256_bytes, sha256_canonical, sha256_file


def test_same_payload_with_different_key_order_has_same_probative_hash() -> None:
    assert sha256_canonical({"b": 2, "a": 1}) == sha256_canonical({"a": 1, "b": 2})


def test_payload_change_changes_hash() -> None:
    assert sha256_canonical({"a": 1}) != sha256_canonical({"a": 2})


def test_file_hash_uses_real_binary_content(tmp_path) -> None:
    path = tmp_path / "atto.bin"
    path.write_bytes(b"contenuto reale")
    assert sha256_file(path) == sha256_bytes(b"contenuto reale")
