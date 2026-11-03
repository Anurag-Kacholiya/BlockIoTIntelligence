# Final task 1: Real timestamps and real device identity

**Goal:** replace the two things the mid-term simulated, *which device sent a message* and *when*, with the
real values recorded in the Edge-IIoTset packet captures, then measure how well the models work on **devices
they have never seen**.

Status: **complete (28 Oct 2026; step 8 finished 3 Nov 2026, §10.10)**. What was built, how it differs from this
plan, and the results are in [§10](#10-implementation-and-results-28-oct-2026). §2–§9 are the original plan, kept
unchanged for the record.
All facts in §2 were measured on our downloaded data.

---

## 1. What it is and why it matters

### The mid-term limitation
- **Timing was simulated.** The CSVs lost the date part of `frame.time`, and each attack sits in its own time
  slot (label leakage). The simulator therefore gave every message a synthetic timestamp.
- **Device identity was simulated.** The selected file has no device ID, and the IP column leaks the label.
  Messages were assigned to 10–500 logical devices at random.

### What this task gives
1. **Real timestamps** (full date and time, microsecond precision) for every message.
2. **Real devices:** one IoT sensor = one device, with its real traffic rate and pattern.
3. **A new experiment:** *generalisation to unseen devices*. Train without a sensor, then test on it.
4. **The foundation for the time-window features** (an add-on after this task), which need real time.

### Questions it answers in the final
- "Is your data realistic?" → real devices, real timing.
- "Would your system work on a sensor it was not trained on?" → the unseen-device experiment.
- "Does the fog layer add anything beyond the edge?" → only answerable with real time (time-window features).

---

## 2. Pre-study: what we measured on the data (Oct 2026)

### 2.1 The 24 packet captures
- **21.1 million packets** in standard pcap format (Ethernet, microsecond timestamps). All 24 parse in ~12 s in Python.
- **Each capture is a separate recording session**, on dates from 21 Nov 2021 to 5 Jan 2022.

| Capture | Packets | Start (UTC) | Notes |
|---|---:|---|---|
| Temperature_and_Humidity | 1,629,749 | 2021-11-21 10:44 | 4 idle gaps > 1 h (multi-day recording) |
| Water_Level | 2,302,497 | 2021-12-28 03:48 | 7-day gap |
| Modbus | 159,514 | 2021-12-20 00:22 | 16-day gap |
| Distance / Heart_Rate / phValue | 1.14 M / 170 k / 760 k | 27–28 Dec 2021 | continuous, 0.4–1.2 h |
| Flame / IR / Sound / Soil_Moisture | 1.07–1.51 M each | 4–5 Jan 2022 | continuous, 0.4–2.3 h |
| DDoS ICMP / TCP SYN / UDP / HTTP | 2.9 M / 2.0 M / 3.2 M / 229 k | 24–25 Nov 2021 | 5–9 minutes each |
| Password | 1,053,893 | 2021-12-04 | 15-hour gap |
| Ransomware | 11,030 | 2021-12-02 | 30-hour gap |
| Backdoor, Port scan, SQLi, XSS, Uploading, Vuln. scanner, MITM, OS fingerprint | 1 k – 266 k | Nov–Dec 2021 | Vuln. scanner has 1 packet with a corrupt timestamp |

- **Out-of-order packets:** a few hundred to ~5,000 per capture (normal for captures); fixed by sorting.

### 2.2 Device identity (who talks to whom)
- **Each normal sensor sits on its own subnet** and talks to one partner host:

| Sensor (capture) | Host pair |
|---|---|
| Distance (ultrasonic) | 192.168.1.101 ↔ 192.168.1.128 |
| pH | 192.168.2.116 ↔ 192.168.2.194 |
| Heart rate | 192.168.3.12 ↔ 192.168.3.18 |
| Water level | 192.168.4.30 ↔ 192.168.4.73 |
| IR receiver | 192.168.5.47 ↔ 192.168.5.46 |
| Sound | 192.168.6.56 ↔ 192.168.6.100 |
| Flame | 192.168.7.62 ↔ 192.168.7.55 |
| **Modbus** | **192.168.7.55 ↔ 192.168.7.62 (same hosts as Flame)** |
| Soil moisture | 192.168.8.104 ↔ 192.168.8.163 |
| Temperature & humidity | 192.168.0.128 ↔ 192.168.0.101 |

  → **Device ID must be the sensor (capture) name, not the IP**, because Modbus and Flame share IPs.
- **Attacks:** almost all are between attacker **192.168.0.170** and victim **192.168.0.128**. The DDoS floods
  use millions of spoofed source IPs. Attacks therefore target one host, not the 10 sensors.
- **MITM** is 79% non-IP traffic (ARP spoofing), so its identity comes from ARP fields/MACs.

### 2.3 CSV rows can be matched to their packets
- **CSV times are UTC+1.** Offsets of 0 and −1 h match nothing; +1 h matches.
- **Raw per-sensor CSV (Heart_Rate):** time of day + source/destination IP → **165,319 of 165,319 rows (100%)
  match exactly one packet**.
- **Selected DNN file (20,000-row sample) against all captures:** **94.3% unique match**, 0.2% ambiguous,
  5.6% unmatched. The unmatched rows are almost all **DDoS_UDP (1,102) and MITM (15)**, whose `frame.time`
  field is corrupt in the CSV. They need a fallback (§4, step 3).

### 2.4 The selected file's "normal" class is one sensor
In the 20,000-row sample, **14,429 of 14,460 normal rows (99.8%) come from the Temperature_and_Humidity
capture**; the rest are Modbus (28) and TCP SYN (3). **The mid-term models learned "normal" from essentially
one device.** The other 9 sensors' normal traffic exists only in the raw per-sensor files.

### 2.5 Raw files use a different value encoding
The raw CSVs have the same 63 columns, but store some fields as **hexadecimal text**: `tcp.flags`
(`0x00000012`), `tcp.checksum` (`0x0000bb14`), `mqtt.conflags`, `mqtt.hdrflags`. The selected file stores the
same values as decimals (`18.0`, `47892.0`). Converting hex to decimal reproduces the selected encoding
exactly, verified on a matched packet: all other differences are formatting only (`0` vs `0.0`).

### 2.6 Pilot: mid-term models on sensors they never saw
Mid-term models applied to 20,000 normal messages from each raw sensor file (hex decoded). Any "attack"
prediction is a **false alarm**.

| Sensor | Device FP | Edge FP | Cloud FP | Note |
|---|---:|---:|---:|---|
| Temperature & humidity (in training) | 0.5% | 0.5% | 0.5% | sanity check |
| Distance, Flame, IR, Soil, Sound, Water, pH | 0.0–0.1% | 0.0–0.1% | 0.0–0.1% | generalise well |
| Heart rate | 3.1% | **8.9%** | 0.2% | partly generalises |
| **Modbus** | **100%** | **100%** | **38.6%** (mostly "MITM") | does not generalise; *provisional* (column audit pending) |

**Reading:** the models generalise to other MQTT sensors but fail on a different protocol (Modbus). This is
exactly what the unseen-device experiment is for, and it is a strong, honest final-report result.

---

## 3. Definitions used in this task

| Term | Definition |
|---|---|
| **Device** | One IoT sensor = one capture (10 normal devices). Attack traffic is assigned to the **victim** host 192.168.0.128; attacker IPs are recorded but **never used as features** |
| **Real timestamp** | The packet's capture time (UTC, µs) from the pcap |
| **Session** | A continuous part of a capture; split where there is an idle gap > 1 hour (configurable) |
| **Replay time** | Real timestamp shifted so every session starts at a common time 0. Keeps real gaps and bursts, removes date (which would reveal the class) |

---

## 4. How we will do it

### Step 1: Packet index (≈1 day)
Parse all 24 pcaps into one table (Parquet): `capture, packet_no, ts_utc_us, src_ip, dst_ip, length, protocol`.
- Sort by time (fixes out-of-order packets); drop the 1 corrupt timestamp.
- Split into sessions at gaps > 1 h.
- No new tools needed (pure Python; ~12 s for all 21 M packets).

### Step 2: Normalise the raw CSVs to the selected encoding (≈1 day)
- Decode hex fields → decimal; unify numeric formatting.
- Apply the **same cleaning as the mid-term**: the publisher's 15 leaky columns dropped, categorical "0"/"0.0" merged.
- **Column audit** for Modbus, DDoS_UDP and MITM raw CSVs (`frame.time` holds an IP or "0.0"): find the shift
  and realign, or rebuild those files from the pcaps with `tshark` (`brew install wireshark`). The 61 features
  are Wireshark field names, so `tshark -T fields -e …` reproduces them directly.

### Step 3: Recover real timestamps (≈1–2 days)
- **Raw CSVs:** match each row to its packet in its own capture by time of day (UTC+1, µs) + source/destination
  IP → full UTC timestamp. Expected ≈100% (measured 100% on Heart_Rate).
- **Selected DNN file:** match across all captures → each row gets its **source capture** and full timestamp
  (measured 94.3%).
- **Fallback** for rows with a corrupt time field (DDoS_UDP, MITM): order alignment within the capture where
  counts match (MITM 1,229 = 1,229), otherwise tshark re-extraction.
- Report the match rate per file; never guess a timestamp.

### Step 4: Device identity (≈0.5 day)
- Device = sensor name for normal traffic; victim host for attack traffic.
- Write the mapping to `data/metadata/device_map.yaml` (capture → device ID, host IPs, protocol, sensor type).

### Step 5: Build the "realistic" dataset v2 (≈1–2 days)
- **Normal:** all 10 sensors (11.2 M raw rows). **Attacks:** the 14 attack captures (9.7 M rows).
- Same de-duplication and leakage rules as the mid-term; keep `device_id`, `session_id`, `ts_utc_us` as
  **metadata only** (never model features).
- To keep laptop runs practical, build a **stratified sample** (by class *and* by device) of a few million rows.
- Write manifests (source hashes, counts, seed), as for the mid-term data.

### Step 6: Realistic replay (≈1–2 days)
- New simulator mode: each device replays its own messages with their **real inter-arrival times**; sessions
  are aligned to a common start and interleaved by replay time. A speed factor (e.g. 10×) keeps runs short.
- The 256-message processing window and the blockchain modes stay unchanged, so results stay comparable.

### Step 7: Three ways to split the data (≈1 day)
| Split | What it measures |
|---|---|
| **A. Random stratified 70/15/15** | Direct comparison with the mid-term |
| **B. Time-based:** train on the earlier part of each session, test on the later part | Realistic deployment (no learning from the future) |
| **C. Leave-one-device-out:** train on 9 sensors' normal traffic + attacks; test on the 10th sensor's normal traffic; repeat for all 10 | **Generalisation to unseen devices** (false-alarm rate per sensor) |

Attack traffic in split C is split by time, since attacks are not per sensor.

### Step 8: Retrain and re-run (≈2 days)
- Retrain the same model families on dataset v2 (device tree, edge/fog forests, 3 cloud candidates).
- Re-run accuracy, tampering, security, cost and scaling on the realistic replay; produce the leave-one-device-out table.

### Step 9: Code, tests and documentation (included above)
| New / changed file | Purpose |
|---|---|
| `src/data/ingestion/pcap_index.py` | Parse captures → packet index (step 1) |
| `src/data/preparation/raw_normalize.py` | Hex decoding and encoding parity with the selected file (step 2) |
| `src/data/preparation/timestamps.py` | Row ↔ packet matching, fallbacks, match-rate report (step 3) |
| `src/data/preparation/devices.py` + `data/metadata/device_map.yaml` | Device identity (step 4) |
| `scripts/build_realistic_dataset.py` | Builds dataset v2 + manifests (step 5) |
| `src/device/simulator.py` | New real-time replay mode (step 6) |
| `src/data/preparation/splits.py` | Time-based and leave-one-device-out splits (step 7) |
| `configs/datasets.yaml` | v2 settings: session gap, UTC offset, sample sizes |
| Tests | hex decoding, matching on a small fixture, no device/time leakage across splits, replay ordering |

---

## 5. Expected results

| Result | Expectation | Evidence so far |
|---|---|---|
| Timestamp recovery, raw sensor files | ≈100% | 100% on Heart_Rate |
| Timestamp recovery, selected file | ≈94% direct; rest via fallback | 94.3% on a 20 k sample |
| Unseen MQTT sensors (leave-one-out) | Low false alarms (≈0–1%) | 0.0–0.2% for 7 sensors in the pilot |
| Unseen heart-rate sensor | Some false alarms | 8.9% at the edge in the pilot |
| Unseen **Modbus** device | High false alarms: a different protocol is not recognised as normal | 100% edge / 38.6% cloud in the pilot (provisional) |
| Training on all 10 sensors | False alarms on known devices drop sharply | To be measured |
| Overall accuracy on dataset v2 | May drop slightly vs the mid-term, because "normal" is now 10 devices, not 1 | To be measured; report honestly |
| Real per-device traffic | Uneven device rates (sensors differ by orders of magnitude) change the Merkle batch sizes and scaling curve | To be measured |

**Headline we expect to be able to say:** *"With real devices and real timing, the models generalise to new
sensors using the same protocol, but not to a new protocol; training on more device types fixes this."*

---

## 6. Risks and how we handle them

| Risk | Mitigation |
|---|---|
| Shifted columns in Modbus / DDoS_UDP / MITM raw CSVs | Column audit; rebuild from pcaps with tshark if needed |
| Capture date reveals the class (each capture is its own session) | Replay with relative time only; date and absolute time never used as features; split B/C checked for leakage |
| Long idle gaps inside captures | Split into sessions at > 1 h gaps |
| Ambiguous matches (same µs, same IPs) | Keep the row only if exactly one packet matches; report counts |
| Data size (21 M rows) on a 16 GB laptop | Process per file; stratified sample for training; Parquet |
| Attacks target one victim, not the 10 sensors | State clearly: the unseen-device test measures **false alarms on normal traffic**; attack detection is tested by time |
| Modbus pilot result may be an artefact of the column shift | Treat as provisional until step 2's audit |

---

## 7. Effort and order
About **8–10 working days**: steps 1–4 (≈3–4 days), step 5–6 (≈3 days), steps 7–8 (≈3 days).
Steps 1 and 2 can run in parallel between two people.

## 8. Definition of done
- [ ] Packet index for all 24 captures, with session splits and a match-rate report per file.
- [ ] Every row of dataset v2 has a real timestamp, device ID and session ID (or is reported as unmatched).
- [ ] Encoding parity with the selected file verified by test.
- [ ] Leave-one-device-out results for all 10 sensors.
- [ ] Core experiments re-run on the realistic replay; figures regenerated.
- [ ] Documentation and manifests updated; all tests pass.

## 9. Note for the final report
The mid-term models were trained on the selected file, whose normal class is effectively **one sensor**
(temperature & humidity). The final report must state this, and present the dataset v2 results as the
realistic evaluation.

---

## 10. Implementation and results (28 Oct 2026)

### 10.1 What was built

| Step | File(s) | Result |
|---|---|---|
| 1 Packet index | `src/data/ingestion/pcap_index.py` | 24 captures, **21,124,493 packets**; one damaged record (Vulnerability scanner, packet 265,828) excluded |
| 2 Features | `src/data/ingestion/tshark_extract.py`, `src/data/preparation/raw_normalize.py` | All 61 features re-extracted with tshark 4.6.9 for **every** packet (see 10.2) |
| 2 Validation | `scripts/validate_tshark_extraction.py` → `experiments/manifests/tshark_validation.json` | tshark vs the publisher's CSV, row by row: Heart_Rate **100%** identical; Temperature_and_Humidity 99.995%; SQL injection 99.95%. The remaining rows are TCP spurious retransmissions: Wireshark 4.6 does not decode the application layer (HTTP, MQTT) of a retransmitted duplicate, the 2021 version did; the original segment keeps its fields (10.9) |
| 3 Timestamps | `src/data/preparation/timestamps.py` | All **17,577,265** publisher CSV rows of the 21 matchable captures mapped to their packet: 17,577,234 directly, 21 by packet order, **10 ambiguous** (Temperature_and_Humidity, never guessed) |
| 4 Devices | `src/data/preparation/devices.py`, `data/metadata/device_map.yaml` | 10 devices from the dataset paper (Table VI); attacks → the attacked edge server's segment |
| 1–4 Event tables | `scripts/build_realistic_events.py` → `data/standardized/events/<capture>.parquet` + manifest | Every packet with real UTC timestamp, session, device, `publisher_selected` flag, labels and 45 features; time-ordered |
| 5 Dataset v2 | `scripts/build_realistic_dataset.py`, `src/data/preparation/realistic.py` → `data/splits/real*/`, `experiments/manifests/realistic_dataset.json` | 1,757,956 rows, 41 features (10.3) |
| 6 Realistic replay | `src/device/simulator.py` (`RealtimeReplay`), `src/pipeline.py` (`replay="realistic"`) | Real devices and real inter-arrival times (10.6) |
| 7 Splits | `src/data/preparation/splits.py` | A random, B time-based, C leave-one-device-out |
| 8 Evaluation | `scripts/run_realistic_eval.py` | Offline (A, B), leave-one-device-out, replay runs → `experiments/results/realistic/` |
| 8 Other experiments | `run_integrity_accuracy.py` / `run_security.py --replay realistic`, suite `final_task1` (`run_experiments.py`), `scripts/run_final_task1.sh` | Tampering, security, comparison, scaling on the replay; figures in `docs/final/task1/` (10.10) |
| 9 Tests | `tests/unit/test_{pcap_index,raw_normalize,timestamps,devices,splits,simulator,model_registry_paths}.py` | 59 unit tests, all passing |

### 10.2 Decisions that differ from the plan, and why

1. **Features come from tshark for all 24 captures**, not from the raw CSVs. The pre-study found the reason the
   Modbus/DDoS_UDP/MITM CSVs are broken: the publisher joined multi-valued fields (e.g. `udp.port` = "5353,5353",
   several DNS query names) with a comma, the CSV separator. **Every UDP row is shifted**, in every file. tshark
   reproduces the publisher's values for every intact row (10.1), so re-extraction is both correct and uniform.
   The CSVs are used only to know which packets the publisher selected (`publisher_selected`).
2. **Which packets are used.** The publisher left out mostly UDP background (DNS to the gateway, mDNS, SSDP,
   broadcasts) and IPv6. Normal captures: **all packets** (all of it is normal sensor traffic). Attack captures:
   **only the publisher's packets** (the left-out background is not attack traffic, so its label is unknown).
   Modbus, DDoS_UDP and MITM: all packets, since their CSV cannot be matched (DDoS_UDP has 14,106 more
   packets than its CSV; they may include a little background labelled as attack, at most 0.44% of the class).
3. **No timestamp recovery for the selected DNN file** (plan step 3, second bullet). Dataset v2 is built directly
   from the captures, so every v2 row has a real timestamp, device and session by construction; mapping the
   mid-term file is no longer needed.
4. **Duplicates are dropped within each time partition**, not over the whole capture. Keeping only the earliest
   copy pushes every repeated packet into the training window: DDoS_ICMP kept 1 test row and MITM 4. A packet
   repeated later is a real repeat that a deployed model must classify. Repeats across partitions are reported
   per class (`test_share_seen_in_train_by_class` in the split manifests). Split A applies the mid-term rule
   exactly (one row per distinct feature vector and label).
5. **Time-split cut points are timestamps** computed once per session on the full traffic (70% / 85% of its
   packets), saved in `data/splits/real/session_cuts.parquet`. De-duplication and sampling cannot move a
   boundary, and the replay streams exactly the test window.
6. **Model registry per view.** The mid-term models stay in `models/<layer>/`; dataset v2 models are in
   `models/real_time/` and `models/real_random/`. `BLOCKIOT_VIEW=<view>` selects data, stream and models together.

### 10.3 Dataset v2

| | Rows |
|---|---:|
| Packets with a certain label (rule 2 above) | 21,002,440 |
| After de-duplication (per capture and time partition) | 16,320,439 |
| of which: same feature vector under another class (kept, reported) | 580,675 (3.6%) |
| **Dataset v2** (at most 100,000 per class and device, uniform over time) | **1,757,956** |

- **Normal: 1,000,000 rows from 10 devices** (100,000 each), versus one sensor in the mid-term file.
- **Attacks:** 100,000 each for the six large classes; all rows for the rest (SQL injection 50,894 … MITM 414).
- **Features:** 41 (device level 13). Removed: the publisher's 15 leakage columns, `dns.qry.name` (free text;
  its length is kept) and 4 constant columns (`data/metadata/real_feature_removal.csv`).
