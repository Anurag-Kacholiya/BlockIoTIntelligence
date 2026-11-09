# Final task 2: Multi-node blockchain

**Goal:** replace the single blockchain node that confirms every transaction instantly with a private network of
**4 validator nodes reaching consensus**, each architecture layer talking to a different node, and measure what
consensus and a real block time cost.

Status: **complete (3 Nov 2026)**. Plan in §1–9; what was built and all results in §10. Definition of done in §8.

---

## 1. What it is and why it matters

### The limitation today
Every blockchain result so far (mid-term and task 1) runs on **one Anvil node in automine mode**: each transaction
is mined into its own block the moment it arrives, with no other node to agree with. Two consequences:
- The system is not decentralised: one process holds the only copy of the ledger.
- Latency **excludes consensus and block time**, the main delay of a real blockchain. The comparison with the
  paper ("blockchain adds latency") is therefore optimistic.

### What this task gives
1. **A real BFT network:** 4 Hyperledger Besu validators running **QBFT** consensus, each with its own key,
   database, peer-to-peer port and RPC endpoint. A block is final when 3 of the 4 agree, so the network keeps
   working with one faulty validator.
2. **Layers on different nodes:** the device gateway writes through node 0, the edges read and write through
   nodes 1 and 2, the fog through node 3. Data committed through one node must be verified through another.
3. **Realistic latency:** each transaction waits for the next block (one per second) and a consensus round.
4. **The same experiments, same data:** dataset v2's realistic replay (task 1), so the only change is the chain.

### Questions it answers in the final
- "Is your blockchain really decentralised?" → 4 validators, BFT consensus, every node holds the same chain.
- "Are your latencies realistic?" → latency now includes block time and consensus, measured per layer.
- "What does decentralisation cost, and where?" → single node vs one block per second vs 4-validator consensus,
  same workload.

---

## 2. Pre-study: what we measured and decided (3 Nov 2026)

| Fact | Consequence |
|---|---|
| Docker is not installed on the project machine; Java 25 is | Validators run as 4 local Besu processes, not containers (containers are week 3 of the plan) |
| Besu 26.10.0 (released 16 Oct 2026, Apache-2.0): tarball 193,367,902 bytes, SHA-256 `927429dd…5d96`, identical to the release's published `.sha256` | Pinned in `configs/blockchain.yaml`; `scripts/setup_besu.py` refuses any other file |
| Besu keeps no unlocked accounts (Anvil does) | The client signs transactions itself with the same dev mnemonic, so every role keeps its address |
| Signing in pure Python: **2.54 ms** per transaction; with `coincurve` (native secp256k1): **0.155 ms** | `coincurve==21.0.0` added; otherwise signing would add ~50 s per 10,000 per-event messages |
| The contract is compiled for the Cancun EVM (Foundry default; bytecode uses `PUSH0`) | The QBFT genesis activates every fork up to Cancun from block 0 |
| Per-event mode on automine Anvil: **35–38 events/s** at 10,000 messages (mid-term and task 1 alike), because every transaction gets its own block (20,000 blocks) | A block-based chain may batch these transactions into far fewer blocks, so per-event mode could even get faster |

---

## 3. Definitions used in this task

| Term | Meaning |
|---|---|
| Validator | A node that proposes and signs blocks; QBFT needs 2f + 1 of n = 3f + 1 to agree (4 → 3) |
| Block period | Time between blocks (QBFT `blockperiodseconds`); a transaction waits for the next block |
| Critical path | Writes that a later check reads: device commitments (read by the edge) and edge processing records (read by the replay check). The next layer must wait for these |
| Audit write | Writes nothing on the event path reads: fog alert audit, cloud inference record |
| Message latency | Time from a micro-batch entering the device layer to its cloud result (`batch_end_to_end`) |
| Read-your-writes | A read through any node sees every write already confirmed through any node |

---

## 4. How we will do it

