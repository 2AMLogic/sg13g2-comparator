# 0004: Input common-mode range row (candidate, evidence-gated)

- **Status**: proposed. **This record is a draft. Its recommendation is that
  the row it defines is not yet ratifiable.** It proposes a new
  input-common-mode-range row for the `README.md` target-spec table, lists
  per row what the committed evidence does and does not support at the band
  edges, and names the minimum extra campaigns needed before the row can be
  ratified. It moves no existing bound, edits no Target or Stretch cell, and
  changes no `README.md` text. Ratification, when the evidence exists, is the
  two-key merge of the PR that lands this record, exactly as DR-0002 "How
  this record gets ratified" describes (a `RATIFY-KEY: ee` and a
  `RATIFY-KEY: market` verdict from non-author reviewers; the merge commit is
  the ratification record). **The drafting agent holds neither key and this
  PR must not be hand-merged.**
- **Date**: 2026-10-10
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
  campaigns this record asks for).
- **Supersedes**: none. DR-0002 and DR-0003 are not edited.
- **Superseded by**: none

## Context

The ratified table says the offset verdict holds "at nominal common mode"
and that "**No whole-latch common-mode range is ratified**" (`README.md`,
Offset sigma row). A standalone comparator with no stated input common-mode
range has no usable interface contract: an integrator cannot tell over which
`vcm` window the Target rows hold.

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

**Interpolation assumption, stated for the EE key.** Three measured points
do not prove that the window's interior behaves. The row would claim a
closed interval on the basis that each metric moves smoothly between the
measured points. The only data on that today is offset: the #79 paired
3σ ratio to nominal is 0.977 (0.919 … 1.028) at `vcm-m050` and
1.036 (0.969 … 1.148) at `vcm-p050`, with paired correlation ≥ 0.952
([`comparison.md`](../../sim/comparator-offset-cm-band/campaigns/20261009-5185f52/comparison.md),
"Paired sensitivity vs nominal"). That is a few-percent monotonic effect, so
the assumption is reasonable for offset. The EE key decides whether it is
also reasonable for decision time and residue once #164 and #165 report.

## Evidence by row at the band edges

"Supported" means a committed, valid 45-point population exists at that
condition and every valid point is inside the ratified bound. Today the
nominal column is supported for all three rows by records DR-0002 and
DR-0003 already cite. No edge is supported for every row.

| Row (bound) | `vcm-m050` (0.55 V) | nominal (0.60 V) | `vcm-p050` (0.65 V) |
|---|---|---|---|
| **1. Offset ≤ 15 mV 3σ** | **Partial, not supported**: 43/45 valid, 6.892 … 11.427 mV, all 43 inside 15 mV. `tt_-40c_1.32v` and `sf_-40c_1.20v` are REJECTED (one ngspice "timestep too small" abort each) and report no sigma. Completion: #89. Source: [`comparison.md`](../../sim/comparator-offset-cm-band/campaigns/20261009-5185f52/comparison.md) | **Supported**: harness compliance record [`20260917-060858-ea40b57`](../../sim/comparator-offset-transient-mc/records/20260917-060858-ea40b57.md), 7.456 … 10.537 mV, 45/45. klt trail `vcm-nom` 6.913 … 12.093 mV, 45/45, bit-identical to [`20261009-d73a9ac`](../../sim/klt-corner-verification/campaigns/20261009-d73a9ac/grading.md) | **Supported**: 45/45 valid, 6.913 … 12.872 mV, all inside 15 mV. Source: same `comparison.md` |
| **3a. Decision time ≤ 1.5 ns at 50 mV** | **Unsupported**: no record at this common mode | **Supported**: harness [`20260916-113309-180cca7`](../../sim/comparator-regeneration/records/20260916-113309-180cca7.md), 0.596 … 0.850 ns; klt `20261009-d73a9ac` grading row 3a, 0.5965 … 0.8502 ns, 45/45 | **Unsupported**: no record at this common mode |
| **4b. Residue ≤ 100 µV** | **Unsupported**: no record at this common mode | **Supported**: harness [`20260916-022249-36773c7`](../../sim/comparator-kickback/records/20260916-022249-36773c7.md), 1.70 … 15.40 µV; klt `20261009-d73a9ac` grading row 4b, 2.034 … 15.63 µV, 45/45 | **Unsupported**: no record at this common mode |
| *(2. Noise, not in the row)* | no record | NOT MET (Row 2) | no record |
| *(4a. Q_kick, not in the row)* | no record | NOT MET, 39/45 (DR-0003) | no record |

Summary: **one of the six edge cells is supported** (offset at +50 mV), one
is partial (offset at −50 mV, 43/45), and four have no data at all.

