# BlockIoTIntelligence — ADR + Phased Research Implementation Document

> **Project:** Research in Information Security — Project 15  
> **Assigned title:** Design of AI/ML-enabled Big Data Analytics for IoT Environment  
> **Reference paper:** S. K. Singh, S. Rathore, J. H. Park, *BlockIoTIntelligence: A Blockchain-enabled Intelligent IoT Architecture with Artificial Intelligence*, Future Generation Computer Systems 110 (2020), 721–743.  
> **Primary implementation objective:** Build a reproducible, research-grade implementation of the architecture and experimental ideas described in the reference paper, while explicitly distinguishing paper-derived requirements from engineering choices needed to make the architecture executable.

---

## 1. Executive Summary

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `README.md` | Planned | Project overview, setup, quick start, experiment commands |
| `docs/BlockIoTIntelligence_ADR_Implementation.md` | Current document | Architecture Decision Record combined with the complete implementation plan |
| `docs/architecture/context.md` | Planned | System context and four-intelligence architecture |
| `docs/experiments/protocol.md` | Planned | Reproducible experiment protocol and measurement rules |

The reference paper proposes **BlockIoTIntelligence**, a layered IoT architecture that converges **Blockchain + Artificial Intelligence** across four intelligence levels: **Device Intelligence, Edge Intelligence, Fog Intelligence, and Cloud Intelligence**. The architecture is intended to improve big-data analytics while addressing security/privacy, accuracy, latency, and centralization issues in IoT environments.

The paper's design overview places IoT devices/sensors at the device layer, AI-enabled blockchain-connected base stations at the edge layer, AI-enabled blockchain-connected fog nodes above them, and blockchain-connected AI-enabled data centers at the cloud layer. Data and processing therefore move upward through a hierarchy rather than depending entirely on a single centralized cloud. The paper presents this architecture in its Figure 3 and describes the roles of the four layers in Section 3.1.

The methodological flow further maps the architecture to six IoT platform layers:

1. Physical layer → Device Intelligence
2. Communication layer → Edge Intelligence
3. Link-control layer → Edge Intelligence
4. Service layer → Fog Intelligence
5. Management layer → Fog Intelligence
6. Application layer → Cloud Intelligence

The paper then evaluates the proposal in two broad ways:

- **Qualitative analysis:** AI-driven Blockchain and Blockchain-driven AI taxonomies.
- **Quantitative analysis:** comparison of device, edge, fog, and cloud intelligence using accuracy, latency, security/privacy, computational complexity, and energy-cost measures.

The implementation in this document therefore follows the paper's architecture, but turns its architectural concepts into an executable research system.

### Important implementation interpretation

The paper is principally an **architecture and comparative evaluation paper**, not a single monolithic software repository with one end-to-end reference implementation. Its quantitative results reuse/compare results from cited systems at the device, edge, fog, and cloud levels. Therefore, a student implementation cannot honestly claim that the paper provides a complete set of source files, datasets, hyperparameters, and infrastructure scripts.

This implementation addresses that gap by creating a **faithful executable realization of the architecture**, with:

- IoT data generation/simulation
- AI/ML processing at all four intelligence layers
- Blockchain participation at all four intelligence layers
- On-chain integrity, identity, metadata, and audit records
- Off-chain storage for high-volume sensor data
- Cross-layer data propagation
- Baseline-vs-blockchain experiments
- Accuracy, latency, resource, security/privacy, and energy-related measurements
- Reproducible experiment configuration
- A dashboard for observing architecture behavior

The result should be presented as an **implementation of the BlockIoTIntelligence architectural model inspired directly by the reference paper**, not as a claim that the exact unpublished internal implementation of the authors has been reconstructed.

---

# 2. Source-of-Truth and Requirements Extraction

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/requirements/paper_requirements.md` | Planned | Verbatim/normalized mapping from paper sections to software requirements |
| `configs/base.yaml` | Planned | Central implementation configuration |
| `docs/experiments/protocol.md` | Planned | Requirement-to-experiment mapping |

## 2.1 Paper-derived requirements

The following requirements are treated as authoritative because they are explicitly described in the attached paper.

| ID | Requirement | Paper basis | Implementation interpretation |
|---|---|---|---|
| RQ-01 | Four intelligence layers must exist | Section 3.1; Figure 3 | Implement Device, Edge, Fog, Cloud as separate logical services |
| RQ-02 | AI must be associated with the four-layer architecture | Sections 3.1 and 3.2 | Each intelligence layer must perform an ML/AI-related task |
| RQ-03 | Blockchain must be integrated with the architecture | Sections 3.1 and 3.2 | Each layer must have blockchain participation/verification capability |
| RQ-04 | Device intelligence collects IoT data | Section 3.1 | Sensors/simulators produce timestamped records |
| RQ-05 | Edge intelligence performs data processing/feature extraction and scaling | Section 3.1 | Edge preprocessing pipeline |
| RQ-06 | Fog intelligence performs faster AI analysis/decision-making and handles processed edge data | Section 3.1 | Fog inference/attack detection/aggregation service |
| RQ-07 | Cloud intelligence performs large-scale analytics | Section 3.1 | Central research training/evaluation layer |
| RQ-08 | Digital identity, hashing, authentication and verification are part of the architecture | Section 3.2 | Device identities and content hashes recorded on-chain |
| RQ-09 | Smart contracts are part of the blockchain + IoT convergence | Section 3.2 | Implement contracts for registration, data commitments, audit/model records |
| RQ-10 | Distributed/decentralized operation is a design objective | Sections 1–3 | Avoid a single application database as the source of truth for integrity |
| RQ-11 | Qualitative AI-driven Blockchain analysis is required | Section 4.1.1 | Include an implementation analysis of AI techniques improving blockchain operations |
| RQ-12 | Qualitative Blockchain-driven AI analysis is required | Section 4.1.2 | Include an implementation analysis of blockchain improving AI trust, data sharing, and auditability |
| RQ-13 | Quantitative analysis must consider accuracy and latency | Section 4.2 | Build benchmark scripts and record both |
| RQ-14 | Quantitative analysis must consider security/privacy | Section 4.2 | Implement integrity/tamper tests and a similarity/privacy proxy |
| RQ-15 | Quantitative analysis must consider computational complexity/resources | Section 4.2 | Record CPU, memory, inference time |
| RQ-16 | Energy/resource efficiency must be discussed | Sections 4.2 and 5 | Measure host/resource power when possible; otherwise clearly label proxy metrics |
| RQ-17 | Research limitations and challenges must be analyzed | Section 5 and Conclusion | Provide limitations, mitigations, and future work |

## 2.2 Architecture facts to preserve

The paper explicitly describes:

- **Device Intelligence:** IoT devices/sensors generate large amounts of data. AI supports collection/learning, while peer-to-peer blockchain supports distributed transfer and security/privacy.
- **Edge Intelligence:** AI-enabled blockchain-connected base stations process traffic and perform feature extraction/scaling/representation of unstructured data.
- **Fog Intelligence:** Multiple AI-enabled fog nodes with blockchain analyze data, provide rapid decision-making, and share intermediate information toward the cloud.
- **Cloud Intelligence:** AI-enabled data centers connected to blockchain perform secure, decentralized large-scale analytics.

The methodological flow additionally identifies analytics intelligence, digital identity, distributed cloud storage, decentralization/distribution, authentication/verification, and chain structure as important features.

---

# 3. Architecture Decision Record

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/BlockIoTIntelligence_ADR_Implementation.md` | Current | Main ADR |
| `src/device/service.py` | Planned | Device intelligence runtime |
| `src/edge/service.py` | Planned | Edge intelligence runtime |
| `src/fog/service.py` | Planned | Fog intelligence runtime |
| `src/cloud/service.py` | Planned | Cloud intelligence runtime |
| `blockchain/contracts/IoTRegistry.sol` | Planned | Blockchain registry and integrity contract |
| `configs/base.yaml` | Planned | Layer topology and experiment configuration |
| `docker-compose.yml` | Planned | Reproducible multi-service runtime |

## ADR-001: Executable Four-Layer Blockchain + AI IoT Architecture

### Status

**Accepted**

### Context

A direct reading of the reference paper shows that the research contribution is an architectural convergence of blockchain and AI for IoT rather than one single deployable software package.

The implementation must therefore satisfy two competing requirements:

1. Remain faithful to the reference architecture.
2. Be executable, observable, testable, and reproducible as a student research project.

A fully physical implementation with hundreds of real IoT devices, Raspberry Pis, real cellular/edge/fog infrastructure, and a public blockchain would be expensive and difficult to reproduce. At the same time, a trivial Python script calling an ML model would not represent the paper's architecture.

### Decision

We will implement BlockIoTIntelligence as a **containerized logical distributed system** consisting of:

```text
                        ┌──────────────────────────────┐
                        │       CLOUD INTELLIGENCE     │
                        │ AI Training / Big Analytics  │
                        │ Model Registry / Aggregation │
                        │ Blockchain Client / Audit    │
                        └──────────────┬───────────────┘
                                       │
                             fog-to-cloud data
                                       │
                 ┌─────────────────────┴────────────────────┐
                 │             FOG INTELLIGENCE             │
                 │ AI inference / attack detection /        │
                 │ aggregation / intermediate parameters    │
                 │ Blockchain verification + audit          │
                 └──────────────┬──────────────┬─────────────┘
                                │              │
                         edge-to-fog      edge-to-fog
                                │              │
                 ┌──────────────┴──────────────┴─────────────┐
                 │             EDGE INTELLIGENCE             │
                 │ Feature extraction / scaling / filtering │
                 │ Lightweight inference                     │
                 │ Blockchain commitments                    │
                 └──────────────┬──────────────┬─────────────┘
                                │              │
                         device data      device data
                                │              │
             ┌──────────────────┴──────────────┴─────────────────┐
             │               DEVICE INTELLIGENCE                 │
             │ Sensor simulators / collectors / local AI        │
             │ Device identity / signing / blockchain client    │
             └───────────────────────────────────────────────────┘
```

### Why this decision

