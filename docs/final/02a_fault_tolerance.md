# Add-on after final task 2: Fault tolerance

**Goal:** switch off each part of the running system and measure, for each failure, how many messages are lost,
how long recovery takes, and whether the pipeline keeps going (ADR Experiment F). The parts switched off are:
- a device;
- an edge;
- a fog;
- the cloud;
- one blockchain validator together with its RPC endpoint;
- two validators.

Each failure is measured with and without recovery mechanisms.

Status: **complete (3 Nov 2026)**. Plan in §1–9; implementation and results in §10; definition of done in §8.

---

## 1. What it is and why it matters

### The limitation before this add-on
- **Nothing in the pipeline handled a failure:**
  - traffic meant for a failed edge or fog was lost;
  - the single cloud had no queue;
  - a dead blockchain node made the client raise `ConnectionError`, and the whole run stopped.
- **The ADR control for blockchain failures was never built.** ADR §14.2 answers "blockchain RPC failure" with
  *retry + local queue + eventual commit*, and ADR Phase 2 step 10 asks for "retry handling for blockchain RPC
  failures". Neither was built: `configs/blockchain.yaml` had a `retry` block that no code read.
- **Experiment F** (ADR §11.2: disable a device, an edge, a fog, a cloud worker and a blockchain RPC endpoint;
  measure event loss, recovery time and pipeline continuity) had not started.

### What this add-on gives
1. **Recovery mechanisms:**
   - **edge and fog failover:** traffic for a failed one goes to the next one that is up;
   - **store and forward** for the cloud;
   - **blockchain client failover:** on a dead node, switch to the next live node and resend every transaction
     that was not confirmed. This is the ADR's eventual commit, and it uses the `retry` settings.
2. **A fault injector** that crashes and restores components on a schedule while the stream runs. Validators are
   crashed with SIGKILL and restarted with their own key and data.
3. **Experiment F** on the 4-validator QBFT network of task 2, with the realistic replay of task 1. Each fault is
   measured with recovery and, for the edge, fog and cloud, also without it.

### Questions it answers in the final
- **"What happens when a node fails?"** → event loss, recovery time and continuity for every layer.
- **"Is the network really Byzantine fault tolerant?"** → with 1 of 4 validators down the chain must continue; with
  2 of 4 it must halt (no quorum) and resume once a validator returns.
- **"Does the blockchain help fault tolerance?"** → because the ledger is shared, any edge can verify any device's
  messages, so an edge can take over a failed edge's devices without rejecting them.

---

## 2. Pre-study: what we measured before building (3 Nov 2026)

These were probes on a fresh 4-validator network (`qbft_network()`, 1 block/s, request timeout 4 s).

| Fact | Consequence |
|---|---|
| A client calling a crashed node gets `requests.exceptions.ConnectionError` at once (connection refused) | Failover can be immediate: no timeout to wait for |
| 1 of 4 validators down: **14 blocks in 30 s** instead of 30 | Every block whose proposer is the dead validator waits for a round change, so blocks come about half as often |
| A crashed validator restarted with its data directory answers after ~4.5 s and has caught up after **~6 s** | Restart and resync are measurable within one experiment |
| 2 of 4 validators down: **0 blocks in 30 s** | The chain halts, as QBFT must without a quorum (3 of 4) |
| Quorum restored after a 30 s halt: first new block only **128.7 s** later. After a 10 s halt: ~16 s later | QBFT's round timer doubles after each round without a block, so the longer the halt, the longer the wait once the quorum is back |
| The client waited at most 120 s for a receipt | A halt plus that recovery delay exceeds 120 s; the timeout became a setting, 600 s (`retry.receipt_timeout_s`) |
| A validator's command line and environment are enough to restart it with the same key, data, ports and peers | `Network.start(i)` restarts it; `Network.stop(i)` kills it |

---

## 3. Definitions used in this add-on

