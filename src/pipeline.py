"""In-process Device -> Edge -> Fog -> Cloud orchestration (ADR Phase 1 baseline, Phases 2-7).

The same function runs the baseline (blockchain=None) and the blockchain-enabled architecture
(blockchain="per_event" or "batch"), so data, seed, models and topology are identical and only the
ledger differs between runs (ADR §11.1).
"""

from __future__ import annotations

import json
import platform
import time
import uuid
import zlib
from collections import defaultdict
from contextlib import ExitStack
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import sklearn
from sklearn.model_selection import train_test_split

from src.cloud.service import CloudNode
from src.common.config import active_view, config_hash, load_config, resolve
from src.common.metrics import LatencyTracker, ResourceSampler
from src.common.storage import git_commit, read_parquet
from src.data.preparation.clean import TARGETS
from src.data.preparation.realistic import captures, read_events, share_budget, source_row_ids
from src.device.service import DeviceLayer
from src.device.simulator import DeviceSimulator, RealtimeReplay
from src.edge.service import EdgeNode
from src.fog.service import FogNode

if TYPE_CHECKING:
    from src.common.blockchain import Chain
    from src.common.faults import Fault, FaultInjector
    from src.device.commit_policy import CommitScheduler

FAULT_POLICIES = ("recover", "none")


def route(home: int, up: list[bool], policy: str) -> int | None:
    """Component that takes traffic meant for component `home`: itself if it is up; else, with policy "recover", the
    next one (in index order) that is up; None when the traffic is lost."""
    if up[home]:
        return home
    if policy == "recover":
        return next(((home + k) % len(up) for k in range(1, len(up)) if up[(home + k) % len(up)]), None)
    return None


def node_roles(n_nodes: int, edge_ids: list[str], fog_ids: list[str]) -> dict[str, int]:
    """Blockchain node used by each role: device gateway on node 0, then each edge, fog and the cloud on the next
    node, round robin. With one node every role shares it (the mid-term setup)."""
    order = ["device_gateway", *edge_ids, *fog_ids, "cloud"]
    return {role: k % n_nodes for k, role in enumerate(order)}


def attach_blockchain(chains: Chain | list[Chain], mode: str, seed: int, device_ids: list[str],
                      device_layer: DeviceLayer, edge_nodes: list[EdgeNode], fog_nodes: list[FogNode], cloud: CloudNode,
                      audit_writes: str = "await", scheduler: CommitScheduler | None = None) -> dict[str, int]:
    """Deploy IoTRegistry, give every node its own account, register devices and models (ADR §6.2, Phase 6).

    With several blockchain nodes (one Chain each), the roles are spread over them (node_roles), so state written
    through one node is read through another. audit_writes="background" confirms fog alert and cloud inference
    records off the event path. A commit scheduler (final task 3) decides when the gateway's Merkle batches close;
    its forecaster, if it has one, is registered and verified on-chain like the layer models. Returns the node index
    of every role."""
    # Imported here so baseline runs need neither web3 nor the blockchain toolchain.
    from src.cloud.blockchain_client import CloudChainClient
    from src.common.blockchain import id32
    from src.device.blockchain_client import DeviceChainClient
    from src.device.collector import device_keys
    from src.edge.blockchain_client import EdgeChainClient
    from src.fog.blockchain_client import FogChainClient

    chains = chains if isinstance(chains, list) else [chains]
    chain = chains[0]                                  # the owner deploys and sets up through node 0
    chain.deploy()
    for c in chains[1:]:
        c.use(chain.contract.address)
    if audit_writes not in ("await", "background"):
        raise ValueError(audit_writes)
    wait = audit_writes == "await"
    roles = node_roles(len(chains), [n.edge_id for n in edge_nodes], [f.fog_id for f in fog_nodes])
    acct = iter(chain.accounts[1:])
    owner, gateway = chain.accounts[0], next(acct)
    edge_accts = [next(acct) for _ in edge_nodes]
    fog_accts = [next(acct) for _ in fog_nodes]
    cloud_acct = next(acct)
    chain.send_many("setup_authorize", "authorize", [[a, True] for a in [gateway, *edge_accts, *fog_accts, cloud_acct]],
                    owner)
    keys = device_keys(device_ids, seed)
    chain.send_many("setup_register_device", "registerDevice", [
        [id32(d), bytes.fromhex(keys[d].public_key_hash.removeprefix("sha256:")), f"edge-iiotset://{d}"]
        for d in device_ids
    ], owner)

    device_layer.ledger = DeviceChainClient(chains[roles["device_gateway"]], keys, gateway, mode, scheduler)
    for node, a in zip(edge_nodes, edge_accts, strict=True):
        node.ledger = EdgeChainClient(chains[roles[node.edge_id]], a, mode)
    for fog, a in zip(fog_nodes, fog_accts, strict=True):
        fog.ledger = FogChainClient(chains[roles[fog.fog_id]], a, fog.fog_id, wait=wait)
    cloud.ledger = CloudChainClient(chains[roles["cloud"]], cloud_acct, wait=wait)

    # Model provenance: the cloud registers every deployed model, then each layer's artifact is verified
    # against the on-chain hash before any event is processed (ADR §13.2 C).
    forecaster = [scheduler.policy.model] if scheduler is not None and scheduler.policy.model is not None else []
    for model in (device_layer.model, edge_nodes[0].model, fog_nodes[0].model, cloud.model, *forecaster):
        cloud.ledger.register_model(model.record)
        cloud.ledger.verify_model(model.record, model.path)
    return roles