### Step 1: Toolchain
`scripts/setup_besu.py` downloads Besu 26.10.0 from the official release page, checks the pinned SHA-256 and
Java ≥ 21, and installs it into `tools/besu` (git-ignored, as Foundry).

### Step 2: Network (`src/common/qbft.py`)
For every experiment, a fresh network: Besu's own generator (`operator generate-blockchain-config`) creates the 4
validator keys and the QBFT genesis (chain id 1337, gas limit 300 M as on Anvil, Cancun rules, zero base fee,
the 20 dev accounts funded). Each validator starts with its own data directory and ports; the helper waits until
every node is peered with the other 3 and blocks are produced, and stops and deletes everything afterwards.

### Step 3: Client (`src/common/blockchain.py`)
- **Local signing** with per-sender nonces (`LocalSigner`).
- **One `Chain` per node** (`connect`), sharing transaction statistics.
- **Read-your-writes across nodes** (`ReadMark`): before a read, the node must have imported the highest block
  holding a confirmed write. Without it, an edge could read a device commitment through a node that has not yet
  imported the block, and reject a genuine message.
- **Audit writes in the background** (option): fog alerts and cloud inference records are confirmed by a watcher
  thread; the run still waits for all of them before it ends. Critical-path writes are always awaited.

### Step 4: Pipeline (`src/pipeline.py`)
`run(chain_backend="qbft")` starts the network and spreads the roles over the nodes (gateway 0, edges 1–2,
fog 3, cloud 0). The result records the backend, nodes, roles, signing, audit-write policy, and a **consensus
check**: every node's block hash at the highest common height must be identical.

### Step 5: Experiments (`scripts/run_multinode.py`, suite `final_task2`)
All on dataset v2's realistic replay (10,000 messages, 2 edges, 1 fog, view `real_time` models).

| Group | Chains | Modes | Purpose |
|---|---|---|---|
| T2.1 comparison | Anvil automine · Anvil 1 block/s · **QBFT 4 validators, 1 block/s** | per-event, batch; 3 seeds | What block time and consensus cost |
| T2.2 await all | QBFT 1 s | per-event, batch | The task 1 client (every write awaited) on the network |
| T2.3 block period | QBFT 2 s, 5 s | batch | Latency vs block period |
| T2.4 scaling | QBFT 1 s, 10–500 devices (task 1 replicas) | batch, per-event | Compare with task 1's single-node scaling |
| Security | QBFT 1 s, fresh network per pass | per-event | `run_security.py --chain qbft`: do all 8 attacks still fail? |

The client is identical in every T2.1 run (local signing, background audit writes), so the chain is the only change.

### Step 6: Figures, tables, docs, tests
`scripts/make_figures.py --set final_task2`; unit tests (genesis, signing, cross-node reads, roles); integration
tests on Anvil and on QBFT; README, project guide and this document.

---

## 5. Expected results

1. **Accuracy and gas are identical on every chain:** the ledger never alters the data, and the same contract
   calls cost the same gas.
2. **Latency grows by about the block period per critical-path write.** Two critical-path writes per micro-batch
   (commitment, processing record) → message latency ≈ 1–2 s at 1 block/s, versus ~0.1 s on automine.
3. **Consensus itself is cheap next to block time:** QBFT 1 s ≈ Anvil 1 s plus a small overhead.
4. **Per-event mode stops being far slower than batch mode:** many transactions share one block.
5. **Background audit writes** shorten each micro-batch by up to two block waits.
6. **Security results unchanged:** all 8 attacks blocked, no genuine message rejected, including cross-edge replay
   detected through a *different* node.
7. **Cost:** 4 Java validators use far more memory and CPU than one Anvil process.

---

## 6. Risks and how we handle them

| Risk | Handling |
|---|---|
| Besu cannot run Cancun bytecode under QBFT | Detected by the first deployment; fallback: compile for Shanghai and report the gas change |
| A node lags behind and a read misses a fresh write | `ReadMark` read-your-writes; integration test checks no genuine rejection |
| Transaction pool limits per sender (per-event mode sends 256 per micro-batch from one gateway account) | Measured in the first runs; Besu pool options raised if transactions are dropped |
| 4 JVMs and the pipeline share one 10-core laptop | Node CPU and memory are reported; runs are sequential |
| Round changes (a slow proposer) create latency spikes | Reported as p95 message latency |
| Startup of a fresh network per run (~tens of seconds) | Excluded from the measured window |

