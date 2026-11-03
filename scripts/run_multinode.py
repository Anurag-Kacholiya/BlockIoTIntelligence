"""Final task 2: the architecture on a multi-node blockchain (Besu validators, QBFT consensus).

  python scripts/run_multinode.py check                        # start a 4-validator network, write via one node,
                                                                # read via another, print the consensus status
  python scripts/run_multinode.py run [--groups comparison …]  # groups of suites.final_task2 (configs/experiments.yaml)
  python scripts/run_multinode.py run --resume                 # skip runs already in runs.jsonl

Every run is appended to experiments/results/final_task2/runs.jsonl. Security on the QBFT network:
  python scripts/run_security.py --rows 3000 --replay realistic --chain qbft
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import load_config, resolve  # noqa: E402

SUITE = "final_task2"


def label(backend: str, block_time) -> str:
    return f"{backend}_{'automine' if block_time is None else f'{block_time:g}s'}"


def plan(suite: dict, groups: list[str]) -> list[dict]:
    runs = []
    for g in groups:
        c = suite["groups"][g]
        for seed in c["seeds"]:
            for backend, block_time in c["chains"]:
                for k in c.get("replicas", [1]):
                    for mode in c["modes"]:
                        runs.append({"group": g, "chain": label(backend, block_time), "backend": backend,
                                     "block_time": block_time, "mode": mode, "seed": seed, "replicas": k,
                                     "rows": c.get("rows", suite["rows"]),
                                     "audit_writes": c.get("audit_writes", suite["audit_writes"])})
    return runs


def key(p: dict) -> tuple:
    return p["group"], p["chain"], p["mode"], p["seed"], p["replicas"]


def run_groups(groups: list[str] | None, resume: bool) -> None:
    from src.pipeline import run

    suite = load_config("experiments")["suites"][SUITE]
    os.environ["BLOCKIOT_VIEW"] = suite["view"]
    out = resolve(load_config("base")["paths"]["results"]) / SUITE
    out.mkdir(parents=True, exist_ok=True)
    runs_file = out / "runs.jsonl"
    done = set()
    if resume and runs_file.exists():
        done = {key(r["task2"]) for r in map(json.loads, runs_file.read_text().splitlines())}
    todo = [p for p in plan(suite, groups or list(suite["groups"])) if key(p) not in done]
    for i, p in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {p}", flush=True)
        result = run(experiment=f"task2_{p['group']}_{p['chain']}_{p['mode']}", blockchain=p["mode"],
                     n_rows=p["rows"], edges=suite["edges"], fogs=suite["fogs"], seed=p["seed"],
                     block_time=p["block_time"], replay=suite["replay"], replicas=p["replicas"],
                     chain_backend=p["backend"], signing=suite["signing"], audit_writes=p["audit_writes"],
                     log=lambda *_: None)
        result["task2"] = p
        with runs_file.open("a") as f:
            f.write(json.dumps(result, default=str) + "\n")
        e2e = result["latency_ms"]["batch_end_to_end"]
        consensus = result["chain_network"].get("consensus", {})
        print(f"    {result['throughput_eps']:,.0f} ev/s; message latency mean {e2e['mean_ms']:,.0f} ms, "
              f"p95 {e2e['p95_ms']:,.0f} ms; rejected {result['events_rejected']}; "
              f"device commit {result['chain']['device_commit']['latency_mean_ms']:,.0f} ms"
              + (f"; consistent={consensus['consistent']} at height {consensus['common_height']}" if consensus else ""),
              flush=True)
    print(f"results: {runs_file}")


def check() -> None:
    """Smallest end-to-end proof of a working network: a write through node 0 is read back through node 3."""
    from src.common.blockchain import LocalSigner, connect, id32
    from src.common.qbft import qbft_network

    with qbft_network() as net:
        chains = connect(net.urls, LocalSigner())
        owner = chains[0]
        address = owner.deploy()
        for c in chains[1:]:
            c.use(address)
        device = id32("check-device")
        receipt = owner.send("check_register", "registerDevice", [device, b"\x01" * 32, "check://device"],
                             owner.accounts[0])
        seen = chains[-1].call("check_read", "devices", device)
        print(json.dumps({"contract": address, "write_block": receipt.blockNumber, "write_status": receipt.status,
                          "read_back_on_last_node": seen[2], **net.report()}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    p = sub.add_parser("run")
    p.add_argument("--groups", nargs="+", default=None)
    p.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.cmd == "check":
        check()
    else:
        run_groups(args.groups, args.resume)


if __name__ == "__main__":
    main()
