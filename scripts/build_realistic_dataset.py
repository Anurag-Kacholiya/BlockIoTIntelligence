"""Build dataset v2 ("realistic") from the event tables (final task 1, step 5).

Rows    every labelled packet of the 24 captures (src/data/preparation/realistic.py), with its real timestamp,
        session and device as metadata only, never as features.
Clean   the mid-term rules: leakage columns are already gone (realistic schema at extraction); constant columns
        are dropped; rows whose feature vector occurs under more than one class are reported. Exact duplicates are
        dropped per device and class *within each time partition*, keeping the earliest: a packet repeated later is
        a real repeat that a deployed model must classify (dropping it would leave a flood such as DDoS_ICMP with
        almost no test rows). Repeats across partitions are reported per class. Split A then applies the mid-term
        rule exactly: one row per distinct feature vector and label.
Sample  at most `max_rows_per_stratum` rows per (class, device), uniformly over time. Each capture is exactly one
        (class, device) stratum, so this is a per-capture cap.
Splits  A random 70/15/15 stratified by class and device       -> data/splits/real_random
        B time-based: per-session cut points computed on the
          full traffic before de-duplication and sampling     -> data/splits/real_time
        C leave-one-device-out, derived at experiment time from data/splits/real/canonical.parquet
          and session_cuts.parquet (src/data/preparation/splits.py)

  python scripts/build_realistic_dataset.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import config_hash, load_config, resolve  # noqa: E402
from src.common.crypto import hash_object  # noqa: E402
from src.common.storage import git_commit, write_parquet  # noqa: E402
from src.data.preparation.clean import TARGETS, feature_columns  # noqa: E402
from src.data.preparation.feature_groups import view_spec  # noqa: E402
from src.data.preparation.realistic import captures, events_path, read_events, source_row_ids  # noqa: E402
from src.data.preparation.splits import (  # noqa: E402
    PARTITIONS,
    cross_split_overlap,
    leave_one_device_out,
    session_cuts,
    split,
    time_partition,
    time_split,
)

PREPROCESSING_VERSION = "2.0.0"


def label_conflicts(df: pd.DataFrame, features: list[str]) -> pd.Series:
    """Per class: rows whose exact feature vector also occurs under another class."""
    h = pd.util.hash_pandas_object(df[features], index=False)
    conflict = df.groupby(h.to_numpy()).Attack_type.transform("nunique").to_numpy() > 1
    return df.Attack_type[conflict].value_counts()


def seen_in_train_by_class(parts: dict[str, pd.DataFrame]) -> dict[str, float]:
    """Per class: share of test rows whose exact feature vector also occurs in train (real repeats over time)."""
    cols = feature_columns(parts["train"])
    train = set(pd.util.hash_pandas_object(parts["train"][cols], index=False))
    seen = pd.util.hash_pandas_object(parts["test"][cols], index=False).isin(train).to_numpy()
    return pd.Series(seen).groupby(parts["test"].Attack_type.to_numpy()).mean().round(4).to_dict()


def main() -> None:
    t0 = time.time()
    cfg = load_config("datasets")
    real, ds = cfg["realistic"], cfg["realistic"]["dataset"]
    seed, cap = ds["seed"], ds["max_rows_per_stratum"]
    categorical = real["feature_schema"]["categorical_columns"]
    paths = {k: resolve(v) for k, v in cfg["paths"].items()}

    samples, cuts, per_capture, sources, hashes = [], [], {}, {}, []
    for capture, spec in captures().items():
        df = read_events(capture)
        features = feature_columns(df)
        numeric = [c for c in features if c not in categorical]
        cuts.append(session_cuts(df))                     # on the full traffic: dedupe/sampling cannot move them
        df["time_partition"] = time_partition(df, cuts[-1])
        rows_in = len(df)

        df[numeric] = df[numeric].replace([np.inf, -np.inf], np.nan)
        bad = df[numeric].isna().any(axis=1)
        df = df[~bad]
        dup = df.duplicated(subset=features + TARGETS + ["time_partition"])   # keeps the earliest (time order)
        df = df[~dup]
        hashes.append(pd.DataFrame({"h": pd.util.hash_pandas_object(df[features], index=False).to_numpy(),
                                    "Attack_type": spec["label"]}))
        rows_dedup = len(df)
        if len(df) > cap:
            df = df.sample(n=cap, random_state=seed).sort_index()
        df.insert(0, "source_row_id", source_row_ids(capture, df.packet_no))
        samples.append(df)

        manifest = json.loads(events_path(capture).with_suffix(".manifest.json").read_text())
        sources[capture] = manifest["output_sha256"]
        per_capture[capture] = {
            "device_id": spec_device(df), "label": spec["label"], "kind": spec["kind"],
            "rows_labelled": rows_in, "rows_dropped_unparseable_or_inf": int(bad.sum()),
            "rows_dropped_duplicate": int(dup.sum()), "rows_after_dedup": rows_dedup, "rows_sampled": len(df),
            "sessions": len(cuts[-1]),
        }
        print(f"{capture:22s} labelled={rows_in:>9,} after_dedup={rows_dedup:>9,} sampled={len(df):>7,}", flush=True)

    canonical = pd.concat(samples, ignore_index=True)
    del samples
    cuts = pd.concat(cuts, ignore_index=True)
    if not canonical.source_row_id.is_unique:
        raise ValueError("source_row_id is not unique")

    # Label conflicts over every de-duplicated row (before sampling) and in the sample, as in the mid-term report.
    all_unique = pd.concat(hashes, ignore_index=True)
    conflict_unique = all_unique.groupby("h").Attack_type.transform("nunique") > 1
    features = feature_columns(canonical)
    constant = [c for c in features if canonical[c].nunique(dropna=False) <= 1]
    canonical = canonical.drop(columns=constant)
    features = [c for c in features if c not in constant]
    numeric = [c for c in features if c not in categorical]
    categorical = [c for c in categorical if c in features]
    if not (time_partition(canonical, cuts) == canonical.time_partition.to_numpy()).all():
        raise ValueError("time partitions differ from the session cuts")

    removals = [{"column": c, "reason": "publisher drop list: identifier/timestamp/port/free-text payload (leakage)"}
                for c in cfg["edge_iiotset"]["leakage_drop_columns"]]
    removals += [{"column": c, "reason": "free text (query name); its length dns.qry.name.len is kept"}
                 for c in real["feature_schema"]["extra_drop_columns"]]
    removals += [{"column": c, "reason": "constant across dataset v2 (no information)"} for c in constant]
    paths["metadata"].mkdir(parents=True, exist_ok=True)
    pd.DataFrame(removals).to_csv(paths["metadata"] / "real_feature_removal.csv", index=False)

    source = {
        "source_file": "data/standardized/events/<capture>.parquet (24 Edge-IIoTset captures, tshark re-extraction)",
        "source_hash": hash_object(sources), "captures": sources,
    }
    lineage = {"source": source, "preprocessing_version": PREPROCESSING_VERSION, "seed": seed,
               "config_hash": config_hash("datasets")}
    cleaning = {
        "rows_labelled": sum(c["rows_labelled"] for c in per_capture.values()),
        "rows_dropped_unparseable_or_inf": sum(c["rows_dropped_unparseable_or_inf"] for c in per_capture.values()),
        "rows_dropped_duplicate": sum(c["rows_dropped_duplicate"] for c in per_capture.values()),
        "rows_after_dedup": len(all_unique),
        "rows_after_dedup_with_label_conflict": int(conflict_unique.sum()),
        "rows_after_dedup_with_label_conflict_by_class":
            all_unique.Attack_type[conflict_unique].value_counts().to_dict(),
        "max_rows_per_stratum": cap,
        "rows_out": len(canonical),
        "rows_with_label_conflict": label_conflicts(canonical, features).to_dict(),
        "constant_columns_dropped": constant,
        "numeric_columns": numeric,
        "categorical_columns": categorical,
    }
    del all_unique, hashes

    out = paths["splits"] / "real"
    files = {"canonical": write_parquet(canonical, out / "canonical.parquet", lineage)["file_hash"],
             "session_cuts": write_parquet(cuts, out / "session_cuts.parquet", lineage)["file_hash"]}
    specs = view_spec(numeric, categorical)

    random_base = canonical.drop_duplicates(subset=features + TARGETS)    # the mid-term rule, across devices
    schemes = {
        "real_random": ("A: random 70/15/15, stratified by class and device; one row per distinct vector and label",
                        split(random_base, seed, stratify=ds["random_split_stratify_on"])),
        "real_time": ("B: per session, earliest 70% train / next 15% validation / latest 15% test",
                      time_split(canonical, cuts)),
    }
    for view, (description, parts) in schemes.items():
        hashes_view = {}
        for name in PARTITIONS:
            rec = write_parquet(parts[name], paths["splits"] / view / f"{name}.parquet", lineage | {"split": name})
            hashes_view[f"splits/{name}"] = rec["file_hash"]
        manifest = lineage | {
            "git_commit": git_commit(), "scheme": description, "canonical_hash": files["canonical"],
            "cleaning": cleaning,
            "split_rows": {n: len(p) for n, p in parts.items()},
            "split_class_counts": {n: p.Attack_type.value_counts().to_dict() for n, p in parts.items()},
            "split_device_counts": {n: p[p.Attack_label == 0].device_id.value_counts().to_dict()
                                    for n, p in parts.items()},
            "cross_split_feature_overlap": cross_split_overlap(parts),
            "test_share_seen_in_train_by_class": seen_in_train_by_class(parts),
            "views": {k: {"n_features": len(v["features"]), **v} for k, v in specs.items()},
            "file_hashes": hashes_view,
        }
        (paths["manifests"] / f"{view}_preparation.json").write_text(json.dumps(manifest, indent=2, default=str))
        print(f"{view}: {manifest['split_rows']}  overlap={manifest['cross_split_feature_overlap']}", flush=True)

    normal_devices = sorted(canonical.loc[canonical.Attack_label == 0, "device_id"].unique())
    lodo = {}
    for device in normal_devices:
        parts = leave_one_device_out(canonical, cuts, device)
        test = parts["test"]
        lodo[device] = {"train": len(parts["train"]), "validation": len(parts["validation"]), "test": len(test),
                        "test_unseen_normal": int(((test.Attack_label == 0) & (test.device_id == device)).sum())}

    summary = lineage | {
        "git_commit": git_commit(), "cleaning": cleaning, "per_capture": per_capture, "file_hashes": files,
        "class_counts": canonical.Attack_type.value_counts().to_dict(),
        "normal_device_counts": canonical[canonical.Attack_label == 0].device_id.value_counts().to_dict(),
        "time_partition_counts": canonical.time_partition.value_counts().to_dict(),
        "sessions": cuts.to_dict("records"),
        "leave_one_device_out": lodo,
        "seconds": round(time.time() - t0, 1),
    }
    (paths["manifests"] / "realistic_dataset.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"canonical rows={len(canonical):,} features={len(features)} constant_dropped={constant} "
          f"({summary['seconds']}s)")


def spec_device(df: pd.DataFrame) -> str:
    devices = df.device_id.unique()
    if len(devices) != 1:
        raise ValueError(f"a capture must map to one device, got {list(devices)}")
    return str(devices[0])


if __name__ == "__main__":
    main()
