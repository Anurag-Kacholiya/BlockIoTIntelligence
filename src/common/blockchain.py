"""EVM adapter: local Anvil node lifecycle, contract deployment, timed transactions with gas accounting (ADR §6).

Every transaction's submit->receipt latency and gas are recorded per `kind`, which is what the
baseline-vs-blockchain experiments report as L_blockchain (ADR Phase 8) and gas overhead.

Multi-node networks (final task 2, `src/common/qbft.py`) use one `Chain` per node endpoint, created by `connect`:
they share the transaction statistics, the local signer (Besu keeps no unlocked accounts) and a read-your-writes
mark, so a read on one node sees every write already confirmed through any other node.
"""

from __future__ import annotations

import json
import queue
import socket
import subprocess
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np
import psutil
from eth_account import Account
from web3 import Web3

from src.common.config import ROOT, load_config

ANVIL = ROOT / "tools" / "foundry" / "anvil"
FORGE = ROOT / "tools" / "foundry" / "forge"
SOLC = ROOT / "tools" / "solc" / "solc-0.8.24"
ARTIFACT = ROOT / "blockchain" / "artifacts" / "IoTRegistry.sol" / "IoTRegistry.json"


def h32(digest: str) -> bytes:
    """'sha256:<hex>' -> 32 raw bytes for a bytes32 argument."""
    return bytes.fromhex(digest.removeprefix("sha256:"))


def id32(text: str) -> bytes:
    """Stable bytes32 identifier for a string id (event, device, model, alert)."""
    return Web3.keccak(text=text)


def compile_contract() -> dict:
    if not ARTIFACT.exists():
        subprocess.run([str(FORGE), "build", "--root", str(ROOT / "blockchain"), "--offline", "--use", str(SOLC)],
                       check=True, capture_output=True)
    return json.loads(ARTIFACT.read_text())


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def local_node(block_time: float | None = None, accounts: int = 20):
    """Start a private Anvil chain for one experiment and stop it afterwards. Yields (rpc_url, process)."""
    if not ANVIL.exists():
        raise FileNotFoundError(f"{ANVIL} missing — see README (Blockchain setup)")
    port = free_port()
    args = [str(ANVIL), "--port", str(port), "--accounts", str(accounts), "--silent",
            "--gas-limit", "300000000", "--chain-id", str(load_config("blockchain")["network"]["chain_id"]),
            # Automine makes one block per transaction; without pruning, Anvil slows ~10x once it holds
            # tens of thousands of blocks, which would measure the dev node rather than the architecture.
            "--prune-history", "256", "--transaction-block-keeper", "4096"]
    if block_time:
        args += ["--block-time", str(block_time)]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(200):
            try:
                if Web3(Web3.HTTPProvider(url)).is_connected():
                    break
            except Exception:
                pass
            time.sleep(0.05)
        else:
            raise RuntimeError("anvil did not start")
        yield url, proc
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@dataclass
class TxStats:
    gas: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    latency_ms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    failed: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    calls: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, kind: str, receipt, latency_ms: float) -> None:
        with self.lock:                   # background receipt watchers record concurrently
            self.latency_ms[kind].append(latency_ms)
            if receipt.status == 1:
                self.gas[kind].append(receipt.gasUsed)
            else:
                self.failed[kind] += 1

    def summary(self) -> dict[str, dict]:
        out = {}
        for kind in sorted(set(self.gas) | set(self.calls) | set(self.failed)):
            g, lat, c = self.gas.get(kind, []), self.latency_ms.get(kind, []), self.calls.get(kind, [])
            out[kind] = {
                "tx_count": len(g), "failed": self.failed.get(kind, 0),
                "gas_total": int(sum(g)), "gas_mean": float(np.mean(g)) if g else 0.0,
                "latency_mean_ms": float(np.mean(lat)) if lat else 0.0,
                "latency_p95_ms": float(np.percentile(lat, 95)) if lat else 0.0,
                "call_count": len(c), "call_mean_ms": float(np.mean(c)) if c else 0.0,
            }
        return out


