# `sim/comparator-transient-noise/`

**Input-referred noise floor of the WHOLE comparator** (`comparator_dut`,
the real regenerative latch — **not** `comparator_dut_analog`), measured by
`ngspice` TRNOISE-injected **transient decision statistics** (a "hit-rate" /
probit measurement) over the full PVT grid.

Backs [`README.md`'s noise row](../../README.md#target-specification-draft--engineering-to-ratify),
as the **compliance evidence path** `CLAUDE.md` names ("the input-referred
noise floor from transient-noise runs with seeds and run counts committed")
and DR-0002 (`spec/decision-records/0002-target-spec-ratification.md`, at
the time of writing still un-ratified — see "Ratification status" below)
scopes for this row. `sim/comparator-preamp-noise/`'s `.noise` AC analysis
remains a **reportable lower bound**, not this row's compliance evidence —
see "Retain, not retire: `comparator_dut_analog`" below for why both benches
stay committed side by side.

```bash
python3 sim/run_corners.py comparator-transient-noise -j 8
```

## Method

Three parallel `comparator_dut` instances, each biased at a fixed
differential overdrive and each independently driven by its own `trnoise()`
source at its input pins:

| rung | overdrive | why |
|---|---|---|
| `frac_high_zero` | 0 (none) | **noise-is-actually-injected guard**: with zero overdrive and mismatch off, the only thing that can make a trial decide either way is the injected noise, so this rung should land near 0.5 |
| `frac_high_plus` | +75 µV | correct decision is HIGH |
| `frac_high_minus` | −75 µV | correct decision is LOW |

Each rung is re-run 40 times per PVT point via `reset` inside an ngspice
`dowhile` loop (a fresh `tran` each time), and `dout` is sampled once per
trial, **while `CLK` is still high** — see "Debugging notes" below for why
that particular timing choice is load-bearing. `frac_high_*` is the raw,
directly observed fraction of trials that decided HIGH at each rung.

**The injected noise is calibrated to, not derived from, this design.** The
`TRNOISE(NA TS 0 0)` source's total broadband rms is set to match
`sim/comparator-preamp-noise/`'s own nominal-corner (`tt_27c_1.20v`) total
integrated input-referred number, **277.827 µV rms**
([record `20260916-113303-180cca7`](../comparator-preamp-noise/records/20260916-113303-180cca7.md)),
applied directly and ideally at the `vinp`/`vinn` pins — the same injection
point and the same "total integrated, differential, input-referred"
definition that record already uses. The **same** injected level is used at
**every** PVT point, deliberately not re-derived per corner: this isolates
what this bench adds (how *this corner's own regeneration dynamics* reshape
a *given* input noise level) from the front end's own already-corner-
characterized noise magnitude. `TS = 20 ps` is chosen safely below the
fastest measured regeneration time constant on this grid (42.6 ps at
`ff_-40c_1.32v`,
[`sim/comparator-regeneration/`](../comparator-regeneration/records/20260916-021945-36773c7.md)),
so the injected process is effectively uncorrelated on the latch's own
regeneration timescale.

### NA/TS calibration (empirical, not assumed)

ngspice-46's `TRNOISE(NA TS NALPHA NAMP)` piecewise-linear-interpolated white
component has a **total variance of `(2/3)·NA²`, independent of `TS`**
(confirmed empirically at `TS = 10p/50p/200p`, matching the analytic
average-interpolation-variance derivation) — i.e. `NA` calibrates the
source's own total broadband rms, not a spectral density. `vn_na = 3.362e-4`
solves `0.8263·vn_na = 277.827e-6`, where `0.8263` is this repo's own
empirically measured total-rms/`NA` ratio (consistent with the analytic
`sqrt(2/3) = 0.8165` prediction to ~1%).

### Why transient, not `.noise`

ngspice-46 has no automatic per-device transient noise (no PSS/pnoise) —
confirmed against the installed checkout and against ngspice's upstream
source (`src/spicelib/devices/vsrc/vsrcload.c`'s `TRNOISE` case). The
mechanism `CLAUDE.md` calls "transient-noise runs" is ngspice's `TRNOISE`
independent-source function: an explicit, calibrated noise voltage injected
at the DUT's own input port, not a small-signal device-physics analysis.
That is what this deck does — see
[`sim/comparator-preamp-noise/README.md`](../comparator-preamp-noise/README.md)'s
"What this bench cannot reach" for the AC bench's own statement of the same
gap.

## Probit inversion

`frac_high_plus`/`frac_high_minus` are the raw measurements; converting them
to an implied 1-sigma input-referred noise is a simple, documented,
reproducible **post-hoc** calculation over the committed record, not a deck
measurement (a saturated `frac_high` of exactly `1.0`, observed at some
corners/probes during calibration, makes the standard probit formula's
`ln(1-p)` term singular, and ngspice's `let` has no clamp the deck could
guard it with):

```
sigma_plus  = od_x / Phi^-1(frac_high_plus)
sigma_minus = od_x / Phi^-1(1 - frac_high_minus)
```

where `Phi^-1` is the standard normal inverse-CDF (probit function) and
`od_x = 75 µV`. This assumes the decision is a zero-threshold comparison of
`(overdrive + noise)` — reasonable here because mismatch is off (the plain
`mos` corner set) and the injected noise dominates any residual simulator-
level asymmetry.

**Precision at `N = 40` is not a flat percentage.** The binomial standard
error on `frac_high` itself is ~7.9% at `p = 0.5` (smaller at the tails),
but that propagates through `Phi^-1`'s derivative, which is steep near
`p = 0.5` and shallow in the `p ≈ 0.7–0.95` band this bench's rungs are
calibrated to land in. Comparing the `+od_x`-derived and `-od_x`-derived
sigma **at the same corner** (which would agree exactly at infinite `N`)
is therefore the honest single-point precision check; the **grid-wide mean
across all 45 corners × 2 rungs** is the defensible summary statistic, not
any single corner's number. See "Records" below for the actual observed
spread.

## Seed reproducibility: recorded, not achieved

`setseed 20260916` is issued at the top of the control block — the same
literal seed value `comparator-offset-mc/` uses, and the form its own
`testbench.py` loader **requires** for a `record_kind: monte-carlo`
manifest (`_validate_monte_carlo_seed`, added per issue #28's finding that
`set rndseed=` does not seed `agauss()` on this pinned ngspice-46).

**On this repo's pinned ngspice-46, none of the three mechanisms available
control `TRNOISE`'s internal generator.** Confirmed empirically by direct
A/B testing (a minimal one-resistor deck, `TRNOISE(1 20p 0 0)`, `reset`-ed
inside a `dowhile` loop, run across separate `ngspice -b` invocations with
an identical seed each time):

| mechanism | reproduces identical `TRNOISE` draws across invocations? |
|---|---|
| `setseed <N>` (control command) | **No** |
| `set rndseed=<N>` (control command) | **No** |
| `.option seed=<N>` (netlist option) | **No** |
| (no seeding at all) | No (same as above — confirms the seed commands have no effect on this generator) |

This is a genuine, confirmed property of the installed ngspice-46 build —
not a deck bug. `TRNOISE`'s generator is evidently not tied to the RNG
stream any of `setseed`/`set rndseed=`/`.option seed=` controls (that stream
is what `agauss()` — used by `comparator-offset-mc/`'s mismatch draws —
*is* confirmed to respond to via `setseed`, per issue #28). **What is
seeded, and does reseed correctly, is not what this bench needs seeded.**

**Consequently:** `setseed 20260916` is recorded here purely for this
repo's cross-experiment seed-recording convention and to satisfy
`testbench.py`'s loader guard — it is **not load-bearing for
reproducibility**. What *is* committed and load-bearing, per `CLAUDE.md`'s
"seeds and run counts committed" requirement, is the **run count** (`N = 40`
trials per rung per PVT point, common across the whole 45-point grid) and
the resulting `frac_high_*` values as observed on this specific dated run.
Re-running this exact deck samples a **different** set of 40 draws per rung
per point and lands at a statistically consistent, not bit-identical,
`frac_high_*` — which is why this document states the `N`-implied precision
above rather than claiming exact reproducibility. This divergence from
`comparator-offset-mc/`'s reproducible-seed convention is itself worth a
reader's attention, which is why it gets its own section rather than a
buried caveat.

## What this bench adds, and does not add, over `comparator-preamp-noise/`

**Adds:** `comparator-preamp-noise/`'s `.noise` analysis is a small-signal,
DC-operating-point analysis of `comparator_dut_analog` — DR-0001's
diode-connected, loop-broken reduced sub-model. It structurally excludes
the regenerative loop's own dynamics and any nonlinear amplification or
attenuation the loop applies to a given input noise level. This bench
instantiates the **whole** `comparator_dut` (real `CLK` strobe, real
cross-coupled regenerative pair) and drives it with the **same magnitude**
of noise the AC bench already reports, observing how the real nonlinear
regeneration reshapes it into a decision-boundary sigma — new information
the AC bench cannot provide by construction.

**Does not add:** this deck injects noise **only** at `comparator_dut`'s
contract input pins (`vinp`/`vinn`) — the DUT's black-box pin contract
(`sim/dut/README.md`) gives testbenches no access to internal nodes, so the
regenerative pair's own thermal/flicker noise sources cannot be
independently injected without editing `design/comparator.spice` (out of
this issue's scope). The measured sigma therefore reflects "the front end's
own already-known noise level, propagated through the real regeneration
dynamics" — **not** an independent measurement of the latch pair's own
noise contribution. This is a materially more complete measurement than the
AC bench's (transient, whole-latch, nonlinear-dynamics-aware) but is
**still not** the fully complete number DR-0001 Consequence 2 originally
named as the open item.

**A real, honestly-reported consequence of this scope:** the implied
decision-boundary sigma this bench reports (see "Records" below) comes out
*lower* than the AC bench's own front-end-only integrated total. This is
not evidence the real noise floor is smaller than the AC bench's number —
it is evidence that a short-correlation-time (`TS = 20 ps`) noise process
is substantially averaged/filtered by the latch's own regeneration dynamics
before it affects the decision, which is a different (and, for a
decision-statistics question, arguably more relevant) quantity than a
DC/AC-integrated total. Both numbers are reported; neither supersedes the
other, per "Retain, not retire" below.

## Retain, not retire: `comparator_dut_analog`

DR-0001 Consequence 2 named an open item: whether `comparator_dut_analog`
(the reduced sub-model `comparator-offset-mc/` and `comparator-preamp-noise/`
instantiate) stays a standing lower-bound check once a transient,
whole-latch path exists, or is retired. **Decision: RETAIN, not retire —**
made independently here because, at the time of writing, the sibling issue
(#23, the transient Monte-Carlo offset bench) that could otherwise have
settled this for the reduced sub-model in general is still open, so there
is no existing decision to defer to.

**Reasoning:**

1. **The two benches measure different, not overlapping, things.** This
   bench's own "What this bench adds, and does not add" section above is
   the whole reason: it reshapes a *given, already-known* front-end noise
   level through real regeneration dynamics, but cannot independently
   source the regenerative pair's own noise (a black-box-contract
   limitation, not a methodology choice this bench could lift on its own).
   `comparator-preamp-noise/`'s AC number remains this bench's own
   **calibration input** (see "Method" above) — retiring it would remove
   the very number this bench is calibrated against, not just a redundant
   cross-check.
2. **The AC bench isolates a decomposition the transient bench cannot.**
   Because it excludes regeneration dynamics by construction, the AC
   number is unambiguously "front-end noise, corner-swept, nothing else" —
   a cleaner quantity for a future front-end sizing/optimization pass than
   a decision-boundary sigma that already has regeneration's own reshaping
   folded in.
3. **No cost to keeping it.** `sim/comparator-preamp-noise/`'s testbench,
   corners, and records are unmodified by this issue (per its own scope);
   retaining it costs nothing beyond what already exists, and DR-0002
   (once ratified) already frames it as a *reportable lower bound*, not a
   claim of completeness — a framing this decision leaves intact.

This decision applies **only to the noise row's own sub-model retention**,
not to the sibling offset row (#23's own open item, to be decided
independently there per that issue's acceptance criteria).

## Debugging notes

- **`dout` must be read while `CLK` is still high.** The comparator's
  output stage (an SR latch) holds the decided value only during the
  evaluate phase; reading after `CLK` falls reads the **reset** value, not
  the held decision — confirmed empirically while developing this deck
  (an early version that sampled after the strobe read a constant value at
  every trial, which is what first surfaced the mistake, not a noise-
  injection failure).
- **`frac_high_zero` landing near 0.5 is itself proof the injection is
  live.** At zero overdrive and zero mismatch, a genuinely un-noised latch
  resolves a deterministic numerical tie-break identically on every
  `reset` — `frac_high_zero` would collapse to exactly `0.0` or `1.0`, not
  sit near `0.5`. `testbench/tb.json`'s `frac_high_zero` check documents
  this as the bench's own structural negative control (see that check's
  `description`).
- **Solver tolerances are looser than the other three benches'**
  (`reltol=1e-2`/`abstol=1e-12` here vs. `1e-4`/`1e-9`/`1e-13` there) —
  deliberately: this bench only needs a correct binary decision at a fixed
  readout instant, not sub-picosecond delay precision the way
  `comparator-regeneration/`'s τ extraction does, and looser tolerances
  materially cut the cost of the `N × 3-rung × 45-corner` transient-run
  grid this bench needs.

## Records

| record | DUT | grid | verdict |
|---|---|---|---|
| [`20260916-151702-ffdd3b9`](records/20260916-151702-ffdd3b9.md) | `comparator-dr0001` (**schematic**, `design/comparator.spice`) | 45/45, `mos` × 3 T × 3 V | PASS |

**Implied decision-boundary sigma (probit inversion over the committed
record, per "Probit inversion" above):** across all 45 corners × 2 rungs
(90 values), **38.3 – 194.6 µV**, grid-wide mean **79.6 µV** (stdev 24.6 µV
across the 90 values — the single-point-precision spread "Probit inversion"
describes, not a claim that this is the sigma's own PVT sensitivity).
**Both Target (≤ 1.0 mV rms) and Stretch (≤ 0.6 mV rms) are met at this
implied sigma**, at every corner and both rungs. This is **consistent
with, not a replacement for,** `comparator-preamp-noise/`'s own
216.7–388.9 µV lower-bound range — see "What this bench adds, and does not
add" above for why a smaller implied number here is expected, not a
contradiction.

## Provenance

Novel to this repo — not ported from `gf180-comparator` or `sky130-sar-adc`.
`sim/comparator-regeneration/testbench/` supplied the harness-integration
shape (parallel comparator instances at different overdrives, driven off
one shared `CLK`, supply-normalized where relevant); the decision-statistics
/ probit-inversion methodology itself is this bench's own, developed against
the specific constraint that ngspice-46 has no PSS/pnoise and the DUT's
black-box contract gives no access to internal noise sources. Calibrated
against `sim/comparator-preamp-noise/`'s own committed AC number rather than
an independently-assumed noise level, so the two benches' numbers are
directly comparable rather than measuring different, un-reconcilable
things.
