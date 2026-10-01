"""EVM adapter: local Anvil node lifecycle, contract deployment, timed transactions with gas accounting (ADR §6).

Every transaction's submit->receipt latency and gas are recorded per `kind`, which is what the
baseline-vs-blockchain experiments report as L_blockchain (ADR Phase 8) and gas overhead.
"""

from __future__ import annotations

import json
import socket
import subprocess
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np
import psutil
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


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def local_node(block_time: float | None = None, accounts: int = 20):
    """Start a private Anvil chain for one experiment and stop it afterwards. Yields (rpc_url, process)."""
    if not ANVIL.exists():
        raise FileNotFoundError(f"{ANVIL} missing — see README (Blockchain setup)")
    port = _free_port()
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


class Chain:
    """Thin, timed wrapper around the IoTRegistry contract on one RPC endpoint."""

    def __init__(self, rpc_url: str, address: str | None = None):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 60}))
        self.accounts = self.w3.eth.accounts          # unlocked dev accounts on Anvil
        self.chain_id = self.w3.eth.chain_id
        self.gas_price = self.w3.eth.gas_price * 2
        artifact = compile_contract()
        self.abi = artifact["abi"]
        self.bytecode = artifact["bytecode"]["object"]
        self.stats = TxStats()
        self.contract = self.w3.eth.contract(address=address, abi=self.abi) if address else None

    def deploy(self) -> str:
        factory = self.w3.eth.contract(abi=self.abi, bytecode=self.bytecode)
        tx = factory.constructor().transact({"from": self.accounts[0]})
        receipt = self.w3.eth.wait_for_transaction_receipt(tx)
        self.stats.gas["deploy"].append(receipt.gasUsed)
        self.contract = self.w3.eth.contract(address=receipt.contractAddress, abi=self.abi)
        return receipt.contractAddress

    def _submit(self, fn: str, args: list, sender: str, gas: int) -> bytes:
        data = self.contract.encode_abi(fn, args=args)
        # Every field is supplied so web3 makes exactly one RPC per transaction (no estimate/lookup round-trips).
        return self.w3.eth.send_transaction({
            "from": sender, "to": self.contract.address, "data": data,
            "gas": gas, "gasPrice": self.gas_price, "chainId": self.chain_id,
        })

    def send_many(self, kind: str, fn: str, args_list: list[list], sender: str, gas: int = 250_000) -> list:
        """Submit all transactions, then collect receipts (pipelined, as a node would)."""
        submitted = [(self._submit(fn, args, sender, gas), time.perf_counter()) for args in args_list]
        receipts = []
        for tx_hash, t0 in submitted:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120, poll_latency=0.005)
            self.stats.latency_ms[kind].append((time.perf_counter() - t0) * 1000)
            if receipt.status == 1:
                self.stats.gas[kind].append(receipt.gasUsed)
            else:
                self.stats.failed[kind] += 1
            receipts.append(receipt)
        return receipts

    def send(self, kind: str, fn: str, args: list, sender: str, gas: int = 250_000):
        return self.send_many(kind, fn, [args], sender, gas)[0]

    def call(self, kind: str, fn: str, *args):
        t0 = time.perf_counter()
        result = getattr(self.contract.functions, fn)(*args).call()
        self.stats.calls[kind].append((time.perf_counter() - t0) * 1000)
        return result


class NodeMonitor:
    """CPU seconds and peak RSS of the blockchain node process over an experiment."""

    def __init__(self, pid: int):
        self.proc = psutil.Process(pid)
        self.peak_rss = 0.0

    def start(self) -> None:
        self._cpu = self.proc.cpu_times()

    def sample(self) -> None:
        self.peak_rss = max(self.peak_rss, self.proc.memory_info().rss / 2**20)

    def stop(self) -> dict[str, float]:
        cpu = self.proc.cpu_times()
        self.sample()
        return {"node_cpu_s": (cpu.user - self._cpu.user) + (cpu.system - self._cpu.system),
                "node_peak_rss_mb": self.peak_rss}