def load_stream_rows(view: str, n_rows: int | None, seed: int) -> tuple[pd.DataFrame, dict]:
    """Stratified sample of the held-out test split; the models never saw these rows."""
    paths = load_config("datasets")["paths"]
    test = pd.read_parquet(resolve(paths["splits"]) / view / "test.parquet")
    manifest = json.loads((resolve(paths["manifests"]) / f"{view}_preparation.json").read_text())
    if n_rows and n_rows < len(test):
        test, _ = train_test_split(test, train_size=n_rows, stratify=test["Attack_type"], random_state=seed)
    return test, manifest


def load_replay_rows(n_rows: int | None) -> tuple[pd.DataFrame, dict]:
    """Dataset v2's realistic stream from the time-split test window of each capture session: labelled packets,
    neither de-duplicated nor sampled (real repeats, gaps and rates). Every capture contributes an equal share of
    `n_rows` as one contiguous slice from the start of its window, so slow sensors are not drowned out by floods
    (a global time cut would give ~0.2 s of mostly DDoS traffic). Only models trained on the time split
    (view real_time) may score it: they never saw this window."""
    paths = load_config("datasets")["paths"]
    manifest = json.loads((resolve(paths["manifests"]) / "real_time_preparation.json").read_text())
    cuts = read_parquet(resolve(paths["splits"]) / "real" / "session_cuts.parquet")
    columns = ["capture", "device_id", "session", "ts_us", "packet_no", *TARGETS,
               *manifest["cleaning"]["numeric_columns"], *manifest["cleaning"]["categorical_columns"]]

    def window(capture: str, horizon_us: dict | None = None) -> list:
        return [[("session", "=", int(c.session)), ("ts_us", ">=", int(c.test_start_us)),
                 *([("ts_us", "<=", horizon_us[int(c.session)])] if horizon_us else [])]
                for c in cuts[cuts.capture == capture].itertuples()]

    # Pass 1: replay offset (time since its session's window start) of every test-window packet.
    starts, offsets = {}, {}
    for capture in captures():
        w = read_events(capture, columns=["session", "ts_us"], filters=window(capture))
        starts[capture] = w.groupby("session").ts_us.min().to_dict()
        offsets[capture] = np.sort((w.ts_us - w.session.map(starts[capture])).to_numpy())
    budget = share_budget({c: len(o) for c, o in offsets.items()}, n_rows)

    # Pass 2: each capture's first `budget` packets in replay time (read up to the horizon, then trim ties).
    parts = []
    for capture, b in budget.items():
        if b == 0:
            continue
        horizon = int(offsets[capture][b - 1])
        rows = read_events(capture, columns=columns,
                           filters=window(capture, {s: t + horizon for s, t in starts[capture].items()}))
        order = np.lexsort((rows.packet_no.to_numpy(), (rows.ts_us - rows.session.map(starts[capture])).to_numpy()))
        rows = rows.iloc[order[:b]].reset_index(drop=True)
        rows.insert(0, "source_row_id", source_row_ids(capture, rows.packet_no))
        parts.append(rows)
    rows = pd.concat(parts, ignore_index=True)
    replay = {"window": "time-split test window, equal contiguous share per capture",
              "packets_in_window": {c: len(o) for c, o in offsets.items()}, "rows_by_capture": budget,
              "slice_seconds_by_capture": {c: float(offsets[c][b - 1]) / 1e6 for c, b in budget.items() if b}}
    return rows, manifest | {"replay": replay}


