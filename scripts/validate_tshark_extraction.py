"""Prove that tshark re-extraction reproduces the publisher's raw CSV values (final task 1, step 2).

For each capture: CSV rows are matched to their packets (time of day + IPs), the same packets are extracted with
tshark, both pass through the same normalisation, and every model feature is compared value by value.
Agreement is reported separately for UDP and non-UDP packets, because the publisher's extraction misaligned
every UDP row (`udp.port` holds two values joined with the column separator).

  python scripts/validate_tshark_extraction.py heart_rate temperature_humidity sql_injection
Writes experiments/manifests/tshark_validation.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import load_config, resolve  # noqa: E402
from src.data.ingestion.pcap_index import index_capture  # noqa: E402
from src.data.ingestion.tshark_extract import extract  # noqa: E402
from src.data.preparation.raw_normalize import normalize, schema  # noqa: E402
from src.data.preparation.timestamps import csv_time_of_day_us, ip_to_int, match_rows, status_report  # noqa: E402

MAX_PACKETS = 300_000


def _agreement(a: pd.Series, b: pd.Series, categorical: bool) -> np.ndarray:
    if categorical:
        return (a.to_numpy() == b.to_numpy())
    x, y = a.to_numpy(float), b.to_numpy(float)
    return np.isclose(x, y, rtol=1e-9, atol=1e-9) | (np.isnan(x) & np.isnan(y))


def validate(capture: str) -> dict:
    cfg = load_config("datasets")
    real, raw_dir = cfg["realistic"], resolve(cfg["edge_iiotset"]["raw_dir"])
    cap = real["captures"][capture]
    packets, summary = index_capture(raw_dir / cap["pcap"], tuple(real["valid_time_utc"]), real["session_gap_seconds"])
    packets = packets[packets.valid_ts].reset_index(drop=True)

    raw = pd.read_csv(raw_dir / cap["csv"], dtype=str, keep_default_na=False, nrows=MAX_PACKETS)
    idx, status = match_rows(csv_time_of_day_us(raw["frame.time"]), ip_to_int(raw["ip.src_host"]),
                             ip_to_int(raw["ip.dst_host"]), packets, real["csv_utc_offset_hours"])
    raw_feat, raw_ok = normalize(raw, empty_as_zero=False)
    matched = idx >= 0
    raw_feat = raw_feat[matched].assign(packet_no=packets.packet_no.to_numpy()[idx[matched]],
                                        csv_valid=raw_ok.to_numpy()[matched])

    ts = extract(raw_dir / cap["pcap"], resolve(real["paths"]["rebuilt"]) / f"_validation_{capture}.tsv", MAX_PACKETS)
    ts_feat, ts_ok = normalize(ts, empty_as_zero=True)
    ts_feat = ts_feat.assign(packet_no=ts["frame.number"].to_numpy(), tshark_valid=ts_ok.to_numpy())

    both = raw_feat.merge(ts_feat, on="packet_no", suffixes=("_csv", "_ts"))
    both = both.merge(packets[["packet_no", "ip_proto", "ethertype"]], on="packet_no")
    is_udp = (both.ip_proto == 17).to_numpy()
    _, categorical = schema("realistic")
    cols = [c for c in raw_feat.columns if c not in ("packet_no", "csv_valid")]
    agree = np.column_stack([_agreement(both[c + "_csv"], both[c + "_ts"], c in categorical) for c in cols])
    row_ok = agree.all(axis=1)

    def part(mask: np.ndarray) -> dict:
        if not mask.any():
            return {"rows": 0}
        col = agree[mask].mean(axis=0)
        return {"rows": int(mask.sum()), "rows_fully_identical": float(row_ok[mask].mean()),
                "csv_rows_unparseable": float((~both.csv_valid.to_numpy()[mask]).mean()),
                "columns_below_100pct": {c: round(float(v), 4) for c, v in zip(cols, col, strict=True) if v < 1.0}}

    (resolve(real["paths"]["rebuilt"]) / f"_validation_{capture}.tsv").unlink(missing_ok=True)
    return {
        "capture": capture, "compared_slice_packets": MAX_PACKETS,
        "csv_rows_read": len(raw), "match": status_report(status),
        "tshark_rows_unparseable": float((~ts_ok).mean()),
        "non_udp": part(~is_udp), "udp": part(is_udp),
    }


def main() -> None:
    captures = sys.argv[1:] or ["heart_rate"]
    out = resolve("experiments/manifests/tshark_validation.json")
    results = json.loads(out.read_text()) if out.exists() else {}
    for capture in captures:
        r = validate(capture)
        results[capture] = r
        print(json.dumps(r, indent=1), flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
