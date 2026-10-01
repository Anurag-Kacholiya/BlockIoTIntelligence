"""Download, verify, and snapshot the Edge-IIoTset dataset (Phase 0 / Dataset Plan step 1).

Source of record: IEEE DataPort, DOI 10.21227/MBC1-1H68 (login required).
Download mirror:  the dataset authors' own Kaggle release (same files), which
                  allows scripted, unauthenticated download of a pinned version.

Each file is fetched individually, so an interrupted run resumes at the next
missing file.

Outputs (all under data/, never edited after creation):
  data/external/edge_iiotset/downloads/             files exactly as served (large ones zipped)
  data/external/edge_iiotset/raw/                   extracted files, original paths kept
  data/metadata/checksums.sha256                    SHA-256 of every archive and extracted file
  data/metadata/dataset_card.yaml                   provenance + row/column counts

Usage:
  python scripts/download_edge_iiotset.py              # all 52 files (~11 GB extracted)
  python scripts/download_edge_iiotset.py --essential  # selected ML/DNN CSVs + docs only
  python scripts/download_edge_iiotset.py --verify     # re-check files against checksums
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote

import requests

KAGGLE_REF = "mohamedamineferrag/edgeiiotset-cyber-security-dataset-of-iot-iiot"
KAGGLE_VERSION = 5  # "Data Update 2022/03/18" — latest release; pin for reproducibility
IEEE_DOI = "10.21227/MBC1-1H68"

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "data" / "external" / "edge_iiotset"
RAW_DIR = DATASET_DIR / "raw"
DOWNLOAD_DIR = DATASET_DIR / "downloads"
API = "https://www.kaggle.com/api/v1/datasets"
METADATA_DIR = ROOT / "data" / "metadata"
CHECKSUMS = METADATA_DIR / "checksums.sha256"
CARD = METADATA_DIR / "dataset_card.yaml"

# Files the experiments cannot run without, plus the publisher's documentation.
ESSENTIAL = [
    "Edge-IIoTset dataset/Selected dataset for ML and DL/ML-EdgeIIoT-dataset.csv",
    "Edge-IIoTset dataset/Selected dataset for ML and DL/DNN-EdgeIIoT-dataset.csv",
    "Edge_IIoTset__DatasetFL.pdf",
    "Readme.txt",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def list_files() -> list[str]:
    names, token = [], None
    while True:
        r = requests.get(f"{API}/list/{KAGGLE_REF}", params={"pageToken": token} if token else {}, timeout=60)
        r.raise_for_status()
        body = r.json()
        names += [f["name"] for f in body.get("datasetFiles") or []]
        if not body.get("hasNextPageToken"):
            return names
        token = body["nextPageToken"]


def fetch(name: str) -> None:
    """Download one dataset file into downloads/ and place it at raw/<name>.

    Kaggle serves larger files as a single-member zip and small ones as-is.
    """
    target = RAW_DIR / name
    if target.exists():
        print(f"have {name}")
        return
    base = DOWNLOAD_DIR / Path(name).name
    blob = next((p for p in (base.with_name(base.name + ".zip"), base) if p.exists()), None)
    if blob is None:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        tmp = base.with_name(base.name + ".part")
        url = f"{API}/download/{KAGGLE_REF}/{quote(name, safe='')}"
        with requests.get(url, params={"datasetVersionNumber": KAGGLE_VERSION}, stream=True, timeout=120) as r:
            r.raise_for_status()
            with tmp.open("wb") as f:
                for chunk in r.iter_content(1 << 22):
                    f.write(chunk)
        blob = base.with_name(base.name + ".zip") if zipfile.is_zipfile(tmp) else base
        tmp.rename(blob)

    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    if zipfile.is_zipfile(blob):
        with zipfile.ZipFile(blob) as z:
            if z.testzip():
                sys.exit(f"corrupt archive: {blob}")
            (member,) = z.namelist()
            with z.open(member) as src, partial.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 22)
    else:
        shutil.copyfile(blob, partial)
    partial.rename(target)
    print(f"ok   {name}")


def csv_shape(path: Path) -> tuple[int, int]:
    """Row count (excluding header) and column count, streaming so multi-GB files are fine."""
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = sum(1 for _ in reader)
    return rows, len(header)


def write_manifest() -> None:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in RAW_DIR.rglob("*") if p.is_file() and p.name != ".DS_Store")

    lines = [f"{sha256(z)}  {z.relative_to(ROOT)}" for z in sorted(DOWNLOAD_DIR.glob("*.zip"))]
    entries = []
    for p in files:
        digest = sha256(p)
        rel = p.relative_to(ROOT)
        lines.append(f"{digest}  {rel}")
        entry = {"path": str(rel), "bytes": p.stat().st_size, "sha256": digest}
        if p.suffix == ".csv":
            entry["rows"], entry["columns"] = csv_shape(p)
        entries.append(entry)
        print(f"hashed {rel}")
    CHECKSUMS.write_text("\n".join(lines) + "\n")

    out = [
        "dataset_name: Edge-IIoTset",
        "title: 'Edge-IIoTset: A New Comprehensive Realistic Cyber Security Dataset of IoT and IIoT Applications for Centralized and Federated Learning'",
        "authors: [Mohamed Amine Ferrag, Othmane Friha, Djallel Hamouda, Leandros Maglaras, Helge Janicke]",
        "citation: 'M. A. Ferrag et al., IEEE Access, vol. 10, pp. 40281-40306, 2022, doi:10.1109/ACCESS.2022.3165809'",
        f"source_of_record: {{publisher: IEEE DataPort, doi: '{IEEE_DOI}'}}",
        f"download_mirror: {{host: Kaggle, ref: '{KAGGLE_REF}', version: {KAGGLE_VERSION}, "
        "version_notes: 'Data Update 2022/03/18', uploader: dataset first author}",
        "license: 'CC BY-NC-SA 4.0 (Kaggle); Readme.txt: free for academic research, commercial use needs author permission'",
        f"retrieval_date: '{dt.date.today().isoformat()}'",
        "targets: {binary: Attack_label, multiclass: Attack_type}",
        "files:",
    ]
    for e in entries:
        shape = f", rows: {e['rows']}, columns: {e['columns']}" if "rows" in e else ""
        out.append(f"  - {{path: '{e['path']}', bytes: {e['bytes']}{shape}, sha256: {e['sha256']}}}")
    CARD.write_text("\n".join(out) + "\n")
    print(f"wrote {CHECKSUMS.relative_to(ROOT)} and {CARD.relative_to(ROOT)}")


def verify() -> None:
    failures = 0
    for line in CHECKSUMS.read_text().splitlines():
        digest, rel = line.split("  ", 1)
        path = ROOT / rel
        if not path.exists() or sha256(path) != digest:
            print(f"MISMATCH {rel}")
            failures += 1
    print("all checksums match" if not failures else f"{failures} file(s) failed")
    sys.exit(1 if failures else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verify", action="store_true", help="only verify existing files against checksums")
    parser.add_argument("--essential", action="store_true", help="only the selected ML/DNN CSVs and docs")
    args = parser.parse_args()
    if args.verify:
        verify()
        return
    for name in ESSENTIAL if args.essential else list_files():
        fetch(name)
    write_manifest()


if __name__ == "__main__":
    main()
