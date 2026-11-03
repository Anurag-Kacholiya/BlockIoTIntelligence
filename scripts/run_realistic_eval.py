"""Dataset v2 evaluation (final task 1, step 8).

  python scripts/run_realistic_eval.py offline                  # deployed real_random / real_time models, test splits
  python scripts/run_realistic_eval.py lodo [--devices d1 d2]   # leave-one-device-out, every normal sensor
  python scripts/run_realistic_eval.py replay [--rows N] [--speed S] [--blockchain batch]

Train the views first:  BLOCKIOT_VIEW=real_time python scripts/train_models.py  (and real_random).
Writes experiments/results/realistic/*.csv and *.json; replay runs also go to exp_*_realistic_replay.csv.
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

from scripts.run_baseline import write_results  # noqa: E402
from src.cloud.evaluate import classification_metrics  # noqa: E402
from src.cloud.model_registry import DeployedModel  # noqa: E402
from src.cloud.train import TARGET_BY_TASK, TrainingData, cap_train_rows, fit  # noqa: E402
from src.common.config import config_hash, load_config, resolve  # noqa: E402
from src.common.schemas import Layer  # noqa: E402
from src.common.storage import git_commit, read_parquet  # noqa: E402
from src.data.preparation.splits import leave_one_device_out  # noqa: E402

LAYERS = ("device", "edge", "fog", "cloud")


def out_dir() -> Path:
    d = resolve(load_config("base")["paths"]["results"]) / "realistic"
    d.mkdir(parents=True, exist_ok=True)
    return d


def task_of(layer: str) -> str:
    return load_config("models")[layer]["task"]


def attack_flags(model, X: pd.DataFrame, task: str) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """(prediction, flagged as attack, P(attack) for binary models)."""
    pred = model.predict(X)
    if task == "binary":
        prob = model.predict_proba(X)[:, list(model.classes_).index(1)]
        return pred, pred.astype(int) == 1, prob
    return pred, pred != "Normal", None


def score(layer: str, model, features: list[str], test: pd.DataFrame, tag: dict) -> tuple[list, list, list]:
    """Metrics in the pipeline's format, per-device false alarms on normal rows, per-class detection."""
    task = task_of(layer)
    pred, flag, prob = attack_flags(model, test[features], task)
    metrics = []
    if task == "binary":
        metrics.append(tag | {"layer": layer, "task": "binary",
                              **classification_metrics(test.Attack_label, pred.astype(int), prob)})
    else:
        metrics.append(tag | {"layer": layer, "task": "multiclass", **classification_metrics(test.Attack_type, pred)})
        metrics.append(tag | {"layer": layer, "task": "binary",
                              **classification_metrics(test.Attack_label, flag.astype(int))})
    normal, attack = (test.Attack_label == 0).to_numpy(), (test.Attack_label == 1).to_numpy()
    by_device = (pd.DataFrame({"device_id": test.device_id.to_numpy()[normal], "false_alarm": flag[normal]})
                 .groupby("device_id").false_alarm.agg(["mean", "size"]).reset_index())
    devices = [tag | {"layer": layer, "device_id": r.device_id, "false_alarm_rate": r.mean, "normal_rows": r.size}
               for r in by_device.itertuples()]
    exact = pred == test.Attack_type.to_numpy() if task == "multiclass" else np.full(len(test), np.nan)
    by_class = (pd.DataFrame({"Attack_type": test.Attack_type.to_numpy()[attack], "detected": flag[attack],
                              "correct_class": exact[attack]})
                .groupby("Attack_type").agg(detected=("detected", "mean"), correct_class=("correct_class", "mean"),
                                            rows=("detected", "size")).reset_index())
    classes = [tag | {"layer": layer, "Attack_type": r.Attack_type, "detection_rate": r.detected,
                      "class_recall": r.correct_class, "attack_rows": r.rows} for r in by_class.itertuples()]
    return metrics, devices, classes


def offline(views: list[str]) -> None:
    paths = load_config("datasets")["paths"]
    metrics, devices, classes, models = [], [], [], {}
    for view in views:
        os.environ["BLOCKIOT_VIEW"] = view            # selects the view's registry (src/common/config.py)
        test = read_parquet(resolve(paths["splits"]) / view / "test.parquet")
        for layer in LAYERS:
            deployed = DeployedModel(Layer[layer.upper()])
            m, d, c = score(layer, deployed.model, deployed.features, test, {"view": view})
            metrics += m
            devices += d
            classes += c
            models[f"{view}/{layer}"] = deployed.model_id
            print(f"{view:12s} {layer:6s} " + "  ".join(f"{r['task']} f1={r['f1_macro']:.4f}" for r in m), flush=True)
    out = out_dir()
    pd.DataFrame(metrics).to_csv(out / "offline_metrics.csv", index=False)
    pd.DataFrame(devices).to_csv(out / "offline_false_alarms_by_device.csv", index=False)
    pd.DataFrame(classes).to_csv(out / "offline_detection_by_class.csv", index=False)
    (out / "offline.json").write_text(json.dumps(
        {"models": models, "git_commit": git_commit(), "config_hash": config_hash("datasets", "models")}, indent=2))


