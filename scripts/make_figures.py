"""Figures and tables built only from files in experiments/.

  python scripts/make_figures.py                     ->  docs/presentation1/{figures,tables}/  (first presentation)
  python scripts/make_figures.py --set final_task1   ->  docs/final/task1/{figures,tables}/    (dataset v2)
  python scripts/make_figures.py --set final_task2   ->  docs/final/task2/{figures,tables}/    (multi-node chain)
  python scripts/make_figures.py --set final_faults  ->  docs/final/faults/{figures,tables}/   (fault tolerance)
  python scripts/make_figures.py --set final_task3   ->  docs/final/task3/{figures,tables}/    (AI-driven blockchain)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.lines  # noqa: E402
import matplotlib.patches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments" / "results"
sys.path.insert(0, str(ROOT))           # final task 3 re-derives each run's waits with the project's scheduler code

# Each set reads the same kinds of results from different files and words its notes for its data.
SETS = {
    "presentation1": {
        "out": ROOT / "docs" / "presentation1",
        "runs": RESULTS / "presentation1" / "runs.jsonl",
        "integrity": RESULTS / "exp_integrity_accuracy.csv",
        "security": RESULTS / "exp_security.csv",
        "recall_runs": "baseline-*.json",
        "accuracy_note": "Edge-IIoTset DNN view, {events:,} held-out events × {seeds} seeds (mean ± sd).",
        "security_note": "Each attack injected in its own pass into real Edge-IIoTset traffic (5% rate).",
        "scaling_xlabel": "Logical IoT devices",
        "scaling_note": "{events:,} held-out events per point, 2 edges, 1 fog, local Anvil chain.",
        "recall_note": "{events:,} held-out events, cloud {family}.",
    },
    "final_task1": {
        "out": ROOT / "docs" / "final" / "task1",
        "runs": RESULTS / "final_task1" / "runs.jsonl",
        "integrity": RESULTS / "realistic" / "integrity_accuracy.csv",
        "security": RESULTS / "realistic" / "security.csv",
        "recall_runs": "realistic_replay-*.json",
        "accuracy_note": "Dataset v2 realistic replay: {events:,} test-window messages from 10 real devices with real"
                         " timing × {seeds} seeds (mean ± sd; every seed replays the same messages).",
        "security_note": "Each attack injected in its own pass into dataset v2's realistic replay (10 real devices,"
                         " real timing; 5% rate).",
        "scaling_xlabel": "IoT devices (each of the 10 real devices split over k devices)",
        "scaling_note": "{events:,} realistic-replay messages per point, the same messages and timing at every point;"
                        " 2 edges, 1 fog, local Anvil chain.",
        "recall_note": "{events:,} realistic-replay messages (real repeats kept), cloud {family}.",
    },
    "final_task2": {
        "out": ROOT / "docs" / "final" / "task2",
        "runs": RESULTS / "final_task2" / "runs.jsonl",
        "security": RESULTS / "final_task2" / "security.csv",
        "security_note": "Each attack injected in its own pass into dataset v2's realistic replay, every blockchain"
                         " pass on a fresh 4-validator QBFT network (layers on different nodes; 5% rate).",
    },
    "final_faults": {
        "out": ROOT / "docs" / "final" / "faults",
        "runs": RESULTS / "final_faults" / "runs.jsonl",
        "rows": RESULTS / "final_faults" / "rows",
    },
    "final_task3": {
        "out": ROOT / "docs" / "final" / "task3",
        "runs": RESULTS / "final_task3" / "runs.jsonl",
        "rows": RESULTS / "final_task3" / "rows",
        "simulation": RESULTS / "final_task3" / "simulation.csv",
        "forecast_quality": RESULTS / "final_task3" / "forecast_quality.csv",
        "forecaster": ROOT / "models" / "real_time" / "device_forecaster",
    },
}

# Validated categorical slots 1-4 (light surface); text never wears series colour.
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3de"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
MODE_COLOR = {"baseline": SLOTS[0], "per_event": SLOTS[1], "batch": SLOTS[2]}
MODE_LABEL = {"baseline": "Baseline (no blockchain)", "per_event": "Blockchain · per-event commit",
              "batch": "Blockchain · Merkle batch commit"}
LAYERS = [("device", "binary"), ("edge", "binary"), ("fog", "multiclass"), ("cloud", "multiclass")]
FIG = TAB = Path()

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.titlecolor": INK, "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "legend.frameon": False, "legend.fontsize": 10, "lines.linewidth": 2, "lines.markersize": 8,
})


def legend_top(ax, ncol: int = 3) -> None:
    """Legend in one row between title and plot, so it never covers data."""
    ax.set_title(ax.get_title(loc="left"), loc="left", pad=34)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=ncol, borderaxespad=0.3, handlelength=1.6)


def save(fig, name: str, note: str | None = None) -> None:
    if note:
        fig.text(0.01, -0.02, note, fontsize=8.5, color=INK2, ha="left", va="top", wrap=True)
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"figure {name}.png")


def bar_labels(ax, bars, fmt: str) -> None:
    for b in bars:
        h = b.get_height()
        if np.isfinite(h):
            ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, h), xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8.5, color=INK2)


def grouped(ax, categories, series: dict[str, list[float]], errors: dict[str, list[float]] | None, fmt: str,
            colors: dict[str, str] = MODE_COLOR, labels: dict[str, str] = MODE_LABEL):
    n = len(series)
    width = 0.8 / n
    x = np.arange(len(categories))
    for i, (mode, vals) in enumerate(series.items()):
        bars = ax.bar(x + (i - (n - 1) / 2) * width, vals, width, color=colors[mode], label=labels[mode],
                      edgecolor=SURFACE, linewidth=2, yerr=(errors or {}).get(mode), ecolor=INK2, capsize=0,
                      error_kw={"elinewidth": 1})
        bar_labels(ax, bars, fmt)
    ax.set_xticks(x, categories)
    ax.grid(axis="x", visible=False)


def load_runs(s: dict) -> pd.DataFrame:
    runs = [json.loads(line) for line in s["runs"].read_text().splitlines()]
    return pd.DataFrame(runs)


def fig_accuracy(runs: pd.DataFrame, s: dict) -> pd.DataFrame:
    comp = runs[runs.group == "comparison"]
    rows = []
    for _, r in comp.iterrows():
        for a in r.accuracy:
            rows.append({"mode": r["mode"], "seed": r.reproducibility["seed"], **a})
    acc = pd.DataFrame(rows)
    acc = acc[acc.apply(lambda x: (x.layer, x.task) in LAYERS, axis=1)]
    stats = acc.groupby(["mode", "layer"])[["accuracy", "f1_macro"]].agg(["mean", "std"])
    cats = [f"{layer.title()}\n({task})" for layer, task in LAYERS]
    for metric, title in (("accuracy", "Accuracy"), ("f1_macro", "Macro-F1")):
        fig, ax = plt.subplots(figsize=(9, 4.6))
        modes = [m for m in MODE_COLOR if m in acc["mode"].unique()]
        grouped(ax, cats, {m: [stats.loc[(m, lay), (metric, "mean")] for lay, _ in LAYERS] for m in modes},
                {m: [stats.loc[(m, lay), (metric, "std")] for lay, _ in LAYERS] for m in modes}, "{:.3f}")
        ax.set_ylim(0, 1.08)
        ax.set_ylabel(title)
        ax.set_title(f"{title} per intelligence layer — clean traffic, with and without blockchain")
        legend_top(ax)
        save(fig, f"01_{metric}_per_layer",
             s["accuracy_note"].format(events=int(comp.events_in.iloc[0]),
                                       seeds=comp.reproducibility.map(lambda x: x["seed"]).nunique())
             + " The ledger does not alter the data models see, so accuracy on untampered traffic is unchanged.")
    table = stats.round(4)
    table.to_csv(TAB / "accuracy_per_layer.csv")
    return acc


def fig_latency(runs: pd.DataFrame, s: dict) -> pd.DataFrame:
    comp = runs[runs.group == "comparison"]
    rows = []
    for _, r in comp.iterrows():
        for stage, v in r.latency_per_event_ms.items():
            rows.append({"mode": r["mode"], "stage": stage, "ms_per_event": v,
                         "cpu_ms_per_event": r.cpu_per_event_ms.get(stage), "throughput_eps": r.throughput_eps})
    lat = pd.DataFrame(rows)
    stats = lat.groupby(["mode", "stage"])[["ms_per_event", "cpu_ms_per_event"]].mean()
    stages = ["device", "edge", "fog", "cloud", "batch_end_to_end"]
    cats = ["Device", "Edge", "Fog", "Cloud", "End-to-end"]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    modes = [m for m in MODE_COLOR if m in lat["mode"].unique()]
    grouped(ax, cats, {m: [stats.loc[(m, st), "ms_per_event"] for st in stages] for m in modes}, None, "{:.3g}")
    ax.set_yscale("log")
    ax.set_ylabel("Processing time per event (ms, log scale)")
    ax.set_title("Latency per intelligence layer — blockchain overhead")
    legend_top(ax)
    save(fig, "02_latency_per_layer",
         "Amortised wall time per event in each layer's stage, micro-batches of 256, local Anvil chain (automine)."
         " Blockchain time sits in device (commit), edge (verify + record) and fog (alert audit).")
    stats.round(4).to_csv(TAB / "latency_cpu_per_layer.csv")
    thr = lat.groupby("mode").throughput_eps.mean().round(1)
    thr.to_csv(TAB / "throughput.csv")
    return stats


def fig_integrity(s: dict) -> None:
    df = pd.read_csv(s["integrity"])
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    for mode in ("baseline", "batch", "per_event"):
        d = df[df["mode"] == mode]
        if d.empty:
            continue
        ax.plot(d.tamper_rate * 100, d.attack_detection_rate * 100, marker="o", color=MODE_COLOR[mode],
                label=MODE_LABEL[mode], markeredgecolor=SURFACE, markeredgewidth=2)
        last = d.iloc[-1]
        ax.annotate(f"{last.attack_detection_rate * 100:.1f}%", (last.tamper_rate * 100, last.attack_detection_rate * 100),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color=INK2)
    ax.set_xlabel("Attack events camouflaged in flight (%)")
    ax.set_ylabel("Attacks detected (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Accuracy under data-integrity attack")
    legend_top(ax, ncol=2)
    save(fig, "03_integrity_attack_detection",
         "An attacker between device and edge swaps attack events' features for a normal event's. Detected ="
         " rejected for integrity or classified as attack.")
    df.round(4).to_csv(TAB / "integrity_accuracy.csv", index=False)


def fig_security(s: dict) -> None:
    df = pd.read_csv(s["security"])
    att = df[~df.attack.str.startswith("legitimate")]
    order = ["tamper", "replay_same_edge", "replay_cross_edge", "unregistered_device", "impersonation",
             "model_tamper_artifact_only", "model_tamper_artifact_and_record", "unauthorized_ledger_write"]
    names = {"tamper": "Payload tampering", "replay_same_edge": "Replay (same edge)",
             "replay_cross_edge": "Replay (other edge)", "unregistered_device": "Unregistered device",
             "impersonation": "Device impersonation", "model_tamper_artifact_only": "Model swap",
             "model_tamper_artifact_and_record": "Model swap + forged record",
             "unauthorized_ledger_write": "Unauthorized ledger write"}
    order = [o for o in order if o in set(att.attack)]
    fig, ax = plt.subplots(figsize=(9, 5))
    y = np.arange(len(order))
    for i, mode in enumerate(("baseline", "blockchain")):
        vals = [att[(att["mode"] == mode) & (att.attack == o)].detection_rate.mean() * 100 for o in order]
        vals = [0 if np.isnan(v) else v for v in vals]
        color = MODE_COLOR["baseline" if mode == "baseline" else "per_event"]
        label = MODE_LABEL["baseline"] if mode == "baseline" else "Blockchain-enabled"
        bars = ax.barh(y + (i - 0.5) * 0.38, vals, 0.38, color=color, label=label, edgecolor=SURFACE, linewidth=2)
        for b, v in zip(bars, vals, strict=True):
            ax.annotate(f"{v:.0f}%", (v, b.get_y() + b.get_height() / 2), xytext=(4, 0), textcoords="offset points",
                        va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(y, [names[o] for o in order])
    ax.invert_yaxis()
    ax.set_xlim(0, 112)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("Attacks detected / blocked (%)")
    ax.grid(axis="y", visible=False)
    ax.set_title("Security evaluation — attack detection rate")
    legend_top(ax, ncol=2)
    save(fig, "04_security_detection", s["security_note"] + " Unauthorized ledger write is blockchain-only.")
    df.to_csv(TAB / "security.csv", index=False)


def fig_scaling(runs: pd.DataFrame, s: dict) -> None:
    sc = runs[runs.group == "scaling"].copy()
    sc["devices"] = sc.topology.map(lambda t: t["devices"])
    sc["e2e"] = sc.latency_per_event_ms.map(lambda d: d["batch_end_to_end"])
    for col, ylabel, title, name in (
        ("throughput_eps", "Events processed per second (log)", "Throughput vs number of IoT devices", "05_scaling_throughput"),
        ("e2e", "End-to-end time per event (ms, log)", "End-to-end latency vs number of IoT devices", "06_scaling_latency"),
    ):
        fig, ax = plt.subplots(figsize=(8.5, 4.6))
        for mode in MODE_COLOR:
            d = sc[sc["mode"] == mode].sort_values("devices")
            if d.empty:
                continue
            ax.plot(d.devices, d[col], marker="o", color=MODE_COLOR[mode], label=MODE_LABEL[mode],
                    markeredgecolor=SURFACE, markeredgewidth=2)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xticks(sorted(sc.devices.unique()), [str(d) for d in sorted(sc.devices.unique())])
        ax.minorticks_off()
        ax.set_xlabel(s["scaling_xlabel"])
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        legend_top(ax)
        save(fig, name, s["scaling_note"].format(events=int(sc.events_in.iloc[0])))
    cols = ["mode", "devices", "throughput_eps", "e2e"]
    sc[cols].sort_values(["mode", "devices"]).round(3).to_csv(TAB / "scaling.csv", index=False)


def fig_gas(runs: pd.DataFrame, s: dict) -> None:
    comp = runs[(runs.group == "comparison") & (runs["mode"] != "baseline")]
    kinds = {"device_commit": "Device commit", "edge_processed": "Edge provenance", "fog_alert_audit": "Fog alert audit",
             "cloud_inference_record": "Cloud inference record"}
    rows = []
    for _, r in comp.iterrows():
        n = r.events_processed
        for k, v in r.chain.items():
            if k in kinds:
                rows.append({"mode": r["mode"], "kind": k, "gas_per_event": v["gas_total"] / n,
                             "tx_per_event": v["tx_count"] / n})
    g = pd.DataFrame(rows).groupby(["mode", "kind"]).mean()
    fig, ax = plt.subplots(figsize=(9, 4.6))
    modes = [m for m in ("per_event", "batch") if m in g.index.get_level_values(0)]
    grouped(ax, list(kinds.values()), {m: [g.loc[(m, k), "gas_per_event"] if (m, k) in g.index else 0
                                           for k in kinds] for m in modes}, None, "{:,.0f}")
    ax.set_ylabel("Gas per event")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_title("On-chain cost per event, by layer")
    legend_top(ax, ncol=2)
    save(fig, "07_gas_per_event", f"Gas used per processed event, mean over {len(comp) // max(1, len(modes))} seeds × {int(comp.events_in.iloc[0]):,} events.")
    g.round(3).to_csv(TAB / "gas_per_event.csv")


def fig_class_recall(s: dict) -> None:
    runs = [p for p in sorted(RESULTS.glob(s["recall_runs"])) if json.loads(p.read_text())["blockchain"] == "off"]
    r = json.loads(runs[-1].read_text())
    c = r["cloud_confusion"]
    m = np.array(c["matrix"])
    recall = pd.Series(m.diagonal() / m.sum(axis=1), index=c["labels"]).sort_values()
    support = pd.Series(m.sum(axis=1), index=c["labels"])
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    bars = ax.barh(recall.index, recall.values * 100, color=MODE_COLOR["baseline"], edgecolor=SURFACE, linewidth=2)
    for b, (label, v) in zip(bars, recall.items(), strict=True):
        ax.annotate(f"{v * 100:.1f}%  (n={support[label]:,})", (v * 100, b.get_y() + b.get_height() / 2), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=8.5, color=INK2)
    ax.set_xlim(0, 125)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("Recall (%)")
    ax.grid(axis="y", visible=False)
    ax.set_title("Cloud model: recall per traffic class (15 classes)")
    family = r["models"]["cloud"].split("-")[1].replace("_", " ").title().replace("Mlp", "MLP")
    save(fig, "08_cloud_recall_per_class", s["recall_note"].format(events=r["events_processed"], family=family))


# ---- dataset v2 only ------------------------------------------------------------------------------------------------

SPLIT_COLOR = {"midterm": SLOTS[0], "real_random": SLOTS[1], "real_time": SLOTS[2]}
SPLIT_LABEL = {"midterm": "Mid-term (DNN file)", "real_random": "Dataset v2 · split A (random)",
               "real_time": "Dataset v2 · split B (time)"}
F1_LAYERS = [("device", "binary", "Device\n(binary)"), ("edge", "binary", "Edge\n(binary)"),
             ("fog", "multiclass", "Fog\n(15 classes)"), ("cloud", "multiclass", "Cloud\n(15 classes)"),
             ("cloud", "binary", "Cloud\n(attack vs normal)")]
MIDTERM_TEST_RUN = RESULTS / "baseline-20260929T125816-d9ae79.json"   # the mid-term's 200,000-event test-split run


def fig_f1_by_split(s: dict) -> None:
    mid = pd.DataFrame(json.loads(MIDTERM_TEST_RUN.read_text())["accuracy"]).assign(view="midterm")
    v2 = pd.read_csv(RESULTS / "realistic" / "offline_metrics.csv")
    f1 = pd.concat([mid, v2]).set_index(["view", "layer", "task"]).f1_macro
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    grouped(ax, [c for _, _, c in F1_LAYERS], {v: [f1[(v, lay, t)] for lay, t, _ in F1_LAYERS] for v in SPLIT_COLOR},
            None, "{:.3f}", colors=SPLIT_COLOR, labels=SPLIT_LABEL)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Macro-F1 on held-out test data")
    ax.set_title("Model quality: mid-term data vs dataset v2, random vs time split")
    legend_top(ax)
    save(fig, "09_macro_f1_by_split",
         "Split A shuffles packets (as the mid-term); split B trains on the first 70% of every capture session and tests"
         " on the last 15%. Most of B's multiclass drop is MITM (8 test packets) and Ransomware.")
    f1.unstack("view")[list(SPLIT_COLOR)].round(4).to_csv(TAB / "macro_f1_by_split.csv")


LODO_LAYER_COLOR = dict(zip(("device", "edge", "fog", "cloud"), SLOTS, strict=True))


def fig_unseen_devices(s: dict) -> None:
    lodo = pd.read_csv(RESULTS / "realistic" / "lodo.csv")
    far = lodo.pivot(index="held_out_device", columns="layer", values="unseen_device_false_alarm_rate") * 100
    far = far.sort_values("cloud", ascending=False)
    fig, ax = plt.subplots(figsize=(9, 5.8))
    y = np.arange(len(far))
    ax.hlines(y, far.min(axis=1), far.max(axis=1), color=GRID, linewidth=2, zorder=1)
    dodge = dict(zip(LODO_LAYER_COLOR, (-0.18, -0.06, 0.06, 0.18), strict=True))   # close values never hide
    for layer, color in LODO_LAYER_COLOR.items():
        ax.scatter(far[layer], y + dodge[layer], s=64, color=color, edgecolors=SURFACE, linewidths=2, zorder=3,
                   label=f"{layer.title()} layer")
    for i, v in enumerate(far["cloud"]):
        ax.annotate(f"{v:.2f}%", (v, i + dodge["cloud"]), xytext=(0, -11), textcoords="offset points", ha="center",
                    fontsize=8, color=INK2)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    ax.set_yticks(y, far.index)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("False alarms on the unseen sensor's normal traffic (% of its messages, log scale)")
    ax.set_title("Sensors the models never saw: false-alarm rate per layer")
    legend_top(ax, ncol=4)
    save(fig, "10_unseen_device_false_alarms",
         "Split C: for each sensor, all four layers retrained without its normal traffic, then tested on all 100,000"
         " of its normal messages. Labels show the cloud layer.")
    lodo.round(5).to_csv(TAB / "unseen_device_false_alarms.csv", index=False)


# ---- final task 2: multi-node chain -------------------------------------------------------------------------------

CHAIN_ORDER = ["anvil_automine", "anvil_1s", "qbft_1s", "qbft_1s_await"]
CHAIN_LABEL = {"anvil_automine": "1 node,\ninstant blocks", "anvil_1s": "1 node,\n1 block/s",
               "qbft_1s": "4 validators (QBFT),\n1 block/s", "qbft_1s_await": "4 validators (QBFT),\n1 block/s,\nevery write awaited"}


def task2_table(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per run: the measures every task 2 figure and table uses."""
    rows = []
    for _, r in runs.iterrows():
        t, e2e, chain = r.task2, r.latency_ms["batch_end_to_end"], r.chain
        n = r.events_processed
        cloud = next(a for a in r.accuracy if (a["layer"], a["task"]) == ("cloud", "multiclass"))
        consensus = r.chain_network.get("consensus", {})
        rows.append({
            "group": t["group"], "chain": t["chain"] + ("_await" if t["audit_writes"] == "await" else ""),
            "mode": t["mode"], "seed": t["seed"], "devices": r.topology["devices"], "block_period_s": t["block_time"],
            "throughput_eps": r.throughput_eps, "message_latency_mean_s": e2e["mean_ms"] / 1000,
            "message_latency_p95_s": e2e["p95_ms"] / 1000,
            "commit_latency_ms": chain["device_commit"]["latency_mean_ms"],
            "processing_record_latency_ms": chain["edge_processed"]["latency_mean_ms"],
            "gas_per_event": sum(v["gas_total"] for k, v in chain.items()
                                 if k in ("device_commit", "edge_processed", "fog_alert_audit",
                                          "cloud_inference_record")) / n,
            "transactions": sum(v["tx_count"] for v in chain.values()), "failed": sum(v["failed"] for v in chain.values()),
            "node_cpu_s": r.resources.get("node_cpu_s"), "node_peak_rss_mb": r.resources.get("node_peak_rss_mb"),
            "cloud_f1_macro": cloud["f1_macro"], "events_processed": n, "events_rejected": r.events_rejected,
            "consistent": consensus.get("consistent"), "blocks": consensus.get("common_height"),
        })
    return pd.DataFrame(rows)


