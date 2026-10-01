"""Blockchain-enabled four-layer run on a fresh private Anvil chain (ADR Phases 2-7, §11.1 "Proposed").

  python scripts/run_blockchain.py --mode per_event --rows 20000
  python scripts/run_blockchain.py --mode batch     --rows 200000

Writes experiments/results/exp_accuracy_blockchain.csv, exp_latency_blockchain.csv and <run_id>.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_baseline import write_results  # noqa: E402
from src.pipeline import run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["per_event", "batch"], default="per_event")
    parser.add_argument("--rows", type=int, default=20000)
    parser.add_argument("--devices", type=int, default=None)
    parser.add_argument("--edges", type=int, default=None)
    parser.add_argument("--fogs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--block-time", type=float, default=None, help="seconds; default automine")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    result = run(experiment=f"blockchain_{args.mode}", blockchain=args.mode, n_rows=args.rows,
                 devices=args.devices, edges=args.edges, fogs=args.fogs, batch_size=args.batch_size,
                 block_time=args.block_time, seed=args.seed)
    path = write_results(result, "blockchain")

    print(f"\nprocessed {result['events_processed']:,}/{result['events_in']:,} events "
          f"at {result['throughput_eps']:,.0f} events/s; rejected {result['events_rejected']}")
    print(pd.DataFrame(result["accuracy"])[["layer", "task", "accuracy", "f1_macro"]].round(4).to_string(index=False))
    print("per-event latency (ms):", {k: round(v, 4) for k, v in result["latency_per_event_ms"].items()})
    print(pd.DataFrame(result["chain"]).T.round(2).to_string())
    print("resources:", {k: round(v, 2) for k, v in result["resources"].items()})
    print(f"full result: {path}")


if __name__ == "__main__":
    main()