---

## 7. Effort and order
About **1 week**: setup and network (1 day), client and pipeline (1 day), experiments (1–2 days, mostly run time),
figures and documentation (1 day). The fault-tolerance test (stop one validator, then an edge, fog, …) is the
add-on that follows this task.

## 8. Definition of done
- [x] Besu installed reproducibly (pinned version and checksum); a 4-validator QBFT network starts, peers, and
  every node holds the same chain. *(§10.1; network check and all 20 QBFT runs `consistent`, §10.3)*
- [x] The full pipeline runs on the network with the layers on different nodes; no genuine message rejected.
  *(150,000 messages on QBFT and 14,870 genuine messages in the security passes: 0 rejected)*
- [x] T2.1–T2.4 and security re-run on QBFT; accuracy and gas checked identical to the single node.
  *(§10.4–10.8)*
- [x] Figures and tables regenerated (`docs/final/task2/`). *(figures 11–14 and 04; 5 tables)*
- [x] Tests and documentation updated; all tests pass. *(80 passed, ruff clean; README, project guide, this
  document)*

## 9. Note for the final report
State the setup exactly: 4 validators on one machine, so network delay between them is loopback (≈0); latency
includes block time and QBFT consensus but not WAN delay. This is the ADR §6.6 "multi-node experiment"; it remains
an engineering approximation of a deployed network.

---

## 10. Implementation and results (3 Nov 2026)

### 10.1 What was built

| Step | File(s) | Result |
|---|---|---|
| 1 Toolchain | `scripts/setup_besu.py`, `configs/blockchain.yaml` (`qbft`) | Besu 26.10.0 in `tools/besu`, SHA-256 checked against the pinned value, Java 25 detected |
| 2 Network | `src/common/qbft.py` | `qbft_network()`: keys and genesis from Besu's generator, 4 validator processes (own data directory, P2P and RPC port each), ready when every node has 3 peers and blocks are produced (~20 s); `Network.report()` checks that all nodes hold the same block at the highest common height |
| 3 Client | `src/common/blockchain.py` | `LocalSigner` (dev mnemonic, per-sender nonces), `connect()` (one `Chain` per node, shared statistics), `ReadMark` (read-your-writes across nodes), `send_many(wait=False)` + background receipt watcher, `drain()`; `NodeMonitor` sums CPU and memory over all node processes |
| 3 Clients per layer | `src/fog/blockchain_client.py`, `src/cloud/blockchain_client.py` | Audit writes may be confirmed in the background (`wait=False`); model registration is always awaited |
| 4 Pipeline | `src/pipeline.py` | `run(chain_backend="qbft", signing=…, audit_writes=…)`; `node_roles()`: device gateway → node 0, edges → nodes 1 and 2, fog → node 3, cloud → node 0; the result records backend, nodes, roles and the consensus check |
| 5 Experiments | `scripts/run_multinode.py`, suite `final_task2`, `scripts/run_security.py --chain qbft`, `scripts/run_final_task2.sh` | T2.1–T2.4 and security (10.3–10.7) |
| 6 Figures | `scripts/make_figures.py --set final_task2` → `docs/final/task2/` | Figures 11–14 and the security figure, with tables |
| Tests | `tests/unit/test_multinode_client.py`, `tests/integration/test_blockchain_pipeline.py` | Genesis, signing and nonces, cross-node reads, roles; locally signed run with background audit writes on Anvil; **the full pipeline on a 4-validator network** (tampered messages rejected, all nodes agree). 80 tests pass |

### 10.2 Decisions and facts found while building

