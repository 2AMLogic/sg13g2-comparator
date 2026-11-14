# 0004: Input common-mode range row (candidate, evidence-gated)

- **Status**: proposed. **This record is a draft, revised 2026-11-08 against
  `main` after the first round of ratification keys (see "Revision history").
  Its recommendation is unchanged: the row it defines is not yet ratifiable,
  because the Row 4b edge cells are 44/45 and the gate below is not met.** It
  proposes an input-common-mode-range row for the `README.md` target-spec
  table, states per row what the committed evidence does and does not
  support at the band edges, and names what is still needed before the row can
  be ratified. It moves no existing bound, edits no Target or Stretch cell,
  and changes no `README.md` text. Ratification, when the evidence exists, is
  the two-key merge of the PR that lands this record, exactly as DR-0002 "How
  this record gets ratified" describes (a `RATIFY-KEY: ee` and a
  `RATIFY-KEY: market` verdict from non-author reviewers; the merge commit is
  the ratification record). **The drafting agent holds neither key and this
  PR must not be hand-merged.**
- **Date**: 2026-10-10 (revised 2026-11-08)
- **Decided by**: Builder agent, issue
  [#160](https://github.com/2AMLogic/sg13g2-comparator/issues/160), drafting
  only.
- **Related**:
  [`0002-target-spec-ratification.md`](0002-target-spec-ratification.md)
  (ratified Rows 1 to 5 at `dut_vcm` only; "Open items" names the missing
  whole-latch common-mode sweep),
  [`0003-evidence-state-update-rows-1-4-5.md`](0003-evidence-state-update-rows-1-4-5.md)
  (recorded the #79 sweep as characterization and said "A binding range needs
  its own record"; this is that record),
  [#79](https://github.com/2AMLogic/sg13g2-comparator/issues/79) (offset
  common-mode band),
  [#89](https://github.com/2AMLogic/sg13g2-comparator/issues/89) (the two
  rejected `vcm-m050` offset points),
  [#92](https://github.com/2AMLogic/sg13g2-comparator/issues/92) (input-pair
  sizing study; may move the usable window),
  [#164](https://github.com/2AMLogic/sg13g2-comparator/issues/164) and
  [#165](https://github.com/2AMLogic/sg13g2-comparator/issues/165) (the
  campaigns this record asked for; both have landed, see the evidence table).
- **Supersedes**: none. DR-0002 and DR-0003 are not edited.
- **Superseded by**: none

## Context

The ratified table says the offset verdict holds "at nominal common mode"
and that "**No whole-latch common-mode range is ratified**" (`README.md`,
Offset sigma row). A comparator with no stated input common-mode range
has no usable interface contract: an integrator cannot tell over which `vcm`
window the Target rows hold. Who that integrator is, and what window they need,
is the subject of "Market framing" below.

`dut_vcm` is 0.6 V (`sim/dut.json`, `params.dut_vcm`; the notes there give
the reason: mid-rail at the nominal 1.2 V supply, with no driving circuit to
inherit a common mode from). In every bench the common mode is an absolute
DC source, `vcm cm 0 dc {dut_vcm}`, and it does not track the supply corner.
A window stated in volts therefore holds across the 1.08 / 1.20 / 1.32 V
supply corners as absolute volts, not as a fraction of VDD.

The only common-mode data on the whole latch is the #79 offset sweep at
`dut_vcm` − 50 mV, `dut_vcm` and `dut_vcm` + 50 mV. DR-0003 recorded it as
characterization only. This record turns that data, plus the data that is
still missing, into a proposed spec row.

Every claim about which records do and do not carry common-mode data was
checked against the committed tree while drafting this record, not copied
from the issue. The check is in "How the evidence state was established"
below.

## Candidate row

Proposed for addition to the `README.md` target-spec table **once the
evidence gate below is met**. It is not added by this PR.

| Parameter | Target (proposed) | Stretch | Condition |
|---|---|---|---|
| Input common-mode range | `dut_vcm` ± 50 mV, i.e. **0.55 … 0.65 V** (absolute, at every supply corner), over which all three of the following hold **at every PVT point** of the 45-point grid: Row 1 offset ≤ 15 mV 3σ (whole latch, Monte Carlo, ratified statistic); Row 3 decision time ≤ 1.5 ns at 50 mV overdrive; Row 4 signal-dependent differential residue ≤ 100 µV | none proposed | Evidence at three points of the window (both edges and nominal), each a full 45-point grid. The ratified bounds of Rows 1, 3 and 4 are used unchanged. |

What the row deliberately does **not** cover, with the reason:

- **Input-referred noise (Row 2).** Row 2 is NOT MET at nominal common mode
  on the compliance path (`README.md`, Row 2; grid-wide mean 1.305 mV rms
  against a 1.0 mV Target in the #81 campaign). A range over which Row 2
  "holds" cannot be claimed while it fails at the center. The row is silent
  on noise and says so; no noise campaign is part of the minimum set.
- **Kickback charge (Row 4a).** The Q_kick sub-bound is NOT MET at nominal
  (39/45 over 25 fC, DR-0003). The same reasoning applies. The kickback
  campaign below records Q_kick at the edges as characterization, and the row
  does not bound it.
- **Metastability sub-rows (τ ≤ 250 ps, ≤ 2.0 ns at 0.1 mV).** The
  decision-time campaign measures both. The row as drafted binds only the
  50 mV decision time named in issue #160. Folding the sub-rows into the hold
  list once #164 reports them is a choice for the key-holders, and it would
  tighten the row, not widen it.
- **Stretch columns.** Offset and decision-time Stretch bounds are already
  missed at nominal (27/45 and 9/45). No Stretch is proposed for the range.

## Market framing

*(Added in the 2026-11-08 revision, answering the market key's Required
change B.)* The first draft called the row the "usable interface contract for
a standalone comparator". That wording invited a comparison with packaged
rail-to-rail comparators (continuous-time, 1.6 … 5.5 V supplies, input range
at or beyond the rails), against which a 100 mV window is not competitive, and
this record does not claim it is. The framing is withdrawn. The row is offered
under this one instead:

- **What the block is.** A *clocked decision element* for a driver that sets
  the common mode: a StrongARM latch sampled at 33.3 MHz, built as the
  reusable decision element for a future sg13g2 SAR ADC (`README.md`, "Why this
  block, on this PDK"). It is "standalone" in the one sense the README uses:
  its spec rows are measured for their own sake. It is not a general-purpose
  comparator for arbitrary-CM signals, and the row does not hold it out as one.
- **Who the buyer is.** A SAR ADC (or similar clocked front end) whose
  capacitive DAC and sampling network define the comparator's input common
  mode. In that class a narrow window around a fixed, designed CM is normal,
  because the driver, not the signal, sets the CM. No named public datasheet
  was found for embedded comparator IP in that class that states an input CM
  range (market key, comp table row 3), so this is stated as the design intent,
  not as a market norm.
- **What the driver must hold.** The row is a contract on the driver:
  **the input common mode must stay within ±50 mV of an absolute 0.60 V
  (0.55 … 0.65 V) at every supply and temperature corner of the 45-point
  grid.** The window is absolute, not VDD-tracking: it is 9.3 % / 8.3 % / 7.6 %
  of VDD at 1.08 / 1.20 / 1.32 V, and it sits above mid-rail at 1.08 V (0.54 V)
  and below mid-rail at 1.32 V (0.66 V). A driver whose CM tracks VDD must
  therefore be checked against this window at the supply extremes, not assumed
  to satisfy it.
- **The gap, stated.** Against rail-to-rail packaged parts the window is about
  12× narrower as a fraction of supply (market key). A buyer who cannot hold
  the CM to ±50 mV of 0.60 V is not served by this block, and the `README.md`
  cell for the row must say so (see "Text for the README cell").
- **The alternative, not taken here.** A materially wider window (the
  general-purpose positioning) needs its own campaigns and its own record
  (Decision item 4, last bullet). This record neither proposes nor forecloses
  it. The window is not narrowed to fit the evidence either: it stays ±50 mV,
  and the edge cells that do not read Supported are reported as such below.

**Interpolation assumption, stated for the EE key.** Three measured points
do not prove that the window's interior behaves. The row claims a closed
interval on the basis that each metric moves smoothly between the measured
points. With all three campaigns now committed:

- Offset: paired 3σ ratio to nominal 0.977 (0.919 … 1.028) at `vcm-m050` and
  1.036 (0.969 … 1.148) at `vcm-p050`, paired correlation ≥ 0.952
  ([`comparison.md`](../../sim/comparator-offset-cm-band/campaigns/20261009-5185f52/comparison.md),
  "Paired sensitivity vs nominal"). A few-percent effect, monotonic in the
  mean but **not** at every point (for example `tt_-40c_1.08v` is above
  nominal at both edges, 1.019 and 1.055); every movement is inside the 9.1 %
  per-point precision.
- Decision time (#164): monotonic at every one of the 45 points (slower at
  −50 mV by +0.030 … +0.079 ns, faster at +50 mV).
- Residue (#165): nearly flat, except where the kickback bench rejects a point
  (below). Those two rejects are not a smooth-variation signal, and they are
  the reason the assumption is not extended to the interior for Row 4b.

## Evidence by row at the band edges

*(Rewritten 2026-11-08 against `main`; the first draft predated #164, #165 and
the #89 supplement.)* "Supported" means a committed, valid 45-point population
exists at that condition and every valid point is inside the ratified bound.
Gate wording is unchanged: every edge cell must read Supported.

| Row (bound) | `vcm-m050` (0.55 V) | nominal (0.60 V) | `vcm-p050` (0.65 V) |
|---|---|---|---|
| **1. Offset ≤ 15 mV 3σ** (klt trail) | **Partial, not supported**: parent campaign 43/45 valid, 6.892 … 11.427 mV, all 43 inside 15 mV; `tt_-40c_1.32v` and `sf_-40c_1.20v` REJECTED (one ngspice "timestep too small" abort each). The separately labelled #89 supplement ([`20261105-58805e2fa-maxstep20p-r2.md`](../../sim/comparator-offset-cm-band/campaigns/20261105-58805e2fa-maxstep20p-r2.md), [`…-r2-resume.md`](../../sim/comparator-offset-cm-band/campaigns/20261105-58805e2fa-maxstep20p-r2-resume.md)) re-runs those two points at `tran 100p 990n 0 20p`: 60/60 valid, 3σ 7.137 mV and 8.690 mV, max \|Δvos\| against the parent 0.00078 mV. See "What the #89 supplement does and does not complete" | **Supported**: harness record [`20260917-060858-ea40b57`](../../sim/comparator-offset-transient-mc/records/20260917-060858-ea40b57.md), 7.456 … 10.537 mV, 45/45. klt trail `vcm-nom` 6.913 … 12.093 mV, 45/45, bit-identical to [`20261009-d73a9ac`](../../sim/klt-corner-verification/campaigns/20261009-d73a9ac/grading.md) | **Supported**: 45/45 valid, 6.913 … 12.872 mV, all inside 15 mV ([`comparison.md`](../../sim/comparator-offset-cm-band/campaigns/20261009-5185f52/comparison.md)). The #89 supplement's `vcm-p050` populations are also 60/60 (3σ 7.123 mV, 9.148 mV) |
| **3a. Decision time ≤ 1.5 ns at 50 mV** (with τ ≤ 250 ps and ≤ 2.0 ns at 0.1 mV) | **Supported**: 45/45, 0.640 … 0.9106 ns, 0 Target fails; τ ≤ 168.1 ps, 0.1 mV ≤ 1.736 ns ([`20261011-94b6bc5b4`](../../sim/comparator-decision-cm-band/campaigns/20261011-94b6bc5b4/comparison.md), #164, PR #208) | **Supported**: harness [`20260916-113309-180cca7`](../../sim/comparator-regeneration/records/20260916-113309-180cca7.md), 0.596 … 0.850 ns; klt `20261009-d73a9ac` row 3a, 0.5965 … 0.8502 ns, 45/45. Reproduced bit-identically by #164 (945 values, 0 mismatches) | **Supported**: 45/45, 0.5604 … 0.803 ns, 0 Target fails; τ ≤ 166.7 ps, 0.1 mV ≤ 1.617 ns (same campaign) |
| **4b. Residue ≤ 100 µV** | **INCOMPLETE, not supported**: 44/45 valid, 1.728 … 15.887 µV. `ss/1.200V/-40C` REJECTED: validity gate `dout_float_big_end` = 6.81e-9 V/V, needs ≥ 0.9 (the floating-input branch did not decide to the correct rail) ([`20261011-165`](../../sim/comparator-kickback-cm-band/campaigns/20261011-165/comparison.md), #165, PR #212) | **Supported**: harness [`20260916-022249-36773c7`](../../sim/comparator-kickback/records/20260916-022249-36773c7.md), 1.70 … 15.40 µV; klt `20261009-d73a9ac` row 4b, 2.034 … 15.63 µV, 45/45. Reproduced 1215/1215 exactly by #165 | **INCOMPLETE, not supported**: 44/45 valid, 2.458 … 15.232 µV. `ss/1.080V/-40C` REJECTED: `dout_float_small_end` = 6.18e-9 V/V, same gate |
| *(2. Noise, not in the row)* | no record | NOT MET (Row 2) | no record |
| *(4a. Q_kick, not in the row)* | 29.376 fC max, 26/45 over 25 fC (reported) | NOT MET: 31.462 fC max, 39/45 over 25 fC (DR-0003) | 33.570 fC max, 44/45 over 25 fC (reported) |

Summary: **three of the six edge cells are Supported** (Row 3a at both edges
and Row 1 at +50 mV), **one is partial** (Row 1 at −50 mV, 43/45
parent plus a labelled supplement), and **two are INCOMPLETE** (Row 4b at both
edges, 44/45). The gate is **not met**.

### Observations carried with the table

- **Stretch.** Decision-time Stretch (≤ 0.8 ns at 50 mV) is missed at 12/45
  points at −50 mV, against 9/45 at nominal and 1/45 at +50 mV. No Stretch is
  proposed for the row; the −50 mV edge is the binding side for it.
- **Q_kick trend.** Q_kick rises about 2 fC per +50 mV (max 29.4 / 31.5 /
  33.6 fC at −50 mV / nominal / +50 mV) and the count over 25 fC rises
  26 → 39 → 44 of 45. Row 4a is not bound by this row. Whoever fixes Row 4a
  needs to know that the high-CM edge is its binding point.
- **Metastability sub-rows.** Both edges meet τ ≤ 250 ps and ≤ 2.0 ns at
  0.1 mV with margin (worst 168.1 ps and 1.736 ns, both at `vcm-m050`
  `ss_-40c_1.08v`). They are folded into the Row 3a hold list above, which
  tightens the row and costs nothing on this evidence.

### Which offset trail is graded

The row grades the **klt trail** at all three conditions. It is the only trail
that has the nominal and both edges, produced by the same bench (#62 via #79),
so the three columns are comparable. The harness nominal record is listed
beside it for the ratified-statistic continuity, but it is not mixed into the
edge comparison. The known klt/harness gap (#82, ratio 1.136) is therefore
common to all three columns. The klt nominal is 45/45 inside 15 mV, so the
choice changes no verdict.

### What the #89 supplement does and does not complete

The supplement reruns the two rejected `vcm-m050` populations (and, as
controls, the same two points at `vcm-nom` and `vcm-p050`) with one tighter max
step. All six populations are 60/60 and the step alone moves vos by at most
0.00078 mV over 1978 paired draws. Its own README keeps the question of "bench
artifact versus a real low-CM / cold weakness" **open**, and says nothing is
merged into the parent's 43/45. This record follows that: the supplement is
**evidence that the two points are probably a time-step-control artifact**, not
a completion of the parent cell. The Row 1 `vcm-m050` cell therefore stays
**Partial** for the gate. The key-holders may decide that the supplement is
sufficient for ratification; this record does not decide that for them.

### The two Row 4b rejections: disposition

The kickback bench rejects one point at each band edge on a
decision-correctness gate: the floating (non-charge-restoring, 1 GΩ / 1 pF)
input branch did not resolve to the correct rail (≈ 6e-9 V/V against ≥ 0.9).
This is not missing data and not a convergence abort. At face value it is a
failure to decide at a cold, slow-process point at each edge. What is known:

- The decision-time bench (#164) resolves 45/45 at both edges, including both
  of these points (`ss_-40c_1.20v` and `ss_-40c_1.08v`), with ≥ 7.4 decades of
  resolution. So the latch decides correctly there when driven by the
  decision-time bench's stimulus.
- The kickback bench differs in the input network (1 GΩ / 1 pF non-restoring
  source, floating branch). Whether the reject is specific to that
  network, an initial-state or settling artifact of the floating branch at the
  shifted CM, or a real marginal decision is **not shown by any committed
  evidence**. No probe of the rejected points has been committed.
- The unvalidated residue at the two rejected points (2.148 µV and 2.250 µV)
  is far below the bound, but the validity gate exists precisely so such a
  number is not used. This record does not use it.
- Whether these two rejects and the two cold (−40 °C) offset aborts of #89
  share a cause is also not shown. All four are `-40C` points at an edge, which is
  suggestive and nothing more.

This record therefore does **not** explain the rejects and does not treat them
as an artifact. Under Decision item 4 below, a Row 4b failure at both edges
leaves the row unratified, and a narrower window does not rescue it (the rejects
are at opposite edges and an interior CM has not been shown to resolve either).
The way to close the gate is a targeted, separately labelled supplementary
probe of exactly those two points, as #89 did for offset. That probe is filed
as a follow-up issue (linked from the PR) and is not run by this revision.

## How the evidence state was established

- `sim/dut.json` binds `dut_vcm = 0.6` and nothing else.
- Every committed SPICE body in `sim/` that sets `dut_vcm` sets it to 0.6
  (`.param dut_vcm=0.6`, 69 occurrences, no other value). The only bodies
  that move the common mode are the #79 ones, via `.param vcm_delta`
  (generated by `sim/kltsim/cmband.py`; bodies under
  `sim/comparator-offset-cm-band/campaigns/20261009-5185f52/`). Apart from
  `cmband.py` and its test, the #79 campaign bodies and
  `sim/comparator-offset-cm-band/README.md`, the #164 and #165 band benches
  (`sim/comparator-decision-cm-band/`, `sim/comparator-kickback-cm-band/`,
  `sim/kltsim/cmdecision.py`, `sim/kltsim/kickback_cmband.py`) mention
  `vcm_delta`. No other ratified-row bench moves the common mode.
- The decision-time, kickback and noise campaigns used by the ratified rows
  (`sim/klt-corner-verification/campaigns/20261009-d73a9ac/{regeneration,kickback,transient_noise}.body.spice`,
  the #80 `ib_*` sweeps, the #81 `tn_full_*` bodies and the #92 sizing bodies)
  all carry `dut_vcm=0.6` with no `vcm_delta`.
  [`sim/klt-corner-verification/README.md`](../../sim/klt-corner-verification/README.md)
  states it directly: "Common mode is fixed at `dut_vcm = 0.6 V`, as in every
  source bench", and `sim/klt-corner-verification/rows.json` scopes the
  offset row to "dut_vcm = 0.6 V; no common-mode claim".
- The harness benches (`sim/comparator-regeneration/`,
  `sim/comparator-kickback/`, `sim/comparator-transient-noise/`) take
  `dut_vcm` from `sim/dut.json`. Their testbenches set it with
  `vcm cm 0 dc {dut_vcm}`, and they have no common-mode sweep.

## Campaigns requested and their state

All were `klt sim` requests on the batch fleet (`KLT_SIM_BACKEND=batch`), not
hand-launched ngspice grids.

| # | Closes | State |
|---|---|---|
| [#89](https://github.com/2AMLogic/sg13g2-comparator/issues/89) | Row 1 at `vcm-m050` | Landed as a labelled supplement: 6/6 populations 60/60 (PRs #402, #403); the parent stays 43/45. Artifact-vs-weakness open |
| [#164](https://github.com/2AMLogic/sg13g2-comparator/issues/164) | Row 3a at both edges | Landed (PR #208): 45/45 at both edges, nominal reproduced bit-identically |
| [#165](https://github.com/2AMLogic/sg13g2-comparator/issues/165) | Row 4b at both edges | Landed (PR #212): 44/45 at each edge, one validity-gate reject per edge, nominal reproduced exactly |
| [#405](https://github.com/2AMLogic/sg13g2-comparator/issues/405) (follow-up) | The two Row 4b rejects | Targeted, separately labelled supplementary probe of `vcm-m050` `ss/1.200V/-40C` and `vcm-p050` `ss/1.080V/-40C`, same shape as the #89 supplement. Not run by this revision |

No noise campaign is listed, because Row 2 is not part of the candidate row.

**Dependency on #92.** All the data above, both existing and requested, is on
the DR-0001 geometry. If the #92 sizing study changes the input pair or the
tail, the edge data must be re-taken on the final geometry before the row is
ratified. A wider pair could move the usable window in either direction.
This record proposes no window for a geometry that has not been measured.

## Decision (proposed)

1. **Define** the candidate row above: `dut_vcm` ± 50 mV (0.55 … 0.65 V),
   holding Row 1, Row 3a and Row 4b at their ratified bounds at every PVT
   point.
2. **Do not ratify it on the current evidence.** Three of six edge cells are
   Supported, one is partial and two are INCOMPLETE (44/45). Ratifying a row
   with an incomplete edge would make it silently hold for fewer points than
   it states, which issue #160 explicitly rejects.
3. **Gate**: the row becomes ratifiable when every edge cell in the evidence
   table reads Supported, on the geometry current at that time (see #92).
   Today that needs (a) the Row 4b rejects dispositioned by committed
   evidence (the follow-up probe), and (b) the key-holders' ruling on whether
   the #89 supplement completes Row 1 at `vcm-m050`.
4. **If an edge fails**, the window narrows; it never widens:
   - one edge fails any of the three rows: propose the one-sided window
     (0.60 … 0.65 V or 0.55 … 0.60 V) that the evidence supports;
   - both edges fail: leave the row unratified. **This is Row 4b's present
     state**, pending the follow-up probe; The status quo stays
     (nominal-only, `README.md` unchanged), and the gap stays explicit;
   - a window wider than ± 50 mV is out of scope for this record. It would
     need its own campaigns and its own record.

**Recommended path for the key-holders (Option B below).** Keep this PR open
and unmerged until the gate is met. Then revise the evidence table in this
same record with the new campaign paths and the window the evidence actually
supports, and add the row to `README.md` in that revision. The two keys are
applied to that revised PR. This is the pattern DR-0002 used, which folded in
new evidence before merge (its 2026-09-21 revision).

## Text for the README cell

*(Market key Required change C and non-blocking note 1; EE key Required
change C.)* When the gate is met, the ratifying revision adds the row to the
`README.md` target-spec table and changes the Offset-sigma sentence "**No
whole-latch common-mode range is ratified**" to point at this record. The row's
own cell carries, and a reader must not have to open this record to find:

> Input CM must be held within **0.55 … 0.65 V, absolute** (not VDD-tracking:
> mid-rail is 0.54 V at 1.08 V supply and 0.66 V at 1.32 V). Over that window
> offset (≤ 15 mV 3σ), 50 mV decision time (≤ 1.5 ns, τ ≤ 250 ps, ≤ 2.0 ns at
> 0.1 mV) and signal-dependent residue (≤ 100 µV) hold at every PVT point.
> **Not covered by this row:** input-referred noise (Row 2, NOT MET at nominal)
> and kickback charge (Row 4a, NOT MET at nominal; Q_kick rises to 33.6 fC max,
> 44/45 points over 25 fC, at +50 mV). The window is designed for a driver that
> sets the common mode (SAR DAC / sampling network); it is about 8 % of VDD and
> is not a rail-to-rail input.

The cell is not added by this PR because the gate is not met.

## Revision history

- **2026-10-10**: first draft (issue #160).
- **2026-11-08**: revised after the first round of ratification keys (EE key
  and market key, both on head `89130fa`). Per finding:
  - EE **A** (stale evidence): merged `main`; rewrote the edge table from
    #208, #212 and the #89 supplement; stated the graded trail; stated that
    the supplement does not by itself complete the −50 mV offset cell.
  - EE **B** (Row 4b rejects): dispositioned honestly. Nothing committed
    explains them, so they are not claimed as an artifact; Decision item 4
    applies; a follow-up probe is filed.
  - EE **C** (complete or do not merge): the record does not add the
    `README.md` row, because the gate is not met. It stays unmerged, which is
    its own Option B. The README cell text is drafted above for the ratifying
    revision.
  - Market **A** is the same as EE A. Market **B**: option (i) taken; the
    "standalone comparator" framing is withdrawn and the driver CM accuracy
    is named ("Market framing"). Market **C**: cell text drafted above.
  - Non-blocking: absolute-vs-mid-rail note, Stretch at −50 mV, Q_kick trend,
    metastability sub-rows folded in, `vcm_delta` sentence corrected.

## Alternatives considered

- **Option A: merge now as "row defined, not in force".** Rejected as the
  recommendation, though it remains open to the key-holders. A merged
  record whose row is not in force puts a second, inactive common-mode
  sentence next to the ratified table, and a later record would still be
  needed to activate it. It does have one advantage: the gap is owned on
  `main` sooner.
- **Option B: hold unmerged until the gate is met, then revise and ratify.**
  Recommended (see above).
- **Publish the ±50 mV offset numbers as the row now.** Rejected (issue
  #160): only offset has been swept, and even offset is 43/45 at the low
  edge.
- **Ratify a one-sided window 0.60 … 0.65 V now, on offset alone.**
  Rejected for the same reason. Decision time and residue have no data at
  0.65 V either.
- **Leave the range unratified with no record.** This is the acceptable
  status quo, but it leaves the interface contract missing with no owner. This
  record keeps the gap explicit and states what closes it.

## What this record does not do

- It changes no bound in the `README.md` Target or Stretch column and adds no
  row to the table.
- It does not edit DR-0002 or DR-0003.
- It does not ratify any common-mode range.
- It does not relax any row, including Row 2 or Row 4a, which fail at
  nominal.
- It does not modify any `sim/` result; `sim/` is append-only.
- It runs no simulation. The campaigns were #89, #164 and #165; the Row 4b
  probe is follow-up issue [#405](https://github.com/2AMLogic/sg13g2-comparator/issues/405).

## Spec lines affected

None in this PR. In the ratifying revision (Option B): one new row in the
`README.md` target-spec table, plus the sentence in the Offset sigma row
"**No whole-latch common-mode range is ratified**", which would then point to
this record.

## How this record gets ratified

As DR-0002: a two-key act per
[2AMLogic/2am#372](https://github.com/2AMLogic/2am/issues/372). The EE key
checks the evidence table against `sim/` (including the interpolation
assumption and which offset trail is graded). The market key checks whether a
±50 mV window, or whatever narrower window the evidence supports, is
competitive as an interface contract for a clocked decision element whose
driver sets the common mode (see "Market framing"), with the gap to
rail-to-rail packaged parts stated.
If it cannot so find, DR-0002's rule is to escalate to `loom:operator`, not to
widen the window. Status stays `proposed` in the merged tree for the same
reason DR-0002's does: status is conferred by the merge commit.
