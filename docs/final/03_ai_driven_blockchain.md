# Final task 3: AI-driven blockchain (RQ-11)

**Goal:** let AI improve the blockchain itself. The device gateway uses a learned traffic forecast to decide, for each
device and each micro-batch, whether to commit the device's Merkle batch now or keep it open for the device's next
messages. Fewer, fuller Merkle roots cost less gas. The work measures how much gas this saves, what latency it adds,
and whether the AI does better than fixed batching and a fixed rule. It is measured on the 4-validator QBFT network
of task 2.

Status: **complete (4 Nov 2026)**. Plan in §1–9; implementation and results in §10; definition of done in §8.

---

## 1. What it is and why it matters

### The limitation today
- **Every AI model in the system decides about data:** attack or normal, which class of attack. None of them
  improves how the blockchain works. The paper names this direction, *AI-driven blockchain* (§4.1.1; ADR RQ-11), and
  it is the only paper requirement the project has not met (`PROJECT_GUIDE.md` §14.1).
- **Merkle batch mode pays per root, not per message.** Every micro-batch of 256 messages ends with one root per
  device that sent in it. Each root is a `commitBatch` transaction plus the edge's `recordProcessing` for it: about
  **149k gas** together (97,228 + 51,912 gas, task 2 means), whatever the number of messages under the root.
- **That is why batching stops helping with many devices** (task 2 §10.7). At 500 devices a micro-batch holds about
  141 devices, so a root covers 1.8 messages on average:
  - on the QBFT network, gas per message grows **6.2×** from 10 to 500 devices (15.6k to 96.3k gas);
  - on the single instant-block node of task 1, throughput falls **15×** (2,035 to 136 messages/s).

### What this task gives
1. **A commit scheduler at the device gateway** (`src/device/commit_policy.py`). After every micro-batch it decides,
   per device, whether to hold the device's batch open for later messages. Holding has two limits:
   - **a latency budget:** a message waits at most `hold_rounds` extra micro-batches;
   - **a price of latency:** `break_even` messages delayed by one micro-batch are worth one root's gas.
2. **A traffic forecaster:** a gradient-boosting model that predicts whether a device will send again before its
   batch must close.
   - **Inputs:** the device's own recent traffic, from the same feature code the gateway runs.
   - **Training:** the cloud trains it on the time split's train windows; the test window is never used.
   - **Provenance:** it is registered and verified on-chain like the four layer models.
3. **A decision that weighs gain against cost.** The AI holds a batch of *m* messages only when
   *p × break_even ≥ m*, where *p* is the forecast probability that the device sends again in time. The expected
   saving is *p* roots; the cost is *m* message-rounds of delay.
4. **An honest comparison.** The AI is compared with:
   - fixed batching (the task 2 design);
   - fixed batching with a longer interval;
   - a fixed rule that holds every small batch;
   - a non-learned forecast, Poisson arrivals at the device's recent rate;
   - perfect foresight, as the reference.

   Each comparison is run offline over the whole gas–latency trade-off and live on the 4-validator network.

### Questions it answers in the final
- **"Where does AI improve the blockchain, not only the blockchain the AI?"** → the gateway's forecaster decides
  when roots are committed; gas and latency are measured on the network.
- **"Does it fix the scaling drop of Merkle batching?"** → gas per message and throughput from 10 to 500 devices,
  fixed vs AI.
- **"Is AI needed, or would a simple rule do?"** → the same decision with no forecast, with a non-learned forecast,
  and with perfect foresight.
- **"What does it cost?"** → added latency per message, separately for attack traffic, and the security checks.

---

## 2. Pre-study: what we measured before building (4 Nov 2026)

All figures are offline counts on the task 2 scaling workload. That is 5,000 realistic-replay messages, each of the
10 real devices split over *k* devices, in micro-batches of 256. The roots are counted exactly as the pipeline
forms them.

| Fact | Consequence |
|---|---|
| At 500 devices: **2,811 roots for 5,000 messages** (1.78 per root); 2,174 of the roots carry at most 2 messages | The number of roots is the lever. Floods already fill their roots |
| Holding every batch one more micro-batch (no forecast), 500 devices: 0.66× the roots, **0.59** micro-batches of added delay per message. With perfect foresight, the same roots for **0.40** | Holding saves a third of the roots. A forecast can at best avoid about a third of the added delay: the holds after which the device sends nothing |
| Every device committing every 2nd micro-batch (fixed longer interval), 500 devices: 0.71× the roots, 0.51 micro-batches of delay | A longer fixed interval delays every device alike, including those that will not send again |
| A prototype forecaster, trained on the train windows: **AUC 0.975** on the test window, against 0.70 for "it sent in this micro-batch, so it will send in the next" | Forecasting is feasible from traffic history alone |
| At 500 devices **34% of the roots carry attack messages**. All attack captures belong to one device; its 50 copies carry the slow attack tails | Holding delays attack traffic too, so the fog's alerts come later. A security-aware variant is needed: never hold a batch the device model flags |
| A flood batch has tens to hundreds of messages | Holding it saves little gas per message and delays many messages, so the decision must weigh the batch size *m* |
| The test-window stream rebuilt from the event tables equals the replayed stream exactly (devices, timestamps, packet numbers; 3,000, 5,000 and 10,000 messages; 10 and 500 devices) | An offline simulation makes exactly the decisions a live run makes, so the whole trade-off can be swept offline and checked live |