- **Splits:** A random 1,191,264 / 255,271 / 255,272 (stratified by class and device);
  B time 1,190,684 / 286,353 / 280,919.
- **Data limit:** MITM has only 414 distinct packets; its time-split test window holds **8**. MITM results
  under split B are not meaningful.

### 10.4 Results: test splits (deployed models of each view; `offline_metrics.csv`)

Macro-F1 (15 classes for fog and cloud):

| Layer | Mid-term (DNN file) | v2, split A (random) | v2, split B (time) |
|---|---:|---:|---:|
| Device (binary) | 0.852 | 0.843 | 0.834 |
| Edge (binary) | 0.962 | 0.954 | 0.938 |
| Fog (multiclass) | 0.897 | 0.896 | 0.814 |
| Cloud (multiclass) | 0.903 | 0.900 | 0.802 |
| Cloud, attack vs normal | 0.962 | 0.949 | 0.941 |

All values are on held-out test data: the mid-term column is the 200,000-message test-split run
(`experiments/results/baseline-20260929T125816-d9ae79.json`); the v2 columns score the whole test split.

- **Same protocol, realistic data → same quality.** Ten real sensors and correctly aligned UDP/MITM rows give
  almost exactly the mid-term scores under split A.
- **Train on the past, test on the future → −9 points of multiclass F1.** Most of it is MITM (0.95 → 0.00 recall
  on 8 test packets; one class is 6.7 points of macro-F1) and Ransomware (0.87 → 0.60). Attack-vs-normal
  detection stays at 0.94.
