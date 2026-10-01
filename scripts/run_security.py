"""Security experiment (ADR §11.2 Experiment D, §14.3): inject attacks on real Edge-IIoTset traffic and
measure what the baseline and the blockchain-enabled architecture each detect.

  python scripts/run_security.py [--rows 3000] [--rate 0.05]

Attacks are synthetic mutations of real events, as the dataset plan's synthetic-data policy allows.
Writes experiments/results/exp_security.csv and security-<timestamp>.json.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import shutil
import sys
import tempfile
import time
import zlib
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cloud.model_registry import ModelIntegrityError  # noqa: E402
from src.cloud.service import CloudNode  # noqa: E402
from src.common.blockchain import Chain, h32, id32, local_node  # noqa: E402
from src.common.config import load_config, resolve  # noqa: E402
from src.common.crypto import DeviceKey, hash_file  # noqa: E402
from src.device.collector import seal  # noqa: E402
from src.device.service import DeviceLayer  # noqa: E402
from src.device.simulator import DeviceSimulator  # noqa: E402
from src.edge.service import EdgeNode  # noqa: E402
from src.fog.service import FogNode  # noqa: E402
from src.pipeline import attach_blockchain, load_stream_rows  # noqa: E402

ATTACKS = ["tamper", "replay_same_edge", "replay_cross_edge", "unregistered_device", "impersonation"]


def stream_with_attacks(mode: str, attack_type: str, rows: pd.DataFrame, n_devices: int, n_edges: int,
                        rate: float, seed: int, chain: Chain | None) -> tuple[list[dict], dict]:
    """One isolated pass: real traffic plus a single attack type, so attacks cannot mask each other."""
    rng = random.Random(seed)
    sim = DeviceSimulator(rows, n_devices, seed)
    device_layer = DeviceLayer()
    edges = [EdgeNode(f"edge-{i:02d}") for i in range(n_edges)]
    if chain is not None:
        attach_blockchain(chain, "per_event", seed, [sim.device_id(i) for i in range(n_devices)], device_layer,
                          edges, [FogNode("fog-00")], CloudNode())
    attacker_key = DeviceKey.from_seed(b"attacker")
    history: list[tuple[dict, int]] = []          # (processed event, edge index) available for replay
    outcomes: list[dict] = []
    edge_ms: list[float] = []

    def route(e: dict) -> int:
        return zlib.crc32(e["device_id"].encode()) % n_edges

    for b, batch in enumerate(sim.batches(128)):
        device_layer.process(batch)                   # seals + commits when the ledger is attached
        inbound: list[tuple[dict, int, str | None]] = []
        for e in batch:
            attack = None
            if attack_type == "tamper" and rng.random() < rate:   # MITM changes one feature value in flight
                e = copy.deepcopy(e)
                key = next(k for k, v in e["values"].items() if isinstance(v, float))
                e["values"][key] = e["values"][key] + 1.0
                attack = "tamper"
            inbound.append((e, route(e), attack))

        n_inject = max(1, int(rate * len(batch)))
        for _ in range(n_inject if history and attack_type.startswith("replay") else 0):
            old, edge_idx = rng.choice(history)
            target = edge_idx if attack_type == "replay_same_edge" else (edge_idx + 1) % n_edges
            inbound.append((copy.deepcopy(old), target, attack_type))
        for i in range(n_inject if attack_type in ("unregistered_device", "impersonation") else 0):
            template = rng.choice(batch)
            for attack, device_id in (("unregistered_device", "device-9999"),
                                      ("impersonation", template["device_id"])):
                if attack != attack_type:
                    continue
                e = copy.deepcopy(template)
                e.update(event_id=f"forged-{attack}-{b}-{i}", trace_id=f"forged-{b}-{i}", device_id=device_id,
                         sequence_number=10**9 + b * 1000 + i)
                if chain is not None:
                    seal(e, attacker_key)             # attacker signs with its own key
                inbound.append((e, route(e), attack))

        for idx, node in enumerate(edges):
            events = [(e, a) for e, r, a in inbound if r == idx]
            before = len(node.rejected)
            t0 = time.perf_counter()
            accepted = node.process([e for e, _ in events])
            edge_ms.append((time.perf_counter() - t0) * 1000 / max(1, len(events)))
            reasons = iter(r for _, r in node.rejected[before:])
            accepted_ids = {id(e) for e in accepted}
            for e, attack in events:
                ok = id(e) in accepted_ids
                outcomes.append({"mode": mode, "attack": attack or f"legitimate (during {attack_type})",
                                 "accepted": ok, "reason": None if ok else next(reasons)})
                if ok and attack is None:
                    history.append((e, idx))
    return outcomes, {"edge_ms_per_event_mean": sum(edge_ms) / len(edge_ms)}


def unauthorized_write(chain: Chain) -> dict:
    """An account the owner never authorized tries to commit a forged event hash."""
    intruder = chain.accounts[-1]
    receipt = chain.send("attack_unauthorized_write", "commitData",
                         [id32("forged"), id32("device-0000"), b"\x11" * 32, 0, 0], intruder)
    return {"mode": "blockchain", "attack": "unauthorized_ledger_write", "accepted": receipt.status == 1,
            "reason": None if receipt.status == 1 else "contract_revert_NotAuthorized"}


def model_tamper(chain: Chain | None, mode: str) -> list[dict]:
    """ADR §14.3 Test 4, in two strengths: artifact-only tampering, and tampering that also rewrites the
    local provenance record so the local hash check passes."""
    layer_dir = resolve(load_config("base")["paths"]["models"]) / "edge"
    record = json.loads((layer_dir / f"{json.loads((layer_dir / 'current.json').read_text())['model_id']}.json")
                        .read_text())
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for attack in ("model_tamper_artifact_only", "model_tamper_artifact_and_record"):
            artifact = Path(tmp) / record["artifact"]
            shutil.copy(layer_dir / record["artifact"], artifact)
            local = dict(record)
            if chain is not None:
                chain.send("model_register", "registerModel",
                           [id32(f"{attack}:{local['model_id']}"), h32(local["model_hash"]), 1, "edge"],
                           chain.accounts[0])
            with artifact.open("ab") as f:
                f.write(b"backdoor")          # attacker swaps in a modified model
            if attack.endswith("and_record"):
                local["model_hash"] = hash_file(artifact)
            try:
                if hash_file(artifact) != local["model_hash"]:
                    raise ModelIntegrityError("local record mismatch")
                if chain is not None:
                    on_chain = chain.call("model_verify", "models", id32(f"{attack}:{local['model_id']}"))[0]
                    if h32(hash_file(artifact)) != on_chain:
                        raise ModelIntegrityError("on-chain registry mismatch")
                out.append({"mode": mode, "attack": attack, "accepted": True, "reason": None})
            except ModelIntegrityError as exc:
                out.append({"mode": mode, "attack": attack, "accepted": False, "reason": str(exc)})
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=3000)
    parser.add_argument("--rate", type=float, default=0.05, help="fraction of traffic tampered / injected")
    parser.add_argument("--devices", type=int, default=10)
    parser.add_argument("--edges", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    view = load_config("models")["training"]["view"]
    rows, _ = load_stream_rows(view, args.rows, args.seed)
    outcomes, timing = [], defaultdict(list)
    for attack in ATTACKS:
        o, t = stream_with_attacks("baseline", attack, rows, args.devices, args.edges, args.rate, args.seed, None)
        outcomes += o
        timing["baseline"].append(t["edge_ms_per_event_mean"])
        with local_node() as (url, _):                       # fresh chain per pass
            o, t = stream_with_attacks("blockchain", attack, rows, args.devices, args.edges, args.rate, args.seed,
                                       Chain(url))
        outcomes += o
        timing["blockchain"].append(t["edge_ms_per_event_mean"])
        print(f"pass done: {attack}", flush=True)
    outcomes += model_tamper(None, "baseline")
    with local_node() as (url, _):
        chain = Chain(url)
        chain.deploy()
        outcomes += model_tamper(chain, "blockchain") + [unauthorized_write(chain)]
    timing = {k: {"edge_ms_per_event_mean": sum(v) / len(v)} for k, v in timing.items()}

    df = pd.DataFrame(outcomes)
    rows_out = []
    for (mode, attack), g in df.groupby(["mode", "attack"], sort=False):
        rejected = g[~g.accepted]
        row = {"mode": mode, "attack": attack, "events": len(g), "rejected": len(rejected),
               "reasons": json.dumps(rejected.reason.value_counts().to_dict())}
        if attack.startswith("legitimate"):
            row["false_reject_rate"] = len(rejected) / len(g)
        else:
            row["detection_rate"] = len(rejected) / len(g)
            row["false_accept_rate"] = 1 - len(rejected) / len(g)
        rows_out.append(row)
    summary = pd.DataFrame(rows_out)

    out = resolve(load_config("base")["paths"]["results"])
    out.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out / "exp_security.csv", index=False)
    stamp = f"{datetime.now(UTC):%Y%m%dT%H%M%S}"
    (out / f"security-{stamp}.json").write_text(json.dumps(
        {"args": vars(args), "timing": timing, "summary": summary.to_dict("records")}, indent=2, default=str))
    pd.set_option("display.width", 200)
    print(summary.drop(columns=["reasons"]).round(3).to_string(index=False))
    print("edge verification cost per event (ms):",
          {k: round(v["edge_ms_per_event_mean"], 3) for k, v in timing.items()})
    by = defaultdict(dict)
    for r in rows_out:
        by[r["attack"]][r["mode"]] = r["reasons"]
    print("detected by:", json.dumps({a: m.get("blockchain") for a, m in by.items()}, indent=1))


if __name__ == "__main__":
    main()
