"""Accuracy under data-integrity attack — the experiment behind the paper's "accuracy is higher with
blockchain" claim (Singh et al. §4.2, Fig. 7a), made measurable.

An in-flight attacker between device and edge camouflages a fraction p of real attack events by
replacing their feature values with those of a real normal event (evasion by tampering). Without
the ledger the models only see "normal" traffic; with it, the edge recomputes the payload hash,
finds it differs from the on-chain commitment, rejects the event and raises an integrity alert.

Attack detection counts an attack event as caught if it is rejected for integrity OR the cloud
classifies it as an attack.

  python scripts/run_integrity_accuracy.py [--rows 20000] [--mode batch]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import load_config, resolve  # noqa: E402
from src.pipeline import run  # noqa: E402


class Camouflage:
    """Replaces the features of a fraction of attack events with those of a recently seen normal event."""

    def __init__(self, rate: float, seed: int):
        self.rate, self.rng = rate, random.Random(seed)
        self.normal_pool: list[dict] = []
        self.truth: dict[str, dict] = {}

    def __call__(self, batch: list[dict]) -> list[dict]:
        for e in batch:
            if e["attack_label"] == 0:
                self.normal_pool.append(dict(e["values"]))
                self.normal_pool = self.normal_pool[-500:]
        for e in batch:
            tampered = e["attack_label"] == 1 and self.normal_pool and self.rng.random() < self.rate
            if tampered:
                e["values"] = dict(self.rng.choice(self.normal_pool))
            self.truth[e["event_id"]] = {"label": e["attack_label"], "tampered": bool(tampered)}
        return batch


def score(result: dict, attacker: Camouflage) -> dict:
    predicted = {r["event_id"]: r["cloud_pred"] != "Normal" for r in result["cloud_rows"]}
    rejected = {eid for eid, _ in result["rejected"]}
    rows = pd.DataFrame([{"event_id": k, **v} for k, v in attacker.truth.items()])
    rows["caught"] = rows.event_id.map(lambda x: x in rejected or predicted.get(x, False))
    attacks, normals = rows[rows.label == 1], rows[rows.label == 0]
    tampered = attacks[attacks.tampered]
    return {
        "attack_detection_rate": attacks.caught.mean(),
        "tampered_attack_detection_rate": tampered.caught.mean() if len(tampered) else float("nan"),
        "normal_false_positive_rate": normals.caught.mean(),
        "integrity_rejections": len(rejected),
        "tampered_events": int(rows.tampered.sum()),
        "throughput_eps": result["throughput_eps"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=20000)
    parser.add_argument("--mode", choices=["per_event", "batch"], default="batch")
    parser.add_argument("--rates", default="0,0.1,0.25,0.5")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    records = []
    for rate in [float(x) for x in args.rates.split(",")]:
        for mode in (None, args.mode):
            attacker = Camouflage(rate, args.seed)
            result = run(experiment="integrity_accuracy", blockchain=mode, n_rows=args.rows, seed=args.seed,
                         interceptor=attacker, log=lambda *_: None)
            rec = {"tamper_rate": rate, "mode": mode or "baseline", **score(result, attacker)}
            records.append(rec)
            print({k: round(v, 4) if isinstance(v, float) else v for k, v in rec.items()}, flush=True)

    out = resolve(load_config("base")["paths"]["results"])
    pd.DataFrame(records).to_csv(out / "exp_integrity_accuracy.csv", index=False)
    (out / "exp_integrity_accuracy.json").write_text(json.dumps({"args": vars(args), "records": records}, indent=2))


if __name__ == "__main__":
    main()
