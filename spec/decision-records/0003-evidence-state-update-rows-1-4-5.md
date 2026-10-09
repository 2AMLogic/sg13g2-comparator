# 0003: Evidence-state update for Rows 1, 4 and 5 after #62 / #78 / #79 / #80

- **Status**: proposed. **This is a status-only record.** It ratifies no
  bound, changes no value in the `README.md` Target or Stretch column, and
  picks no Row 5 Target number. It restates, with citations, what the
  evidence committed since DR-0002 now says, and it updates the Measured and
  Status text of Rows 1, 4 and 5 to match. The ratification act is the
  two-key merge of the PR that lands this record, exactly as DR-0002 "How
  this record gets ratified" describes (a `RATIFY-KEY: ee` and a
  `RATIFY-KEY: market` verdict from non-author reviewers; the merge commit is
  the ratification record). **The drafting agent holds neither key and this
  PR must not be hand-merged.**
- **Date**: 2026-10-09
- **Decided by**: Builder agent, issue
  [#93](https://github.com/2AMLogic/sg13g2-comparator/issues/93), drafting
  only.
- **Related**:
  [`0002-target-spec-ratification.md`](0002-target-spec-ratification.md)
  (the record whose "Open items" this one closes out, without editing it),
  [#62](https://github.com/2AMLogic/sg13g2-comparator/issues/62),
  [#78](https://github.com/2AMLogic/sg13g2-comparator/issues/78),
  [#79](https://github.com/2AMLogic/sg13g2-comparator/issues/79),
  [#80](https://github.com/2AMLogic/sg13g2-comparator/issues/80),
  [#89](https://github.com/2AMLogic/sg13g2-comparator/issues/89) (the two
  rejected `vcm-m050` points)
- **Supersedes**: none. DR-0002 is not superseded; this record is the
  "higher-numbered record" DR-0002 and `README.md` say later status follows
  from. Where DR-0002's Row 1/4/5 *status* wording differs from the text
  below, this record governs the status wording; every bound stays as
  DR-0002 ratified it.
- **Superseded by**: none

## Context

DR-0002 ratified all five rows against the harness records under `sim/*/records/`
and listed its own gaps under "Open items". Four pieces of work have merged
since:

- **#62** re-measured every ratified row on the schematic DUT as `klt sim`
  corner envelopes over the 45-point grid
  ([`sim/klt-corner-verification/`](../../sim/klt-corner-verification/README.md),
  campaign `20261009-d73a9ac`). It is a separate evidence trail; no DR-0002
  record was touched.
- **#78** validated the direct Q_kick instrument that #62 added, with a
  known-charge fixture (campaign `20261009-issue78`).
- **#79** swept the whole-latch offset at three input common modes
  ([`sim/comparator-offset-cm-band/`](../../sim/comparator-offset-cm-band/README.md),
  campaign `20261009-5185f52`).
- **#80** swept the tail-bias reference `dut_ib` as a Pareto table
  ([`ibsweep.md`](../../sim/klt-corner-verification/campaigns/20261009-issue80/ibsweep.md)).

`README.md` still carried DR-0002-era wording for three rows ("charge
sub-bound CONSISTENT, NOT CERTIFIED", "no whole-latch common-mode sweep
exists yet", "no study exists to found a power bound"). Left alone, the
front-page table understates a known Target miss on Row 4. `CLAUDE.md` routes
anything that restates a ratified row's status through `spec/` with a record.

Every number below was re-read from the cited artifact while drafting this
record, not copied from the issue text.

## Decision

Proposed for ratification: the Measured and Status text for Rows 1, 4 and 5 in
`README.md` is replaced by the text summarized per row below. **No bound
changes.**

### Row 4 (Kickback): charge sub-bound is **NOT MET** on direct measurement

| | |
|---|---|
| **Ratified Target (unchanged)** | ≤ 25 fC/side peak transient injected charge (condition per DR-0002 Row 4) **and** ≤ 100 µV signal-dependent differential residue |
| **Ratified Stretch (unchanged)** | ≤ 8 fC/side and ≤ 30 µV |
| **Direct measurement** | Q_kick per side, branch A, worst side graded: **23.58 … 31.46 fC**, binding point `ff_125c_1.32v` (sides 30.87 / 31.46 fC there). **39 of 45 points exceed 25 fC; 45 of 45 exceed the 8 fC Stretch.** Source: [`grading.md`](../../sim/klt-corner-verification/campaigns/20261009-d73a9ac/grading.md), [`klt-corner-verification/README.md`](../../sim/klt-corner-verification/README.md) row 4a. |
| **Instrument validation** | #78 known-charge fixture reads back within 0.0002 fC at four cases including a zero-net bipolar case (20 fC peak read as 19.9999 fC, where the end-of-window estimator reads 0.0001 fC) and a restoring-resistor case; a 1 ps max-step re-run at the binding point moves Q_kick +0.03 % (31.46 to 31.47 fC); the with/without-instrument A/B at `mos_tt / 1.2 V / 27 C` leaves decisions bit-identical and the peak excursion within 0.02 % ([`campaigns/20261009-issue78/`](../../sim/klt-corner-verification/campaigns/20261009-issue78/)). |
| **Relation to DR-0002's estimate** | The direct value is 2.2× the `kick_1k_peak_mv × C_in` estimate (14.3 fC) at the binding point, inside the 1.3 … 2.9× under-reporting bias DR-0002 Row 4 (b) derived, and above the upper edge of the 11 … 41 fC bracket's *lower* half, i.e. on the "over 25 fC" side of the straddle. |
| **Residue sub-bound** | 2.03 … 15.63 µV (klt) vs. 1.70 … 15.40 µV (harness record); Target and Stretch both met. Unchanged in meaning. |
| **Status (replaces "CONSISTENT, NOT CERTIFIED")** | Charge Target **NOT MET** (39/45), charge Stretch **NOT MET** (45/45); residue Target and Stretch **MET**. The sub-bound is no longer "without a testbench": the klt `kickback` bench is its testbench. |

Consequences stated plainly, not decided here. DR-0002 ratified a Target the
design now demonstrably misses, on the same footing as Row 2 (noise). DR-0002
forbids relaxing a bound to make a result pass and so does `CLAUDE.md`; this
record does neither. The choice between relaxing the bound (a Row 4 revision,
which per DR-0002 needs the market key's explicit competitiveness finding) and
a redesign (DR-0002 Row 4 names a double-tail latch, ~3 to 5×, and a static
isolating buffer, rejected by DR-0001 on headroom) is an operator decision and
a separate record. **The intended escalation path for this finding is
`loom:operator`.** The best-fit direction from the kickback and noise sizing
work should inform it; that work is not part of this record.

One caveat that belongs with the measurement: the harness bench
[`sim/comparator-kickback/`](../../sim/comparator-kickback/README.md) still
emits no charge key and was deliberately not ported (#78 decision); the 25 fC
check lives in the klt port only. The harness record
`20260916-022249-36773c7` is unchanged and still reports the estimator.

### Row 1 (Offset sigma): common-mode band characterized, with a 43/45 caveat

| | |
|---|---|
| **Ratified Target / Stretch (unchanged)** | ≤ 15 mV / ≤ 8 mV, 3σ, at every PVT point, at `dut_vcm` |
| **Compliance basis (unchanged)** | The nominal-common-mode whole-latch record `20260917-060858-ea40b57` (7.456 … 10.537 mV, 45/45 inside Target, Stretch missed 27/45). The #62 klt re-measurement reads 6.91 … 12.09 mV (45/45 inside Target; Stretch FAIL, count quoted in the note below) and is a parallel trail, not a replacement. |
| **New characterization (#79)** | Whole latch, N = 60 per point, same seed contract (draw k is the same mismatch under all three conditions), 3σ min … max / grid mean: `vcm-m050` (0.55 V) **43/45 valid**, 6.89 … 11.43 / 9.34 mV; `vcm-nom` (0.60 V) 45/45, 6.91 … 12.09 / 9.51 mV; `vcm-p050` (0.65 V) 45/45, 6.91 … 12.87 / 9.85 mV. Every valid point is under 15 mV. Paired 3σ ratio to nominal averages 0.98 (`vcm-m050`) and 1.04 (`vcm-p050`). |
| **Caveat** | `vcm-m050` is **deliberately partly met**: `tt_-40c_1.32v` and `sf_-40c_1.20v` each lost one draw to an ngspice "timestep too small" abort and are REJECTED, not repaired (no sigma reported; the informational 59-draw values are 7.17 and 8.75 mV). Completion is tracked in [#89](https://github.com/2AMLogic/sg13g2-comparator/issues/89). |
| **Status (replaces "No whole-latch common-mode sweep exists yet")** | Row 1 Target **MET at nominal CM on the compliance record (unchanged)**. Over ±50 mV of input common mode the whole latch is **characterized, not certified**: 133 of 135 point-conditions are valid and all valid ones are inside 15 mV as a reference. **No whole-latch common-mode range is ratified**, and the sweep is quoted against 15 mV for reference only. A binding range needs its own record. |

Note on the Stretch count: the #62 README labels the klt Stretch verdict
"FAIL (40/45)" and DR-0002 records 27/45 for the harness bench; the two
benches differ by a known offset level gap (tracked in #82), and the klt
count is quoted from its own source, not reconciled here. Neither affects the
Target verdict.

### Row 5 (Supply / power): Pareto basis exists; no Target number picked

| | |
|---|---|
| **Ratified (unchanged)** | Supply Target 1.2 V ±10 %, −40 … 125 °C; 33.3 MHz; **no Target-column power bound**; Stretch ≤ 20 µW average including the bias branch |
| **Basis now available (#80)** | Seven `dut_ib` values {2.5, 5, 7.5, 10, 15, 20, 40} µA (tail current 4 × `dut_ib`), 45/45 points each for the regeneration bench; Monte Carlo (Rows 1, 2) run only at 10, 15 and 20 µA. Table: [`ibsweep.md`](../../sim/klt-corner-verification/campaigns/20261009-issue80/ibsweep.md). Worst-point power (klt full-cycle instrument, incl. bias branch): 18.69, 20.58, 23.27, 26.22, 32.41, 38.78, 64.75 µW respectively. |
| **What the Pareto shows** | No swept value meets every ratified Target. Rows 3a/3b hold down to 7.5 µA; 3c fails from 10 µA (2/45, `ss` 1.08 V) and below; 3a/3b/3c all fail at 5 µA and below. Row 2 fails at every bias where it was measured (1.074, 1.238, 1.289 mV grid mean at 10, 15, 20 µA). Row 1 at 15 µA is INCOMPLETE (44/45; one aborted draw at `ff_-40c_1.08v`). Only 2.5 µA is under the 20 µW Stretch and it fails Rows 3a/3b/3c. 40 µA is the only value meeting the 0.8 ns decision-time Stretch (0.637 ns). |
| **Status (replaces "no study exists to found a power bound")** | Supply Target **MET / exercised**. Power Stretch **NOT MET** at the baseline `dut_ib` = 20 µA (22.9 … 29.5 µW harness; 27.90 … 38.78 µW klt, a different instrument, see `klt-corner-verification/README.md` "Power reads higher"). **A study to found a Target now exists; this record picks no number from it.** |
| **Why no Target number** | The best bias point depends on the final geometry (tail width was not swept, kickback was not swept at any bias, and Row 4 and Row 2 both currently fail), so a number chosen now could be stale after the sizing work. Whether to ratify a Row 5 Target is a separate two-key act that should follow that study. |

## What this record does not do

- It changes no bound in the `README.md` Target or Stretch column.
- It does not edit DR-0002; DR-0002's text, including "Open items", stays as
  merged. A one-line cross-reference to this record is added to the end of
  DR-0002's "Open items" heading per the append-only convention (pointer
  only, no history rewritten).
- It does not decide relax-versus-redesign for Row 4.
- It does not ratify a whole-latch common-mode range or a Row 5 Target.
- It does not touch Row 2 or Row 3 status. (Later whole-latch noise work with
  the regenerative pair injected, #81, is outside this record's scope and
  needs its own status update.)
- It does not modify any `sim/` result; `sim/` is append-only.

## Alternatives considered

- **Edit `README.md` in place without a record.** Rejected: the table is
  ratified spec text and `CLAUDE.md` requires a record.
- **Edit DR-0002's Open items directly.** Rejected: records are append-only;
  later status follows from a higher-numbered record.
- **Fold a Row 5 Target into this record.** Rejected: see "Why no Target
  number" above.
- **Hold the Row 4 status until a decision on relax versus redesign.**
  Rejected: the front-page table would continue to understate a known
  Target miss in the meantime.

## Spec lines affected

`README.md` only, Measured and Status text of Rows 1, 4 and 5, the closing
"What ratified does and does not mean" paragraph, and the Target-spec intro
sentence that names Row 4's charge sub-bound as consistent-not-certified. No
Target or Stretch cell changes.

## Consequences

1. The front-page table shows Row 4's charge Target as NOT MET (39/45). That
   makes two ratified Targets the design currently misses (Rows 2 and 4a),
   which is also the state `klt signoff` already reports for T1 item 5.
2. A Row 4 relax-versus-redesign decision is now unblocked and belongs with
   the operator.
3. Row 1's `vcm-m050` completion (#89) and any Row 5 Target remain open.

## How this record gets ratified

As DR-0002: a two-key act per
[2AMLogic/2am#372](https://github.com/2AMLogic/2am/issues/372). The EE key
reviews the cited numbers against `sim/`; the market key reviews the Row 4
NOT MET wording and whether the row remains competitive as ratified (if it
cannot so find, DR-0002's rule is to escalate `loom:operator`). Status stays
`proposed` in the merged tree for the same reason DR-0002's does: status is
conferred by the merge commit.