1. **Besu runs the Cancun bytecode under QBFT.** The contract deployed and worked unchanged with `shanghaiTime`
   and `cancunTime` at 0, so gas is directly comparable with the Anvil runs (risk in §6 did not occur).
2. **Transaction pool limit.** Besu's default refuses a transaction more than 200 nonces ahead of the sender's
   last confirmed one (`Transaction nonce is too distant from current sender nonce`). One micro-batch sends up to
   256 transactions per account (per-event mode), so `--tx-pool-max-future-by-sender` is set to 10,000
   (`configs/blockchain.yaml`).
3. **QBFT block headers** carry the validator list and their signatures in `extraData` (327 bytes in the network
   check), which web3.py rejects by default; the consensus report reads blocks through web3's
   proof-of-authority middleware. Transactions and receipts are unaffected.
4. **Network check** (`run_multinode.py check`): 4 validators, each with 3 peers; a device registered through
   node 0 is read back through node 3; all heads equal (block 4), identical hashes. Start-up to first use ≈ 20 s.
5. **Same client for every chain in T2.1.** Anvil runs also sign locally and confirm audit writes in the
   background, so only the chain differs between the three T2.1 chains. The task 1 numbers (Anvil signing, every
   write awaited) remain the single-node reference.

### 10.3 How the experiments were run
`scripts/run_final_task2.sh` (3 Nov 2026, 20:04–21:46, **1 h 43 min**): network check → the 32 runs of suite
`final_task2` → security on QBFT → figures. Log: `experiments/logs/final_task2.log`; every run in
`experiments/results/final_task2/runs.jsonl`; figures and tables in `docs/final/task2/`.

- **Data:** dataset v2 realistic replay, `real_time` models, 2 edges, 1 fog, micro-batches of 256 messages:
  10,000 messages per run (5,000 in T2.4).
- **Client in every run:** transactions signed locally; fog and cloud audit records confirmed in the background
  (except T2.2).
- **Totals:** 32 runs and 270,000 messages; 20 of the runs and 150,000 of the messages on a 4-validator network.
- **Checks passed by every run:**
  - 0 failed transactions;
  - 0 genuine messages rejected;
  - every QBFT run: 4 validators, each node with 3 peers, and the same block at the highest common height on all
    4 nodes (`consistent = true`).

### 10.4 T2.1: what block time and consensus cost (3 seeds)
Figures 11 and 12, table `chain_comparison.csv`. Means over seeds 42–44.

| Chain | Mode | Throughput (msg/s) | Message latency mean / p95 (s) | Commitment confirmed (ms) | Processing record confirmed (ms) | Node CPU (s) | Node peak memory (MB) |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 node, instant blocks | per-event | 38.4 | 6.51 / 11.33 | 1,429 | 1,114 | 220 | 1,943 |
| 1 node, instant blocks | batch | 2,382 | 0.10 / 0.12 | 5.9 | 3.8 | 0.7 | 163 |
| 1 node, 1 block/s | per-event | 74.8 | 3.31 / 4.01 | 862 | 636 | 9.2 | 459 |
| 1 node, 1 block/s | batch | 90.1 | 2.75 / 3.01 | 947 | 946 | 2.6 | 72 |
| **4 validators (QBFT), 1 block/s** | per-event | **63.5** | **3.91 / 4.82** | 999 | 778 | 214 | 2,650 |
| **4 validators (QBFT), 1 block/s** | batch | **90.2** | **2.75 / 3.02** | 981 | 921 | 93 | 1,722 |

Seeds barely differ:
- QBFT batch: 90.15–90.16 msg/s;
- QBFT per-event: 62.1–64.6 msg/s.

#### Block time, not consensus, sets the latency
- **Merkle batch mode on QBFT behaves the same as one node with 1 block/s:** 2.75 s and 90 msg/s on both.
- Agreement among 4 validators adds **34 ms** to the time a commitment takes to be confirmed (981 vs 947 ms).
  That is about 1% of the message latency.

#### Where the 2.75 s go
Measured per layer in the QBFT batch run, seed 42:

