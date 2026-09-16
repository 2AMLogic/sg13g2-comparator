# 0002: Target-specification ratification — all five rows, against the DR-0001 schematic's measured evidence

- **Status**: proposed. **The ratification act is the two-key merge of the PR
  that lands this record**, per
  [2AMLogic/2am#372](https://github.com/2AMLogic/2am/issues/372)
  ("the merge commit is the ratification record") and the standing
  ratification-via-PR policy it succeeds,
  [2AMLogic/2am#357](https://github.com/2AMLogic/2am/issues/357). Nothing in
  this record binds `README.md`'s table until that merge happens with both
  `RATIFY-KEY: ee` and `RATIFY-KEY: market` verdicts present from non-author
  reviewers. The drafting agent holds neither key (see "How this record gets
  ratified" below).
- **Date**: 2026-09-16
- **Decided by**: Builder agent, issue
  [#12](https://github.com/2AMLogic/sg13g2-comparator/issues/12) — drafting
  only; the proposal below is a recommendation to the key-holders, not a
  self-ratification.
- **Related**:
  [#3](https://github.com/2AMLogic/sg13g2-comparator/issues/3) (gap-to-T1
  tracker; this record is the third and last step of the topology →
  schematic → ratification chain named there, and clears item 5's structural
  blocker without closing item 5 itself),
  [`0001-comparator-topology.md`](0001-comparator-topology.md) ("DR-0001",
  the topology every number below was measured on),
  [`../README.md`](../README.md) (the DR process this record follows),
  [`../porting-plan.md`](../porting-plan.md) (next step 5, "revisit the
  README target-spec table's DRAFT bounds… if/when the table is set"),
  [`../../sim/README.md`](../../sim/README.md) (the four experiments, one per
  first-class row), [`../../design/README.md`](../../design/README.md) (the
  `comparator_dut_analog` reduced-sub-model caveat, load-bearing for two
  rows below)
- **Supersedes**: none. This is the first record that ratifies anything in
  `README.md`'s target-specification table; DR-0001 explicitly ratified no
  row ("No `README.md` row is ratified, changed, or scoped by this record").
- **Superseded by**: none

## Context

`README.md`'s target-specification table has been **DRAFT / unratified**
since the repo was opened. Its bounds were original engineering judgment for
SG13G2's 1.2 V LV core — no sibling had a ratified standalone-comparator spec
to port, and at drafting time no design and no measurement existed at all.
`spec/README.md` requires a decision record whenever that table is **set**,
**changed**, or **scoped**; this record does all three at once, for the first
time:

- **Set** — every row's bound becomes binding rather than indicative.
- **Changed** — the Kickback row's stated quantity and bound are revised (one
  row, with the reasoning fully in the open below; this is the only row whose
  numbers move).
- **Scoped** — two previously open scope questions are closed: the power
  row's "at a stated clock rate (TBD)" is fixed at 33.3 MHz, and the
  metastability row gains an explicit τ bound so it is falsifiable rather
  than descriptive.

What makes ratification possible now is that measurements exist against a
real design. Issue [#11](https://github.com/2AMLogic/sg13g2-comparator/issues/11)
(PR [#17](https://github.com/2AMLogic/sg13g2-comparator/pull/17), merged
`6b6ce16`) implemented DR-0001's single-tail StrongARM in `design/`, repointed
`sim/dut.json` at it (`provenance: "schematic"`, was `"placeholder"`), and
re-ran all four experiments over the full 45-point PVT grid. **Every number
in this record comes from those `provenance: schematic` records. No row is
ratified from a placeholder-DUT record.**

## The evidence this record rests on

| row | experiment | record (all `provenance: schematic`, commit `36773c7`) | grid | record verdict |
|---|---|---|---|---|
| Offset σ | [`sim/comparator-offset-mc/`](../../sim/comparator-offset-mc/) | [`20260916-021822-36773c7`](../../sim/comparator-offset-mc/records/20260916-021822-36773c7.md) | 45 pts (5 `mos_*_mismatch` × 3 T × 3 V), **200 MC draws per point**, ngspice `rndseed=20260910` common across points | PASS |
| Input-referred noise | [`sim/comparator-preamp-noise/`](../../sim/comparator-preamp-noise/) | [`20260916-021939-36773c7`](../../sim/comparator-preamp-noise/records/20260916-021939-36773c7.md) | 45 pts (5 × 3 × 3), `.noise` | **FAIL** — check-floor only, see below |
| Decision time / metastability | [`sim/comparator-regeneration/`](../../sim/comparator-regeneration/) | [`20260916-021945-36773c7`](../../sim/comparator-regeneration/records/20260916-021945-36773c7.md) | 45 pts (5 × 3 × 3), transient, 3-rung overdrive ladder (50 mV / 1 mV / 0.1 mV) | **FAIL** — check-floor only, see below |
| Kickback | [`sim/comparator-kickback/`](../../sim/comparator-kickback/) | [`20260916-022249-36773c7`](../../sim/comparator-kickback/records/20260916-022249-36773c7.md) | 45 pts (5 × 3 × 3), transient, 1 kΩ/100 fF drive plus 1 GΩ/1 pF non-restoring drive | PASS |

All four: PDK `ihp-sg13g2` release `0.3.0`, ngspice-46, Python 3.14.7;
process {tt, ff, ss, fs, sf} × temperature {−40, 27, 125 °C} × supply {1.08,
1.20, 1.32 V}, 45/45 points completed in every case.

**Two of the four records carry `Verdict: FAIL`, and this record ratifies
rows from them anyway — deliberately, with the reason stated.** Both failures
are *corner-sensitivity floor* checks (`min_spread_pct_by_axis`), not
measurement-validity checks and not spec checks:

- `comparator-preamp-noise`: `av_dc`'s process-axis floor (≥ 3 %) against a
  weakest observed slice of 1.07 %.
- `comparator-regeneration`: `td_od50_ns`'s temperature-axis floor (≥ 8 %)
  against a weakest observed slice of 2.73 %.

Those floors exist to catch a corner runner that is silently not sweeping an
axis. They were calibrated against the **placeholder** DUT's own first
45-point record and do not hold against the real design — a diode-connected-
load gain stage's `gm`-ratio gain genuinely cancels process skew to first
order, and the real latch's supply-normalized delay threshold genuinely
removes much of the temperature dependence. `sim/selftest.sh`'s
`--sabotage-corners` negative control still fails as designed on both
benches, which is the actual proof that corner switching works.
`design/README.md` already records this finding and, per `sim/README.md`'s
"Do not relax a check to make a result pass", deliberately left both FAIL
records committed as-is rather than recalibrating the floors. This record
takes the same position: **the floors are not touched here either**, and
recalibrating them is named as an open item, not performed.

## Decision

Five rows. Four keep their DRAFT bounds unchanged; one (Kickback) is revised,
with the alternatives laid out for the key-holders rather than decided
unilaterally. **Three of the five rows are NOT met by the current design, and
this record ratifies the bounds anyway** — that is the point of the exercise.
A fourth (Kickback) is ratified with its charge clause **undetermined**: the
bench emits no charge measurement, so that sub-bound is "consistent, not
certified" rather than met (Row 4 (b)–(c)); its residue clause is met.

### Row 1 — Offset σ: **ratified unchanged**, and NOT met

| | |
|---|---|
| **Ratified Target** | ≤ 15 mV, 3σ, input-referred, calibration-free (unchanged from DRAFT) |
| **Ratified Stretch** | ≤ 8 mV, 3σ (unchanged from DRAFT) |
| **Ratified statistical basis** | Monte Carlo over SG13G2's shipped per-instance local-mismatch models (`mos_{tt,ff,ss,fs,sf}_mismatch`), **N = 200 draws per PVT point**, seed `20260910` common across points, σ precision 1/√(2N) = ±5 %. Reported as 1σ and 3σ at **every** point of the 45-point grid; the row is met only if the **worst** point meets it. |
| **Measured** | σ 3.708 mV (`ss_mismatch_-40c_1.08v`) … 5.676 mV (`ff_mismatch_125c_1.32v`); **3σ 11.12 … 17.03 mV**. 10 of 45 points exceed 15 mV, all of them hot (125 °C) or hot-ish/fast. |
| **Status** | **NOT MET** — and the true margin is worse than shown, because this number is a **lower bound**. |

**Why it is a lower bound.** Per DR-0001 Decision §3 the topology has no
DC-resolvable analog front end; `comparator_dut_analog` is DR-0001's named
interim path — a diode-connected, loop-broken reduced sub-model. It captures
input-pair and tail-mirror mismatch and **excludes the regenerative loop's own
offset contribution entirely, by construction**. The real offset is ≥ the
measured 17.03 mV worst corner.

**Why the bound does not move.** There is a known, unexercised design lever:
σ_Vos ∝ 1/√(W·L) (Pelgrom), and DR-0001's sizing is explicitly *not* a sizing
study — `design/README.md` states "Device widths/lengths here are the round
numbers DR-0001's own 'Sizing rationale' section named as a block-diagram-level
starting point… not the output of a gm/Id or noise-budget sizing study."
Closing the front-end gap alone needs ≥ 1.3× input-pair area (17.03/15 = 1.135
in σ ⇒ 1.29 in area); covering the excluded decision-stage term needs more.
That is ordinary design work on a 130 nm node, not a physical wall. Moving the
bound to 17.03 mV would be precisely the "relax the ratified spec to make
results pass" that `CLAUDE.md` forbids, so the bound stays and **the design
carries the failure** until a sizing pass or a topology escalation (DR-0001's
named double-tail path) closes it.

### Row 2 — Input-referred noise: **ratified unchanged**, evidence path scoped

| | |
|---|---|
| **Ratified Target** | ≤ 1.0 mV rms, differential, input-referred, total integrated (unchanged from DRAFT) |
| **Ratified Stretch** | ≤ 0.6 mV rms (unchanged from DRAFT) |
| **Ratified evidence path (scoping, new)** | The **compliance** number must come from **transient-noise runs with seeds and run counts committed**, per `CLAUDE.md`'s metastability row ("the input-referred noise floor from transient-noise runs with seeds and run counts committed"). The `.noise`-on-a-reduced-sub-model number is ratified as a **reportable lower bound**, not as the compliance path. |
| **Measured (lower bound)** | 216.7 µV rms (`ff_-40c_1.20v`) … **388.9 µV rms** (`fs_125c_1.08v`), all 45 points; total integrated output noise ÷ measured DC gain (not `inoise_total` — see the record's own note on the 200× error that convention has caused upstream). |
| **Status** | **CONSISTENT, NOT CERTIFIED.** The lower bound sits 2.6× under Target and 1.5× under Stretch, so nothing here argues the bound is wrong; but it excludes the regeneration-phase noise that dominates a StrongARM's real floor, so it cannot certify the row either. |

**Why the bound does not move.** A bound with 2.6× headroom against a lower
bound is not evidence to move in either direction — tightening it on
lower-bound data would be as unfounded as relaxing it. The honest act is to
ratify the number and ratify the *evidence standard* that can settle it, which
is what the scoping line above does.

### Row 3 — Decision time vs. overdrive, and metastability: **ratified, with τ added as a bounded sub-row**

Metastability is a first-class row here, not an appendix (`CLAUDE.md`,
`sim/README.md`). DRAFT bounded only the 50 mV decision time and left the
regeneration time constant τ — the actual metastability parameter —
undescribed. This record bounds it.

| | |
|---|---|
| **Ratified Target** | ≤ 1.5 ns at 50 mV overdrive, 1.2 V core, at **every** point of the PVT grid (unchanged from DRAFT) |
| **Ratified Stretch** | ≤ 0.8 ns at 50 mV overdrive (unchanged from DRAFT) |
| **Ratified sub-row (new): regeneration time constant** | **τ ≤ 250 ps**, worst PVT point, extracted from the (1 mV, 0.1 mV) delay pair as τ = Δt/ln 10 |
| **Ratified sub-row (new): small-overdrive decision time** | **≤ 2.0 ns at 0.1 mV overdrive**, worst PVT point |
| **Measured, 50 mV** | 0.596 ns (`ff_-40c_1.08v`) … **0.850 ns** (`ss_125c_1.32v`), 45/45 points |
| **Measured, τ** | 42.6 ps (`ff_-40c_1.32v`) … **167.3 ps** (`ss_-40c_1.08v`); resolution depth ≥ 7.63 decades at every point |
| **Measured, 0.1 mV** | 0.910 ns (`ff_-40c_1.32v`) … **1.662 ns** (`ss_-40c_1.08v`) |
| **Status** | **Target MET at all 45 points** (1.8× margin at the worst point). **Stretch NOT MET at 9 of 45** — every `ss` point, max 0.850 ns. Both new sub-rows MET. |

**Where the two new numbers come from, and why they are not rubber stamps.**
They are set from measurement because DRAFT bounded nothing here at all — this
is founding a bound, not weakening an existing one. Each is also independently
anchored to the operating point rather than only to the data:

- **τ ≤ 250 ps**: at the ratified 33.3 MHz clock (Row 5) the strobe is high
  for 10 ns, so τ ≤ 250 ps guarantees ≥ 40 τ ≈ 17 decades of regeneration per
  decision — the condition under which the metastability window is negligible
  against any realistic input distribution. It is 1.5× the measured worst
  point, so an `ss`-corner design change that degraded τ by half would break
  the row rather than quietly pass it.
- **≤ 2.0 ns at 0.1 mV**: a 500× smaller overdrive than the headline row —
  2.7 decades, ~6.2 τ of extra regeneration — is the deepest rung the bench
  probes, and 2.0 ns keeps even that rung inside the 10 ns strobe phase with
  5× margin, so a near-metastable input still resolves within one decision
  cycle rather than smearing into the next. It is 1.2× the measured worst
  point, deliberately tighter in relative terms than the τ bound because this
  number is bounded by the clock, not by the device.

**Why the 0.8 ns Stretch does not move to cover the `ss` corner.** It is a
*stretch* — missing it at the slow corner is exactly what a stretch column is
for. Widening it to 0.86 ns to capture the measured worst point would convert
a design ambition into a retroactive description of one schematic's
performance.

### Row 4 — Kickback: **the one revised row** (bound changes; options presented, not decided alone)

This is the row where measured reality and the DRAFT bound diverge hardest,
and the only row whose numbers this record proposes to change. Per
2AMLogic/2am#372's relax-after-measured-FAIL rule, the revision is presented
as a recommendation with its alternatives, and **requires the market key's
explicit competitiveness finding** — it is not treated as settled by the
drafting agent.

**What DRAFT said**: "≤ 5 mV disturbance into a 1 kΩ source impedance at the
input nodes, single decision edge", with its own Basis column already
conceding "Source impedance (1 kΩ) is a stated planning assumption, not yet
tied to any specific driving stage."

**What was measured** (record `20260916-022249-36773c7`, all 45 points):

| quantity | measured | vs. DRAFT |
|---|---|---|
| peak single-ended excursion at 1 kΩ / 100 fF, relative to the node's own driving source | **+87.7 mV** (`ss_-40c_1.08v`) … **+143.3 mV** (`ff_125c_1.32v`); negative excursion −29.3 … −40.6 mV | **18–29× over the 5 mV bound at every single corner** |
| signal-dependent differential residue, non-restoring source (1 GΩ / 1 pF, RC = 1 ms vs. a 30 ns cycle) | 1.70 µV (`ff_125c_1.32v`) … **15.40 µV** (`ss_-40c_1.20v`) | ~325× **under** 5 mV |
| common-mode displacement of the floating input | up to 1.67 mV | — |
| decision correctness under the 1 kΩ drive | correct at 45/45 points (`dout_1k_end` ≥ 0.99998) | — |

**The diagnosis: DRAFT bounded the wrong quantity.** A peak excursion at an
assumed node capacitance is not a property of the comparator — it is
Q_kick/C_in, a property of the *driver*. The comparator's own property is the
charge Q_kick it injects per decision edge. From the measurement,
Q_kick ≈ V_peak · C_in = 143.3 mV × 100 fF ≈ **14.3 fC/side** at the worst
corner — but that equality holds only in a fast-pulse limit this bench does
**not** satisfy, and the error is one-sided toward *under*-reporting. The
estimator, its bias, and what can and cannot be certified from it are worked
through in "The charge quantity, precisely" below; the diagnosis of DRAFT's
defect does not depend on the estimator's accuracy, only on the ~29×
order-of-magnitude gap. Restated in those terms, DRAFT's "≤ 5 mV at 1 kΩ" is exactly the
requirement **C_in ≳ 2.9 pF at the driving network** — a constraint on a
driving stage that does not exist and is not named anywhere in this repo.

It is also not reachable by redesigning the comparator: 5 mV at C_in = 100 fF
means Q_kick ≤ 0.5 fC/side, ~29× below measured. The kick is the rail-to-rail
swing of the regeneration nodes coupled through the input pair's own intrinsic
C_gd (SG13G2 PSP103 models — a real device capacitance, not a stand-in). DR-0001's
named escalation path (double-tail) reduces the *swing* the input pair sees
from a full rail to a few hundred mV, i.e. a ~3–5× improvement, not 29×; only
an isolating buffer or preamp between source and input pair — whose static
current DR-0001 rejected on headroom grounds, and which would itself add
offset and noise — gets close. **No dynamic latch meets 5 mV at 100 fF.**

**Options put to the key-holders:**

- **Option A — hold DRAFT's ≤ 5 mV at 1 kΩ / 100 fF, fail the row, and
  re-open DR-0001.** Honest, but on the analysis above it commits the block to
  a target no member of the dynamic-latch family reaches at this node
  capacitance; the likely outcome is a preamp that DR-0001 rejected for
  reasons this record has no evidence to overturn. Rejected as recommended,
  but it is a real option and the key-holders may take it.
- **Option B (recommended) — restate the row on the comparator's own
  properties**: injected charge per edge, plus settled signal-dependent
  differential residue; publish the peak excursion at the stated 1 kΩ / 100 fF
  drive as a recorded number in the table rather than deleting it; state the
  driver-facing equivalence explicitly so no downstream user is surprised.
- **Option C — keep "5 mV" and change the stated condition to C_in ≥ 3 pF.**
  Arithmetically identical to B, but it "passes" by picking a friendlier test
  condition while keeping a familiar-looking number. Rejected: that is the
  cosmetic shape `CLAUDE.md` is guarding against, even though the underlying
  physics is the same as B's.

**Recommended ratified row (Option B):**

| | |
|---|---|
| **Ratified Target** | **≤ 25 fC/side peak transient injected charge per decision edge** (quantity **Q_kick**, defined precisely below), **and** ≤ 100 µV signal-dependent differential residue at the input nodes at the end of a 30 ns decision cycle, measured against a non-charge-restoring source (1 GΩ / 1 pF) |
| **Ratified Stretch** | ≤ 8 fC/side, **and** ≤ 30 µV residue |
| **Ratified measurement condition for Q_kick** | Branch **A** of [`sim/comparator-kickback/testbench/tb_kickback.spice`](../../sim/comparator-kickback/testbench/tb_kickback.spice) — input node `apa`/`ana`, driven from an ideal source through R_src = 1 kΩ with C_in = 100 fF to ground. Q_kick is the **peak net charge displaced from that node during one decision**, i.e. `max_t |∫₀ᵗ i_kick dt'|` over the integration window 30 … 45 ns (one strobe of the 33.3 MHz, 30 ns-period clock), referenced to the node's own pre-decision level at 29 ns. It is a **peak-transient** quantity — what the driver must source/sink *during* the event — **not** the net charge retained after recovery on the floating branch, which is a different quantity ~8× smaller (see (a) below). |
| **Ratified measurement condition for the residue** | Branches **B** and **C** (1 GΩ / 1 pF, RC = 1 ms ≫ the 30 ns cycle), key `kick_sigdep_nv`: the difference between the settled differential input displacement at a 1 mV and a 100 mV input, 29 ns → 55 ns. This clause, unlike Q_kick, is emitted directly by the bench. |
| **Measured** | Q_kick **estimated** at 8.8 … **14.3 fC/side** via `kick_1k_peak_mv × C_in`, an estimator with a **1.3 … 2.9× under-reporting bias** (derived below) ⇒ a true-value bracket of roughly **11 … 41 fC/side**; residue 1.70 … **15.40 µV**; peak **+87.7 … +143.3 mV** (−29.3 … −40.6 mV negative) |
| **Status (charge sub-bound)** | **CONSISTENT, NOT CERTIFIED.** The bench emits no Q_kick measurement; the only available estimator is biased toward passing by a factor of ~1.3 … 2.9× (derived in (b) below), a range that straddles the bound. 25 fC survives if the effective kick duration is ≲ R_src·C_in = 100 ps and fails if it is ≳ 200 ps, and the committed records cannot distinguish the two. Same vocabulary as Rows 1 and 2, and for the same reason. |
| **Status (residue sub-bound)** | **MET**, 6.5× margin (15.40 µV vs. 100 µV), directly from a committed bench key at 45/45 points. |
| **Status (Stretch)** | **NOT MET** on charge under any reading of the estimator (8.8 fC estimated vs. 8 fC, before any bias correction). |

#### The charge quantity, precisely — and why its status is *not* "MET"

The row above is the only one in this record whose status **improves** as a
result of the restatement, so it gets the same scrutiny Rows 1 and 2 get, and
lands in the same place.

**(a) Two different quantities both answer to "injected charge per edge", and
they differ by ~8×.** This bench has two charge-relevant drives, and they
measure physically different things:

| reading | branch | what it is | measured |
|---|---|---|---|
| **peak transient** | A (1 kΩ / 100 fF) | charge displaced from the node *during* the event, before any of it flows back — what a real driver must supply and settle out | est. 8.8 … 14.3 fC/side (see (b) for the estimator) |
| **net settled** | B (1 GΩ / 1 pF, RC = 1 ms) | charge still on the node after the decision has finished and the tail has settled, from `kick_cm_nv × C_float` | 0.008 fC (`ff_125c_1.32v`) … **1.673 fC/side** (`ss_-40c_1.32v`) |

The 8× gap is physical, not a discrepancy: most of the displaced charge
returns to the node once the regeneration nodes and the tail settle. **The
ratified Target is the peak-transient reading (branch A)**, because that is
the quantity that sets a driver's settling requirement and it is the larger
(conservative) of the two. The net-settled reading is recorded here so no
future reader can score the row against the friendlier number by accident; it
is *not* a second ratified bound.

**(b) The estimator, and its bias — quantified, not qualified.** No `tb.json`
key emits Q_kick. The only available estimate is
`Q_est = kick_1k_peak_mv × C_in`. Branch A's node obeys

```
C_in · dv_d/dt + v_d / R_src = i_kick(t),     R_src·C_in = 1 kΩ × 100 fF = 100 ps
```

where `v_d = v(apa) − v(asp)` is exactly what `kick_1k_peak_mv` records.
`Q_est = C_in·max|v_d|` equals the true injected charge **only** when the kick
is fast compared with R_src·C_in; otherwise the 1 kΩ drains part of the charge
*during* the event and the peak — hence Q_est — comes out low. For a
first-order rectangular current pulse of total charge Q_kick and effective
duration T, with θ = T/(R_src·C_in):

```
Q_est / Q_kick = (1 − e^(−θ)) / θ        ⇒   Q_kick / Q_est = θ / (1 − e^(−θ))
```

| T | θ | Q_kick / Q_est | Q_kick from the 8.8 … 14.3 fC estimate |
|---|---|---|---|
| → 0 (the fast-pulse limit the bare estimator assumes) | → 0 | 1.00× | 8.8 … 14.3 fC |
| 50 ps | 0.5 | 1.27× | 11.2 … 18.2 fC |
| 100 ps | 1.0 | 1.58× | 13.9 … 22.6 fC |
| 200 ps | 2.0 | 2.31× | 20.4 … 33.1 fC |
| 267 ps | 2.7 | 2.87× | 25.2 … 41.0 fC |

**T is not small here.** The kick is driven by the regeneration nodes' swing,
whose timescale is the 100 ps clock edge (`vclk … 100p 100p`, line 55 of
`tb_kickback.spice`) plus the measured regeneration time constant τ = 42.6 …
167.3 ps (record `20260916-021945-36773c7`). T is therefore of order 100–270 ps,
i.e. θ ≈ 1 … 2.7 — the *same order* as R_src·C_in, not fast against it. The
25 fC bound survives the correction for θ ≲ 1.25 (T ≲ 125 ps) and is
**exceeded at the worst corner** for θ ≳ 1.3. **Nothing in the committed
records distinguishes those cases**, so the honest statement is that the row
is consistent with 25 fC and not certified at it — not "MET with 1.7× margin".

Two further reasons to state the bound rather than the estimate as the claim:
the model above is linear and lumped, whereas the real kick couples through a
bias-dependent C_gd while the node's own voltage moves; and `v_d` is
bidirectional (+87.7 … +143.3 mV then −29.3 … −40.6 mV), so "peak charge" and
"net charge per edge" are not the same integral — which is exactly why the
measurement condition above names the window and the sign convention.

**(c) What would certify it.** A direct `meas`-level integration of the branch-A
source current over 30 … 45 ns — one `.meas tran` integral plus one `measure:`
key — would emit Q_kick outright and remove both the estimator and the
ambiguity in (a). That is a testbench change, and `sim/` is append-only
evidence, so it is filed as an open item below rather than performed inside a
spec-ratification PR. Until it lands, the charge sub-bound is ratified as a
bound with **no automated check behind it**; the residue sub-bound, which does
have one, carries the row's only certified pass.

**Why 25 fC and 100 µV, and why this is founding rather than relaxing.**
Neither quantity had *any* prior bound — DRAFT bounded volts-at-an-assumed-cap
and nothing else — so there is no previously ratified number being weakened.
25 fC is 1.7× the worst-corner *estimate* — tight enough that a design change
that doubled input-device C_gd would break the row, loose enough to survive
ordinary sizing movement. Note that that 1.7× is headroom against the
estimator, **not** demonstrated margin against the true quantity: per (b)
above the correction factor plausibly consumes all of it. The bound is chosen
on the design-pressure argument, and is deliberately *not* re-floated upward
to guarantee a pass — which is what choosing a number the block may not meet,
and labelling the row accordingly, means here. 100 µV is 6.5× the measured worst residue and,
more importantly, ~1/50 of the ratified offset Target's 1σ equivalent
(15 mV/3 = 5 mV) and 2–4× below the measured input-referred noise lower bound
(217–389 µV rms) — i.e. it is the level at which kickback stays a negligible
term in the error budget rather than a contributor to it. The 8 fC stretch is a real design
ask (it needs ~1.8× less input-pair C_gd) and is deliberately not set at the
measured value.

### Row 5 — Supply / power: **ratified, TBD closed at 33.3 MHz**, power stretch NOT met

| | |
|---|---|
| **Ratified Target (supply)** | 1.2 V ±10 % LV core (`sg13_lv_nmos`/`sg13_lv_pmos`), −40 … 125 °C (unchanged from DRAFT) |
| **Ratified scope** | 3.3 V HV I/O flavor remains **out of scope** (unchanged; a future DR may scope it in) |
| **Ratified scoping (new): the stated clock rate** | **33.3 MHz (30 ns period, 10 ns strobe)** — the rate at which every committed transient record in this repo was taken. DRAFT's "(TBD)" is closed by this line. |
| **Ratified Stretch (power)** | ≤ 20 µW average at 33.3 MHz, **including the tail-bias reference branch** (bound unchanged; the inclusion clause is new, to close the obvious loophole) |
| **Measured** | Static 20.22 µA (`ss_-40c_1.32v`) … 20.83 µA (`ff_125c_1.32v`); switching energy 31.2 fJ (`sf_27c_1.08v`) … 61.3 fJ (`ff_125c_1.32v`) per decision. Total average: **22.9 µW** (`sf_-40c_1.08v`) … **29.5 µW** (`ff_125c_1.32v`) at 33.3 MHz. The supply axis itself is exercised: 45/45 points completed at 1.08/1.20/1.32 V in all four experiments. |
| **Status** | Supply Target **MET / exercised**. Power Stretch **NOT MET** (22.9–29.5 µW vs. ≤ 20 µW). |

**Where the power goes, and why the bound does not move.** Switching energy
contributes only 1.04–2.04 µW at 33.3 MHz; **the static tail-bias reference
branch is ~95 % of the total** (20.3 µA × 1.2 V ≈ 24.4 µW). That current is
`dut_ib = 20 µA`, which `sim/dut.json` documents as "the harness's existing
expectation absent a documented reason to change it — carried over unchanged
from the placeholder binding", i.e. a convention, not a sizing result. The row
is missed by a parameter nobody has yet optimized; relaxing the bound to cover
it would freeze an arbitrary choice into the spec.

**What this record deliberately does NOT ratify**: any Target-column average
power bound. DRAFT left that cell holding the supply scope, with a power
number only in the Stretch column, and no sizing or gm/Id study exists to
found a Target. Inventing one here would be a number with no evidence behind
it — the failure mode this whole DR process exists to prevent. Named as an
open item.

## What this record does not ratify

- **Any layout, extraction, or post-layout claim.** Every number is
  schematic-level. No layout exists.
- **Any Target-column average power bound** (Row 5, above).
- **A compliance certificate for Rows 1 and 2.** Both rest on the
  `comparator_dut_analog` reduced sub-model and are lower bounds; the ratified
  *bounds* bind, but the design's true offset and noise remain unmeasured.
- **A compliance certificate for Row 4's charge sub-bound.** The 25 fC bound
  binds; whether the design meets it is undetermined, because the bench emits
  no Q_kick key and the available estimator's bias bracket straddles the bound
  (Row 4 (b)). The residue sub-bound of the same row *is* certified.
- **The gap-to-T1 tracker's item 5.** This record clears item 5's *structural
  blocker* (there is now a ratified table to simulate against). Item 5 itself
  — a full PVT corner campaign scored against the ratified spec — is separate,
  later work.
- **Recalibration of the two failing corner-sensitivity check floors**
  (`av_dc` process, `td_od50_ns` temperature). Left failing, on purpose.

## Alternatives considered

- **Ratify only the rows that pass, leave the rest DRAFT.** Rejected: a
  partially-DRAFT table leaves item 5 structurally blocked for exactly the
  rows where a scored corner campaign matters most, and it creates the
  incentive to ratify rows *because* they pass — the inversion of the safety
  property in 2AMLogic/2am#372 ("the party that failed a spec must not be able
  to lower the bar").
- **Move each failing bound to just above its measured worst corner.** This is
  the relaxation `CLAUDE.md` forbids by name, and it would have changed four
  rows instead of one. Rejected outright.
- **Defer ratification until transient-MC offset and transient-noise benches
  exist.** Rejected on the same process grounds DR-0001 used for its own
  deferral question: those benches are independently buildable, and leaving
  the table DRAFT keeps every downstream verification item blocked in the
  meantime. Ratifying a bound the design currently misses is the normal state
  of a spec, not an anomaly.
- **Re-open DR-0001's topology choice now, on the kickback and offset
  misses.** Rejected as premature: both misses have unexercised
  sizing/driver-side levers ahead of a topology change, and DR-0001's
  double-tail and preamp escalation paths remain explicitly on the table for
  whoever finds those levers insufficient.

## Spec lines affected

Every row of `README.md`'s target-specification table, as set out above.
`README.md` is updated in the same change: the DRAFT marker is removed, each
row carries its ratified bound plus a measured-status cell, and the section
points back here. Downstream anchors in `spec/README.md`, `sim/README.md` and
the three experiment READMEs are re-pointed at the renamed section.

## Consequences

1. **Three rows are ratified in a failing state** (offset, power stretch,
   decision-time stretch), and the restated kickback row is certified only on
   its residue clause — its charge clause is ratified as "consistent, not
   certified", the same status Rows 1 and 2 carry. That is now the public,
   recorded state of the block — `README.md` says so in the table itself, not
   in a footnote.
2. **The design acquires a concrete, ordered work list**: input-pair sizing
   for offset (≥ 1.3× area at the front end alone), `dut_ib` reduction for
   power (~95 % of the total), and `ss`-corner speed for the decision-time
   stretch. None of these needs a new decision record; they are ordinary
   design work against a now-binding spec.
3. **Item 5 of the gap-to-T1 tracker is unblocked** and can be scored "vs.
   ratified spec" for the first time.
4. **The kickback row now constrains future driving stages explicitly.**
   Anyone attaching a source network to this comparator gets a Q_kick bracket
   of ~11 … 41 fC/side (estimate 8.8 … 14.3 fC, with the bias of Row 4 (b)
   applied) and the V_peak ≈ Q/C_in conversion, rather than a 5 mV promise that
   would not have survived contact with a real 100 fF input node. Sizing a
   driver off the low end of that bracket is a mistake the record now names.
5. **Two committed FAIL records are now cited by a ratified spec.** That is
   acceptable only because the failures are check-floor calibration artifacts
   with a passing negative control; it also makes recalibrating those floors
   more urgent, since a reader landing on a FAIL record cited by the spec has
   to read three documents to learn it is not a spec failure.

## Open items

- **A Target-column average power bound**, founded on a gm/Id or bias-point
  sizing study (not on the current carried-over `dut_ib`).
- **Transient Monte-Carlo offset and transient-noise benches** — DR-0001
  Consequence 1's required re-founding — so Rows 1 and 2 can be certified
  rather than lower-bounded. `CLAUDE.md` already names transient noise with
  committed seeds and run counts as this repo's methodology for the noise
  floor.
- **A direct Q_kick measurement in the kickback bench.** The ratified charge
  sub-bound of Row 4 currently has **no automated check behind it**: no
  `testbench/tb.json` `measure:` key in
  [`sim/comparator-kickback/`](../../sim/comparator-kickback/) emits a charge
  at all (the one charge-shaped key, `q_resid_small_ac`, is the attocoulomb
  *differential residue* on the floating branches B/C, not Q_kick), so the
  bound is scored today only by the hand-derived, biased
  `kick_1k_peak_mv × C_in` estimator analysed in Row 4 (b). Adding a
  `.meas tran` integral of branch A's source current over the 30 … 45 ns window
  plus one `measure:` key would emit Q_kick directly, let a `checks:` entry
  enforce the 25 fC bound like every other ratified row, and settle whether
  the row is MET or NOT MET. **Until that lands, Row 4's charge clause is a
  ratified bound without a testbench** — a standing exception to `CLAUDE.md`'s
  "no claim without a testbench", recorded here rather than papered over.
- **Recalibration (or deliberate retention) of the two corner-sensitivity
  check floors** that now fail against the real DUT — already tracked as
  [#16](https://github.com/2AMLogic/sg13g2-comparator/issues/16).
- **Stale placeholder-era note blocks in three `testbench/tb.json` files**,
  which are reproduced verbatim into the `provenance: schematic` records and
  now describe the DUT incorrectly (e.g. the kickback record's "PLACEHOLDER
  CAVEAT… explicit 5 fF/side stand-in" when its own Claim text correctly says
  the coupling is through the real input pair's C_gd; the regeneration
  record's "the placeholder DUT's decision stage… draws no supply current at
  all" when this record cites its switching energy for the power row). The
  measurements are unaffected; the prose is misleading.
- **A named driving stage** for the kickback row, which would let the peak
  excursion carry a bound instead of a reporting requirement.
- **The 3.3 V HV I/O flavor** remains out of scope until a future DR scopes it
  in.

## How this record gets ratified

Per 2AMLogic/2am#372, ratification is a **two-key** act and **neither key may
be held by the author**:

1. **EE key** — technical-soundness review by a non-author agent: the proposed
   values against device physics, this repo's own `sim/` evidence, and
   sibling-canary precedent. Posted as a PR review containing a
   `RATIFY-KEY: ee` marker block.
2. **Market key** — per-row market-positioning verdict with a comp table
   against named public parts. **Row 4 (Kickback) is a relax-vs-DRAFT on a
   measured miss and therefore requires this key's explicit finding that the
   restated row remains competitive**; if it cannot so find, the epic's rule
   is to escalate `loom:operator` rather than merge.

The second key-holder applies `loom:auto-merge-ok` with a consolidated
ratification-record comment, and **the merge commit is the ratification
record**. Until then this record's Status stays `proposed` and `README.md`'s
table is ratified only conditionally on that merge. The drafting agent has
applied no key, and this PR must not be hand-merged.

**Expected, not a bug: the merged tree carries `Status: proposed` next to a
README that says "ratified".** Because status is conferred by the two-key
merge commit itself, the *content* of the merge cannot already record its own
outcome — the last pre-merge revision of this file is necessarily the one that
gets merged, and it says `proposed`. DR-0001 merged the same way and is
ratified by the same mechanism. **Status is conferred by the merge, not by
this line**: a reader should take the merge commit (and its
`RATIFY-KEY: ee` / `RATIFY-KEY: market` review bodies) as authoritative, and
read `Status: proposed` as "proposed as of the last commit before
ratification". A later editorial commit may flip the word to `accepted`; that
commit would be a transcription of the merge, not a second ratification act,
and its absence does not unratify anything.