This structure matches the paper's Figure 3 concept while replacing physical infrastructure with logical nodes that can be launched repeatedly.

### What will be decentralized

The implementation will decentralize:

- identity records,
- data integrity commitments,
- model metadata,
- audit events,
- selected access-control decisions,
- blockchain verification.

The implementation will **not** place raw high-volume sensor records directly on-chain.

This is an engineering decision because directly storing every sensor value on a blockchain would introduce unnecessary storage and performance costs and would not scale as a practical IoT data platform.

### Blockchain model decision

Use a **local Ethereum-compatible private blockchain** for the implementation.

Recommended development setup:

- local EVM chain
- Solidity contracts
- JSON-RPC endpoint
- one or more logical blockchain clients representing device/edge/fog/cloud nodes
- deterministic accounts for experiments
- transaction receipt and gas recording

The paper discusses Ethereum, Go-Ethereum, smart contracts, digital signatures, hashing, decentralized/distributed storage, and blockchain-based IoT processing. A private local EVM network is therefore a closer implementation fit than using a completely unrelated blockchain stack.

### AI model decision

Use a layered model strategy:

| Layer | Primary AI purpose | Recommended implementation |
|---|---|---|
| Device | Local lightweight intelligence | anomaly/threshold classifier or compact classifier |
| Edge | Feature extraction + lightweight inference | preprocessing + Random Forest / small neural network |
| Fog | Attack/traffic-flow detection | supervised classifier |
| Cloud | Large-scale training + analytics | Gradient Boosting / Random Forest / MLP + model comparison |

The exact model is deliberately configurable. This prevents the architecture from becoming dependent on one algorithm and supports ablation experiments.

### Data storage decision

Use:

- **on-chain:** hashes, IDs, timestamps, metadata, provenance, model/version records, audit events
- **off-chain:** raw sensor data, processed feature matrices, model artifacts, large experiment files

Recommended off-chain implementation:

- local Parquet files for reproducible experiments
- MinIO/object storage when running the full containerized stack

### Transport decision

Use an IoT-style publish/subscribe channel such as MQTT for simulated device-to-edge communication.

This produces a realistic streaming behavior without requiring physical sensors.

### Service communication

Use HTTP/REST or gRPC for explicit service APIs between edge, fog, and cloud, while MQTT handles device-oriented telemetry.

### Rejected alternatives

| Alternative | Decision | Reason |
|---|---|---|
| Public Ethereum | Rejected | Cost, external dependency, non-reproducibility |
| Put all sensor data on-chain | Rejected | Poor scalability and unnecessary storage overhead |
| One Python monolith | Rejected | Does not demonstrate layered intelligence |
| Only a blockchain demo | Rejected | Does not implement the AI/big-data objective |
| Only an ML pipeline | Rejected | Misses the central blockchain contribution |
| Purely simulated mathematical graphs | Rejected | Useful for analysis but insufficient as an implementation |
| Hyperledger Fabric as the primary stack | Not selected | Valid alternative but Ethereum/Solidity matches the paper's explicit terminology more directly |

---

# 4. File Structure and Module Responsibilities

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `README.md` | Planned | Root project documentation |
| `docker-compose.yml` | Planned | Full local deployment |
| `.env.example` | Planned | Runtime configuration template |
| `configs/base.yaml` | Planned | Main system configuration |
| `configs/blockchain.yaml` | Planned | Chain/network configuration |
| `configs/models.yaml` | Planned | ML model configuration |
| `configs/datasets.yaml` | Planned | Dataset and split configuration |
| `src/common/config.py` | Planned | Configuration loading and validation |
| `src/common/schemas.py` | Planned | Shared typed data models |
| `src/common/crypto.py` | Planned | Hashing/signature utilities |
| `src/common/blockchain.py` | Planned | Common EVM interaction helpers |
| `src/common/metrics.py` | Planned | Metric collection |
| `src/device/` | Planned | Device Intelligence implementation |
| `src/edge/` | Planned | Edge Intelligence implementation |
| `src/fog/` | Planned | Fog Intelligence implementation |
| `src/cloud/` | Planned | Cloud Intelligence implementation |
| `blockchain/contracts/IoTRegistry.sol` | Planned | Device/data/model/audit registry |
| `blockchain/scripts/deploy.py` | Planned | Contract deployment |
| `tests/unit/` | Planned | Unit tests |
| `tests/integration/` | Planned | Cross-layer tests |
| `tests/security/` | Planned | Integrity and access tests |
| `experiments/` | Planned | Reproducible experiment runners |
| `dashboard/` | Planned | Results visualization |

## 4.1 Final repository tree

```text
blockiotintelligence/
│
├── README.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
│
├── configs/
│   ├── base.yaml
│   ├── blockchain.yaml
│   ├── datasets.yaml
│   ├── models.yaml
│   └── experiments.yaml
│
├── blockchain/
│   ├── contracts/
│   │   └── IoTRegistry.sol
│   ├── scripts/
│   │   └── deploy.py
│   ├── artifacts/
│   └── tests/
│       └── test_registry.py
│
├── src/
│   ├── common/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── schemas.py
│   │   ├── crypto.py
│   │   ├── blockchain.py
│   │   ├── storage.py
│   │   ├── logging.py
│   │   └── metrics.py
│   │
│   ├── device/
│   │   ├── __init__.py
│   │   ├── simulator.py
│   │   ├── collector.py
│   │   ├── local_model.py
│   │   ├── blockchain_client.py
│   │   └── service.py
│   │
│   ├── edge/
│   │   ├── __init__.py
│   │   ├── ingest.py
│   │   ├── preprocessing.py
│   │   ├── feature_extraction.py
│   │   ├── local_model.py
│   │   ├── blockchain_client.py
│   │   └── service.py
│   │
│   ├── fog/
│   │   ├── __init__.py
│   │   ├── aggregation.py
│   │   ├── traffic_analysis.py
│   │   ├── attack_detection.py
│   │   ├── intermediate_state.py
│   │   ├── blockchain_client.py
│   │   └── service.py
│   │
│   └── cloud/
│       ├── __init__.py
│       ├── ingestion.py
│       ├── dataset_builder.py
│       ├── train.py
│       ├── evaluate.py
│       ├── model_registry.py
│       ├── analytics.py
│       ├── blockchain_client.py
│       └── service.py
│
├── scripts/
│   ├── generate_data.py
│   ├── seed_network.py
│   ├── run_pipeline.py
│   ├── run_baseline.py
│   ├── run_blockchain.py
│   ├── benchmark.py
│   ├── collect_metrics.py
│   └── reproduce_results.py
│
├── experiments/
│   ├── configs/
│   ├── results/
│   ├── logs/
│   └── reports/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── performance/
│
├── dashboard/
│   ├── app.py
│   ├── data_loader.py
│   └── pages/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── external/
│
├── models/
│   ├── device/
│   ├── edge/
│   ├── fog/
│   └── cloud/
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_device_analysis.ipynb
│   ├── 03_edge_analysis.ipynb
│   ├── 04_fog_analysis.ipynb
│   └── 05_cloud_analysis.ipynb
│
└── docs/
    ├── BlockIoTIntelligence_ADR_Implementation.md
    ├── architecture/
    ├── requirements/
    ├── experiments/
    └── reports/
```

## 4.2 File responsibility rules

### `src/common/`

This package contains infrastructure that must remain independent of the intelligence-layer business logic.

`schemas.py` should define canonical objects such as:

```text
DeviceReading
TelemetryEvent
DataCommitment
FeatureRecord
InferenceResult
AttackAlert
ModelMetadata
BlockchainReceipt
ExperimentMetric
```

Every record should contain at least:

```text
event_id
device_id
layer
timestamp
sequence_number
payload_hash
previous_event_hash (when applicable)
trace_id
```

### `src/device/`

This is the first intelligence layer.

Main responsibilities:

1. Generate/collect IoT telemetry.
2. Attach device identity.
3. Calculate a deterministic payload hash.
4. Optionally execute lightweight local inference.
5. Publish telemetry to the edge.
6. Create blockchain commitments/audit events.
7. Record local timing/resource metrics.

### `src/edge/`

Main responsibilities:

1. Receive device telemetry.
2. Validate schema and basic integrity.
3. Validate blockchain commitment.
4. Normalize data.
5. Handle missing values/outliers.
6. Extract features.
7. Perform lightweight inference.
8. Commit processed-data metadata.
9. Forward processed events to fog.

### `src/fog/`

Main responsibilities:

1. Aggregate multiple edge streams.
2. Detect traffic anomalies/attacks.
3. Combine intermediate feature/state information.
4. Validate edge provenance.
5. Generate near-real-time alerts.
6. Store relevant blockchain audit events.
7. Forward aggregate/intermediate parameters to cloud.

### `src/cloud/`

Main responsibilities:

1. Consolidate data from fog.
2. Build large training/evaluation datasets.
3. Train multiple candidate models.
4. Evaluate accuracy and error.
5. Register model metadata and hash.
6. Analyze cross-layer results.
7. Produce reproducibility reports.

---

# 5. Data Model and End-to-End Data Flow

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `src/common/schemas.py` | Planned | Canonical domain objects |
| `src/common/storage.py` | Planned | Off-chain data persistence |
| `src/device/collector.py` | Planned | Telemetry generation/collection |
| `src/edge/ingest.py` | Planned | Device-event ingestion |
| `src/fog/aggregation.py` | Planned | Cross-edge aggregation |
| `src/cloud/ingestion.py` | Planned | Fog-to-cloud consolidation |
| `blockchain/contracts/IoTRegistry.sol` | Planned | On-chain commitments and audit metadata |

## 5.1 Canonical telemetry object

Recommended logical schema:

```json
{
  "event_id": "evt-000001",
  "device_id": "device-0004",
  "layer": "device",
  "timestamp": "2026-09-15T10:15:33.102Z",
  "sequence_number": 1023,
  "sensor_type": "temperature",
  "values": {
    "temperature": 28.41,
    "humidity": 65.2,
    "pressure": 1008.2
  },
  "payload_hash": "sha256:...",
  "previous_event_hash": "sha256:...",
  "trace_id": "trace-...",
  "signature": "0x..."
}
```