def fig_t2_latency(t2: pd.DataFrame) -> None:
    d = t2[t2.group.isin(["comparison", "await_all"])]
    stats = d.groupby(["chain", "mode"]).message_latency_mean_s.agg(["mean", "std"])
    chains = [c for c in CHAIN_ORDER if c in d.chain.unique()]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    grouped(ax, [CHAIN_LABEL[c] for c in chains],
            {m: [stats.loc[(c, m), "mean"] for c in chains] for m in ("per_event", "batch")},
            {m: [stats.loc[(c, m), "std"] for c in chains] for m in ("per_event", "batch")}, "{:.2f}")
    ax.set_ylabel("Message latency, device → cloud result (s)")
    ax.set_title("What block time and consensus cost: message latency")
    legend_top(ax, ncol=2)
    save(fig, "11_message_latency_by_chain",
         "Dataset v2 realistic replay, 10,000 messages in micro-batches of 256; mean over 3 seeds (± sd; 1 seed for"
         " 'every write awaited'). Same client everywhere: transactions signed locally; fog and cloud audit records"
         " confirmed in the background unless every write is awaited.")


def fig_t2_throughput(t2: pd.DataFrame) -> None:
    d = t2[t2.group.isin(["comparison", "await_all"])]
    thr = d.groupby(["chain", "mode"]).throughput_eps.mean()
    chains = [c for c in CHAIN_ORDER if c in d.chain.unique()]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    y = np.arange(len(chains))
    for mode in ("per_event", "batch"):
        vals = [thr[(c, mode)] for c in chains]
        ax.scatter(vals, y, s=64, color=MODE_COLOR[mode], edgecolors=SURFACE, linewidths=2, zorder=3,
                   label=MODE_LABEL[mode])
        for v, yy in zip(vals, y, strict=True):
            ax.annotate(f"{v:,.0f}", (v, yy), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=8.5,
                        color=INK2)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_yticks(y, [CHAIN_LABEL[c].replace("\n", " ") for c in chains])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Messages processed per second (log scale)")
    ax.set_title("Throughput by chain")
    legend_top(ax, ncol=2)
    save(fig, "12_throughput_by_chain", "Same runs as figure 11, mean over seeds.")


