from __future__ import annotations

from audit.hashing import sha256_bytes
from audit.merkle import build_merkle_tree, merkle_proof, merkle_root, verify_merkle_proof


def test_merkle_root_and_proof_roundtrip() -> None:
    hashes = [sha256_bytes(f"event-{index}".encode("ascii")) for index in range(5)]
    root = merkle_root(hashes)
    proof = merkle_proof(hashes[2], hashes)
    assert root == build_merkle_tree(hashes).root
    assert verify_merkle_proof(hashes[2], proof, root)


def test_merkle_proof_detects_wrong_event() -> None:
    hashes = [sha256_bytes(f"event-{index}".encode("ascii")) for index in range(3)]
    proof = merkle_proof(hashes[0], hashes)
    assert not verify_merkle_proof(sha256_bytes(b"other"), proof, merkle_root(hashes))
