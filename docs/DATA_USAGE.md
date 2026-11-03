# Data usage: mid-term vs final

What data the project used for the mid-term evaluation, exactly how much, and what it will use for the
final. All numbers come from `data/metadata/dataset_card.yaml` and `experiments/manifests/*_preparation.json`.

**Dataset:** Edge-IIoTset, IEEE DataPort, DOI 10.21227/MBC1-1H68 (Ferrag et al., IEEE Access 10, 2022).
Downloaded from the authors' official Kaggle copy (version 5), because DataPort needs a subscription login.
All 52 files are SHA-256 verified (`python scripts/download_edge_iiotset.py --verify`).

---

## 1. What is downloaded (everything available)

| Part | Files | Size | Rows | Used at mid-term? |
|---|---:|---:|---:|---|
| Selected file for deep learning (`DNN-EdgeIIoT-dataset.csv`) | 1 | 1.2 GB | 2,219,201 | **Yes: the main source** |
| Selected file for classic ML (`ML-EdgeIIoT-dataset.csv`) | 1 | 82 MB | 157,800 | Prepared only, not used in experiments |
| Raw normal traffic, one CSV per sensor | 10 | 3.99 GB | 11,209,913 | No |
| Raw attack traffic, one CSV per attack | 14 | 3.74 GB | 9,729,709 | No |
| Packet captures (PCAP), normal + attack | 24 | 2.20 GB | packets | No |
| Dataset paper (PDF) and Readme | 2 | — | — | Reference only |

---

## 2. Mid-term: what we used, and how much

### 2.1 Source and cleaning (DNN file)

| Step | Rows |
|---|---:|
| Raw records | 2,219,201 |
| Exact duplicates removed | −309,530 |
| **Clean records** | **1,909,671** |
| of which: identical features but different labels (kept, reported) | 44,172 (2.3%) |

- **Columns:** 63 in the file. We dropped the publisher's 15 leaky columns (timestamps, IP addresses,
  ports, payloads) and 4 constant columns, leaving **42 features** plus 2 labels. Every removal and its reason
  is in `data/metadata/dnn_feature_removal.csv`.
- **Features per level:** device 13 (header fields only); edge, fog and cloud all 42.
- **Labels:** attack or normal (`Attack_label`), and the attack type (`Attack_type`, 15 classes: Normal + 14 attacks).

### 2.2 Split (stratified by attack type)

| Split | Rows | Used for |
|---|---:|---|
| Train | 1,336,769 | Training. Models use a **300,000-row stratified sample** of it |
| Validation | 286,451 | Choosing the cloud model (macro-F1) |
| Test | 286,451 | Every experiment result (never seen in training) |

Test-split mix: **71.4% normal, 28.6% attack**. Rarest classes in test: MITM 53, Fingerprinting 128.

### 2.3 How much test data each experiment used

| Experiment | Messages | Repetitions | Slide |
|---|---:|---|---|
| Full-scale run (no blockchain, Merkle batch) | 200,000 | 1 each | 14 (recall chart) |
| Comparison: 3 modes | 10,000 | 3 seeds × 3 modes | 14, 17, 19 |
| Accuracy under tampering | 10,000 | 4 tamper rates × 2 modes | 15 |
| Security: 8 attack types | 3,000 per attack pass | 5 passes × 2 modes (+ model and ledger tests) | 16 |
| Scalability | 5,000 | 5 device counts × 3 modes | 18 |

All test messages are a stratified sample of the test split, replayed by the simulator.

### 2.4 What was simulated (not in the data)
- **Device identity:** the selected file has no device IDs, and the IP column leaks the label, so messages
  were assigned to 10–500 **logical devices at random**.
- **Timing:** `frame.time` lost its date and each attack sits in its own time slot (label leakage), so the
  simulator gave each message a **synthetic replay timestamp**.

### 2.5 Prepared but not used: ML file
157,800 rows → 152,196 after removing 5,604 duplicates → 106,537 / 22,829 / 22,830, with **38 features**
(different columns are constant in this file). Only **15.8% normal**, the opposite balance to the DNN file.

---

## 3. Final: what we will use

| Data | Size | Why | Status |
|---|---|---|---|
| **DNN selected file** (same as mid-term) | 2.2 M rows | Keep as the main benchmark so final results compare directly with the mid-term | Ready |
| **24 packet captures** | 2.2 GB | Only source of **real timestamps** (full dates, Nov–Dec 2021); also give real device identity (sensor IPs) | Downloaded, not processed |
| **Raw per-sensor normal CSVs** | 10 files, 11.2 M rows | **Real device identity:** one sensor = one device; enables a **test on unseen devices** | Downloaded, not processed |
| **Raw per-attack CSVs** | 14 files, 9.7 M rows | Large-scale and per-attack experiments | Downloaded; needs a column audit (see below) |
| X-IIoTID (IEEE DataPort, DOI 10.21227/mpb6-py55) | 107 MB | External validation on a second dataset | **Optional: instructor approval and DataPort login needed** |
| ToN_IoT (IEEE DataPort, DOI 10.21227/fesz-dm97) | — | External validation | Optional: the DataPort entry has no files (hosted by UNSW) |

### Two ways to get real timestamps
1. **Match by time (cheaper):** CSV rows kept the time of day to the microsecond, so each row can be matched
   to its packet in the capture to recover the full timestamp. The publisher's features stay unchanged.