def fig_t2_block_period(t2: pd.DataFrame) -> None:
    d = t2[(t2["mode"] == "batch") & (t2.chain.str.startswith("qbft")) & ~t2.chain.str.endswith("_await")
           & t2.group.isin(["comparison", "block_period"])]
    g = d.groupby("block_period_s")[["message_latency_mean_s", "message_latency_p95_s"]].mean().sort_index()
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    ax.plot(g.index, g.message_latency_mean_s, marker="o", color=SLOTS[0], label="Mean",
            markeredgecolor=SURFACE, markeredgewidth=2)
    ax.plot(g.index, g.message_latency_p95_s, marker="o", color=SLOTS[1], label="95th percentile",
            markeredgecolor=SURFACE, markeredgewidth=2)
    # p95 above-left, mean below-right: the two lines are close at 1 s and both rise to the right
    for col, offset, ha, va in (("message_latency_mean_s", (7, -4), "left", "top"),
                                ("message_latency_p95_s", (-7, 4), "right", "bottom")):
        for x, v in g[col].items():
            ax.annotate(f"{v:.1f} s", (x, v), xytext=offset, textcoords="offset points", ha=ha, va=va,
                        fontsize=8.5, color=INK2)
    ax.set_xticks(g.index, [f"{x:g} s" for x in g.index])
    ax.set_xlim(g.index.min() - 0.6, g.index.max() + 0.6)
    ax.set_xlabel("QBFT block period")
    ax.set_ylabel("Message latency (s)")
    ax.set_ylim(0, None)
    ax.set_title("Message latency vs block period (4 validators, Merkle batch)")
    legend_top(ax, ncol=2)
    save(fig, "13_latency_vs_block_period", "10,000 realistic-replay messages per point (1 s: mean of 3 seeds).")
    g.round(3).to_csv(TAB / "block_period.csv")


