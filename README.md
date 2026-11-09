# BlockIoTIntelligence

Executable realization of the BlockIoTIntelligence architecture (Singh, Rathore & Park, *Future Generation
Computer Systems* 110, 2020) for RIS Project 15, *Design of AI/ML-enabled Big Data Analytics for IoT
Environment*. Four cooperating intelligence layers (Device → Edge → Fog → Cloud) run AI on a real IoT/IIoT
workload, with a private EVM blockchain for identity, integrity and provenance. The blockchain is added
in Phase 2. The design and phase plan are in
[BlockIoTIntelligence_ADR_Implementation.md](BlockIoTIntelligence_ADR_Implementation.md).

## Dataset

**Edge-IIoTset**, IEEE DataPort, DOI [10.21227/MBC1-1H68](https://doi.org/10.21227/MBC1-1H68).
IEEE DataPort needs a subscription login to download, so the files are fetched from the dataset
authors' own Kaggle release (version 5, identical content). The DataPort page itself points to this
release. Cite: M. A. Ferrag et al., IEEE Access 10 (2022) 40281–40306, doi:10.1109/ACCESS.2022.3165809.

| File | Rows | Use |
|---|---:|---|
| `DNN-EdgeIIoT-dataset.csv` | 2,219,201 | primary workload (73% normal) |
| `ML-EdgeIIoT-dataset.csv` | 157,800 | fast iteration (85% attack) |
| raw `Normal traffic/`, `Attack traffic/` CSV + PCAP | — | per-sensor captures, device identity |

## Quick start

```bash
make setup                                  # pinned dependencies (Python 3.11+)
make data-essential                         # selected ML/DNN CSVs + docs (make data = all 52 files, ~11 GB)
python scripts/prepare_dataset.py           # clean, leakage-drop, split 70/15/15, build layer views
python scripts/train_models.py              # cloud trains + registers device/edge/fog/cloud models
python scripts/run_baseline.py              # Phase 1: four-layer pipeline, blockchain off
make test
```

## Blockchain setup (Phases 2–6)

Toolchain lives inside the project (`tools/`, `.venv/`, both git-ignored). On Apple Silicon:

```bash
python3 -m venv --system-site-packages .venv && .venv/bin/pip install "web3>=7,<8" coincurve==21.0.0
mkdir -p tools/foundry tools/solc
curl -L https://github.com/foundry-rs/foundry/releases/download/stable/foundry_stable_darwin_arm64.tar.gz | tar -xz -C tools/foundry
curl -L -o tools/solc/solc-0.8.24 "https://binaries.soliditylang.org/macosx-amd64/solc-macosx-amd64-v0.8.24+commit.e11b9ed9"
chmod +x tools/solc/solc-0.8.24
tools/foundry/forge build --root blockchain --offline --use "$PWD/tools/solc/solc-0.8.24"

.venv/bin/python scripts/run_blockchain.py --mode batch --rows 20000     # or --mode per_event
.venv/bin/python scripts/run_security.py                                  # attack injection experiment
scripts/run_presentation1.sh && .venv/bin/python scripts/make_figures.py  # all presentation results
```

Each run starts its own private Anvil chain, deploys `IoTRegistry`, registers devices and models, and stops the
chain afterwards. Results and figures: [docs/presentation1/README.md](docs/presentation1/README.md).

Data used at the mid-term and planned for the final: [docs/DATA_USAGE.md](docs/DATA_USAGE.md).

## Dataset v2: real timestamps and real devices (final task 1)

Needs all 52 dataset files (`make data`) and Wireshark's `tshark` (`brew install wireshark`).

```bash
.venv/bin/python scripts/validate_tshark_extraction.py     # tshark features vs the publisher's CSVs
.venv/bin/python scripts/build_realistic_events.py         # 24 pcaps -> per-packet events (~15 min)
.venv/bin/python scripts/build_realistic_dataset.py        # dataset v2 + splits A (random) and B (time)
for v in real_time real_random; do BLOCKIOT_VIEW=$v .venv/bin/python scripts/train_models.py; done
.venv/bin/python scripts/run_realistic_eval.py offline     # test-split metrics, per device and per class
.venv/bin/python scripts/run_realistic_eval.py lodo        # split C: leave one device out (~10 folds)
.venv/bin/python scripts/run_realistic_eval.py replay --rows 200000 [--blockchain batch]
scripts/run_final_task1.sh --step8-only     # tampering, security, comparison + scaling on the replay; figures
```

`scripts/run_final_task1.sh` without the flag reproduces all of task 1. Figures and tables: `docs/final/task1/`.

`BLOCKIOT_VIEW` selects the data view, the stream and the model folder together (`models/<view>/`); without it,
everything uses the mid-term view and models. Design and results:
[docs/final/01_real_timestamps_device_identity.md](docs/final/01_real_timestamps_device_identity.md).

## Multi-node blockchain: 4 QBFT validators (final task 2)

Needs Java 21+. Each experiment starts a fresh private network of 4 Hyperledger Besu validators (QBFT consensus,
one block per second) as local processes; the layers write and read through different nodes.

```bash
.venv/bin/python scripts/setup_besu.py              # pinned Besu release, SHA-256 checked, into tools/besu
.venv/bin/python scripts/run_multinode.py check     # write through node 0, read back through node 3
scripts/run_final_task2.sh                          # all task 2 experiments + figures (~1 h 45 min)
```

Figures and tables: `docs/final/task2/`. Design and results:
[docs/final/02_multi_node_blockchain.md](docs/final/02_multi_node_blockchain.md).

Headline results at one block per second:
- message latency 2.75 s in Merkle batch mode, the same as one node with the same block time (consensus adds
  ~34 ms per confirmation);
- all 8 attacks still blocked, no genuine message rejected;
- accuracy and gas identical to the single node.

## Fault tolerance (add-on after final task 2, ADR Experiment F)

Each run switches one part of the system off 30 s into the stream and back on 30 s later: a device, an edge, a
fog, the cloud, one validator, or two validators. It measures event loss, recovery time and continuity, with and
without recovery:
- edge and fog failover;
- cloud store and forward;
- blockchain client failover that resends unconfirmed transactions.

```bash
scripts/run_final_faults.sh                         # all fault scenarios + figures (~40 min)
.venv/bin/python scripts/run_faults.py --scenarios node_down quorum_lost   # a subset
```

Figures and tables: `docs/final/faults/`. Design and results:
[docs/final/02a_fault_tolerance.md](docs/final/02a_fault_tolerance.md).

Headline results:
- with recovery, no message is lost in any scenario and every prediction is unchanged;
- without recovery, a 30 s outage of an edge, fog or the cloud loses 19–26% of the messages, attack traffic
  included;
- 1 of 4 validators down: the chain continues at 0.4 blocks/s;
- 2 of 4 down: it halts and resumes 64.8 s after the quorum returns, without forking.

## AI-driven blockchain (final task 3, RQ-11)

In Merkle batch mode every micro-batch ends with one root per device: a `commitBatch` plus the edge's
`recordProcessing`, ~149k gas whatever the number of messages under it. With 500 devices most roots cover one or two
messages.

Here the device gateway decides, per micro-batch and device, whether to commit the device's batch now or keep it open
for the device's next messages. A learned traffic forecaster drives the decision: will the device send again in
time?
- It is trained by the cloud on the time split's train windows.
- It is registered and verified on-chain like the layer models.
- A batch of *m* messages is held only if *m ≤ p × N*, with *N* an explicit price of latency.

```bash
BLOCKIOT_VIEW=real_time .venv/bin/python scripts/train_forecaster.py   # the cloud trains the forecaster (~25 s)
.venv/bin/python scripts/run_ai_blockchain.py simulate                  # every policy over the whole trade-off (~1 min)
scripts/run_final_task3.sh                                              # everything + figures (~1 h)
```

Figures and tables: `docs/final/task3/`. Design and results:
[docs/final/03_ai_driven_blockchain.md](docs/final/03_ai_driven_blockchain.md).

Headline results at 500 devices, on 4 QBFT validators (a batch waits at most one extra micro-batch):
- **Gas:** the AI cuts gas per message by 22.5% (96.3k → 74.6k) for +0.82 s of message latency (3 seeds). A fixed
  rule that holds every small batch saves 26.8%, but adds +1.18 s.
- **At equal gas,** offline, the AI needs less added delay than the rule in 59 of 60 comparisons (median 15% less).
  It gets half of the gain perfect foresight would give.
- **Attacks:** never holding batches the device model flags as attacks keeps attack traffic at the fixed design's
  latency, and still saves 15% of the gas.
- **Unchanged:** every prediction, the alerts and the security checks are identical to the fixed design.
- **Scaling, partly fixed:** gas per message from 10 to 500 devices grows 4.8× instead of 6.2×. One root per device
  per commit stays the floor.

## Layout

| Path | Contents |
|---|---|
| `configs/` | topology, dataset, model, blockchain and experiment settings |
| `src/common/` | schemas, canonical hashing + Ed25519 signatures, config, logging, metrics, Parquet storage |
| `src/data/` | Edge-IIoTset ingestion, validation, cleaning, splits, layer views |
| `src/device/`, `src/edge/`, `src/fog/`, `src/cloud/` | the four intelligence layers |
| `src/pipeline.py` | in-process Device → Edge → Fog → Cloud orchestration (baseline and blockchain runs) |
| `scripts/` | download, prepare, train, run experiments |
| `experiments/manifests/`, `experiments/results/` | data lineage and experiment outputs |
| `data/`, `models/**/*.joblib` | generated, not committed; reproducible from the scripts |

## Data decisions that differ from the first ADR draft

- `frame.time` cannot drive the fog time windows: it is a small float in the ML view and a
  date-truncated time of day in the DNN view, and each attack occupies its own time slice (label leakage).
  Windows use the replay time assigned by the device simulator. They feed alerting, not the classifier.
- The selected views have no device identity. `ip.src_host` is a leakage column (192.168.0.170 is 100%
  attack). Logical devices are assigned at random during replay.
- The publisher's 15-column drop list is applied, plus 4 constant columns. See
  `data/metadata/<view>_feature_removal.csv`.