## 5.2 Hashing strategy

The system must never hash a Python dictionary in its default arbitrary serialization.

Instead:

1. Normalize fields.
2. Serialize using canonical JSON.
3. Encode as UTF-8.
4. Calculate SHA-256.
5. Store the digest as the immutable content identifier.

Example:

```text
canonical_event =
{
  event_id,
  device_id,
  timestamp,
  sequence_number,
  values
}

payload_hash = SHA256(canonical_json(canonical_event))
```

For blockchain submission:

```text
keccak256(
    event_id,
    device_id,
    payload_hash,
    timestamp
)
```

The off-chain SHA-256 value provides reproducible dataset integrity; the blockchain commitment provides a tamper-evident distributed record.

## 5.3 Chain-of-custody flow

```text
Device
  │
  ├── raw telemetry
  ├── canonical serialization
  ├── SHA-256 payload hash
  ├── device signature
  │
  └──────► Blockchain commitment
               │
               ▼
             Edge
               │
        validate hash/signature
               │
        preprocess + feature extraction
               │
               ├── new processed hash
               └──────► blockchain commitment
                             │
                             ▼
                           Fog
                             │
                      aggregate/analyze
                             │
                             ├── alert hash
                             └──────► blockchain audit
                                            │
                                            ▼
                                          Cloud
                                            │
                                    train/evaluate
                                            │
                                   model fingerprint
                                            │
                                            └────► blockchain
```

## 5.4 What is stored on-chain vs off-chain

| Data | On-chain | Off-chain |
|---|---:|---:|
| Device ID | Yes | Optional |
| Raw sensor stream | No | Yes |
| Raw payload hash | Yes | Yes |
| Timestamp | Yes | Yes |
| Data provenance | Yes | Yes |
| Access/audit event | Yes | Yes |
| Model hash | Yes | Yes |
| Model weights | No | Yes |
| Feature matrix | No | Yes |
| Experiment logs | Hash/reference | Yes |
| Aggregated metric | Optional | Yes |
| Alert record | Compact summary/hash | Full record |

This hybrid storage decision is required for a practical large-data IoT system.

---

# 6. Blockchain Design

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `blockchain/contracts/IoTRegistry.sol` | Planned | Core smart contract |
| `blockchain/scripts/deploy.py` | Planned | Contract deployment |
| `src/common/blockchain.py` | Planned | Shared EVM adapter |
| `src/device/blockchain_client.py` | Planned | Device blockchain actions |
| `src/edge/blockchain_client.py` | Planned | Edge blockchain actions |
| `src/fog/blockchain_client.py` | Planned | Fog blockchain actions |
| `src/cloud/blockchain_client.py` | Planned | Cloud blockchain actions |
| `configs/blockchain.yaml` | Planned | Chain/network configuration |
| `tests/security/test_blockchain_integrity.py` | Planned | Integrity and audit tests |

## 6.1 Smart contract responsibilities

The contract should provide a small, deterministic API rather than attempting to store large datasets.

Suggested interface:

```solidity
registerDevice(
    bytes32 deviceId,
    bytes32 devicePublicKeyHash,
    string calldata metadataUri
)

commitData(
    bytes32 eventId,
    bytes32 deviceId,
    bytes32 payloadHash,
    uint8 layer,
    uint64 timestamp
)

recordProcessing(
    bytes32 eventId,
    bytes32 parentEventHash,
    bytes32 processedPayloadHash,
    uint8 layer
)

registerModel(
    bytes32 modelId,
    bytes32 modelHash,
    string calldata metadataUri
)

recordInference(
    bytes32 eventId,
    bytes32 modelId,
    bytes32 resultHash,
    uint64 timestamp
)
```

## 6.2 Device registration

At system bootstrap:

```text
Device keypair generated
        │
        ├── public key hash
        └── blockchain address
              │
              ▼
       registerDevice()
              │
              ▼
        registry event
```

The device registry entry should contain:

```text
device_id
address
public_key_hash
status
registration_timestamp
metadata_reference
```

## 6.3 Data commitment

The device does not upload the full payload to the chain.

Instead:

```text
payload
  ↓
canonicalize
  ↓
SHA-256
  ↓
payload_hash
  ↓
commitData(...)
```

The edge can later re-hash the received payload and compare it against the blockchain record.

## 6.4 Integrity verification test

Test procedure:

1. Device publishes event.
2. Blockchain stores event hash.
3. Edge receives event.
4. Edge recalculates hash.
5. Edge retrieves blockchain commitment.
6. Hashes match → accept.
7. Hashes differ → reject and emit security alert.

Tampering experiment:

```text
original value     = 28.41
tampered value     = 38.41
original hash      != tampered hash
blockchain hash    = original hash
result             = integrity violation
```

## 6.5 Layer-specific blockchain role

| Layer | Blockchain role |
|---|---|
| Device | Device identity, event commitment, source provenance |
| Edge | Verification, processed-data commitment |
| Fog | Attack/alert/audit record and distributed state |
| Cloud | Model provenance, model hash, experiment result provenance |

## 6.6 Consensus

The paper discusses multiple blockchain consensus approaches and provides architecture-level analysis rather than requiring one exact production consensus implementation.

For this student system:

- development mode: local single-validator/private network for deterministic tests
- multi-node experiment: multiple EVM nodes/validators when evaluating decentralized behavior
- public mainnet: never required

The project report must explicitly state that the local consensus setup is an engineering approximation for reproducibility.

---

# 7. AI/ML Design

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `configs/models.yaml` | Planned | Model hyperparameters and layer assignments |
| `src/device/local_model.py` | Planned | Lightweight device inference |
| `src/edge/feature_extraction.py` | Planned | Feature transformation pipeline |
| `src/edge/local_model.py` | Planned | Edge model |
| `src/fog/traffic_analysis.py` | Planned | Traffic-flow analysis |
| `src/fog/attack_detection.py` | Planned | Security/anomaly model |
| `src/cloud/train.py` | Planned | Full model training |
| `src/cloud/evaluate.py` | Planned | Evaluation and metrics |
| `src/cloud/model_registry.py` | Planned | Model hashing/metadata |

## 7.1 AI placement

The reference paper emphasizes that AI is applied throughout the architecture rather than being confined to the cloud.

Implementation mapping:

```text
Device:
  lightweight anomaly / state classifier

Edge:
  preprocessing
  feature extraction
  lightweight inference

Fog:
  traffic classification
  attack/anomaly detection
  rapid response

Cloud:
  large-scale training
  model selection
  global analytics
```

## 7.2 Feature pipeline

Edge preprocessing should include:

1. schema validation
2. timestamp normalization
3. missing-value handling
4. duplicate removal
5. outlier handling
6. numerical scaling
7. feature extraction
8. feature vector hash generation

Example feature groups:

```text
rolling_mean
rolling_std
min/max
rate_of_change
lag_1
lag_5
sensor correlation
device message rate
inter-arrival time
packet/event size
```

## 7.3 Device model

The device model must be lightweight enough to run on a constrained logical node.

Recommended initial model:

- logistic regression
- small decision tree
- compact random forest

Evaluation:

```text
Accuracy
Precision
Recall
F1
Inference time
CPU %
Memory %
```

## 7.4 Edge model

The edge layer should receive richer features and make a fast decision.

Recommended candidates:

```text
Random Forest
Gradient Boosting
Small MLP
```

Use the same train/test split policy for fair comparisons.

## 7.5 Fog attack detection

The paper's quantitative discussion specifically references attack detection at the fog layer.

The implementation should therefore include a security-focused task:

```text
input:
  traffic statistics + event metadata + timing features

output:
  normal / suspicious / attack
```

Candidate features:

```text
event_rate
unique_device_count
mean_interval
variance_interval
payload_size_mean
payload_size_std
failed_verification_count
duplicate_event_count
unexpected_sequence_count
```

## 7.6 Cloud analytics

Cloud intelligence should train/evaluate larger models and produce the final research comparison.

Recommended experiment:

```text
Model A: Random Forest
Model B: Gradient Boosting
Model C: MLP
```

Store:

```text
model_id
training_data_hash
feature_schema_hash
hyperparameters
framework/version
metrics
model_artifact_hash
training_timestamp
```

Then register the model metadata on-chain.

---

# 8. Communication and Service Interfaces

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `src/device/service.py` | Planned | Device API + MQTT publisher |
| `src/edge/service.py` | Planned | Edge ingestion and processing API |
| `src/fog/service.py` | Planned | Fog analytics API |
| `src/cloud/service.py` | Planned | Cloud analytics API |
| `src/common/schemas.py` | Planned | Shared request/response schemas |
| `docker-compose.yml` | Planned | Service topology |

## 8.1 Device → Edge

MQTT topic pattern:

```text
iot/{device_id}/telemetry
```

Payload:

```json
{
  "event_id": "...",
  "device_id": "...",
  "timestamp": "...",
  "values": {...},
  "payload_hash": "...",
  "signature": "..."
}
```

## 8.2 Edge → Fog

REST/gRPC payload:

```json
{
  "trace_id": "...",
  "edge_id": "edge-01",
  "features": {...},
  "source_event_ids": ["..."],
  "processed_hash": "...",
  "inference": {...}
}
```

## 8.3 Fog → Cloud

Payload:

```json
{
  "fog_id": "fog-01",
  "batch_id": "...",
  "aggregated_features": {...},
  "alerts": [...],
  "intermediate_state_hash": "...",
  "source_edges": ["edge-01", "edge-02"]
}
```

## 8.4 Cloud response

```json
{
  "model_id": "...",
  "model_hash": "...",
  "metrics": {
    "accuracy": 0.91,
    "precision": 0.89,
    "recall": 0.93,
    "f1": 0.91
  }
}
```

---

# 9. Storage Architecture

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `src/common/storage.py` | Planned | Storage adapter |
| `src/cloud/dataset_builder.py` | Planned | Build analytical datasets |
| `configs/datasets.yaml` | Planned | Dataset locations and schema |
| `data/raw/` | Planned | Original/raw source data |
| `data/processed/` | Planned | Canonical processed datasets |
| `models/` | Planned | Trained model artifacts |
| `experiments/results/` | Planned | Benchmark outputs |