| Term | Meaning |
|---|---|
| Sent | Messages the devices sent. A device that is off sends nothing; its readings in that window are counted as *unsent*, not lost |
| Delivered | Distinct messages that reached the cloud (with a cloud prediction) |
| **Event loss** | Sent − delivered − rejected at an edge: messages that disappeared |
| Duplicates | Messages that reached the cloud more than once (must be 0, also when transactions are resent) |
| **Pipeline continuity** | Messages reaching the cloud per second over time; the longest interval with no delivery |
| **Recovery time** | From the repair until every message generated before the repair has reached the cloud |
| Failover time | From a validator's crash until a client using it has switched to another node |
| Resync time | From a validator's restart until it holds every block the other validators hold |
| Halt | Time without any new block; recovery delay = from the quorum's return to the first new block |
| Policy "recover" | Failover for edges and fogs, store and forward for the cloud |
| Policy "none" | Traffic for a failed edge, fog or cloud is lost (what the pipeline did before this add-on) |

---

## 4. How we will do it

### Step 1: Blockchain client failover (`src/common/blockchain.py`)
- **Which node a client fails over to:** each node's client knows the other nodes, in order (`connect`). When an
  RPC finds its node dead, `Endpoints.fail` moves to the next node that answers: the others first, then the dead
  node itself, for `retry.attempts` rounds with `retry.backoff_seconds` between rounds.
- **Every thread reconnects:** the main thread and the background receipt watcher each keep their own connection
  (`_Link`) and reconnect after a failover.
- **Unconfirmed transactions are resent:** a signed transaction sent to a node that has since died may never have
  left it. So every unconfirmed transaction is resent to the new node, in nonce order. A signed transaction's hash
  is fixed by its bytes, so resending is idempotent: "already known" or "nonce too low" just means it is already
  there.
- **Reads after a failover:** a read checks the new node's height before trusting it (read-your-writes, task 2).

### Step 2: Validators that crash and restart (`src/common/qbft.py`)
- `Network.stop(i)` kills validator i (SIGKILL, like a power cut).
- `Network.start(i)` restarts it with its own key, data directory and ports.
- `Network.head(i)` returns its height, and `Network.block_times()` the timestamp of every block.
- `NodeMonitor` follows restarted processes, so node CPU and memory stay correct.

### Step 3: Fault injector (`src/common/faults.py`)
- **What a fault is:** `Fault(target, down_at_s, up_at_s)`. The target is `device:<id>`, `edge-<k>`, `fog-<k>`,
  `cloud` or `node:<i>`.
- **Runs in its own thread:** during a chain halt the pipeline thread is blocked inside a transaction, and the
  repair must still happen on time.
- **Logs every action** with its time, including each restarted node's resync.
- **Nothing stays broken:** whatever is still down when the stream ends is repaired then, and restarted nodes are
  waited for until they have resynced.

### Step 4: Pipeline (`src/pipeline.py`)
- **A separate loop:** `run(faults=[...], fault_policy=...)` uses `_stream_with_faults`. The original loop is
  unchanged, so every earlier result is reproduced exactly; `faults=[]` gives the reference run, with the same loop
  and records but nothing failing.
- **Decisions at every hop:** each hop checks whether its next component is up when it sends (gateway → edge,
  edge → fog, fog → cloud) and applies the policy. A component fails between hops, never in the middle of
  processing a micro-batch.
- **What it records:**
  - how many messages were unsent, rerouted, held or lost, and where;
  - a timeline of every delivery to the cloud (time, messages, latency);
  - the clients' failovers;
  - every block's time.

### Step 5: Experiments (`scripts/run_faults.py`, suite `final_faults`)
**Setup of every run:**
- data: dataset v2 realistic replay, 10,000 messages, models of view `real_time`;
- chain: 4 QBFT validators, 1 block/s, background audit writes;
- topology: 2 edges, **2 fogs** (so every layer but the cloud has a peer), 1 cloud;
- node roles: gateway → node 0, edge-00 → 1, edge-01 → 2, fog-00 → 3, fog-01 → 0, cloud → 1;
- timing: each fault starts **30 s** into the stream and is repaired **30 s** later, unless stated otherwise.

