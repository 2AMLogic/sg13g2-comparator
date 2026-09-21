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
- **Date**: 2026-09-16; **Rows 1–2 and the evidence table revised
  2026-09-21** per
  [#36](https://github.com/2AMLogic/sg13g2-comparator/issues/36) to fold in
  the two whole-latch benches that landed on `main` after this record was
  drafted:
  [`sim/comparator-offset-transient-mc/`](../../sim/comparator-offset-transient-mc/)
  (issue
  [#23](https://github.com/2AMLogic/sg13g2-comparator/issues/23),
  [PR #33](https://github.com/2AMLogic/sg13g2-comparator/pull/33), merged
  2026-09-17) and
  [`sim/comparator-transient-noise/`](../../sim/comparator-transient-noise/)
  (issue
  [#24](https://github.com/2AMLogic/sg13g2-comparator/issues/24),
  [PR #40](https://github.com/2AMLogic/sg13g2-comparator/pull/40), merged
  2026-09-21)
- **Decided by**: Builder agent, issue
  [#12](https://github.com/2AMLogic/sg13g2-comparator/issues/12) — drafting
  only; the proposal below is a recommendation to the key-holders, not a
  self-ratification. The 2026-09-21 revision is drafting in the same sense:
  it records what the two new benches measured and re-derives Rows 1–2's
  verdict language accordingly; it applies no ratification key and moves no
  bound.
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
  [`../../sim/README.md`](../../sim/README.md) (the six experiments backing
  the four first-class rows), [`../../design/README.md`](../../design/README.md) (the
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

**Two things then landed on `main` between this record's drafting
(2026-09-16, records at commit `36773c7`) and its two-key review, and this
revision folds both in rather than deferring the record further.** First,
the **two whole-latch benches DR-0001 Consequence 1 named as the eventual
re-founding of the offset and noise rows**:
[`sim/comparator-offset-transient-mc/`](../../sim/comparator-offset-transient-mc/)
(issue
[#23](https://github.com/2AMLogic/sg13g2-comparator/issues/23),
[PR #33](https://github.com/2AMLogic/sg13g2-comparator/pull/33)) — the
un-reduced topology, strobed decisions — and
[`sim/comparator-transient-noise/`](../../sim/comparator-transient-noise/)
(issue
[#24](https://github.com/2AMLogic/sg13g2-comparator/issues/24),
[PR #40](https://github.com/2AMLogic/sg13g2-comparator/pull/40)) — the
`TRNOISE` compliance measurement `CLAUDE.md` mandates for the noise row.
Second, the two **run-mechanism corrections** that re-founded the
front-end benches' own records: comparator-offset-mc's Monte-Carlo seeding
([#28](https://github.com/2AMLogic/sg13g2-comparator/issues/28) —
`set rndseed=` does not reseed ngspice-46's `agauss()` stream — fixed by
[#32](https://github.com/2AMLogic/sg13g2-comparator/pull/32), re-run
committed as
[`20260916-125444-4d0cf7c`](../../sim/comparator-offset-mc/records/20260916-125444-4d0cf7c.md))
and the two placeholder-derived corner-sensitivity check floors
([#16](https://github.com/2AMLogic/sg13g2-comparator/issues/16), recalibrated
against the real DUT by
[#29](https://github.com/2AMLogic/sg13g2-comparator/pull/29), re-runs
committed as
[`20260916-113303-180cca7`](../../sim/comparator-preamp-noise/records/20260916-113303-180cca7.md)
and
[`20260916-113309-180cca7`](../../sim/comparator-regeneration/records/20260916-113309-180cca7.md)).
Drafted before any of that, Rows 1 and 2 below could cite only front-end-only
reduced-sub-model numbers — one extrapolated from a claimed lower bound to
"the real offset is worse than shown", one leaving the compliance path blank.
The revised rows cite the whole-latch measurements, name what each one still
does not cover, and rest each verdict on the bench that measures the row's
actual subject.

## The evidence this record rests on

All `provenance: schematic`, every one measured on the DR-0001 single-tail
StrongARM over the full 45-point PVT grid:

| row | experiment | record | grid / statistical basis | record verdict |
|---|---|---|---|---|
| Offset σ (front end only, reduced sub-model) | [`sim/comparator-offset-mc/`](../../sim/comparator-offset-mc/) | [`20260916-125444-4d0cf7c`](../../sim/comparator-offset-mc/records/20260916-125444-4d0cf7c.md) | 45 pts (5 `mos_*_mismatch` × 3 T × 3 V), **200 MC draws per point**, `setseed 20260910` common across points — the `set rndseed=` form used at drafting does not reseed ngspice-46's `agauss()` stream (issue #28); this is the #32-corrected re-run, and the drafting-time record [`20260916-021822-36773c7`](../../sim/comparator-offset-mc/records/20260916-021822-36773c7.md) is **not reproducible by its own committed command** for that reason | PASS |
| Offset σ (**whole latch**) | [`sim/comparator-offset-transient-mc/`](../../sim/comparator-offset-transient-mc/) | [`20260917-060858-ea40b57`](../../sim/comparator-offset-transient-mc/records/20260917-060858-ea40b57.md) | 45 pts, **60 MC draws per point**, `setseed 20260916` common across points, one 33-level digital-staircase transient per draw (PR #33) | PASS |
| Input-referred noise (front end only, reduced sub-model — reportable lower bound) | [`sim/comparator-preamp-noise/`](../../sim/comparator-preamp-noise/) | [`20260916-113303-180cca7`](../../sim/comparator-preamp-noise/records/20260916-113303-180cca7.md) | 45 pts (5 × 3 × 3), `.noise`, total integrated ÷ measured DC gain | PASS |
| Input-referred noise (**whole latch** — compliance path) | [`sim/comparator-transient-noise/`](../../sim/comparator-transient-noise/) | [`20260921-154729-41cbc7f`](../../sim/comparator-transient-noise/records/20260921-154729-41cbc7f.md) | 45 pts, `TRNOISE`-injected decision statistics, **N = 80 trials per rung per point** (3 rungs); the run count, not the seed, is the load-bearing reproducibility input (PR #40) | PASS |
| Decision time / metastability | [`sim/comparator-regeneration/`](../../sim/comparator-regeneration/) | [`20260916-021945-36773c7`](../../sim/comparator-regeneration/records/20260916-021945-36773c7.md) | 45 pts (5 × 3 × 3), transient, 3-rung overdrive ladder (50 mV / 1 mV / 0.1 mV) — cited as drafted; the floor-recalibrated re-run of the same measurement, [`20260916-113309-180cca7`](../../sim/comparator-regeneration/records/20260916-113309-180cca7.md) (identical numbers, PASS), exists alongside it | **FAIL** — check-floor only, see below |
| Kickback | [`sim/comparator-kickback/`](../../sim/comparator-kickback/) | [`20260916-022249-36773c7`](../../sim/comparator-kickback/records/20260916-022249-36773c7.md) | 45 pts (5 × 3 × 3), transient, 1 kΩ/100 fF drive plus 1 GΩ/1 pF non-restoring drive | PASS |

All six: PDK `ihp-sg13g2` release `0.3.0`, ngspice-46; process {tt, ff, ss,
fs, sf} × temperature {−40, 27, 125 °C} × supply {1.08, 1.20, 1.32 V},
45/45 points completed in every case. The drafting-era records (commit
`36773c7`) ran under Python 3.14.7 and the re-founded / whole-latch records
under Python 3.12.3; `sim/toolchain.json` floors Python at ≥ 3.9 and both
interpreters exceed it.

At drafting, **two of the then-four cited records carried `Verdict: FAIL`,
and the record ratified rows from them anyway — deliberately, with the
reason stated.** Both failures were *corner-sensitivity floor* checks
(`min_spread_pct_by_axis`), not measurement-validity checks and not spec
checks:

- `comparator-preamp-noise`: `av_dc`'s process-axis floor (≥ 3 %) against a
  weakest observed slice of 1.07 %.
- `comparator-regeneration`: `td_od50_ns`'s temperature-axis floor (≥ 8 %)
  against a weakest observed slice of 2.73 %.

Those floors exist to catch a corner runner that is silently not sweeping an
axis. They were calibrated against the **placeholder** DUT's own first
45-point record and did not hold against the real design — a diode-connected-
load gain stage's `gm`-ratio gain genuinely cancels process skew to first
order, and the real latch's supply-normalized delay threshold genuinely
removes much of the temperature dependence. `sim/selftest.sh`'s
`--sabotage-corners` negative control still fails as designed on both
benches, which is the actual proof that corner switching works.
`design/README.md` already recorded this finding, and the drafting record
accordingly took the position that the floors were not touched there and
recalibrating them was named as an open item, not performed. **That open
item has since been resolved the honest way — recalibrated against the real
DUT by #16 / [PR #29](https://github.com/2AMLogic/sg13g2-comparator/pull/29)
(issue
[#16](https://github.com/2AMLogic/sg13g2-comparator/issues/16)), which
re-ran both benches — so this revision cites the recalibrated, PASS re-run
for the noise row.** The one remaining FAIL-verdict citation is the
regeneration row's drafting-time record, kept (with the re-run named beside
it) because re-pointing Row 3 is outside the scope `loom:issue` #36 gave this
revision; its failure is the floor artifact just described, and its own
Status cell needs no caveat to read correctly against it.

## Decision

Five rows. Four keep their DRAFT bounds unchanged; one (Kickback) is revised,
with the alternatives laid out for the key-holders rather than decided
unilaterally. **The bounds are ratified in the state the current design
actually measures — met, missed, or undetermined — and no bound moves to
flatter it; that is the point of the exercise.** With the two whole-latch
benches folded in by this revision: Row 1's Target is **met at 45/45 points**
with its Stretch missed at 27/45; Row 2's Target is **NOT met on the
ratified compliance path** (grid-wide mean 1.335 mV vs. ≤ 1.0 mV — the
worst finding this revision adds); Row 3's Target is met with its Stretch
missed at the 9 `ss` points; Row 4's residue clause is met, its charge clause
is **undetermined** — the bench emits no charge measurement, so that
sub-bound is "consistent, not certified" rather than met (Row 4 (b)–(c)) —
and its Stretches are missed; Row 5's supply axis is exercised with its power
Stretch missed.

### Row 1 — Offset σ: **ratified unchanged**; Target MET on the whole latch, Stretch NOT met

| | |
|---|---|
| **Ratified Target** | ≤ 15 mV, 3σ, input-referred, calibration-free (unchanged from DRAFT) |
| **Ratified Stretch** | ≤ 8 mV, 3σ (unchanged from DRAFT) |
| **Ratified statistical basis** | Monte Carlo over SG13G2's shipped per-instance local-mismatch models (`mos_{tt,ff,ss,fs,sf}_mismatch`), seed common across points in both benches so grid movement is a real PVT effect, not sampling noise: the front-end bench runs **N = 200 draws per point, `setseed 20260910`, σ precision ±5 %**; the whole-latch bench runs **N = 60 draws per point, `setseed 20260916`, σ precision ±9.1 %** (its per-draw cost is a full 990 ns / 33-level transient rather than one `dc` sweep — see the bench README's "Why N = 60, not N = 200"). Reported as 1σ and 3σ at **every** point of the 45-point grid; the row is met only if the **worst** point meets it. |
| **Measured, front end only** — [`sim/comparator-offset-mc/`](../../sim/comparator-offset-mc/) (loop-broken `comparator_dut_analog` reduced sub-model) | 3σ **11.61 mV** (`ss_mismatch_-40c_1.32v`) … **18.10 mV** (`ff_mismatch_125c_1.32v`), mean 14.14 mV; 10 of 45 points exceed 15 mV, all of them hot or hot-and-fast. Record [`20260916-125444-4d0cf7c`](../../sim/comparator-offset-mc/records/20260916-125444-4d0cf7c.md). |
| **Measured, whole latch** — [`sim/comparator-offset-transient-mc/`](../../sim/comparator-offset-transient-mc/) (un-reduced `comparator_dut`: input pair, tail, cross-coupled regenerative pair, reset devices, isolation inverters, SR latch; real strobe cadence) | 3σ **7.456 mV** (`tt_mismatch_27c_1.32v`) … **10.537 mV** (`tt_mismatch_125c_1.08v`), mean 8.404 mV — **inside the 15 mV Target at 45/45 points**; above the 8 mV Stretch at 27/45. Record [`20260917-060858-ea40b57`](../../sim/comparator-offset-transient-mc/records/20260917-060858-ea40b57.md) (one isolated ngspice convergence warning on one corner's worst draw, disclosed and shown benign in the bench README's Records section; all four of the record's checks pass). |
| **Status** | **Target MET at 45/45 points on the whole-latch measurement; Stretch NOT MET at 27/45 points.** |

**Why the verdict rests on the whole-latch number.** The row's subject is the
input-referred offset of the comparator *as built*, and the whole-latch bench
measures exactly that: every device that participates in a real decision
carries its own `agauss()` mismatch draw and is exercised through the real
strobe, so nothing in the topology is excluded by construction and nothing
has to be extrapolated from the result. The front-end bench cannot make that
claim: per DR-0001 Decision §3 the topology has no DC-resolvable analog front
end, `comparator_dut_analog` is the named interim path, and the drafting-time
version of this row — readable in the PR's history — carried its "lower
bound" qualifier *precisely because* that sub-model excludes the
regenerative loop's own contribution.

**And the two benches disagree, in the direction the "lower bound" qualifier
did not predict.** The whole-latch 3σ is *lower* than the front-end-only 3σ
at **every one of the 45 matched PVT points** — a consistent ~35–45 %
reduction (means: 8.404 mV vs. 14.14 mV), not just on average. That finding
was published by the bench itself on landing
([`sim/comparator-offset-transient-mc/README.md` → "An observation, not
(yet) a DR-contradiction"](../../sim/comparator-offset-transient-mc/README.md#an-observation-not-yet-a-dr-contradiction)),
and this record takes that reading rather than re-deriving it:
`design/README.md`'s "lower bound" framing describes what the reduced
sub-model *excludes* (the loop's own mismatch term) — it is not a proof that
an excluded term can only *add* variance, and the reduced sub-model's
loop-broken bias point (tail switch held on, diode-connected rather than
cross-coupled loads) is also a **different operating point**, which can carry
different mismatch **sensitivity**: a diode-connected load's own low
intrinsic gain divides the same device-level current mismatch into a
*larger* input-referred offset than the same mismatch produces through the
regenerative pair's much higher effective decision gain. "Different
methodology, different operating point, different mismatch sensitivity" is
the only reading consistent with two benches that each reproduce themselves
and were calibrated against the same PDK models — not "one bench is wrong".

**Both benches stay committed** (issue #23's resolution of DR-0001
Consequence 2 for the offset row — *retain, not retire*): the **difference**
between the two numbers is itself a diagnostic (it approximates what the
regenerative stage and its bias conditions contribute), the front-end bench
is the cheap regression check a sizing pass runs first, and it still carries
the ±50 mV common-mode axis the whole-latch bench does not sweep at all —
see [`sim/comparator-offset-transient-mc/README.md` → "Relationship to
`comparator-offset-mc`"](../../sim/comparator-offset-transient-mc/README.md#relationship-to-comparator-offset-mc).

**Why the bound does not move.** It does not need to: the unchanged DRAFT
Target is met at 45/45 by the measurement that measures the row's actual
subject — so the drafting-time question ("is this bound set above what the
design reaches?") is answered, not waived. The 8 mV **Stretch** is missed at
27/45 points, exactly what a Stretch column exists to record, and the Pelgrom
lever named at drafting remains the honest design work for closing it:
σ_Vos ∝ 1/√(W·L), DR-0001's sizing is explicitly *not* a sizing study
(`design/README.md`), and the worst whole-latch point (10.537 mV 3σ) needs
10.537/8 = 1.32 in σ ⇒ ≈ 1.7× input-pair area to come inside the Stretch —
ordinary design work on a 130 nm node, not a physical wall. What neither
measurement supports is a **common-mode** claim: the whole-latch bench
sweeps the differential axis at `dut_vcm` only (a named extension in its
README), so no statement about whole-latch offset *vs. common-mode movement*
is made here, and none should be inferred from Row 1's MET status.

### Row 2 — Input-referred noise: **ratified unchanged**; NOT met on the compliance path

| | |
|---|---|
| **Ratified Target** | ≤ 1.0 mV rms, differential, input-referred, total integrated (unchanged from DRAFT) |
| **Ratified Stretch** | ≤ 0.6 mV rms (unchanged from DRAFT) |
| **Ratified evidence path (scoping, unchanged from drafting)** | The **compliance** number must come from **transient-noise runs with seeds and run counts committed**, per `CLAUDE.md` ("the input-referred noise floor from transient-noise runs with seeds and run counts committed"). At drafting this was a forward scoping — no such bench existed; it now exists, and its measurement is the row's Status below. The `.noise`-on-a-reduced-sub-model number remains a **reportable lower bound**, not the compliance path. |
| **Measured (reportable lower bound, front end only)** — [`sim/comparator-preamp-noise/`](../../sim/comparator-preamp-noise/) | 216.7 µV rms (`ff_-40c_1.20v`) … **388.9 µV rms** (`fs_125c_1.08v`), all 45 points; nominal corner 277.8 µV rms integrated over that sub-model's own 58.7 MHz band (input-referred white density 36.27 nV/√Hz). Total integrated output noise ÷ measured DC gain (not `inoise_total` — the record's own note on the 200× error that convention has caused upstream). Record [`20260916-113303-180cca7`](../../sim/comparator-preamp-noise/records/20260916-113303-180cca7.md). |
| **Measured (compliance path, whole latch)** — [`sim/comparator-transient-noise/`](../../sim/comparator-transient-noise/) | `TRNOISE`-injected transient decision statistics against `comparator_dut` (real strobe, real cross-coupled regenerative pair), injecting the AC bench's own 36.27 nV/√Hz density at the input pins and letting the latch set its own aperture; **N = 80 trials per rung per PVT point**, 3 rungs (±1.0 mV overdrive plus a zero-overdrive noise-is-injected guard), 45/45 points. Implied 1σ input-referred decision noise (the bench's committed `probit.py` slope estimator, immune to threshold offset): per-point min **0.889 mV** (`tt_27c_1.20v`) … max **2.710 mV** (`tt_125c_1.08v`), **grid-wide mean 1.335 mV**. Record [`20260921-154729-41cbc7f`](../../sim/comparator-transient-noise/records/20260921-154729-41cbc7f.md), `Verdict: PASS`. |
| **Status** | **NOT MET on the ratified compliance path.** The grid-wide mean — the summary statistic the bench's own precision analysis designates (±13 % 1σ per-corner sampling scatter at N = 80; per-corner rank claims are unsupported below that) — exceeds the 1.0 mV Target. |

**Three qualifiers govern the reading, and all three are the bench's own**
([`sim/comparator-transient-noise/README.md` → "Implications for DR-0002's
review"](../../sim/comparator-transient-noise/README.md#implications-for-dr-0002s-review)):

1. **The compliance number is itself still a lower bound.** The injection
   enters at the DUT's black-box input pins; the regenerative pair's own
   thermal/flicker noise is not independently injected at all. A
   strictly-more-complete measurement therefore predicts a *higher* true
   floor — the miss can widen with better evidence, not close.
2. **It is the first compliance-path number, and it landed ~5× the AC lower
   bound** — exactly the direction the drafting-time demotion of the
   `.noise` figure predicted for a strictly-more-complete measurement. (An
   early draft of the bench that calibrated to the AC *total* instead of its
   *density* produced the inversion instead; the bench README documents why
   the density, not the band-limited total, is the right injection.)
3. **"Exceeds the Target as measured" is not the same finding as "the Target
   is wrong."** The draft Target was set when the only measurement was a
   0.278 mV band-limited lower bound; the first whole-latch compliance number
   comes out at 1.335 mV. Whether the bound is re-derived, the front end
   re-sized, or the evidence chain (regeneration-stage injection) extended
   before the row is judged again is a conversation the key-holders hold with
   real numbers on both sides — this row's order of operations is the DR
   process itself, and no re-derivation is performed here.

**Why the bound does not move.** Not relaxed — `CLAUDE.md` forbids
relaxing-to-pass, no relaxation is proposed, and the row is ratified in a
failing state exactly like the other recorded misses. Not tightened or
re-derived either — a single first compliance measurement with ±13 %
per-corner scatter and a known-missing noise term is not evidence on which
to re-found a bound in *either* direction. Folding it in honestly means
recording the miss in the table and handing the design the work list:
front-end noise density (a first-stage sizing matter — the offset row's
Pelgrom lever and this row's density share their lever), and the
regeneration-stage injection extension that would complete the bench (an
open item below — the DUT's black-box pin contract currently gives
testbenches no access to internal nodes).

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
| **Status (charge sub-bound)** | **CONSISTENT, NOT CERTIFIED.** The bench emits no Q_kick measurement; the only available estimator is biased toward passing by a factor of ~1.3 … 2.9× (derived in (b) below), a range that straddles the bound. 25 fC survives if the effective kick duration is ≲ R_src·C_in = 100 ps and fails if it is ≳ 200 ps, and the committed records cannot distinguish the two. The same vocabulary this record uses wherever committed evidence cannot certify a bound either way — by contrast, Rows 1 and 2 now carry whole-latch measurements with definite verdicts. |
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
- **Row 1's common-mode behaviour.** The Target is met on the whole-latch
  bench's differential axis at `dut_vcm`; no whole-latch common-mode sweep
  exists (a named extension in that bench's README), and
  `comparator-offset-mc`'s ±50 mV common-mode axis reaches only the front
  end. Nothing here certifies the row against common-mode movement.
- **A complete figure for Row 2.** The compliance-path measurement is itself
  still a lower bound (the regenerative pair's own device noise is not
  injected); the ratified Target binds, is missed on what is measured, and
  the complete floor remains unmeasured.
- **A compliance certificate for Row 4's charge sub-bound.** The 25 fC bound
  binds; whether the design meets it is undetermined, because the bench emits
  no Q_kick key and the available estimator's bias bracket straddles the bound
  (Row 4 (b)). The residue sub-bound of the same row *is* certified.
- **The gap-to-T1 tracker's item 5.** This record clears item 5's *structural
  blocker* (there is now a ratified table to simulate against). Item 5 itself
  — a full PVT corner campaign scored against the ratified spec — is separate,
  later work.
- **Recalibration (or deliberate retention) of the two corner-sensitivity
  check floors** (`av_dc` process, `td_od50_ns` temperature). This record
  ratifies no floor either way: the drafting record deliberately left both
  failing, and the open item was resolved outside it by
  [#16](https://github.com/2AMLogic/sg13g2-comparator/issues/16) /
  [PR #29](https://github.com/2AMLogic/sg13g2-comparator/pull/29)
  recalibrating both against the real DUT.

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
  of a spec, not an anomaly. *This revision is the tail of that alternative
  realized, in the opposite order: the benches landed on `main` while this
  record sat proposed, and instead of waiting for a re-draft their evidence
  is folded into Rows 1–2 and the bound-founding reasoning is re-derived
  there (issue #36).*
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

1. **The table is ratified in the state the design actually measures, misses
   included** — as of this revision: the noise row's Target misses on the
   whole-latch compliance path (1.335 mV grid mean vs. ≤ 1.0 mV), the
   offset row's Target is met at 45/45 with its Stretch missed at 27/45,
   the decision-time stretch misses at 9 `ss` points and the power stretch
   misses outright. The restated kickback row is certified only on its
   residue clause — its charge clause is ratified as "consistent, not
   certified", because no committed testbench emits that quantity directly.
   That is now the public, recorded state of the block — `README.md` says so
   in the table itself, not in a footnote.
2. **The design acquires a concrete, ordered work list**: front-end noise
   density (and the regeneration-stage injection extension) for the noise
   row's compliance-path miss, input-pair sizing for the offset Stretch
   (≈ 1.7× front-end area at the worst hot corner by the Pelgrom lever —
   the Target no longer needs it), `dut_ib` reduction for power (~95 % of
   the total), and `ss`-corner speed for the decision-time stretch. None of
   these needs a new decision record; they are ordinary design work against
   a now-binding spec.
3. **Item 5 of the gap-to-T1 tracker is unblocked** and can be scored "vs.
   ratified spec" for the first time.
4. **The kickback row now constrains future driving stages explicitly.**
   Anyone attaching a source network to this comparator gets a Q_kick bracket
   of ~11 … 41 fC/side (estimate 8.8 … 14.3 fC, with the bias of Row 4 (b)
   applied) and the V_peak ≈ Q/C_in conversion, rather than a 5 mV promise that
   would not have survived contact with a real 100 fF input node. Sizing a
   driver off the low end of that bracket is a mistake the record now names.
5. **One committed FAIL record is cited by this spec as drafted** (the
   regeneration row's — the other drafting-time FAIL citation was retired in
   this revision by re-pointing Row 2's evidence at the recalibrated, PASS
   re-run, and the floors themselves were recalibrated outside this record
   by #16 / PR #29). The remaining citation is acceptable only because the
   failure is a check-floor calibration artifact with a passing negative
   control — the evidence section says so inline precisely so a reader
   landing on that FAIL record does not have to read three documents to
   learn it is not a spec failure.

## Open items

- **A Target-column average power bound**, founded on a gm/Id or bias-point
  sizing study (not on the current carried-over `dut_ib`).
- **Regeneration-stage noise injection.** The whole-latch offset and
  transient-noise benches DR-0001 Consequence 1 named have both landed
  (issues
  [#23](https://github.com/2AMLogic/sg13g2-comparator/issues/23) /
  [PR #33](https://github.com/2AMLogic/sg13g2-comparator/pull/33) and
  [#24](https://github.com/2AMLogic/sg13g2-comparator/issues/24) /
  [PR #40](https://github.com/2AMLogic/sg13g2-comparator/pull/40)) — that
  requirement is discharged, and Rows 1–2 above rest on them as revised. The
  residual gap for *Row 2* is injection completeness: the compliance bench
  injects only the front end's own density at the DUT's black-box input
  pins, the regenerative pair's own thermal/flicker noise is not
  independently injected, and completing it needs the DUT's pin contract
  (`sim/dut/README.md`) extended so a testbench can reach internal nodes —
  future harness work, not a spec change.
- **A whole-latch common-mode offset sweep.** The residual gap for *Row 1*:
  the whole-latch offset bench sweeps the differential axis at `dut_vcm`
  only, and `comparator-offset-mc`'s ±50 mV common-mode axis has no
  whole-latch analogue yet — a named, not-yet-specified extension in that
  bench's README, and the stated reason Row 1's MET status carries no
  common-mode claim.
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
  check floors** that failed against the real DUT at drafting — resolved
  outside this record by #16 / PR #29 (both floors recalibrated, both
  benches re-run to PASS); the regeneration row's drafting-time citation is
  kept with its FAIL explained in the evidence section.
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