## 9.1 Storage rule

The system will use a **hybrid storage architecture**:

```text
High-volume telemetry ──► Parquet / object store
                           │
                           └── hash ──► blockchain

Small critical metadata ─► blockchain
```

This allows big-data processing without making blockchain the raw data warehouse.

## 9.2 Reproducibility rule

Every dataset used for a reported experiment must have:

```text
dataset_name
source
download/access date
row count
schema hash
file hash
preprocessing version
train/validation/test split seed
```

---

# 10. Phased Implementation Plan

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `scripts/generate_data.py` | Planned | Synthetic/replay telemetry generation |
| `scripts/seed_network.py` | Planned | Device/edge/fog/cloud network initialization |
| `scripts/run_pipeline.py` | Planned | Full end-to-end execution |
| `scripts/run_baseline.py` | Planned | No-blockchain baseline |
| `scripts/run_blockchain.py` | Planned | Full architecture |
| `scripts/benchmark.py` | Planned | Performance evaluation |
| `scripts/reproduce_results.py` | Planned | One-command reproducibility |
| `experiments/configs/` | Planned | Phase experiment configurations |
| `tests/` | Planned | Phase-level quality gates |

## Phase 0 — Requirements, repository, and environment

### Goal

Create a reproducible project shell before implementing AI or blockchain logic.

### Files

```text
README.md
pyproject.toml
requirements.txt
.env.example
Makefile
docker-compose.yml
configs/base.yaml
configs/blockchain.yaml
configs/models.yaml
configs/datasets.yaml
```

### Tasks

1. Create Git repository.
2. Create Python environment.
3. Add formatter/linter.
4. Add unit-test framework.
5. Add configuration loader.
6. Add structured logging.
7. Create directories.
8. Pin tested dependency versions.
9. Create Dockerfiles where needed.
10. Add CI workflow later.

### Completion criteria

```text
python -m pytest
```

must run successfully even before domain functionality is implemented.

---

## Phase 1 — Baseline IoT analytics pipeline

### Goal

Implement the IoT data path without blockchain first.

This baseline is critical because the reference paper compares blockchain-enabled and non-blockchain behavior.

### Files

```text
src/device/simulator.py
src/device/collector.py
src/edge/ingest.py
src/edge/preprocessing.py
src/edge/feature_extraction.py
src/fog/aggregation.py
src/fog/traffic_analysis.py
src/cloud/ingestion.py
src/cloud/dataset_builder.py
src/cloud/train.py
src/cloud/evaluate.py
scripts/generate_data.py
scripts/run_baseline.py
tests/integration/test_baseline_pipeline.py
```

### Tasks

#### 1. Generate data

Simulate many logical devices.

Device classes:

```text
temperature sensor
humidity sensor
motion sensor
traffic sensor
environment sensor
```

The exact number is configuration-driven.

Example:

```yaml
devices:
  count: 100
  events_per_device: 1000
```

#### 2. Stream to edge

Each device produces timestamped events.

#### 3. Preprocess at edge

Implement:

```text
validation
deduplication
missing values
normalization
feature extraction
```

#### 4. Fog analytics

Aggregate multiple edges and classify suspicious traffic.

#### 5. Cloud analytics

Train the selected global models.

### Baseline metrics

Record:

```text
accuracy
precision
recall
f1
latency
throughput
CPU
memory
```

### Exit criteria

A complete no-blockchain data pipeline must exist and produce a machine-readable result file.

---

## Phase 2 — Private blockchain infrastructure

### Goal

Add the distributed ledger without changing the AI algorithm initially.

### Files

```text
blockchain/contracts/IoTRegistry.sol
blockchain/scripts/deploy.py
src/common/blockchain.py
src/device/blockchain_client.py
src/edge/blockchain_client.py
src/fog/blockchain_client.py
src/cloud/blockchain_client.py
configs/blockchain.yaml
tests/security/test_blockchain_integrity.py
```

### Tasks

1. Start local EVM network.
2. Generate deterministic experiment accounts.
3. Deploy contract.
4. Register devices.
5. Commit sample events.
6. Read commitments back.
7. Verify hashes.
8. Record transaction receipts.
9. Record gas used.
10. Build retry handling for blockchain RPC failures.

### Exit criteria

The device can submit a commitment and the edge can independently verify it.

---

## Phase 3 — Device Intelligence

### Goal

Turn the device simulator into the first true BlockIoTIntelligence layer.

### Files

```text
src/device/simulator.py
src/device/collector.py
src/device/local_model.py
src/device/blockchain_client.py
src/device/service.py
tests/unit/test_device.py
tests/integration/test_device_edge.py
```

### Device workflow

```text
generate sensor reading
       ↓
canonicalize
       ↓
hash
       ↓
sign
       ↓
local AI decision
       ↓
blockchain commit
       ↓
publish to edge
```

### Device blockchain event

```text
DEVICE_REGISTERED
DATA_COMMITTED
INFERENCE_RECORDED
```

### Device resource experiment

Run:

```text
10 devices
25 devices
50 devices
100 devices
250 devices
500 devices
```

Record:

```text
event processing time
CPU
memory
blockchain transaction time
```

---

## Phase 4 — Edge Intelligence

### Goal

Implement blockchain-enabled edge processing and feature extraction.

### Files

```text
src/edge/ingest.py
src/edge/preprocessing.py
src/edge/feature_extraction.py
src/edge/local_model.py
src/edge/blockchain_client.py
src/edge/service.py
tests/integration/test_edge_processing.py
```

### Edge workflow

```text
receive event
  ↓
verify identity/signature
  ↓
verify blockchain commitment
  ↓
preprocess
  ↓
feature extraction
  ↓
local inference
  ↓
commit processed hash
  ↓
forward to fog
```

### Required measurements

Compare:

```text
baseline edge
vs
blockchain edge
```

Measure:

```text
accuracy
latency
CPU
memory
transaction overhead
```

### Important research question

Does blockchain improve trust/integrity sufficiently to justify additional latency/resource overhead?

This question directly reflects the tension described by the paper's quantitative analysis: blockchain-enabled accuracy is reported as higher in the compared studies, while latency can also be higher.

---

## Phase 5 — Fog Intelligence

### Goal

Implement the security-oriented intermediate processing layer.

### Files

```text
src/fog/aggregation.py
src/fog/traffic_analysis.py
src/fog/attack_detection.py
src/fog/intermediate_state.py
src/fog/blockchain_client.py
src/fog/service.py
tests/integration/test_fog_detection.py
```

### Workflow

```text
edge streams
     ↓
aggregation
     ↓
feature construction
     ↓
traffic analysis
     ↓
attack classifier
     ↓
alert generation
     ↓
blockchain audit
     ↓
cloud forwarding
```

### Attack scenarios for testing

At minimum simulate:

```text
event flooding
duplicate events
spoofed device identity
payload tampering
replay of old event
sequence-number manipulation
```

These are implementation test scenarios and should not be described as exact attack datasets from the reference paper unless the source dataset is independently verified.

### Exit criteria

A forged/tampered telemetry event should be detected either:

- cryptographically,
- through provenance validation,
- or through ML anomaly detection.

---

## Phase 6 — Cloud Intelligence

### Goal

Implement the high-compute analytical layer.

### Files

```text
src/cloud/ingestion.py
src/cloud/dataset_builder.py
src/cloud/train.py
src/cloud/evaluate.py
src/cloud/model_registry.py
src/cloud/analytics.py
src/cloud/blockchain_client.py
src/cloud/service.py
```

### Workflow

```text
fog batches
   ↓
dataset assembly
   ↓
quality validation
   ↓
feature matrix
   ↓
model training
   ↓
evaluation
   ↓
model artifact
   ↓
model hash
   ↓
blockchain model registry
```

### Model provenance

A cloud model is valid only when:

```text
model_hash
+
training_dataset_hash
+
feature_schema_hash
+
hyperparameters
```

are recorded.

This makes the AI pipeline auditable rather than treating model weights as opaque artifacts.

---

## Phase 7 — Full four-layer integration

### Goal

Run the architecture as one system.

### Files

```text
src/device/service.py
src/edge/service.py
src/fog/service.py
src/cloud/service.py
src/common/metrics.py
docker-compose.yml
scripts/run_pipeline.py
```

### Full execution

```text
Device
 ↓
MQTT
 ↓
Edge
 ↓
REST/gRPC
 ↓
Fog
 ↓
REST/gRPC
 ↓
Cloud
```

Blockchain interactions occur at each layer.

### Required trace propagation

Every message must preserve:

```text
trace_id
event_id
device_id
source_layer
destination_layer
parent_event_hash
```

This enables end-to-end provenance analysis.

### End-to-end test

A single source event must be traceable from:

```text
device creation
→ blockchain commitment
→ edge processing
→ edge blockchain commitment
→ fog analysis
→ fog audit
→ cloud aggregation
→ model/inference result
```

---

## Phase 8 — Quantitative Evaluation

### Goal

Reproduce the spirit of the reference paper's quantitative evaluation in a controlled, transparent experiment suite.

### Files

```text
scripts/benchmark.py
scripts/collect_metrics.py
experiments/configs/*.yaml
experiments/results/*.csv
dashboard/app.py
```

### Metrics

#### Accuracy

Use:

```text
Accuracy
Precision
Recall
F1
```

#### Latency

Measure:

```text
L_device
L_edge
L_fog
L_cloud
L_blockchain_commit
L_end_to_end
```

Define:

```text
L_end_to_end =
t_cloud_result - t_device_generation
```

and separately:

```text
L_blockchain =
t_receipt - t_submission
```

#### Computational complexity / resource use

Record:

```text
CPU utilization
memory utilization
message throughput
inference time
transaction count
gas usage
```

#### Security/privacy proxy

The paper uses a **similarity index (SI)** in its discussion of security and privacy. The implementation must not pretend that SI is a universal cryptographic metric.

Instead report:

