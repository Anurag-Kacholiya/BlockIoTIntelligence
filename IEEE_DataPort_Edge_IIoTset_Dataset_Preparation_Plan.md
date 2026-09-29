# IEEE DataPort Dataset Preparation Plan — Edge-IIoTset

## Recommended dataset decision

Use **Edge-IIoTset** as the primary dataset for Project 15. It is published through IEEE DataPort under DOI `10.21227/MBC1-1H68`, was generated using a purpose-built IoT/IIoT testbed, includes cloud/fog/edge/blockchain components, more than ten IoT device/sensor types, fourteen attacks, and 61 selected high-correlation features from 1,176 candidates. citeturn751680search0turn716330search4

The release contains separate `DNN-EdgeIIoT-dataset.csv` and `ML-EdgeIIoT-dataset.csv` views for deep-learning and traditional ML experiments. citeturn712340search2

## Data lineage

```text
IEEE DataPort Edge-IIoTset
        ↓
Immutable raw snapshot + checksum
        ↓
Validation / cleaning
        ↓
Leakage audit
        ↓
Canonical event schema
        ↓
Device / Edge / Fog / Cloud views
        ↓
Train / validation / test
        ↓
Baseline + blockchain experiments
```

## Repository layout

```text
data/
├── external/edge_iiotset/raw/
├── metadata/
│   ├── dataset_card.yaml
│   ├── schema.json
│   └── checksums.sha256
├── standardized/{events,network,labels}/
├── prepared/{device,edge,fog,cloud}/
├── splits/{train,validation,test}/
└── synthetic/security_injection/
```

## Preparation steps

### 1. Preserve the source

Record DOI, retrieval date, source filename/version, SHA-256, row count and column count. Never mutate the downloaded source.

### 2. Reproduce publisher preparation

Retain the publisher's documented binary label (`Attack_label`), multiclass label (`Attack_type`), merging, invalid-record removal, duplicate removal, unnecessary-flow-feature removal and categorical encoding lineage. citeturn712340search3

### 3. Perform a project-specific leakage audit

Investigate direct label leakage, attack identifiers, capture/session identifiers, future information and cross-split duplicates.

### 4. Build a canonical event

```json
{
  "event_id": "...",
  "device_id": "...",
  "source_type": "iot|iiot",
  "protocol": "...",
  "timestamp": "...",
  "features": {"...": "..."},
  "attack_label": 0,
  "attack_type": "Normal",
  "source_dataset": "Edge-IIoTset",
  "source_file": "...",
  "source_row_id": "...",
  "source_hash": "..."
}
```

### 5. Create four views from the same source

| View | Use |
|---|---|
| Device | minimal local inference |
| Edge | preprocessing, scaling, feature extraction, lightweight inference |
| Fog | temporal aggregation and attack detection |
| Cloud | global model training/evaluation |

### 6. Create fog temporal features

Recommended windows: 1 s, 5 s, 30 s, 60 s. Derive event-rate, inter-arrival, packet-size, byte-rate, destination-count, duplicate-count and verification-failure features.

### 7. Split safely

Use a primary 70/15/15 train/validation/test split, stratified by label and group-aware where possible. Add an optional held-out-device/source generalization split.

### 8. Handle imbalance correctly

Perform oversampling only after splitting and only on the training partition. Keep validation/test untouched.

### 9. Scale correctly

Fit scaling only on the training set.

### 10. Generate manifests

Every derived view must record source hash, view name, rows, features, target, seed, preprocessing version and Git commit.

## Required experiments

1. Baseline binary attack detection.
2. Baseline multiclass attack detection.
3. Blockchain-enabled binary detection.
4. Layered Device→Edge→Fog→Cloud execution.
5. Tampering detection.
6. Replay detection.
7. Scaling/throughput experiment.
8. Held-out-group generalization experiment.

## Synthetic-data rule

Do not create a synthetic replacement dataset. Use synthetic mutations only for controlled system/security experiments, e.g.:

```text
real Edge-IIoTset event → tamper/replay/spoof → security evaluation
```

## Final decision

Use **Edge-IIoTset only as the mandatory primary dataset**. Additional IEEE DataPort datasets should be treated as optional external validation and added only after the core experiment is stable and with instructor approval.
