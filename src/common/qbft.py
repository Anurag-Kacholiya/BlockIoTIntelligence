"""Private multi-node network: Hyperledger Besu validators reaching QBFT consensus (final task 2).

Every validator is its own process with its own key, database, P2P port and JSON-RPC endpoint. A block is final
once 2f + 1 of the n = 3f + 1 validators commit it (4 validators: 3 must agree, 1 may fail). One block is proposed
every `block_period_s`, so a transaction waits for the next block plus a consensus round, as on a real network.

`qbft_network()` builds a fresh network for one experiment (keys and QBFT genesis from Besu's own generator, the
project's dev accounts pre-funded), waits until every validator is peered and blocks are produced, and stops it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from src.common.blockchain import LocalSigner, free_port
from src.common.config import ROOT, load_config

BESU = ROOT / "tools" / "besu" / "bin" / "besu"
# Fixed mixHash of every IBFT 2.0 / QBFT block (bytes of "...ctical byzantine fault tolerance"); the generator adds
# the validator list to the genesis extraData.
QBFT_MIX_HASH = "0x63746963616c2062797a616e74696e65206661756c7420746f6c6572616e6365"


def genesis_config(validators: int, block_period_s: int, accounts: list[str]) -> dict:
    """Input of `besu operator generate-blockchain-config`: genesis (QBFT, Cancun rules for the contract's
    bytecode, zero base fee so the dev accounts never run dry) plus `validators` freshly generated node keys."""
    cfg = load_config("blockchain")["qbft"]
    return {
        "genesis": {
            "config": {
                "chainId": cfg["chain_id"], "berlinBlock": 0, "londonBlock": 0, "shanghaiTime": 0, "cancunTime": 0,
                "zeroBaseFee": True,
                "qbft": {"blockperiodseconds": block_period_s, "epochlength": 30000,
                         "requesttimeoutseconds": cfg["request_timeout_s"]},
            },
            "nonce": "0x0", "timestamp": "0x0", "difficulty": "0x1", "mixHash": QBFT_MIX_HASH,
            "coinbase": "0x0000000000000000000000000000000000000000", "gasLimit": hex(cfg["gas_limit"]),
            "alloc": {a: {"balance": hex(10**24)} for a in accounts},
        },
        "blockchain": {"nodes": {"generate": True, "count": validators}},
    }


@dataclass
class Network:
    urls: list[str]
    procs: list[subprocess.Popen]
    workdir: Path
    block_period_s: int

    @property
    def pids(self) -> list[int]:
        return [p.pid for p in self.procs]

    def report(self) -> dict:
        """Consensus check: every node holds the same block at the highest height they all reached."""
        nodes = [Web3(Web3.HTTPProvider(u, request_kwargs={"timeout": 30})) for u in self.urls]
        for w3 in nodes:     # QBFT block headers carry the validators and their seals in extraData (> 32 bytes)
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        heads = [w3.eth.block_number for w3 in nodes]
        common = min(heads)
        hashes = {w3.eth.get_block(common).hash.hex() for w3 in nodes}
        validators = nodes[0].provider.make_request("qbft_getValidatorsByBlockNumber", ["latest"])["result"]
        return {"nodes": len(nodes), "validators": len(validators), "heads": heads, "common_height": common,
                "consistent": len(hashes) == 1, "peers": [w3.net.peer_count for w3 in nodes],
                "block_period_s": self.block_period_s}


def _generate(workdir: Path, validators: int, block_period_s: int) -> tuple[Path, list[Path]]:
    config = workdir / "qbft_config.json"
    config.write_text(json.dumps(genesis_config(validators, block_period_s, LocalSigner().addresses), indent=2))
    out = workdir / "network"
    subprocess.run([str(BESU), "operator", "generate-blockchain-config", f"--config-file={config}", f"--to={out}",
                    "--private-key-file-name=key"], check=True, capture_output=True, text=True,
                   env=_env(load_config("blockchain")["qbft"]["jvm_heap"]))
    keys = sorted((out / "keys").iterdir())
    if len(keys) != validators:
        raise RuntimeError(f"expected {validators} validator keys, got {len(keys)}")
    return out / "genesis.json", keys


def _env(heap: str) -> dict:
    return os.environ | {"BESU_OPTS": f"-Xmx{heap}"}


def _wait(cond, what: str, timeout: float, logs: list[Path]) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if cond():
                return
        except Exception:
            pass
        time.sleep(0.25)
    tails = "\n".join(f"--- {p.name}\n" + "\n".join(p.read_text(errors="replace").splitlines()[-20:]) for p in logs)
    raise RuntimeError(f"QBFT network: {what} not reached in {timeout:.0f}s\n{tails}")


@contextmanager
def qbft_network(validators: int | None = None, block_period_s: int | None = None, keep: bool = False):
    """Start a fresh n-validator QBFT network; yields a Network; stops every node (and deletes its data) after."""
    if not BESU.exists():
        raise FileNotFoundError(f"{BESU} missing: run scripts/setup_besu.py (needs Java 21+)")
    cfg = load_config("blockchain")["qbft"]
    validators = validators or cfg["validators"]
    block_period_s = int(block_period_s or cfg["block_period_s"])
    workdir = Path(tempfile.mkdtemp(prefix="blockiot-qbft-"))
    procs: list[subprocess.Popen] = []
    try:
        genesis, keys = _generate(workdir, validators, block_period_s)
        p2p = [free_port() for _ in keys]
        rpc = [free_port() for _ in keys]
        enodes = [f"enode://{(k / 'key.pub').read_text().strip().removeprefix('0x')}@127.0.0.1:{port}"
                  for k, port in zip(keys, p2p, strict=True)]
        logs = [workdir / f"node{i}.log" for i in range(validators)]
        for i, key in enumerate(keys):
            args = [str(BESU), f"--data-path={workdir / f'node{i}'}", f"--genesis-file={genesis}",
                    f"--node-private-key-file={key / 'key'}", "--p2p-host=127.0.0.1", f"--p2p-port={p2p[i]}",
                    f"--bootnodes={','.join(e for j, e in enumerate(enodes) if j != i)}",
                    "--rpc-http-enabled", "--rpc-http-host=127.0.0.1", f"--rpc-http-port={rpc[i]}",
                    "--rpc-http-api=ETH,NET,QBFT,WEB3,TXPOOL", "--host-allowlist=*", "--min-gas-price=0",
                    # a micro-batch sends up to 256 transactions from one account at once; Besu's default
                    # refuses any more than 200 nonces ahead of the account's last confirmed one
                    f"--tx-pool-max-future-by-sender={cfg['tx_pool_max_future_by_sender']}",
                    "--sync-mode=FULL", "--logging=WARN"]
            with logs[i].open("w") as log:
                procs.append(subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=_env(cfg["jvm_heap"])))
        urls = [f"http://127.0.0.1:{port}" for port in rpc]
        nodes = [Web3(Web3.HTTPProvider(u, request_kwargs={"timeout": 5})) for u in urls]
        _wait(lambda: all(w3.is_connected() for w3 in nodes), "every RPC endpoint up", 120, logs)
        _wait(lambda: all(w3.net.peer_count >= validators - 1 for w3 in nodes), "full peering", 120, logs)
        _wait(lambda: min(w3.eth.block_number for w3 in nodes) >= 2, "blocks produced on every node", 120, logs)
        yield Network(urls, procs, workdir, block_period_s)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()
        if not keep:
            shutil.rmtree(workdir, ignore_errors=True)