1. the paper's SI concept as a literature-comparison field,
2. a clearly defined implementation integrity metric,
3. tamper-detection rate,
4. unauthorized-access rejection rate,
5. replay detection rate.

Example:

```text
Integrity Detection Rate
= correctly detected tampered events / all tampered events
```

#### Energy

If hardware power data is available:

```text
Energy = ∫ Power(t) dt
```

Otherwise use:

```text
CPU-time
transaction count
estimated power proxy
```

and explicitly label these as proxies.

---

# 11. Experimental Design

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `configs/experiments.yaml` | Planned | Experiment defaults |
| `experiments/configs/baseline.yaml` | Planned | Baseline setup |
| `experiments/configs/blockchain.yaml` | Planned | Blockchain-enabled setup |
| `experiments/configs/scaling.yaml` | Planned | Device/node scaling |
| `experiments/configs/security.yaml` | Planned | Security tests |
| `scripts/benchmark.py` | Planned | Benchmark runner |
| `scripts/reproduce_results.py` | Planned | Reproduction entrypoint |

## 11.1 Baseline vs proposed system

The most important comparison is:

```text
Baseline:
IoT → Edge → Fog → Cloud
(no blockchain)

Proposed:
IoT + Blockchain + AI
→ Edge + Blockchain + AI
→ Fog + Blockchain + AI
→ Cloud + Blockchain + AI
```

Keep:

- datasets
- random seeds
- model family
- train/test splits
- hardware
- traffic volume

constant between runs.

Only vary the architecture feature being studied.

## 11.2 Experiment matrix

### Experiment A — Accuracy

Variables:

```text
number of devices
number of edge nodes
number of fog nodes
blockchain = off/on
```

Measure:

```text
accuracy
precision
recall
f1
```

### Experiment B — Latency

Variables:

```text
device count
edge count
fog count
blockchain = off/on
```

Measure:

```text
processing latency
network latency
blockchain latency
end-to-end latency
```

### Experiment C — Resource overhead

Measure:

```text
CPU
memory
transaction count
gas
inference time
```

### Experiment D — Security

Inject:

```text
tampering
replay
spoofing
duplicate event
invalid signature
```

Measure:

```text
detection rate
false accept rate
false reject rate
verification latency
```

### Experiment E — Scalability

Scale:

```text
10
25
50
100
250
500
1000 logical devices
```

Record:

```text
throughput
latency
CPU
memory
transaction throughput
```

### Experiment F — Fault tolerance

Disable:

```text
one device
one edge
one fog node
one cloud worker
one blockchain RPC endpoint
```

Measure:

```text
event loss
recovery time
pipeline continuity
```

---

# 12. Paper-aligned Quantitative Benchmarks to Reference

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/experiments/paper_comparison.md` | Planned | Comparison of implementation outputs with paper-reported values |
| `experiments/reports/paper_comparison.csv` | Planned | Structured comparison table |
| `scripts/benchmark.py` | Planned | Produces implementation values |

The paper reports a comparative table containing the following values from prior studies:

| Intelligence | Accuracy (%) | Latency (ms) | Security/Privacy SI | CPU / Memory notes | Energy |
|---|---:|---:|---|---|---|
| Device | 72 | 56.2–57.4 | 1.0–0.01 | IoT CPU 3.1–4.3%; edge server 33%; memory 11.0–14.7%; edge server 24% | — |
| Edge | 75 | 56.0–58.0 | 0.62–0.4 | IoT CPU 3.4–4.5%; edge server 36%; memory 11.5–14.4%; edge server 25% | — |
| Fog | 90 | 0.0–11.0 | 0.9–0.1 | CPU 90%; memory 91% | — |
| Cloud | 68 | — | — | — | 50% lower than Round-Robin; 20% lower than MiniBrown in the cited cloud study |

The paper also discusses Figure 7 as a comparative analysis of device, edge, and fog intelligence:

- With blockchain, reported accuracy ranges reach 72% (device), 75% (edge), and 90% (fog).
- Without blockchain, the comparison is reported as reaching 59%, 62%, and 80%, respectively.
- Blockchain-enabled latency can be higher, with reported ranges up to 57.4 ms (device), 58.0 ms (edge), and 22 ms (fog).

### Critical interpretation rule

These values are **not ground-truth targets that the student implementation must numerically reproduce**.

They are values synthesized from existing research referenced by the paper. The implementation must instead report:

```text
paper-reported comparative value
vs
our measured value
```

and explain differences.

---

# 13. AI-driven Blockchain and Blockchain-driven AI Implementation Analysis

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/architecture/ai_driven_blockchain.md` | Planned | AI improving blockchain-related operations |
| `docs/architecture/blockchain_driven_ai.md` | Planned | Blockchain improving AI trust and provenance |
| `src/` relevant layer implementations | Planned | Executable examples |
| `experiments/configs/ai_blockchain.yaml` | Planned | Qualitative-to-quantitative mapping |

## 13.1 AI-driven Blockchain

The paper classifies how AI can address blockchain limitations such as:

- energy consumption,
- scalability,
- security/privacy,
- efficiency,
- hardware constraints,
- talent/knowledge constraints,
- data gates.

Implementation examples:

### A. Energy-aware scheduling

Use ML to predict expected workload and choose:

```text
low-cost execution schedule
```

### B. Traffic prediction

Use ML to anticipate traffic bursts and pre-scale fog/edge workers.

### C. Anomaly-aware routing

Use anomaly scores to prioritize or delay suspicious flows.

### D. Data aggregation

ML-based aggregation reduces redundant telemetry before blockchain commitment.

## 13.2 Blockchain-driven AI

The paper classifies blockchain assistance for:

- explainable AI,
- AI effectiveness,
- data sharing,
- artificial trust,
- security/privacy.

Implementation examples:

### A. Explainable provenance

For every inference:

```text
input hash
model hash
model version
timestamp
device source
result hash
```

Store a compact proof record.

### B. Data sharing

Only devices/users with authorized blockchain identities can reference selected datasets.

### C. Model integrity

A model artifact is accepted only if:

```text
SHA-256(model_file) == registered_model_hash
```

### D. Auditability

Every model deployment/inference is traceable to a specific model version.

---

# 14. Security Architecture

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `src/common/crypto.py` | Planned | Hash/signature functions |
| `src/common/blockchain.py` | Planned | Verification adapter |
| `blockchain/contracts/IoTRegistry.sol` | Planned | Immutable registry/audit state |
| `tests/security/test_blockchain_integrity.py` | Planned | Tamper detection |
| `tests/security/test_replay.py` | Planned | Replay protection |
| `tests/security/test_identity.py` | Planned | Device identity validation |
| `tests/security/test_access_control.py` | Planned | Authorization tests |

## 14.1 Threat model

Threat actors:

```text
T1: malicious IoT device
T2: compromised edge node
T3: malicious insider
T4: network attacker
T5: replay attacker
T6: data tampering attacker
T7: unauthorized data consumer
```

### Assets

```text
sensor telemetry
device identities
feature records
AI model artifacts
inference results
audit records
access permissions
```

## 14.2 Threat → control mapping

| Threat | Control |
|---|---|
| Payload tampering | Hash + blockchain commitment |
| Spoofed device | Device identity/signature |
| Replay | Sequence number + timestamp window + nonce/event ID |
| Unauthorized data access | Smart-contract access policy |
| Model replacement | Model hash registry |
| Audit deletion | Blockchain event history |
| Malicious AI result | Input/model provenance |
| Blockchain RPC failure | Retry + local queue + eventual commit |
| Large payload attack | Max payload limits + rate limiting |
| Duplicate data flood | Deduplication + sequence checks |

## 14.3 Security tests

### Test 1 — Tamper

```text
generate event
commit hash
mutate payload
verify
expect rejection
```

### Test 2 — Replay

```text
capture valid event
send same event again
expect replay rejection
```

### Test 3 — Invalid signer

```text
sign with unauthorized key
submit
expect authorization failure
```

### Test 4 — Model tamper

```text
register model hash
modify model
recalculate hash
expect mismatch
```

---

# 15. Observability and Metrics Architecture

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `src/common/metrics.py` | Planned | Central metric collection |
| `src/common/logging.py` | Planned | Structured event logging |
| `scripts/collect_metrics.py` | Planned | Export metrics |
| `dashboard/app.py` | Planned | Research dashboard |
| `experiments/results/` | Planned | Persistent benchmark data |

## 15.1 Every event must expose

```text
trace_id
timestamp
layer
node_id
event_id
operation
duration_ms
cpu_percent
memory_percent
blockchain_tx_hash
gas_used
success/failure
```

## 15.2 Metric event example

```json
{
  "trace_id": "trace-001",
  "layer": "edge",
  "operation": "feature_extraction",
  "duration_ms": 4.21,
  "cpu_percent": 28.3,
  "memory_percent": 31.1,
  "blockchain_tx_hash": "0x...",
  "success": true
}
```

---

# 16. Dashboard

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `dashboard/app.py` | Planned | Main dashboard |
| `dashboard/data_loader.py` | Planned | Benchmark result loader |
| `dashboard/pages/architecture.py` | Planned | Four-layer architecture visualization |
| `dashboard/pages/performance.py` | Planned | Accuracy/latency/resource charts |
| `dashboard/pages/security.py` | Planned | Security test results |
| `dashboard/pages/blockchain.py` | Planned | Transaction/gas/audit metrics |

## Dashboard views

### Architecture

Show:

```text
Device → Edge → Fog → Cloud
```

with:

```text
node status
event count
blockchain status
AI status
```

### Performance

Charts:

```text
accuracy vs node count
latency vs node count
CPU vs node count
memory vs node count
```

### Blockchain

Charts:

```text
transactions/minute
confirmation latency
gas/event
failed transactions
```

### Security

Charts:

```text
tamper detection
replay detection
unauthorized access rejection
```

---

