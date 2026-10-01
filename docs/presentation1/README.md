# BlockIoTIntelligence — First Presentation: Progress and Results

RIS Project 15, *Design of AI/ML-enabled Big Data Analytics for IoT Environment*.
Reference paper: Singh, Rathore & Park, *BlockIoTIntelligence*, FGCS 110 (2020) 721–743.
Every number below is produced by `scripts/run_presentation1.sh` followed by `scripts/make_figures.py`.
Raw outputs are in `experiments/results/` and the tables in `tables/`.

---

## 1. What is built

The paper proposes four intelligence layers (Device → Edge → Fog → Cloud), each running AI, joined by a
blockchain for identity, integrity and provenance. The paper does not implement this system; its
quantitative section compares numbers from other studies. We built an executable version and measured it.

| Layer | AI running there | Blockchain role (implemented) |
|---|---|---|
| **Device** | Decision tree, attack vs normal, 13 header features | Ed25519 identity registered on-chain; every event hashed, signed and committed (per event or as a Merkle batch) |
| **Edge** | Random Forest, attack vs normal, 42 features | Checks registered identity, signature, on-chain hash and cross-node replay; records processing provenance |
| **Fog** | Random Forest, 15-class attack type, plus traffic-window flood alerts | Every alert hashed into an on-chain audit trail |
| **Cloud** | Trains all layer models; deploys the best of RF / gradient boosting / MLP | Model registry: every model's SHA-256 registered and re-verified on-chain before use; inference results recorded |

Smart contract: `blockchain/contracts/IoTRegistry.sol` (Solidity 0.8.24), on a private Ethereum-compatible chain
(Foundry Anvil). Only hashes and metadata go on-chain. Raw data stays off-chain in Parquet (ADR §5.4).

**Status against the ADR phases**

| Phase | Status |
|---|---|
| 0 Repository, configs, tests | Done: 34 automated tests, lint clean |
| 1 Baseline four-layer pipeline (no blockchain) | Done |
| 2 Private blockchain + smart contract | Done |
| 3 Device intelligence + on-chain commitments | Done |
| 4 Edge verification + provenance | Done |
| 5 Fog attack detection + alert audit | Done (single fog node in these runs) |
| 6 Cloud training + on-chain model registry | Done |
| 7 Full integration | Partly done: the layers run in one process; MQTT/REST transport and Docker are next |
| 8 Quantitative evaluation | Partly done: accuracy, latency, resources, gas, security and scaling are done; fault tolerance and dashboard are for the final |

## 2. Dataset

**Edge-IIoTset** (IEEE DataPort, DOI 10.21227/MBC1-1H68). IEEE DataPort requires a subscription login to
download, so the files were fetched from the dataset authors' own Kaggle release (v5, identical files).
All 52 files are downloaded and SHA-256-verified (`data/metadata/checksums.sha256`, `dataset_card.yaml`).

| Part | Size | Rows | Use |
|---|---:|---:|---|
| `DNN-EdgeIIoT-dataset.csv` (publisher-selected) | 1.2 GB | 2,219,201 | **Used now.** Primary workload |
| `ML-EdgeIIoT-dataset.csv` (publisher-selected) | 82 MB | 157,800 | **Usable now.** Already cleaned and split; for quick checks |
| Raw normal traffic, 10 sensor CSVs | 4.0 GB | 11,209,913 | **Final.** Real per-sensor device identity |
| Raw attack traffic, 14 attack CSVs | 3.7 GB | 9,729,709 | **Final.** Large-scale and per-attack experiments |
| 24 PCAP captures (normal + attack) | 2.2 GB | packets | **Final.** Only source of true timestamps |

Preparation of the DNN view (`experiments/manifests/dnn_preparation.json`):

- Dropped the 15 identifier, timestamp and payload columns the publisher drops (they leak the label),
  plus 4 constant columns. Each removal and its reason is listed in `data/metadata/dnn_feature_removal.csv`.
- Removed 309,530 exact duplicates. 1,909,671 rows remain, split 70/15/15 stratified by class:
  1,336,769 train, 286,451 validation, 286,451 test.
