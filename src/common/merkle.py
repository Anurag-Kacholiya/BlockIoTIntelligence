"""Binary SHA-256 Merkle tree for batch commitments: one on-chain root, per-event inclusion proofs."""

from __future__ import annotations

import hashlib


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _parent(left: bytes, right: bytes) -> bytes:
    return _h(b"\x01" + left + right)   # domain-separate inner nodes from leaves


def leaf(item: bytes) -> bytes:
    return _h(b"\x00" + item)


def build(items: list[bytes]) -> tuple[bytes, list[list[tuple[bytes, bool]]]]:
    """Return (root, proofs). proofs[i] is a list of (sibling, sibling_is_right) from leaf to root.
    An odd node at any level is paired with itself."""
    if not items:
        raise ValueError("empty batch")
    level = [leaf(x) for x in items]
    positions = list(range(len(items)))
    proofs: list[list[tuple[bytes, bool]]] = [[] for _ in items]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        for i, pos in enumerate(positions):
            sibling = pos ^ 1
            proofs[i].append((level[sibling], sibling > pos))
            positions[i] = pos // 2
        level = [_parent(level[j], level[j + 1]) for j in range(0, len(level), 2)]
    return level[0], proofs


def root_from_proof(item: bytes, proof: list[tuple[bytes, bool]]) -> bytes:
    node = leaf(item)
    for sibling, sibling_is_right in proof:
        node = _parent(node, sibling) if sibling_is_right else _parent(sibling, node)
    return node
