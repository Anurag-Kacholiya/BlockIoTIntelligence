"""Final task 2 client pieces that need no running chain: QBFT genesis, local signing, cross-node reads, roles."""

import pytest
from eth_account import Account

from src.common.blockchain import Chain, LocalSigner, ReadMark
from src.common.qbft import QBFT_MIX_HASH, genesis_config
from src.pipeline import node_roles

ANVIL_ACCOUNT_0 = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"   # Anvil's first dev account (same mnemonic)


def test_qbft_genesis():
    accounts = LocalSigner().addresses
    cfg = genesis_config(4, 2, accounts)
    chain = cfg["genesis"]["config"]
    assert chain["qbft"]["blockperiodseconds"] == 2 and chain["qbft"]["requesttimeoutseconds"] == 4
    # the contract is compiled for Cancun (PUSH0 etc.): every fork up to it is active from genesis
    assert chain["shanghaiTime"] == 0 and chain["cancunTime"] == 0 and chain["londonBlock"] == 0
    assert chain["zeroBaseFee"] is True and chain["chainId"] == 1337
    assert cfg["genesis"]["mixHash"] == QBFT_MIX_HASH and int(cfg["genesis"]["gasLimit"], 16) == 300_000_000
    assert set(cfg["genesis"]["alloc"]) == set(accounts) and len(accounts) == 20
    assert cfg["blockchain"]["nodes"] == {"generate": True, "count": 4}


class _FakeEth:
    def __init__(self, counts=None, heads=()):
        self.counts, self.heads, self.head_calls = counts or {}, list(heads), 0

    def get_transaction_count(self, address, block):
        assert block == "pending"
        return self.counts.get(address, 0)

    @property
    def block_number(self):
        self.head_calls += 1
        return self.heads.pop(0) if len(self.heads) > 1 else self.heads[0]


class _FakeW3:
    def __init__(self, **kw):
        self.eth = _FakeEth(**kw)


def test_local_signer_uses_anvil_accounts_and_counts_nonces_per_sender():
    signer = LocalSigner()
    a, b = signer.addresses[:2]
    assert a == ANVIL_ACCOUNT_0
    w3 = _FakeW3(counts={a: 5, b: 0})
    txs = [{"from": s, "to": b, "data": b"", "gas": 21_000, "gasPrice": 0, "chainId": 1337} for s in (a, a, b, a)]
    raws = [signer.sign(w3, tx) for tx in txs]
    assert [tx["nonce"] for tx in txs] == [5, 6, 0, 7]        # starts at the node's pending count, then counts locally
    assert [Account.recover_transaction(r) for r in raws] == [a, a, b, a]


def _chain_on(heads, mark_block, head=0):
    chain = Chain.__new__(Chain)                          # no RPC endpoint needed for the sync logic
    chain.url, chain.w3, chain.mark, chain._head = "fake", _FakeW3(heads=heads), ReadMark(), head
    chain.mark.advance(mark_block)
    return chain


def test_read_waits_until_the_node_has_every_confirmed_write():
    chain = _chain_on(heads=[7, 8, 9], mark_block=9)
    chain._sync()
    assert chain._head == 9 and chain.w3.eth.head_calls == 3


def test_read_needs_no_rpc_when_the_node_is_known_to_be_current():
    chain = _chain_on(heads=[1], mark_block=4, head=4)    # e.g. the write was confirmed through this node
    chain._sync()
    assert chain.w3.eth.head_calls == 0


def test_read_times_out_on_a_stuck_node():
    with pytest.raises(TimeoutError):
        _chain_on(heads=[3], mark_block=4)._sync(timeout=0.05)


def test_roles_spread_over_nodes():
    assert node_roles(4, ["edge-00", "edge-01"], ["fog-00"]) == {
        "device_gateway": 0, "edge-00": 1, "edge-01": 2, "fog-00": 3, "cloud": 0}
    assert set(node_roles(1, ["edge-00", "edge-01"], ["fog-00"]).values()) == {0}