---

## 3. Definitions used in this task

| Term | Meaning |
|---|---|
| Round | One micro-batch of 256 messages: the unit in which the pipeline commits, verifies and records |
| Root | One Merkle batch commitment: `commitBatch` at the device gateway plus `recordProcessing` at the edge |
| Hold | Keep a device's batch open, so the device's messages of the next round join the same root |
| `hold_rounds` (H) | The latency budget: a message waits at most H extra rounds |
| `break_even` (N) | The price of latency: delaying N messages by one round is worth one root's gas (~149k gas) |
| Policy | `fixed` (never hold: the task 2 design) · `interval` (every device commits every k-th round) · `rule` (hold if m ≤ N) · `forecast`, the AI (hold if m ≤ p × N) · `oracle` (the rule, only if the device really sends again in time) |
| Merged root / wasted hold | A held batch that later messages joined (one root saved) / one that nothing joined (delay for nothing) |
| Added delay | Rounds a message waits at the gateway (offline); the change in message latency, in seconds (live) |
| Message latency | Per message, from its arrival at the device layer to its cloud result |
| Merkle gas per message | Gas of all `commitBatch` and `recordProcessing` transactions ÷ messages |
| Gas per message | All event-path writes ÷ messages (task 2's definition: commitments, processing records, alert audits, inference records) |

---

## 4. How we will do it

### Step 1: Commit scheduler (`src/device/commit_policy.py`)
- `CommitScheduler.step(events, final)` keeps sealed messages per device and returns the ones to commit now, in
  arrival order. A device's messages are committed together and in order, so the edge's per-device sequence check
  still holds. The stream's last round commits everything.
- `TrafficHistory` is what the gateway knows after each round. Per device it keeps:
  - messages in the last 3 rounds;
  - the gaps between its active rounds;
  - its message rate;
  - the replay time since its last message.

  It also keeps the pace of the whole stream. These form 17 features.
- The five policies of §3 share the same limits: H, N and, optionally, `protect_suspicious`.
- `simulate(stream, policy)` runs a policy over a stream offline, with the same scheduler code.

### Step 2: Forecaster (`src/cloud/train_forecaster.py`, `scripts/train_forecaster.py`)
- **Training streams:**
  - cut from the time split's **train** windows with the replay's own construction, each capture's slice starting
    at a random packet;
  - 4 stream sizes × 6 streams;
  - 7 device counts (10–640). Only 10 is also an experiment value; the experiments use 10–500.
- **Validation:** the same from the validation windows, 2 streams per size, used for every model choice.
- **Label:** does the device send within the next r rounds (r = 1–3)?
- **Model:** scikit-learn `HistGradientBoostingClassifier`, saved as a device-layer model of its own kind
  (`models/real_time/device_forecaster/`), with its hash and metrics.

### Step 3: Pipeline (`src/pipeline.py`)
- `run(commit_policy={...})` builds the scheduler.
- The forecaster is registered and verified on-chain like the layer models (5 models instead of 4).
- Every message carries its arrival time, so the latency of a held message includes its wait.
- The result records the schedule's statistics and per-message latency (all, attack, normal messages).
- `commit_policy=None` keeps every earlier experiment's code path unchanged.

### Step 4: Offline sweep (`run_ai_blockchain.py simulate`)
Every policy over:
- H = 1–3;
- 10 values of N from 1 to 32;
- intervals of 2–4 rounds;
- with and without `protect_suspicious`;
- at 10–500 devices and 5,000 and 10,000 messages.

That is 244 settings per stream. The forecaster's quality on the test window is scored against persistence and the
Poisson rate.

### Step 5: Live experiments (`run_ai_blockchain.py run`, suite `final_task3`)
The task 2 scaling workload (5,000 messages, 2 edges, 1 fog), 4 QBFT validators at 1 block/s, the task 2 client
(local signing, background audit writes). Shared setting: **H = 1, N = 4.**

| Group | What | Runs |
|---|---|---:|
| T3.1 scaling | fixed, rule, AI, oracle at 10, 50, 100, 250, 500 devices | 20 |
| T3.2 seeds | fixed, rule, AI at 500 devices, seeds 43 and 44 | 6 |
| T3.3 settings | 500 devices: interval 2; rule and AI with N = 16; rule and AI with H = 2 | 5 |
| T3.4 protect | 500 devices: rule and AI that never hold a batch the device model flags as an attack | 2 |
| T3.5 single node | fixed and AI on one Anvil node with instant blocks (task 1's chain), 10–500 devices | 10 |

### Step 6: Figures, tables, tests, docs
- `make_figures.py --set final_task3` → `docs/final/task3/`.
- Unit tests: features by hand, the scheduler, every policy, the latency budget, training labels.
- Integration tests:
  - the fixed policy equals the original code path;
  - the AI changes no prediction;
  - live decisions equal the offline simulation;
  - tampering with a held message is detected;
  - a run on QBFT.
- README, project guide and this document.

---

## 5. Expected results

1. **Accuracy and security unchanged:**
   - the same messages reach the same models, so every prediction is identical;
   - no genuine message is rejected;
   - a tampered message from a held batch fails its Merkle proof.
2. **Fewer roots at 500 devices.** The offline values at H = 1, N = 4:

   | Policy | Roots vs fixed | Added delay (rounds) |
   |---|---:|---:|
   | Rule | 0.69× | 0.49 |
   | AI | 0.74× | 0.30 |
   | Oracle | 0.69× | 0.30 |

   That is about −22% (AI) to −27% (rule) gas per message. The AI delays messages about 40% less than the rule for
   about 85% of its saving.
3. **At equal gas, the AI adds less delay than the rule.** On the offline trade-off it should sit between the rule
   and perfect foresight, and ahead of the Poisson rate.
4. **At 10 devices there is little to gain.** Roots are about 20% of the gas, and most batches are full floods.
5. **On QBFT, throughput stays about the same:** the number of rounds does not change. On the instant-block node,
   fewer transactions mean higher throughput.
6. **The scaling drop is reduced, not removed.** One root per device per commit stays the floor.
7. **With `protect_suspicious`, attack messages get almost no added delay,** and the saving is smaller.

---

## 6. Risks and how we handle them

| Risk | Handling |
|---|---|
| The forecaster learns the replay's structure rather than traffic | Trained on train windows at device counts not used in the experiments (except 10); chosen on validation windows; test-window quality reported separately |
| A model choice is tuned on the test data | Features and hyperparameters are chosen on validation only; any change made after looking at test results is reported (§10.2) |
| Offline and live decisions differ | One scheduler code path; an integration test asserts equal roots |
| Holding breaks a security check (order, replay, Merkle proof) | A device's messages are released together and in order; integration tests show no genuine rejection and tampering detected |
| The latency cost outweighs the gas saving | H and N are explicit; the whole trade-off is shown, not one point |
| Holding delays attack alerts | Attack and normal latency reported separately; the `protect_suspicious` variant |

---

## 7. Effort and order
About **1 week**:
- scheduler and forecaster: 2 days;
- pipeline and tests: 1 day;
- offline sweep and live runs: 1 day, mostly run time;
- figures and documentation: 1 day.

The time-window features add-on (after task 1) is still pending.

## 8. Definition of done
- [x] The commit scheduler, the five policies and the forecaster are built. The forecaster is trained on the train
  windows, reproducibly (same hash on a retrain), and registered and verified on-chain.
  *(§10.1; retrain hash `475884c92daf` twice, §10.2; 5 models verified in every AI run, §10.3)*
- [x] The offline sweep covers every policy over the whole trade-off at 10–500 devices; the forecaster is scored on
  the test window against persistence and the Poisson rate. *(2,440 simulations; §10.4–10.5)*
- [x] T3.1–T3.5 are run live. For every run:
  - 0 failed transactions and 0 genuine rejections;
  - predictions identical to the fixed policy;
  - the 4 nodes consistent;
  - live roots equal to the offline simulation.

  *(43 of 43 runs, §10.3)*
- [x] Figures and tables regenerated (`docs/final/task3/`). *(figures 19–24, 5 tables; the earlier sets regenerate
  byte-identically)*
- [x] Tests and documentation updated; all tests pass. *(119 passed, ruff clean; README, project guide, data usage,
  this document)*

## 9. Note for the final report
State exactly what the AI decides and what it does not:
- it decides when the gateway closes each device's Merkle batch, from traffic history only;
- it never sees or changes message content, labels or any model's prediction;
- the gas saved is real gas on a real QBFT network, and the latency it adds is measured per message;
- the comparison includes a fixed rule and perfect foresight, so the AI's share of the gain is explicit.

One limit of the design stays: one root per device per commit. A gateway-wide root per round would remove the
device-count effect entirely, but it changes the contract and gives up the on-chain per-device binding (§10).

---

## 10. Implementation and results (4 Nov 2026)

### 10.1 What was built

| Step | File(s) | Result |
|---|---|---|
| 1 Scheduler | `src/device/commit_policy.py` | `CommitScheduler` (open batches per device, released together and in order); `TrafficHistory` (17 features, online); the five policies; `simulate` (offline, same code) |
| 2 Forecaster | `src/cloud/train_forecaster.py`, `scripts/train_forecaster.py`, `configs/models.yaml` (`forecaster`), `src/cloud/model_registry.py` (a model *kind* with its own folder) | `device-forecaster-gradient_boosting-475884c92daf`: 1,327,144 training samples from 24 train-window streams at 7 device counts; fitted in 13 s |
| 2 Streams | `src/data/preparation/realistic.py` (`window_packets`, `timing_stream`) | The replay's construction on any window. On the test window it equals the replayed stream exactly |
| 3 Pipeline | `src/pipeline.py`, `src/device/service.py`, `src/device/blockchain_client.py`, `src/cloud/service.py` | `run(commit_policy=…)`. The forecaster is registered and verified on-chain (5 models per run). Latency is measured per message from its arrival. Each result records the schedule and the per-message latency |
| 4–5 Experiments | `scripts/run_ai_blockchain.py` (`simulate`, `run`), suite `final_task3`, `scripts/run_final_task3.sh` | Offline sweep: 2,440 simulations in 41 s (6 min before the forecaster ran on one thread, §10.2 item 9). 43 live runs |
| 6 Figures | `scripts/make_figures.py --set final_task3` → `docs/final/task3/` | Figures 19–24; 5 tables (runs, scaling, at 500 devices, trade-off, forecaster) |
| Tests | `tests/unit/test_commit_policy.py` (14), `tests/integration/test_ai_blockchain.py` (5), `tests/security/test_model_integrity.py` (+1: a tampered forecaster is refused) | 119 tests pass |

### 10.2 Decisions and facts found while building

1. **The decision weighs gain against cost:** hold a batch of *m* messages if *m ≤ p × N*.
   - A first prototype held a batch whenever *p ≥ 0.5*, whatever its size.
   - Offline, both forms lie on the same gas–latency curve.
   - The final form adds the batch size and makes the price of latency one explicit setting, the same for every
     policy.
2. **The forecaster was changed once, after a test-window result.** This is disclosed here because it touches the
   protocol of §6.
   - The first version had 15 features.
   - On the test window its AUC was 0.97 overall but only 0.73–0.80 on single-message batches: the cases that
     decide whether a hold pays off.
   - Two features were added: *rounds until the device's next message is due*, and the *trend in stream pace*.
   - The new version was chosen on the **validation** windows only: AUC on single-message batches 0.9153 → 0.9174.
   - A larger model (63 leaves, 500 iterations) reached 0.9221 on validation. It was not adopted, because the gain
     was marginal.
3. **One test stream is not an outlier.** The validation streams vary widely: AUC on single-message batches ranges
   from 0.60 to 0.97 between streams and device counts. The test window's 0.80–0.90 (50–500 devices) is inside
   that range.
4. **"Perfect foresight" bounds the rule, not every policy.** It is the rule's decision with the future known.
   - The AI's threshold *p × N* is continuous, so it reaches points between the rule's integer steps (hold
     batches of ≤ 1, ≤ 2, … messages).
   - At a few points the AI therefore needs *less* delay than "perfect foresight" for the same roots.
   - Equal-gas comparisons (§10.5) use each policy's lower convex envelope, starting from the fixed design
     (0 delay, all roots). Interpolating between two settings is the same as mixing them.
5. **The non-learned reference is weak where the stream changes.** The Poisson rate scores AUC 0.73 on validation
   but only 0.36–0.76 on the test window. A flood that is about to end looks, by its rate, the most certain to
   continue.
6. **Training is deterministic:** two fresh fits gave the registered model's hash, `475884c92daf`.
7. **Live decisions equal offline decisions:**
   - the stream rebuilt from the event tables equals the replay;
   - the scheduler is one code path;
   - live roots equal the simulated roots in every run (§10.3).
8. **The fixed design runs through the same scheduler** (policy `fixed`), so every run returns its cloud rows. An
   integration test shows it equals the original code path: the same roots, gas and accuracy.
9. **The forecaster first ran on every core; the 15 AI runs were re-run on one thread.**
   - The first pass of the live runs used scikit-learn's default: each prediction spread over all 10 cores.
   - A round asks about ~120 devices: 19–25 ms per round that way, against 2.0 ms on one thread. Live, next to the 4
     Besu validators, the AI's device stage took 60–90 ms longer than the rule's.
   - The forecaster now predicts on one thread, as the layer models already do (`n_jobs=1`). A whole scheduling step
     takes 2.3–2.8 ms per round, and every decision is unchanged (the same roots).
   - The 15 AI runs were re-run; no other run uses the forecaster. The first-pass results are kept in
     `experiments/results/final_task3/runs_first_pass_forecaster_all_cores.jsonl`.
   - **The effect on latency was smaller than expected.** At 500 devices the seed-42 run went from 4.79 to 4.35 s,
     but seeds 43 and 44 changed by at most 0.07 s (the mean went from 4.47 to 4.34 s). The rest of the difference
     was the block timing of §10.6, not the forecaster.
10. **A first table bug, fixed.** The per-wait latency split (§10.6) replays each run's decisions offline. It first
    ran without the device model's flags, so the two "attacks never held" runs looked unprotected. It now reads each
    message's device prediction from the run's own rows, and checks that the replayed roots equal the live ones, in
    all 43 runs.

### 10.3 How the experiments were run
- **Forecaster and offline sweep, 4 Nov 2026:**
  - `train_forecaster.py`: 25 s;
  - `run_ai_blockchain.py simulate`: 2,440 simulations in 6 min. Re-run on 5 Nov 2026 with the forecaster on one
    thread: 41 s, and both output files byte-identical (no decision changed).
- **Live runs:**
  - `run_ai_blockchain.py run`, 4 Nov 2026, 12:18–13:09 IST: 43 runs;
  - the 15 AI runs again from 13:11 to 13:28, after the one-thread change (§10.2 item 9).

  Log: `experiments/logs/final_task3.log`. Every run is in `experiments/results/final_task3/runs.jsonl`; the
  messages each delivered, with every layer's prediction, are in `rows/*.parquet`. Figures and tables are in
  `docs/final/task3/`.
- **Data:**
  - task 2's scaling workload: 5,000 realistic-replay messages, the 10 real devices split over 10–500 devices,
    micro-batches (rounds) of 256;
  - 2 edges, 1 fog;
  - the task 2 client: local signing, audit records confirmed in the background.
- **Totals:** 43 runs and 215,000 messages. 33 runs (165,000 messages) on a 4-validator QBFT network at 1 block/s;
  10 on one Anvil node mining every transaction at once.

**Checks passed by every run:**
- 5,000 of 5,000 messages processed, 0 rejected, 0 failed transactions.
- Every layer's prediction is identical, message by message, to the fixed run with the same chain, devices and seed.
- Cloud macro-F1 is 0.7531 and the fog raised 2,389 alerts in every run. Holding changes neither the predictions
  nor the alerts, because each device's messages keep their order and timestamps.
- Live roots equal the offline simulation's (43 of 43), with one processing record per root.
- Every QBFT run ends with all 4 nodes holding the same chain.
- The AI runs register and verify 5 models on-chain (the forecaster included); all other runs verify 4.
- **The fixed policy reproduces task 2's T2.4:**
  - the same roots and gas per message at every device count: 15,620, 27,253, 39,840, 68,713 and 96,304;
  - throughput within 1.4 msg/s of task 2's: 91.0, 80.7, 82.0, 79.5 and 69.5 msg/s, against 91.0, 82.1, 80.7, 80.7
    and 69.5.

### 10.4 The forecaster
Table `forecaster.csv`.

**Validation windows**

These are the numbers recorded in the model's provenance file: 461,294 samples, 71.4% positive.

| Forecaster | ROC-AUC | Brier score | Accuracy |
|---|---:|---:|---:|
| **AI (gradient boosting)** | **0.944** | **0.080** | **0.891** |
| Persistence ("it sent in this round") | 0.642 | — | 0.739 |
| Poisson arrivals at its recent rate | 0.729 | 0.185 | — |

**Test window (the replayed messages, 5,000-message streams)**

| Devices | Samples | Positive rate | AI ROC-AUC | Persistence ROC-AUC | Poisson ROC-AUC | Single-message batches: AI / Poisson ROC-AUC |
|---:|---:|---:|---:|---:|---:|---|
| 10 | 362 | 0.80 | 0.936 | 0.702 | 0.355 | 0.917 / 0.667 (7 samples) |
| 50 | 1,716 | 0.78 | 0.927 | 0.701 | 0.374 | 0.847 / 0.681 |
| 100 | 3,207 | 0.77 | 0.922 | 0.694 | 0.382 | 0.867 / 0.669 |
| 250 | 6,928 | 0.71 | 0.905 | 0.674 | 0.460 | 0.795 / 0.539 |
| 500 | 11,313 | 0.62 | 0.871 | 0.630 | 0.569 | 0.809 / 0.708 |

On the 10,000-message streams the AI's AUC is 0.904–0.934.

**What this shows:**
- The forecaster generalises from the train windows to the test window, and to device counts it was not trained on
  (50, 100, 250, 500).
- It is weakest exactly where decisions are hardest: single-message batches of sparse devices (AUC about 0.8).
  That limits how close it can come to perfect foresight (§10.5).

### 10.5 The whole trade-off, offline
Figure 21, table `tradeoff.csv`. The same scheduler code as the live runs, on the 5,000-message workload.

**The live setting (H = 1, N = 4).** Roots relative to fixed batching, and added delay in rounds per message:

| Devices | Rule | AI | Poisson-rate forecast | Perfect foresight |
|---:|---|---|---|---|
| 10 | 0.934× · 0.006 | 0.962× · 0.002 | 0.953× · 0.004 | 0.934× · 0.004 |
| 50 | 0.798× · 0.064 | 0.839× · 0.044 | 0.833× · 0.048 | 0.798× · 0.050 |
| 100 | 0.672× · 0.195 | 0.771× · 0.101 | 0.777× · 0.112 | 0.672× · 0.147 |
| 250 | 0.687× · 0.273 | 0.719× · 0.188 | 0.731× · 0.193 | 0.687× · 0.187 |
| 500 | 0.692× · 0.489 | 0.742× · 0.303 | 0.737× · 0.347 | 0.692× · 0.300 |

At the same price of latency, the AI holds fewer batches. It gives up some of the rule's saving and avoids most of
its useless waiting: at 500 devices, 84% of the rule's root reduction for 62% of its delay.

**At equal gas, the AI adds less delay than the rule.** The table gives the added delay (rounds per message) each
policy needs to cut the roots to a target, read off its envelope over the whole sweep of N:

| 500 devices | Roots ≤ 90% | Roots ≤ 80% | Roots ≤ 70% |
|---|---:|---:|---:|
| Rule (H = 1) | 0.138 | 0.276 | 0.468 |
| **AI (H = 1)** | **0.084** (−39%) | **0.197** (−28%) | **0.401** (−14%) |
| Poisson rate (H = 1) | 0.107 | 0.215 | 0.435 |
| Perfect foresight (H = 1) | 0.056 | 0.118 | 0.282 |

**Across all 60 comparisons** (10–500 devices; H = 1–3; root targets 50–90%, wherever every policy reaches them):
- **The AI needs less delay than the rule in 59.** The median is 15% less; the range runs from 39% less to 9% more.
  The one exception is 50 devices, H = 2, roots ≤ 90%: 0.021 vs 0.020 rounds.
- **It never needs more than the Poisson-rate forecast.**
- **It captures a median of 50% of the gain perfect foresight gives over the rule.**

On the 10,000-message streams the AI is ahead of the rule in 57 of 62 comparisons (median 12% less delay). The other
five are within 6%.

**Fixed batching with a longer interval is the worst of the fixed designs.** Every device commits every k-th round:
- k = 2 at 500 devices: 0.708× the roots for 0.512 rounds of delay;
- that is fewer roots saved, for more delay, than the rule (0.692× for 0.489) or the AI (0.742× for 0.303).

The interval also delays attack messages most: 0.49 rounds each.

**Longer budgets save more and cost more.** At 500 devices:
- H = 2: 0.65× the roots for 0.48 rounds (AI, N = 4), and at most 0.50× for about 1 round (N ≥ 12);
- H = 3: 0.49× for 0.92 rounds (N = 6), and 0.41× for 1.6 rounds (N = 32).

**Attack traffic.** At 500 devices (AI, N = 4), attack messages wait 0.231 rounds on average and normal messages
0.402. With `protect_suspicious`:
- attack messages wait 0.043 rounds. The remainder are attacks the device model does not flag;
- the roots rise from 0.742× to 0.825×.

### 10.6 Live: gas, latency and throughput from 10 to 500 devices (T3.1)
Figures 19, 20 and 24, table `scaling.csv`. Seed 42, H = 1, N = 4.

| Devices | Gas per message: fixed / rule / **AI** / perfect foresight | Message latency (s): fixed / rule / **AI** / perfect foresight | Throughput (msg/s): fixed / **AI** |
|---:|---|---|---|
| 10 | 15.6k / 15.4k / **15.5k** / 15.4k | 2.71 / 2.78 / **2.77** / 2.72 | 91.0 / **89.2** |
| 50 | 27.3k / 24.3k / **24.9k** / 24.3k | 3.04 / 3.18 / **3.13** / 3.14 | 80.7 / **81.9** |
| 100 | 39.8k / 30.9k / **33.6k** / 30.9k | 2.99 / 3.58 / **3.30** / 3.49 | 82.0 / **82.0** |
| 250 | 68.7k / 51.1k / **52.9k** / 51.1k | 3.10 / 3.89 / **3.64** / 3.56 | 79.5 / **80.7** |
| 500 | 96.3k / 70.4k / **74.6k** / 70.5k | 3.56 / 4.89 / **4.35** / 4.19 | 69.5 / **75.8** |

**Gas falls where the devices are many:**
- At 10 devices the AI saves 0.8% of the gas: its roots are mostly full floods.
- At 500 it saves **22.5%** (96.3k → 74.6k gas per message); the rule and perfect foresight save 26.8%.
- Gas per message still grows from 10 to 500 devices: 6.2× fixed, **4.8× AI**, 4.6× rule.

**At the same price of latency, the AI adds less latency than the rule:**

| Devices | AI: share of the rule's root saving | AI: share of the rule's added latency |
|---:|---:|---:|
| 100 | 70% | 52% (+0.31 vs +0.59 s) |
| 250 | 90% | 68% (+0.54 vs +0.80 s) |
| 500 | 84% | 59% (+0.79 vs +1.33 s, seed 42; 69% on the 3-seed means of §10.7) |

**How the latency arises.** Table `runs.csv` splits each run's messages by the rounds they waited. In the runs at
H = 1, N = 4:
- a message that waits no round takes 2.7–3.4 s;
- a message that waits one round takes 5.6–6.8 s;
- with H = 2, a message that waits two rounds takes 8.9 s.

Rounds with fewer transactions are shorter, so in the N = 16 and protected runs a held message took 5.1–5.5 s.

So a held message pays about one extra round (~3 s), and the added mean latency is roughly the share of held
messages × 3 s. At 500 devices the rule holds 2,445 messages, the AI 1,517 and perfect foresight 1,499 of 5,000.

**Throughput on QBFT stays about the same or rises.** Every policy runs the same 20 rounds. Fewer transactions per
round make rounds shorter: at 500 devices the AI's throughput is 75.8 msg/s against 69.5 fixed (+9%), and the rule's
78.2.

**On the instant-block node the AI also restores throughput** (figure 24, dashed). There every root is mined as its
own block:

| Devices | 10 | 50 | 100 | 250 | 500 |
|---|---:|---:|---:|---:|---:|
| Fixed (msg/s) | 2,415 | 1,060 | 603 | 256 | 143 |
| AI (msg/s) | 2,272 (−6%) | 1,151 (+9%) | 746 (+24%) | 369 (+44%) | 210 (+47%) |

- The fall from 10 to 500 devices shrinks from 16.9× to 10.8×.
- Latency there changes by −0.14 to +0.01 s with the AI (1.72 vs 1.77 s at 500 devices): every round is shorter,
  which offsets the waiting.
- At 10 devices the AI's few milliseconds per round cost 6%, because a round takes only 0.1 s.

### 10.7 Live at 500 devices: seeds, other settings, attack traffic (T3.2–T3.4)
Figures 22 and 23, table `at_500_devices.csv`. Mean over the runs given; H = 1 and N = 4 unless stated.

| Setting | Runs | Roots vs fixed | Gas per message | Latency mean / p95 (s) | Added latency | Attack / normal latency (s) | Throughput (msg/s) |
|---|---:|---:|---:|---|---:|---|---:|
| Fixed | 3 | 1.000 | 96.3k | 3.52 / 4.67 | — | 3.37 / 3.74 | 70.2 |
| Rule | 3 | 0.692 | 70.4k (−26.8%) | 4.71 / 7.34 | +1.18 s | 4.06 / 5.58 | 80.8 |
| **AI** | 3 | **0.742** | **74.6k (−22.5%)** | **4.34 / 8.08** | **+0.82 s** | **4.00 / 4.81** | 76.1 |
| Perfect foresight | 1 | 0.692 | 70.5k (−26.8%) | 4.19 / 7.09 | +0.64 s | 4.07 / 4.36 | 77.0 |
| Fixed interval, every 2nd round | 1 | 0.708 | 71.8k (−25.5%) | 4.22 / 5.76 | +0.66 s | 3.87 / 4.69 | 116.4 |
| Rule, N = 16 | 1 | 0.656 | 67.4k (−30.0%) | 4.53 / 6.99 | +0.97 s | 3.90 / 5.38 | 92.6 |
| AI, N = 16 | 1 | 0.660 | 67.7k (−29.7%) | 4.44 / 6.99 | +0.89 s | 4.02 / 5.02 | 90.9 |
| Rule, H = 2 | 1 | 0.574 | 60.6k (−37.1%) | 5.13 / 9.04 | +1.57 s | 3.93 / 6.75 | 86.3 |
| AI, H = 2 | 1 | 0.652 | 67.1k (−30.3%) | 4.61 / 8.99 | +1.05 s | 3.83 / 5.66 | 82.0 |
| Rule, attacks never held | 1 | 0.805 | 80.0k (−17.0%) | 4.18 / 7.02 | +0.62 s | 3.32 / 5.34 | 77.0 |
| **AI, attacks never held** | 1 | **0.825** | **81.7k (−15.2%)** | **4.01 / 7.99** | **+0.45 s** | **3.43 / 4.80** | 73.5 |

**Seeds.** A seed changes only event ids and device keys, so the decisions, roots and gas are identical. Latency:
- fixed 3.41–3.61 s;
- rule 4.60–4.89 s;
- AI 4.31–4.37 s.

**On the 3-seed means, the AI gives 84% of the rule's root saving for 69% of its added latency** (+0.82 vs +1.18 s).

**Why the AI adds less delay** (figure 22). Among the batches held at least one round:
- the rule held 1,745, and 879 of them (50%) waited for nothing;
- the AI held 1,081, and 355 (33%) waited for nothing;
- perfect foresight held 866, none for nothing.

The AI keeps most of the useful holds (726 of 866) and avoids most of the useless ones.

**Who pays the delay** (figure 23):
- Without protection, attack messages wait too: the AI raises their mean latency from 3.43 s (fixed, seed 42) to
  4.03 s.
- With `protect_suspicious`, the AI's attack messages arrive in **3.43 s, the same as fixed (seed 42)**, while it still saves
  15.2% of the gas. The rule with protection: 3.32 s and 17.0%.
- Normal traffic pays the whole delay instead: 4.80 s.

**Longer budgets and a cheaper price of latency:**
- N = 16 or H = 2 save about 30% of the gas for +0.9 to +1.1 s with the AI.
- The rule with H = 2 saves 37.1% for +1.57 s, and a p95 of 9.0 s.

**Two timing effects of this pipeline.** They are explained here because they make single live latencies noisy, and
they flatter one baseline.
1. **Rounds are quantized by the blocks.** A round takes about 3 or 4 block periods: one for the device commitment
   and one for each edge's processing record, plus processing that may cross a block boundary.
   - Runs with identical decisions differ by up to 0.5 s in mean latency: the AI with attacks never held took 3.81 s
     in the first pass and 4.01 s in the re-run.
   - This is why 500 devices was run with 3 seeds.
2. **The replay is not paced** (as in tasks 1–2): a round starts as soon as the previous one ends. A round in which
   every device holds its batch commits nothing and takes ~0.1 s.
   - The fixed interval holds everything in every other round, so live it behaves like rounds of 512 messages:
     +0.66 s latency and 116 msg/s.
   - Offline it costs 0.51 rounds of waiting per message, more than the AI (0.30).
   - In a deployment where messages arrive in real time, a round lasts as long as its messages take to arrive, and
     the offline rounds measure (§10.5) is the right one for comparing latency.

### 10.8 Does it fix the scaling drop?
**Partly.**
- **Gas per message from 10 to 500 devices:**
  - fixed: **6.2×** (15.6k → 96.3k);
  - AI: **4.8×** (74.6k); with H = 2 or N = 16, **4.3–4.4×** (67.1k–67.7k);
  - rule: 4.6×.
- **On the instant-block node,** the throughput fall shrinks from 16.9× to 10.8×.

**What remains is structural:** one root per device per commit.
- At 500 devices each device sends about 10 messages in 20 rounds, so even a 3-round budget keeps 0.41× of the roots
  at best (offline, H = 3, N = 32), for 1.6 rounds of delay per message.
- **A gateway-wide root** (one root per round over all devices) would remove the device-count effect. This is an
  estimate, not measured: ~20 `commitBatch` and ~40 `recordProcessing` transactions for 5,000 messages, so Merkle
  gas of about 0.8k per message instead of 58k–84k.
- But it needs a contract change, and it gives up two things the per-device design has:
  - the on-chain check that the device is registered and active for each batch (`UnknownDevice`);
  - per-device commitment records.

  Each message would still carry its device signature and Merkle proof. This is a protocol decision rather than an
  AI one, and is left as future work.

### 10.9 Expected vs measured

| # | Expected (§5) | Measured | Verdict |
|---|---|---|---|
| 1 | Accuracy and security unchanged | Every prediction identical in 43 runs; F1 0.7531 and 2,389 alerts in all; 0 rejected; a tampered message from a held batch fails its Merkle proof (integration test) | Confirmed |
| 2 | At 500 devices: rule 0.69×, AI 0.74×, foresight 0.69× roots; −22 to −27% gas | Exactly these roots live (live = offline); gas −26.8% (rule), −22.5% (AI) | Confirmed |
| 3 | At equal gas the AI adds less delay than the rule | Offline: 59 of 60 comparisons, median −15%. Live at the same N: +0.82 vs +1.18 s (3 seeds) | Confirmed |
| 4 | Little to gain at 10 devices | −0.8% gas, +0.06 s | Confirmed |
| 5 | QBFT throughput about the same; higher on the instant-block node | QBFT: +9% (AI) at 500 devices, within ±2% elsewhere; instant node: +9% to +47% from 50 devices, but −6% at 10 | Confirmed, except 10 devices on the instant node |
| 6 | The scaling drop reduced, not removed | Gas growth 6.2× → 4.8× (AI), 4.3× (AI, H = 2) | Confirmed |
| 7 | With protection, attack messages barely delayed | AI: attack latency 3.43 s, as fixed; saving 15.2% instead of 22.5% | Confirmed |

### 10.10 Limitations and what remains
- **The replay is not paced, and rounds are block-quantized** (§10.7): live latencies of single runs vary by up to
  0.5 s, and the fixed interval looks better live than it would with real-time arrivals. Offline rounds waited are
  the deployment-independent measure.
- **One test stream** (the test window) for the live runs. Offline, 2 stream sizes. The validation streams show that
  forecast quality varies widely between streams (§10.2 item 3).
- **The forecaster is good, not perfect,** where it matters: AUC ~0.8 on single-message batches, and a median of half
  of the gain perfect foresight would give over the rule.
- **The forecaster sees only timing.** It could also use, for example, the device model's attack probability.
- **Holding delays the on-chain anchoring** of a message by up to H rounds. Its content is still protected in the
  meantime by the device's signature, which the edge checks.
- **One root per device per commit** limits the gain at scale (§10.8).
- **Next:** the time-window features add-on (after task 1), the last item of the final-phase plan.