- Models train on a 300,000-row stratified sample of train; every result uses held-out test rows only.

**Data problems found in checking** (these shape the final-phase plan):

1. The dataset CSVs have no usable timestamps. `frame.time` has lost its date (only "2021 11:44:10" remains) and
   each attack occupies its own time slot, so time windows built on it would leak the label. Fog windows use
   simulator replay time for now; the PCAPs have real timestamps for the final.
2. The selected views carry no device identity, and the source-IP column leaks the label
   (192.168.0.170 is 100% attack). Logical devices are assigned at random for now; the per-sensor raw files
   give real device identity for the final.
3. 2.3% of rows share an identical feature vector with a row of a different class, which caps achievable accuracy.
4. The raw Modbus, DDoS_UDP and MITM CSVs have misaligned leading columns and need an audit before use.

**Candidate external-validation datasets for the final** (IEEE DataPort, instructor approval needed):
X-IIoTID (DOI 10.21227/mpb6-py55, 107 MB, login required); ToN_IoT (DOI 10.21227/fesz-dm97; the DataPort
entry has no files, they are hosted by UNSW).

## 3. Results

Setup: 10 logical devices, 2 edges, 1 fog, 1 cloud, micro-batches of 256 events, single Apple M4 laptop.
Three configurations run on identical data, seeds and models:
- **Baseline:** no blockchain.
- **Per-event:** one on-chain commitment per event.
- **Merkle batch:** one commitment per device per micro-batch, with per-event inclusion proofs.

### 3.1 Accuracy per layer (clean traffic) — `figures/01_accuracy_per_layer.png`

| Layer | Task | Accuracy | Macro-F1 |
|---|---|---:|---:|
| Device | attack vs normal | 0.892 | 0.851 |
| Edge | attack vs normal | 0.970 | 0.962 |
| Fog | 15 classes | 0.962 | 0.892 |
| Cloud | 15 classes | 0.963 | 0.896 |

10,000 held-out events × 3 seeds, sd ≤ 0.006. Results are **identical with and without blockchain**: the ledger
does not change the data the models see. On the full 200,000-event test stream the cloud model scores 0.964
accuracy and 0.903 macro-F1. Weakest classes: Uploading, Fingerprinting, SQL injection and HTTP DDoS
(recall 62–68%, `figures/08_cloud_recall_per_class.png`).

### 3.2 Accuracy under data-integrity attack — `figures/03_integrity_attack_detection.png`

An attacker between device and edge disguises attack events by giving them a normal event's features.

| Attack events camouflaged | 0% | 10% | 25% | 50% |
|---|---:|---:|---:|---:|
| Baseline: attacks detected | 89.4% | 80.8% | 66.8% | **45.7%** |
| Blockchain: attacks detected | 89.4% | 90.5% | 91.8% | **94.8%** |

With the ledger, 100% of tampered events are rejected (on-chain hash mismatch), with no increase in false
alarms (0.01%). This is the controlled, measurable version of the paper's claim that accuracy is higher
with blockchain (Fig. 7a).

### 3.3 Security evaluation — `figures/04_security_detection.png`

Each attack is injected in its own pass into 3,000 real events.

| Attack | Baseline | Blockchain | Caught by |
|---|---:|---:|---|
| Payload tampering | 0% | **100%** | on-chain hash mismatch |
| Replay to the same edge | 100% | 100% | local duplicate check |
| Replay to a different edge | 53% | **100%** | on-chain "already processed" state |
| Unregistered device | 0% | **100%** | device registry |
| Device impersonation | 0% | **100%** | public key ≠ registered key |
| Model swap | 100% | 100% | hash check |
| Model swap + forged local record | 0% | **100%** | on-chain model registry |
| Unauthorized ledger write | n/a | **100%** | contract access control |

Legitimate events wrongly rejected: 0% with blockchain in every pass. In the baseline, accepted forged
impersonation events advanced the victim device's sequence counter and **locked out 92.5% of its genuine
traffic**. Building this experiment also exposed the same flaw in our own edge code (sequence state updated
before verification); it is fixed and covered by a regression test.

### 3.4 Latency, throughput and resources — `figures/02_latency_per_layer.png`, `07_gas_per_event.png`

