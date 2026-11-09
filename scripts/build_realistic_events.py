"""Build the realistic event tables: every packet with real timestamp, session and device (final task 1, steps 1–4).

For each of the 24 captures:
  1. packet index from the pcap (real UTC timestamps, sessions, corrupt timestamps removed)
  2. features re-extracted with tshark (correctly aligned for every packet; validated against the publisher's
     CSVs: 99.95–100% of rows identical, see experiments/manifests/tshark_validation.json)
  3. publisher selection: the publisher's CSV rows are matched to their packets, and every packet is flagged
     `publisher_selected`. For the three captures whose CSV layout is broken (rebuild_from_pcap) the selection
     cannot be recovered and all packets are kept.
  4. device id and labels attached; written to data/standardized/events/<capture>.parquet + a manifest.

  python scripts/build_realistic_events.py                 # all captures
  python scripts/build_realistic_events.py heart_rate mitm  # selected captures
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import config_hash, load_config, resolve  # noqa: E402
from src.common.crypto import hash_file  # noqa: E402
from src.common.storage import git_commit  # noqa: E402
from src.data.ingestion.pcap_index import index_capture, ip_to_str  # noqa: E402
from src.data.ingestion.tshark_extract import extract_to_tsv, read_tsv  # noqa: E402
from src.data.preparation.devices import capture_to_device  # noqa: E402
from src.data.preparation.raw_normalize import normalize  # noqa: E402
from src.data.preparation.timestamps import csv_time_of_day_us, ip_to_int, match_rows, status_report  # noqa: E402

CHUNK = 500_000
META = ["capture", "device_id", "packet_no", "ts_us", "session", "src_ip", "dst_ip", "ip_proto", "ethertype",
        "publisher_selected", "Attack_label", "Attack_type"]


def publisher_selection(capture: str, spec: dict, packets: pd.DataFrame, real: dict, raw_dir: Path) -> tuple[set, dict]:
    if capture in real["rebuild_from_pcap"]:
        return set(packets.packet_no.tolist()), {"method": "all packets (CSV layout broken; selection not recoverable)"}
    csv = pd.read_csv(raw_dir / spec["csv"], dtype=str, keep_default_na=False,
                      usecols=["frame.time", "ip.src_host", "ip.dst_host"])
    idx, status = match_rows(csv_time_of_day_us(csv["frame.time"]), ip_to_int(csv["ip.src_host"]),
                             ip_to_int(csv["ip.dst_host"]), packets, real["csv_utc_offset_hours"])
    selected = set(packets.packet_no.to_numpy()[idx[idx >= 0]].tolist())
    return selected, {"method": "CSV rows matched to packets", "csv_rows": int(len(csv)), **status_report(status)}


def build_capture(capture: str) -> dict:
    t0 = time.time()
    cfg = load_config("datasets")
    real, raw_dir = cfg["realistic"], resolve(cfg["edge_iiotset"]["raw_dir"])
    spec = real["captures"][capture]
    device = capture_to_device()[capture]
    attack_label = 0 if spec["kind"] == "normal" else 1

    packets, summary = index_capture(raw_dir / spec["pcap"], tuple(real["valid_time_utc"]), real["session_gap_seconds"])
    packets = packets[packets.valid_ts].drop(columns="valid_ts").set_index("packet_no", drop=False)
    selected, selection = publisher_selection(capture, spec, packets.reset_index(drop=True), real, raw_dir)

    out_dir = resolve(real["paths"]["events"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{capture}.parquet"
    tsv = extract_to_tsv(raw_dir / spec["pcap"], resolve(real["paths"]["rebuilt"]) / f"{capture}.tsv")

    writer, rows_out, unparseable, no_packet = None, 0, 0, 0
    extracted = np.zeros(int(packets.packet_no.max()) + 1, dtype=bool)
    try:
        for chunk in read_tsv(tsv, chunksize=CHUNK):
            feats, ok = normalize(chunk, empty_as_zero=True, schema_name="realistic")
            numbers = chunk["frame.number"].to_numpy()
            extracted[numbers[numbers < len(extracted)]] = True
            in_index = np.isin(numbers, packets.packet_no.to_numpy())   # drops the corrupt-timestamp packets
            keep = ok.to_numpy() & in_index
            unparseable += int((~ok.to_numpy()).sum())
            no_packet += int((~in_index).sum())
            feats = feats[keep].reset_index(drop=True)
            pk = packets.loc[numbers[keep]].reset_index(drop=True)
            meta = pd.DataFrame({
                "capture": capture, "device_id": device, "packet_no": pk.packet_no.to_numpy(),
                "ts_us": pk.ts_us.to_numpy(), "session": pk.session.to_numpy(),
                "src_ip": ip_to_str(pk.src_ip.to_numpy()), "dst_ip": ip_to_str(pk.dst_ip.to_numpy()),
                "ip_proto": pk.ip_proto.to_numpy(), "ethertype": pk.ethertype.to_numpy(),
                "publisher_selected": np.isin(pk.packet_no.to_numpy(), list(selected)),
                "Attack_label": attack_label, "Attack_type": spec["label"],
            })
            table = pa.Table.from_pandas(pd.concat([meta, feats], axis=1), preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(out_path, table.schema, compression="zstd")
            writer.write_table(table)
            rows_out += len(meta)
    finally:
        if writer is not None:
            writer.close()
        tsv.unlink(missing_ok=True)

    # Every indexed packet must have its features (tshark stops early at a damaged record).
    missing = int((~extracted[packets.packet_no.to_numpy()]).sum())
    if missing:
        raise RuntimeError(f"{capture}: tshark output lacks {missing} indexed packets")

    # Time order (captures contain a few hundred out-of-order packets); replay needs strict order.
    table = pq.read_table(out_path)
    order = np.lexsort((table["packet_no"].to_numpy(), table["ts_us"].to_numpy()))
    pq.write_table(table.take(pa.array(order)), out_path, compression="zstd")
    del table

    manifest = {
        "capture": capture, "device_id": device, "label": spec["label"], "kind": spec["kind"],
        "pcap": spec["pcap"], "pcap_sha256": hash_file(raw_dir / spec["pcap"]),
        "packet_index": summary, "publisher_selection": selection,
        "rows_written": rows_out, "rows_publisher_selected": int(len(selected)),
        "tshark_rows_unparseable_dropped": unparseable, "tshark_rows_without_valid_packet_dropped": no_packet,
        "indexed_packets_without_features": missing,
        "output": str(out_path.relative_to(resolve("."))), "output_sha256": hash_file(out_path),
        "seconds": round(time.time() - t0, 1), "created_utc": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(), "config_hash": config_hash("datasets"),
    }
    out_path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return manifest


def main() -> None:
    captures = sys.argv[1:] or list(load_config("datasets")["realistic"]["captures"])
    for capture in captures:
        m = build_capture(capture)
        sel = m["publisher_selection"]
        print(f"{capture:22s} rows={m['rows_written']:>9,} selected={m['rows_publisher_selected']:>9,} "
              f"match={ {k: v for k, v in sel.items() if k not in ('method',) and v} } "
              f"unparseable={m['tshark_rows_unparseable_dropped']} sessions={m['packet_index']['sessions']} "
              f"({m['seconds']}s)", flush=True)


if __name__ == "__main__":
    main()