| Scenario | Fault | Modes | Policies |
|---|---|---|---|
| Reference | none | batch, per-event | — |
| Device off | `soil_moisture` (142 messages in the window; keeps sending afterwards) | batch | — |
| Edge down | edge-00 (all attack traffic: the attacked device, plus 3 normal sensors) | batch | recover, none |
| Fog down | fog-00 (the same traffic, from edge-00) | batch | recover, none |
| Cloud down | the cloud | batch | recover, none |
| 1 of 4 validators down | validator 1, the RPC endpoint of edge-00 and the cloud | batch, per-event | client failover |
| 2 of 4 validators down | validators 2 and 3. Validator 3 is restarted at 60 s, which restores the quorum; validator 2 is restarted at the end | batch, per-event | client failover |

### Step 6: Figures, tables, tests, docs
- `scripts/make_figures.py --set final_faults` → `docs/final/faults/`.
- Unit tests: routing, the fault schedule, endpoint failover, resending, the node monitor across restarts.
- Integration tests: every layer fault with and without recovery; the ledger lets another edge verify; a
  validator crash on QBFT.
- README, project guide and this document.

---

## 5. Expected results

1. **Edge and fog failover:** no message lost, latency about unchanged. Without recovery, the failed component's
   share of 30 s of traffic is lost.
2. **Cloud, store and forward:** no message lost. The held messages arrive with up to ~30 s of extra latency, and
   recovery takes a few seconds. Without recovery, 30 s of traffic is lost.
3. **Device off:** only its own readings are unsent; everything else is unchanged. When it returns, its messages are
   accepted: a gap in sequence numbers is allowed, a step back is not.
4. **1 of 4 validators down:**
   - the chain continues (f = 1), producing blocks about half as often;
   - its clients fail over within about a second;
   - nothing is lost;
   - the restarted node resyncs in seconds.
5. **2 of 4 validators down:**
   - the chain halts;
   - the pipeline stalls without losing a message or accepting anything unverified;
   - it resumes after the quorum returns, delayed by QBFT's round-change backoff.
6. **In every run:**
   - every delivered message gets the same prediction at every layer as in the reference run;
   - no failed transactions;
   - all 4 validators hold the same chain at the end.

---

## 6. Risks and how we handle them

| Risk | Handling |
|---|---|
| A transaction sent to a node that then crashes is lost from its pool | Resend every unconfirmed transaction after a failover (idempotent) |
| Resending creates duplicates | A signed transaction can only be included once (nonce); duplicates at the cloud are counted (must be 0) |
| A restarted validator corrupts its database after SIGKILL | Resync measured and logged; the consensus check at the end covers all 4 nodes |
| The halt plus QBFT recovery exceeds the receipt timeout | `retry.receipt_timeout_s` = 600 s |
| Timing of faults differs slightly between runs | Faults are scheduled in wall-clock seconds from the stream start; every action's actual time is logged and used |

## 7. Effort and order
About **2 days**: probes and client failover (½ day), injector and pipeline (½ day), experiments (~40 min of run
time), figures, tests and documentation (1 day). Task 3 (RQ-11) follows.

## 8. Definition of done
- [x] Recovery mechanisms built: edge and fog failover, cloud store and forward, blockchain client failover with
  resending (ADR §14.2), using `configs/blockchain.yaml` `retry`. *(§10.1)*
- [x] Every ADR Experiment F fault measured (device, edge, fog, cloud, blockchain RPC endpoint), plus 1 and 2 of 4
  validators; event loss, recovery time and continuity reported. *(§10.4–10.6)*
- [x] With recovery: 0 messages lost, 0 duplicates, 0 genuine messages rejected, 0 failed transactions, predictions
  identical to the reference, all nodes consistent. *(all 13 runs, §10.3; flood alerts on fog failover: §10.7)*