A note on the offset trail. The Row 1 compliance basis at nominal is the
harness record. The edge data is the klt trail (#62 bench via #79), whose
absolute level differs from the harness by the known gap tracked in #82. For
the range row, all three offset conditions should be graded on the **same**
trail. The klt trail is the only one that has all three. Its nominal is inside
15 mV at 45/45, so using it changes no verdict, but the ratifying PR should
say which trail it grades.

The front-end bench `sim/comparator-offset-mc/` also carries a ±50 mV
common-mode axis (`common-mode-dependent offset`, see its README). It covers
the reduced, loop-broken sub-model only, which DR-0002 Row 1 treats as a
lower bound and not the row's subject. It does not count as whole-latch edge
evidence here.

## How the evidence state was established

- `sim/dut.json` binds `dut_vcm = 0.6` and nothing else.
- Every committed SPICE body in `sim/` that sets `dut_vcm` sets it to 0.6
  (`.param dut_vcm=0.6`, 69 occurrences, no other value). The only bodies
  that move the common mode are the #79 ones, via `.param vcm_delta`
  (generated by `sim/kltsim/cmband.py`; bodies under
  `sim/comparator-offset-cm-band/campaigns/20261009-5185f52/`). Apart from
  `cmband.py` and its test, no other `sim/` file mentions `vcm_delta`.
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

## Minimum extra campaigns

All of them are `klt sim` requests on the batch fleet
(`KLT_SIM_BACKEND=batch`), not hand-launched ngspice grids. Each one reuses an
existing bench unchanged except for the #79 `vcm_delta` line, so the edge
numbers are directly comparable to the nominal ones.

| # | Closes | Request shape | Size |
|---|---|---|---|
| [#89](https://github.com/2AMLogic/sg13g2-comparator/issues/89) (exists) | Row 1 at `vcm-m050`, 43/45 to 45/45 | #79 `offset_cm` Monte-Carlo request at the two rejected points, one tighter max step applied uniformly to all three conditions at those points, same seed (20260916), N = 60, kept as a separately labelled supplementary campaign | 2 points × 3 conditions × 60 draws |
| [#164](https://github.com/2AMLogic/sg13g2-comparator/issues/164) | Row 3a at both edges (and reports τ and 0.1 mV) | #62 `regeneration` corner request (`mos_{tt,ff,ss,fs,sf}` × `vsup`=`vsupa` ∈ {1.08, 1.2, 1.32} × {−40, 27, 125} °C, `tran 5p 60n`, same measurements and limits) at `vcm_delta` ∈ {−0.05, 0.0, +0.05}. The 0.0 condition is a bit-identity reproduction gate against `20261009-d73a9ac`. No Monte Carlo | 3 × 45 corner runs |
| [#165](https://github.com/2AMLogic/sg13g2-comparator/issues/165) | Row 4b at both edges (and reports Q_kick) | #62 `kickback` corner request, same 45-point grid, analysis and measurements as `20261009-d73a9ac/kickback.request.json`, at the same three `vcm_delta` values, with the same reproduction gate. No Monte Carlo | 3 × 45 corner runs |

No noise campaign is listed, because Row 2 is not part of the candidate row
(see above). If the key-holders want noise characterized over the band anyway,
that is an addition to this minimum set, not a prerequisite for it.

**Dependency on #92.** All the data above, both existing and requested, is on
the DR-0001 geometry. If the #92 sizing study changes the input pair or the
tail, the edge data must be re-taken on the final geometry before the row is
ratified. A wider pair could move the usable window in either direction.
This record proposes no window for a geometry that has not been measured.

## Decision (proposed)

1. **Define** the candidate row above: `dut_vcm` ± 50 mV (0.55 … 0.65 V),
   holding Row 1, Row 3a and Row 4b at their ratified bounds at every PVT
   point.
2. **Do not ratify it on the current evidence.** One of six edge cells is
   supported. Ratifying on partial evidence would make a row that silently
   holds for one metric, which issue #160 explicitly rejects.
3. **Gate**: the row becomes ratifiable when #89, #164 and #165 have landed
   append-only evidence and every edge cell in the table above reads
   Supported, on the geometry current at that time (see #92).
4. **If an edge fails**, the window narrows; it never widens:
   - one edge fails any of the three rows: propose the one-sided window
     (0.60 … 0.65 V or 0.55 … 0.60 V) that the evidence supports;
   - both edges fail: leave the row unratified. The status quo stays
     (nominal-only, `README.md` unchanged), and the gap stays explicit;
   - a window wider than ± 50 mV is out of scope for this record. It would
     need its own campaigns and its own record.

**Recommended path for the key-holders (Option B below).** Keep this PR open
and unmerged until the gate is met. Then revise the evidence table in this
same record with the new campaign paths and the window the evidence actually
supports, and add the row to `README.md` in that revision. The two keys are
applied to that revised PR. This is the pattern DR-0002 used, which folded in
new evidence before merge (its 2026-09-21 revision).

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
- It runs no simulation. The campaigns are requested via #164 and #165, and
  #89 already exists.

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
competitive as an interface contract for a standalone comparator on this node.
If it cannot so find, DR-0002's rule is to escalate to `loom:operator`, not to
widen the window. Status stays `proposed` in the merged tree for the same
reason DR-0002's does: status is conferred by the merge commit.