def fig_t2_scaling(t2: pd.DataFrame) -> None:
    single = load_runs(SETS["final_task1"])
    single = single[(single.group == "scaling") & (single["mode"] != "baseline")]
    rows = [{"chain": "1 node, instant blocks", "mode": r["mode"], "devices": r.topology["devices"],
             "throughput_eps": r.throughput_eps} for _, r in single.iterrows()]
    rows += [{"chain": "4 validators (QBFT), 1 block/s", "mode": r["mode"], "devices": r.devices,
              "throughput_eps": r.throughput_eps} for _, r in t2[t2.group == "scaling"].iterrows()]
    sc = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    style = {"1 node, instant blocks": "--", "4 validators (QBFT), 1 block/s": "-"}
    for (chain, mode), d in sc.groupby(["chain", "mode"]):
        d = d.sort_values("devices")
        ax.plot(d.devices, d.throughput_eps, marker="o", color=MODE_COLOR[mode], linestyle=style[chain],
                markeredgecolor=SURFACE, markeredgewidth=2)
        if mode == "batch":                       # the drop is the story: label both ends of the batch lines
            for x, v, dy in ((d.devices.iloc[0], d.throughput_eps.iloc[0], 8),
                             (d.devices.iloc[-1], d.throughput_eps.iloc[-1], 8)):
                ax.annotate(f"{v:,.0f}", (x, v), xytext=(0, dy), textcoords="offset points", ha="center",
                            fontsize=8.5, color=INK2)
    # colour = commit mode, line style = chain (two short legends read better than four long entries)
    handles = [matplotlib.lines.Line2D([], [], color=MODE_COLOR[m], marker="o", markeredgecolor=SURFACE,
                                       markeredgewidth=2, label=MODE_LABEL[m]) for m in ("per_event", "batch")]
    handles += [matplotlib.lines.Line2D([], [], color=INK2, linestyle=ls, label=chain) for chain, ls in style.items()]
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xticks(sorted(sc.devices.unique()), [str(d) for d in sorted(sc.devices.unique())])
    ax.minorticks_off()
    ax.set_xlabel("IoT devices (each of the 10 real devices split over k devices)")
    ax.set_ylabel("Messages processed per second (log)")
    ax.set_title("Throughput vs number of devices: single node vs QBFT network")
    ax.set_title(ax.get_title(loc="left"), loc="left", pad=48)
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, borderaxespad=0.3,
              handlelength=3.2)
    save(fig, "14_scaling_single_node_vs_qbft",
         "5,000 realistic-replay messages per point, the same messages and timing at every point; 2 edges, 1 fog."
         " Dashed: task 1 runs on one Anvil node (instant blocks); solid: 4 QBFT validators. The two per-event lines"
         " overlap at about 60 messages/s.")
    sc.sort_values(["chain", "mode", "devices"]).round(1).to_csv(TAB / "scaling.csv", index=False)


def task2(s: dict) -> None:
    t2 = task2_table(load_runs(s))
    t2.round(4).to_csv(TAB / "runs.csv", index=False)
    summary = (t2[t2.group.isin(["comparison", "await_all"])].groupby(["chain", "mode"])
               .agg(runs=("seed", "size"), throughput_eps=("throughput_eps", "mean"),
                    message_latency_mean_s=("message_latency_mean_s", "mean"),
                    message_latency_p95_s=("message_latency_p95_s", "mean"),
                    commit_latency_ms=("commit_latency_ms", "mean"),
                    processing_record_latency_ms=("processing_record_latency_ms", "mean"),
                    gas_per_event=("gas_per_event", "mean"), node_cpu_s=("node_cpu_s", "mean"),
                    node_peak_rss_mb=("node_peak_rss_mb", "mean"), cloud_f1_macro=("cloud_f1_macro", "mean"),
                    failed=("failed", "sum"), rejected=("events_rejected", "sum")))
    summary.round(4).to_csv(TAB / "chain_comparison.csv")
    for fn in (fig_t2_latency, fig_t2_throughput, fig_t2_block_period, fig_t2_scaling):
        fn(t2)
    try:
        fig_security(s)
    except FileNotFoundError as exc:
        print(f"skipped fig_security: {exc}", file=sys.stderr)


FAULT_ORDER = ["device_off", "edge_down", "fog_down", "cloud_down", "node_down", "quorum_lost"]
FAULT_LABEL = {"reference": "No fault", "device_off": "One device off", "edge_down": "One edge down",
               "fog_down": "One fog down", "cloud_down": "Cloud down", "node_down": "1 of 4 validators down",
               "quorum_lost": "2 of 4 validators down"}
POLICY_COLOR = {"recover": SLOTS[0], "none": SLOTS[1]}
POLICY_LABEL = {"recover": "With recovery (failover, store and forward)", "none": "Without recovery"}
PRED_COLUMNS = ["device_pred", "edge_pred", "fog_pred", "cloud_pred"]


def _fault_window(r) -> tuple[float, float]:
    """(failure, repair) in s since the stream start; the repair is the first one during the stream (for 2 of 4
    validators down: the restart that brings back the quorum)."""
    log = r.faults["log"]
    downs = [e["t_s"] for e in log if e["action"] == "down"]
    ups = [e["t_s"] for e in log if e["action"] == "up" and not e.get("at_end_of_stream")]
    ups = ups or [e["t_s"] for e in log if e["action"] == "up"]
    return (min(downs), min(ups)) if downs else (np.nan, np.nan)


def _mean(x: np.ndarray) -> float:
    return float(x.mean()) if len(x) else np.nan


def fault_table(runs: pd.DataFrame, s: dict) -> pd.DataFrame:
    """One row per run: event accounting, continuity, recovery, chain behaviour and prediction identity."""
    ref_rows = {m: pd.read_parquet(s["rows"] / f"reference_{m}_recover.parquet").set_index("event_id")
                for m in ("batch", "per_event")}
    ref_alerts = {r.fault_run["mode"]: r.alerts for _, r in runs.iterrows() if r.fault_run["scenario"] == "reference"}
    out = []
    for _, r in runs.iterrows():
        k, f = r.fault_run, r.faults
        m, tl = f["messages"], np.array(f["timeline"], dtype=float).reshape(-1, 3)
        tl = tl[tl[:, 1] > 0]
        t, n, lat = tl[:, 0], tl[:, 1], tl[:, 2] / 1000
        generated = t - lat
        down, up = _fault_window(r)
        if np.isnan(down):                                       # the reference: same window, nothing fails
            down, up = 30.0, 60.0
        end = t.max()
        ref = ref_rows[k["mode"]]
        rows = pd.read_parquet(s["rows"] / f"{k['key']}.parquet").set_index("event_id")[PRED_COLUMNS]
        common = rows.index.intersection(ref.index)
        missing = ref.loc[ref.index.difference(rows.index)]   # lost, or never sent by a device that was off
        unsent = f["counts"].get("unsent_device_off", 0)
        blocks = np.array(f["block_times_s"] or [])
        after_up = blocks[blocks >= up]
        resync = [e for e in f["log"] if e["action"] == "resynced"]
        out.append({
            "scenario": k["scenario"], "mode": k["mode"], "policy": k["policy"],
            **{key: m[key] for key in ("generated", "sent", "delivered", "lost", "duplicates", "rejected")},
            "unsent_device_off": f["counts"].get("unsent_device_off", 0),
            "rerouted_or_held": sum(f["counts"].get(c, 0) for c in ("rerouted_edge", "rerouted_fog", "held_for_cloud")),
            "fault_s": round(down, 1), "repair_s": round(up, 1),
            "longest_gap_s": float(np.diff(np.concatenate([[0.0], t])).max()),
            "throughput_before": n[t < down].sum() / down,
            "throughput_during": n[(t >= down) & (t < up)].sum() / (up - down),
            "throughput_after": n[t >= up].sum() / (end - up) if end > up else np.nan,
            "latency_before_s": _mean(lat[generated < down]),
            "latency_fault_s": _mean(lat[(generated >= down) & (generated < up)]),
            "latency_max_s": lat.max(),
            # recovery: from the repair until every message generated before it has reached the cloud
            "recovery_s": max(0.0, t[generated < up].max() - up) if (generated < up).any() else 0.0,
            "failover_after_s": f["failovers"][0]["t_s"] - down if f["failovers"] else np.nan,
            "failovers": len(f["failovers"]),
            "blocks_per_s_fault": ((blocks >= down) & (blocks < up)).sum() / (up - down) if len(blocks) else np.nan,
            "longest_block_gap_s": float(np.diff(blocks[blocks >= 0]).max()) if len(blocks) > 1 else np.nan,
            "first_block_after_repair_s": after_up.min() - up if len(after_up) else np.nan,
            "resync_s": "; ".join(f"{e['target']} {e['resynced_after_s']:.1f}" for e in resync),
            # what the lost messages were in the reference run (no run has both lost and unsent messages)
            "attack_messages_lost": int(missing.attack_label.sum()) if m["lost"] and not unsent else 0,
            "lost_flagged_by_cloud_in_reference": int((missing.cloud_pred != "Normal").sum()) if m["lost"] else 0,
            "alerts": r.alerts, "alerts_vs_reference": r.alerts - ref_alerts[k["mode"]],
            "predictions_identical": float((rows.loc[common] == ref.loc[common, PRED_COLUMNS]).all(axis=1).mean()),
            "messages_compared": len(common),
            "failed_tx": sum(v["failed"] for v in r.chain.values()),
            "consistent": r.chain_network["consensus"]["consistent"], "wall_s": r.resources["wall_s"],
        })
    return pd.DataFrame(out)


