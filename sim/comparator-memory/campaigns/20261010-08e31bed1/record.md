# Memory / hysteresis characterization record `20261010-08e31bed1` (issue #159)

**Characterization, not compliance.** Characterization only. No specification row is added, changed or claimed; a spec claim needs a separate DR-0002 decision record.

- git: `b0d699c729dc9806308eab8310a042099be07db9` (feature/issue-159)
- generated: 2026-10-10T21:36:15+00:00
- ngspice engine(s): 46; klt: klt 0.5.0+ge8ca621a6961
- DUT netlist sha256: `b31b936dd78634b224d882e5f43ceb3b43eb34e5c3400336f09213cef8a39b90`
- mismatch off, deterministic search: no seeds or Monte-Carlo run counts apply.
- search: deterministic 10-ary search, integer uV: 100 mV -> 10 mV -> 1 mV -> 100 uV -> 10 uV in four sequential klt sim rounds (round 1 = 11 probes incl. endpoints, rounds 2-4 = 9 interior probes)

## Controls (tt / 1.20 V / 27 C)

| control | period | shift (uV) | verdict | note |
|---|---|---|---|---|
| long_reset | 110 ns (100 ns reset) | -10.0 | **PASS** | |shift| <= 20 uV |
| short_reset | 11 ns (1 ns reset) | -10.0 | **FAIL** | |shift| 10 uV below 40 uV; excess over long-reset 0 uV below 20 uV |

Bench sensitivity control: **FAIL**. A control did not pass. A 'no measurable memory' conclusion is NOT supported by this record; a near-zero nominal shift must not be read as evidence of no memory.

## Nominal 45-point grid

- points with two thresholds: 45/45; rejected: 0
- probes evaluated 3420: resolved+ 1710, resolved- 1710, **unresolved 0**, **wrong-polarity 0** (counted separately), missing 0
- memory shift (P - N): min -10.0 uV, max -10.0 uV, mean -10.0 uV; largest |shift| 10.0 uV at `tt/1.08V/-40C`; widest final bracket 10 uV

| corner | thr after P (mV) | thr after N (mV) | shift (uV) | bracket P/N (uV) | unres | wrong-pol |
|---|---|---|---|---|---|---|
| tt/1.08V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| tt/1.08V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| tt/1.08V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| tt/1.20V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| tt/1.20V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| tt/1.20V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| tt/1.32V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| tt/1.32V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| tt/1.32V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ff/1.08V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ff/1.08V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ff/1.08V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ff/1.20V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ff/1.20V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ff/1.20V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ff/1.32V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ff/1.32V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ff/1.32V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ss/1.08V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ss/1.08V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ss/1.08V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ss/1.20V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ss/1.20V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ss/1.20V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ss/1.32V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ss/1.32V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| ss/1.32V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| fs/1.08V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| fs/1.08V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| fs/1.08V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| fs/1.20V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| fs/1.20V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| fs/1.20V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| fs/1.32V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| fs/1.32V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| fs/1.32V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| sf/1.08V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| sf/1.08V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| sf/1.08V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| sf/1.20V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| sf/1.20V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| sf/1.20V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| sf/1.32V/-40C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| sf/1.32V/27C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |
| sf/1.32V/125C | -0.00500 | +0.00500 | -10.0 | 10/10 | 0 | 0 |

## Determinism repeat (tt / 1.20 V / 27 C)

All rounds bit-identical: **True** (rounds: 1, 2, 3, 4).

## Batch provenance

- `sim/comparator-memory/campaigns/20261010-08e31bed1/control-long/round1/memory.mos_tt.request.json`: batch job `klt-sim-f2d1b3174d44` (1 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/control-long/round2/memory.mos_tt.request.json`: batch job `klt-sim-f9fefd14a6b2` (1 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/control-long/round3/memory.mos_tt.request.json`: batch job `klt-sim-4de18a90a220` (1 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/control-long/round4/memory.mos_tt.request.json`: batch job `klt-sim-245dbc503f50` (1 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/control-short/round1/memory.mos_tt.request.json`: batch job `klt-sim-29a544daa2ca` (1 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/control-short/round2/memory.mos_tt.request.json`: batch job `klt-sim-0aafa388a92b` (1 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/control-short/round3/memory.mos_tt.request.json`: batch job `klt-sim-e705f2924d82` (1 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/control-short/round4/memory.mos_tt.request.json`: batch job `klt-sim-49f218692663` (1 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round1/memory.mos_ff.request.json`: batch job `klt-sim-7a5cf5600670` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round1/memory.mos_fs.request.json`: batch job `klt-sim-bc0a02ff7715` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round1/memory.mos_sf.request.json`: batch job `klt-sim-ea4dbab60a06` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round1/memory.mos_ss.request.json`: batch job `klt-sim-50097aa648ba` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round1/memory.mos_tt.request.json`: batch job `klt-sim-7cd534f0969d` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round2/memory.mos_ff.request.json`: batch job `klt-sim-5b3905fbc659` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round2/memory.mos_fs.request.json`: batch job `klt-sim-fe22c45d8588` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round2/memory.mos_sf.request.json`: batch job `klt-sim-a6f2950e3867` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round2/memory.mos_ss.request.json`: batch job `klt-sim-e8e4ef89f518` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round2/memory.mos_tt.request.json`: batch job `klt-sim-7cd2a757214b` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round3/memory.mos_ff.request.json`: batch job `klt-sim-e5cc54b84dd4` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round3/memory.mos_fs.request.json`: batch job `klt-sim-d176e71573d9` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round3/memory.mos_sf.request.json`: batch job `klt-sim-8ddb06f894cc` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round3/memory.mos_ss.request.json`: batch job `klt-sim-67ae17233968` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round3/memory.mos_tt.request.json`: batch job `klt-sim-db2e780b3e7c` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round4/memory.mos_ff.request.json`: batch job `klt-sim-f833c6429d16` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round4/memory.mos_fs.request.json`: batch job `klt-sim-acd82422d173` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round4/memory.mos_sf.request.json`: batch job `klt-sim-314af5b846f5` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round4/memory.mos_ss.request.json`: batch job `klt-sim-d5eb37347f4a` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/nominal/round4/memory.mos_tt.request.json`: batch job `klt-sim-689c7255a141` (9 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/repeat/round1/memory.mos_tt.request.json`: batch job `klt-sim-2e21bb077230` (1 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/repeat/round2/memory.mos_tt.request.json`: batch job `klt-sim-954f72ead64e` (1 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/repeat/round3/memory.mos_tt.request.json`: batch job `klt-sim-60217b44d7a8` (1 corners, status pass)
- `sim/comparator-memory/campaigns/20261010-08e31bed1/repeat/round4/memory.mos_tt.request.json`: batch job `klt-sim-87d0c58c94f1` (1 corners, status pass)
