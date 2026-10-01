"""Run an experiment suite from configs/experiments.yaml and append every run to one JSONL file.

  python scripts/run_experiments.py --suite presentation1 [--only comparison|scaling]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import load_config, resolve  # noqa: E402
from src.pipeline import run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="presentation1")
    parser.add_argument("--only", choices=["comparison", "scaling"], default=None)
    args = parser.parse_args()
    suite = load_config("experiments")["suites"][args.suite]
    out_dir = resolve(load_config("base")["paths"]["results"]) / args.suite
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_file = out_dir / "runs.jsonl"

    plan = []
    if args.only in (None, "comparison"):
        c = suite["comparison"]
        plan += [dict(group="comparison", mode=m, seed=s, rows=c["rows"], devices=c["devices"], edges=c["edges"],
                      fogs=c["fogs"]) for s in c["seeds"] for m in c["modes"]]
    if args.only in (None, "scaling"):
        c = suite["scaling"]
        plan += [dict(group="scaling", mode=m, seed=c["seed"], rows=c["rows"], devices=d, edges=c["edges"],
                      fogs=c["fogs"]) for d in c["devices"] for m in c["modes"]]

    for i, p in enumerate(plan, 1):
        print(f"[{i}/{len(plan)}] {p}", flush=True)
        result = run(experiment=f"{p['group']}_{p['mode']}", blockchain=None if p["mode"] == "baseline" else p["mode"],
                     n_rows=p["rows"], devices=p["devices"], edges=p["edges"], fogs=p["fogs"], seed=p["seed"],
                     log=lambda *_: None)
        result["group"], result["mode"] = p["group"], p["mode"]
        with runs_file.open("a") as f:
            f.write(json.dumps(result, default=str) + "\n")
        print(f"    {result['throughput_eps']:,.0f} ev/s, e2e/event "
              f"{result['latency_per_event_ms']['batch_end_to_end']:.3f} ms", flush=True)
    print(f"results: {runs_file}")


if __name__ == "__main__":
    main()