def _shade(ax, r, **kw) -> None:
    down, up = _fault_window(r)
    if not np.isnan(down):
        ax.axvspan(down, up, color=GRID, alpha=0.6, lw=0, **kw)


def _timeline(r) -> np.ndarray:
    """Deliveries to the cloud: [s since start, messages, latency ms], empty deliveries dropped."""
    tl = np.array(r.faults["timeline"], dtype=float).reshape(-1, 3)
    return tl[tl[:, 1] > 0]


def _cumulative(r) -> tuple[np.ndarray, np.ndarray]:
    tl = _timeline(r)
    return np.concatenate([[0.0], tl[:, 0]]), np.concatenate([[0.0], np.cumsum(tl[:, 1])])


def _latency(r) -> tuple[np.ndarray, np.ndarray]:
    tl = _timeline(r)
    return tl[:, 0] - tl[:, 2] / 1000, tl[:, 2] / 1000           # placed at the time the messages were generated


def _fault_runs(runs: pd.DataFrame, scenario: str, mode: str = "batch") -> dict:
    sel = runs[runs.fault_run.map(lambda k: k["scenario"] == scenario and k["mode"] == mode)]
    return {r.fault_run["policy"]: r for _, r in sel.iterrows()}


def _fault_panels(runs: pd.DataFrame, series, points: bool, ylabel: str, title: str, name: str, note: str,
                  log_y: bool = False) -> None:
    """One panel per fault (own time axis, shared y): the reference in grey, each policy in its colour."""
    ref = _fault_runs(runs, "reference")["recover"]
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.6), sharey=True)
    for ax, scenario in zip(axes.flat, FAULT_ORDER, strict=True):
        found = _fault_runs(runs, scenario)
        _shade(ax, next(iter(found.values())))
        for policy, r in [("reference", ref), *found.items()]:
            x, y = series(r)
            color = INK2 if policy == "reference" else POLICY_COLOR[policy]
            if points and policy != "reference":         # hollow on top, so identical points show both
                ax.plot(x, y, "o", color=color, ms=6 if policy == "none" else 3.5, alpha=0.9,
                        mfc="none" if policy == "none" else color, mew=1.2)
            else:
                ax.plot(x, y, color=color, lw=1.2 if policy == "reference" else 1.8,
                        alpha=0.6 if policy == "reference" else 1, ls="--" if policy == "none" else "-")
        ax.set_title(FAULT_LABEL[scenario], fontsize=11, loc="left", pad=6)
        ax.set_xlim(0, None)
        ax.grid(axis="x", visible=False)
        if log_y:
            ax.set_yscale("log")
            ax.yaxis.set_major_locator(matplotlib.ticker.FixedLocator([1, 2, 5, 10, 20, 50, 100, 200]))
            ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,g}"))
    for ax in axes[1]:
        ax.set_xlabel("Seconds since the stream started")
    fig.supylabel(ylabel, fontsize=11, color=INK2)
    recover = (matplotlib.lines.Line2D([], [], color=SLOTS[0], ls="none", marker="o", ms=4) if points
               else matplotlib.lines.Line2D([], [], color=SLOTS[0], lw=1.8))
    none = (matplotlib.lines.Line2D([], [], color=SLOTS[1], ls="none", marker="o", ms=6, mfc="none", mew=1.2) if points
            else matplotlib.lines.Line2D([], [], color=SLOTS[1], lw=1.8, ls="--"))
    handles = [matplotlib.lines.Line2D([], [], color=INK2, lw=1.2, alpha=0.6), recover, none,
               matplotlib.patches.Patch(color=GRID, alpha=0.6)]
    labels = ["No fault", POLICY_LABEL["recover"], POLICY_LABEL["none"], "Component down"]
    fig.suptitle(title, x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.01, 0.955), ncol=4, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    save(fig, name, note)


def fig_fault_throughput(runs: pd.DataFrame) -> None:
    _fault_panels(runs, _cumulative, False, "Messages delivered to the cloud (cumulative)",
                  "Pipeline continuity: messages reaching the cloud while a component is down",
                  "15_fault_continuity",
                  "Dataset v2 realistic replay, 10,000 messages, Merkle batch mode, 4 QBFT validators at 1 block/s;"
                  " 2 edges, 2 fogs, 1 cloud. Each component fails 30 s into the stream and is repaired 30 s later"
                  " (2 of 4 validators: the second is repaired after the stream). A flat line is a stall; a lower end"
                  " is loss.")


def fig_fault_latency(runs: pd.DataFrame) -> None:
    _fault_panels(runs, _latency, True, "Message latency (s, log scale)", "Message latency while a component is down",
                  "16_fault_latency",
                  "Same runs as figure 15. Each point is one micro-batch's delivery to the cloud, placed at the time"
                  " its messages were generated; messages held for the cloud or waiting out a halted chain arrive"
                  " late. No messages are generated while the chain is halted.", log_y=True)


def fig_fault_loss(t: pd.DataFrame) -> None:
    d = t[(t["mode"] == "batch") & (t.scenario != "reference")]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    y = {sc: i for i, sc in enumerate(FAULT_ORDER)}
    for policy, offset in (("recover", -0.12), ("none", 0.12)):
        p = d[d.policy == policy]
        ax.scatter(p.lost, [y[s] + offset for s in p.scenario], s=64, color=POLICY_COLOR[policy], zorder=3,
                   edgecolors=SURFACE, linewidths=2, label=POLICY_LABEL[policy])
        for _, row in p.iterrows():
            label = f"{row.lost:,} ({row.lost / row.sent:.1%})"
            if row.lost:
                label += f", of which {row.attack_messages_lost:,} attack messages"
            ax.annotate(label, (row.lost, y[row.scenario] + offset), xytext=(8, 0),
                        textcoords="offset points", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(list(y.values()), [FAULT_LABEL[s] for s in y])
    ax.invert_yaxis()
    ax.set_xlim(-100, d.lost.max() * 1.9 + 100)
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel("Messages lost (of the messages the devices sent)")
    ax.set_title("Event loss: with and without recovery")
    legend_top(ax, ncol=2)
    save(fig, "17_fault_event_loss",
         "Same runs as figure 15. A device that is off sends nothing: its unsent messages are not counted as lost."
         " Validator faults are always handled by the client's failover.")


def fig_fault_blocks(runs: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.6))
    styles = {"reference": (INK2, "-"), "node_down": (SLOTS[0], "-"), "quorum_lost": (SLOTS[1], "-")}
    for scenario, (color, ls) in styles.items():
        r = _fault_runs(runs, scenario)["recover"]
        b = np.array(r.faults["block_times_s"])
        b = b[b >= 0]
        ax.step(b, np.arange(1, len(b) + 1), where="post", color=color, ls=ls, lw=1.8, label=FAULT_LABEL[scenario])
    down, up = _fault_window(_fault_runs(runs, "node_down")["recover"])
    ax.axvspan(down, up, color=GRID, alpha=0.6, lw=0, label="Validator(s) down")
    ax.set_xlabel("Seconds since the stream started")
    ax.set_ylabel("Blocks produced since the stream started")
    ax.set_title("Block production when validators fail")
    legend_top(ax, ncol=4)
    save(fig, "18_fault_blocks",
         "Merkle batch runs of figure 15. 1 of 4 down: validator 1 crashes at 30 s and restarts at 60 s; QBFT keeps"
         " the quorum (3 of 4). 2 of 4 down: validators 2 and 3 crash at 30 s; validator 3 restarts at 60 s, which"
         " restores the quorum; validator 2 restarts after the stream.")


def faults(s: dict) -> None:
    runs = load_runs(s)
    t = fault_table(runs, s)
    t.round(4).to_csv(TAB / "faults_summary.csv", index=False)
    fig_fault_throughput(runs)
    fig_fault_latency(runs)
    fig_fault_loss(t)
    fig_fault_blocks(runs)


# ---- final task 3: AI-driven blockchain (when the gateway commits each device's Merkle batch) --------------------

T3_COLOR = {"fixed": INK2, "interval": "#a3a29d", "rule": SLOTS[1], "forecast": SLOTS[0], "rate": SLOTS[3],
            "oracle": SLOTS[2]}
