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
python3 -m venv --system-site-packages .venv && .venv/bin/pip install "web3>=7,<8"
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