def run(*, experiment: str, blockchain: str | None = None, n_rows: int | None = None, devices: int | None = None,
        edges: int | None = None, fogs: int | None = None, batch_size: int = 256,
        events_per_second: float = 1000.0, seed: int | None = None, block_time: float | None = None,
        replay: str = "random", speed: float = 1.0, replicas: int = 1, chain_backend: str = "anvil",
        signing: str | None = None, audit_writes: str = "await", interceptor=None,
        faults: list[Fault] | None = None, fault_policy: str = "recover", commit_policy: dict | None = None,
        log=print) -> dict:
    """interceptor(batch) -> batch, if given, runs between the device and edge layers: an in-flight
    attacker (security experiments). Rejected event ids are then returned in the result.

    replay="random" (mid-term): rows from the view's test split, N logical devices, Poisson arrivals.
    replay="realistic" (dataset v2): real devices and real timing at `speed`; `devices` and `events_per_second`
    are then properties of the data, not parameters. `replicas` splits each real device over that many devices
    (device scaling with the same messages and timing).

    chain_backend="anvil": one local node (automine, or a block every `block_time` s). chain_backend="qbft"
    (final task 2): a fresh network of Besu validators reaching QBFT consensus, one block every `block_time` s
    (default configs/blockchain.yaml). signing: "node" (Anvil's unlocked accounts, the default there) or "local"
    (the client signs; always for QBFT). audit_writes: "await" or "background" (see attach_blockchain).

    faults (fault-tolerance add-on): a schedule of `src.common.faults.Fault`, applied while the stream runs;
    fault_policy "recover" (failover and store-and-forward) or "none" (traffic for a failed component is lost); see
    _stream_with_faults. Node faults need chain_backend="qbft". faults=[] is the reference of a fault experiment:
    the same loop and records, nothing fails.

    commit_policy (final task 3, RQ-11): when the device gateway closes each device's Merkle batch, e.g.
    {"policy": "forecast", "hold_rounds": 1, "break_even": 16}; see src/device/commit_policy.py. None = one root per
    device per micro-batch (the design of every earlier experiment). Needs blockchain="batch"."""
    signing = signing or ("local" if chain_backend == "qbft" else "node")
    if signing not in ("node", "local") or (chain_backend == "qbft" and signing != "local"):
        raise ValueError(f"signing={signing!r} with chain_backend={chain_backend!r}: Besu signs nothing for clients")
    if faults is not None and (interceptor is not None or fault_policy not in FAULT_POLICIES):
        raise ValueError(f"faults run without an interceptor, with fault_policy in {FAULT_POLICIES}")
    if commit_policy is not None and (blockchain != "batch" or faults is not None):
        raise ValueError("commit_policy schedules Merkle batches: it needs blockchain='batch' and no faults")
    with ExitStack() as stack:
        chains = monitor = network = injector = None
        if blockchain:
            from src.common.blockchain import LocalSigner, NodeMonitor, connect, local_node

            if chain_backend == "anvil":
                url, proc = stack.enter_context(local_node(block_time=block_time))
                urls, pids = [url], [proc.pid]
            elif chain_backend == "qbft":
                from src.common.qbft import qbft_network

                network = stack.enter_context(qbft_network(block_period_s=block_time))
                urls, block_time = network.urls, network.block_period_s
                pids = lambda: network.pids              # noqa: E731 -- follows validators restarted by faults
            else:
                raise ValueError(f"unknown chain_backend {chain_backend!r}")
            chains = connect(urls, LocalSigner() if signing == "local" else None)
            monitor = NodeMonitor(pids)
        if faults is not None:
            from src.common.faults import FaultInjector

            injector = FaultInjector(faults, network)
        return _run(experiment=experiment, blockchain=blockchain, chains=chains, monitor=monitor, network=network,
                    chain_backend=chain_backend, signing=signing, audit_writes=audit_writes, n_rows=n_rows,
                    devices=devices, edges=edges, fogs=fogs, batch_size=batch_size,
                    events_per_second=events_per_second, seed=seed, block_time=block_time,
                    replay=replay, speed=speed, replicas=replicas, interceptor=interceptor, injector=injector,
                    fault_policy=fault_policy, commit_policy=commit_policy, log=log)