T3_LABEL = {"fixed": "Fixed: one root per device per round (task 2)", "interval": "Fixed interval: every k-th round",
            "rule": "Rule: hold every small batch", "forecast": "AI: hold when the forecast says it pays",
            "rate": "Poisson-rate forecast (no learning)", "oracle": "Perfect foresight (reference)"}
T3_SHORT = {"fixed": "Fixed", "interval": "Interval", "rule": "Rule", "forecast": "AI", "oracle": "Perfect foresight"}
T3_LIVE = ["fixed", "rule", "forecast", "oracle"]
PER_EVENT_GAS_T2 = 161_618              # task 2 §10.7: per-event gas per message at every device count (QBFT)


def _t3_setting(spec: dict, default: dict) -> str:
    """Short name of a live run's setting: 'AI', 'AI, N = 16', 'Rule, H = 2', 'AI, attacks never held', ..."""
    name = T3_SHORT[spec["policy"]] + (f" {spec['every']}" if spec["policy"] == "interval" else "")
    if spec["policy"] in ("fixed", "interval"):
        return name
    extra = [f"{label} = {spec[k]:g}" for k, label in (("hold_rounds", "H"), ("break_even", "N")) if spec[k] != default[k]]
    if spec.get("protect_suspicious"):
        extra.append("attacks never held")
    return ", ".join([name, *extra])


def task3_table(runs: pd.DataFrame, s: dict) -> pd.DataFrame:
    """One row per live run, with three checks: predictions identical to the fixed run (same chain, devices, seed),
    live roots equal to the offline simulation of the same setting, and the usual run health."""
    from src.common.config import load_config

    default = load_config("experiments")["suites"]["final_task3"]["policy"]
    sim = pd.read_csv(s["simulation"])
    sim = sim[sim["rows"] == runs.iloc[0].events_in]
    rows = []
    for _, r in runs.iterrows():
        t, spec, ch = r.task3, r.task3["commit_policy"], r.chain
        n, cs, lat = r.events_processed, r.commit_schedule, r.message_latency_ms
        cloud = next(a for a in r.accuracy if (a["layer"], a["task"]) == ("cloud", "multiclass"))
        merkle = ch["device_commit"]["gas_total"] + ch["edge_processed"]["gas_total"]
        match = sim[(sim.devices == r.topology["devices"]) & (sim.label == spec["policy"])]
        if spec["policy"] == "interval":
            match = match[match.every == spec["every"]]
        elif spec["policy"] != "fixed":
            match = match[(match.hold_rounds == spec["hold_rounds"]) & (match.break_even == spec["break_even"])
                          & (match.protect_suspicious == spec["protect_suspicious"])]
        rows.append({
            "key": t["key"], "group": t["group"], "chain": "qbft_1s" if t["chain"][0] == "qbft" else "anvil_automine",
            "policy": spec["policy"], "setting": _t3_setting(spec, default), "seed": t["seed"],
            "devices": r.topology["devices"], "roots": ch["device_commit"]["tx_count"],
            "offline_roots": int(match.roots.iloc[0]) if len(match) == 1 else np.nan,
            "processing_records": ch["edge_processed"]["tx_count"], "messages_per_root": n / ch["device_commit"]["tx_count"],
            "merkle_gas_per_msg": merkle / n,
            "gas_per_msg": sum(v["gas_total"] for k, v in ch.items()
                               if k in ("device_commit", "edge_processed", "fog_alert_audit", "cloud_inference_record")) / n,
            "latency_mean_s": lat["all"]["mean_ms"] / 1000, "latency_p95_s": lat["all"]["p95_ms"] / 1000,
            "attack_latency_mean_s": lat["attack"]["mean_ms"] / 1000, "normal_latency_mean_s": lat["normal"]["mean_ms"] / 1000,
            "throughput_eps": r.throughput_eps, "held_rounds_per_message": cs["held_rounds_per_message"],
            "holds": cs["holds"], "merged_roots": cs["merged_roots"], "wasted_holds": cs["wasted_holds"],
            "commit_latency_ms": ch["device_commit"]["latency_mean_ms"], "alerts": r.alerts,
            "failed": sum(v["failed"] for v in ch.values()), "rejected": r.events_rejected, "processed": n,
            "consistent": r.chain_network.get("consensus", {}).get("consistent"),
            "cloud_f1_macro": cloud["f1_macro"], "node_cpu_s": r.resources.get("node_cpu_s"), "wall_s": r.resources["wall_s"],
        })
    df = pd.DataFrame(rows)
    fixed = {(x.chain, x.devices, x.seed): x.key for x in df[df.policy == "fixed"].itertuples()}

    def identical(x) -> float:
        ref = pd.read_parquet(s["rows"] / f"{fixed[(x.chain, x.devices, x.seed)]}.parquet").set_index("event_id")
        mine = pd.read_parquet(s["rows"] / f"{x.key}.parquet").set_index("event_id")
        if set(ref.index) != set(mine.index):
            return 0.0
        return float((mine.loc[ref.index, PRED_COLUMNS] == ref[PRED_COLUMNS]).all(axis=1).mean())

    df["predictions_identical"] = [identical(x) for x in df.itertuples()]
    waits = _t3_latency_by_wait(runs, s)
    df = df.merge(waits, on="key", how="left")
    ref = df[df.policy == "fixed"].set_index(["chain", "devices", "seed"])
    idx = pd.MultiIndex.from_frame(df[["chain", "devices", "seed"]])
    df["roots_vs_fixed"] = df.roots.to_numpy() / ref.roots.reindex(idx).to_numpy()
    df["gas_vs_fixed"] = df.gas_per_msg.to_numpy() / ref.gas_per_msg.reindex(idx).to_numpy()
    df["latency_added_s"] = df.latency_mean_s.to_numpy() - ref.latency_mean_s.reindex(idx).to_numpy()
    return df


