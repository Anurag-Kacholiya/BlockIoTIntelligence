"""Phase 1 baseline: the four-layer pipeline with the blockchain switched off (ADR §10 Phase 1, §11.1).

  python scripts/run_baseline.py [--rows 200000] [--devices 10] [--edges 2] [--fogs 1]

Writes experiments/results/exp_accuracy_baseline.csv, exp_latency_baseline.csv and <run_id>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import load_config, resolve  # noqa: E402
from src.pipeline import run  # noqa: E402


def write_results(result: dict, suffix: str) -> Path:
    out = resolve(load_config("base")["paths"]["results"])
    out.mkdir(parents=True, exist_ok=True)
    meta = {"run_id": result["run_id"], "experiment": result["experiment"], "blockchain": result["blockchain"],
            "seed": result["reproducibility"]["seed"], "events": result["events_processed"], **result["topology"]}

    acc = pd.DataFrame([meta | row for row in result["accuracy"]])
    lat = pd.DataFrame([
        meta | {"stage": stage, **stats, "per_event_ms": result["latency_per_event_ms"].get(stage)}
        for stage, stats in result["latency_ms"].items()
    ])
    for name, df in (("accuracy", acc), ("latency", lat)):
        path = out / f"exp_{name}_{suffix}.csv"
        df.to_csv(path, mode="a", header=not path.exists(), index=False)
    run_file = out / f"{result['run_id']}.json"
    run_file.write_text(json.dumps(result, indent=2, default=str))
    return run_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=None)
    parser.add_argument("--devices", type=int, default=None)
    parser.add_argument("--edges", type=int, default=None)
    parser.add_argument("--fogs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    result = run(experiment="baseline", blockchain=None, n_rows=args.rows, devices=args.devices,
                 edges=args.edges, fogs=args.fogs, batch_size=args.batch_size, seed=args.seed)
    path = write_results(result, "baseline")

    print(f"\nprocessed {result['events_processed']:,}/{result['events_in']:,} events "
          f"at {result['throughput_eps']:,.0f} events/s; rejected {result['events_rejected']}")
    print(pd.DataFrame(result["accuracy"])[["layer", "task", "accuracy", "precision_macro", "recall_macro",
                                           "f1_macro"]].round(4).to_string(index=False))
    print("per-event latency (ms):", {k: round(v, 4) for k, v in result["latency_per_event_ms"].items()})
    print("resources:", {k: round(v, 2) for k, v in result["resources"].items()})
    print(f"full result: {path}")


if __name__ == "__main__":
    main()
