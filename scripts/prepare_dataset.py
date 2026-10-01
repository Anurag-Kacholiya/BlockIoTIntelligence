"""Build the canonical Edge-IIoTset splits and Device/Edge/Fog/Cloud views (ADR §2A steps 1-11).

  python scripts/prepare_dataset.py              # primary view from configs/datasets.yaml (DNN)
  python scripts/prepare_dataset.py --view ml    # the 157,800-row ML view

Outputs:
  data/splits/<view>/{train,validation,test}.parquet       canonical cleaned rows + provenance
  data/prepared/<layer>/<view>/{train,validation,test}.parquet
  data/metadata/<view>_feature_removal.csv                  every removed column with its reason
  experiments/manifests/<view>_preparation.json             lineage, counts, hashes, seed, commit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import config_hash, load_config, resolve  # noqa: E402
from src.common.logging import get_logger  # noqa: E402
from src.common.storage import git_commit, write_parquet  # noqa: E402
from src.data.ingestion.edge_iiotset import load  # noqa: E402
from src.data.preparation.clean import clean  # noqa: E402
from src.data.preparation.feature_groups import view_spec  # noqa: E402
from src.data.preparation.splits import cross_split_overlap, split  # noqa: E402
from src.data.validation.schema import validate  # noqa: E402

PREPROCESSING_VERSION = "1.0.0"
log = get_logger("prepare_dataset")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--view", choices=["ml", "dnn"], default=None)
    parser.add_argument("--nrows", type=int, default=None, help="read only the first N rows (smoke tests)")
    args = parser.parse_args()

    cfg = load_config("datasets")
    view = args.view or cfg["edge_iiotset"]["primary"]
    paths = {k: resolve(v) for k, v in cfg["paths"].items()}

    raw, provenance = load(view, nrows=args.nrows)
    log.info("loaded", extra={"view": view, "rows": len(raw)})
    validation_report = validate(raw)
    df, removals, clean_report = clean(raw)
    log.info("cleaned", extra=clean_report | {"numeric_columns": len(clean_report["numeric_columns"])})

    parts = split(df)
    overlap = cross_split_overlap(parts)
    seed = cfg["edge_iiotset"]["split"]["seed"]
    lineage = {
        "source": provenance, "preprocessing_version": PREPROCESSING_VERSION, "seed": seed,
        "config_hash": config_hash("datasets"),
    }

    files = {}
    for name, part in parts.items():
        rec = write_parquet(part, paths["splits"] / view / f"{name}.parquet", lineage | {"split": name})
        files[f"splits/{name}"] = rec["file_hash"]

    specs = view_spec(clean_report["numeric_columns"], clean_report["categorical_columns"])
    for layer, spec in specs.items():
        cols = ["source_row_id", *spec["features"], *spec["targets"]]
        for name, part in parts.items():
            rec = write_parquet(
                part[cols], paths["prepared"] / layer / view / f"{name}.parquet",
                lineage | {"layer": layer, "split": name, "targets": spec["targets"]},
            )
            files[f"{layer}/{name}"] = rec["file_hash"]

    paths["metadata"].mkdir(parents=True, exist_ok=True)
    pd.DataFrame(removals).to_csv(paths["metadata"] / f"{view}_feature_removal.csv", index=False)

    manifest = lineage | {
        "git_commit": git_commit(),
        "validation": validation_report,
        "cleaning": clean_report,
        "split_rows": {n: len(p) for n, p in parts.items()},
        "split_class_counts": {n: p["Attack_type"].value_counts().to_dict() for n, p in parts.items()},
        "cross_split_feature_overlap": overlap,
        "views": {k: {"n_features": len(v["features"]), **v} for k, v in specs.items()},
        "file_hashes": files,
    }
    paths["manifests"].mkdir(parents=True, exist_ok=True)
    out = paths["manifests"] / f"{view}_preparation.json"
    out.write_text(json.dumps(manifest, indent=2, default=str))
    log.info("done", extra={"manifest": str(out), "split_rows": manifest["split_rows"], "overlap": overlap})


if __name__ == "__main__":
    main()
