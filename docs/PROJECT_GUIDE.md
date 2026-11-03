# BlockIoTIntelligence — Complete Project Guide

This guide explains the whole project to someone who has never seen it. It covers:
- what the project is about and the ideas behind it (in plain language),
- everything that has been built so far, in the order it was done and why,
- what every folder and file is for,
- how to run it, what the results are, and what is still left to do.

If you only have five minutes, read sections 1, 2, 9, 11.1 and 12.

---

## Contents

1. [The project in plain language](#1-the-project-in-plain-language)
2. [Key ideas you need (glossary)](#2-key-ideas-you-need-glossary)
3. [The architecture: four layers and a shared ledger](#3-the-architecture-four-layers-and-a-shared-ledger)
4. [The journey of one piece of data](#4-the-journey-of-one-piece-of-data)
5. [What was done, step by step](#5-what-was-done-step-by-step)
6. [Folder-by-folder and file-by-file guide](#6-folder-by-folder-and-file-by-file-guide)
7. [Important design decisions and why](#7-important-design-decisions-and-why)
8. [Problems found along the way and how they were handled](#8-problems-found-along-the-way-and-how-they-were-handled)
9. [Results so far](#9-results-so-far)
10. [How to run everything](#10-how-to-run-everything)
11. [Progress report: what is completed and what is pending](#11-progress-report-what-is-completed-and-what-is-pending)
12. [The complete project outcome](#12-the-complete-project-outcome)
13. [Architecture in depth](#13-architecture-in-depth)
14. [How the project maps to the paper](#14-how-the-project-maps-to-the-paper)
15. [Experiment methodology and metric definitions](#15-experiment-methodology-and-metric-definitions)
16. [Technology stack and environment](#16-technology-stack-and-environment)
17. [Questions to expect in the presentation](#17-questions-to-expect-in-the-presentation)
18. [References](#18-references)

---

## 1. The project in plain language

### The course assignment

This is **Project 15** of the *Research in Information Security* course:
**"Design of AI/ML-enabled Big Data Analytics for IoT Environment."**
The assignment gives one reference research paper:

> S. K. Singh, S. Rathore, J. H. Park, *"BlockIoTIntelligence: A Blockchain-enabled Intelligent IoT
> Architecture with Artificial Intelligence"*, Future Generation Computer Systems 110 (2020) 721–743.
> (The PDF is in this repository: `blockchain_proj_ref.pdf`.)

### The problem the paper talks about

**IoT (Internet of Things)** means everyday physical devices that are connected to a network: temperature
sensors, water-level sensors, heart-rate monitors, smart meters, factory controllers. There are billions of
them, and they produce enormous amounts of data ("big data").

People want to use **AI (Artificial Intelligence)** on this data, for example to notice automatically that
a network is under attack. But there are problems:

1. **Trust**: how do you know the data wasn't changed on the way? An attacker could alter a sensor
   reading, or make attack traffic look normal.
2. **Identity**: how do you know a message really came from the device it claims to come from?
3. **Centralization**: if everything goes to one central server, that server is a single point of
   failure and a single point of attack.
4. **Speed**: sending everything to a far-away cloud is slow.

### The paper's idea

The paper proposes an architecture (a design, not a finished program) called **BlockIoTIntelligence**
that combines two technologies:

- **AI at every level**, not just in the cloud: on the device, at the nearby "edge" station, at a
  regional "fog" node, and in the "cloud" data centre.
- **Blockchain** (a shared, tamper-proof record book) connecting those levels, so that identities, data
  fingerprints and AI models can be verified by anyone and cannot be secretly changed.

The paper argues this makes AI **more accurate and more secure**, but also **slower** (checking and
recording things on a blockchain takes time). It supports this by comparing numbers from other published
studies. **It does not provide a working system.**

### What this project does

We turn the paper's design into a **real, working program**, feed it **real IoT attack data**, and
**measure** whether the paper's claims hold:

- Does blockchain make the AI more accurate?
- How much slower does it make things?
- Which attacks does it actually stop?

This is what makes it research: we test the paper's claims with experiments, not just re-describe them.

---

## 2. Key ideas you need (glossary)

You don't need to know these in depth; a rough idea is enough to follow the rest.

### IoT and networking

| Term | Meaning |
|---|---|
| **IoT device / sensor** | A small connected device that measures something (temperature, distance, water level…) and sends it over the network. |
| **Edge** | Computing done *close* to the devices, e.g. a local gateway or base station. Fast, but not very powerful. |
| **Fog** | A middle layer between edge and cloud, e.g. a regional server that combines data from several edges. |
| **Cloud** | Big, powerful data centres far away. Slow to reach, but can do heavy computation such as training AI models. |
| **Network traffic / packet** | The messages devices send. Each message ("packet") has properties such as size, protocol and flags. |
| **Protocol** | The "language" of a message: TCP, UDP, HTTP, MQTT (common in IoT), Modbus (common in factories), and so on. |
| **Cyber attack** | A malicious action, e.g. DDoS (flooding a target with traffic), SQL injection, password guessing, ransomware. |
| **IDS (Intrusion Detection System)** | Software that looks at traffic and decides "normal" or "attack". Our AI models are IDSs. |

### AI / Machine Learning

| Term | Meaning |
|---|---|
| **Model** | A program that learns patterns from examples and then makes predictions on new data. |
| **Training** | Showing the model many labelled examples ("this traffic was normal, this was an attack"). |
| **Features** | The measurable properties the model looks at (e.g. packet length, TCP flags). |
| **Label** | The correct answer for an example. Here: `Attack_label` (0 = normal, 1 = attack) and `Attack_type` (which of 15 classes). |
| **Binary vs multiclass** | Binary = two answers (attack / normal). Multiclass = many answers (Normal plus 14 attack types). |
| **Decision tree / Random Forest / Gradient Boosting / MLP** | Types of models. A decision tree is a flowchart of yes/no questions; a Random Forest is many trees voting; Gradient Boosting builds trees that correct each other; an MLP is a small neural network. |
| **Train / validation / test split** | The data is divided in three: *train* to learn from, *validation* to choose between models, *test* to measure final performance on data the model has **never seen**. |
| **Accuracy** | Fraction of predictions that are correct. |
| **Precision / recall / F1** | Precision: of the things flagged as attack, how many really were. Recall: of the real attacks, how many were caught. F1 combines both. **Macro-F1** averages F1 over all classes equally, so rare attack types count as much as common ones. |
| **Data leakage** | When the model accidentally gets a hint of the answer from a column it shouldn't use (e.g. an IP address only attackers used). It makes results look better than they really are. We check for this carefully. |

### Blockchain and cryptography

| Term | Meaning |
|---|---|
| **Hash (SHA-256)** | A "fingerprint" of data: a short fixed-length code computed from the data. Change even one character and the fingerprint changes completely. You cannot go backwards from the fingerprint to the data. |
| **Digital signature (Ed25519)** | Proof that a message came from a specific device. The device has a secret *private key* to sign; anyone with its *public key* can check the signature. |
| **Blockchain** | A shared record book (ledger) that many parties can read and that cannot be secretly edited after the fact. Entries are grouped into "blocks" linked by hashes. |
| **Ethereum / EVM** | A popular blockchain platform that can run programs. EVM is the "Ethereum Virtual Machine" that runs them. |
| **Smart contract** | A program stored on the blockchain that enforces rules, e.g. "only registered devices may record data". Ours is written in **Solidity**. |
| **Transaction** | A request to change something on the blockchain (e.g. "record this fingerprint"). |
| **Gas** | The unit of computational cost on Ethereum. More gas means more work for the blockchain. We use it as a cost measure. |
| **Private / local chain** | A blockchain running only on our own machine for testing (no real money). We use **Anvil** from the **Foundry** toolkit. |
| **Merkle tree** | A way to combine many fingerprints into one "root" fingerprint. You can later prove that one item belongs to the group using a short proof. It lets us record 256 events with one blockchain transaction instead of 256. |
| **Replay attack** | Resending an old, genuine message to trick the system into processing it again. |
| **Impersonation / spoofing** | Pretending to be a device you are not. |
| **Tampering** | Changing data while it travels. |

---

## 3. The architecture: four layers and a shared ledger

```
                         ┌─────────────────────────────┐
                         │      CLOUD INTELLIGENCE      │  trains all AI models, picks the best,
                         │  (big analytics, training)   │  registers every model on the blockchain
                         └──────────────▲──────────────┘
                                        │ batches of analysed events
                         ┌──────────────┴──────────────┐
                         │       FOG INTELLIGENCE       │  combines edges, identifies WHICH attack
                         │  (attack-type detection)     │  (15 classes), raises alerts, logs alerts
                         └──────────────▲──────────────┘  on the blockchain
                                        │ checked, pre-processed events
                         ┌──────────────┴──────────────┐
                         │       EDGE INTELLIGENCE      │  verifies identity, signature and data
                         │ (verification + fast AI)     │  fingerprint against the blockchain,
                         └──────────────▲──────────────┘  then decides attack vs normal
                                        │ signed events
                         ┌──────────────┴──────────────┐
                         │      DEVICE INTELLIGENCE     │  produces data, quick local AI check,
                         │ (sensors + tiny AI)          │  fingerprints + signs every event and
                         └─────────────────────────────┘  records the fingerprint on the blockchain

      ════════════════════ BLOCKCHAIN (shared, tamper-proof ledger) ════════════════════
        device identities · data fingerprints · processing history · alerts · AI model fingerprints
```

This matches Figure 3 of the paper. The paper also maps six "IoT platform layers" onto these four:
- physical → device
- communication and link-control → edge
- service and management → fog
- application → cloud

**What is stored where** (a key design choice from the ADR):
- **On the blockchain:** only small things. Fingerprints (hashes), IDs, timestamps, model fingerprints,
  alert fingerprints.
- **Off the blockchain** (normal files): the actual data, features and trained models. Blockchains are far
  too slow and expensive to store millions of readings.

---

## 4. The journey of one piece of data

Following one network event through the blockchain-enabled system makes the whole design concrete.

1. **Device.** A row of real IoT traffic is replayed as if a device (`device-0003`) just produced it.
   The device:
   - runs its tiny AI model (a decision tree) for a first guess: "normal".
   - computes the event's **fingerprint** (SHA-256 of the event in a fixed, canonical format).
   - **signs** the fingerprint with its private key.
   - sends a **transaction** to the smart contract: "device-0003 committed event X with fingerprint F".
     (In *batch mode*, it records one Merkle root for a group of its events instead.)
2. **In transit.** The event travels to an edge node. *This is where an attacker could interfere.*
3. **Edge.** The edge node checks, in order:
   - Is the message well-formed? Is it a duplicate? Is its sequence number newer than the last one?
   - Is `device-0003` **registered** on the blockchain?
   - Does the attached public key match the one **registered** for `device-0003`?
   - Recomputing the fingerprint of what arrived: does it match the fingerprint **on the blockchain**?
     If someone changed the data, it won't.
   - Is the signature valid?
   - Has **any** edge already processed this event (recorded on the blockchain)? If yes, it's a replay.

   If every check passes, the edge's AI model (Random Forest) decides "attack or normal", and the edge
   records on the blockchain that it processed the event (provenance).
4. **Fog.** The fog node receives events from all edges. Its AI model decides **which** of 15 classes
   the event is. If it is an attack, or the device is flooding traffic, it raises an **alert** and records
   the alert's fingerprint on the blockchain, so alerts can't later be deleted or altered.
5. **Cloud.** The cloud runs the most accurate model and records a fingerprint of its predictions. Before
   anything started, the cloud had registered every layer's AI model fingerprint on the blockchain, and each
   model was checked against it. A secretly replaced model would have been refused.
6. **Measurement.** Because we know the true label of every row, we compute accuracy for every layer, and
   we time every step.

The **baseline** (no-blockchain) run does exactly the same thing minus every blockchain step. Comparing
the two runs is the core experiment.

---

## 5. What was done, step by step

### Step 0 — Starting point

The repository initially contained only planning documents:
- `BlockIoTIntelligence_ADR_Implementation.md`, a very detailed design plan (an "ADR", *Architecture
  Decision Record*) with 9 implementation phases (0–8).
- `IEEE_DataPort_Edge_IIoTset_Dataset_Preparation_Plan.md`, the plan for the dataset.
- `understanding_1.md`, a summary written by a teammate.
- `Project_list.pdf` (the course project list) and `blockchain_proj_ref.pdf` (the paper).

There was **no code and no data**.

### Step 1 — Verifying the plan against the paper and the dataset

Before building, every factual claim in the plan was checked against the paper's PDF, the dataset's own
paper, and the actual data files once downloaded.

- **Correct:** the paper's numbers (Table 3, Figure 7), the six-to-four layer mapping, the dataset facts
  (61 features chosen from 1,176, 14 attacks in 5 categories, row counts).
- **Problems found in the plan** (details in [section 8](#8-problems-found-along-the-way-and-how-they-were-handled)):
  - the plan's time-window features would leak the answer.
  - the dataset has no device IDs.
  - earlier sections of the plan still described fake (synthetic) sensors after the team had decided on
    real data.
  - a few smaller inconsistencies.

### Step 2 — Getting the dataset

The course requires a dataset from **IEEE DataPort**. The chosen one is **Edge-IIoTset**
(DOI 10.21227/MBC1-1H68): real traffic from a purpose-built IoT/industrial-IoT testbed, with normal traffic
from 10 kinds of sensors and 14 kinds of attacks.

- IEEE DataPort requires a paid-subscription login to download. The dataset's own DataPort page points to
  the authors' official Kaggle copy (identical files), so we downloaded that (version 5, all 52 files,
  ~10 GB) and still cite IEEE DataPort as the source.
- Every file was fingerprinted (SHA-256) so anyone can prove they have exactly the same data.
  `scripts/download_edge_iiotset.py` does all of this reproducibly.

### Step 3 — Phase 0: the project skeleton

Configuration files, shared utilities (data formats, hashing and signatures, logging, timing, storage),
the test framework and the linter. The ADR's rule for this phase: "tests must run even before any real
functionality exists."

### Step 4 — Preparing the data

`scripts/prepare_dataset.py` turns the raw CSV into clean, ready-to-use files:

1. **Validate:** check that all 63 columns exist and the labels make sense.
2. **Remove leaky columns:** 15 columns the dataset's own authors also remove (IP addresses, timestamps,
   ports, raw payloads), plus 4 columns that never change. Every removal is written down with its reason.
3. **Remove duplicates:** 309,530 exact duplicate rows.
4. **Split** into train (70%), validation (15%) and test (15%), keeping the same proportion of each attack
   type in every part.
5. Build four **views**, one per layer (e.g. the device only sees 13 simple header features; the edge,
   fog and cloud see all 42).

### Step 5 — Phase 1: the four-layer pipeline without blockchain (the baseline)

- The **cloud** trains the models for all layers:
  - device: decision tree.
  - edge: Random Forest.
  - fog: Random Forest.
  - cloud: three candidates, of which the best (Random Forest) is deployed.
- A **device simulator** replays held-out test rows as live traffic from N logical devices.
- **Edge, fog and cloud services** process the stream and measure accuracy and time at every step.

Result: 200,000 unseen events processed at ~12,000 events per second with 96–97% accuracy at edge, fog
and cloud.

### Step 6 — Phases 2 to 6: adding the blockchain

- Wrote the **smart contract** `IoTRegistry.sol`: device registry, data commitments (single and batch),
  processing records, alert audit, model registry, inference records, and access control (only authorized
  nodes may write).
- Installed the toolchain *inside the project* (Foundry/Anvil, the Solidity compiler, web3). Nothing was
  installed system-wide.
- Wrote one **blockchain client per layer**, doing exactly what each layer needs (commit, verify, audit,
  register).
- Two modes, to measure the cost trade-off:
  - **per-event:** one blockchain transaction per event. Simple and strongest, but slow.
  - **Merkle batch:** one transaction per device per group of events. Much cheaper.

### Step 7 — Experiments for the first presentation

1. **Comparison:** baseline vs per-event vs batch, 3 random seeds, 10,000 events each. Accuracy, time,
   CPU, gas.
2. **Integrity under attack:** an attacker disguises real attacks as normal traffic in transit. Does the
   system still catch them?
3. **Security:** eight attack types injected one at a time. Which does each version stop?
4. **Scaling:** 10 to 500 devices.
5. **Full scale:** 200,000 events, baseline and batch.
6. **Figures and tables** for the slides, generated automatically from the results.

### Step 8 — Final task 1: real timestamps and real devices (Oct 2026)

The mid-term had to simulate *which device* sent a message and *when*. Final task 1 replaces both with the
real values from the 24 packet captures:

1. **Packet index:** every packet's real time, session and addresses (21.1 million packets).
2. **Features re-extracted with tshark** for every packet. This also fixes a fault in the publisher's CSVs: every
   UDP row is shifted by one column, because multi-valued fields were joined with the CSV comma.
3. **CSV rows matched to their packets** (17.6 million rows, 10 ambiguous) to know what the publisher selected.
4. **Real devices:** 10 sensors from the dataset paper; attacks belong to the attacked segment.
5. **Dataset v2:** 1.76 million rows, normal traffic from all 10 sensors; three splits (random, time-based,
   leave-one-device-out).
6. **Realistic replay:** each device sends its own messages with their real gaps.
7. **Retrained and re-evaluated** every layer.
8. **The other experiments re-run on the realistic replay** (finished 3 Nov 2026): tampering in transit, the 8
   security attacks, the mode comparison and scaling to 500 devices.

Details and results: [final/01_real_timestamps_device_identity.md §10](final/01_real_timestamps_device_identity.md#10-implementation-and-results-28-oct-2026)
(step 8 in §10.10).

### Step 9 — Final task 2: a 4-validator blockchain network (Nov 2026)

Until now the blockchain was **one Anvil node** that mined every transaction instantly. Final task 2 replaces it
with a private network of **4 Hyperledger Besu validators running QBFT consensus**:
- each validator has its own key, database and ports;
- one block is produced per second;
- a block is final when 3 of the 4 validators agree.

The layers use different nodes: device gateway → node 0, edges → nodes 1 and 2, fog → node 3, cloud → node 0.

1. **Toolchain:** `scripts/setup_besu.py` installs a pinned Besu release, checking its SHA-256.
2. **Network:** `src/common/qbft.py` starts a fresh 4-validator network for every run and checks at the end that
   all 4 nodes hold the same chain.
3. **Client** (`src/common/blockchain.py`):
   - transactions are signed by the client;
   - a read through any node waits until that node has every write already confirmed elsewhere;
   - fog and cloud audit records are confirmed in the background, but each run still waits for all of them
     before it ends.
4. **Experiments** (dataset v2 realistic replay):
   - the same workload on 1 node with instant blocks, 1 node with 1 block/s, and 4 validators;
   - every write awaited;
   - block periods of 1, 2 and 5 s;
   - scaling to 500 devices;
   - all 8 attacks.
5. **Main results:**
   - message latency 2.75 s at 1 block/s, set by block time, not consensus;
   - security, accuracy and gas unchanged.

Details and results: [final/02_multi_node_blockchain.md §10](final/02_multi_node_blockchain.md#10-implementation-and-results-3-nov-2026).

### Step 10 — Add-on after task 2: fault tolerance (Nov 2026)

Experiment F of the ADR: parts of the running system are switched off and back on. Before this add-on nothing
handled a failure: a failed edge or fog lost its traffic, the cloud had no queue, and a dead blockchain node stopped
the whole run.

1. **Recovery mechanisms:**
   - an edge or fog that fails hands its traffic to the next one;
   - the fogs hold the cloud's input while it is down and forward it when it returns (store and forward);
   - the blockchain client switches to another node when its node dies, and resends every transaction not yet
     confirmed. This is the ADR's "retry + local queue + eventual commit", built for the first time.
2. **A fault injector** (`src/common/faults.py`) switches off a device, an edge, a fog, the cloud, or crashes and
   restarts validators while a run streams.
3. **13 runs** on the 4-validator network:
   - each fault from 30 to 60 s;
   - edge, fog and cloud each with and without recovery;
   - plus 1 and 2 of 4 validators down.
4. **Main results:**
   - **With recovery, no message is lost** in any scenario, and every prediction is unchanged.
   - **Without recovery,** 19–26% of the run's messages are lost, including up to 1,386 attack messages.
   - **With 1 of 4 validators down** the chain continues at 0.4 blocks/s.
   - **With 2 of 4 down** it halts and resumes 64.8 s after the quorum returns. Nothing is lost, and every node ends
     with the same chain.
   - **Finding:** fog failover loses the fog's flood-detection state; in this run, all 108 flood alerts.

Details and results: [final/02a_fault_tolerance.md §10](final/02a_fault_tolerance.md#10-implementation-and-results-3-nov-2026).

---

## 6. Folder-by-folder and file-by-file guide

### 6.1 The big picture

```
BlockIoTIntelligence/
├── (planning documents + PDFs)   what the project is supposed to be
├── README.md                     quick start
├── configs/                      all settings in one place (no numbers hard-coded in code)
├── src/                          the actual system (all the Python source code)
│   ├── common/                   shared tools used by every layer
│   ├── data/                     reading, checking and cleaning the dataset
│   ├── device/  edge/  fog/  cloud/   the four intelligence layers
│   └── pipeline.py               wires the four layers together and runs them
├── blockchain/                   the smart contract and its compiled output
├── scripts/                      command-line programs you actually run
├── tests/                        automated checks that the code works
├── data/                         the dataset (raw + processed); mostly NOT stored in git
├── models/                       trained AI models + their fingerprints
├── experiments/                  raw experiment outputs and data-lineage records
├── docs/                         this guide and the presentation results
└── tools/, .venv/                local toolchain (blockchain node, compiler, Python libs); NOT in git
```

**Why this structure?** Each folder has one job. The four layers live in separate folders because the
paper's whole point is that intelligence is *distributed* across layers; putting them in one file would
hide that (the ADR explicitly rejects "one Python monolith"). Shared code lives in `src/common/` so the
layers don't copy each other. Anything you *run* is in `scripts/`; anything that is *reused* is in `src/`.

### 6.2 Top-level files

| File | What it is | Why it exists |
|---|---|---|
| `BlockIoTIntelligence_ADR_Implementation.md` | The original design plan (3,355 lines) | Defines the architecture, phases and experiments we follow |
| `IEEE_DataPort_Edge_IIoTset_Dataset_Preparation_Plan.md` | The original dataset plan | Defines how data must be prepared (no leakage, correct splitting) |
| `understanding_1.md` | A teammate's summary of the plan | Background reading (its links point to another computer and don't work here) |
| `Project_list.pdf` | The course's list of projects | Shows Project 15 and its reference paper |
| `blockchain_proj_ref.pdf` | The reference research paper | The source of all requirements and of the numbers we compare against |
| `README.md` | Short project introduction and how to run it | The first file a newcomer should open |
| `pyproject.toml` | Python project settings | Lists dependencies, test settings and code-style rules |
| `requirements.txt` | Exact versions of Python libraries | So everyone installs the same versions (reproducibility) |
| `Makefile` | Shortcuts: `make setup`, `make data`, `make test`… | Saves typing long commands |
| `.env.example` | Template for local settings | Documents the settings that can be overridden |
| `.gitignore` | Files git should not store | The dataset (10 GB), trained models and toolchain are too big and can be regenerated |

### 6.3 `configs/` — all settings

Settings live here instead of inside the code, so experiments can change them without editing programs,
and every result can record exactly which settings produced it.

| File | Controls |
|---|---|
| `base.yaml` | Global settings: random seed (42), number of devices/edges/fogs/clouds, where models and results go |
| `datasets.yaml` | Which dataset files to use, the 15 leaky columns to drop and *why*, which columns are categories, split ratios (70/15/15); dataset v2 settings (session gap, CSV time zone, rows per class and device, fog flood threshold for the realistic replay) |
| `models.yaml` | Which AI model each layer uses and its settings, and the training sample size (300,000 rows) |
| `blockchain.yaml` | Blockchain network settings (local address, chain ID, dev accounts); what the client does when a node stops answering (`retry`: failover rounds, pause, receipt timeout); the multi-node QBFT network of final task 2 (Besu version and checksum, 4 validators, block period, gas limit) |
| `experiments.yaml` | Experiment plans: the `presentation1` suite (modes, seeds, sizes, device counts), `final_task1` (the same on dataset v2's realistic replay), `final_task2` (single node vs QBFT network) and `final_faults` (the fault scenarios of the fault-tolerance add-on) |

### 6.4 `src/common/` — shared tools

These are used by every layer. Per the ADR, this folder must not contain any layer-specific logic.

| File | What it does | Why it matters |
|---|---|---|
| `config.py` | Reads the YAML settings; computes a fingerprint of the settings | Every result records exactly which settings produced it |
| `schemas.py` | Defines the standard data formats: a telemetry event, an alert, model metadata, a blockchain receipt… | All layers agree on what a message looks like; malformed messages are rejected automatically |
| `crypto.py` | Canonical JSON, SHA-256 fingerprints, Ed25519 device keys and signatures | The basis of integrity and identity. "Canonical" means the same data always produces the same fingerprint (key order and number formatting are fixed) |
| `merkle.py` | Builds a Merkle tree over many fingerprints and checks inclusion proofs | Enables batch mode: one blockchain transaction covers a whole group of events |
| `blockchain.py` | Starts and stops a private Anvil chain; deploys the contract; sends transactions (signed by the node, or locally with `LocalSigner`); records the time and gas of every transaction; one `Chain` per node with read-your-writes across nodes; optional background confirmation of audit writes; failover to another node with every unconfirmed transaction resent (fault-tolerance add-on) | The single place that talks to the blockchain, so all measurements are collected consistently |
| `qbft.py` | Builds, starts, checks and stops a private network of 4 Besu validators with QBFT consensus (final task 2); crashes and restarts single validators (fault-tolerance add-on) | A real multi-node blockchain: blocks need 3 of 4 validators |
| `faults.py` | Fault schedule and injector: takes a device, edge, fog, the cloud or a validator down and back up while a run streams, logging every action (fault-tolerance add-on) | Experiment F: what each failure costs and how the system recovers |
| `metrics.py` | Times each layer and measures CPU and memory | Produces the latency and resource numbers |
| `storage.py` | Saves data as Parquet files, each with a "manifest" (fingerprint, row count, git commit); refuses to load a file whose fingerprint changed | Off-chain storage with proof the data wasn't altered |
| `logging.py` | Structured (JSON) log messages | Makes logs machine-readable |

### 6.5 `src/data/` — preparing the dataset

| File | What it does |
|---|---|
| `ingestion/edge_iiotset.py` | Loads the dataset CSV exactly as-is (everything as text, nothing silently converted) and attaches provenance: source file, row number, file fingerprint |
| `ingestion/pcap_index.py` | Reads the 24 packet captures: every packet's real time, addresses, ports, sessions (final task 1) |
| `ingestion/tshark_extract.py` | Re-extracts the 61 publisher features of every packet with Wireshark's tshark (final task 1) |
| `validation/schema.py` | Checks the 63 expected columns and the 15 valid classes, and that the two labels agree with each other. Stops with an error if not |
| `preparation/clean.py` | Removes leaky and constant columns, normalizes categories (e.g. "0" and "0.0" both mean "absent"), removes duplicates, counts rows whose features are identical but labels differ. Records a reason for every removal |
| `preparation/splits.py` | Splits into train/validation/test with the same class proportions; reports any feature patterns that appear in both train and test. Dataset v2: time-based split (per-session cut points) and leave-one-device-out |
| `preparation/raw_normalize.py` | Decodes tshark's values into the publisher's encoding (hex, True/False) and detects shifted rows (final task 1) |
| `preparation/timestamps.py` | Matches publisher CSV rows to their packets (time of day in UTC+1 plus addresses) (final task 1) |
| `preparation/devices.py` | Maps each capture to its real device (`data/metadata/device_map.yaml`) (final task 1) |
| `preparation/realistic.py` | Dataset v2 helpers: capture list, row ids, per-capture event tables, equal replay share per capture (final task 1) |
| `preparation/feature_groups.py` | Decides which columns each layer sees (device: 13 cheap header fields; edge, fog, cloud: all 42) |

### 6.6 The four layers: `src/device/`, `src/edge/`, `src/fog/`, `src/cloud/`

Every layer has a **`service.py`** (what the layer does) and a **`blockchain_client.py`** (what the layer
does on the blockchain). The service works without the blockchain; the blockchain client is plugged in
only for blockchain runs. That lets one piece of code serve both the baseline and the blockchain
experiment, so the **only** difference between the two runs is the blockchain.

#### `src/device/` — Device Intelligence

| File | What it does |
|---|---|
| `simulator.py` | Turns prepared dataset rows into a live stream of events from N logical devices, assigns each event an ID, a sequence number and a replay timestamp. (The dataset has no usable device IDs or timestamps; see section 8.) |
| `collector.py` | Gives each device a deterministic key pair; "seals" an event (computes its fingerprint and signs it) |
| `service.py` | Runs the device's tiny AI model (decision tree, attack vs normal) on each event |
| `blockchain_client.py` | Seals every event and records its fingerprint on-chain: one transaction per event, or one Merkle root per device per batch |

#### `src/edge/` — Edge Intelligence

| File | What it does |
|---|---|
| `ingest.py` | Checks that need no blockchain: valid format, not a duplicate, sequence number increasing. Updates its memory only after *all* checks pass (the fix for the lockout bug in section 8) |
| `preprocessing.py` | Scales numbers and converts categories into model inputs, learned from training data only |
| `service.py` | Runs the gate checks, then the blockchain checks (if enabled), then the Random Forest (attack vs normal) |
| `blockchain_client.py` | Verifies device registration, the public key, the on-chain fingerprint, the signature and cross-edge replay; records "processed" on-chain |

#### `src/fog/` — Fog Intelligence

| File | What it does |
|---|---|
| `traffic_analysis.py` | For each device, counts events in 1, 5, 30 and 60-second sliding windows, and flags devices sending far more than normal (flooding) |
| `service.py` | Merges streams from all edges, runs the Random Forest (15 attack types), raises alerts |
| `blockchain_client.py` | Records a fingerprint of every alert on-chain (up to 150 alerts per transaction), creating an audit trail nobody can quietly edit |

#### `src/cloud/` — Cloud Intelligence

| File | What it does |
|---|---|
| `train.py` | Trains the device, edge and fog models and three cloud candidates (Random Forest, Gradient Boosting, MLP), scores them on validation data and deploys the best |
| `model_registry.py` | Saves each model with its fingerprint, the training-data fingerprint, its settings and scores; refuses to load a model whose file no longer matches its fingerprint |
| `evaluate.py` | Computes accuracy, precision, recall, F1, ROC-AUC and confusion matrices |
| `service.py` | Receives fog output, runs the cloud model, produces per-layer accuracy reports |
| `blockchain_client.py` | Registers every model's fingerprint on-chain; verifies a model against the *on-chain* fingerprint (not the local file, which an attacker could also edit); records inference results |

#### `src/pipeline.py` — the conductor

Creates the layers, connects them (device → the right edge → fog → cloud), optionally starts a private
blockchain and plugs in the blockchain clients, streams the data, times every layer, and returns one
complete result (accuracy, latency, CPU, memory, gas, rejections, model IDs, reproducibility info).
It also accepts an **interceptor**, a hook between device and edge where experiments can play the
attacker.

### 6.7 `blockchain/` — the smart contract

| File | What it is |
|---|---|
| `contracts/IoTRegistry.sol` | The smart contract (Solidity). Functions: `registerDevice`, `revokeDevice`, `authorize`, `commitData` (one event), `commitBatch` (Merkle root), `recordProcessing`, `recordAlert(s)`, `registerModel`, `recordInference`. It refuses writes from unauthorized accounts, unknown devices and duplicate commitments |
| `foundry.toml` | Compiler settings (Solidity 0.8.24, optimizer on) |
| `artifacts/` | Compiled output: the contract's bytecode and ABI (its "interface description"), used by Python to talk to the contract |
| `scripts/` | Empty for now; a standalone deploy script is planned |

### 6.8 `scripts/` — the programs you run

| Script | Purpose | Typical time |
|---|---|---|
| `download_edge_iiotset.py` | Downloads the dataset (all files or `--essential`), extracts it, fingerprints every file, writes the dataset card. `--verify` re-checks all fingerprints | slow network: hours; fast: minutes |
| `prepare_dataset.py` | Validate → clean → split → build layer views; writes manifests | ~1 min |
| `train_models.py` | Cloud trains and registers all models | ~2 min |
| `run_baseline.py` | Four-layer run **without** blockchain | 200k events in ~17 s |
| `run_blockchain.py` | Four-layer run **with** blockchain (`--mode per_event` or `batch`) | depends on mode |
| `run_experiments.py` | Runs the whole comparison and scaling plan from `experiments.yaml` | ~30 min |
| `run_integrity_accuracy.py` | "Attacker disguises attacks" experiment | ~3 min |
| `run_security.py` | Eight-attack security experiment | ~5 min |
| `run_presentation1.sh` | Runs **all** presentation experiments in order | ~50 min |
| `make_figures.py` | Draws the figures and tables from results: `--set presentation1` (default), `final_task1`, `final_task2`, `final_faults` | seconds |
| `validate_tshark_extraction.py` | Final task 1: compares tshark's features with the publisher's CSVs row by row | ~10 min |
| `build_realistic_events.py` | Final task 1: 24 packet captures → per-packet event tables with real time, session and device | ~15 min |
| `build_realistic_dataset.py` | Final task 1: dataset v2 and its random and time splits | ~5 min |
| `run_realistic_eval.py` | Final task 1: test-split metrics, leave-one-device-out, realistic replay runs | minutes to hours (LODO) |
| `run_final_task1.sh` | Final task 1: reproduces everything (`--step8-only`: the experiments re-run on the replay, ~30 min) | hours |
| `setup_besu.py` | Final task 2: installs the pinned, checksum-verified Besu release into `tools/besu` | ~1 min |
| `run_multinode.py` | Final task 2: `check` (4-validator network, cross-node read), `run` (experiment groups T2.1–T2.4) | ~1.5 h for `run` |
| `run_final_task2.sh` | Final task 2: reproduces every result and figure | ~1 h 45 min |
| `run_faults.py` | Fault-tolerance add-on: the fault scenarios of `final_faults` (`--scenarios`, `--resume`) | ~40 min |
| `run_final_faults.sh` | Fault-tolerance add-on: reproduces every result and figure | ~40 min |

### 6.9 `tests/` — automated checks (99 tests, all passing)

Run with `make test` (or `.venv/bin/python -m pytest`). They prove the code does what it claims.

| Folder / file | Checks |
|---|---|
| `unit/test_crypto.py` | Fingerprints are stable; changed data changes the fingerprint; wrong key → invalid signature |
| `unit/test_schemas_and_config.py` | All settings load; split sums to 100%; malformed events rejected |
| `unit/test_edge_ingest.py` | Duplicates and replays rejected; a rejected forged event can't lock out a real device |
| `unit/test_merkle.py` | Every event proves into its batch root; changed events don't |
| `unit/test_traffic_analysis.py` | Window counts and flood detection are correct |
| `unit/test_pcap_index.py` | Packet capture reading: addresses, ports, ARP, corrupt timestamps, out-of-order packets, sessions |
| `unit/test_raw_normalize.py` | Hex and True/False decoding; shifted (misaligned) rows are detected |
| `unit/test_timestamps.py` | CSV row ↔ packet matching: UTC+1, IP filter, order resolution, ambiguity never guessed |
| `unit/test_devices.py` | Every capture has a device; attacks map to the attacked segment; replay budget per capture |
| `unit/test_splits.py` | Time split is ordered and survives sampling; held-out device never in training; mid-term split reproduced exactly |
| `unit/test_simulator.py` | Realistic replay keeps real gaps and devices, hides dates; random replay unchanged |
| `unit/test_model_registry_paths.py` | Dataset v2 models never replace the mid-term models |
| `unit/test_multinode_client.py` | QBFT genesis; local signing with per-sender nonces; reads wait for confirmed writes on other nodes (and re-check the node after a failover); roles spread over nodes |
| `unit/test_faults.py` | Traffic routing on failure; fault schedule and repair at the end; failover to the next live node; unconfirmed transactions resent in order; node monitoring across restarts |
| `integration/test_baseline_pipeline.py` | Whole baseline: every event reaches the cloud, all layers predict, accuracy beats guessing |
| `integration/test_blockchain_pipeline.py` | Whole blockchain run (both modes): every event committed and verified, all 4 models verified on-chain, tampered events rejected; locally signed with background audit writes; the same on a 4-validator QBFT network (all nodes agree) |
| `integration/test_fault_tolerance.py` | An edge, fog or the cloud down: nothing lost and every prediction unchanged with recovery, its traffic lost without; a device that is off; another edge verifies a failed edge's devices through the ledger; a validator crash on QBFT loses nothing and the node rejoins |
| `security/test_model_integrity.py` | A modified model file is refused |
| `performance/` | Empty for now (planned) |

### 6.10 `data/` — the dataset

| Folder | Contents | In git? |
|---|---|---|
| `external/edge_iiotset/downloads/` | Files exactly as downloaded (large ones zipped) | No (~1.6 GB) |
| `external/edge_iiotset/raw/` | Extracted dataset: `Selected dataset for ML and DL/` (the two main CSVs), `Normal traffic/` (10 sensors, CSV + PCAP), `Attack traffic/` (14 attacks, CSV + PCAP), the dataset's paper and Readme | No (~10 GB) |
| `metadata/` | `checksums.sha256` (fingerprint of every file), `dataset_card.yaml` (source, license, date, row counts), `*_feature_removal.csv` (every dropped column and why) | Yes (small, important) |
| `splits/<dnn\|ml>/` | Cleaned train/validation/test Parquet files, each with a manifest | No (regenerable) |
| `prepared/<layer>/<dnn\|ml>/` | Per-layer views of the splits | No (regenerable) |

"dnn" and "ml" are the two versions of the dataset the publishers selected: **DNN** (2.2 million rows; our
main one) and **ML** (158 thousand rows; for quick checks).

### 6.11 `models/` — trained AI models

One folder per layer (`device/`, `edge/`, `fog/`, `cloud/`). For each model:
- `<layer>-<type>-<fingerprint>.joblib` is the model itself (not in git; regenerate with `train_models.py`).
- `<same name>.json` is its **provenance record**: model fingerprint, training-data fingerprint, feature
  list, settings, validation scores and training time.
- `current.json` says which model the layer currently uses.

### 6.12 `experiments/` — outputs and lineage

| Path | Contents |
|---|---|
| `manifests/dnn_preparation.json`, `ml_preparation.json` | Complete record of how the data was prepared: counts at every step, class counts per split, fingerprints of every output file |
| `results/baseline-*.json`, `blockchain_batch-*.json` | Full-scale (200k-event) run results |
| `results/presentation1/runs.jsonl` | All 24 comparison and scaling runs, one per line |
| `results/exp_integrity_accuracy.*` | Integrity-under-attack results |
| `results/exp_security.csv`, `security-*.json` | Security experiment results |
| `manifests/real_*_preparation.json`, `realistic_dataset.json`, `tshark_validation.json` | Final task 1: dataset v2 lineage and the tshark check |
| `results/realistic/` | Final task 1: test-split metrics, leave-one-device-out, integrity and security on the realistic replay |
| `results/realistic_replay-*.json` | Final task 1: 200,000-message realistic replay runs |
| `results/final_task1/runs.jsonl` | Final task 1: comparison and scaling on the realistic replay |
| `results/final_task2/` | Final task 2: every single-node and QBFT run (`runs.jsonl`) and security on QBFT |
| `results/final_faults/` | Fault-tolerance add-on: every fault run (`runs.jsonl`) and the messages each delivered, with every layer's prediction (`rows/*.parquet`) |
| `results/exp_accuracy_baseline.csv`, `exp_latency_baseline.csv` | Baseline summary tables |
| `logs/` | Console logs of the final-phase runs (`final_task1_step8.log`, `final_task2.log`, `final_faults.log`, …) |
| `configs/`, `reports/` | Empty placeholders for later phases |

### 6.13 `docs/` — documentation

| Path | Contents |
|---|---|
| `PROJECT_GUIDE.md` | This guide |
| `DATA_USAGE.md` | Exactly which data and how much was used at the mid-term, and what the final will use |
| `presentation1/README.md` | Results write-up for the first presentation, including the paper comparison and the 6-week plan |
| `presentation1/figures/` | 9 slide-ready charts |
| `presentation1/tables/` | The numbers behind each chart, as CSV |
| `final/01_real_timestamps_device_identity.md` | Final task 1: plan, implementation, results, audit |
| `final/02_multi_node_blockchain.md` | Final task 2: plan, implementation, results |
| `final/02a_fault_tolerance.md` | Add-on after task 2, fault tolerance (Experiment F): plan, implementation, results |
| `final/task1/`, `final/task2/`, `final/faults/` | Figures and tables of each final task and of the fault-tolerance add-on |

### 6.14 Folders not in git

- `tools/`: the private blockchain node and compiler (`foundry/anvil`, `foundry/forge`, `solc/solc-0.8.24`), and
  Hyperledger Besu for the multi-node network (`besu/`, installed by `scripts/setup_besu.py`; `downloads/` caches
  the verified release).
- `.venv/`: a Python environment with the blockchain libraries (web3; coincurve for fast transaction signing).
  It reuses the main Python's other libraries.
- `dashboard/`: empty; a live dashboard is planned for the final presentation.

---

## 7. Important design decisions and why

| Decision | Why |
|---|---|
| **Real dataset, not made-up data** | The course requires an IEEE DataPort dataset, and results on real attacks are more credible. Made-up data is used only to *inject attacks* in security tests, as the dataset plan allows |
| **Only fingerprints on the blockchain** | A blockchain cannot store millions of readings cheaply. A fingerprint is enough to detect any change |
| **Same code for baseline and blockchain runs** | Only one thing differs between the two, so any difference in results is caused by the blockchain |
| **Two blockchain modes (per-event and batch)** | Measures the paper's trade-off (security vs speed) at two cost points |
| **Model fingerprints checked against the blockchain, not a local file** | An attacker who can replace a model file can also edit a local record; they cannot edit the blockchain |
| **Cloud trains every layer's model** | Matches the paper (the cloud has the compute) and gives one provenance chain for all models |
| **Test data never used for training** | Otherwise accuracy would be inflated |
| **Leaky columns removed** | Otherwise the model would "cheat" (e.g. learn attacker IP addresses instead of attack behaviour) |
| **Everything seeded, fingerprinted and configured in files** | Anyone can reproduce every number exactly (ADR §19) |
| **Toolchain installed inside the project** | Nothing on the computer is changed outside this folder |
| **Local private chain (Anvil)** | Free, fast, repeatable. Public Ethereum costs money and gives unrepeatable timings (ADR rejected it) |
| **A private 4-validator QBFT network (Besu) for final task 2** | Real consensus and block time, still free and repeatable. QBFT tolerates 1 faulty validator out of 4. Besu runs the same contract bytecode, so gas is directly comparable |
| **Audit records confirmed in the background (task 2)** | No layer reads them during a run, so waiting for them only adds two blocks per micro-batch. The run still ends only after every one is confirmed |
| **A read waits until its node has every confirmed write (task 2)** | With layers on different nodes, an edge could otherwise read through a node that has not yet imported a device's commitment, and reject a genuine message |

---

## 8. Problems found along the way and how they were handled

1. **The dataset has no usable timestamps.** The date part of `frame.time` is missing ("2021 11:44:10"
   with no day or month), and each attack was recorded in its own time slot. Time-based features built
   from it would secretly reveal the answer. *Handled:* the column is dropped; time windows use the
   simulator's replay time. *Final phase:* use the PCAP captures, which have real timestamps.
2. **No device IDs, and IP addresses leak the answer.** One IP (192.168.0.170) is 100% attack traffic.
   *Handled:* IPs dropped; logical devices assigned randomly. *Final phase:* use the per-sensor raw files.
3. **Duplicates and contradictory rows.** 13.9% duplicates were removed. 2.3% of rows have identical
   features but different labels; no model can separate these, which caps accuracy. This is reported.
4. **Huge models.** Unlimited-depth Random Forests were 450–900 MB (slow to load and fingerprint). Depth
   was capped; models got smaller *and* more accurate.
5. **A library bug.** The MLP crashed in scikit-learn 1.7.2 when early stopping was on with text labels.
   Early stopping was turned off (documented in `models.yaml`).
6. **A slow fog stage.** The first version re-scanned 60 seconds of history for every event. It was
   rewritten; throughput went from 541 to 12,000 events/s.
7. **A security bug in our own edge code.** The edge updated a device's sequence counter *before* the
   blockchain checks. A forged event (rejected) could still push the counter forward and lock out all of
   the real device's later messages. *Fixed:* state updates only after all checks pass; covered by a test.
   The same weakness in the no-blockchain baseline locked out 92.5% of genuine traffic in the experiment.
8. **The local blockchain slows down as it grows.** In per-event mode every transaction becomes a block,
   and Anvil slowed ~10× after tens of thousands of blocks. *Handled:* per-event runs kept at 10,000 events;
   disclosed as a limitation.
9. **Slow network.** The dataset and toolchain downloads were ~50 KB/s single-stream. *Handled:*
   downloads split into parallel pieces.
10. **Besu refused bursts of transactions (task 2).** Per-event mode sends up to 256 transactions from one account
    per micro-batch. By default Besu refuses a transaction more than 200 nonces ahead of the sender's last
    confirmed one. *Handled:* the pool limit is raised to 10,000 (`configs/blockchain.yaml`).
11. **web3.py rejected QBFT block headers (task 2).** QBFT stores the validators and their signatures in a
    327-byte header field that web3.py rejects by default. *Handled:* the consensus check reads blocks through
    web3's proof-of-authority middleware; transactions were never affected.

---

## 9. Results so far

(Full details and charts: `docs/presentation1/README.md`.)

- **Accuracy on normal (untampered) traffic:** device 89.2%, edge 97.0%, fog 96.2%, cloud 96.3%.
  **Identical with and without blockchain**, because the blockchain doesn't change the data the AI sees.
- **Accuracy under attack:** when an attacker disguises 50% of attacks in transit, the baseline catches only
  **45.7%** of attacks, while the blockchain version catches **94.8%** (every tampered event is rejected).
  This is the measurable version of the paper's claim that blockchain improves accuracy.
- **Security:** the blockchain version stopped **8 of 8** attack types with no genuine traffic rejected.
  The baseline stopped only 2 fully (same-edge replay and a simple model swap).
- **Cost:** the blockchain makes processing slower.

  | | Time per event | Throughput | Gas per event |
  |---|---:|---:|---:|
  | Baseline | 0.083 ms | 11,357 events/s | 0 |
  | Merkle batch | 0.665 ms | 1,492 events/s | ~12,700 |
  | Per-event | 27.4 ms | 37 events/s | ~155,900 |

  This agrees with the paper: blockchain adds latency, mostly at the device and edge.
- **Scaling:** batch mode loses its advantage with many devices (batches become tiny). The fix is planned.

**Final phase results** (dataset v2; details in the task documents):
- **Final task 1, real timestamps and devices:** [final/01 §10](final/01_real_timestamps_device_identity.md#10-implementation-and-results-28-oct-2026),
  with every experiment re-run on the realistic replay in §10.10.
- **Final task 2, 4 QBFT validators at one block per second:** [final/02 §10](final/02_multi_node_blockchain.md#10-implementation-and-results-3-nov-2026).

  | Chain (Merkle batch mode, 10,000 messages) | Message latency | Throughput |
  |---|---:|---:|
  | 1 node, instant blocks | 0.10 s | 2,382 msg/s |
  | 1 node, 1 block/s | 2.75 s | 90 msg/s |
  | 4 validators (QBFT), 1 block/s | 2.75 s | 90 msg/s |

  - **Block time, not consensus, sets the latency:** consensus adds ~34 ms per confirmation.
  - **Latency is about 2.75 block periods** (1, 2 and 5 s measured).
  - **Security unchanged:** 8 of 8 attacks blocked, no genuine message rejected.
  - **Accuracy and gas identical** to the single node.
  - **Scaling to 500 devices:** throughput falls 24% on QBFT (15× on the instant-block node), but gas per message
    grows 6.2×.

---

## 10. How to run everything

```bash
# one-time setup
make setup                               # install Python libraries
make data-essential                      # download the two main CSVs (make data = everything)
# blockchain toolchain: see README.md "Blockchain setup"

# prepare and train
python scripts/prepare_dataset.py        # clean + split + layer views
python scripts/train_models.py           # cloud trains all models

# run
python scripts/run_baseline.py                                  # without blockchain
.venv/bin/python scripts/run_blockchain.py --mode batch         # with blockchain
.venv/bin/python scripts/run_security.py                        # attack experiment
scripts/run_presentation1.sh && .venv/bin/python scripts/make_figures.py   # all results + charts

# final task 1 (dataset v2) and final task 2 (4-validator QBFT network)
scripts/run_final_task1.sh                                       # or --step8-only
.venv/bin/python scripts/setup_besu.py && scripts/run_final_task2.sh
scripts/run_final_faults.sh                                      # fault-tolerance add-on (Experiment F)

# check
make test
```

---

## 11. Progress report: what is completed and what is pending

This section measures progress against the project's own plan (the ADR), so "how much is done" is
counted, not guessed. Four yardsticks are used here, and a fifth (the paper's requirements) in §14.1:
- the phases (ADR §10),
- the official acceptance checklist (ADR §21),
- the experiment matrix (ADR §11.2),
- the planned file list (ADR §4.1).

The pending work is listed after them.

### 11.1 Summary

| Yardstick | Completed | Partly done | Not started | Completion |
|---|---:|---:|---:|---:|
| Implementation phases 0–8 (§11.2) | 7 | 2 | 0 | **7 of 9 fully done** |
| Acceptance checklist, 31 items (§11.3) | 29 | 2 | 0 | **94% fully met** (29/31) |
| Experiments A–F (§11.4) | 5 | 1 | 0 | **5 of 6 fully done** |
| Planned files (§11.5) | 54 | 26 merged elsewhere | 21 | **80 of 101 covered** (79%) |
| Paper requirements RQ-01 … RQ-17 (§14.1) | 11 | 5 | 1 | **11 of 17 fully met** |
| Automated tests | 99 passing | — | — | 100% passing |

**Update, 3 Nov 2026:** final tasks 1 and 2 and the fault-tolerance add-on (Experiment F) are complete. The two
tasks remove three of the realism gaps named below:
- simulated timestamps;
- simulated device identity;
- a single blockchain node without consensus.

Still open: real network transport, containers, the dashboard and the final report.

**Overall estimate at the first presentation: about 65% of the total project effort was complete.** This is a
judgement, not a count; the paragraph below explains it as written then.
The acceptance checklist is 90% met, but it measures whether each capability *exists*. The remaining work
makes the system *realistic*: real timestamps, real network transport, a multi-node blockchain,
fault-tolerance testing, a dashboard and the final report. Those are the heavier tasks, so the overall
figure is lower than the checklist figure. Everything needed for the **first presentation is complete**.

### 11.2 Phases (ADR §10)

| Phase | What it means | Status | Evidence |
|---|---|---|---|
| 0 | Repository, configuration, tests | ✅ Done | `configs/`, `src/common/`, 99 tests, lint clean |
| 1 | Baseline four-layer pipeline, no blockchain | ✅ Done | `scripts/run_baseline.py`; 200k events at ~12,000 events/s |
| 2 | Private blockchain + smart contract | ✅ Done | `blockchain/contracts/IoTRegistry.sol`, `src/common/blockchain.py` |
| 3 | Device intelligence + commitments | ✅ Done | `src/device/` (sign + commit, per-event and Merkle batch) |
| 4 | Edge verification + provenance | ✅ Done | `src/edge/` (identity, signature, hash, replay checks) |
| 5 | Fog attack detection + audit | ✅ Done | `src/fog/` (15-class model, flood alerts, on-chain alert audit) |
| 6 | Cloud training + model registry | ✅ Done | `src/cloud/` (3 candidates, on-chain model fingerprints) |
| 7 | Full integration | 🟡 Partly | All layers work together and, since final task 2, use a 4-validator blockchain network (separate processes). The layers themselves still run **in one process**: no MQTT/REST transport, no Docker, one fog node in experiments |
| 8 | Quantitative evaluation | 🟡 Partly | Accuracy, latency (including block time and consensus, task 2), CPU/memory, gas, security, scaling and fault tolerance (Experiment F) done; **dashboard missing** |

### 11.3 Acceptance checklist (ADR §21)

The ADR says the project is complete only when all 31 items are met.

| Group | Item | Status | Notes |
|---|---|---|---|
| Architecture | Four intelligence layers exist | ✅ | `src/device`, `edge`, `fog`, `cloud` |
| | Each layer performs an AI/ML task | ✅ | decision tree / RF binary / RF 15-class / best-of-3 |
| | Each layer participates in blockchain operations | ✅ | commit / verify + record / alert audit / model registry |
| | Device → Edge → Fog → Cloud flow works | ✅ | integration tests pass |
| | Runs from a fresh environment | 🟡 | Documented in README, but never tested on a clean machine; no Docker |
| Blockchain | Devices can register | ✅ | `registerDevice` |
| | Telemetry commitments recorded | ✅ | `commitData` / `commitBatch` |
| | Hash verification works | ✅ | edge compares against on-chain fingerprint |
| | Tampering detected | ✅ | 100% in security experiment |
| | Replay protection works | ✅ | 100% same-edge and cross-edge |
| | Model hashes registered | ✅ | all 4 models registered and verified per run |
| | Audit records queryable | ✅ | contract storage + event logs (no viewer UI yet) |
| AI | Device inference works | ✅ | |
| | Edge preprocessing/feature extraction works | 🟡 | Preprocessing (scaling/encoding) done; **rolling-window feature extraction (ADR §7.2) not done** |
| | Fog attack detection works | ✅ | |
| | Cloud model training works | ✅ | |
| | Model metadata versioned | ✅ | `models/<layer>/*.json` provenance records |
| Evaluation | Baseline experiment exists | ✅ | |
| | Blockchain-enabled experiment exists | ✅ | two modes |
| | Accuracy reported | ✅ | |
| | Latency reported | ✅ | |
| | CPU/memory reported | ✅ | |
| | Security test results reported | ✅ | 8 attack types |
| | Scaling experiments reported | ✅ | 10–500 devices |
| | Energy measured or transparent proxy | ✅ | CPU-time proxy, labelled as such |
| Reproducibility | Configuration version controlled | ✅ | Committed in `b3fb693`; later changes still to be committed |
| | Dataset hashes recorded | ✅ | `data/metadata/checksums.sha256` |
| | Random seeds recorded | ✅ | in every result file |
| | One-command experiment execution | ✅ | `scripts/run_presentation1.sh` |
| | Results exported to CSV/JSON | ✅ | `experiments/results/` |
| | Comparison with paper-reported values | ✅ | `docs/presentation1/README.md` §4 (preliminary) |

**Totals:** 29 ✅, 2 🟡, 0 ❌.

### 11.4 Experiment matrix (ADR §11.2)

| Experiment | What it asks | Status | Notes |
|---|---|---|---|
| A — Accuracy | With vs without blockchain | ✅ | 3 seeds; plus the integrity-under-attack experiment |
| B — Latency | Per layer, with vs without | ✅ | per layer and end-to-end |
| C — Resource overhead | CPU, memory, transactions, gas | ✅ | |
| D — Security | tamper, replay, spoofing, duplicate, invalid signature | ✅ | 8 attack types (more than the ADR lists) |
| E — Scalability | 10 → 1,000 devices; also edge/fog node counts | 🟡 | done for 10–500 devices, on one node and on the 4-validator network (task 2); **1,000 devices and varying edge/fog node counts not run** |
| F — Fault tolerance | switch off a device, edge, fog, cloud or chain node | ✅ | all five, plus 1 and 2 of 4 validators; event loss, recovery time, continuity (`final/02a_fault_tolerance.md`) |

### 11.5 Planned files (ADR §4.1 and §2A) vs what exists

Some planned files were deliberately **merged** into another file because they would have held only a few
lines. The job they describe is done; it just lives elsewhere. They count as covered.

| Planned file | Status | Where the job is done |
|---|---|---|
| `README.md`, `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore`, `Makefile` | ✅ | — |
| `LICENSE` | ❌ | — |
| `docker-compose.yml` | ❌ | — (Phase 7) |
| `configs/base, blockchain, datasets, models, experiments.yaml` | ✅ | — |
| `blockchain/contracts/IoTRegistry.sol`, `artifacts/` | ✅ | — |
| `blockchain/scripts/deploy.py` | 🔀 merged | `attach_blockchain()` in `src/pipeline.py` deploys per run |
| `blockchain/tests/test_registry.py` | 🔀 merged | contract tested through `tests/integration/test_blockchain_pipeline.py` and `run_security.py` |
| `src/common/config, schemas, crypto, blockchain, storage, logging, metrics.py` | ✅ | (+ `merkle.py`, not in the plan) |
| `src/device/simulator, collector, blockchain_client, service.py` | ✅ | — |
| `src/device/local_model.py` | 🔀 merged | `src/device/service.py` |
| `src/edge/ingest, preprocessing, blockchain_client, service.py` | ✅ | — |
| `src/edge/local_model.py` | 🔀 merged | `src/edge/service.py` |
| `src/edge/feature_extraction.py` | ❌ | rolling-window features not built |
| `src/fog/traffic_analysis, blockchain_client, service.py` | ✅ | — |
| `src/fog/aggregation.py`, `attack_detection.py` | 🔀 merged | `src/fog/service.py` |
| `src/fog/intermediate_state.py` | ❌ | fog-to-cloud intermediate parameters not built |
| `src/cloud/train, evaluate, model_registry, blockchain_client, service.py` | ✅ | — |
| `src/cloud/ingestion.py`, `analytics.py` | 🔀 merged | `src/cloud/service.py` |
| `src/cloud/dataset_builder.py` | 🔀 merged | `scripts/prepare_dataset.py` + `src/cloud/train.py` |
| `src/data/ingestion, validation, clean, feature_groups, splits` | ✅ | — |
| `src/data/preparation/build_views.py` | 🔀 merged | `scripts/prepare_dataset.py` |
| `data/metadata/dataset_card.yaml`, `checksums.sha256` | ✅ | — |
| `data/metadata/schema.json` | 🔀 merged | column list in `src/data/validation/schema.py` |
| `scripts/run_baseline.py`, `run_blockchain.py` | ✅ | — |
| `scripts/generate_data.py` | 🔀 replaced | real data: `download_edge_iiotset.py` + `prepare_dataset.py` + device simulator |
| `scripts/seed_network.py` | 🔀 merged | `attach_blockchain()` in `src/pipeline.py` |
| `scripts/run_pipeline.py` | 🔀 merged | `src/pipeline.py`, called by the run scripts |
| `scripts/benchmark.py`, `collect_metrics.py` | 🔀 merged | `scripts/run_experiments.py` + `src/common/metrics.py` |
| `scripts/reproduce_results.py` | 🔀 merged | `scripts/run_presentation1.sh` |
| `tests/unit`, `integration`, `security` | ✅ | 99 tests |
| `tests/performance/` | ❌ | empty |
| `dashboard/app.py`, `data_loader.py` | ❌ | not started |
| `notebooks/01…05_*.ipynb` (5) | ❌ | not started |
| `experiments/manifests/` | ✅ | — |
| `experiments/configs/baseline, blockchain, scaling, security, ai_blockchain.yaml` (5) | 🔀 merged | one file: `configs/experiments.yaml` |
| `experiments/reports/paper_comparison.csv` | ❌ | the comparison exists only as a Markdown table |
| `docs/BlockIoTIntelligence_ADR_Implementation.md` | ✅ | kept at the repository root |
| `docs/reports/results.md`, `limitations.md`, `paper_comparison.md`, `docs/experiments/paper_comparison.md` (4) | 🔀 merged | `docs/presentation1/README.md` (§3–§5) and this guide (§11.7) |
| `docs/architecture/context.md`, `ai_driven_blockchain.md`, `blockchain_driven_ai.md`; `docs/experiments/protocol.md`; `docs/requirements/paper_requirements.md`; `docs/reports/methodology.md`, `security_analysis.md`, `conclusion.md` (8) | ❌ | final-report documents, not written yet |

Counting every individual planned file gives 101 in total:
- **54 exist.**
- **26 are merged** into other files, so their job is done.
- **21 are missing:** `LICENSE`, `docker-compose.yml`, `feature_extraction.py`, `intermediate_state.py`, the
  performance tests, 2 dashboard files, 5 notebooks, 8 report and architecture documents, and
  `paper_comparison.csv`.

The 54 existing and 26 merged files give 80 of 101 (79%) covered. The missing files are mostly Phase 7–8 and
final-report items.

### 11.6 Pending work, in priority order

**A. Short, housekeeping (hours):**

| # | Item | Why it matters |
|---|---|---|
| 1 | ~~Commit the work to git~~ | Done (commit `b3fb693`); later work still to be committed |
| 2 | Fix the ADR's inconsistencies | Stale synthetic-sensor sections, undefined "Phase 9", leftover `citeturn` markers, wrong PDF names, broken links in `understanding_1.md` |
| 3 | Add a `LICENSE` | Planned in the ADR |
| 4 | Test a fresh-machine setup | Checklist item "runs from a fresh environment" |

**B. Final phase: three main tasks and two add-ons, in the agreed order:**

| Order | Item | Status | Fixes |
|---|---|---|---|
| Task 1 | Real timestamps and device identity: features from the 24 PCAP captures; each real sensor replayed as its own device; held-out-device test; every experiment re-run | ✅ Done (28 Oct; step 8 on 3 Nov 2026) | The two biggest data limitations (simulated time and identity) |
| Add-on after task 1 | Time-window features: edge rolling windows (`feature_extraction.py`) and fog windows on real time; retrain and compare | Pending | 🟡 "Edge feature extraction" checklist item, RQ-05 |
| Task 2 | Multi-node blockchain: 4 Besu validators, QBFT consensus, 1 block/s, layers on different nodes; latency including block time | ✅ Done (3 Nov 2026) | Single node without consensus; RQ-10 (ledger part) |
| Add-on after task 2 | Fault tolerance: a device, edge, fog, the cloud, 1 and 2 of 4 validators fail and recover; failover, store and forward, client failover with resending | ✅ Done (3 Nov 2026) | Experiment F; ADR §14.2 "retry + local queue + eventual commit" |
| Task 3 | AI-driven blockchain (RQ-11): a model forecasts each gateway's traffic and picks the Merkle batch size, compared with fixed batching | **Next** | RQ-11; the scaling drop, which on the QBFT network is mainly gas (6.2× at 500 devices) |

**Still planned after the three tasks:**
- MQTT and REST between layers, Docker Compose (Phase 7);
- batched alert audit, 1,000 devices, other edge/fog counts (Experiment E);
- a second IEEE DataPort dataset (X-IIoTID or ToN_IoT, if approved) and the Streamlit dashboard;
- a full reproduction run, the final report and slides.

**C. Paper requirement not yet met:** **RQ-11 "AI-driven blockchain"** (see §14). The paper expects AI to
*improve the blockchain*, not only the reverse. This is task 3: a small model that forecasts each gateway's
traffic and picks the Merkle batch size / commit interval, compared with fixed batching. It is measured on the
4-validator network, where gas per message and message latency are the two objectives (task 2 §10.7).

**D. Optional, if time allows:** the five analysis notebooks, performance tests, and fog→cloud intermediate
parameters (`intermediate_state.py`).

### 11.7 Known limitations of the current results

These are not bugs but boundaries that must be stated whenever the results are shown:

- Everything runs on one laptop, and the four layers run in one process:
  - the mid-term and task 1 results use a local blockchain that mines instantly, so their latencies exclude block
    time and consensus;
  - task 2 runs 4 QBFT validators with one block per second, so its latencies include both;
  - none of the results include network transfer between layers or WAN delay between validators.
- Device identity and event timing are simulated in the mid-term results, because the dataset's selected CSVs
  contain neither. Dataset v2 (final task 1) uses the real values.
- In the mid-term data, every DDoS_UDP and MITM row (and some Normal DNS rows) has shifted columns, a fault in the
  publisher's CSVs; and the Normal class is ~99.8% one sensor. Dataset v2 corrects both.
- Per-event blockchain runs are limited to 10,000 events because the instant-mining Anvil node slows as blocks
  accumulate. On the QBFT network, per-event transactions share blocks (about 165 blocks instead of 20,117 for
  10,000 messages), so that cause does not apply there. Longer per-event runs on QBFT were not tested.
- Energy is a CPU-time proxy, not a power measurement.
- Fault-tolerance results cover crashes and unreachable components (one seed, one 30 s fault). They do not cover
  Byzantine validators, network partitions or slow links. Fog failover loses the fog's traffic windows, and in the
  run with fog failover that lost every flood alert.
- The paper's numbers come from other studies on different tasks, so the comparison is a reference, not a like-for-like test.

---

## 12. The complete project outcome

### 12.1 What the finished project delivers

When all phases are complete (final presentation, ~6 weeks), the project delivers six things.

1. **A working, reproducible implementation of BlockIoTIntelligence.** Four cooperating AI layers, each on
   its own container, talking over real IoT and service protocols (MQTT, REST), connected by a
   multi-node private Ethereum blockchain. It runs on real IoT/IIoT traffic from IEEE DataPort.
2. **A controlled, measured answer to the paper's claims.** The paper argues from other people's numbers;
   this project measures one system with and without blockchain, holding everything else fixed.
3. **An evaluation covering all six ADR experiments:** accuracy, latency, resource cost, security,
   scalability and fault tolerance.
4. **A security analysis:** which attacks the blockchain stops, which it doesn't, and at what cost.
5. **A research report and slides.** Report structure from ADR §20: Introduction, Background, Reference
   architecture, Implementation, Blockchain design, AI design, Methodology, Results, Security analysis,
   Scalability analysis, Comparison with the paper, Limitations, Future work, Conclusion.
6. **A reproducibility package:** pinned versions, configuration files, dataset fingerprints, seeds, and
   one command that regenerates every number and chart.

### 12.2 Research contributions (ADR §27) and where each stands

| Contribution | Meaning | Status |
|---|---|---|
| A — Architectural implementation | An executable four-layer architecture exists | ✅ done (layers in one process; blockchain on 4 validator processes since task 2); 🔜 containers + real transport |
| B — AI + blockchain convergence | AI and blockchain act on the *same* data, model and provenance pipeline, not as two separate demos | ✅ done: fingerprinted events feed the models; models are registered and verified on-chain |
| C — Measured trade-offs | Benefits and costs both quantified | ✅ done for accuracy, latency, CPU, gas, and block-time and consensus latency (task 2); 🔜 energy on hardware |
| D — Security evidence | Tampering, replay, spoofing and model replacement produce measurable rejections | ✅ done (8 attack types) |
| E — Reproducibility | Another student can regenerate everything | 🟡 scripts and fingerprints done; git commit and fresh-machine test pending |

### 12.3 The main findings so far (the "story" of the project)

1. **Blockchain does not change accuracy on clean data.** Every layer scores exactly the same with and
   without it, because the ledger never alters what the models see.
2. **Blockchain protects accuracy when data is attacked.** If an attacker disguises attacks in transit, the
   ordinary system goes blind (45.7% of attacks caught at 50% tampering); the blockchain system catches
   94.8%, because altered data no longer matches its on-chain fingerprint. *This refines the paper's claim:
   the gain is in integrity, and it shows up as accuracy under attack.*
3. **Security coverage is broad:** 8 of 8 attack types stopped, 0 genuine events rejected.
4. **The price is speed and computation.** Committing every event costs about 330× the processing time;
   batching events under one Merkle fingerprint brings that down to about 8×. The paper's
   "blockchain adds latency" is confirmed and quantified per layer.
5. **Design matters as much as the technology.** Batching per device stops helping with many devices; the
   fog alert audit becomes the largest cost once batching is used. These point to concrete design fixes.
6. **On a real validator network, block time, not consensus, sets the latency** (final task 2). With 4 QBFT
   validators and one block per second:
   - a message takes 2.75 s, the same as on one node with the same block time;
   - consensus adds ~34 ms per confirmation;
   - every write the next layer must read costs about one block.

   Merkle batching keeps its 10× gas saving, but its speed advantage shrinks from 62× to 1.4×.
7. **The system survives failures it is designed for, and pays in time, not data** (fault-tolerance add-on).
   - **With failover and store and forward,** no message is lost when an edge, a fog, the cloud or a validator
     fails.
   - **Without them,** a 30 s outage loses 19–26% of the run's messages, including attack traffic.
   - **QBFT behaves exactly as Byzantine fault tolerance promises:** 1 of 4 validators down, the chain continues at
     40% speed; 2 of 4, it halts without forking.
   - **But recovering from a lost quorum took 64.8 s** after the quorum returned, twice the outage itself.

### 12.4 What the final results are expected to add

- ✅ *Done in task 2:* latency **including** block time and consensus. At 1 block/s it is 2.75 s per message,
  far above the instant-mining numbers. 🔜 Network transfer between layers is still to be added.
- ✅ *Done in the fault-tolerance add-on:* behaviour when a node fails (Experiment F). 🔜 1,000 devices.
- ✅ *Done in task 1:* accuracy with **real device identity and real timing** from the PCAP captures,
  including a test on devices the model never saw during training (generalisation).
- An AI-driven blockchain optimisation (RQ-11) with its measured gas/latency saving.
- Results on a second dataset, if the instructor approves.

---

## 13. Architecture in depth

The simple picture in section 3 shows *what* the layers do. This section shows *how* the system is built.

### 13.1 Four views of the architecture

| View | Question it answers | Section |
|---|---|---|
| Logical | Which layers exist and what does each do? | 3 |
| Software | How is the code organised and what depends on what? | 13.2 |
| Runtime | What actually runs, today and in the final version? | 13.3, 13.4 |
| Data and ledger | What data exists, and what is written on the blockchain? | 13.5, 13.6 |
| Security | Who might attack, and what stops them? | 13.7 |
| AI | Which models, trained how, deployed how? | 13.8 |

### 13.2 Software architecture (code structure and dependencies)

```
                         scripts/  (command-line entry points)
    download · prepare · train · run_baseline · run_blockchain · run_experiments · run_security · make_figures
                                        │ call
                                        ▼
                               src/pipeline.py  (orchestrator)
             builds layers ─ attaches blockchain clients ─ streams events ─ collects metrics
                  │                │                 │                │
                  ▼                ▼                 ▼                ▼
            src/device/       src/edge/          src/fog/         src/cloud/
            service           service            service          service · train · evaluate
            simulator         ingest             traffic_analysis model_registry
            collector         preprocessing
            blockchain_client blockchain_client  blockchain_client blockchain_client
                  │                │                 │                │
                  └────────────────┴───────┬─────────┴────────────────┘
                                           ▼
                                   src/common/   (shared, layer-independent)
             config · schemas · crypto · merkle · blockchain · metrics · storage · logging
                                           │
                        ┌──────────────────┴───────────────────┐
                        ▼                                      ▼
            blockchain/ IoTRegistry.sol                 src/data/  (dataset pipeline)
            (compiled ABI + bytecode)          ingestion · validation · clean · splits · feature_groups
```

**Rules that keep this clean:**
- `src/common/` never imports a layer.
- A layer's `service.py` never talks to the blockchain directly; it calls its optional `ledger`
  (the layer's `blockchain_client.py`). With no ledger, you get the baseline.
- Settings come from `configs/`, never from numbers written in the code.
- Every layer loads its AI model through `cloud/model_registry.py`, which checks the model's fingerprint.

### 13.3 Runtime architecture today (first presentation and final tasks 1–2)

```
 ┌──────────────────────────── one Python process ────────────────────────────┐
 │  DeviceSimulator → DeviceLayer → [interceptor] → EdgeNode ×2 → FogNode → CloudNode │
 │        micro-batches of 256 events, routed to an edge by device ID            │
 └───────────────────────────────┬────────────────────────────────────────────┘
                                 │ JSON-RPC over HTTP (web3.py)
                                 ▼
                ┌───────────────────────────────────┐
                │ Anvil: private Ethereum node,     │  started fresh for every run,
                │ instant mining, 20 dev accounts   │  contract deployed, then stopped
                └───────────────────────────────────┘
```

- Each node has **its own blockchain account**, and the contract only accepts writes from authorized
  accounts:
  - account 0 is the owner/administrator,
  - then the device gateway,
  - then one account per edge node, per fog node and for the cloud.
- The *interceptor* is a test hook where experiments play the attacker between device and edge.
- The same process runs the baseline by simply not starting Anvil and not attaching the ledger.

**Final task 2: the same process on a 4-validator network** (`run(chain_backend="qbft")`):

```
 ┌───────────────────────────── one Python process ─────────────────────────────┐
 │ device gateway        edge-00          edge-01          fog-00      cloud    │
 └──────┬──────────────────┬────────────────┬────────────────┬──────────┬───────┘
        │ JSON-RPC         │                │                │          │
        ▼                  ▼                ▼                ▼          │
 ┌────────────┐     ┌────────────┐   ┌────────────┐   ┌────────────┐    │
 │ Besu node 0│◄───►│ Besu node 1│◄─►│ Besu node 2│◄─►│ Besu node 3│    │
 │ validator  │     │ validator  │   │ validator  │   │ validator  │    │
 └────────────┘     └────────────┘   └────────────┘   └────────────┘    │
        ▲            QBFT consensus, 1 block/s, final when 3 of 4 agree │
        └────────────────────────────── cloud ──────────────────────────┘
```

- A fresh network for every run: keys and genesis come from Besu's generator, and the network is stopped and
  deleted afterwards.
- The client signs transactions itself with the same dev accounts as Anvil.
- A read waits until its node has every write already confirmed (read-your-writes across nodes).
- Fog and cloud audit records are confirmed in the background.
- At the end of a run, every node must hold the same block at the highest common height.

### 13.4 Target runtime architecture (final presentation)

```
 [device containers ×N] ──MQTT──► [Mosquitto broker] ──► [edge containers ×E]
                                                              │ REST
                                                              ▼
                                                        [fog containers ×F]
                                                              │ REST
                                                              ▼
                                                       [cloud container]
        every container ──JSON-RPC──► [private chain: several validator nodes, block time > 0]
        off-chain data ──► Parquet files / object storage          dashboard ──► reads results + chain
```

This is ADR Phase 7. It adds the costs today's numbers leave out:
- network transfer between layers,
- broker queuing,
- block production time (✅ measured in final task 2),
- consensus between several blockchain nodes (✅ measured in final task 2).

### 13.5 On-chain design: the `IoTRegistry` smart contract

**What the contract stores:**

| Storage | Key → value | Written by |
|---|---|---|
| `authorized` | account → true/false | owner |
| `devices` | device ID → public-key fingerprint, registration time, active flag | owner |
| `commitments` | event ID or batch ID → device ID, data fingerprint (or Merkle root), time, count, layer | device gateway |
| `processed` | event/batch ID → processing fingerprint | edge |
| `alerts` | alert ID → alert fingerprint | fog |
| `models` | model ID → model fingerprint, registration time, layer, description | cloud |

**Functions and their measured cost** (gas per call, from the 200k-event run):

| Function | Purpose | Gas per call |
|---|---|---:|
| (deploy) | Create the contract | 1,219,911 (once) |
| `authorize` | Allow a node account to write | ~44,250 |
| `registerDevice` | Record a device and its key fingerprint | ~70,360 |
| `commitData` / `commitBatch` | Record one event fingerprint / one Merkle root | ~97,200 |
| `recordProcessing` | Edge records that it processed an event/batch | ~51,900 |
| `recordAlerts` | Fog records up to 150 alert fingerprints | ~1,699,000 (≈11,300 per alert) |
| `registerModel` | Cloud records a model fingerprint | ~112,600 |
| `recordInference` | Cloud records a fingerprint of a batch of predictions | ~27,600 |

The contract also exposes `revokeDevice` and single-alert `recordAlert`. Every write also emits an **event
log** (e.g. `DataCommitted`, `AlertRecorded`), which is how audit records are queried later.

**Rules the contract enforces:**
- only the owner registers devices and authorizes nodes,
- only authorized accounts write,
- data from unknown or revoked devices is refused,
- the same event or batch ID cannot be committed twice (a built-in replay block),
- the same item cannot be marked "processed" twice.

### 13.6 Data model

**Off-chain dataset files:** raw CSV → cleaned and split Parquet files → per-layer views (section 6.10).
Each file has a manifest with its fingerprint.

**A telemetry event** (defined in `src/common/schemas.py`):

| Field | Meaning |
|---|---|
| `event_id`, `trace_id` | Unique ID of the event; trace ID follows it through all layers |
| `device_id` | Which logical device produced it |
| `timestamp`, `sequence_number` | Replay time; per-device counter (increases by 1 each event) |
| `values` | The 42 network features from the dataset row |
| `source_file`, `source_row_id`, `source_dataset` | Exactly which dataset row this came from (provenance) |
| `payload_hash` | SHA-256 fingerprint of `event_id, device_id, timestamp, sequence_number, values` |
| `signature`, `public_key` | Device's Ed25519 signature over the fingerprint, and its public key |
| `batch_id`, `merkle_proof` | Batch mode only: which batch, and the proof that the event belongs to it |
| `attack_label`, `attack_type` | The true answer. Carried **only for scoring**; no layer uses it to decide |

As an event passes through, layers add `device_inference`, `edge_id`, `edge_inference`, `fog_inference`
and `traffic` (window statistics). Other formats in `schemas.py`: `AttackAlert`, `ModelMetadata`,
`BlockchainReceipt`, `DataCommitment`, `FeatureRecord`, `InferenceResult`, `ExperimentMetric`.

### 13.7 Security architecture: threat model and controls

Threat actors are from ADR §14.1; the controls are what this project implements.

| Threat | Example | Control in this project | Tested? |
|---|---|---|---|
| T1 Malicious IoT device | Unregistered device sends data | On-chain device registry | ✅ 100% blocked |
| T2 Compromised edge node | Edge alters data before passing it on | Edge's processing fingerprint recorded on-chain; downstream re-verification | 🟡 recorded, not yet re-verified at fog |
| T3 Malicious insider | Replaces an AI model and edits its local record | On-chain model registry, checked before use | ✅ 100% blocked |
| T4 Network attacker (man-in-the-middle) | Changes values in transit; disguises attacks | Fingerprint on-chain + device signature | ✅ 100% of tampered events blocked |
| T5 Replay attacker | Resends an old genuine message, possibly to another edge | Sequence numbers + on-chain "processed" state + no double commitment | ✅ 100% blocked |
| T6 Data-tampering attacker | Impersonates a device with their own key | Registered public-key fingerprint | ✅ 100% blocked |
| T7 Unauthorized data consumer / writer | Writes forged records to the ledger | Contract access control (`authorize`) | ✅ write blocked; 🔜 read-access policy not built |

**Not covered (stated honestly):**
- a device whose *private key* is stolen can still send validly signed but false data. This needs anomaly
  detection or key revocation (`revokeDevice` exists but is not exercised);
- denial-of-service against the blockchain node itself. A node that *crashes* is covered: the client fails over
  to another node and resends what was unconfirmed (ADR §14.2, fault-tolerance add-on). A flood of requests was not
  tested;
- privacy of the data (nothing is encrypted; the paper's privacy measure is not reproduced).

### 13.8 AI architecture

| Layer | Model | Task | Input features | Why this choice |
|---|---|---|---|---|
| Device | Decision tree (depth ≤ 8) | attack vs normal | 13 simple header fields | Tiny and fast, fits a constrained device |
| Edge | Random Forest (50 trees, depth ≤ 16) | attack vs normal | all 42 | Fast, accurate first filter |
| Fog | Random Forest (100 trees, depth ≤ 20) | which of 15 classes | all 42 | Rapid attack identification (paper's fog role) |
| Cloud | Best of Random Forest (200 trees), Gradient Boosting, small neural network | 15 classes | all 42 | Heavy analytics and model selection (paper's cloud role) |

**Model lifecycle:**

```
 train split (300k-row stratified sample)
        │ cloud trains each layer's model
        ▼
 scored on validation split ──► best cloud candidate chosen by macro-F1
        │
        ▼
 saved to models/<layer>/ + provenance record (model fingerprint, training-data fingerprint, feature list)
        │  blockchain runs: fingerprint registered on-chain
        ▼
 each layer loads its model ──► fingerprint checked (local, and on-chain in blockchain runs)
        │
        ▼
 predictions on the held-out test stream ──► accuracy per layer
```

Scaling and category encoding are learned from the training split only and saved *inside* each model, so
every layer applies exactly the transformation its model was trained with.

---

## 14. How the project maps to the paper

### 14.1 Paper requirements traceability (ADR §2.1, RQ-01 … RQ-17)

| ID | Requirement from the paper | Status | Where |
|---|---|---|---|
| RQ-01 | Four intelligence layers | ✅ | `src/device`, `edge`, `fog`, `cloud` |
| RQ-02 | AI at every layer | ✅ | §13.8 |
| RQ-03 | Blockchain at every layer | ✅ | the four `blockchain_client.py` files |
| RQ-04 | Device layer collects IoT data | ✅ | real Edge-IIoTset traffic replayed by `simulator.py` |
| RQ-05 | Edge: processing, feature extraction, scaling | 🟡 | scaling/encoding done; rolling feature extraction pending |
| RQ-06 | Fog: fast analysis and decisions on edge data | ✅ | `fog/service.py`, 15-class detection + alerts |
| RQ-07 | Cloud: large-scale analytics | ✅ | `cloud/train.py`, model selection |
| RQ-08 | Digital identity, hashing, authentication, verification | ✅ | `crypto.py`, device registry, edge checks |
| RQ-09 | Smart contracts | ✅ | `IoTRegistry.sol` |
| RQ-10 | Decentralised / distributed operation | 🟡 | ledger decentralised since final task 2: 4 QBFT validators, layers on different nodes, all nodes verified to hold the same chain. The layers themselves still run in one process (MQTT/REST and containers pending) |
| RQ-11 | **AI-driven blockchain** (AI improves the blockchain) | ❌ | not yet: Merkle batching reduces cost but is not AI. Final task 3 (see 11.6 C) |
| RQ-12 | **Blockchain-driven AI** (blockchain improves AI trust) | ✅ | model registry, data provenance, alert audit, integrity-under-attack experiment |
| RQ-13 | Accuracy and latency measured | ✅ | §9 |
| RQ-14 | Security and privacy measured | 🟡 | security measured (8 attacks); privacy not measured |
| RQ-15 | Computational complexity / resources | ✅ | CPU, memory, gas, transactions |
| RQ-16 | Energy efficiency discussed | 🟡 | CPU-time proxy only |
| RQ-17 | Limitations and research challenges analysed | 🟡 | limitations written (§11.7); the paper's Table 4 challenges not yet discussed |

**Totals:** 11 ✅, 5 🟡, 1 ❌.

### 14.2 The paper's two convergence ideas

- **Blockchain-driven AI** (paper §4.1.2: explainable AI, data sharing, trust, security): *implemented.*
  Every prediction can be traced back to a specific registered model and to device-committed input data.
  A swapped model is refused, and tampered input is rejected before it reaches the AI.
- **AI-driven blockchain** (paper §4.1.1: AI addressing blockchain energy, scalability, efficiency):
  *not yet implemented.* The plan is an AI model that predicts traffic load and chooses how many events
  to batch per blockchain transaction, reducing gas and latency. We will measure that saving.

### 14.3 The paper's figures and our equivalents

| Paper | Our equivalent |
|---|---|
| Fig. 3: four-intelligence architecture | Implemented system (§3, §13) |
| Fig. 4: six IoT platform layers | Mapped in §3 |
| Fig. 7(a): accuracy with/without blockchain | `figures/01_accuracy_per_layer.png` (clean) and `03_integrity_attack_detection.png` (under attack) |
| Fig. 7(b): latency with/without blockchain | `figures/02_latency_per_layer.png` |
| Table 3: accuracy, latency, security (SI), CPU/memory, energy | `docs/presentation1/README.md` §4; security as detection rates; energy as CPU proxy |
| Fig. 8: architectural analysis (accuracy, latency, security, centralisation) | Pending: planned as a final-report summary chart |
| Table 4: research challenges and solutions | Pending: discussion for the final report |

---

## 15. Experiment methodology and metric definitions

### 15.1 Fairness rules (ADR §11.1)

Baseline and blockchain runs use the **same**:
- data rows,
- random seed,
- trained models,
- topology (devices, edges, fogs),
- batch size,
- machine.

Only the blockchain is switched on or off. All scores use the **test split**, which no model saw during
training or model selection.

### 15.2 Metrics

| Metric | Definition |
|---|---|
| Accuracy | correct predictions ÷ all predictions |
| Macro-F1 | average of per-class F1; rare attack types count equally |
| Attack detection rate (integrity experiment) | attack events that were rejected for integrity **or** classified as attack ÷ all attack events |
| Detection rate (security) | injected malicious items rejected ÷ injected malicious items |
| False-reject rate | genuine events wrongly rejected ÷ genuine events |
| Latency per layer | wall-clock time spent in that layer ÷ events processed (amortised over micro-batches of 256) |
| End-to-end latency | time from a batch's creation to the cloud finishing it, per event |
| Throughput | events fully processed ÷ total run time |
| Message latency (final task 2) | time from a micro-batch entering the device layer to its cloud result; mean and 95th percentile over micro-batches, in seconds |
| Transaction latency | time from submitting a blockchain transaction to receiving its receipt (on QBFT: once the block is final) |
| Consensus check (final task 2) | every validator holds the same block hash at the highest common height at the end of a run |
| Event loss (fault add-on) | messages the devices sent − messages delivered to the cloud − messages rejected at an edge; a device that is off sends nothing, and its readings are counted as unsent, not lost |
| Pipeline continuity (fault add-on) | messages reaching the cloud over time; the longest interval without a delivery |
| Recovery time (fault add-on) | from the repair until every message generated before it has reached the cloud (no fault: 1.9 s, the micro-batch in flight) |
| CPU per event | CPU time of the pipeline process (plus the blockchain node) ÷ events |
| Gas per event | total gas of all data-path transactions ÷ events (setup excluded) |
| Energy (proxy) | CPU time. Clearly labelled as a proxy, not measured watts |

### 15.3 Experiment designs

| Experiment | Design |
|---|---|
| Comparison | 3 modes × 3 seeds × 10,000 test events; 10 devices, 2 edges, 1 fog |
| Full scale | 200,000 test events; baseline and batch mode |
| Integrity under attack | 10,000 events; 0/10/25/50% of attack events have their features replaced with a normal event's features in transit |
| Security | 3,000 events per pass; each attack type injected at 5% in its own pass on a fresh chain; plus model-tamper and unauthorized-write tests |
| Scaling | 5,000 events per point; 10, 50, 100, 250, 500 devices; all three modes |
| Final task 2: chain comparison | 10,000 realistic-replay messages; 1 node instant / 1 node 1 block/s / 4 QBFT validators 1 block/s × per-event, batch × 3 seeds; same client in all |
| Final task 2: other groups | every write awaited (QBFT, 1 seed); block period 2 s and 5 s (batch); scaling 10–500 devices on QBFT (5,000 messages); security on a fresh QBFT network per attack pass |
| Fault tolerance (add-on) | 10,000 realistic-replay messages on 4 QBFT validators; 2 edges, 2 fogs; each fault 30–60 s: device, edge-00, fog-00, cloud (with and without recovery), validator 1, validators 2 and 3; batch mode, plus per-event for the validator faults; 1 seed |

---

## 16. Technology stack and environment

| Area | Tool (version) | Used for |
|---|---|---|
| Language | Python 3.13.9 (Anaconda) | all system code |
| Data | pandas 2.3.3, NumPy 2.3.5, PyArrow 21.0.0 | data handling, Parquet files |
| Machine learning | scikit-learn 1.7.2 | all models, preprocessing, metrics |
| Data validation | pydantic 2.12.4 | message formats |
| Cryptography | cryptography 46.0.3 | Ed25519 signatures; SHA-256 via Python `hashlib` |
| Blockchain node | Foundry Anvil 1.5.1 | private Ethereum chain (single node) |
| Blockchain network | Hyperledger Besu 26.10.0 on Java 25.0.1 | 4 QBFT validators (final task 2) |
| Transaction signing | eth-account with coincurve 21.0.0 (native secp256k1) | client-side signing for Besu, 0.155 ms per transaction |
| Packet features | tshark 4.6.9 | re-extracting features from the PCAP captures (final task 1) |
| Smart contract | Solidity 0.8.24, compiled with Foundry forge 1.5.1 | `IoTRegistry.sol` |
| Blockchain client | web3.py 7.16.0 (in `.venv/`) | talking to the chain from Python |
| Resource measurement | psutil | CPU and memory |
| Charts | matplotlib 3.10.6 | presentation figures |
| Testing and style | pytest 8.4.2, ruff 0.12.0 | 80 tests, lint |
| Configuration | PyYAML 6.0.3 | `configs/*.yaml` |
| Machine used | Apple M4, 10 cores, 16 GB RAM, macOS | all reported numbers |

Planned additions for the final: Eclipse Mosquitto (MQTT), FastAPI (REST), Docker Compose, Streamlit
(dashboard).

---

## 17. Questions to expect in the presentation

**Did you just re-implement the paper?**
No. The paper has no implementation; its numbers come from other studies. We built the architecture it
describes and measured it under controlled conditions.

**Why does blockchain not improve accuracy in your results, when the paper says it does?**
On clean data the blockchain doesn't change the data the model sees, so accuracy is identical. The benefit
appears when data is attacked: with 50% of attacks disguised, accuracy drops to 45.7% without blockchain but
stays at 94.8% with it.

**Why not store the data on the blockchain?**
Far too slow and expensive for millions of readings. A 32-byte fingerprint on-chain is enough to detect any
change to data stored off-chain (ADR decision).

**Couldn't digital signatures alone stop tampering?**
Signatures stop tampering *if* the receiver knows the right public key. The blockchain is what gives every
node the same trusted list of device keys. It also adds things signatures can't:
- replay detection across different edges (shared "already processed" state),
- a tamper-proof model registry,
- an audit trail nobody can quietly delete.

**Why a local blockchain and not real Ethereum?**
Real Ethereum costs money and gives unrepeatable timings. The ADR rejected it; a private chain is standard
for research prototypes. Since final task 2 the private chain is a real network: 4 Besu validators running QBFT
consensus, with the layers writing and reading through different nodes.

**Is your blockchain really decentralised?**
Since final task 2, yes for the ledger:
- 4 validators each hold the full chain;
- a block is final only when 3 of the 4 agree;
- every run checks that all 4 nodes end with the same chain;
- a replay is caught even when the original was recorded through a different node.

Limits: the validators run on one machine (no WAN delay), and the four AI layers still run in one process.

**Your latencies are much smaller than the paper's. Why?**
That was true of the instant-mining chain: no block time, no consensus, no network.
- On the 4-validator network with one block per second, a message takes **2.75 s** (Merkle batch mode),
  because every write that the next layer must read waits for a block.
- The block period is the main setting: 2 s blocks give 5.5 s, 5 s blocks give 13.7 s.
- Consensus itself adds only ~34 ms per confirmation.
- Network transfer between layers is still not included.

The paper's numbers come from other studies on different tasks, so they are a reference, not a like-for-like
comparison.

**What happens when a part of the system fails?**
It was measured (Experiment F) by switching each part off for 30 s while 10,000 messages streamed:
- **An edge or fog that fails** hands its traffic to the other one, so no message is lost.
- **The cloud's input waits at the fogs** and arrives up to 33 s late, but complete.
- **A crashed blockchain node:** its clients switch to another node within milliseconds and resend what was
  unconfirmed.
- **Without these mechanisms,** 19–26% of the messages are lost, including attack traffic.
- **The 4 validators tolerate one failure** (the chain continues, slower). With two failures the chain halts until
  one returns, losing nothing and never forking.

**Is the dataset from IEEE DataPort?**
Yes: Edge-IIoTset, DOI 10.21227/MBC1-1H68. The files were downloaded from the authors' official Kaggle
copy because DataPort requires a subscription login; the files are identical and fingerprinted.

**How do you know the models aren't cheating?**
Columns that reveal the answer (IP addresses, timestamps, ports, payloads) are removed, duplicates are
removed, and all results use test data never seen in training. Every removal is logged with its reason.

**What is still missing?**
See §11.6. Real timestamps and device identity (task 1), the multi-node chain (task 2) and the fault-tolerance
tests are done. Still missing:
- the AI-driven blockchain part (RQ-11, task 3, next);
- time-window features;
- real network transport and containers;
- the dashboard.

---

## 18. References

1. S. K. Singh, S. Rathore, J. H. Park. *BlockIoTIntelligence: A Blockchain-enabled Intelligent IoT
   Architecture with Artificial Intelligence.* Future Generation Computer Systems 110 (2020) 721–743.
   (`blockchain_proj_ref.pdf`)
2. M. A. Ferrag, O. Friha, D. Hamouda, L. Maglaras, H. Janicke. *Edge-IIoTset: A New Comprehensive
   Realistic Cyber Security Dataset of IoT and IIoT Applications for Centralized and Federated Learning.*
   IEEE Access 10 (2022) 40281–40306, doi:10.1109/ACCESS.2022.3165809.
3. Edge-IIoTset dataset, IEEE DataPort, DOI 10.21227/MBC1-1H68.
4. Course project list: Research in Information Security, Monsoon 2026 (`Project_list.pdf`), Project 15.
5. Project design documents: `BlockIoTIntelligence_ADR_Implementation.md`,
   `IEEE_DataPort_Edge_IIoTset_Dataset_Preparation_Plan.md`.
6. Candidate external-validation datasets (IEEE DataPort): X-IIoTID, DOI 10.21227/mpb6-py55; ToN_IoT,
   DOI 10.21227/fesz-dm97.
