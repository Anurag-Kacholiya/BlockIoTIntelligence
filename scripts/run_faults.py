"""Fault-tolerance add-on (after final task 2; ADR Experiment F): components fail and recover during a run.

  python scripts/run_faults.py                       # every scenario of suites.final_faults (configs/experiments.yaml)
  python scripts/run_faults.py --scenarios edge_down cloud_down
  python scripts/run_faults.py --resume              # skip runs already in runs.jsonl

Each run is appended to experiments/results/final_faults/runs.jsonl; the messages that reached the cloud (with every
layer's prediction) go to rows/<scenario>_<mode>_<policy>.parquet, to check them against the reference run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import load_config, resolve  # noqa: E402

SUITE = "final_faults"


def plan(suite: dict, scenarios: list[str]) -> list[dict]:
    from src.common.faults import Fault

    runs = []
    for name in scenarios:
        s = suite["scenarios"][name]
        faults = [Fault(f["target"], f.get("down_at_s", suite["down_at_s"]), f.get("up_at_s", suite["up_at_s"]))
                  for f in s["faults"]]
        for mode in s["modes"]:
            for policy in s.get("policies", ["recover"]):
                runs.append({"scenario": name, "mode": mode, "policy": policy, "faults": faults})
    return runs


def key(p: dict) -> str:
    return f"{p['scenario']}_{p['mode']}_{p['policy']}"


def main() -> None:
    from src.pipeline import run

    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", nargs="+", default=None)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    suite = load_config("experiments")["suites"][SUITE]
    os.environ["BLOCKIOT_VIEW"] = suite["view"]
    out = resolve(load_config("base")["paths"]["results"]) / SUITE
    (out / "rows").mkdir(parents=True, exist_ok=True)
    runs_file = out / "runs.jsonl"
    done = set()
    if args.resume and runs_file.exists():
        done = {r["fault_run"]["key"] for r in map(json.loads, runs_file.read_text().splitlines())}
    todo = [p for p in plan(suite, args.scenarios or list(suite["scenarios"])) if key(p) not in done]
    for i, p in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {key(p)}: {[f.target for f in p['faults']] or 'no fault'}", flush=True)
        result = run(experiment=f"faults_{key(p)}", blockchain=p["mode"], n_rows=suite["rows"], edges=suite["edges"],
                     fogs=suite["fogs"], seed=suite["seed"], block_time=suite["block_period_s"],
                     replay=suite["replay"], chain_backend=suite["chain_backend"], audit_writes=suite["audit_writes"],
                     faults=p["faults"], fault_policy=p["policy"], log=lambda *_: None)
        rows = pd.DataFrame(result.pop("cloud_rows"))
        rows.to_parquet(out / "rows" / f"{key(p)}.parquet", index=False)
        result["fault_run"] = {"key": key(p), "scenario": p["scenario"], "mode": p["mode"], "policy": p["policy"]}
        with runs_file.open("a") as f:
            f.write(json.dumps(result, default=str) + "\n")
        m, consensus = result["faults"]["messages"], result["chain_network"]["consensus"]
        print(f"    sent {m['sent']:,}, delivered {m['delivered']:,}, lost {m['lost']:,}, duplicates "
              f"{m['duplicates']}, rejected {m['rejected']}; failovers {len(result['faults']['failovers'])}; "
              f"consistent={consensus['consistent']} at height {consensus['common_height']}", flush=True)
        for entry in result["faults"]["log"]:
            print(f"      {entry}", flush=True)
    print(f"results: {runs_file}")


if __name__ == "__main__":
    main()