# 17. Testing Strategy

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `tests/unit/test_schemas.py` | Planned | Data validation |
| `tests/unit/test_crypto.py` | Planned | Hash/signature correctness |
| `tests/unit/test_models.py` | Planned | Model behavior |
| `tests/integration/test_baseline_pipeline.py` | Planned | Baseline flow |
| `tests/integration/test_device_edge.py` | Planned | Device → Edge |
| `tests/integration/test_edge_fog.py` | Planned | Edge → Fog |
| `tests/integration/test_fog_cloud.py` | Planned | Fog → Cloud |
| `tests/security/test_blockchain_integrity.py` | Planned | Integrity |
| `tests/security/test_replay.py` | Planned | Replay protection |
| `tests/security/test_identity.py` | Planned | Identity |
| `tests/performance/test_scaling.py` | Planned | Scaling behavior |

## 17.1 Unit tests

Test:

```text
schema validation
hash determinism
signature verification
feature extraction
metric calculations
model serialization
blockchain ABI helpers
```

## 17.2 Integration tests

Test:

```text
Device → Edge
Edge → Fog
Fog → Cloud
Blockchain → Layer
Cloud → Model Registry
```

## 17.3 End-to-end test

A complete test should assert:

```text
event generated
AND
event committed
AND
event verified
AND
edge processed
AND
fog analyzed
AND
cloud received
AND
model result produced
AND
result provenance recorded
```

---

# 18. Performance and Scalability Engineering

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `scripts/benchmark.py` | Planned | Main benchmark |
| `scripts/run_baseline.py` | Planned | Baseline benchmark |
| `scripts/run_blockchain.py` | Planned | Blockchain benchmark |
| `tests/performance/test_scaling.py` | Planned | Automated scaling test |
| `experiments/configs/scaling.yaml` | Planned | Scaling parameters |

## 18.1 Scaling dimensions

### Horizontal

Increase:

```text
device count
edge node count
fog node count
cloud worker count
```

### Vertical

Increase:

```text
event frequency
payload size
feature dimension
model size
```

## 18.2 Throughput

Define:

```text
throughput =
successfully processed events / second
```

Measure at:

```text
device
edge
fog
cloud
blockchain
```

## 18.3 Queue/back-pressure behavior

When downstream capacity is smaller than incoming telemetry:

```text
device queue
→ edge buffer
→ fog queue
→ cloud batch
```

The system must not silently drop records.

Count:

```text
received
processed
rejected
duplicated
dropped
```

---

# 19. Reproducibility Protocol

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `scripts/reproduce_results.py` | Planned | One-command reproduction |
| `configs/experiments.yaml` | Planned | Experiment definitions |
| `README.md` | Planned | Setup and reproduction steps |
| `experiments/results/` | Planned | Generated results |
| `experiments/reports/` | Planned | Final tables/plots |

## 19.1 Reproduction requirements

Every experiment must capture:

```text
git commit
OS
Python version
ML framework version
blockchain node version
hardware
seed
dataset hash
configuration hash
```

## 19.2 Reproduction command

The target user experience:

```bash
make setup
make blockchain
make seed
make experiment
make report
```

or:

```bash
python scripts/reproduce_results.py \
    --config configs/experiments.yaml
```

## 19.3 Result naming

Use:

```text
experiments/results/
  exp_accuracy_baseline.csv
  exp_accuracy_blockchain.csv
  exp_latency_baseline.csv
  exp_latency_blockchain.csv
  exp_security.csv
  exp_scalability.csv
```

---

# 20. Research Report Structure Generated from the Implementation

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/reports/methodology.md` | Planned | Methodology chapter |
| `docs/reports/results.md` | Planned | Experimental results |
| `docs/reports/security_analysis.md` | Planned | Security analysis |
| `docs/reports/limitations.md` | Planned | Limitations |
| `docs/reports/conclusion.md` | Planned | Final conclusions |

Recommended final research-report structure:

```text
1. Introduction
2. Background
   2.1 IoT
   2.2 Big Data Analytics
   2.3 AI/ML
   2.4 Blockchain
3. Reference Architecture
4. Proposed Implementation
   4.1 Device Intelligence
   4.2 Edge Intelligence
   4.3 Fog Intelligence
   4.4 Cloud Intelligence
5. Blockchain Design
6. AI/ML Design
7. Experimental Methodology
8. Results
9. Security Analysis
10. Scalability Analysis
11. Comparison with Reference Paper
12. Limitations
13. Future Work
14. Conclusion
```

---

# 21. Acceptance Criteria

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `tests/` | Planned | Automated acceptance tests |
| `scripts/reproduce_results.py` | Planned | Complete system reproduction |
| `docs/reports/results.md` | Planned | Acceptance evidence |

The project will be considered complete only when all of the following are satisfied.

## Architecture

- [ ] Four intelligence layers exist.
- [ ] Each layer performs a defined AI/ML-related task.
- [ ] Each layer participates in blockchain operations.
- [ ] Device → Edge → Fog → Cloud data flow works.
- [ ] The architecture can run from a fresh environment.

## Blockchain

- [ ] Devices can register.
- [ ] Telemetry commitments are recorded.
- [ ] Hash verification works.
- [ ] Tampering is detected.
- [ ] Replay protection works.
- [ ] Model hashes are registered.
- [ ] Audit records are queryable.

## AI

- [ ] Device inference works.
- [ ] Edge preprocessing/feature extraction works.
- [ ] Fog attack detection works.
- [ ] Cloud model training works.
- [ ] Model metadata is versioned.

## Evaluation

- [ ] Baseline experiment exists.
- [ ] Blockchain-enabled experiment exists.
- [ ] Accuracy is reported.
- [ ] Latency is reported.
- [ ] CPU/memory are reported.
- [ ] Security test results are reported.
- [ ] Scaling experiments are reported.
- [ ] Energy is measured directly or transparently represented by a proxy.

## Reproducibility

- [ ] Configuration is version controlled.
- [ ] Dataset hashes are recorded.
- [ ] Random seeds are recorded.
- [ ] One-command experiment execution works.
- [ ] Results are exported to CSV/JSON.
- [ ] A final comparison with paper-reported values exists.

---

# 22. Risks, Limitations, and Mitigations

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/reports/limitations.md` | Planned | Formal limitation statement |
| `docs/experiments/protocol.md` | Planned | Controls for experimental validity |

| Risk | Impact | Mitigation |
|---|---|---|
| Paper does not provide complete source code | High | Reconstruct architecture, not nonexistent source |
| Paper values come from prior studies | High | Do not claim exact numeric replication |
| Blockchain adds latency | High | Measure separately and present trade-off |
| Raw data cannot scale on-chain | High | Hybrid on-chain/off-chain model |
| AI results depend on dataset | High | Pin dataset, split, seed |
| Local blockchain differs from production network | Medium | Clearly document private-network approximation |
| Physical IoT hardware unavailable | Medium | Logical/containerized device simulation |
| Energy measurement unavailable | Medium | CPU-time/power-proxy with explicit limitation |
| Model drift | Medium | Model versioning + hash registry |
| Network failures | Medium | Queueing/retry and fault tests |

---

# 23. ADR Decision Summary

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/BlockIoTIntelligence_ADR_Implementation.md` | Current | Consolidated ADR decisions |

### Decision 1 — Four explicit intelligence services

**Accepted.**

The architecture will not be implemented as one monolith.

### Decision 2 — Local/private Ethereum-compatible blockchain

**Accepted.**

This most closely matches the paper's explicit Ethereum/Go-Ethereum/Solidity references while preserving reproducibility.

### Decision 3 — Hybrid storage

**Accepted.**

Only hashes/metadata/audit state are stored on-chain; large data and models remain off-chain.

### Decision 4 — MQTT + API-based inter-layer transport

**Accepted.**

This provides a realistic IoT communication abstraction while keeping edge/fog/cloud services independently testable.

### Decision 5 — Configurable ML models

**Accepted.**

The architecture is more important than one fixed model. Models remain replaceable through configuration.

### Decision 6 — Baseline before blockchain

**Accepted.**

The baseline is essential for quantifying blockchain overhead.

### Decision 7 — Research-grade traceability

**Accepted.**

Every important telemetry/model/inference artifact gets a hash and provenance record.

---

# 24. Phase Dependency Graph

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/BlockIoTIntelligence_ADR_Implementation.md` | Current | Master dependency plan |

```text
Phase 0
  │
  ▼
Phase 1 ───────────────► baseline measurements
  │
  ▼
Phase 2 ───────────────► blockchain infrastructure
  │
  ├──────────────┐
  ▼              ▼
Phase 3        Phase 4
Device         Edge
  │              │
  └───────┬──────┘
          ▼
       Phase 5
        Fog
          │
          ▼
       Phase 6
       Cloud
          │
          ▼
       Phase 7
       Integration
          │
          ▼
       Phase 8
     Evaluation
          │
          ▼
       Phase 9
   Security/Scalability
          │
          ▼
       Final Report
```

Recommended implementation order is therefore:

```text
0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9
```

Do **not** start with the cloud model or dashboard. The strongest research implementation begins with a measurable baseline and adds one architectural capability at a time.

---

# 25. Suggested Git Commit Plan

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| Repository-wide | Planned | Commit sequence for implementation traceability |

Recommended commits:

```text
01-init-project-structure
02-add-config-and-common-schemas
03-add-device-simulator
04-add-baseline-edge-processing
05-add-fog-analytics
06-add-cloud-training
07-add-private-blockchain
08-add-device-blockchain-integration
09-add-edge-blockchain-integration
10-add-fog-blockchain-integration
11-add-cloud-model-registry
12-add-end-to-end-pipeline
13-add-security-tests
14-add-performance-benchmarks
15-add-dashboard
16-add-reproducibility-script
17-add-final-research-report
```

Every major experiment should be traceable to a commit.

---

# 26. Implementation Checklist by File

### Files implemented/changed in this section

| File group | Status | Short description |
|---|---|---|
| `configs/` | Planned | Configuration |
| `src/common/` | Planned | Shared platform |
| `src/device/` | Planned | Device intelligence |
| `src/edge/` | Planned | Edge intelligence |
| `src/fog/` | Planned | Fog intelligence |
| `src/cloud/` | Planned | Cloud intelligence |
| `blockchain/` | Planned | Smart contracts and deployment |
| `scripts/` | Planned | Reproduction and experiments |
| `tests/` | Planned | Validation |
| `dashboard/` | Planned | Visualization |
| `docs/` | Current/Planned | Architecture and research documentation |

