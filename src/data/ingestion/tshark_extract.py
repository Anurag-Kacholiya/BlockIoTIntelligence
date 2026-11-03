"""Re-extract the 61 Edge-IIoTset features from a packet capture with tshark (final task 1, step 2).

Used for the captures whose raw CSV layout is broken (Modbus, DDoS_UDP, MITM). The feature names are Wireshark
field names, so tshark reproduces them directly; `frame.number` keys each row to the packet index, so no time
matching is needed. Accuracy is verified against captures whose raw CSV is intact (see
scripts/validate_tshark_extraction.py).

Output values are raw tshark text: "" for a field the packet does not have, hex for flag fields. Pass the
result through raw_normalize.normalize(..., empty_as_zero=True).
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from src.data.preparation.raw_normalize import feature_columns

KEY_FIELDS = ["frame.number", "frame.time_epoch"]


def tshark_path() -> str:
    path = shutil.which("tshark")
    if not path:
        raise FileNotFoundError("tshark not found: install Wireshark's CLI (brew install wireshark)")
    return path


def extract_to_tsv(pcap: str | Path, out_tsv: str | Path, max_packets: int | None = None) -> Path:
    """Run tshark over `pcap` and write one tab-separated row per packet to `out_tsv`.

    One value per field (first occurrence). The publisher's CSVs broke where multi-valued fields (e.g.
    `udp.port` = source and destination port) were joined with the column separator; this rebuild avoids that.
    """
    fields = KEY_FIELDS + feature_columns()
    cmd = [tshark_path(), "-n", "-r", str(pcap), "-T", "fields", "-E", "header=y", "-E", "separator=/t",
           "-E", "quote=n", "-E", "occurrence=f"]
    if max_packets:
        cmd += ["-c", str(max_packets)]
    for f in fields:
        cmd += ["-e", f]
    out_tsv = Path(out_tsv)
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, text=True)
    # A damaged record ends the readable part of a capture (Vulnerability scanner: record 265,828, after the last
    # packet the publisher used). tshark has written every packet before it; callers check none is missing.
    if proc.returncode != 0 and "appears to be damaged or corrupt" not in proc.stderr:
        raise RuntimeError(f"tshark failed on {pcap}: {proc.stderr.strip()[:500]}")
    return out_tsv


def read_tsv(out_tsv: str | Path, chunksize: int | None = None):
    """Read a tshark TSV as text columns (a DataFrame, or an iterator of chunks when `chunksize` is set)."""
    fields = KEY_FIELDS + feature_columns()

    def check(df: pd.DataFrame) -> pd.DataFrame:
        if list(df.columns) != fields:
            raise ValueError(f"{out_tsv}: unexpected header {list(df.columns)[:5]}…")
        df["frame.number"] = df["frame.number"].astype("int64")
        return df

    reader = pd.read_csv(out_tsv, sep="\t", dtype=str, keep_default_na=False, quoting=csv.QUOTE_NONE,
                         on_bad_lines="error", chunksize=chunksize)
    if chunksize is None:
        return check(reader)
    return (check(chunk) for chunk in reader)


def extract(pcap: str | Path, out_tsv: str | Path, max_packets: int | None = None) -> pd.DataFrame:
    """Convenience: extract and read back in one go (small captures and tests)."""
    return read_tsv(extract_to_tsv(pcap, out_tsv, max_packets))
