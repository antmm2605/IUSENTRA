"""Merkle tree with explicit domain separation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .exceptions import AuditValidationError
from .hashing import is_sha256_hex

MERKLE_ALG = "SHA-256/domain-separated/duplicate-last"


@dataclass(frozen=True)
class ProofStep:
    side: str
    hash: str

    def to_dict(self) -> dict[str, str]:
        return {"side": self.side, "hash": self.hash}


@dataclass(frozen=True)
class MerkleTree:
    leaves: tuple[str, ...]
    levels: tuple[tuple[bytes, ...], ...]

    @property
    def root(self) -> str:
        if not self.levels:
            return hashlib.sha256(b"empty:audit-merkle").hexdigest()
        return self.levels[-1][0].hex()


def _hash(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _hash_bytes_from_hex(value: str) -> bytes:
    if not is_sha256_hex(value):
        raise AuditValidationError("Event hash non valido per Merkle tree.")
    return bytes.fromhex(value)


def merkle_leaf(event_hash: str) -> bytes:
    return _hash(b"leaf:" + _hash_bytes_from_hex(event_hash))


def build_merkle_tree(event_hashes: list[str] | tuple[str, ...]) -> MerkleTree:
    leaves_hex = tuple(str(value).lower() for value in event_hashes)
    if not leaves_hex:
        return MerkleTree((), ())
    current = tuple(merkle_leaf(value) for value in leaves_hex)
    levels: list[tuple[bytes, ...]] = [current]
    while len(current) > 1:
        nodes: list[bytes] = []
        for index in range(0, len(current), 2):
            left = current[index]
            right = current[index + 1] if index + 1 < len(current) else left
            nodes.append(_hash(b"node:" + left + right))
        current = tuple(nodes)
        levels.append(current)
    return MerkleTree(leaves_hex, tuple(levels))


def merkle_root(event_hashes: list[str] | tuple[str, ...]) -> str:
    return build_merkle_tree(event_hashes).root


def merkle_proof(event_hash: str, event_hashes: list[str] | tuple[str, ...]) -> list[ProofStep]:
    wanted = str(event_hash or "").lower()
    tree = build_merkle_tree(event_hashes)
    try:
        index = tree.leaves.index(wanted)
    except ValueError as exc:
        raise AuditValidationError("Evento non presente nello snapshot Merkle.") from exc
    proof: list[ProofStep] = []
    for level in tree.levels[:-1]:
        sibling_index = index ^ 1
        if sibling_index >= len(level):
            sibling_index = index
        side = "left" if sibling_index < index else "right"
        proof.append(ProofStep(side=side, hash=level[sibling_index].hex()))
        index //= 2
    return proof


def verify_merkle_proof(event_hash: str, proof: list[ProofStep] | list[dict[str, str]], root: str) -> bool:
    try:
        current = merkle_leaf(event_hash)
        for raw_step in proof:
            step = raw_step if isinstance(raw_step, ProofStep) else ProofStep(str(raw_step.get("side", "")), str(raw_step.get("hash", "")))
            sibling = bytes.fromhex(step.hash)
            if step.side == "left":
                current = _hash(b"node:" + sibling + current)
            elif step.side == "right":
                current = _hash(b"node:" + current + sibling)
            else:
                return False
        return current.hex() == str(root or "").lower()
    except Exception:
        return False
