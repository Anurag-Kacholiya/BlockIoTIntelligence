"""Figures and tables for the first project presentation, built only from files in experiments/.

  python scripts/make_figures.py      ->  docs/presentation1/figures/*.png, docs/presentation1/tables/*.csv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments" / "results"
OUT = ROOT / "docs" / "presentation1"
FIG, TAB = OUT / "figures", OUT / "tables"

# Validated categorical slots 1-3 (light surface); text never wears series colour.
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3de"
MODE_COLOR = {"baseline": "#2a78d6", "per_event": "#eb6834", "batch": "#1baf7a"}
MODE_LABEL = {"baseline": "Baseline (no blockchain)", "per_event": "Blockchain · per-event commit",
              "batch": "Blockchain · Merkle batch commit"}
LAYERS = [("device", "binary"), ("edge", "binary"), ("fog", "multiclass"), ("cloud", "multiclass")]

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


def grouped(ax, categories, series: dict[str, list[float]], errors: dict[str, list[float]] | None, fmt: str):
    n = len(series)
    width = 0.8 / n
    x = np.arange(len(categories))
    for i, (mode, vals) in enumerate(series.items()):
        bars = ax.bar(x + (i - (n - 1) / 2) * width, vals, width, color=MODE_COLOR[mode], label=MODE_LABEL[mode],
                      edgecolor=SURFACE, linewidth=2, yerr=(errors or {}).get(mode), ecolor=INK2, capsize=0,
                      error_kw={"elinewidth": 1})
        bar_labels(ax, bars, fmt)
    ax.set_xticks(x, categories)
    ax.grid(axis="x", visible=False)


def load_runs() -> pd.DataFrame:
    runs = [json.loads(line) for line in (RESULTS / "presentation1" / "runs.jsonl").read_text().splitlines()]
    return pd.DataFrame(runs)


def fig_accuracy(runs: pd.DataFrame) -> pd.DataFrame:
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
             f"Edge-IIoTset DNN view, {int(comp.events_in.iloc[0]):,} held-out events × {comp.reproducibility.map(lambda x: x['seed']).nunique()} seeds (mean ± sd)."
             " The ledger does not alter the data models see, so accuracy on untampered traffic is unchanged.")
    table = stats.round(4)
    table.to_csv(TAB / "accuracy_per_layer.csv")
    return acc


def fig_latency(runs: pd.DataFrame) -> pd.DataFrame:
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
    grouped(ax, cats, {m: [stats.loc[(m, s), "ms_per_event"] for s in stages] for m in modes}, None, "{:.3g}")
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


def fig_integrity() -> None:
    df = pd.read_csv(RESULTS / "exp_integrity_accuracy.csv")
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


def fig_security() -> None:
    df = pd.read_csv(RESULTS / "exp_security.csv")
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
    save(fig, "04_security_detection",
         "Each attack injected in its own pass into real Edge-IIoTset traffic (5% rate). Unauthorized ledger write is"
         " blockchain-only.")
    df.to_csv(TAB / "security.csv", index=False)


def fig_scaling(runs: pd.DataFrame) -> None:
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
        ax.set_xlabel("Logical IoT devices")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        legend_top(ax)
        save(fig, name, f"{int(sc.events_in.iloc[0]):,} held-out events per point, 2 edges, 1 fog, local Anvil chain.")
    cols = ["mode", "devices", "throughput_eps", "e2e"]
    sc[cols].sort_values(["mode", "devices"]).round(3).to_csv(TAB / "scaling.csv", index=False)


def fig_gas(runs: pd.DataFrame) -> None:
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


def fig_class_recall() -> None:
    runs = sorted(RESULTS.glob("baseline-*.json"))
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
    save(fig, "08_cloud_recall_per_class", f"{r['events_processed']:,} held-out events, cloud Random Forest.")


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    runs = load_runs()
    fig_accuracy(runs)
    fig_latency(runs)
    fig_gas(runs)
    fig_scaling(runs)
    for fn in (fig_integrity, fig_security, fig_class_recall):
        try:
            fn()
        except FileNotFoundError as exc:
            print(f"skipped {fn.__name__}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