def _t3_latency_by_wait(runs: pd.DataFrame, s: dict) -> pd.DataFrame:
    """Each run's message latency split by how many rounds the message waited at the gateway. The waits are replayed
    offline with the run's own policy (the same decisions: live roots = offline roots) and joined on the event ids,
    which are fixed per seed."""
    import os
    import uuid

    os.environ["BLOCKIOT_VIEW"] = "real_time"
    from src.device.commit_policy import CommitScheduler, TrafficForecaster, future_rounds, make_policy, timing_events
    from src.device.simulator import RealtimeReplay
    from src.pipeline import load_replay_rows

    replay, _ = load_replay_rows(int(runs.iloc[0].events_in))
    forecaster = TrafficForecaster()
    out = []
    for _, r in runs.iterrows():
        t = r.task3
        sim = RealtimeReplay(replay, seed=t["seed"], replicas=t["replicas"])
        batch = r.topology["batch_size"]
        policy = make_policy(dict(t["commit_policy"]), forecaster=forecaster, future=future_rounds(sim.device_of, batch))
        ns = uuid.UUID(int=t["seed"])
        index = {str(uuid.uuid5(ns, str(i))): i for i in range(len(sim))}
        rows = pd.read_parquet(s["rows"] / f"{t['key']}.parquet")
        flags = np.zeros(len(sim), dtype=int)            # the device model's flag, as the live scheduler saw it
        flags[rows.event_id.map(index).to_numpy()] = rows.device_pred.astype(int).to_numpy()
        scheduler, wait = CommitScheduler(policy, sim.device_ids), np.zeros(len(sim))
        n_rounds = -(-len(sim) // batch)
        for k, events in enumerate(timing_events(sim, batch, flags)):
            for e in scheduler.step(events, final=k == n_rounds - 1):
                wait[e["i"]] = k - e["i"] // batch
        if scheduler.stats["roots"] != r.chain["device_commit"]["tx_count"]:
            raise ValueError(f"{t['key']}: replayed decisions differ from the live run")
        w = rows.event_id.map(index).map(lambda i, wait=wait: wait[i])
        out.append({"key": t["key"], "messages_waited": int((w > 0).sum()),
                    "latency_not_waited_s": rows.e2e_ms[w == 0].mean() / 1000,
                    "latency_waited_1_s": rows.e2e_ms[w == 1].mean() / 1000 if (w == 1).any() else np.nan,
                    "latency_waited_2_s": rows.e2e_ms[w == 2].mean() / 1000 if (w == 2).any() else np.nan,
                    "round_s": r.latency_ms["batch_end_to_end"]["mean_ms"] / 1000})
    return pd.DataFrame(out)


def _t3_scaling(df: pd.DataFrame, chain: str = "qbft_1s") -> pd.DataFrame:
    d = df[(df.group == "scaling") & (df.chain == chain)] if chain == "qbft_1s" else df[df.chain == chain]
    return d.sort_values("devices")


def _end_labels(ax, x, y, fmt: str, dy: int = 0) -> None:
    ax.annotate(fmt.format(y.iloc[-1]), (x.iloc[-1], y.iloc[-1]), xytext=(7, dy), textcoords="offset points",
                va="center", fontsize=8.5, color=INK2)


def _devices_axis(ax, devices) -> None:
    ax.set_xscale("log")
    ax.set_xticks(devices, [str(d) for d in devices])
    ax.minorticks_off()
    ax.set_xlabel("IoT devices (each of the 10 real devices split over k devices)")


def fig_t3_gas(df: pd.DataFrame) -> None:
    d = _t3_scaling(df)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    # the rule and perfect foresight commit exactly the same roots (so the same gas): the rule is dashed on top
    for policy in ("fixed", "oracle", "forecast", "rule"):
        p = d[d.policy == policy]
        dashed = policy == "rule"
        ax.plot(p.devices, p.gas_per_msg / 1000, marker="o", color=T3_COLOR[policy], label=T3_LABEL[policy],
                ls=(0, (4, 3)) if dashed else "-", mfc="none" if dashed else T3_COLOR[policy],
                markeredgecolor=T3_COLOR[policy] if dashed else SURFACE, markeredgewidth=1.5 if dashed else 2,
                zorder=4 if dashed else 3 if policy == "forecast" else 2)
    for policy, label, dy in (("fixed", "{:.1f}k", 0), ("forecast", "{:.1f}k", 6),
                              ("rule", "{:.1f}k: rule and perfect foresight", -8)):
        p = d[d.policy == policy]
        _end_labels(ax, p.devices, p.gas_per_msg / 1000, label, dy)
    ax.axhline(PER_EVENT_GAS_T2 / 1000, color=INK2, ls=":", lw=1.2)
    ax.annotate(f"Per-event commits (task 2): {PER_EVENT_GAS_T2 / 1000:.1f}k", (10, PER_EVENT_GAS_T2 / 1000),
                xytext=(0, -12), textcoords="offset points", fontsize=8.5, color=INK2)
    _devices_axis(ax, sorted(d.devices.unique()))
    ax.set_xlim(8, 1400)
    ax.set_ylim(0, None)
    ax.set_ylabel("Gas per message (thousands)")
    ax.set_title("Gas per message vs number of devices: fixed batching vs AI-scheduled commits")
    ax.set_title(ax.get_title(loc="left"), loc="left", pad=48)
    handles, labels = ax.get_legend_handles_labels()
    order = [labels.index(T3_LABEL[p]) for p in T3_LIVE]
    ax.legend([handles[i] for i in order], [labels[i] for i in order], loc="lower left", bbox_to_anchor=(0, 1.0),
              ncol=2, borderaxespad=0.3, handlelength=2.4)
    save(fig, "19_gas_per_message_vs_devices",
         "Task 2's scaling workload: 5,000 realistic-replay messages per point (the same messages and timing), 2 edges,"
         " 1 fog, 4 QBFT validators at 1 block/s. Rule, AI and perfect foresight: a batch waits at most one extra"
         " round (H = 1); one root's gas is worth delaying 4 messages by one round (N = 4). Gas of every event-path"
         " write (commitments, processing records, alert audits, inference records).")


def fig_t3_latency(df: pd.DataFrame) -> None:
    d = _t3_scaling(df)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    offsets = {"fixed": -6, "rule": 6, "forecast": 0, "oracle": -12}
    for policy in T3_LIVE:
        p = d[d.policy == policy]
        ax.plot(p.devices, p.latency_mean_s, marker="o", color=T3_COLOR[policy], label=T3_LABEL[policy],
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=3 if policy == "forecast" else 2)
        _end_labels(ax, p.devices, p.latency_mean_s, "{:.2f} s", offsets[policy])
    _devices_axis(ax, sorted(d.devices.unique()))
    ax.set_xlim(8, 800)
    ax.set_ylim(0, None)
    ax.set_ylabel("Message latency, mean (s)")
    ax.set_title("What holding batches costs: message latency vs number of devices")
    ax.set_title(ax.get_title(loc="left"), loc="left", pad=48)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, borderaxespad=0.3, handlelength=1.6)
    save(fig, "20_latency_vs_devices",
         "Same runs as figure 19. Per message, from its arrival at the device layer to its cloud result, including"
         " the rounds it waited at the gateway.")


def fig_t3_tradeoff(sim: pd.DataFrame, df: pd.DataFrame, devices: int = 500) -> None:
    d = sim[(sim["rows"] == df.processed.iloc[0]) & (sim.devices == devices)].copy()
    fixed_roots = d[d.label == "fixed"].roots.iloc[0]
    d["ratio"] = d.roots / fixed_roots
    live = df[(df.chain == "qbft_1s") & (df.devices == devices) & (df.seed == df.seed.min())]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, h in zip(axes, (1, 2), strict=True):
        for label in ("rule", "rate", "forecast", "oracle"):
            p = d[(d.label == label) & (d.hold_rounds == h) & (d.protect_suspicious == False)]  # noqa: E712
            p = p.sort_values("break_even")
            x = np.concatenate([[0.0], p.held_rounds_per_message])
            y = np.concatenate([[1.0], p.ratio])
            ax.plot(x, y, marker="o", ms=5, color=T3_COLOR[label], label=T3_LABEL[label], markeredgecolor=SURFACE,
                    markeredgewidth=1.2, zorder=3 if label == "forecast" else 2)
            if label == "forecast":
                for _, row in p[p.break_even.isin([1.5, 4, 16])].iterrows():
                    ax.annotate(f"N = {row.break_even:g}", (row.held_rounds_per_message, row.ratio), xytext=(5, -13),
                                textcoords="offset points", fontsize=8, color=SLOTS[0])
        iv = d[(d.label == "interval") & (d.every == h + 1)]
        ax.scatter(iv.held_rounds_per_message, iv.ratio, marker="s", s=60, color=T3_COLOR["interval"], zorder=3,
                   edgecolors=SURFACE, linewidths=1.5, label=f"{T3_LABEL['interval']} (k = H + 1)")
        lv = live[(live.policy.isin(["rule", "forecast", "oracle", "interval"]))]
        lv = lv[lv.key.str.contains(f"hold_rounds{h}") | (lv.policy == "interval") & (h == 1)]
        lv = lv[~lv.key.str.contains("protect_suspiciousTrue")]
        ax.scatter(lv.held_rounds_per_message, lv.roots_vs_fixed, s=110, facecolors="none", edgecolors=INK, lw=1.2,
                   zorder=4, label="Live run on the QBFT network")
        ax.scatter([0], [1], s=60, color=T3_COLOR["fixed"], zorder=4)
        ax.annotate("Fixed", (0, 1), xytext=(6, 4), textcoords="offset points", fontsize=8.5, color=INK2)
        ax.set_title(f"A batch waits at most {h} extra round{'s' if h > 1 else ''} (H = {h})", fontsize=11, pad=6)
        ax.set_xlabel("Added delay at the gateway (rounds per message, mean)")
        ax.set_xlim(-0.03, None)
    axes[0].set_ylabel("Merkle roots, relative to fixed batching")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle(f"The gas–latency trade-off at {devices} devices: every policy over its whole range", x=0.01,
                 ha="left", fontsize=13, fontweight="bold")
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.01, 0.95), ncol=3, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    save(fig, "21_tradeoff_at_500_devices",
         "Offline simulation with the scheduler code of the live runs, task 2's 5,000-message workload. Each line"
         " sweeps the price of latency N (1 to 32: one root is worth delaying N messages by one round); lower and"
         " further left is better. Circles: live QBFT runs (N = 4, and N = 16 for H = 1), on their offline points.")


def fig_t3_holds(df: pd.DataFrame, devices: int = 500) -> None:
    d = df[(df.chain == "qbft_1s") & (df.devices == devices) & (df.seed == df.seed.min())
           & df.policy.isin(["rule", "forecast", "oracle"]) & df.group.isin(["scaling", "protect"])]
    d = d.sort_values(["group", "policy"], key=lambda c: c.map({"scaling": 0, "protect": 1, "rule": 0, "forecast": 1,
                                                                "oracle": 2}))
    fig, ax = plt.subplots(figsize=(9, 3.9))
    y = np.arange(len(d))
    ax.barh(y, d.merged_roots, color=SLOTS[0], height=0.6, edgecolor=SURFACE, linewidth=2,
            label="Held, and later messages joined: one root saved")
    ax.barh(y, d.wasted_holds, left=d.merged_roots, color=GRID, height=0.6, edgecolor=SURFACE, linewidth=2,
            label="Held, and nothing joined: delay for nothing")
    for yy, (_, row) in zip(y, d.iterrows(), strict=True):
        ax.annotate(f"{row.merged_roots:,} + {row.wasted_holds:,}", (row.merged_roots + row.wasted_holds, yy),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(y, d.setting)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, (d.merged_roots + d.wasted_holds).max() * 1.2)
    ax.set_xlabel("Batches held at least one round")
    ax.set_title(f"Why the AI adds less delay: which holds paid off ({devices} devices)")
    legend_top(ax, ncol=1)
    ax.set_title(ax.get_title(loc="left"), loc="left", pad=44)
    save(fig, "22_holds_paid_off",
         "Live QBFT runs of figure 19 at 500 devices (H = 1, N = 4), plus the variants that never hold a batch with a"
         " message the device model flags as an attack.")