- [x] Figures and tables (`docs/final/faults/`). *(figures 15–18, `faults_summary.csv`)*
- [x] Tests and documentation updated; all tests pass. *(99 tests; README, project guide, task 2 doc, this
  document)*

## 9. Note for the final report
- **Faults are crashes and unreachability.** A validator that sends conflicting messages (Byzantine behaviour), a
  network partition or slow links were not tested.
- **Everything runs on one machine,** so failure detection and failover use loopback.
- **Detection timing:** a failed layer is detected when the next message is sent to it. A validator crash is
  detected at the next RPC that uses that node.

---

## 10. Implementation and results (3 Nov 2026)

### 10.1 What was built

| Step | File(s) | Result |
|---|---|---|
| 1 Client failover | `src/common/blockchain.py` (`Endpoints`, `_Link`, `Chain`, `_ReceiptWatcher`, `connect`), `configs/blockchain.yaml` `retry` | Failover to the next live node; every unconfirmed signed transaction resent in nonce order (main thread and background watcher); reads re-check the new node's height; receipt timeout 600 s |
| 2 Validators | `src/common/qbft.py` (`Network.stop/start/head/block_times`), `NodeMonitor` | Crash (SIGKILL) and restart with the same key, data and ports; CPU and memory followed across restarts |
| 3 Injector | `src/common/faults.py` | Schedule in its own thread; actions and resyncs logged; everything repaired at the end |
| 4 Pipeline | `src/pipeline.py` (`route`, `_stream_with_faults`, `_fault_summary`) | Failover, store and forward or loss per policy; event accounting; delivery timeline; block times |
| 5 Experiments | `scripts/run_faults.py`, suite `final_faults`, `scripts/run_final_faults.sh` | 13 runs (§10.3) |
| 6 Figures | `scripts/make_figures.py --set final_faults` → `docs/final/faults/` | Figures 15–18 and `faults_summary.csv` |
| Tests | `tests/unit/test_faults.py`, `tests/unit/test_multinode_client.py`, `tests/integration/test_fault_tolerance.py` | 19 new tests: routing, schedule, failover, resending, monitor; every layer fault with and without recovery; ledger-backed edge takeover; a validator crash on QBFT. 99 tests pass |

### 10.2 Facts found while building

1. **Failover on QBFT works end to end** (smoke test, 2,000 messages, validator 1 down 5–20 s):
   - its clients switched to node 2 about 1 s after the crash;
   - the restarted node answered after 4.5 s and had caught up after 6.1–6.7 s;
   - nothing was lost, duplicated or failed, in both modes;
   - all 4 nodes ended consistent.
2. **Quorum loss** (smoke test, validators 2 and 3 down at 5 s, validator 3 back at 15 s):
   - no block from 4.9 s to 30.9 s: the first block came 16 s after the quorum returned;
   - with validator 2 still down, blocks then came in groups of 3 with a ~5 s pause whenever validator 2 was the
     proposer, and message latency was ~7 s instead of 2.75 s;
   - all 3,000 messages were delivered, with no failed transactions.
3. **A bug found by the unit tests:** a restarted node's "resynced" entry could be logged before its "up" entry,
   because the resync thread started first. The injector now logs the restart first.
4. **Empty cloud:** a cloud that is down for the whole stream without recovery receives nothing. The accuracy
   report then had no rows to score; it now reports none instead of failing.