## Configuration files

| File | Primary responsibility |
|---|---|
| `configs/base.yaml` | Global topology, ports, logging, runtime |
| `configs/blockchain.yaml` | RPC endpoints, contract addresses, confirmations |
| `configs/datasets.yaml` | Dataset sources and preprocessing |
| `configs/models.yaml` | Model families and hyperparameters |
| `configs/experiments.yaml` | Repetition count, seeds, scale factors |

## Common files

| File | Primary responsibility |
|---|---|
| `src/common/config.py` | Typed configuration loading |
| `src/common/schemas.py` | Shared data structures |
| `src/common/crypto.py` | Hash/signature utilities |
| `src/common/blockchain.py` | EVM abstraction |
| `src/common/storage.py` | Off-chain storage abstraction |
| `src/common/logging.py` | Structured logs |
| `src/common/metrics.py` | Timing/resource/experiment metrics |

## Device files

| File | Primary responsibility |
|---|---|
| `simulator.py` | Generate IoT telemetry |
| `collector.py` | Device-side event pipeline |
| `local_model.py` | Lightweight inference |
| `blockchain_client.py` | Device commitments |
| `service.py` | Process lifecycle |

## Edge files

| File | Primary responsibility |
|---|---|
| `ingest.py` | Receive telemetry |
| `preprocessing.py` | Clean/normalize |
| `feature_extraction.py` | Create ML features |
| `local_model.py` | Edge inference |
| `blockchain_client.py` | Integrity commitment |
| `service.py` | Edge runtime |

## Fog files

| File | Primary responsibility |
|---|---|
| `aggregation.py` | Aggregate edge streams |
| `traffic_analysis.py` | Traffic features |
| `attack_detection.py` | Security classifier |
| `intermediate_state.py` | Maintain fog state |
| `blockchain_client.py` | Audit/alert records |
| `service.py` | Fog runtime |

## Cloud files

| File | Primary responsibility |
|---|---|
| `ingestion.py` | Receive fog data |
| `dataset_builder.py` | Build training datasets |
| `train.py` | Train models |
| `evaluate.py` | Evaluate models |
| `model_registry.py` | Hash/version models |
| `analytics.py` | Research analytics |
| `blockchain_client.py` | Register provenance |
| `service.py` | Cloud runtime |

---

# 27. What Counts as a Successful Research Contribution

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/reports/results.md` | Planned | Final evidence |
| `docs/reports/security_analysis.md` | Planned | Security evidence |
| `docs/reports/limitations.md` | Planned | Scientific limitations |

The project should **not** be evaluated solely on whether a blockchain transaction succeeds.

A research-grade submission should demonstrate the following:

### Contribution A — Architectural implementation

An executable four-layer BlockIoTIntelligence architecture exists.

### Contribution B — AI + blockchain convergence

AI and blockchain are not isolated demos. They influence the same telemetry/model/provenance pipeline.

### Contribution C — Measured trade-offs

The project quantifies both benefits and costs.

Expected trade-off:

```text
more verification/provenance
        +
better auditability
        +
stronger integrity
        ↓
additional blockchain overhead
        ↓
possible latency/resource cost
```

### Contribution D — Security evidence

The implementation demonstrates that:

```text
tampering
replay
spoofing
model replacement
```

produce measurable security failures/rejections.

### Contribution E — Reproducibility

Another student should be able to reproduce:

```text
environment
data
configuration
experiments
metrics
graphs
```

without manually reconstructing undocumented assumptions.

---

# 28. Final Recommended Implementation Milestones

### Files implemented/changed in this section

| Milestone | Files | Completion meaning |
|---|---|---|
| M1 | `configs/`, `src/common/`, tests | Clean project foundation |
| M2 | `src/device/`, `src/edge/`, baseline scripts | No-blockchain baseline works |
| M3 | `blockchain/`, blockchain clients | Ledger integrity path works |
| M4 | `src/device/`, `src/edge/` | Device + edge blockchain/AI works |
| M5 | `src/fog/` | Fog security analytics works |
| M6 | `src/cloud/` | Cloud big-data analytics works |
| M7 | `docker-compose.yml`, services | Full architecture runs |
| M8 | `experiments/`, benchmark scripts | Quantitative evaluation works |
| M9 | `tests/security/` | Security claims have evidence |
| M10 | `dashboard/`, `docs/reports/` | Research-grade presentation complete |

---

# 29. Final Implementation Position

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/BlockIoTIntelligence_ADR_Implementation.md` | Current | Final architecture and implementation decision |

The final implementation should be described using the following wording in the project report:

> **“We implement a reproducible, containerized realization of the BlockIoTIntelligence architecture proposed by Singh, Rathore, and Park. The implementation instantiates Device, Edge, Fog, and Cloud Intelligence as cooperating AI-enabled services, integrates an Ethereum-compatible private blockchain for identity, integrity, provenance, auditability, and model registration, and evaluates the resulting system against a non-blockchain baseline using accuracy, latency, computational-resource, security, scalability, and energy-related metrics.”**

Avoid claiming:

> “We reproduced every numerical result of the paper.”

Instead state:

> “We reproduced the architectural principles and evaluation dimensions of the paper and conducted a controlled implementation-specific experimental study.”

That distinction is important because the paper's quantitative section aggregates findings from multiple prior systems rather than presenting one fully specified source repository with identical datasets and execution parameters.

---

# 30. Reference Paper Mapping

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/requirements/paper_requirements.md` | Planned | Detailed paper section mapping |
| `docs/reports/paper_comparison.md` | Planned | Final reference comparison |

| Paper section / element | Implementation section |
|---|---|
| Section 1 — Motivation and challenges | Sections 1–2 |
| Section 2 — Blockchain/AI background | Background in final report |
| Section 3.1 — Architecture overview | Sections 3–7 |
| Figure 3 — Four-intelligence architecture | Section 3 |
| Section 3.2 — Methodological flow | Sections 5 and 8 |
| Figure 4 — Methodological flow | Section 5 |
| Analytics intelligence | Section 7 |
| Digital identity | Section 6 |
| Distributed cloud storage | Section 9 |
| Decentralization/distribution | Section 3 + blockchain implementation |
| Authentication/verification | Sections 6 and 14 |
| Chain structure | Section 6 |
| Section 4.1.1 — AI-driven Blockchain | Section 13 |
| Section 4.1.2 — Blockchain-driven AI | Section 13 |
| Section 4.2 — Quantitative analysis | Sections 11–12 |
| Figure 7 — Accuracy/latency comparison | Section 12 |
| Figure 8 — Architectural analysis | Dashboard + report |
| Section 5 — Research challenges | Section 22 |
| Section 6 — Conclusion and limitations | Sections 21–29 |

---

# 31. Source Notes

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `blockchain_proj_ref(2).pdf` | Source | Attached reference paper |
| `Project_list(1).pdf` | Source | Course/project allocation list |

The course project list identifies **Project 15** as:

> “Design of AI/ML-enabled Big data analytics for IoT environment”

and gives Singh et al.'s BlockIoTIntelligence paper as the reference.

The reference paper identifies the core proposal as a blockchain-enabled intelligent IoT architecture combining AI and blockchain across **cloud, fog, edge, and device intelligence**.

The paper's quantitative table reports accuracy, latency, security/privacy similarity index, computational complexity, and energy-cost values drawn from cited prior systems. This document therefore treats those values as **literature comparison baselines**, not immutable acceptance thresholds for a new implementation.

---

# 32. Immediate Next Implementation Step

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `README.md` | Planned | First executable setup instructions |
| `pyproject.toml` | Planned | Environment |
| `configs/base.yaml` | Planned | First configuration |
| `src/common/schemas.py` | Planned | First executable domain schema |
| `src/device/simulator.py` | Planned | First executable component |

The first coding milestone should be **Phase 0 + Phase 1**, not the smart contract.

The correct development sequence is:

```text
1. Create repository
2. Define schemas
3. Build IoT simulator
4. Build device → edge pipeline
5. Add fog aggregation
6. Add cloud model training
7. Measure baseline
8. Introduce blockchain
9. Repeat measurements
10. Add security experiments
11. Add scaling experiments
12. Produce final comparison
```

This sequencing makes the research contribution measurable: every blockchain-related improvement or overhead can be compared against an already working IoT + AI baseline.

---

## Appendix A — Paper Facts Used as Non-Negotiable Architecture Constraints

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `docs/requirements/paper_requirements.md` | Planned | Consolidated non-negotiable source constraints |

The following are the most important paper-grounded constraints for implementation:

1. The architecture is **hierarchically layered**.
2. The four intelligence layers are **device, edge, fog, cloud**.
3. Device intelligence is associated with data collection.
4. Edge intelligence is associated with AI-enabled base stations and feature/data processing.
5. Fog intelligence is associated with AI-enabled fog nodes and rapid processing/decision-making.
6. Cloud intelligence is associated with AI-enabled data centers and large-scale data analysis.
7. Blockchain is used for decentralization, distributed operation, digital identity, validation, security/privacy, smart contracts, and data provenance.
8. The methodology describes six IoT platform layers mapped onto the four intelligence layers.
9. The paper distinguishes **AI-driven Blockchain** from **Blockchain-driven AI**.
10. The paper uses quantitative dimensions including accuracy, latency, security/privacy, computational complexity, and energy cost.
11. The paper explicitly acknowledges unresolved problems such as scalability, interoperability, resource management, standards, anonymity, data-flow integrity, heterogeneity, cost/capability constraints, and energy efficiency.
12. The paper concludes that computational power and latency are **not completely mitigated**, and suggests further decentralized feature extraction, scaling, and classification.

---

## Appendix B — Minimum Viable Research Build

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `src/device/simulator.py` | Must implement | IoT source |
| `src/edge/service.py` | Must implement | Edge processing |
| `src/fog/service.py` | Must implement | Fog security analysis |
| `src/cloud/service.py` | Must implement | Cloud analytics |
| `blockchain/contracts/IoTRegistry.sol` | Must implement | Integrity/provenance ledger |
| `scripts/run_baseline.py` | Must implement | Baseline |
| `scripts/run_blockchain.py` | Must implement | Proposed architecture |
| `scripts/benchmark.py` | Must implement | Experimental comparison |
| `tests/security/` | Must implement | Security evidence |

The minimum acceptable implementation should still contain all four layers and both AI + blockchain components. A reduced prototype should reduce **scale**, not remove architectural layers.

---

# End of ADR + Implementation Document

# 2A. IEEE DataPort Dataset Strategy — Revised Decision

### Files implemented/changed in this section

| File | Status | Short description |
|---|---|---|
| `data/external/edge_iiotset/` | Required | Raw IEEE DataPort dataset |
| `data/metadata/dataset_card.yaml` | Planned | Dataset provenance, version, checksum and access information |
| `src/data/ingestion/edge_iiotset.py` | Planned | Ingest and validate the IEEE DataPort release |
| `src/data/validation/schema.py` | Planned | Schema/value validation |
| `src/data/preparation/clean.py` | Planned | Cleaning and duplicate/invalid-record handling |
| `src/data/preparation/feature_groups.py` | Planned | Feature taxonomy and layer mapping |
| `src/data/preparation/splits.py` | Planned | Leakage-safe train/validation/test splitting |
| `src/data/preparation/build_views.py` | Planned | Device/Edge/Fog/Cloud derived views |
| `configs/datasets.yaml` | Planned | Dataset preparation configuration |
| `experiments/manifests/` | Planned | Immutable dataset/split manifests |

## Decision

Because the course instructor has explicitly required the dataset source to be **IEEE DataPort**, the primary dataset strategy is changed to a **single primary IEEE DataPort dataset: Edge-IIoTset**.

This is a particularly strong fit because Edge-IIoTset was purpose-built as a realistic IoT/IIoT cybersecurity dataset and its underlying testbed itself contains cloud, NFV, blockchain, fog, SDN, edge, and IoT/IIoT perception layers. It includes heterogeneous devices/sensors, multiple IoT/IIoT protocols, fourteen attacks across five threat categories, and 61 selected high-correlation features extracted from 1,176 candidate features. citeturn751680search0turn716330search4

The publisher paper describes 49 original files organized into normal traffic, attack traffic, and selected ML/DL datasets, including sensor-specific captures such as ultrasonic distance, flame, heart-rate, IR, Modbus, pH, soil moisture, sound, temperature/humidity, and water level. citeturn751680search0

The release also provides two selected machine-learning views: `DNN-EdgeIIoT-dataset.csv` for deep-learning experiments and `ML-EdgeIIoT-dataset.csv` for traditional machine-learning experiments. citeturn712340search2

## Why Edge-IIoTset is preferred

| Requirement | Fit |
|---|---|
| IEEE DataPort source | Direct — published through IEEE DataPort under DOI `10.21227/MBC1-1H68`. citeturn716330search3turn716330search12 |
| IoT environment | Strong — purpose-built IoT/IIoT testbed |
| Heterogeneous sensors/devices | Strong — more than ten device/sensor types |
| Network/security analytics | Strong — labelled normal/attack traffic and flow features |
| AI/ML | Direct — selected for ML/DL intrusion-detection research |
| Edge/Fog relevance | Very strong — explicit edge/fog components in the testbed |
| Blockchain relevance | Very strong — blockchain layer in the underlying testbed |
| Cloud relevance | Strong — cloud computing layer is part of the testbed |
| Large dataset | Strong — reported DNN view is about 2.2M records and ML view about 157.8K records |
| Reproducibility | Strong — release documents its extraction and processing methodology |

## Important interpretation

We should **not** claim that the selected CSV is a complete raw sensor-value dataset for every layer. The ML/DL views are primarily network/telemetry/security feature datasets. We will therefore use Edge-IIoTset as the **real observed workload**, while our executable system models where data is generated, verified, transformed, analysed, and committed.

```text
IEEE DataPort Edge-IIoTset
        |
        +-- observed IoT/IIoT records
        +-- network-flow features
        +-- normal/attack labels
        +-- sensor/device context
                 |
                 v
        OUR EXECUTABLE ARCHITECTURE
                 |
        +--------+--------+--------+
        v        v        v        v
     Device    Edge     Fog      Cloud