| Layer | Mean time per micro-batch | What it waits for |
|---|---:|---|
| Device | 1.01 s | One commitment transaction: one block |
| Edge | 1.70 s (median 1.94 s) | Each edge waits for its own processing record, and the pipeline runs the 2 edges one after the other. A micro-batch with messages for both edges therefore waits 2 blocks |
| Fog | 18 ms | Its audit write is confirmed in the background |
| Cloud | 15 ms | Its audit write is confirmed in the background |

So message latency ≈ (1 + number of edges in the micro-batch) × block period.

#### Throughput is limited by latency, not by the chain's capacity
- Micro-batches are processed one after another, so throughput ≈ 256 messages / 2.75 s ≈ 93 msg/s
  (measured: 90 msg/s).
- The chain is almost idle:
  - Merkle batch mode: 1.5 M gas/s, 0.5% of a block's 300 M gas limit, 4.8 transactions/s;
  - per-event mode: 10.3 M gas/s, 3.4% of the limit, 128 transactions/s.

#### Per-event mode is 15% slower on QBFT than on one node with the same block time
- Throughput: 63.5 vs 74.8 msg/s. Message latency: 3.91 vs 3.31 s.
- Each block now carries about 128 transactions, and every validator must execute and import it. A commitment
  takes 999 ms to be confirmed instead of 862 ms.
- Per-event mode on QBFT is still **1.7× faster than on the instant-block node** (38.4 msg/s):
  - Anvil automine mines each of the 20,117 transactions into its own block;
  - on QBFT the chain is only 165–171 blocks high at the end of a run, including start-up.

#### Merkle batching keeps its gas advantage but loses most of its speed advantage
| | Batch vs per-event throughput | Batch vs per-event gas per message |
|---|---|---|
| 1 node, instant blocks | 62× faster (2,382 vs 38.4 msg/s) | 10.1× less (16.0 k vs 162.0 k) |
| 4 validators (QBFT), 1 block/s | 1.4× faster (90.2 vs 63.5 msg/s) | 10.1× less (16.0 k vs 162.0 k) |

Once every write waits for a block, the number of transactions matters little. What matters is how many block waits
happen one after another.

#### Accuracy and gas are identical on every chain
- **Accuracy:** every layer's scores are identical to 6 decimals in all 32 runs, and identical to task 1.
  Cloud multiclass macro-F1 is 0.7794 at 10,000 messages and 0.7531 at 5,000.
- **Gas, event path:** for the same seed, every event-path and setup transaction costs exactly the same gas on all
  three chains and in task 1, including every T2.4 point. For example, with seed 42 device commitments total
  972,491,600 gas in per-event mode and 20,417,796 in batch mode.
- **Gas, audit records:** fog alert audits and cloud inference records differ by at most 1,536 gas out of
  127.5 M (0.001%). Their hashed content includes the wall-clock time, which changes how many zero bytes the
  calldata has (4 gas per zero byte, 16 per non-zero byte).

#### Cost of running the network
- 4 Besu validators use **35× the CPU and 24× the memory** of one Anvil node with the same block time
  (batch mode: 93 s vs 2.6 s CPU, 1.7 GB vs 72 MB).
- In per-event mode: 214 s vs 9 s CPU, 2.65 GB vs 0.46 GB.
- The validators keep running consensus every second even when no transactions arrive.

### 10.5 T2.2: every write awaited (the task 1 client on the network)
QBFT, 1 block/s, seed 42. Figures 11 and 12 (rightmost group).

| Mode | Audit writes in the background | Every write awaited | Change |
|---|---|---|---|
| Batch | 90.2 msg/s, 2.75 s | 52.7 msg/s, 4.75 s | +2.0 s, −42% |
| Per-event | 63.7 msg/s, 3.90 s | 42.9 msg/s, 5.82 s | +1.9 s, −33% |

**Awaiting the fog alert audit and the cloud inference record costs two more blocks per micro-batch.**

