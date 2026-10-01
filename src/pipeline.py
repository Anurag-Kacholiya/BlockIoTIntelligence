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
from contextlib import ExitStack
from datetime import UTC, datetime

import pandas as pd
import sklearn
from sklearn.model_selection import train_test_split

from src.cloud.blockchain_client import CloudChainClient
from src.cloud.service import CloudNode
from src.common.blockchain import Chain, NodeMonitor, id32, local_node
from src.common.config import config_hash, load_config, resolve
from src.common.metrics import LatencyTracker, ResourceSampler
from src.common.storage import git_commit
from src.device.blockchain_client import DeviceChainClient
from src.device.collector import device_keys
from src.device.service import DeviceLayer
from src.device.simulator import DeviceSimulator
from src.edge.blockchain_client import EdgeChainClient
from src.edge.service import EdgeNode
from src.fog.blockchain_client import FogChainClient
from src.fog.service import FogNode


def attach_blockchain(chain: Chain, mode: str, seed: int, device_ids: list[str], device_layer: DeviceLayer,
                      edge_nodes: list[EdgeNode], fog_nodes: list[FogNode], cloud: CloudNode) -> None:
    """Deploy IoTRegistry, give every node its own account, register devices and models (ADR §6.2, Phase 6)."""
    chain.deploy()
    acct = iter(chain.accounts[1:])
    owner, gateway = chain.accounts[0], next(acct)
    edge_accts = [next(acct) for _ in edge_nodes]
    fog_accts = [next(acct) for _ in fog_nodes]
    cloud_acct = next(acct)
    chain.send_many("setup_authorize", "authorize", [[a, True] for a in [gateway, *edge_accts, *fog_accts, cloud_acct]],
                    owner)
    keys = device_keys(len(device_ids), seed)
    chain.send_many("setup_register_device", "registerDevice", [
        [id32(d), bytes.fromhex(keys[d].public_key_hash.removeprefix("sha256:")), f"edge-iiotset://{d}"]
        for d in device_ids
    ], owner)

    device_layer.ledger = DeviceChainClient(chain, keys, gateway, mode)
    for node, a in zip(edge_nodes, edge_accts, strict=True):
        node.ledger = EdgeChainClient(chain, a, mode)
    for fog, a in zip(fog_nodes, fog_accts, strict=True):
        fog.ledger = FogChainClient(chain, a, fog.fog_id)
    cloud.ledger = CloudChainClient(chain, cloud_acct)

    # Model provenance: the cloud registers every deployed model, then each layer's artifact is verified
    # against the on-chain hash before any event is processed (ADR §13.2 C).
    for model in (device_layer.model, edge_nodes[0].model, fog_nodes[0].model, cloud.model):
        cloud.ledger.register_model(model.record)
        cloud.ledger.verify_model(model.record, model.path)


def load_stream_rows(view: str, n_rows: int | None, seed: int) -> tuple[pd.DataFrame, dict]:
    """Stratified sample of the held-out test split; the models never saw these rows."""
    paths = load_config("datasets")["paths"]
    test = pd.read_parquet(resolve(paths["splits"]) / view / "test.parquet")
    manifest = json.loads((resolve(paths["manifests"]) / f"{view}_preparation.json").read_text())
    if n_rows and n_rows < len(test):
        test, _ = train_test_split(test, train_size=n_rows, stratify=test["Attack_type"], random_state=seed)
    return test, manifest


def run(*, experiment: str, blockchain: str | None = None, n_rows: int | None = None, devices: int | None = None,
        edges: int | None = None, fogs: int | None = None, batch_size: int = 256,
        events_per_second: float = 1000.0, seed: int | None = None, block_time: float | None = None,
        interceptor=None, log=print) -> dict:
    """interceptor(batch) -> batch, if given, runs between the device and edge layers: an in-flight
    attacker (security experiments). Rejected event ids are then returned in the result."""
    with ExitStack() as stack:
        chain = monitor = None
        if blockchain:
            url, proc = stack.enter_context(local_node(block_time=block_time))
            chain, monitor = Chain(url), NodeMonitor(proc.pid)
        return _run(experiment=experiment, blockchain=blockchain, chain=chain, monitor=monitor, n_rows=n_rows,
                    devices=devices, edges=edges, fogs=fogs, batch_size=batch_size,
                    events_per_second=events_per_second, seed=seed, block_time=block_time,
                    interceptor=interceptor, log=log)


def _run(*, experiment, blockchain, chain, monitor, n_rows, devices, edges, fogs, batch_size, events_per_second,
         seed, block_time, interceptor, log) -> dict:
    base, exp = load_config("base"), load_config("experiments")
    topo = base["topology"]
    devices, edges, fogs = devices or topo["devices"], edges or topo["edges"], fogs or topo["fogs"]
    seed = base["seed"] if seed is None else seed
    view = load_config("models")["training"]["view"]
    rows, manifest = load_stream_rows(view, n_rows or exp["sample_rows"], seed)

    sim = DeviceSimulator(rows, devices, seed, events_per_second, source_file=manifest["source"]["source_file"])
    per_device_eps = events_per_second / devices
    device_layer = DeviceLayer()
    edge_nodes = [EdgeNode(f"edge-{i:02d}") for i in range(edges)]
    fog_nodes = [FogNode(f"fog-{i:02d}", flood_events_per_second=10 * per_device_eps) for i in range(fogs)]
    cloud = CloudNode()
    if chain is not None:
        attach_blockchain(chain, blockchain, seed, [sim.device_id(i) for i in range(devices)],
                          device_layer, edge_nodes, fog_nodes, cloud)
    log(f"{experiment}: streaming {len(sim):,} events from {devices} devices via {edges} edges, {fogs} fogs"
        f" (blockchain={blockchain or 'off'})")

    latency, resources = LatencyTracker(), ResourceSampler()
    resources.start()
    if monitor is not None:
        monitor.start()
    wall_start = time.perf_counter()
    for batch in sim.batches(batch_size):
        generated_at = time.perf_counter()
        with latency.measure("device"):
            device_layer.process(batch)
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
    wall = time.perf_counter() - wall_start
    usage = resources.stop()
    if monitor is not None:
        usage |= monitor.stop()

    processed = len(cloud.rows)
    rejected = [r for node in edge_nodes for r in node.rejected]
    result = {
        "run_id": f"{experiment}-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}",
        "experiment": experiment,
        "blockchain": blockchain or "off",
        "block_time_s": block_time,
        "topology": {"devices": devices, "edges": edges, "fogs": fogs, "batch_size": batch_size},
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
        "chain": chain.stats.summary() if chain is not None else {},
        "rejected": rejected if interceptor is not None else None,
        "cloud_rows": cloud.rows if interceptor is not None else None,
        "accuracy": cloud.accuracy_report(),
        "cloud_confusion": cloud.confusion_matrix("cloud"),
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