```

## Required dataset hierarchy

```text
data/
├── external/
│   └── edge_iiotset/
│       ├── raw/
│       │   ├── normal/
│       │   ├── attack/
│       │   ├── selected_ml/
│       │   └── selected_dnn/
│       └── manifests/
├── metadata/
│   ├── dataset_card.yaml
│   ├── schema.json
│   └── checksums.sha256
├── standardized/
│   ├── events/
│   ├── network/
│   └── labels/
├── prepared/
│   ├── device/
│   ├── edge/
│   ├── fog/
│   └── cloud/
├── splits/
│   ├── train/
│   ├── validation/
│   └── test/
└── synthetic/
    └── security_injection/
```

Only `external/` contains the downloaded source. Every later directory contains derived artefacts and is reproducible from the source manifest plus code/configuration.

## Required preparation pipeline

```text
IEEE DataPort source
        ↓
raw immutable copy
        ↓
provenance + checksum
        ↓
schema inspection
        ↓
duplicate/null/Inf validation
        ↓
canonical feature names
        ↓
data-type normalization
        ↓
label normalization
        ↓
leakage review
        ↓
feature grouping
        ↓
layer-specific views
        ↓
train/validation/test split
        ↓
architecture simulation streams
```

### Step 1 — Preserve source data

Never edit the downloaded source in place. Record:

```text
dataset_name
IEEE DataPort DOI
retrieval date
source version
file name
SHA-256
row count
column count
```

### Step 2 — Retain the original publisher processing lineage

The Edge-IIoTset authors describe a sequence of binary labelling, multiclass labelling, CSV merging, corruption/duplicate/missing-value handling, removal of unnecessary flow features, categorical encoding, and dataset splitting. Their selected ML/DL release is the result of this preparation workflow. citeturn712340search3

Our implementation should reproduce that lineage before adding project-specific controls.

### Step 3 — Leakage audit

Every candidate feature must be checked for:

```text
direct label leakage
attack-specific identifiers
capture/session identifiers
future information
split duplicates
```

The final report must include a feature-removal table with a reason for every excluded column.

### Step 4 — Preserve both target tasks

**Binary:** `Attack_label`, where 0 indicates normal and 1 indicates attack.

**Multiclass:** `Attack_type`, for fine-grained attack categories.

These labels are part of the original Edge-IIoTset preparation methodology. citeturn712340search3

### Step 5 — Canonical event schema

Transform records to a common project schema:

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

Fields not natively present in the selected view must be marked as **derived metadata**, not presented as original dataset columns.

### Step 6 — Derive four architectural views from one source

Do not create four independent datasets. Create four views from the same canonical records.

| View | Purpose | Transformation |
|---|---|---|
| `device_view` | Source-side intelligence | minimal feature subset + provenance metadata |
| `edge_view` | preprocessing and lightweight inference | normalized protocol/network features |
| `fog_view` | traffic and attack analysis | temporal/flow aggregates |
| `cloud_view` | global analytics | full validated analytical feature set |

This keeps the experiment traceable to one source event throughout Device → Edge → Fog → Cloud.

### Step 7 — Fog temporal features

Because the selected dataset is event/flow oriented, derive windowed features for fog processing:

```text
window = 1s / 5s / 30s / 60s

features:
  event_count
  mean_interarrival
  std_interarrival
  mean_packet_size
  std_packet_size
  bytes_per_second
  unique_destination_count
  duplicate_count
  verification_failure_count
  attack_score_history
```

These are our **derived features** and must be labelled as such.

### Step 8 — Leakage-safe splitting

Primary split target:

```text
70% train
15% validation
15% test
```

Use stratification for labels and group-aware constraints where capture/device metadata allows it. In addition to the main split, create a harder generalization experiment holding out source/device groups so the model is not rewarded for memorising a particular capture environment.

### Step 9 — Imbalance handling

Never run SMOTE or similar oversampling before the split.

Correct ordering:

```text
clean
 ↓
split
 ↓
fit preprocessing on train only
 ↓
optional oversampling on train only
 ↓
validate on untouched validation set
 ↓
report once on untouched test set
```

### Step 10 — Scaling

Fit the scaler only on the training data and apply the frozen transformation to validation/test.

### Step 11 — Dataset manifests

Each derived view must have a manifest containing at least:

```text
source dataset/DOI
source file hash
view name
row count
feature count
label definition
split seed
preprocessing version
git commit
```

## Dataset-to-experiment mapping

| Experiment | View | Target | Main layer |
|---|---|---|---|
| Baseline binary IDS | edge | `Attack_label` | Edge |
| Multiclass attack detection | fog | `Attack_type` | Fog |
| Lightweight source inference | device | `Attack_label` | Device |
| Temporal anomaly detection | fog | `Attack_label` | Fog |
| Global model training | cloud | binary + multiclass | Cloud |
| Blockchain integrity | any view + source metadata | integrity status | All |
| Tampering | canonical records | integrity violation | Device→Edge |
| Replay | canonical records | replay violation | Edge/Fog |
| Scaling | replayed/sampled records | throughput/latency | All |

## Synthetic-data policy

Synthetic data is allowed only for **controlled security and systems experiments**, not as a replacement for the primary dataset.

Examples:

```text
real Edge-IIoTset event
       ↓
controlled mutation/injection
       ↓
 tampering / replay / spoofing experiment
```

This keeps the workload grounded in the IEEE DataPort data while allowing us to test blockchain-specific properties that are not represented directly as labels in the source data.

## Recommended project data strategy — final

**Primary dataset:** Edge-IIoTset, IEEE DataPort, DOI `10.21227/MBC1-1H68`.

**No second mandatory primary dataset.**

A second IEEE DataPort dataset should be introduced only as an optional external-validation experiment after the core project works and only with instructor approval. The main implementation, results, and report should remain centered on Edge-IIoTset.