5. **The first full run (3 Nov, 22:31–23:11) was redone, for two reasons:**
   - **Its edge and fog faults hit the wrong components.** They hit edge-01 and fog-01, which carry only five
     normal sensors. All attack traffic (the attacked device's 6,049 messages) goes through edge-00 and fog-00, so
     losing edge-01 lost no attack message and changed no alert. The scenarios now fail edge-00 and fog-00: the
     heavier load to take over, and the traffic whose loss matters.
   - **The pipeline checked which components were down only at the start of each micro-batch.** A micro-batch that
     started while the cloud was down was held even when the cloud was back by the time it reached it, which
     added ~3 s to the cloud's recovery time. Each hop now checks when it sends.

   Everything else in that run matched expectations, and all 13 scenarios were re-run with the final code:
   - 0 messages lost with recovery;
   - 1,198 / 699 / 2,560 messages lost without recovery (edge-01, fog-01, cloud);
   - predictions identical to the reference;
   - all nodes consistent.

### 10.3 How the experiments were run
`scripts/run_final_faults.sh` (3 Nov 2026, re-run 23:15–23:55, **40 min**) ran the 13 runs of suite `final_faults`,
then the figures. Log: `experiments/logs/final_faults.log`. Every run is in
`experiments/results/final_faults/runs.jsonl`, and the messages each run delivered (every layer's prediction) are in
`rows/*.parquet`. Figures 15–18 and `faults_summary.csv` are in `docs/final/faults/`.

**Setup:**
- 10,000 realistic-replay messages per run;
- 4 QBFT validators, 1 block/s;
- 2 edges, 2 fogs, 1 cloud;
- background audit writes; seed 42;
- each fault from 30 s to 60 s after the stream started (the logged times agree to within 0.1 s).

**Checked in every one of the 13 runs:**
- 0 duplicates, 0 genuine messages rejected, 0 failed transactions;
- every delivered message has exactly the reference run's prediction at all four layers (10,000 of 10,000 compared
  where all were delivered);
- all 4 validators end with the same chain, each with 3 peers.

### 10.4 Event loss
Figure 17. Merkle batch mode.

| Fault | With recovery: lost | Moved instead (rerouted or held) | Without recovery: lost | Of the lost: attack messages |
|---|---:|---:|---:|---:|
| One device off (`soil_moisture`) | 0 | — | — | — |
| One edge down (edge-00) | **0** | 2,535 to edge-01 | 2,535 (25.4%) | 1,386 |
| One fog down (fog-00) | **0** | 1,893 to fog-01 | 1,893 (18.9%) | 794 |
| Cloud down | **0** | 2,560 held at the fogs | 2,560 (25.6%) | 794 |
| 1 of 4 validators down | **0** | client failover | — | — |
| 2 of 4 validators down | **0** | client failover; the pipeline waits | — | — |

**Device off:** the device sent nothing for 30 s (137 readings unsent, one contiguous block). Its 262 messages
after it came back were all accepted: a gap in sequence numbers is allowed, a step back is not. Nothing else changed.

**Without recovery, the loss falls on attack traffic.** edge-00 and fog-00 carry the attacked device, so a failed
edge or fog silently drops attacks:
- 1,386 attack messages without the edge;
- 794 without the fog or the cloud.

Of the 794 lost when the fog or the cloud is down, the cloud had flagged 629 as attacks in the reference run.

### 10.5 Continuity, latency and recovery time
Figures 15 and 16. Merkle batch mode; the no-fault reference is shown for comparison.

| Fault (with recovery) | Messages/s while down (reference: 85) | Latency of messages generated while down (reference: 3.0 s) | Longest gap with no delivery (reference: 3.0 s) | Recovery time after the repair (reference: 1.9 s) |
|---|---:|---:|---:|---:|
| One device off | 82 | 3.0 s | 3.0 s | 2.0 s |
| One edge down | **128** | **2.1 s** | 3.0 s | 3.0 s |
| One fog down | 85 | 3.0 s | 3.0 s | 2.0 s |
| Cloud down | 0 (149 on average after the repair, backlog included) | 16.6 s mean, **33.0 s max** | 33.0 s | **2.2 s** |
| 1 of 4 validators down | 34 | **7.0 s** | 8.0 s | 3.9 s |
| 2 of 4 validators down | **0** | none generated: the pipeline waits | **101 s** | **69.9 s** |

What the table means:

- **Recovery time includes the micro-batch in flight.** It runs from the repair until the last message generated
  before the repair reaches the cloud. In the reference this is 1.9 s, simply the micro-batch that was in flight at
  60 s.
- **Fog failover costs nothing measurable.** Throughput, latency and recovery time are the same as in the
  reference.
- **Edge failover is faster than normal.** With one edge, a micro-batch waits for one processing record instead of
  two: the pipeline runs the edges one after the other (task 2, §10.4). So latency drops to 2.1 s and throughput
  rises to 128 messages/s.
- **Store and forward loses nothing and recovers immediately.** The cloud's input waits at the fogs: up to 33 s for
  the oldest message, decreasing linearly to the newest. It is forwarded in order the first time a fog sends after
  the repair. The backlog cleared 2.2 s after the repair, 0.2 s more than the reference.
- **1 of 4 validators down:**
  - the clients of node 1 (edge-00 and the cloud) failed over to node 2 **3–4 ms** after the crash, because they
    were polling it for receipts;
  - the chain kept producing blocks, but only **0.40 blocks/s**: every block whose proposer is the dead validator
    waits out a round change (the longest gap between blocks was 5 s);
  - so latency rose from 3.0 to 7.0 s and throughput fell from 85 to 34 messages/s;
  - restarted at 60 s, node 1 answered after 5 s, had caught up after **9.9 s**, and the next block came 2.8 s
    after the restart.
- **2 of 4 validators down:** see §10.6.

**Per-event mode** behaves the same way:
- 1 of 4 validators down: latency 9.0 s (reference 4.0 s), 34 messages/s (reference 60), recovery 11.0 s,
  resync 10.8 s;
- 2 of 4 validators down: 98 s longest gap, recovery 64.9 s.

### 10.6 Validator faults: what QBFT guarantees, measured
Figure 18.

| | 1 of 4 down (validator 1, 30–60 s) | 2 of 4 down (validators 2 and 3 at 30 s; 3 back at 60 s, 2 after the stream) |
|---|---|---|
| Blocks while down | 0.40 per second (reference 1.0) | **none: the chain halts (no quorum)** |
| Longest gap between blocks | 5 s | **95 s** (both modes) |
| First block after the repair | 2.8 s after the restart | **64.8 s** after the quorum returned (both modes) |
| Messages lost / failed transactions | 0 / 0 | 0 / 0 |
| Client failover | 3–4 ms after the crash | when the client first needed its node: 95.6 s after the crash (batch, after the halt) or 0.25 s (per-event); it skipped node 3 while that was down |
| Restarted node back in sync | 9.9–10.8 s | node 3: 4.8–5.6 s; node 2, which missed 86–107 blocks: 12.5–16.5 s |
| Rest of the stream | 1 block/s again | 0.4 blocks/s with 3 of 4, ~7 s per message; the stream took 312 s instead of 111 s (per-event 356 s instead of 159 s) |

**What this shows:**

1. **Byzantine fault tolerance holds as specified.** With f = 1 of 4 down the chain continues; with 2 down it stops.
   It never forks: every node ends with the same chain, including both restarted ones.
2. **The pipeline is safe while the chain is halted.** It waits with each micro-batch's device commitment
   unconfirmed. No message is processed without its commitment and none is lost. When blocks resume, every
   transaction is confirmed: those resent after the failover and those that waited out the halt.
3. **Recovery from a quorum loss is much slower than the outage itself.** The first block came 64.8 s after the
   quorum returned: twice in each mode, 63.8–64.9 s across both runs of the experiment. Earlier measurements,
   after shorter or differently timed halts, gave 16 s and 128.7 s. These values are close to 4 s × 2ⁿ (16 = 4·2²,
   64 = 4·2⁴, 128 = 4·2⁵). That is consistent with QBFT's round timer, which starts at the request timeout (4 s)
   and doubles after every round without a block, and with the validators waiting out the current round. The
   measured delays are reported as observed; Besu's own consensus logs (`--logging=WARN`) were not used to confirm
   the round numbers.
4. **One validator down still costs speed.** With 1 of 4 validators down, blocks come at 40% of the normal rate,
   because a quarter of the proposer turns time out. A validator should be restarted quickly even though the chain
   survives without it.

### 10.7 Detection results under faults
**Model predictions are unchanged.** Every delivered message has the same device, edge, fog and cloud prediction
as in the reference run: in all 13 runs, 100% of the messages compared.

**Flood alerts are lost when a fog's state is lost.** With edge-00 or fog-00 failing over, the run raised **108
fewer alerts** (4,824 instead of 4,932). These are exactly all 108 rate-based flood alerts of the reference; all
4,824 model-based alerts are identical. The cause was reproduced without a blockchain (same fog logic, deterministic
switch-over):
- **The flood check is stateful.** It counts each device's messages over the last 1 s of message time, and fires
  above 2,500 messages/s.
- **That second covers the whole outage here.** The pipeline processes ~85 messages per second of wall time,
  while the attacked device's flood packs ~2,700 messages into one second of message time. So one second of
  message time spans about 30 s of processing.
- **The backup fog misses the flood.** It starts with an empty window, and the flood began just before the
  failover. Its window peaks at 912 messages: the flood is never seen.

Failing over stateful analysis needs that state. Recording each fog's windows, or rebuilding them from the
messages the edges already recorded, would close this gap. It is noted as a limitation (§10.9).

### 10.8 Expected vs measured

| # | Expected (§5) | Measured | Verdict |
|---|---|---|---|
| 1 | Edge and fog failover: no loss, latency about unchanged; without recovery, 30 s of that component's traffic lost | 0 lost; fog latency unchanged; edge latency *lower* (2.1 vs 3.0 s; sequential edges); without recovery 2,535 / 1,893 lost, including 1,386 / 794 attack messages | Confirmed; edge faster than expected |
| 2 | Cloud: no loss, held messages up to ~30 s late, recovery in seconds; without recovery, 30 s lost | 0 lost; up to 33.0 s late; backlog cleared 2.2 s after the repair; without recovery 2,560 lost | Confirmed |
| 3 | Device off: only its readings unsent; accepted again afterwards | 137 unsent; 262 later messages all accepted; nothing else changed | Confirmed |
| 4 | 1 of 4 validators: chain continues at about half rate, failover within ~1 s, no loss, resync in seconds | 0.40 blocks/s; failover in 3–4 ms; 0 lost; resync 9.9–10.8 s | Confirmed |
| 5 | 2 of 4: chain halts, pipeline stalls safely, resumes after the quorum returns, delayed by round-change backoff | Halt 95 s; first block 64.8 s after the quorum returned; 0 lost, 0 failed | Confirmed; the delay is much longer than the 30 s outage |
| 6 | Identical predictions, no failed transactions, consistent nodes | All three in every run; but 108 flood alerts lost on fog failover (§10.7) | Confirmed, plus one finding |

### 10.9 Limitations and what remains
- **Faults are crashes and unreachability.** Not tested:
  - a Byzantine validator, one that signs conflicting blocks;
  - a network partition;
  - slow links;
  - a crash in the middle of processing a micro-batch.
- **Fog failover loses the fog's traffic windows.** In this run that meant every flood alert (§10.7); sharing or
  rebuilding the window state is future work.
- **One seed, one fault time (30–60 s) and one machine.** The quorum-recovery delay depends on when the quorum
  returns relative to QBFT's round timer (observed 16–129 s).
- **The cloud is a single point:** store and forward keeps its input but needs memory at the fogs for the whole
  outage (2,560 messages here).
- **Next:** ~~final task 3 (RQ-11, AI-chosen Merkle batch size) on this network~~: done, see
  [03_ai_driven_blockchain.md](03_ai_driven_blockchain.md). The time-window features add-on is still pending.