class LocalSigner:
    """Signs transactions in the client with the accounts of the project's dev mnemonic (the same addresses Anvil
    unlocks). Besu exposes no unlocked accounts; nonces are counted here, per sender, across all nodes."""

    def __init__(self, n_accounts: int = 20, mnemonic: str | None = None):
        Account.enable_unaudited_hdwallet_features()
        mnemonic = mnemonic or load_config("blockchain")["accounts"]["mnemonic"]
        self.keys = [Account.from_mnemonic(mnemonic, account_path=f"m/44'/60'/0'/0/{i}") for i in range(n_accounts)]
        self.addresses = [k.address for k in self.keys]
        self._by_address = {k.address: k for k in self.keys}
        self._nonce: dict[str, int] = {}

    def sign(self, w3: Web3, tx: dict) -> bytes:
        sender = tx.pop("from")
        if sender not in self._nonce:
            self._nonce[sender] = w3.eth.get_transaction_count(sender, "pending")
        tx["nonce"] = self._nonce[sender]
        self._nonce[sender] += 1
        return self._by_address[sender].sign_transaction(tx).raw_transaction


class ReadMark:
    """Highest block holding a confirmed write. A read waits until its node has imported that block, so state
    written through one node is visible through every other (read-your-writes across the network)."""

    def __init__(self):
        self.block = 0
        self.lock = threading.Lock()

    def advance(self, block: int) -> None:
        with self.lock:
            self.block = max(self.block, block)


class Chain:
    """Thin, timed wrapper around the IoTRegistry contract on one RPC endpoint."""

    def __init__(self, rpc_url: str, address: str | None = None, signer: LocalSigner | None = None,
                 stats: TxStats | None = None, mark: ReadMark | None = None):
        self.url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 60}))
        self.signer = signer
        self.accounts = signer.addresses if signer else self.w3.eth.accounts   # else: unlocked dev accounts on Anvil
        self.chain_id = self.w3.eth.chain_id
        self.gas_price = self.w3.eth.gas_price * 2
        artifact = compile_contract()
        self.abi = artifact["abi"]
        self.bytecode = artifact["bytecode"]["object"]
        self.stats = stats or TxStats()
        self.mark = mark or ReadMark()
        self._head = 0                                 # highest block this node is known to have imported
        self._pending: queue.Queue | None = None       # background receipts (send_many(wait=False))
        self.contract = self.w3.eth.contract(address=address, abi=self.abi) if address else None

    def use(self, address: str) -> None:
        self.contract = self.w3.eth.contract(address=address, abi=self.abi)

    def deploy(self) -> str:
        if self.signer is None:
            factory = self.w3.eth.contract(abi=self.abi, bytecode=self.bytecode)
            tx = factory.constructor().transact({"from": self.accounts[0]})
        else:
            tx = self.w3.eth.send_raw_transaction(self.signer.sign(self.w3, {
                "from": self.accounts[0], "data": self.bytecode, "gas": 3_000_000, "gasPrice": self.gas_price,
                "chainId": self.chain_id}))
        receipt = self.w3.eth.wait_for_transaction_receipt(tx)
        self.stats.gas["deploy"].append(receipt.gasUsed)
        self._confirmed(receipt)
        self.use(receipt.contractAddress)
        return receipt.contractAddress

    def _submit(self, fn: str, args: list, sender: str, gas: int) -> bytes:
        data = self.contract.encode_abi(fn, args=args)
        # Every field is supplied so web3 makes exactly one RPC per transaction (no estimate/lookup round-trips).
        tx = {"from": sender, "to": self.contract.address, "data": data,
              "gas": gas, "gasPrice": self.gas_price, "chainId": self.chain_id}
        if self.signer is None:
            return self.w3.eth.send_transaction(tx)
        return self.w3.eth.send_raw_transaction(self.signer.sign(self.w3, tx))

    def _confirmed(self, receipt) -> None:
        self._head = max(self._head, receipt.blockNumber)
        self.mark.advance(receipt.blockNumber)

    def send_many(self, kind: str, fn: str, args_list: list[list], sender: str, gas: int = 250_000,
                  wait: bool = True) -> list:
        """Submit all transactions, then collect receipts (pipelined, as a node would). wait=False returns at once:
        a background watcher records the receipts (writes nothing later reads, e.g. audit records); drain() waits."""
        submitted = [(self._submit(fn, args, sender, gas), time.perf_counter()) for args in args_list]
        if not wait:
            self._watcher().put_many(kind, submitted)
            return []
        receipts = []
        for tx_hash, t0 in submitted:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120, poll_latency=0.005)
            self.stats.record(kind, receipt, (time.perf_counter() - t0) * 1000)
            self._confirmed(receipt)
            receipts.append(receipt)
        return receipts

    def send(self, kind: str, fn: str, args: list, sender: str, gas: int = 250_000, wait: bool = True):
        receipts = self.send_many(kind, fn, [args], sender, gas, wait)
        return receipts[0] if receipts else None

    def call(self, kind: str, fn: str, *args):
        t0 = time.perf_counter()
        self._sync()
        result = getattr(self.contract.functions, fn)(*args).call()
        self.stats.calls[kind].append((time.perf_counter() - t0) * 1000)
        return result

    def _sync(self, timeout: float = 60.0) -> None:
        """Wait until this node has imported every block that holds a confirmed write (no RPC when it has)."""
        target = self.mark.block
        deadline = time.perf_counter() + timeout
        while self._head < target:
            self._head = self.w3.eth.block_number
            if self._head < target:
                if time.perf_counter() > deadline:
                    raise TimeoutError(f"{self.url} stuck at block {self._head}, needs {target}")
                time.sleep(0.002)

    def _watcher(self) -> _ReceiptWatcher:
        if self._pending is None:
            self._pending = _ReceiptWatcher(self.url, self.stats)
        return self._pending

    def drain(self) -> None:
        """Wait for every background receipt; raises if a background write was not confirmed."""
        if self._pending is not None:
            self._pending.join()


