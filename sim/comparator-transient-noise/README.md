# `sim/comparator-transient-noise/`

**Input-referred noise floor of the WHOLE comparator** (`comparator_dut`,
the real regenerative latch — **not** `comparator_dut_analog`), measured by
`ngspice` TRNOISE-injected **transient decision statistics** (a "hit-rate" /
probit measurement) over the full PVT grid.

Backs [`README.md`'s noise row](../../README.md#target-specification-draft--engineering-to-ratify)
as the **compliance evidence path** `CLAUDE.md` names — "the input-referred
noise floor from transient-noise runs with seeds and run counts committed".
`sim/comparator-preamp-noise/`'s `.noise` AC analysis remains a **reportable
lower bound**, not this row's compliance evidence; see "Retain, not retire"
below for why both benches stay committed side by side.

```bash
python3 sim/run_corners.py comparator-transient-noise -j 8
```

## Method

Three parallel `comparator_dut` instances, each biased at a fixed
differential overdrive and each independently driven by its own `trnoise()`
source at its input pins:

| rung | overdrive | why |
|---|---|---|
| `frac_high_zero` | 0 (none) | **noise-is-actually-injected guard**: with zero overdrive and mismatch off, the only thing that can make a trial decide either way is the injected noise, so this rung must land near 0.5 (see "Negative control" below — this is checked by running it, not by assertion) |
| `frac_high_plus` | +1.0 mV | correct decision is HIGH |
| `frac_high_minus` | −1.0 mV | correct decision is LOW |

Each rung is re-run **80 times per PVT point** via `reset` inside an ngspice
`dowhile` loop (a fresh `tran` each time), and `dout` is sampled once per
trial, **while `CLK` is still high** — see "Debugging notes" below for why
that timing choice is load-bearing. `frac_high_*` is the raw, directly
observed fraction of trials that decided HIGH at each rung.

The probe overdrive `od_x = 1.0 mV` is chosen to sit near the measured
1-sigma decision noise, so each rung's hit rate lands in the informative
0.7–0.95 band. That choice is not cosmetic: a hit rate that saturates at
exactly 1.0 inverts to an *infinite* probit, i.e. a reported sigma of
exactly zero, so the manifest's `frac_high_plus`/`frac_high_minus` checks
**fail on saturation** rather than let a flattering number through.

## Calibration: a spectral density, not a band-limited total

**This is the methodological core of the bench, and the one place it is
easiest to get quietly wrong.**

`sim/comparator-preamp-noise/` reports two different things about the same
`.noise` analysis:

| quantity | nominal-corner value | what it is |
|---|---|---|
| `vn_in_uv` | 277.827 µV rms | the total, **integrated over that sub-model's own 58.7 MHz noise bandwidth** (`enbw_mhz`) |
| `white_nv_rthz` / `av_dc` | 59.4598 / 1.63936 = **36.27 nV/√Hz** | the input-referred white **density** that total was integrated from |

([record `20260916-113303-180cca7`](../comparator-preamp-noise/records/20260916-113303-180cca7.md).)

This bench injects the **density**, at `vinp`/`vinn`, and lets the **latch**
set the bandwidth. Injecting "the same total rms" instead would be wrong
here: 58.7 MHz is a property of a diode-connected, loop-broken sub-model,
not of a strobed decision, and a real decision integrates input noise over
its own aperture — tens of picoseconds, i.e. a bandwidth orders of magnitude
wider. Spreading the sub-model's *band-limited total* across this source's
own much wider band divides the in-band density by the ratio of the two
bandwidths and understates the answer by roughly the square root of that
ratio. Matching the density asks exactly the question the reduced sub-model
cannot answer for itself: *given this front-end noise density, how much
input-referred noise actually reaches the decision, through the real
regeneration dynamics and the real aperture?*

The **same** injected density is used at **every** PVT point, deliberately
not re-derived per corner: this isolates what this bench adds (how *this
corner's own regeneration dynamics* convert a *given* input noise density
into a decision-boundary sigma) from the front end's own already-corner-
characterized noise magnitude — the same separation `comparator-regeneration/`
and `comparator-offset-mc/` already make for delay and offset.

### NA/TS calibration (derived, then empirically confirmed)

ngspice's `TRNOISE(NA TS NALPHA NAMP)` white component is a linear
interpolation of iid `N(0, NA²)` samples spaced `TS` apart. Its two-sided
PSD is therefore `NA²·TS·sinc⁴(f·TS)`, giving

```
one-sided density   S = NA·sqrt(2·TS)          [V/√Hz, low-frequency]
total variance      σ² = (2/3)·NA²             (independent of TS, since ∫sinc⁴ = 2/3)
```

Both halves were confirmed on this repo's pinned ngspice-46 rather than
taken from documentation, with a standalone one-source/one-RC deck:

| check | predicted | measured |
|---|---|---|
| unfiltered source rms, `NA = 1` | 0.8165 | 0.8156 |
| rms through 1-pole RC, ENBW 157.1 MHz, `TS = 20 ps` | 79.27 mV | 81.24 mV |
| rms through 1-pole RC, ENBW 157.1 MHz, `TS = 10 ps` | 56.05 mV | 55.99 mV |
| rms through 1-pole RC, ENBW 78.5 MHz, `TS = 20 ps` | 56.05 mV | 53.42 mV |

(each from a 1 µs transient; the ~5 % residuals are the rms estimator's own
sampling error at a few hundred correlation times, and the `TS = 10 ps` row
is the one that confirms the density scales as `sqrt(TS)` rather than being
TS-independent like the total.)

`vn_na = 5.735e-3` solves `vn_na·sqrt(2·vn_ts) = 36.27e-9` at
`vn_ts = 20 ps`. `TS = 20 ps` is itself chosen safely below the fastest
measured regeneration time constant on this grid (42.6 ps at `ff_-40c_1.32v`,
[`sim/comparator-regeneration/`](../comparator-regeneration/records/20260916-021945-36773c7.md)),
so the injected process is effectively uncorrelated on the latch's own
regeneration timescale.

### TS-insensitivity cross-check

Because the calibration fixes the **density**, the measured sigma must not
depend on `TS` — the injected bandwidth is an artifact of the source, not of
the circuit. Re-running the nominal point at `TS = 10 ps` with `NA` rescaled
to `8.110e-3` (holding `NA·sqrt(2·TS)` constant) is therefore a real
falsification test of the whole calibration, not a formality. Result: see
"Records" below.

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
measurement (ngspice's `let` has no clamp with which the deck could guard
the singularity at `p = 1`):

```
sigma_plus  = od_x / Phi^-1(frac_high_plus)
sigma_minus = od_x / Phi^-1(1 - frac_high_minus)
```

where `Phi^-1` is the standard normal inverse-CDF (probit function) and
`od_x = 1.0 mV`. This assumes the decision is a zero-threshold comparison of
`(overdrive + noise)` — reasonable here because mismatch is off (the plain
`mos` corner set) and the injected noise dominates any residual
simulator-level asymmetry.

**Precision at `N = 80` is not a flat percentage.** The binomial standard
error on `frac_high` is ~5.6 % at `p = 0.5` (smaller at the tails), but it
propagates through `Phi^-1`'s derivative, which is steep near `p = 0.5` and
shallow in the `p ≈ 0.7–0.95` band `od_x` puts these rungs in — roughly
±20 % of sampling scatter on any **single** corner's implied sigma.
Comparing the `+od_x`-derived and `−od_x`-derived sigma **at the same
corner** (which would agree exactly at infinite `N`) is the honest
single-point precision check; the **grid-wide mean across all 45 corners ×
2 rungs** is the defensible summary statistic, not any single corner's
number.

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
"seeds and run counts committed" requirement, is the **run count** (`N = 80`
trials per rung per PVT point, common across the whole 45-point grid) and
the resulting `frac_high_*` values as observed on this specific dated run.
Re-running this exact deck samples a **different** set of 80 draws per rung
per point and lands at a statistically consistent, not bit-identical,
`frac_high_*` — which is why this document states the `N`-implied precision
above rather than claiming exact reproducibility. This divergence from
`comparator-offset-mc/`'s reproducible-seed convention is itself worth a
reader's attention, which is why it gets its own section rather than a
buried caveat.

## Negative control (actually run)

The `frac_high_zero` rung is this bench's structural negative control, and
it was **exercised**, not merely asserted: forcing `vn_na = 0` (noise
injection off) at `tt_27c_1.20v` and re-running gives

| measurement | noise on (`vn_na = 5.735e-3`) | noise off (`vn_na = 0`) |
|---|---|---|
| `frac_high_zero` | ≈ 0.5 | **2.3e-8** (LOW on every trial) |
| `frac_high_plus` | 0.7–0.95 | **1.0** (saturated) |
| `frac_high_minus` | 0.05–0.3 | **2.3e-8** (saturated) |

and the harness **fails** the point (`frac_high_zero … < required 0.1`), as
designed. A genuinely un-noised, zero-mismatch regenerative latch resolves
the same deterministic numerical tie-break on every `reset`; only live noise
injection can put `frac_high_zero` near 0.5. This is what makes a
near-0.5 zero rung in a committed record *evidence* that noise was injected,
rather than an assumption about the simulator.

## What this bench adds, and does not add, over `comparator-preamp-noise/`

**Adds:** `comparator-preamp-noise/`'s `.noise` analysis is a small-signal,
DC-operating-point analysis of `comparator_dut_analog` — DR-0001's
diode-connected, loop-broken reduced sub-model. It structurally excludes the
regenerative loop's own dynamics, and its integrated total is band-limited
by that sub-model's own 58.7 MHz noise bandwidth, which is not the bandwidth
over which a strobed decision integrates noise. This bench instantiates the
**whole** `comparator_dut` (real `CLK` strobe, real cross-coupled
regenerative pair), injects the same input-referred noise **density**, and
lets the real latch set its own aperture — new information the AC bench
cannot provide by construction.

**Does not add:** this deck injects noise **only** at `comparator_dut`'s
contract input pins (`vinp`/`vinn`) — the DUT's black-box pin contract
(`sim/dut/README.md`) gives testbenches no access to internal nodes, so the
regenerative pair's own thermal/flicker noise sources cannot be
independently injected without editing `design/comparator.spice` (out of
this issue's scope). The injected density is itself the reduced sub-model's
input-referred white density, so the front-end term inherits that model's
own limits. The result is "the front end's own noise density, propagated
through the real regeneration dynamics and the real aperture" — materially
more complete than the AC bench's number, but **still a lower bound** on the
complete figure, not a certificate.

**The two numbers are consistent, and in the expected order.** The sigma
this bench reports is *larger* than `comparator-preamp-noise/`'s integrated
total, which is exactly what DR-0002's framing of that number as a
*reportable lower bound* predicts: the AC bench has both fewer noise sources
and a much narrower integration band. (An earlier draft of this bench
calibrated the injection to the AC bench's *total* instead of its density
and consequently reported a sigma several times *smaller* than the AC lower
bound — an inversion that is physically impossible for a strictly-more-
complete measurement, and the reason the calibration section above is as
emphatic as it is.)

## Retain, not retire: `comparator_dut_analog`

DR-0001 Consequence 2 named an open item: whether `comparator_dut_analog`
(the reduced sub-model `comparator-offset-mc/` and `comparator-preamp-noise/`
instantiate) stays a standing lower-bound check once a transient,
whole-latch path exists, or is retired. **Decision: RETAIN, not retire —**
made independently here because, at the time of writing, the sibling issue
(#23, the transient Monte-Carlo offset bench) that could otherwise have
settled this for the reduced sub-model in general is still open, so there is
no existing decision to defer to. This decision binds the **noise** row
only; #23 decides the offset row's half on its own evidence.

**Reasoning:**

1. **The AC bench is this bench's calibration input, not a redundant
   cross-check.** The injected density (36.27 nV/√Hz) comes directly from
   `comparator-preamp-noise/`'s own `white_nv_rthz`/`av_dc`. Retiring it
   would remove the number this bench is calibrated against — the transient
   bench cannot stand alone without it.
2. **The AC bench isolates a decomposition the transient bench cannot.**
   Because it excludes regeneration dynamics by construction, the AC number
   is unambiguously "front-end noise, corner-swept, nothing else" — a
   cleaner quantity for a future front-end sizing/optimization pass than a
   decision-boundary sigma that already has regeneration's own reshaping and
   aperture folded in. In particular it, not this bench, is where a
   per-corner noise **density** would come from if this bench is ever
   extended to re-derive the injection per corner.
3. **No cost to keeping it.** `sim/comparator-preamp-noise/`'s testbench,
   corners, and records are unmodified by this issue; retaining it costs
   nothing beyond what already exists, and DR-0002 already frames it as a
   *reportable lower bound*, not a claim of completeness — a framing this
   decision leaves intact.

## Debugging notes

- **`dout` must be read while `CLK` is still high.** The comparator's
  output stage (an SR latch) holds the decided value only during the
  evaluate phase; reading after `CLK` falls reads the **reset** value, not
  the held decision — confirmed empirically while developing this deck
  (an early version that sampled after the strobe read a constant value at
  every trial, which is what first surfaced the mistake, not a noise-
  injection failure).
- **Solver tolerances are looser than the other three benches'**
  (`reltol=1e-2`/`abstol=1e-12` here vs. `1e-4`/`1e-9`/`1e-13` there) —
  deliberately: this bench only needs a correct binary decision at a fixed
  readout instant, not sub-picosecond delay precision the way
  `comparator-regeneration/`'s τ extraction does, and looser tolerances
  materially cut the cost of the `N × 3-rung × 45-corner` transient-run grid
  this bench needs.
- **This bench is minutes-per-point, not seconds.** `N = 80` trials × 3
  rungs = 240 transient runs per PVT point; `sim/characterize.sh` documents
  the resulting exception to its "smoke is seconds" contract.

## Records

TBD-RECORDS

## Provenance

Novel to this repo — not ported from `gf180-comparator` or `sky130-sar-adc`.
`sim/comparator-regeneration/testbench/` supplied the harness-integration
shape (parallel comparator instances at different overdrives, driven off
one shared `CLK`, supply-normalized where relevant); the decision-statistics
/ probit-inversion methodology itself is this bench's own, developed against
the specific constraint that ngspice-46 has no PSS/pnoise and the DUT's
black-box contract gives no access to internal noise sources. Calibrated
against `sim/comparator-preamp-noise/`'s own committed white-noise density
rather than an independently-assumed noise level, so the two benches'
numbers are directly comparable rather than measuring different,
un-reconcilable things.