def lodo(devices: list[str] | None, seed: int) -> None:
    """Split C: per sensor, train every layer without its normal traffic; measure false alarms on it."""
    cfg, paths = load_config("models"), load_config("datasets")["paths"]
    canonical = read_parquet(resolve(paths["splits"]) / "real" / "canonical.parquet")
    cuts = read_parquet(resolve(paths["splits"]) / "real" / "session_cuts.parquet")
    manifest = json.loads((resolve(paths["manifests"]) / "real_time_preparation.json").read_text())
    os.environ["BLOCKIOT_VIEW"] = "real_time"
    cloud_family = DeployedModel(Layer.CLOUD).record["family"]      # the family selected on the time split
    devices = devices or sorted(canonical.loc[canonical.Attack_label == 0, "device_id"].unique())

    rows, classes, per_device = [], [], []
    for device in devices:
        t0 = time.time()
        parts = leave_one_device_out(canonical, cuts, device)
        data = TrainingData(
            view=f"real_lodo/{device}", train=cap_train_rows(parts["train"], seed), validation=parts["validation"],
            train_hash="", numeric=manifest["cleaning"]["numeric_columns"],
            categorical=manifest["cleaning"]["categorical_columns"],
            layer_features={k: v["features"] for k, v in manifest["views"].items()},
        )
        test = parts["test"]
        unseen = ((test.Attack_label == 0) & (test.device_id == device)).to_numpy()
        seen = ((test.Attack_label == 0) & (test.device_id != device)).to_numpy()
        attack = (test.Attack_label == 1).to_numpy()
        normal = (test.Attack_label == 0).to_numpy()
        for layer in LAYERS:
            if layer == "cloud":
                family, params = cloud_family, cfg["cloud"]["candidates"][cloud_family]
            else:
                family, params = cfg[layer]["family"], cfg[layer]["params"]
            task = task_of(layer)
            features = data.layer_features[layer]
            model, _ = fit(family, params, features, data, TARGET_BY_TASK[task], seed)
            pred, flag, _ = attack_flags(model, test[features], task)
            rows.append({
                "held_out_device": device, "layer": layer, "family": family,
                "unseen_device_false_alarm_rate": float(flag[unseen].mean()), "unseen_normal_rows": int(unseen.sum()),
                "seen_devices_false_alarm_rate": float(flag[seen].mean()), "seen_normal_rows": int(seen.sum()),
                "attack_detection_rate": float(flag[attack].mean()), "attack_rows": int(attack.sum()),
                "train_rows": len(data.train),
            })
            far = pd.DataFrame({"device_id": test.device_id.to_numpy()[normal], "fa": flag[normal]}) \
                .groupby("device_id").fa.agg(["mean", "size"])
            per_device += [{"held_out_device": device, "layer": layer, "device_id": d, "unseen": d == device,
                            "false_alarm_rate": float(r["mean"]), "normal_rows": int(r["size"])}
                           for d, r in far.iterrows()]
            if task == "multiclass":   # what the unseen sensor's normal traffic is mistaken for
                mistaken = pd.Series(pred[unseen & flag]).value_counts()
                classes += [{"held_out_device": device, "layer": layer, "predicted_as": k, "rows": int(v)}
                            for k, v in mistaken.items()]
            print(f"{device:28s} {layer:6s} unseen FAR={rows[-1]['unseen_device_false_alarm_rate']:.4f} "
                  f"seen FAR={rows[-1]['seen_devices_false_alarm_rate']:.4f} "
                  f"attack DR={rows[-1]['attack_detection_rate']:.4f}", flush=True)
        print(f"  fold {device}: {time.time() - t0:.0f}s", flush=True)

    out = out_dir()
    suffix = "" if devices is None or len(devices) > 1 else f"_{devices[0]}"
    pd.DataFrame(rows).to_csv(out / f"lodo{suffix}.csv", index=False)
    pd.DataFrame(classes).to_csv(out / f"lodo_mistaken_for{suffix}.csv", index=False)
    pd.DataFrame(per_device).to_csv(out / f"lodo_false_alarms_by_device{suffix}.csv", index=False)
    (out / f"lodo{suffix}.json").write_text(json.dumps(
        {"seed": seed, "cloud_family": cloud_family, "canonical_hash": manifest["canonical_hash"],
         "max_train_rows": cfg["training"].get("max_train_rows"), "git_commit": git_commit(),
         "config_hash": config_hash("datasets", "models")}, indent=2))


def replay(rows: int, speed: float, blockchain: str | None, seed: int, edges: int, fogs: int) -> None:
    from src.pipeline import run

    os.environ["BLOCKIOT_VIEW"] = "real_time"
    result = run(experiment="realistic_replay", blockchain=blockchain, n_rows=rows, replay="realistic", speed=speed,
                 seed=seed, edges=edges, fogs=fogs)
    path = write_results(result, "realistic_replay")
    print(f"processed {result['events_processed']:,}/{result['events_in']:,} events from "
          f"{result['topology']['devices']} devices; replay span {result['replay']['replay_seconds']:.1f}s "
          f"at speed {speed}; throughput {result['throughput_eps']:,.0f} events/s; alerts {result['alerts']:,}")
    print(pd.DataFrame(result["accuracy"])[["layer", "task", "accuracy", "f1_macro"]].round(4).to_string(index=False))
    print("cloud false alarms by device:",
          {k: round(v, 4) for k, v in result["breakdown"]["false_alarm_rate_by_device"]["cloud"].items()})
    print(f"full result: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("offline")
    p.add_argument("--views", nargs="+", default=["real_random", "real_time"])
    p = sub.add_parser("lodo")
    p.add_argument("--devices", nargs="+", default=None)
    p.add_argument("--seed", type=int, default=42)
    p = sub.add_parser("replay")
    p.add_argument("--rows", type=int, default=200_000)
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--blockchain", choices=["per_event", "batch"], default=None)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--edges", type=int, default=None)
    p.add_argument("--fogs", type=int, default=None)
    args = parser.parse_args()
    if args.cmd == "offline":
        offline(args.views)
    elif args.cmd == "lodo":
        lodo(args.devices, args.seed)
    else:
        replay(args.rows, args.speed, args.blockchain, args.seed, args.edges, args.fogs)


if __name__ == "__main__":
    main()