def fig_t3_attack_latency(df: pd.DataFrame, devices: int = 500) -> None:
    d = df[(df.chain == "qbft_1s") & (df.devices == devices) & (df.seed == df.seed.min())
           & df.group.isin(["scaling", "protect"])]
    d = d.sort_values(["group", "policy"], key=lambda c: c.map({"scaling": 0, "protect": 1, "fixed": 0, "rule": 1,
                                                                "forecast": 2, "oracle": 3}))
    fig, ax = plt.subplots(figsize=(10, 4.6))
    x = np.arange(len(d))
    for i, (col, label, color) in enumerate((("attack_latency_mean_s", "Attack messages", SLOTS[1]),
                                             ("normal_latency_mean_s", "Normal messages", SLOTS[0]))):
        bars = ax.bar(x + (i - 0.5) * 0.38, d[col], 0.38, color=color, label=label, edgecolor=SURFACE, linewidth=2)
        bar_labels(ax, bars, "{:.2f}")
    ax.set_xticks(x, [sv.replace(", attacks never held", ",\nattacks\nnever held").replace("Perfect foresight",
                                                                                         "Perfect\nforesight")
                      for sv in d.setting])
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Message latency, mean (s)")
    ax.set_title(f"Who pays the delay: attack vs normal messages ({devices} devices)")
    legend_top(ax, ncol=2)
    fig.subplots_adjust(bottom=0.2)                 # room for the three-line labels above the note
    save(fig, "23_attack_vs_normal_latency",
         "\nSame runs as figure 22. An attack message's latency is when the fog and the cloud can act on it."
         " 'Attacks never held': a batch with a message the device model flags as an attack is committed at once.")


def fig_t3_throughput(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    style = {"anvil_automine": "--", "qbft_1s": "-"}
    chain_label = {"anvil_automine": "1 node, instant blocks", "qbft_1s": "4 validators (QBFT), 1 block/s"}
    for chain in ("anvil_automine", "qbft_1s"):
        d = _t3_scaling(df, chain)
        for policy in ("fixed", "forecast"):
            p = d[d.policy == policy]
            ax.plot(p.devices, p.throughput_eps, marker="o", color=T3_COLOR[policy], ls=style[chain],
                    markeredgecolor=SURFACE, markeredgewidth=2)
            _end_labels(ax, p.devices, p.throughput_eps, "{:,.0f}", 6 if policy == "forecast" else -6)
    handles = [matplotlib.lines.Line2D([], [], color=T3_COLOR[p], marker="o", markeredgecolor=SURFACE,
                                       markeredgewidth=2, label=T3_LABEL[p]) for p in ("fixed", "forecast")]
    handles += [matplotlib.lines.Line2D([], [], color=INK2, ls=ls, label=chain_label[c]) for c, ls in style.items()]
    _devices_axis(ax, sorted(df.devices.unique()))
    ax.set_xlim(8, 900)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_ylabel("Messages processed per second (log)")
    ax.set_title("Throughput vs number of devices: fixed batching vs AI-scheduled commits")
    ax.set_title(ax.get_title(loc="left"), loc="left", pad=48)
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, borderaxespad=0.3,
              handlelength=3.2)
    save(fig, "24_throughput_vs_devices",
         "Same workload as figure 19 (H = 1, N = 4). Dashed: one Anvil node mining every transaction at once (task 1's"
         " chain), with the same client as the QBFT runs; solid: 4 QBFT validators.")


def tradeoff_table(sim: pd.DataFrame) -> pd.DataFrame:
    """Added delay each policy needs to cut the roots to a target share of fixed batching, read off the lower convex
    envelope of its sweep from (0 delay, all roots); interpolating means mixing two settings of the policy."""
    def hull(points):
        pts = sorted({(0.0, 1.0), *points})
        h = []
        for p in pts:
            while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (p[1] - h[-2][1])
                                   - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0])) <= 0:
                h.pop()
            h.append(p)
        out = [h[0]]
        for p in h[1:]:
            if p[1] < out[-1][1]:
                out.append(p)
        return np.array(out)

    def delay_at(h, target):
        if h[:, 1].min() > target:
            return np.nan
        i = int(np.argmax(h[:, 1] <= target))
        (x0, y0), (x1, y1) = h[i - 1], h[i]
        return x0 + (target - y0) * (x1 - x0) / (y1 - y0)

    rows = []
    sim = sim[sim.protect_suspicious != True]  # noqa: E712
    for (n, dev), g in sim.groupby(["rows", "devices"]):
        fixed_roots = g[g.label == "fixed"].roots.iloc[0]
        for h in sorted(g.hold_rounds.dropna().unique()):
            hulls = {lab: hull(list(zip(q.held_rounds_per_message, q.roots / fixed_roots, strict=True)))
                     for lab in ("rule", "forecast", "rate", "oracle")
                     for q in [g[(g.label == lab) & (g.hold_rounds == h)]]}
            for target in (0.9, 0.8, 0.7, 0.6, 0.5):
                v = {lab: delay_at(hh, target) for lab, hh in hulls.items()}
                if any(np.isnan(x) for x in v.values()):
                    continue
                gap = v["rule"] - v["oracle"]
                rows.append({"rows": n, "devices": dev, "hold_rounds": int(h), "roots_target": target,
                             **{f"delay_{k}": x for k, x in v.items()},
                             "ai_vs_rule": v["forecast"] / v["rule"] - 1 if v["rule"] else np.nan,
                             "ai_share_of_foresight_gain": (v["rule"] - v["forecast"]) / gap if gap > 1e-9 else np.nan})
    return pd.DataFrame(rows)


def task3(s: dict) -> None:
    runs = load_runs(s)
    df = task3_table(runs, s)
    df.round(4).to_csv(TAB / "runs.csv", index=False)
    sc = df[df.group.isin(["scaling", "single_node"])].pivot_table(
        index=["chain", "devices"], columns="policy",
        values=["gas_per_msg", "merkle_gas_per_msg", "latency_mean_s", "latency_p95_s", "throughput_eps", "roots"])
    sc.round(3).to_csv(TAB / "scaling.csv")
    at500 = (df[(df.chain == "qbft_1s") & (df.devices == df.devices.max())]
             .groupby("setting", sort=False)
             .agg(runs=("seed", "size"), roots=("roots", "mean"), roots_vs_fixed=("roots_vs_fixed", "mean"),
                  gas_per_msg=("gas_per_msg", "mean"), merkle_gas_per_msg=("merkle_gas_per_msg", "mean"),
                  latency_mean_s=("latency_mean_s", "mean"), latency_p95_s=("latency_p95_s", "mean"),
                  latency_added_s=("latency_added_s", "mean"), attack_latency_mean_s=("attack_latency_mean_s", "mean"),
                  normal_latency_mean_s=("normal_latency_mean_s", "mean"), throughput_eps=("throughput_eps", "mean"),
                  held_rounds_per_message=("held_rounds_per_message", "mean"), merged_roots=("merged_roots", "mean"),
                  wasted_holds=("wasted_holds", "mean")))
    at500.round(4).to_csv(TAB / "at_500_devices.csv")
    sim = pd.read_csv(s["simulation"])
    tradeoff_table(sim).round(4).to_csv(TAB / "tradeoff.csv", index=False)
    record = json.loads((s["forecaster"] / json.loads((s["forecaster"] / "current.json").read_text())["model_id"])
                        .with_suffix(".json").read_text())
    quality = pd.read_csv(s["forecast_quality"]).assign(window="test")
    validation = pd.DataFrame([{"window": "validation", **{k: v for k, v in record["metrics"].items()}}])
    pd.concat([validation, quality], ignore_index=True).round(4).to_csv(TAB / "forecaster.csv", index=False)
    fig_t3_gas(df)
    fig_t3_latency(df)
    fig_t3_tradeoff(sim, df)
    fig_t3_holds(df)
    fig_t3_attack_latency(df)
    fig_t3_throughput(df)


def main() -> None:
    global FIG, TAB
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=list(SETS), default="presentation1")
    args = parser.parse_args()
    s = SETS[args.set]
    FIG, TAB = s["out"] / "figures", s["out"] / "tables"
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    if args.set == "final_task2":
        task2(s)
        return
    if args.set == "final_faults":
        faults(s)
        return
    if args.set == "final_task3":
        task3(s)
        return
    runs = load_runs(s)
    fig_accuracy(runs, s)
    fig_latency(runs, s)
    fig_gas(runs, s)
    fig_scaling(runs, s)
    extra = (fig_f1_by_split, fig_unseen_devices) if args.set == "final_task1" else ()
    for fn in (fig_integrity, fig_security, fig_class_recall, *extra):
        try:
            fn(s)
        except FileNotFoundError as exc:
            print(f"skipped {fn.__name__}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