class _ReceiptWatcher(queue.Queue):
    """Collects receipts of background writes on its own connection (web3 providers are not shared across threads)."""

    def __init__(self, url: str, stats: TxStats):
        super().__init__()
        self.stats, self.error = stats, None
        self.w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 60}))
        threading.Thread(target=self._run, daemon=True).start()

    def put_many(self, kind: str, submitted: list) -> None:
        for tx_hash, t0 in submitted:
            self.put((kind, tx_hash, t0))

    def _run(self) -> None:
        while True:
            kind, tx_hash, t0 = self.get()
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120, poll_latency=0.005)
                self.stats.record(kind, receipt, (time.perf_counter() - t0) * 1000)
            except Exception as exc:          # surfaced by join(); never silently lost
                self.error = exc
            finally:
                self.task_done()

    def join(self) -> None:
        super().join()
        if self.error is not None:
            raise RuntimeError(f"background transaction not confirmed: {self.error}")


def connect(urls: list[str], signer: LocalSigner | None = None) -> list[Chain]:
    """One Chain per node, sharing statistics, signer and read-your-writes mark (one network, many endpoints)."""
    stats, mark = TxStats(), ReadMark()
    return [Chain(url, signer=signer, stats=stats, mark=mark) for url in urls]


class NodeMonitor:
    """CPU seconds and peak RSS of the blockchain node process(es) over an experiment (summed over nodes)."""

    def __init__(self, pids: int | list[int]):
        self.procs = [psutil.Process(p) for p in ([pids] if isinstance(pids, int) else pids)]
        self.peak_rss = 0.0

    def start(self) -> None:
        self._cpu = [p.cpu_times() for p in self.procs]

    def sample(self) -> None:
        self.peak_rss = max(self.peak_rss, sum(p.memory_info().rss for p in self.procs) / 2**20)

    def stop(self) -> dict[str, float]:
        cpu = [p.cpu_times() for p in self.procs]
        self.sample()
        return {"node_cpu_s": sum((c.user - c0.user) + (c.system - c0.system) for c, c0 in zip(cpu, self._cpu,
                                                                                               strict=True)),
                "node_peak_rss_mb": self.peak_rss}
