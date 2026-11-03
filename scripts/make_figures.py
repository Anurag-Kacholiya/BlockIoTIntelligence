"""Figures and tables built only from files in experiments/.

  python scripts/make_figures.py                     ->  docs/presentation1/{figures,tables}/  (first presentation)
  python scripts/make_figures.py --set final_task1   ->  docs/final/task1/{figures,tables}/    (dataset v2)
  python scripts/make_figures.py --set final_task2   ->  docs/final/task2/{figures,tables}/    (multi-node chain)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.lines  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments" / "results"

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