def _stream_with_faults(sim, batch_size: int, device_layer: DeviceLayer, edge_nodes: list[EdgeNode],
                        fog_nodes: list[FogNode], cloud: CloudNode, latency: LatencyTracker, monitor,
                        injector: FaultInjector, policy: str, wall_start: float) -> dict:
    """The stream loop of _run while components fail (fault-tolerance add-on, ADR Experiment F).

    Each hop checks whether its next component is up when it sends (a component fails between hops, never in the
    middle of processing a micro-batch):
      - a device that is down sends nothing (its readings in that window are never sent);
      - traffic for an edge or fog that is down goes, with policy "recover", to the next one that is up (each
        device's messages are verified against the shared ledger, so any edge can take them), else it is lost;
      - fog output for a cloud that is down is held at the fog, with policy "recover", and forwarded in order the
        next time a fog sends and the cloud is back (store and forward), else it is lost.
    Node faults are handled inside the blockchain client (failover to another node, resending what was sent to the
    dead one). Returns the counts and a timeline of deliveries to the cloud: [s since start, messages, latency ms]."""
    counts: dict[str, int] = defaultdict(int)
    held: list[tuple[dict, float]] = []
    timeline: list[list[float]] = []
    n_edges, n_fogs = len(edge_nodes), len(fog_nodes)

    def deliver(out: dict, generated_at: float) -> None:
        cloud.ingest(out, generated_at)
        now = time.perf_counter()
        timeline.append([round(now - wall_start, 3), len(out["events"]), round((now - generated_at) * 1000, 1)])

    for batch in sim.batches(batch_size):
        generated_at = time.perf_counter()
        down = injector.snapshot()                     # devices: when the readings are taken
        sent = [e for e in batch if f"device:{e['device_id']}" not in down]
        counts["unsent_device_off"] += len(batch) - len(sent)
        with latency.measure("device"):
            device_layer.process(sent)
        down = injector.snapshot()                     # device gateway -> edges
        edge_up = [node.edge_id not in down for node in edge_nodes]
        per_edge: list[list[dict]] = [[] for _ in edge_nodes]
        for e in sent:
            home = zlib.crc32(e["device_id"].encode()) % n_edges
            k = route(home, edge_up, policy)
            if k is None:
                counts["lost_at_edge"] += 1
                continue
            counts["rerouted_edge"] += k != home
            per_edge[k].append(e)
        with latency.measure("edge"):
            edge_out = [node.process(events) if up else []
                        for node, events, up in zip(edge_nodes, per_edge, edge_up, strict=True)]
        down = injector.snapshot()                     # edges -> fogs
        fog_up = [fog.fog_id not in down for fog in fog_nodes]
        per_fog: list[list[list[dict]]] = [[] for _ in fog_nodes]
        for j, out in enumerate(edge_out):
            k = route(j % n_fogs, fog_up, policy)
            if k is None:
                counts["lost_at_fog"] += len(out)
                continue
            counts["rerouted_fog"] += len(out) if k != j % n_fogs else 0
            per_fog[k].append(out)
        with latency.measure("fog"):
            fog_out = [fog.process(ins) for fog, ins, up in zip(fog_nodes, per_fog, fog_up, strict=True) if up]
        with latency.measure("cloud"):
            if "cloud" in injector.snapshot():         # fogs -> cloud
                n = sum(len(out["events"]) for out in fog_out)
                if policy == "recover":
                    held += [(out, generated_at) for out in fog_out]
                    counts["held_for_cloud"] += n
                else:
                    counts["lost_at_cloud"] += n
            else:
                for out, t in held:                    # the backlog first, in order
                    deliver(out, t)
                held.clear()
                for out in fog_out:
                    deliver(out, generated_at)
        latency.samples["batch_end_to_end"].append((time.perf_counter() - generated_at) * 1000)
        if monitor is not None:
            monitor.sample()
    record = injector.finish()                         # repairs anything still down (nodes: until resynced)
    for out, t in held:                                # cloud repaired only at the end of the stream
        deliver(out, t)
    return record | {"policy": policy, "counts": dict(counts), "timeline": timeline}


def _fault_summary(record: dict, sim, cloud: CloudNode, rejected: list, chains, network) -> dict:
    """Event accounting of a fault run (every message sent is delivered once, rejected, or counted as lost) plus the
    clients' failovers and, on a multi-node network, the time of every block; times in s since the stream start."""
    epoch0, counts = record.pop("epoch0"), record["counts"]
    ids = [r["event_id"] for r in cloud.rows]
    sent = len(sim) - counts.get("unsent_device_off", 0)
    record["messages"] = {"generated": len(sim), "sent": sent, "delivered": len(set(ids)),
                          "duplicates": len(ids) - len(set(ids)), "rejected": len(rejected),
                          "lost": sent - len(set(ids)) - len(rejected)}
    record["failovers"] = [{"node": i, "t_s": round(f["t"] - epoch0, 3), "from": f["from"], "to": f["to"]}
                           for i, c in enumerate(chains or []) for f in c.endpoints.failovers]
    record["block_times_s"] = [t - epoch0 for t in network.block_times()] if network is not None else None
    return record


