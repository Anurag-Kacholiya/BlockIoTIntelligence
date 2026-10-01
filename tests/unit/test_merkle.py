import pytest

from src.common import merkle


@pytest.mark.parametrize("n", [1, 2, 3, 7, 8, 33])
def test_every_leaf_proves_into_the_root(n):
    items = [bytes([i]) * 32 for i in range(n)]
    root, proofs = merkle.build(items)
    assert all(merkle.root_from_proof(x, p) == root for x, p in zip(items, proofs, strict=True))


def test_modified_leaf_does_not_prove():
    items = [bytes([i]) * 32 for i in range(5)]
    root, proofs = merkle.build(items)
    assert merkle.root_from_proof(b"\xff" * 32, proofs[2]) != root