Confirming them in the background weakens nothing:
- **Nothing reads them:** no layer reads these records during a run.
- **Every record is still confirmed:** in the per-event run with seed 42, all 57 alert audits and 40 inference
  records were confirmed (mean 936 ms and 917 ms, 0 failed). Every other run also had 0 failed.
- **The run waits for them:** a run ends only after the last of them is confirmed.

### 10.6 T2.3: block period
Figure 13, table `block_period.csv`. QBFT, Merkle batch mode. The 1 s values are the mean of 3 seeds; 2 s and 5 s
use seed 42.

| Block period | Message latency mean / p95 | Throughput | Commitment confirmed | Chain height at the end |
|---|---|---:|---:|---:|
| 1 s | 2.75 / 3.02 s | 90.2 msg/s | 981 ms | 121 |
| 2 s | 5.50 / 6.01 s | 45.1 msg/s | 1,991 ms | 120 |
| 5 s | 13.75 / 15.02 s | 18.0 msg/s | 4,981 ms | 120 |

- **Latency is exactly 2.75 block periods** (2.75, 5.50 = 2.0×, 13.75 = 5.0×), and throughput falls by the same
  factor.
- Every period needs the same ~111 blocks of run time:
  - 40 micro-batches × ~2.75 block waits;
  - plus about 10 blocks for start-up and deployment.
- **The block period is the main setting that decides latency** for this architecture.

### 10.7 T2.4: scaling, single node vs QBFT
Figure 14, table `scaling.csv`. Seed 42, 5,000 messages; the same messages and timing at every point (task 1
replicas).

| IoT devices | Batch throughput, 1 node, instant (task 1) | Batch throughput, QBFT | Per-event throughput, 1 node, instant (task 1) | Per-event throughput, QBFT | QBFT batch: gas per message | QBFT batch: Merkle roots per micro-batch |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 2,035 | 91.0 | 62.3 | 61.0 | 15,620 | 5.3 |
| 50 | 823 | 82.1 | 59.8 | 59.6 | 27,253 | 24.8 |
| 100 | 498 | 80.7 | 62.0 | 58.8 | 39,840 | 45.9 |
| 250 | 233 | 80.7 | 61.2 | 60.3 | 68,713 | 94.3 |
| 500 | 136 | 69.5 | 59.5 | 58.2 | 96,304 | 140.6 |

Per-event gas per message is 161,618 at every point.

#### On one instant-block node, Merkle batch throughput falls 15×
From 2,035 to 136 msg/s as devices go from 10 to 500.
- Each micro-batch commits one Merkle root per device.
- At 500 devices a 256-message micro-batch holds ~141 roots, about 1.8 messages each.
- Every root is a separate transaction, mined on its own.

#### On QBFT the same transactions share one block, so throughput falls only 24%
- Throughput: 91 → 70 msg/s. Message latency: 2.69 → 3.55 s.
- **The cost moves to gas:** gas per message grows **6.2×** (15.6 k → 96.3 k), most of the way to per-event
  mode (161.6 k).
- Per-event mode stays flat at about 60 msg/s on both chains.

#### What this means for task 3 (RQ-11, AI chooses the Merkle batch size)
On a real network the scaling problem is **gas per message**, plus a smaller throughput loss. So task 3 is
evaluated on the QBFT network, with two objectives:
- gas per message;
- message latency.

Collecting more messages per root (a longer window) lowers gas, and every extra block of waiting raises latency.

### 10.8 Security on the QBFT network
Figure 04 (task 2 version), table `security.csv`.

**Setup:**
- `run_security.py --rows 3000 --replay realistic --chain qbft`;
- every attack pass runs on a fresh 4-validator network;
- device gateway → node 0, edges → nodes 1 and 2, fog → node 3.

