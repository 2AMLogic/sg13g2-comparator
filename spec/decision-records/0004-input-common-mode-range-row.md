# 0004: Input common-mode range row (candidate, evidence-gated)

- **Status**: proposed. Only nominal common mode (0.60 V) is ratified.
  Each band edge still lacks a valid Row 4b residue measurement at one cold
  corner. This PR stays open until the evidence gate below is met and both
  independent keys review the ratifying revision.
- **Date**: 2026-10-10 (revised 2026-11-25)
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
inherit a common mode from). The band campaigns add a fixed voltage to the nominal
source. Thus 0.55, 0.60 and 0.65 V denote the same absolute input common modes
at all three supplies (1.08, 1.20 and 1.32 V).

DR-0003 recorded the #79 offset sweep as characterization. The evidence
below also includes timing (#164), kickback (#165) and the subsequent
investigations of rejected measurements.

## Candidate row

Proposed for addition to the `README.md` target-spec table **once the
evidence gate below is met**. It is not added by this PR.

| Parameter | Target (proposed) | Stretch | Condition |
|---|---|---|---|
| Input common mode | Candidate operating points **0.55, 0.60 and 0.65 V absolute**. At each point, whole-latch offset ≤ 15 mV (3σ, Row 1), decision time ≤ 1.5 ns at 50 mV overdrive (Row 3a), and signal-dependent differential residue ≤ 100 µV (Row 4b). | none proposed | All 45 PVT corners at each stated input common mode. Only 0.60 V is currently ratified. |

The design goal in #160 is a continuous ±50 mV tolerance around 0.60 V.
This draft limits the proposed guarantee to the three measured settings.
Extending it between them would require evidence that bounds interior
offset, decision time and residue over the same PVT grid.

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
- **Metastability sub-rows (τ ≤ 250 ps, ≤ 2.0 ns at 0.1 mV).** The campaign
  reports both as characterization at the two edges. Row 3a in this proposal
  binds only the 50 mV decision time specified by #160.
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
- **Driver common mode.** The intended driver sets an absolute 0.60 V.
  A driver that uses VDD/2 delivers 0.54 V at 1.08 V supply and 0.66 V at
  1.32 V supply, already 10 mV outside the respective design edges before
  driver error. Only nominal CM currently has a joint specification. A driver tolerance
  requires evidence for intermediate common modes.
- **Market finding.** The market review found a driver-set common mode
  plausible for a SAR front end. Its comparisons with packaged comparators
  and SAR ADC inputs did not establish a competitive joint guarantee of
  offset, timing and residue for embedded latch IP. That finding remains
  open for the market key on the eventual supported scope. [Market review](https://github.com/2AMLogic/sg13g2-comparator/pull/166#issuecomment-7048032219)

**Between the samples.** At all 45 PVT points the 50 mV decision time decreases
across the three sampled voltages. Offset does not follow a single direction
at every corner. For example, at `tt_-40c_1.08v` the low- and high-edge 3σ
ratios to nominal are 1.019 and 1.055. Two edge residue observations are
invalid. These measurements give no worst-case bound between samples for the
three quantities together. [Paired offset comparison](../../sim/comparator-offset-cm-band/campaigns/20261009-5185f52/comparison.md)

## Evidence by row at the band edges

For this draft, **Supported** means every one of the 45 PVT corners has
a valid measurement within the stated bound at that sampled CM. For offset,
each corner contributes a complete 60-draw population. The grading rule
below identifies the source of each population. Status here describes
evidence for the proposal. Ratification still applies only at nominal CM.

| Row (bound) | `vcm-m050` (0.55 V) | nominal (0.60 V) | `vcm-p050` (0.65 V) |
|---|---|---|---|
| **1. Offset ≤ 15 mV 3σ** (klt trail) | **Supported for the draft gate, from two records**: parent campaign 43/45 valid, 6.892 … 11.427 mV, all 43 inside 15 mV; `tt_-40c_1.32v` and `sf_-40c_1.20v` REJECTED (one ngspice "timestep too small" abort each). The separately labelled #89 supplement ([`20261105-58805e2fa-maxstep20p-r2.md`](../../sim/comparator-offset-cm-band/campaigns/20261105-58805e2fa-maxstep20p-r2.md), [`…-r2-resume.md`](../../sim/comparator-offset-cm-band/campaigns/20261105-58805e2fa-maxstep20p-r2-resume.md)) re-runs those two points at `tran 100p 990n 0 20p`: 60/60 valid, 3σ 7.137 mV and 8.690 mV, max \|Δvos\| against the parent 0.00078 mV. See “Grading the two low-CM offset reruns” | **Supported**: harness record [`20260917-060858-ea40b57`](../../sim/comparator-offset-transient-mc/records/20260917-060858-ea40b57.md), 7.456 … 10.537 mV, 45/45. klt trail `vcm-nom` 6.913 … 12.093 mV, 45/45, bit-identical to [`20261009-d73a9ac`](../../sim/klt-corner-verification/campaigns/20261009-d73a9ac/grading.md) | **Supported**: 45/45 valid, 6.913 … 12.872 mV, all inside 15 mV ([`comparison.md`](../../sim/comparator-offset-cm-band/campaigns/20261009-5185f52/comparison.md)). The #89 supplement's `vcm-p050` populations are also 60/60 (3σ 7.123 mV, 9.148 mV) |
| **3a. Decision time ≤ 1.5 ns at 50 mV** (τ and 0.1 mV values reported separately as characterization) | **Supported**: 45/45, 0.640 … 0.9106 ns, 0 Target fails; τ ≤ 168.1 ps, 0.1 mV ≤ 1.736 ns ([`20261011-94b6bc5b4`](../../sim/comparator-decision-cm-band/campaigns/20261011-94b6bc5b4/comparison.md), #164, PR #208) | **Supported**: harness [`20260916-113309-180cca7`](../../sim/comparator-regeneration/records/20260916-113309-180cca7.md), 0.596 … 0.850 ns; klt `20261009-d73a9ac` row 3a, 0.5965 … 0.8502 ns, 45/45. Reproduced bit-identically by #164 (945 values, 0 mismatches) | **Supported**: 45/45, 0.5604 … 0.803 ns, 0 Target fails; τ ≤ 166.7 ps, 0.1 mV ≤ 1.617 ns (same campaign) |
| **4b. Residue ≤ 100 µV** | **INCOMPLETE, not supported**: 44/45 valid, 1.728 … 15.887 µV. `ss/1.200V/-40C` REJECTED: validity gate `dout_float_big_end` = 6.81e-9 V/V, needs ≥ 0.9 (the floating-input branch ended at the wrong rail) ([`20261011-165`](../../sim/comparator-kickback-cm-band/campaigns/20261011-165/comparison.md), #165, PR #212) | **Supported**: harness [`20260916-022249-36773c7`](../../sim/comparator-kickback/records/20260916-022249-36773c7.md), 1.70 … 15.40 µV; klt `20261009-d73a9ac` row 4b, 2.034 … 15.63 µV, 45/45. Reproduced 1215/1215 exactly by #165 | **INCOMPLETE, not supported**: 44/45 valid, 2.458 … 15.232 µV. `ss/1.080V/-40C` REJECTED: `dout_float_small_end` = 6.18e-9 V/V, same gate |
| *(2. Noise, not in the row)* | no record | NOT MET (Row 2) | no record |
| *(4a. Q_kick, not in the row)* | 29.376 fC max, 26/44 valid points over 25 fC | NOT MET: 31.462 fC max, 39/45 over 25 fC (DR-0003) | 33.570 fC max, 44/44 valid points over 25 fC |

**Four of six edge cells have supporting measurements** under the proposed
offset grading rule. Row 4b remains incomplete at both edges (44/45 each).
Only the nominal column has all three rows ratified.

### Observations carried with the table

- **Stretch.** Decision-time Stretch (≤ 0.8 ns at 50 mV) is missed at 12/45
  points at −50 mV, against 9/45 at nominal and 1/45 at +50 mV. No Stretch is
  proposed for the row; the −50 mV edge is the binding side for it.
- **Q_kick trend.** Q_kick rises about 2 fC per +50 mV (max 29.4 / 31.5 /
  33.6 fC at −50 mV / nominal / +50 mV) and the count over 25 fC rises
  from 26/44 valid points to 39/45 and 44/44. Row 4a is not bound by this row. Whoever fixes Row 4a
  needs to know that the high-CM edge is its binding point.
- **Metastability sub-rows.** Both edges meet τ ≤ 250 ps and ≤ 2.0 ns at
  0.1 mV with margin (worst 168.1 ps and 1.736 ns, both at `vcm-m050`
  `ss_-40c_1.08v`). These margins characterize the edges. The proposed
  timing guarantee is ≤ 1.5 ns at 50 mV overdrive.

### Which offset trail is graded

The row grades the **klt trail** at all three conditions. It is the only trail
that has the nominal and both edges, produced by the same bench (#62 via #79),
so the three columns are comparable. The harness nominal record is listed
beside it for the ratified-statistic continuity, but it is not mixed into the
edge comparison. The reported klt/harness ratio of 1.136 (#82) was
measured at nominal CM. The klt nominal is 45/45 inside 15 mV, so the
choice changes no verdict.

### Grading the two low-CM offset reruns

For the proposed gate, use the #79 parent population at each of its valid
corners. At 0.55 V use the #89 supplement's entire population for each of the
two rejected corners only. The parent lost draw mc12 at TT/−40 °C/1.32 V and
mc23 at SF/−40 °C/1.20 V. At a uniform 20 ps maximum step, the supplement
completed all 60 matched draws at each corner, giving 3σ of 7.137 mV and
8.690 mV respectively. Both are below 15 mV.

The bench, mismatch seeds (base 20260916), 3 mV quantization step and
variance correction are the same. The maximum absolute change across 1,978
paired valid draws was 0.00078 mV. This supports using the two complete
reruns for those individual corners. No draw is pooled or substituted within
a population. The parent remains 43/45 at low CM. The cause of its two
aborts remains open. The EE key must review this grading rule on the
ratifying revision. [Completed #89 supplement](../../sim/comparator-offset-cm-band/campaigns/20261105-58805e2fa-maxstep20p-r2-resume.md)

### Why the two Row 4b measurements are still missing

The #405 probe reproduced #165's wrong rail at both rejected points. A 20 ps
maximum step preserved both failures. The bench programs 1 mV and 100 mV on
its two floating branches. With the specified 1 GΩ / 1 pF load, the measured
input differentials at the 30 ns strobe were much smaller. [#405 probe measurements](../../sim/comparator-kickback-cm-band/campaigns/20261108-405-probe/comparison.md)

| Edge at SS/−40 °C | 1 mV / 100 mV branches at strobe (#405) | Original 55 ns decision gate (minimum 0.9 V/V) | Valid residue at this corner |
|---|---|---|---|
| 0.55 V CM, 1.20 V supply | 23.56 µV / 2.356 mV | Large branch 6.81 × 10⁻⁹ | Missing |
| 0.65 V CM, 1.08 V supply | 16.89 µV / 1.689 mV | Small branch 6.18 × 10⁻⁹ | Missing |

In #415 the forced-DC arm seeded the latch outputs low, opposite the
expected decision. At both edge corners the DC solve failed and the outputs
were already high before the strobe. All three 55 ns gate readings then
passed without a transition, while the input differential remained collapsed.
At the **0.60 V controls** at the same supplies and temperature, the outputs
started low, the inputs reached the programmed differential to within 0.1%,
and the outputs switched high after the strobe. The probes identify the
recorded edge failures as solver-state artifacts. Neither the original
residues (2.148 and 2.250 µV) nor the forced-DC endpoint passes qualify
either edge. [#415 forced-DC results and initial-state evidence](../../sim/comparator-kickback-cm-band/campaigns/20261114-415-forceddc/README.md)

To close either cell, measure the programmed differential on both floating
branches at the strobe, show a transition from a known opposite state on
that strobe and verify all three 55 ns gates. Only then grade the measured
signal-dependent differential residue against 100 µV with the original
load. The two corner measurements and their nominal controls are tracked
in [#552](https://github.com/2AMLogic/sg13g2-comparator/issues/552).

## Sources and replay limits

The #79 offset, #164 decision-time and #165 kickback decks all apply
`dut_vcm + vcm_delta` to an absolute source. The nominal harness takes
`dut_vcm = 0.6` from [the DUT parameters](../../sim/dut.json). The band
campaigns reproduce their respective nominal references before comparing
the edges.

The three #165 envelopes record the same SHA-256 for `cornerMOSlv.lib`,
`03d505847c880d233b341be115a1e5460edf4d8e9b3e8a7df791a52fa4455d67`.
The reference campaign verified this top-level library against the repository's
IHP Open PDK v0.3.0 installation. The envelope's PDK version is null and the
library digest does not identify its transitive includes or loaded binaries.
Exact replay of those dependencies therefore remains unverified.
[Low-edge envelope](../../sim/comparator-kickback-cm-band/campaigns/20261011-165/vcm-m050/kickback.envelope.json) · [Reference campaign provenance](../../sim/klt-corner-verification/README.md#toolchain-and-provenance-actually-used) · [PDK release and archive digest](../../sim/pdk.json)

## Campaigns requested and their state

| Issue | Measurement | State |
|---|---|---|
| [#89](https://github.com/2AMLogic/sg13g2-comparator/issues/89) | Row 1 at `vcm-m050` | Landed as a labelled supplement: 6/6 populations 60/60 (PRs #402, #403); the parent stays 43/45. Artifact-vs-weakness open |
| [#164](https://github.com/2AMLogic/sg13g2-comparator/issues/164) | Row 3a at both edges | Landed (PR #208): 45/45 at both edges, nominal reproduced bit-identically |
| [#165](https://github.com/2AMLogic/sg13g2-comparator/issues/165) | Row 4b at both edges | Landed (PR #212): 44/45 at each edge, one validity-gate reject per edge, nominal reproduced exactly |
| [#405](https://github.com/2AMLogic/sg13g2-comparator/issues/405) | Reproduction of the two Row 4b rejects | Both reproduced, including with a 20 ps maximum step. |
| [#415](https://github.com/2AMLogic/sg13g2-comparator/issues/415) | Initial-state controls | Solver-state artifacts identified. A post-strobe decision was demonstrated at the two nominal controls only. |
| [#552](https://github.com/2AMLogic/sg13g2-comparator/issues/552) | Valid Row 4b edge measurements | Requested at the two SS/−40 °C corners listed above, with the original load. |

No noise campaign is listed, because Row 2 is not part of the candidate row.

**Geometry.** These campaigns used the DR-0001 input pair. The closed #92
sizing study characterized an 8 µm alternative. Adoption is a separate
decision. If the geometry changes, the band evidence for the old geometry
cannot establish these limits for the new latch. [Adoption issue #476](https://github.com/2AMLogic/sg13g2-comparator/issues/476)

## Decision (proposed)

Keep the ratified specification at 0.60 V and hold this PR open (Option B).
Before adding a sampled edge, every bound in the candidate row must have
valid evidence at all 45 PVT corners for the geometry to be ratified. This
requires the missing Row 4b measurement at that edge and EE acceptance of the
stated offset grading rule. If only one edge qualifies, propose that sampled
setting alongside nominal. If neither qualifies, retain nominal only.

Even if both edges qualify, 0.55, 0.60 and 0.65 V are three operating points.
A continuous window needs additional evidence bounding all three metrics
between those points. A wider window would need its own record.

## Text for the README cell

The following is proposed wording **only if both sampled edges qualify**.
The ratifying revision must list only the settings that actually qualify.

> Input common mode (absolute) at 0.55, 0.60 and 0.65 V. At each listed setting
> and all 45 PVT corners, whole-latch offset is ≤ 15 mV (3σ), decision time is
> ≤ 1.5 ns at 50 mV overdrive and signal-dependent differential residue is
> ≤ 100 µV. Intermediate common modes are unqualified. The driver sets CM
> independently of VDD (VDD/2 is 0.54 V and 0.66 V at the supply extremes).
> The edge τ and 0.1 mV timing results are characterization. Input noise
> (Row 2) and kickback charge (Row 4a) are outside this row. Both miss their
> nominal targets. At 0.65 V the reported maximum charge is 33.6 fC.

Until ratification, the existing README statement that no whole-latch
common-mode range is ratified continues to apply.

## Revision history

- **2026-10-10**: first draft (issue #160).
- **2026-11-08**: revised after the first round of ratification keys (EE key
  and market key, both on head `89130fa`). Per finding:
  - EE **A** (stale evidence): merged `main`; rewrote the edge table from
    #208, #212 and the #89 supplement; stated the graded trail; stated that
    the supplement does not by itself complete the −50 mV offset cell.
  - EE **B** (Row 4b rejects): the cause was unknown at that revision.
    The follow-up probe was filed as #405.
  - EE **C** (complete or do not merge): the record does not add the
    `README.md` row, because the gate is not met. It stays unmerged, which is
    its own Option B. The README cell text is drafted above for the ratifying
    revision.
  - Market **A** is the same as EE A. Market **B**: option (i) taken; the
    "standalone comparator" framing is withdrawn and the driver CM accuracy
    is named ("Market framing"). Market **C**: cell text drafted above.
  - Non-blocking: absolute-vs-mid-rail note, Stretch at −50 mV, Q_kick trend,
    metastability sub-rows folded in, `vcm_delta` sentence corrected.
- **2026-11-25**: incorporated the #405 and #415 probes, identified the
  missing strobe-qualified residue measurements (#552), and specified how
  the two complete #89 offset reruns would be graded. Limited the scope to
  sampled common modes and the 50 mV timing bound requested by #160.

## Alternatives considered

- **Option A: merge now as "row defined, not in force".** Rejected as the
  recommendation, though it remains open to the key-holders. A merged
  record whose row is not in force puts a second, inactive common-mode
  sentence next to the ratified table, and a later record would still be
  needed to activate it. It does have one advantage: the gap is owned on
  `main` sooner.
- **Option B: hold unmerged until the gate is met, then revise and ratify.**
  Recommended (see above).
- **Publish an edge on offset alone.** Offset and timing have edge data,
  but each edge lacks a valid residue at one required corner. Neither
  one-sided interval has an interior bound.
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
- The revision uses committed measurements. Issue #552 requests the two
  outstanding edge measurements.

## Spec lines affected

None in this PR. In the ratifying revision (Option B): one new row in the
`README.md` target-spec table, plus the sentence in the Offset sigma row
"**No whole-latch common-mode range is ratified**", which would then point to
this record.

## How this record gets ratified

The non-author EE reviewer checks the corner populations, offset procedure,
decision validity and scope of the sampled settings. The independent market
reviewer must find that the proposed operating points and bounds are
competitive for a clocked decision element with a driver-set common mode.
If that finding is unavailable, the operator decides how to proceed.

After the evidence gate is met, revise the README and this record together.
The independent non-author reviewers must issue fresh `RATIFY-KEY: ee` and
`RATIFY-KEY: market` approvals on that revision. The operator decides whether
to ratify, and the merge commit records that decision. [DR-0002](0002-target-spec-ratification.md#how-this-record-gets-ratified).