- **DDoS_UDP is still detected 100%** with correctly aligned rows, so the mid-term's 100% was not only an
  artefact of the misaligned rows. Web attacks (Uploading, SQL injection, XSS, DDoS_HTTP, Password) stay at
  0.6–0.75 recall in both splits; these classes have the most label conflicts with normal traffic.

**False alarms on each device's normal traffic (split B, % of its normal test messages):**

| Device | Device level | Edge | Fog | Cloud |
|---|---:|---:|---:|---:|
| 9 MQTT sensors | 6.6–7.5 | 1.1–2.0 | 0.01–0.06 | 0.06–0.16 |
| **Modbus** | **24.8** | **27.6** | **18.6** | **20.8** |

Under split A, Modbus false alarms are 0.2–1.7%. **Why Modbus fails over time:** the publisher's feature set
contains counters that only grow. In the Modbus test window, 36.5% of `mbtcp.trans_id` values and 22% of
`tcp.seq` values exceed anything seen in training, and `tcp.len` reaches 1,460 bytes (training max 193). A random
split hides this; a time split exposes it. **Proposed follow-up:** an ablation without counter features
(`mbtcp.trans_id`, `tcp.seq`, `tcp.ack`, `udp.stream`).

### 10.5 Results: unseen devices (split C, leave one device out; `lodo*.csv`)