2. **Re-extract from the captures (cleaner):** the 61 features are Wireshark field names, so `tshark` can
   rebuild them with timestamps directly from the PCAPs. This also fixes the shifted raw CSVs.

### Known issues to handle in the final
- **Captures and CSVs don't align row for row:** checked on 5 files. Only MITM matches exactly (1,229 = 1,229).
  Others have 1–17% more packets than CSV rows (e.g. Heart_Rate 170,435 packets vs 165,319 rows), so
  timestamps can't be copied by position.
- **Each capture is a separate session on a different day.** Absolute clock time would reveal the label.
  Replay each capture with its **real relative timing** (gaps, bursts), but shift all captures to a common
  start and interleave them.
- **Shifted columns** in the raw Modbus, DDoS_UDP and MITM CSVs (`frame.time` holds an IP address or "0.0").
  Audit these before use, or re-extract them from the PCAPs.
- **Rare classes stay rare:** MITM has only 53 test messages, so report its results with that caveat.

### Facts found in the pre-study for final task 1 (Oct 2026)
Full details and the plan: [final/01_real_timestamps_device_identity.md](final/01_real_timestamps_device_identity.md).
- **The selected file's "normal" class is effectively one sensor:** 99.8% of sampled normal rows come from the
  Temperature_and_Humidity capture. The other 9 sensors' normal traffic exists only in the raw files.
- **CSV times are UTC+1.** Matching rows to packets by time of day + IPs works: 100% on Heart_Rate, 94.3% on
  a selected-file sample (the rest are DDoS_UDP/MITM rows with a corrupt time field).
- **Raw CSVs store some fields in hexadecimal** (`tcp.flags`, `tcp.checksum`, MQTT flags); decode to decimal
  to match the selected file.
- **Modbus and Flame share host IPs**, so device ID = sensor name, not IP.
- **Pilot:** mid-term models raise almost no false alarms on 7 unseen MQTT sensors, 8.9% on heart rate at the
  edge, and ~100% on Modbus (provisional).

### New experiments this data enables
- Real time-window features at the edge and fog (1, 5, 30, 60 s), using real timestamps.
- **Generalisation to unseen devices:** train on some sensors, test on others.
- Scaling with real per-device traffic rates instead of random assignment.

---

## 4. Final task 1, as built (28 Oct 2026): dataset v2

Details, decisions and results: [final/01_real_timestamps_device_identity.md §10](final/01_real_timestamps_device_identity.md#10-implementation-and-results-28-oct-2026).

### 4.1 What is used now

| Data | Used for | Amount |
|---|---|---|
| **24 packet captures** | Real timestamps, sessions, device identity, and **all features** (re-extracted with tshark) | 21,124,493 packets → 21,124,492 event rows (1 damaged record) |
| **Raw per-sensor / per-attack CSVs** | Only to know which packets the publisher selected | 17,577,265 rows matched to their packet (10 ambiguous) |
| DNN selected file | Mid-term benchmark only (unchanged) | 2,219,201 rows |

### 4.2 Dataset v2 in numbers

| Step | Rows |
|---|---:|
| Packets with a certain label | 21,002,440 |
| After de-duplication (per capture and time partition) | 16,320,439 |
| **Dataset v2** (≤ 100,000 per class and device) | **1,757,956** |
| Normal, 10 devices × 100,000 | 1,000,000 |
| Attacks, 14 classes | 757,956 |

- 41 features (device level 13); real timestamp, session and device are **metadata only**, never features.
- Split A (random): 1,191,264 / 255,271 / 255,272. Split B (time): 1,190,684 / 286,353 / 280,919.
  Split C (leave-one-device-out): built per sensor from `data/splits/real/canonical.parquet`.

### 4.3 Corrections to the mid-term data, found in task 1
- **Every UDP row in the publisher's CSVs is misaligned** (multi-valued fields joined with the CSV comma). In
  the DNN file this covers all 121,568 DDoS_UDP and 1,214 MITM rows, and 1,845 Normal DNS rows. Mid-term
  results for DDoS_UDP and MITM were computed on shifted columns. (DDoS_UDP is still detected 100% on the
  corrected data.)
- **The DNN file's Normal class is ~99.8% one sensor** (Temperature_and_Humidity). Dataset v2 has all 10.
- **The publisher left out most UDP background traffic** (DNS, mDNS, SSDP, broadcasts) and IPv6 packets.

### 4.4 How much of it each experiment uses

Offline metrics score the whole test split (A: 255,272 rows; B: 280,919). Leave-one-device-out tests on all
100,000 normal rows of the held-out sensor plus every other row's time-test part. Every pipeline experiment
streams the **realistic replay**: rows from the time-split test window of every capture session, an equal
contiguous share per capture, never used for training.

| Experiment | Messages per run | Results |
|---|---:|---|
| Replay, no blockchain and Merkle batch | 200,000 | task 1 §10.6 |
| Comparison (3 seeds) and integrity under attack | 10,000 | task 1 §10.10; task 2 T2.1–T2.3 |
| Device scaling (each device split over k) | 5,000 | task 1 §10.10; task 2 T2.4 |
| Security | 3,000 per attack pass | task 1 §10.10; task 2 security |
