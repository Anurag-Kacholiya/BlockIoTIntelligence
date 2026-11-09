"""Final task 3 (RQ-11, AI-driven blockchain): the device gateway decides when each device's Merkle batch closes.

  python scripts/train_forecaster.py                       # the cloud trains the traffic forecaster (train windows)
  python scripts/run_ai_blockchain.py simulate             # offline: every policy over the whole gas/latency trade-off
  python scripts/run_ai_blockchain.py run [--groups …]     # live runs on the 4-validator QBFT network
  python scripts/run_ai_blockchain.py run --resume         # skip runs already in runs.jsonl

Suite final_task3 (configs/experiments.yaml). Outputs in experiments/results/final_task3/:
  simulation.csv        one row per (stream, devices, policy, setting): roots, waiting, from the same scheduler code a
                        live run uses (src/device/commit_policy.py)
  forecast_quality.csv  the forecaster on the test window, against persistence and the Poisson rate
  runs.jsonl            every live run; rows/<key>.parquet the messages that reached the cloud, with every prediction
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import load_config, resolve  # noqa: E402

SUITE = "final_task3"


def out_dir() -> Path:
    out = resolve(load_config("base")["paths"]["results"]) / SUITE
    (out / "rows").mkdir(parents=True, exist_ok=True)
    return out


def settings(sim_cfg: dict) -> list[dict]:
    """Every policy setting of the offline sweep."""
    out = [{"policy": "fixed"}]
    out += [{"policy": "interval", "every": k} for k in sim_cfg["every"]]
    for h in sim_cfg["hold_rounds"]:
        for n in sim_cfg["break_even"]:
            for name in ("rule", "forecast", "rate", "oracle"):
                for protect in (False, True):
                    out.append({"policy": name, "hold_rounds": h, "break_even": n, "protect_suspicious": protect})
    return out


def device_flags(rows: pd.DataFrame) -> np.ndarray:
    """The device model's attack flag per message, in the replay's order (what protect_suspicious reads live)."""
    from src.cloud.model_registry import DeployedModel
    from src.common.schemas import Layer

    model = DeployedModel(Layer.DEVICE)
    return np.asarray(model.model.predict(rows[model.features]), dtype=int)


def simulate() -> None:
    from sklearn.metrics import roc_auc_score

    from src.cloud.train_forecaster import RateForecaster, forecast_metrics, rate_probability, samples
    from src.device.commit_policy import FEATURES, TrafficForecaster, future_rounds, make_policy
    from src.device.commit_policy import simulate as simulate_policy
    from src.device.simulator import RealtimeReplay
    from src.pipeline import load_replay_rows

    suite = load_config("experiments")["suites"][SUITE]
    os.environ["BLOCKIOT_VIEW"] = suite["view"]
    forecaster, rate = TrafficForecaster(), RateForecaster()
    rows_out, quality = [], []
    for n_rows in suite["simulate"]["rows"]:
        rows, _ = load_replay_rows(n_rows)
        for k in suite["replicas"]:
            sim = RealtimeReplay(rows, replicas=k)
            label = sim.rows.Attack_label.to_numpy()
            flags = device_flags(sim.rows)
            future = future_rounds(sim.device_of, suite["batch_size"])
            t0 = time.perf_counter()
            for spec in settings(suite["simulate"]):
                name = spec["policy"]
                policy = make_policy(spec | {"policy": "forecast" if name == "rate" else name},
                                     forecaster=rate if name == "rate" else forecaster, future=future)
                r = simulate_policy(sim, policy, suite["batch_size"], attack_label=label, flags=flags)
                rows_out.append({"rows": n_rows, "devices": len(sim.device_ids), "label": name} | r)
            s = samples(sim, suite["batch_size"], load_config("models")["forecaster"]["max_hold_rounds"])
            x, y = s[FEATURES].to_numpy(), s.y.to_numpy()
            p = forecaster.model.predict_proba(x)[:, 1]
            hard = ((s.msgs_this_round <= 2) & (s.remaining_rounds == 1) & (s.rounds_since_last == 0)).to_numpy()
            q = forecast_metrics(y, p, x)
            if len(np.unique(y[hard])) == 2:
                q |= {"single_msg_samples": float(hard.sum()),
                      "single_msg_roc_auc": float(roc_auc_score(y[hard], p[hard])),
                      "single_msg_rate_roc_auc": float(roc_auc_score(y[hard], rate_probability(x[hard])))}
            quality.append({"rows": n_rows, "devices": len(sim.device_ids)} | q)
            print(f"rows {n_rows:,}, {len(sim.device_ids)} devices: {len(settings(suite['simulate']))} settings in"
                  f" {time.perf_counter() - t0:.0f} s; forecaster AUC {q['roc_auc']:.3f}", flush=True)
    out = out_dir()
    df = pd.DataFrame(rows_out)
    df["held_roots_by_rounds"] = df.held_roots_by_rounds.map(json.dumps)
    df.to_csv(out / "simulation.csv", index=False)
    pd.DataFrame(quality).to_csv(out / "forecast_quality.csv", index=False)
    print(f"results: {out / 'simulation.csv'}, {out / 'forecast_quality.csv'}")


def plan(suite: dict, groups: list[str]) -> list[dict]:
    runs = []
    for g in groups:
        c = suite["groups"][g]
        for seed in c["seeds"]:
            for k in c.get("replicas", suite["replicas"]):
                for spec in c["policies"]:
                    spec = {"policy": spec} if isinstance(spec, str) else dict(spec)
                    if spec["policy"] not in ("fixed", "interval"):
                        spec = suite["policy"] | spec
                    runs.append({"group": g, "seed": seed, "replicas": k, "commit_policy": spec,
                                 "chain": c.get("chain", [suite["chain_backend"], suite["block_period_s"]])})
    return runs


def key(p: dict) -> str:
    spec = p["commit_policy"]
    parts = [spec["policy"], *(f"{k}{v}" for k, v in sorted(spec.items()) if k != "policy")]
    backend, block = p["chain"]
    chain = f"{backend}{'' if block is None else block}"
    return f"{p['group']}_{chain}_{'-'.join(map(str, parts))}_r{p['replicas']}_s{p['seed']}"


def run_groups(groups: list[str] | None, resume: bool) -> None:
    from src.pipeline import run

    suite = load_config("experiments")["suites"][SUITE]
    os.environ["BLOCKIOT_VIEW"] = suite["view"]
    out = out_dir()
    runs_file = out / "runs.jsonl"
    done = set()
    if resume and runs_file.exists():
        done = {r["task3"]["key"] for r in map(json.loads, runs_file.read_text().splitlines())}
    todo = [p for p in plan(suite, groups or list(suite["groups"])) if key(p) not in done]
    for i, p in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {key(p)}", flush=True)
        spec = p["commit_policy"]
        backend, block = p["chain"]
        result = run(experiment=f"task3_{key(p)}", blockchain="batch", n_rows=suite["rows"], edges=suite["edges"],
                     fogs=suite["fogs"], seed=p["seed"], block_time=block, replay=suite["replay"],
                     replicas=p["replicas"], chain_backend=backend, signing=suite["signing"],
                     audit_writes=suite["audit_writes"], batch_size=suite["batch_size"],
                     commit_policy=spec, log=lambda *_: None)   # "fixed" too: the same code path, rows saved
        pd.DataFrame(result.pop("cloud_rows") or []).to_parquet(out / "rows" / f"{key(p)}.parquet", index=False)
        result["task3"] = p | {"key": key(p)}
        with runs_file.open("a") as f:
            f.write(json.dumps(result, default=str) + "\n")
        lat, chain = result["message_latency_ms"]["all"], result["chain"]
        merkle = chain["device_commit"]["gas_total"] + chain["edge_processed"]["gas_total"]
        consensus = result["chain_network"].get("consensus", {})
        print(f"    {result['throughput_eps']:,.0f} msg/s; message latency mean {lat['mean_ms']:,.0f} ms, p95 "
              f"{lat['p95_ms']:,.0f} ms; roots {chain['device_commit']['tx_count']:,}; Merkle gas/msg "
              f"{merkle / result['events_processed']:,.0f}; rejected {result['events_rejected']}"
              + (f"; consistent={consensus['consistent']}" if consensus else ""), flush=True)
    print(f"results: {runs_file}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("simulate")
    p = sub.add_parser("run")
    p.add_argument("--groups", nargs="+", default=None)
    p.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.cmd == "simulate":
        simulate()
    else:
        run_groups(args.groups, args.resume)


if __name__ == "__main__":
    main()