For each sensor: all four layers are retrained without its normal traffic (time-split train part of everything
else, 300,000-row cap, cloud family = random forest as selected on split B), then tested on **all 100,000 of
its normal messages**. Any "attack" prediction is a false alarm.

**False-alarm rate on the unseen sensor (%):**

| Held-out sensor | Device | Edge | Fog | Cloud | Mistaken for (cloud) |
|---|---:|---:|---:|---:|---|
| Distance, Flame, IR, Sound, Soil, Water level | 4.8–6.0 | 3.3–4.7 | 0.02–0.05 | 0.08–0.15 | DDoS_HTTP |
| Heart rate | 7.2 | 6.2 | 0.04 | 0.11 | DDoS_HTTP |
| pH | 6.4 | 5.0 | 0.85 | 0.91 | DDoS_UDP |
| **Temperature & humidity** | 18.6 | 16.6 | **11.8** | **12.1** | Vulnerability_scanner |
| **Modbus** | 63.3 | 36.2 | **18.7** | **20.2** | Vulnerability_scanner |

Attack detection stays the same in every fold: device 75%, edge 91–95%, fog and cloud 90%.

- **Seven MQTT sensors generalise:** an unseen sensor gets as few false alarms at fog and cloud as a sensor the
  models were trained on (seen MQTT sensors in the same folds: 0.05–0.4%).
