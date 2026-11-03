"""EVM adapter: local Anvil node lifecycle, contract deployment, timed transactions with gas accounting (ADR §6).

Every transaction's submit->receipt latency and gas are recorded per `kind`, which is what the
baseline-vs-blockchain experiments report as L_blockchain (ADR Phase 8) and gas overhead.

Multi-node networks (final task 2, `src/common/qbft.py`) use one `Chain` per node endpoint, created by `connect`:
they share the transaction statistics, the local signer (Besu keeps no unlocked accounts) and a read-your-writes
mark, so a read on one node sees every write already confirmed through any other node.

A node that stops answering (fault-tolerance add-on, ADR §14.2 "retry + local queue + eventual commit"): the client
fails over to the next live node of the network and resends every signed transaction not yet confirmed. A signed
transaction's hash is fixed by its bytes, so resending it is idempotent.
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
import requests
from eth_account import Account
from web3 import Web3
from web3.exceptions import Web3RPCError

from src.common.config import ROOT, load_config

DEAD_NODE = (requests.exceptions.ConnectionError, requests.exceptions.Timeout)

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


def _answers(url: str) -> bool:
    try:
        return Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 2})).eth.block_number >= 0
    except Exception:
        return False


class Endpoints:
    """The node a client uses, then the nodes it fails over to, in order. Shared by a Chain and its receipt watcher:
    every failover bumps `generation`, so each thread reconnects and resends what was sent to the dead node."""

    def __init__(self, urls: list[str]):
        self.urls, self.index, self.generation = list(urls), 0, 0
        self.lock = threading.Lock()
        self.failovers: list[dict] = []                # {"t": unix time, "from": url, "to": url}

    @property
    def url(self) -> str:
        return self.urls[self.index]

    def fail(self, seen: int) -> None:
        """The node of generation `seen` stopped answering: move to the next node that answers (the others first,
        then itself), `attempts` rounds with a pause between them. Several threads may notice the same failure."""
        with self.lock:
            if seen != self.generation:
                return                                 # another thread has already failed over
            cfg = load_config("blockchain")["retry"]
            for _ in range(cfg["attempts"]):
                for k in range(1, len(self.urls) + 1):
                    i = (self.index + k) % len(self.urls)
                    if _answers(self.urls[i]):
                        self.failovers.append({"t": time.time(), "from": self.url, "to": self.urls[i]})
                        self.index, self.generation = i, self.generation + 1
                        return
                time.sleep(cfg["backoff_seconds"])
            raise requests.exceptions.ConnectionError(f"no node answers: {', '.join(self.urls)}")


class _Link:
    """One thread's connection to the network (web3 providers are not shared across threads): its own Web3 on the
    current endpoint, rebuilt after a failover."""

    def __init__(self, endpoints: Endpoints):
        self.endpoints, self.generation, self.w3 = endpoints, -1, None
        self.refresh()

    def refresh(self) -> bool:
        """Reconnect if another thread failed over; True if it did."""
        if self.generation == self.endpoints.generation:
            return False
        self.generation = self.endpoints.generation
        self.w3 = Web3(Web3.HTTPProvider(self.endpoints.url, request_kwargs={"timeout": 60}))
        return True

    def rpc(self, fn):
        """fn(w3) on the current node; on a dead node, fail over and run it again on the next."""
        while True:
            self.refresh()
            try:
                return fn(self.w3)
            except DEAD_NODE:
                self.endpoints.fail(self.generation)

    def resend_stale(self, txs: list[list]) -> None:
        """txs: [tx hash, signed bytes or None, endpoint generation it was sent to], in nonce order. Each one sent to
        a node that has died since may never have left it: resend it to the current node (eventual commit)."""
        for tx in txs:
            while tx[1] is not None and tx[2] != self.generation:
                try:
                    self.w3.eth.send_raw_transaction(tx[1])
                except Web3RPCError:                   # already in this node's pool, or already in a block
                    pass
                except DEAD_NODE:
                    self.endpoints.fail(self.generation)
                    self.refresh()
                    continue
                tx[2] = self.generation

    def receipt(self, tx: list, unconfirmed: list[list]):
        """Wait for the receipt of tx; after any failover, first resend every unconfirmed transaction (tx included)."""
        timeout = load_config("blockchain")["retry"]["receipt_timeout_s"]
        while True:
            self.refresh()
            self.resend_stale(unconfirmed)
            try:
                return self.w3.eth.wait_for_transaction_receipt(tx[0], timeout=timeout, poll_latency=0.005)
            except DEAD_NODE:
                self.endpoints.fail(self.generation)


class Chain:
    """Thin, timed wrapper around the IoTRegistry contract on one RPC endpoint (and the endpoints it fails over to)."""

    def __init__(self, rpc_url: str, address: str | None = None, signer: LocalSigner | None = None,
                 stats: TxStats | None = None, mark: ReadMark | None = None, fallbacks: list[str] = ()):
        self.endpoints = Endpoints([rpc_url, *fallbacks])
        self.link = _Link(self.endpoints)
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
        self._head_on = self.link.generation           # ... on the node of this generation
        self._pending: queue.Queue | None = None       # background receipts (send_many(wait=False))
        self.contract = None
        if address:
            self.use(address)

    @property
    def w3(self) -> Web3:
        return self.link.w3

    @property
    def url(self) -> str:
        return self.endpoints.url

    def use(self, address: str) -> None:
        self.contract = self.w3.eth.contract(address=address, abi=self.abi)
        self._bound_on = self.link.generation

    def _bound(self):
        """The contract bound to the current node (rebound after a failover)."""
        if self._bound_on != self.link.generation:
            self.use(self.contract.address)
        return self.contract

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

    def _submit(self, fn: str, args: list, sender: str, gas: int) -> list:
        """[tx hash, signed bytes or None, endpoint generation it was sent to, submit time]."""
        data = self.contract.encode_abi(fn, args=args)
        # Every field is supplied so web3 makes exactly one RPC per transaction (no estimate/lookup round-trips).
        tx = {"from": sender, "to": self.contract.address, "data": data,
              "gas": gas, "gasPrice": self.gas_price, "chainId": self.chain_id}
        t0 = time.perf_counter()
        if self.signer is None:
            return [self.link.rpc(lambda w3: w3.eth.send_transaction(tx)), None, self.link.generation, t0]
        raw = self.link.rpc(lambda w3: self.signer.sign(w3, dict(tx)))   # first use per sender reads its nonce
        self.link.rpc(lambda w3: w3.eth.send_raw_transaction(raw))
        return [Web3.keccak(raw), raw, self.link.generation, t0]

    def _confirmed(self, receipt) -> None:
        self._head = max(self._head, receipt.blockNumber)
        self.mark.advance(receipt.blockNumber)

    def send_many(self, kind: str, fn: str, args_list: list[list], sender: str, gas: int = 250_000,
                  wait: bool = True) -> list:
        """Submit all transactions, then collect receipts (pipelined, as a node would). wait=False returns at once:
        a background watcher records the receipts (writes nothing later reads, e.g. audit records); drain() waits."""
        submitted = [self._submit(fn, args, sender, gas) for args in args_list]
        if not wait:
            self._watcher().put_many(kind, submitted)
            return []
        receipts = []
        for i, tx in enumerate(submitted):
            receipt = self.link.receipt(tx, submitted[i:])
            self.stats.record(kind, receipt, (time.perf_counter() - tx[3]) * 1000)
            self._confirmed(receipt)
            receipts.append(receipt)
        return receipts

    def send(self, kind: str, fn: str, args: list, sender: str, gas: int = 250_000, wait: bool = True):
        receipts = self.send_many(kind, fn, [args], sender, gas, wait)
        return receipts[0] if receipts else None

    def call(self, kind: str, fn: str, *args):
        t0 = time.perf_counter()
        self._sync()
        result = self.link.rpc(lambda _: getattr(self._bound().functions, fn)(*args).call())
        self.stats.calls[kind].append((time.perf_counter() - t0) * 1000)
        return result

    def _sync(self, timeout: float = 60.0) -> None:
        """Wait until this node has imported every block that holds a confirmed write (no RPC when it has)."""
        if self._head_on != self.link.generation:      # failed over: nothing is known about the new node yet
            self._head, self._head_on = 0, self.link.generation
        target = self.mark.block
        deadline = time.perf_counter() + timeout
        while self._head < target:
            self._head = self.link.rpc(lambda w3: w3.eth.block_number)
            self._head_on = self.link.generation
            if self._head < target:
                if time.perf_counter() > deadline:
                    raise TimeoutError(f"{self.url} stuck at block {self._head}, needs {target}")
                time.sleep(0.002)

    def _watcher(self) -> _ReceiptWatcher:
        if self._pending is None:
            self._pending = _ReceiptWatcher(self.endpoints, self.stats)
        return self._pending

    def drain(self) -> None:
        """Wait for every background receipt; raises if a background write was not confirmed."""
        if self._pending is not None:
            self._pending.join()


class _ReceiptWatcher(queue.Queue):
    """Collects receipts of background writes on its own connection to the same endpoints."""

    def __init__(self, endpoints: Endpoints, stats: TxStats):
        super().__init__()
        self.stats, self.error = stats, None
        self.endpoints = endpoints
        threading.Thread(target=self._run, daemon=True).start()

    def put_many(self, kind: str, submitted: list) -> None:
        for tx in submitted:
            self.put((kind, tx))

    def _run(self) -> None:
        link = _Link(self.endpoints)
        while True:
            kind, tx = self.get()
            try:
                with self.mutex:                       # the rest of the queue, in nonce order, for resending
                    waiting = [t for _, t in self.queue]
                receipt = link.receipt(tx, [tx, *waiting])
                self.stats.record(kind, receipt, (time.perf_counter() - tx[3]) * 1000)
            except Exception as exc:          # surfaced by join(); never silently lost
                self.error = exc
            finally:
                self.task_done()

    def join(self) -> None:
        super().join()
        if self.error is not None:
            raise RuntimeError(f"background transaction not confirmed: {self.error}")


def connect(urls: list[str], signer: LocalSigner | None = None) -> list[Chain]:
    """One Chain per node, sharing statistics, signer and read-your-writes mark (one network, many endpoints).
    Each Chain fails over to the other nodes, starting with the next one."""
    stats, mark = TxStats(), ReadMark()
    return [Chain(url, signer=signer, stats=stats, mark=mark, fallbacks=urls[i + 1:] + urls[:i])
            for i, url in enumerate(urls)]


class NodeMonitor:
    """CPU seconds and peak RSS of the blockchain node process(es) over an experiment (summed over nodes).

    `pids` may be a callable returning the current pids: a node killed and restarted during the run (fault
    experiments) is then a new process, counted from its start; a killed one keeps the CPU seen at its last sample."""

    def __init__(self, pids):
        self._pids = pids if callable(pids) else (lambda: [pids] if isinstance(pids, int) else list(pids))
        self.peak_rss = 0.0
        self._procs: dict[int, list] = {}              # pid -> [process, cpu seconds at start, last cpu seconds]

    @staticmethod
    def _cpu(p: psutil.Process) -> float:
        t = p.cpu_times()
        return t.user + t.system

    def _refresh(self, baseline_now: bool) -> None:
        for pid in self._pids():
            if pid not in self._procs:
                try:
                    p = psutil.Process(pid)
                    cpu = self._cpu(p)
                except psutil.NoSuchProcess:           # listed but already gone (a node being stopped)
                    continue
                self._procs[pid] = [p, cpu if baseline_now else 0.0, cpu]

    def start(self) -> None:
        self._refresh(baseline_now=True)

    def sample(self) -> None:
        self._refresh(baseline_now=False)              # a process started after start() counts from zero
        rss = 0
        for entry in self._procs.values():
            try:
                entry[2] = self._cpu(entry[0])
                rss += entry[0].memory_info().rss
            except psutil.NoSuchProcess:               # killed: keep its last CPU reading
                pass
        self.peak_rss = max(self.peak_rss, rss / 2**20)

    def stop(self) -> dict[str, float]:
        self.sample()
        return {"node_cpu_s": sum(last - first for _, first, last in self._procs.values()),
                "node_peak_rss_mb": self.peak_rss}