| Attack | Baseline (no blockchain) | Blockchain on QBFT | Detected by |
|---|---:|---:|---|
| Payload tampering | 0% | **100%** (130/130) | `hash_mismatch` |
| Replay, same edge | 100% | **100%** (134/134) | `duplicate_event` |
| Replay, other edge | 65% | **100%** (134/134) | `replay_already_processed` |
| Unregistered device | 0% | **100%** (140/140) | `unregistered_device` |
| Device impersonation | 0% | **100%** (140/140) | `identity_mismatch` |
| Model swap | 100% | **100%** | local record mismatch |
| Model swap + forged record | 0% | **100%** | on-chain registry mismatch |
| Unauthorized ledger write | — | **100%** | contract revert `NotAuthorized` |

- **All 8 attacks blocked, and 0 of 14,870 genuine messages rejected.** The baseline, by contrast, rejects 89.5% of
  genuine messages during impersonation (sequence-number lockout, as in the mid-term and task 1).
- **Identical to Anvil:** the events, rejected and reasons columns match task 1's results
  (`experiments/results/realistic/security.csv`) exactly.
- **Cross-node verification works:** a replay to the other edge is caught through a different node. The processing
  record is written through node 1 or 2 and checked through the other one.
- **Edge cost per message:** 17.9 ms on QBFT vs 6.0 ms on Anvil. Each edge micro-batch (~64 messages) waits one
  block for its processing record: 1 s / 64 ≈ 16 ms.

### 10.9 Expected vs measured

| # | Expected (§5) | Measured | Verdict |
|---|---|---|---|
| 1 | Accuracy and gas identical on every chain | Accuracy identical to 6 decimals; event-path gas identical to the unit; audit records ±0.001% (wall-clock content) | Confirmed |
| 2 | Latency ≈ block period per critical-path write; 1–2 s at 1 block/s | 2.75 s: there are up to **3** awaited writes per micro-batch, not 2, because the two edges' processing records are awaited one after the other | Confirmed; the estimate was low |
| 3 | Consensus cheap next to block time | Batch: identical to 1 node with 1 block/s (+34 ms per confirmation); per-event: −15% throughput (bigger blocks) | Confirmed |
| 4 | Per-event stops being far slower than batch | Gap 62× → 1.4×; per-event on QBFT 1.7× faster than on instant blocks | Confirmed |
| 5 | Background audit writes save up to two block waits | Awaiting them adds 1.9–2.0 s (two blocks) and costs 33–42% of throughput | Confirmed |
| 6 | Security unchanged | 8/8 attacks blocked, 0 genuine rejected, identical to Anvil | Confirmed |
| 7 | 4 validators cost far more CPU and memory | 35× CPU, 24× memory (batch) | Confirmed |

### 10.10 Limitations and what remains
- **One machine:**
  - the 4 validators talk over loopback, so latency includes block time and QBFT consensus but no WAN delay (§9);
  - the 4 JVMs share the 10 cores with the pipeline, using up to 1.4 cores.
- **One seed** for T2.2, T2.3 and T2.4. The 3-seed T2.1 shows almost no seed variation on QBFT (batch
  90.15–90.16 msg/s, per-event 62.1–64.6 msg/s).
- **Edges run one after the other** in the pipeline, as in the mid-term and task 1. This is kept so the results
  stay comparable. Run in parallel, a micro-batch would wait at most one block at the edges. This is an estimate,
  not measured: about 2 s instead of 2.75 s at 1 block/s (§10.4).
- **Not measured here:**
  - a validator or layer failure: the fault-tolerance add-on, next;
  - network sizes other than 4 validators;
  - WAN delay.
- **Next:**
  1. ~~the fault-tolerance add-on~~: done, see [02a_fault_tolerance.md](02a_fault_tolerance.md). With 1 of 4
     validators down the chain continued at 0.4 blocks/s; with 2 of 4 it halted and resumed 64.8 s after the quorum
     returned. No message was lost in either case;
  2. ~~task 3 (RQ-11), evaluated on this network (§10.7)~~: done, see
     [03_ai_driven_blockchain.md](03_ai_driven_blockchain.md). AI-scheduled commits cut gas per message at 500
     devices by 22.5%, and the growth from 10 to 500 devices from 6.2× to 4.8×.