| | Baseline | Merkle batch | Per-event |
|---|---:|---:|---:|
| End-to-end processing per event | 0.083 ms | 0.665 ms (8×) | 27.4 ms (330×) |
| Throughput | 11,357 events/s | 1,492 events/s | 37 events/s |
| Transactions per event | 0 | 0.09 | 2.0 |
| Gas per event | 0 | 12,700 | 155,900 |
| CPU per event (pipeline + chain node) | 0.09 ms | 0.70 ms | 31.3 ms |

Most per-event cost sits at the device (commit, 11.8 ms) and the edge (verify + record, 15.3 ms). Merkle batching
cuts device and edge gas by about 25×. The fog alert audit (6,650 gas/event) is then the largest remaining cost.
CPU time is our energy proxy: blockchain costs 8× (batch) to 355× (per-event) the baseline CPU per event.
At full scale, the Merkle batch run processed 200,000 events at 443 events/s with 0 failed transactions.

### 3.5 Scalability — `figures/05_scaling_throughput.png`, `06_scaling_latency.png`

5,000 events per point, 10–500 devices. The baseline and per-event throughput are flat. Batch throughput falls
from 1,513 to 77 events/s because batches are formed per device: with 500 devices a 256-event window holds
fewer than one event per device on average, so batching degrades to per-event cost. For the final: batch per edge gateway instead.

## 4. Comparison with the reference paper

The paper's values come from different cited systems, tasks and hardware (object detection on Raspberry Pis,
SDN attack detection). They are reference points, not targets.

| Layer | Paper accuracy with BC (without) | Ours, with = without | Paper latency with BC (without) | Ours with BC: per-event / batch (without) |
|---|---:|---:|---:|---:|
| Device | 72% (59%) | 89.2% | ≤57.4 ms (≤38.0) | 11.8 / 0.16 ms (0.003) |
| Edge | 75% (62%) | 97.0% | ≤58.0 ms (≤44.0) | 15.3 / 0.36 ms (0.023) |
| Fog | 90% (80%) | 96.2% | ≤22 ms (≤11) | 0.13 / 0.08 ms (0.023) |
| Cloud | 68% | 96.3% | — | 0.14 / 0.07 ms (0.034) |

- **Agrees with the paper:** blockchain adds latency and CPU at every layer. The device and edge layers pay most,
  because that is where commitments and verification happen.
- **Refines the paper:** on clean data, blockchain does not change accuracy. Its accuracy benefit appears
  when data is tampered with (§3.2).
- **Security/privacy:** the paper's similarity index is a literature measure. We report measured detection
  rates for eight attacks instead (§3.3).

## 5. Limitations (stated honestly)

- Single machine, in-process layers, local chain with instant mining: latencies exclude network and consensus
  delay. Anvil also slows as blocks accumulate, so per-event runs are kept to 10,000 events.
- Device identity and event timing are simulated, because the selected dataset views contain neither (§2).
- Energy is a CPU-time proxy, not a measured power figure.
- Edge rolling-window feature extraction (ADR §7.2), fault-tolerance experiments and the dashboard are not built yet.

## 6. Plan to the final presentation (6 weeks)

| Week | Work |
|---|---|
| 1 | Extract features from the PCAPs with real timestamps. Replay each sensor as its own device. Add a held-out-device generalization split |
| 2 | Edge temporal feature extraction. Fog windowed features from real time. Retrain and compare |
| 3 | MQTT device→edge and REST edge→fog→cloud transport; Docker Compose; multi-node chain with block time > 0 (realistic consensus latency) |
| 4 | Per-gateway Merkle batching and batched alert audit (fixes §3.5 scaling). Fault-tolerance experiment (ADR Exp. F) |
| 5 | External validation on a second DataPort dataset (if approved). Streamlit dashboard |
| 6 | Full reproduction run, final report and slides |

## Reproduce

```bash
make setup && make data-essential
python scripts/prepare_dataset.py && python scripts/train_models.py
scripts/run_presentation1.sh          # about 50 min; add --skip-full to skip the two 200k-event runs
.venv/bin/python scripts/make_figures.py
```