def _commit_scheduler(spec: dict, sim, batch_size: int) -> CommitScheduler:
    from src.device.commit_policy import CommitScheduler, TrafficForecaster, future_rounds, make_policy

    name = spec["policy"]
    policy = make_policy(spec, forecaster=TrafficForecaster() if name == "forecast" else None,
                         future=future_rounds(sim.device_of, batch_size) if name == "oracle" else None)
    return CommitScheduler(policy, sim.device_ids)


def message_latency(rows: list[dict]) -> dict:
    """Per-message latency, arrival at the device layer -> cloud result (ms): all, attack and normal messages."""
    df = pd.DataFrame(rows, columns=["e2e_ms", "attack_label"])
    out = {}
    for name, d in (("all", df), ("attack", df[df.attack_label == 1]), ("normal", df[df.attack_label == 0])):
        a = d.e2e_ms.to_numpy()
        out[name] = {"count": int(a.size), **({"mean_ms": float(a.mean()), "p50_ms": float(np.percentile(a, 50)),
                                                "p95_ms": float(np.percentile(a, 95)), "max_ms": float(a.max())}
                                             if a.size else {})}
    return out


def _run(*, experiment, blockchain, chains, monitor, network, chain_backend, signing, audit_writes, n_rows, devices,
         edges, fogs, batch_size, events_per_second, seed, block_time, replay, speed, replicas, interceptor,
         log, injector=None, fault_policy="recover", commit_policy=None) -> dict:
    base, exp = load_config("base"), load_config("experiments")
    topo = base["topology"]
    devices, edges, fogs = devices or topo["devices"], edges or topo["edges"], fogs or topo["fogs"]
    seed = base["seed"] if seed is None else seed
    view = active_view()
    n_rows = n_rows or exp["sample_rows"]
    if replay == "realistic":
        if view != "real_time":
            raise ValueError("the realistic replay streams the time-split test window: run it with models trained "
                             f"on view real_time (BLOCKIOT_VIEW=real_time), not {view!r}")
        rows, manifest = load_replay_rows(n_rows)
        sim = RealtimeReplay(rows, speed=speed, seed=seed, source_file=manifest["source"]["source_file"],
                             replicas=replicas)
        devices = len(sim.device_ids)
        # per-device threshold: a device split over `replicas` devices sends 1/replicas of its rate to each
        flood_eps = load_config("datasets")["realistic"]["replay"]["flood_events_per_second"] * speed / replicas
    elif replay == "random":
        if replicas != 1:
            raise ValueError("replicas applies to the realistic replay; use devices for the random replay")
        rows, manifest = load_stream_rows(view, n_rows, seed)
        sim = DeviceSimulator(rows, devices, seed, events_per_second, source_file=manifest["source"]["source_file"])
        flood_eps = 10 * events_per_second / devices
    else:
        raise ValueError(f"unknown replay mode {replay!r}")
    device_layer = DeviceLayer()
    edge_nodes = [EdgeNode(f"edge-{i:02d}") for i in range(edges)]
    fog_nodes = [FogNode(f"fog-{i:02d}", flood_events_per_second=flood_eps) for i in range(fogs)]
    cloud = CloudNode()
    roles = None
    scheduler = _commit_scheduler(commit_policy, sim, batch_size) if commit_policy is not None else None
    if chains is not None:
        roles = attach_blockchain(chains, blockchain, seed, sim.device_ids, device_layer, edge_nodes, fog_nodes, cloud,
                                  audit_writes, scheduler)
    log(f"{experiment}: streaming {len(sim):,} events from {devices} devices via {edges} edges, {fogs} fogs"
        f" (blockchain={blockchain or 'off'}{f', {chain_backend}' if blockchain else ''})")

    latency, resources = LatencyTracker(), ResourceSampler()
    resources.start()
    if monitor is not None:
        monitor.start()
    wall_start = time.perf_counter()
    fault_record = None
    if injector is not None:
        injector.start()
        fault_record = _stream_with_faults(sim, batch_size, device_layer, edge_nodes, fog_nodes, cloud, latency,
                                           monitor, injector, fault_policy, wall_start)
    else:
        n_rounds = -(-len(sim) // batch_size)
        for k, batch in enumerate(sim.batches(batch_size)):
            generated_at = time.perf_counter()
            for e in batch:
                e["arrived_at"] = generated_at
            with latency.measure("device"):
                # the events that leave the device layer now: all of them unless a commit scheduler holds some
                batch = device_layer.process(batch, final=k == n_rounds - 1)
            if interceptor is not None:
                batch = interceptor(batch)
            per_edge: list[list[dict]] = [[] for _ in edge_nodes]
            for e in batch:
                per_edge[zlib.crc32(e["device_id"].encode()) % edges].append(e)
            edge_out = []
            with latency.measure("edge"):
                for node, events in zip(edge_nodes, per_edge, strict=True):
                    edge_out.append(node.process(events))
            with latency.measure("fog"):
                fog_out = [fog.process(edge_out[i::fogs]) for i, fog in enumerate(fog_nodes)]
            with latency.measure("cloud"):
                for out in fog_out:
                    cloud.ingest(out, generated_at)
            latency.samples["batch_end_to_end"].append((time.perf_counter() - generated_at) * 1000)
            if monitor is not None:
                monitor.sample()
    for c in chains or []:
        c.drain()                                      # background audit writes are part of the run's work
    wall = time.perf_counter() - wall_start
    usage = resources.stop()
    if monitor is not None:
        usage |= monitor.stop()

    processed = len(cloud.rows)
    rejected = [r for node in edge_nodes for r in node.rejected]
    if fault_record is not None:
        fault_record = _fault_summary(fault_record, sim, cloud, rejected, chains, network)
    result = {
        "run_id": f"{experiment}-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}",
        "experiment": experiment,
        "blockchain": blockchain or "off",
        "block_time_s": block_time,
        "chain_network": None if chains is None else {
            "backend": chain_backend, "nodes": len(chains), "signing": signing, "audit_writes": audit_writes,
            "roles": roles, **({"consensus": network.report()} if network is not None else {})},
        "topology": {"devices": devices, "edges": edges, "fogs": fogs, "batch_size": batch_size},
        "replay": {"mode": replay, "speed": speed if replay == "realistic" else None,
                   "replicas": replicas if replay == "realistic" else None,
                   "flood_events_per_second": flood_eps, "replay_seconds": float(sim.offsets[-1]) if len(sim) else 0.0,
                   **manifest.get("replay", {})},
        "events_in": len(sim),
        "events_processed": processed,
        "events_rejected": len(rejected),
        "rejection_reasons": pd.Series([r for _, r in rejected], dtype=str).value_counts().to_dict(),
        "alerts": sum(len(f.alerts) for f in fog_nodes),
        "throughput_eps": processed / wall if wall else 0.0,
        "resources": usage,
        "latency_ms": latency.summary(),
        "latency_per_event_ms": {
            stage: s["total_ms"] / processed for stage, s in latency.summary().items() if processed
        },
        "cpu_per_event_ms": {
            stage: s["cpu_total_ms"] / processed for stage, s in latency.summary().items() if processed
        },
        "chain": chains[0].stats.summary() if chains is not None else {},
        "faults": fault_record,
        "commit_schedule": scheduler.summary() if scheduler is not None else None,
        "message_latency_ms": message_latency(cloud.rows) if processed else None,
        "rejected": rejected if interceptor is not None else None,
        "cloud_rows": cloud.rows if interceptor is not None or fault_record is not None or scheduler is not None
        else None,
        # nothing reaches the cloud only when a fault takes it down for the whole stream without recovery
        "accuracy": cloud.accuracy_report() if processed else [],
        "cloud_confusion": cloud.confusion_matrix("cloud") if processed else None,
        "breakdown": cloud.breakdown() if processed else None,
        "models": {
            "device": device_layer.model.model_id, "edge": edge_nodes[0].model.model_id,
            "fog": fog_nodes[0].model.model_id, "cloud": cloud.model.model_id,
        },
        "reproducibility": {
            "seed": seed, "view": view, "dataset_source_hash": manifest["source"]["source_hash"],
            "test_split_hash": manifest["file_hashes"]["splits/test"],
            "config_hash": config_hash("base", "datasets", "models", "experiments"),
            "git_commit": git_commit(), "python": platform.python_version(),
            "scikit_learn": sklearn.__version__, "platform": platform.platform(),
        },
    }
    return result