- **Temperature & humidity:** 99% of its false alarms (11,933 of 12,051) are **IPv6 TCP segments** (1,440-byte
  ACK/PSH), 19% of its traffic and a traffic type no other sensor produces. A new traffic type, not a new sensor,
  causes the alarms. (Checked: the attack captures contain none of this sensor's traffic, so it is not label noise.)
- **Modbus:** high, but about as high when Modbus *is* in training (16–36% in the other folds), because of the
  counter features (10.4). Time drift, not novelty, is the main problem.
- **Compared with the pilot** (mid-term models, §2.6): Modbus 100% / 100% / 38.6% (device / edge / cloud)
  → 63% / 36% / 20% with correct features and nine sensors in training.

### 10.6 Results: realistic replay (`replay="realistic"`)

Each device sends its own messages with their **real inter-arrival times**; every session's test window starts at
replay time 0 (dates hidden). Each of the 24 captures contributes an equal share as **one contiguous slice from
the start of its window**: a global time cut would give 0.2 s of mostly DDoS traffic. Fog flood threshold:
2,500 events/s per device (1.5 × the busiest sensor's 1-second peak in training).

**200,000 messages, no blockchain** (`realistic_replay-20261028T102400-b77ccb.json`):
- 10 devices; replay span **1,514 s**; slices from 1.5 s (DDoS_UDP) to 1,514 s (Port scanning), 156 s for
  Temperature & humidity, 225 s for Modbus.
- Macro-F1: device 0.826, edge 0.942, fog 0.782, cloud 0.771 (multiclass); cloud attack vs normal 0.939.
  This stream keeps real repeats (no de-duplication), so it is not directly comparable with the test-split scores.
- Cloud false alarms per MQTT sensor 0.05–0.33%; Modbus 3.4% (the first 225 s of its window drift less).
- Throughput 13,426 events/s; per-event time device 0.003 ms, edge 0.019 ms, fog 0.019 ms, cloud 0.028 ms.

**The same 200,000 messages with the Merkle-batch blockchain** (`realistic_replay-20261028T103013-7f7fce.json`),
compared with the mid-term's 200,000-message batch run:

| | Mid-term (random devices) | Realistic replay |
|---|---:|---:|
| Messages rejected | 0 | 0 |
| Predictions | — | identical to the run without blockchain |
| Device Merkle commits | 7,820 | **4,624** (−41%) |
| Messages per commit | 25.6 | **43.3** |
| Gas for data integrity (device commits + edge records) | 1,166 M | **690 M** (−41%) |
| Fog alerts audited on chain | 51,186 | 82,827 |
| Gas for the alert audit | 1,329 M | 2,144 M (+61%) |
| Total gas per message | 12,589 | 14,281 |
| Throughput (events/s) | 443 | 549 |

- **Real traffic is uneven across devices**, so each 256-message window holds fewer devices with more messages
  each: fewer, larger Merkle batches and 41% less gas for data integrity. This was expected (§5) and is now measured.
- Total gas still rises, because the realistic stream raises more alerts (14 of its 24 equal shares are attack
  captures, plus real flood alerts). The alert audit is now **75% of all gas**, which strengthens the case for
  the planned batched alert audit.

### 10.7 Definition of done (§8), status

- [x] Packet index for all 24 captures, with session splits and a match-rate report per file
  (`data/standardized/events/<capture>.manifest.json`).
- [x] Every row of dataset v2 has a real timestamp, device ID and session ID (by construction; 10 ambiguous CSV
  rows only affect the `publisher_selected` flag, never a timestamp).
- [x] Encoding parity with the selected file: verified row by row by `scripts/validate_tshark_extraction.py`;
  decoding rules covered by unit tests.
- [x] Leave-one-device-out results for all 10 sensors.
- [x] Core experiments re-run on the realistic replay; figures regenerated: accuracy and cost (10.6), then
  tampering, security, the comparison suite and scaling, with 11 figures in `docs/final/task1/` (10.10).
- [x] Documentation and manifests updated; all tests pass.

### 10.8 What remains, and suggested next steps

1. ~~Re-run the other experiments on dataset v2~~: done (10.10).
2. **Counter-feature ablation** (10.4): retrain without `mbtcp.trans_id`, `tcp.seq`, `tcp.ack`, `udp.stream` and
   compare Modbus false alarms and macro-F1 under split B.
3. **Time-window features (add-on after task 1)** can now use real time: `RealtimeReplay` stamps every message with its real
   offset, and the fog already computes 1/5/30/60 s windows per device.
4. State in the final report: the mid-term Normal class was one sensor; the mid-term DDoS_UDP and MITM rows were
   misaligned (DDoS_UDP is still detected 100% on corrected data; MITM has too few distinct packets for a time split).

### 10.9 Verification audit (3 Nov 2026)

An independent audit of everything above: 162 checks. 161 pass; the one below its threshold (XSS parity 99.70%,
threshold 99.9%) is fully explained below. Where possible it compares our outputs with sources the pipeline does
not use for that purpose, so it can catch errors the build would repeat.

| What was checked | How | Result |
|---|---|---|
| Nothing changed since the build | SHA-256 of all 24 event tables, 8 split files, 8 deployed models vs their manifests; every model trained on its own view's train split | all match |
| Timestamps, sessions, labels, devices | All 24 event tables: time order, session breaks exactly at gaps > 1 h, timestamps in the valid window, one row per indexed packet, label and device per capture | all correct |
| Device identity | Share of each normal capture's IPv4 packets that involve its Table VI hosts | 98.9–100% |
| Features and timestamps | **Fresh tshark read** of 25 random packets per capture (600 packets), compared with the event tables | 0 differences |
| Parity with the publisher | 3,000 random publisher CSV rows per capture, all 21 matchable captures, matched to their packets and compared field by field (non-UDP rows) | 99.70–100% identical. **Every difference** is an HTTP or MQTT field on a TCP spurious retransmission (checked one by one); the original segment of each request carries the same fields in our data, so no request is lost |
| Split leakage on the real data | Partitions disjoint (row ids); no metadata among any layer's features; split B: train < validation < test in time in all 33 sessions, and every row in the partition its cut points give; split A: no feature+label vector twice; split C: the held-out sensor's 100,000 normal rows are all in test and none in train/validation, for all 10 sensors | all pass |
| Realistic replay (200,000 messages) | Every row inside its session's test window; none used for training or model selection; inter-arrival times equal the capture's to 1 µs; timestamps non-decreasing; per-device sequence numbers 0, 1, 2, …; dates hidden; no metadata in payloads | all pass |
| Reproducibility | Offline evaluation re-run and compared with the saved result files | identical |
| Code | 69 automated tests, lint | all pass |

**Requirements status (§4 steps, §8 definition of done):**

| Requirement | Status |
|---|---|
| Steps 1–4: packet index, encoding, timestamps, devices | ✅ Built and verified. Two differences from the plan wording: the packet index is stored per capture (24 files), and frame `length` is read but not stored, as no feature uses it; the attack traffic's device is the attacked segment's device (`dht11_temperature_humidity`), not a separate victim-host ID |
| Step 3, selected DNN file timestamps (94% expected) | Not done, by decision (10.2 item 3) |
| Step 5: dataset v2 with manifests | ✅ |
| Step 6: realistic replay, speed factor, 256-message window and blockchain modes unchanged | ✅ |
| Step 7: splits A, B, C | ✅ (verified on the real data) |
| Step 8: retrain same model families; accuracy, cost, leave-one-device-out | ✅ |
| Step 8: tampering, security and scaling re-runs; figures | ❌ Not done at the time of this audit; **done afterwards (10.10)** |
| Step 9: code, tests, documentation | ✅ |

**Expected results (§5) vs measured:** timestamp recovery ≈100% → met (all but 10 of 17.6 M rows). Unseen MQTT
sensors ≈0–1% false alarms → met at fog and cloud (0.02–0.9%); **not at device and edge (3.3–7.2%)**, but
those layers show similar rates on sensors they were trained on, so it is a property of the v2 device and edge
models, not of unseen devices. Unseen heart rate "some false alarms" → 6.2% at the edge, 0.11% at the cloud.
Unseen Modbus high → 20% at the cloud, explained mostly by counter features (10.4). Overall accuracy "may drop
slightly" → unchanged under split A, −9 points of multiclass F1 under split B (mostly MITM). Uneven device
traffic changes Merkle batches → measured (−41% commits); the scaling curve was measured afterwards (10.10).

### 10.10 Step 8 completed: the remaining experiments on the realistic replay (3 Nov 2026)

The mid-term's tampering, security, comparison and scaling experiments, re-run unchanged on dataset v2's realistic
replay with the `real_time` models (`scripts/run_final_task1.sh --step8-only`, ~30 min). The mid-term result files
are untouched: v2 results go to `experiments/results/realistic/` and `experiments/results/final_task1/`, figures and
tables to `docs/final/task1/` (`scripts/make_figures.py --set final_task1`; the presentation-1 set still
regenerates byte-identical).

**What was added for it:** `--replay realistic` in `run_integrity_accuracy.py` and `run_security.py`; suite
`final_task1` in `configs/experiments.yaml`; `RealtimeReplay(replicas=k)` for device scaling, which splits each real
device's messages round-robin over k devices of its type, so the device count grows while the messages and their
timing stay the same (the fog's per-device flood threshold is divided by k, as the mid-term scaled it with the device
count); two new figures: macro-F1 by split (`09`) and false alarms on unseen sensors (`10`).

**Comparison: 10,000 messages, 3 seeds** (`01`, `02`, `07`). In the realistic replay every seed replays the same
test-window messages (a seed changes only event ids and device keys), so accuracy has no spread across seeds.

| | Mid-term | Dataset v2 |
|---|---:|---:|
| Throughput, events/s: no blockchain / Merkle batch / per-event | 11,357 / 1,492 / 36.5 | 12,489 / 1,902 / 37.7 |
| Predictions with vs without blockchain | identical | identical |
| Gas per message, batch: data integrity (device commit + edge record) | 5,941 | **3,132** (−47%) |
| Gas per message, batch: fog alert audit | 6,649 | **12,754** (+92%) |
| Gas per message, per-event: device commit + edge record | 149,159 | 149,161 |

Macro-F1 on this 10,000-message stream: device 0.790, edge 0.941, fog 0.792, cloud 0.779.

**Accuracy under data-integrity attack: 10,000 messages, Merkle batch** (`03`): attacks detected (%).

| Attacks camouflaged | No blockchain (mid-term → v2) | Blockchain (mid-term → v2) |
|---|---:|---:|
| 0% | 89.4 → 85.9 | 89.4 → 85.9 |
| 10% | 80.8 → 77.3 | 90.4 → 87.3 |
| 25% | 66.8 → 64.7 | 91.8 → 89.7 |
| 50% | 45.7 → **43.9** | 94.8 → **93.4** |

With the blockchain every camouflaged attack is caught: 2,796 of 2,797 by integrity rejection. The last one had
exactly the same feature values as the normal message chosen to disguise it, so nothing changed and its hash still
matched; the cloud classified it as an attack. False positives on normal traffic: 0.16% (mid-term 0.014%).

**Security: 3,000 messages, 5% attack rate** (`04`). With the blockchain, **all 8 attack types are blocked (100%)
and no genuine message is rejected**, as at the mid-term. Without it: tampering, unregistered device,
impersonation and a model swap with a forged record pass (0%); same-edge replay is caught (100%, duplicate check);
cross-edge replay 65% (mid-term 53%, by sequence numbers only); and during impersonation the baseline locks out
89.5% of genuine traffic (mid-term 92.5%). Edge verification costs 6.0 ms per message with the blockchain and
0.05 ms without (mid-term 7.5 / 0.03).

**Scaling: 5,000 messages, each real device split over k devices** (`05`, `06`): events/s.

| Devices | 10 | 50 | 100 | 250 | 500 |
|---|---:|---:|---:|---:|---:|
| Merkle batch, dataset v2 | 2,035 | 823 | 498 | 233 | 136 |
| Merkle batch, mid-term | 1,513 | 441 | 221 | 111 | 77 |
| Per-event, dataset v2 | 62 | 60 | 62 | 61 | 60 |
| No blockchain, dataset v2 | 12,577 | 12,279 | 12,132 | 11,471 | 11,957 |

- **The scaling drop remains:** batch throughput falls 15× from 10 to 500 devices (mid-term 20×). Each device gets
  its own Merkle commit per 256-message window, so with many devices every commit covers fewer messages. Real
  traffic is uneven, so dataset v2 is 1.3–2.3× faster at every point, but the shape is a property of per-device
  batching, not of the data. Final task 3 (AI-chosen batching) addresses it.
- These runs use one Anvil node that mines every transaction at once. They are the single-node reference for
  final task 2 (4 QBFT validators, real block time). The same scaling on QBFT is compared with them in
  [02_multi_node_blockchain.md §10.7](02_multi_node_blockchain.md#107-t24-scaling-single-node-vs-qbft): batch
  throughput falls only 24% there, while gas per message grows 6.2×.

