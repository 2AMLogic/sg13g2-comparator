# `sim/comparator-offset-transient-mc/`

**Transient Monte-Carlo input-referred offset of the WHOLE latch** (strobe →
decision) — the un-reduced [DR-0001](../../spec/decision-records/0001-comparator-topology.md)
topology (`comparator_dut`, `design/comparator.spice`), not
[`sim/comparator-offset-mc/`](../comparator-offset-mc/)'s loop-broken,
diode-connected `comparator_dut_analog` reduced sub-model.

Backs [`README.md`'s Offset-σ row](../../README.md#target-specification-draft--engineering-to-ratify)
alongside `comparator-offset-mc` — see "Relationship to `comparator-offset-mc`"
below for what each of the two experiments now answers, and why **both stay
committed**.

> **`provenance: schematic` records here substantiate DR-0001's chosen
> topology's own measured whole-latch offset — not yet a ratified
> `README.md` number.** That ratification is a separate, later act
> (`spec/porting-plan.md`'s third step in this chain; see also DR-0002,
> [#12](https://github.com/2AMLogic/sg13g2-comparator/issues/12) /
> [PR #18](https://github.com/2AMLogic/sg13g2-comparator/pull/18), open at
> the time this experiment was added — "README.md's Measured column" below).

```bash
python3 sim/run_corners.py comparator-offset-transient-mc -j 8
```

## Method

**A digital staircase, not a DC sweep or a per-draw bisection search.**
`comparator_dut` has no DC-resolvable operating point at all (DR-0001
Decision §3 — the cross-coupled regenerative pair's positive feedback
prevents one once `CLK` is high, and the front end is simply off while
`CLK` is low), so `comparator-offset-mc`'s `dc`-sweep method cannot reach it.

`set rndseed=20260916` once, then **60 draws per PVT point** through a
`dowhile` / `reset` loop — each `reset` re-evaluates SG13G2's `agauss()`
mismatch terms (confirmed against the installed checkout during issue #6,
[`sim/device-mismatch-confirm/README.md`](../device-mismatch-confirm/README.md)),
exactly the idiom `comparator-offset-mc` already uses for its own loop. Per
draw, ONE 990 ns transient sweeps a 33-level differential-input staircase
(−48 mV to +48 mV, 3 mV/step) riding on the periodic strobe, 30 ns/level (10
ns reset, 10 ns evaluate, 10 ns settle — the exact cadence
[`comparator-regeneration`](../comparator-regeneration/) already validates
for this DUT). Every level is a genuinely independent decision: `reset`
between strobes clears the prior decision, the same property
`comparator-regeneration`'s "every instance decides both ways" already
demonstrates for this DUT. The held, supply-normalized output is sampled
once per level, well after that level's strobe has closed.

Offset is extracted from the resulting near-binary staircase:

```
lowcount = number of the 33 levels reading LOW
vos      = -0.048 + (lowcount - 0.5) * 0.003          [V]
```

1-sigma is reported both raw (`sig_vos_raw_mv`, includes the staircase's own
3 mV quantization noise) and quantization-corrected (`sig_vos_mv = sqrt(raw
variance − (3 mV)²/12)`, the standard uniform-quantization deconvolution).
`vos_3sig_mv` is the corrected 3σ value a comparator offset spec is
conventionally stated at. Every `sqrt()` is guarded with `abs()`, mirroring
`comparator-offset-mc`'s own numerical-precision discipline (a
mismatch-collapsed population can land a few ULPs negative from
floating-point summation order; ngspice's `sqrt()` of a negative real returns
a COMPLEX value the harness's `m_<name> = <float>` regex cannot parse).

### Why a staircase, not a bisection search

A per-draw bisection (several short `tran` sub-runs per draw, narrowing
toward the flip point) was considered and rejected: ngspice only re-rolls
SG13G2's `agauss()` mismatch terms on `reset`, and `reset` also restarts the
transient clock — so holding *one* draw's mismatch fixed across several
bisection sub-runs is not achievable with this harness's control-block idiom.
One staircase transient per draw sidesteps that: one `reset` (one mismatch
draw), one `tran` covering every level.

### What this bench does NOT cover (named, not silently omitted)

- **Common-mode dependence of the whole-latch offset.** This bench sweeps
  only the differential axis at the DUT's own `dut_vcm`; `comparator-offset-mc`'s
  ±50 mV common-mode sweep has no analogue here yet — a named, not-yet-specified
  extension, kept out of scope here so the transient grid (33 levels × 60
  draws × 45 PVT points) stays inside the harness's per-point timeout.
- **Layout-induced systematic offset.** This is a schematic-level record; no
  layout exists yet.
- **Dynamic (regeneration-noise-driven) metastability spread.** This bench's
  `dowhile`/`reset` loop only re-draws static `agauss()` mismatch, never
  thermal/flicker noise — it reports the mismatch-driven offset distribution
  only. The noise-driven decision-time/metastability spread is
  [issue #24](https://github.com/2AMLogic/sg13g2-comparator/issues/24)'s
  separate transient-noise bench, not this one.

### Why N = 60, not N = 200

`comparator-offset-mc`'s 200 draws are cheap: one `dc` sweep per draw (six
operating points, milliseconds each). This bench's per-draw cost is a full
990 ns / 33-level transient — far higher — so N = 60 was chosen as the draw
count the 45-point grid can complete in a practical wall-clock budget.
Statistical precision on each reported σ is `1/sqrt(2N)` = **9.1 %** at
N = 60 (`comparator-offset-mc`'s N = 200 gives 5.0 %). The same seed
(`20260916`) is used at every PVT point (common random numbers), so movement
of the reported σ across the grid is a real PVT effect, not sampling noise.

## Relationship to `comparator-offset-mc`

**Both experiments stay committed — this is a deliberate decision, not an
oversight (DR-0001 Consequence 2's open item, resolved here).**

DR-0001 Consequence 2 named an undecided choice: whether
`comparator_dut_analog` (the reduced sub-model `comparator-offset-mc`
instantiates) is retained as a standing lower-bound check alongside a new
transient-methodology bench, or the offset-MC/preamp-noise benches are fully
re-founded on transient methodology instead. This experiment answers that
for the **offset** row specifically (the noise row's equivalent choice is
out of scope — a separate future issue, not #23):

**Decision: retain `comparator-offset-mc` / `comparator_dut_analog` as a
standing lower-bound check. Do not retire it.**

- **The two experiments measure genuinely different, complementary
  quantities, not redundant ones.** `comparator-offset-mc` isolates the
  front end's own contribution (input pair + tail mirror + diode-connected
  load mismatch) at a real, stable DC operating point; this bench measures
  the *whole* latch's decision threshold, folding in the regenerative pair's,
  reset devices', isolation inverters', and SR latch's own mismatch as well
  as whatever the different bias condition the closed clocked loop settles
  into contributes. Comparing the two numbers side by side is itself a
  diagnostic: the *difference* between them approximates how much offset the
  regenerative stage and its own bias conditions add (or, as observed below,
  do not add) on top of the front end alone — a decomposition that is lost
  if the reduced sub-model is retired.
- **`comparator-offset-mc` is far cheaper per point** (a `dc` sweep vs. a
  990 ns / 33-level transient), so it remains the fast regression check for
  a sizing change's front-end-mismatch impact, while this bench is the
  expensive, authoritative whole-latch number.
- **`comparator-offset-mc` also still covers the common-mode axis** this
  bench does not (see above) — retiring it would drop that coverage
  entirely, not just make it more expensive to get.
- Retiring `comparator-offset-mc` saves nothing this repo needs saved: `sim/`
  is append-only evidence, not a maintained "current status" page, so a
  second standing experiment costs disk and wall-clock time on a full
  characterization run, not upkeep risk.

### An observation, not (yet) a DR-contradiction

The first full grid measured by this bench (see "Records" below) reports
whole-latch `sig_vos_mv` **below** `comparator-offset-mc`'s own reported
front-end-only `sig_vos_mv` at the matching corners, rather than at or above
it. `design/README.md`'s "lower bound" framing for `comparator_dut_analog`
describes what that reduced sub-model *excludes* (the regenerative loop's own
mismatch contribution) — it is not itself a proof that the excluded term can
only add variance; the reduced sub-model's loop-broken bias point (tail
switch gate tied to `vdd`, not clocked; diode-connected rather than
cross-coupled loads) is also a different operating point from the real
clocked latch's, and a different operating point can carry different
mismatch *sensitivity* (e.g. different small-signal gain at the point the
offset is referred through), independent of which devices are or are not
included. This is flagged here as a genuine, measured finding worth
carrying into DR-0002's eventual review (§ once [PR #18](https://github.com/2AMLogic/sg13g2-comparator/pull/18)
lands) — it is **not** filed as a new decision record on its own: DR-0002
is not yet merged/ratified, so there is nothing ratified for this finding to
contradict on physics grounds yet, and the finding itself is consistent with
"different methodology, different operating point" rather than with either
bench being wrong.

## Mismatch is a corner selection, not a fragment parameter

Same convention as `comparator-offset-mc`: the `mos_mismatch` corner set
(`mos_{tt,ff,ss,fs,sf}_mismatch`) is both the process-corner axis and the
Monte-Carlo mismatch switch at once (`sim/harness/corners.py`'s module
docstring). This bench's `.spice` fragment sets nothing mismatch-related
itself.

## `README.md`'s Measured column

The issue that scoped this bench (#23) was drafted expecting a "Measured"
column already present in `README.md`'s target-specification table — that
column does not exist on `main` yet: it is introduced by
[DR-0002](../../spec/decision-records/) / [PR #18](https://github.com/2AMLogic/sg13g2-comparator/pull/18)
(closes [#12](https://github.com/2AMLogic/sg13g2-comparator/issues/12)),
which is **open and deliberately held for a human**
(`loom:operator-only` + `loom:operator-blocked`) at the time this bench was
built. Rather than block on that merge or edit PR #18's branch, this bench's
evidence is instead folded into the **existing** Offset-σ row's *Basis* text
(the pattern every other row already follows — inline evidence narration, no
separate column) — see `README.md`. **Once PR #18 lands and introduces a real
Measured column, this bench's number belongs there too** — that follow-up
edit is out of scope here; a dedicated issue should be filed against that
gap if it is not picked up automatically once PR #18 merges.

## Provenance

Testbench structure (staircase levels, strobe cadence, quantization-noise
correction, checks) is original engineering for this bench — there is no
directly analogous transient-offset-staircase methodology in
`gf180-comparator`/`sky130-sar-adc` to port (their comparators either have a
DC-resolvable front end or use a different offset-extraction technique).
The Monte-Carlo seeding/`reset` idiom, corner-set convention, and
quantization-guard discipline are carried over unchanged from
`sim/comparator-offset-mc/`, per [`spec/porting-plan.md`](../../spec/porting-plan.md).

## Records

| record | DUT | grid | verdict |
|---|---|---|---|
| _pending — see the record minted by the full 45-point run this PR commits_ | `comparator-dr0001` (**schematic**, `design/comparator.spice`) | 45/45, `mos_mismatch` × 3 T × 3 V | _pending_ |
