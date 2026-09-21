# `sim/comparator-transient-noise/`

**Input-referred noise floor of the WHOLE comparator** (`comparator_dut`,
the real regenerative latch — **not** `comparator_dut_analog`), measured by
`ngspice` TRNOISE-injected **transient decision statistics** (a "hit-rate" /
probit measurement) over the full PVT grid.

Backs [`README.md`'s noise row](../../README.md#target-specification-draft--engineering-to-ratify)
via the **compliance evidence path** `CLAUDE.md` names — "the input-referred
noise floor from transient-noise runs with seeds and run counts committed".
`sim/comparator-preamp-noise/`'s `.noise` AC analysis remains a **reportable
lower bound**, not this row's compliance evidence; see "Retain, not retire"
below for why both benches stay committed side by side.

> **DR-0002 is proposed, not ratified, at the time this bench's evidence is
> committed.** [Issue #12](https://github.com/2AMLogic/sg13g2-comparator/issues/12)
> / [PR #18](https://github.com/2AMLogic/sg13g2-comparator/pull/18) — which
> would ratify the noise row's scoping, name transient noise as its
> compliance path, and demote the `.noise` number to a reportable lower
> bound — is **open** and deliberately held for a human
> (`loom:operator-only`). Everything below that cites DR-0002 cites a
> *proposal*. The requirement this bench actually answers to today is
> `CLAUDE.md`'s own, which is in force regardless. Consequently **nothing
> here is measured against a ratified bound**, and this bench files no new
> decision record: there is no ratified DR-0002 claim for it to contradict
> on physics grounds. What it does instead is hand DR-0002's eventual review
> a number the proposal currently has to leave blank — see "Implications for
> DR-0002's review" below, and `comparator-offset-transient-mc/`'s identical
> handling of the same situation one row over.

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

### Why white only (no 1/f term is injected)

`trnoise()` takes four arguments — `TRNOISE(NA TS NALPHA NAMP)` — and this
deck passes `NALPHA = NAMP = 0`. That is a decision, not an omission, and it
is quantified rather than asserted.

`comparator-preamp-noise/` attributes **11.28 % of its total noise power** to
flicker at the nominal corner (`flicker_frac_pct`) — but that share is stated
over *its own* 58.7 MHz band. The two terms rescale to a different band very
differently: white power grows **linearly** with the upper limit, 1/f power
only **logarithmically**. Carried to this bench's ~0.9 GHz decision aperture
("Implied aperture" below):

| term | scaling to ~0.9 GHz | power at nominal |
|---|---|---|
| white | × `9.2e8 / 5.87e7` = **15.7** | 1.07e−6 V² |
| flicker | × `ln(9.2e8) / ln(5.87e7)` = **1.15** | 1.0e−8 V² |

so flicker falls to **~0.9 % of the in-aperture noise power**, i.e. **~0.46 %
on σ** — roughly **1/28** of this bench's own ±13 % per-corner sampling error,
and far below the discrimination of any check here.

The physical argument lands in the same place from the other direction: 1/f
power that matters sits decades below a ~1 GHz aperture, so **within one 5 ns
strobe a flicker fluctuation is a static offset**, not decision noise. Offset
is budgeted by [`comparator-offset-mc/`](../comparator-offset-mc/) and
[`comparator-offset-transient-mc/`](../comparator-offset-transient-mc/), so
injecting 1/f here would double-count it into the noise row. Combined with
"mismatch is off" (the plain `mos` corner set), the division of labour is
explicit: **everything static within one strobe — device mismatch *and* 1/f —
belongs to the offset row; this bench measures only what varies
strobe-to-strobe.**

### TS-insensitivity cross-check

Because the calibration fixes the **density**, the measured sigma must not
depend on `TS` — the injected bandwidth is an artifact of the source, not of
the circuit. If the deck were in fact responding to the injected source's
*total* variance (which is `(2/3)·NA²`, i.e. **`TS`-independent**) rather
than to its density, halving `TS` at constant density would change the
answer by √2. So this is a real falsification test of the whole calibration,
not a formality. It was run:

| nominal point `tt_27c_1.20v`, `N = 80` | `NA` | `frac_high_zero` | `frac_high_plus` | `frac_high_minus` | slope `sigma` |
|---|---|---|---|---|---|
| `TS = 20 ps` (production) | 5.735e-3 | 0.4750 | 0.8500 | 0.2375 | **1.142 mV** |
| `TS = 10 ps` (cross-check) | 8.110e-3 | 0.4375 | 0.7875 | 0.1750 | **1.155 mV** |

**Agreement to 1.1 %**, against a ±13 % sampling error per point and the
√2 = 41 % shift the "responds to total variance" failure mode would have
produced. The calibration is measuring what it claims to measure.

This doubles as the **timestep-resolution check**, which is the other way
this bench could have been quietly wrong. Both runs use the deck's
`tran 20p 5.1n 0 20p` (max timestep 20 ps), so the cross-check run injects a
source whose knots are spaced *half* the max timestep — the most aliasing-
exposed configuration of the two — and still lands within 1.1 % of the
production run. That matches the analytic expectation: the source's
`sinc⁴(f·TS)` envelope has its first null at `1/TS`, and the only spectral
power that can fold below the latch's own ~1 GHz effective aperture
bandwidth (see "Records") comes from within a few percent of that null,
where `sinc⁴` has already collapsed. Resolving the *circuit* is what the
20 ps cap is really for, and 20 ps is ~2× finer than the fastest measured
regeneration time constant on this grid.

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
to an implied 1-sigma input-referred noise is a **post-hoc** step over the
committed record, not a deck measurement (`Φ⁻¹(p)` diverges as `p → 0` or
`1`; ngspice has no `Φ⁻¹` builtin at all and `let` has no clamp with which
the deck could guard the singularity).

That step is **executable, not prose** — every σ quoted in this file and in
the repo-root `README.md` is an output of
[`probit.py`](probit.py) run against a committed record:

```bash
python3 sim/comparator-transient-noise/probit.py \
        sim/comparator-transient-noise/records/<record-id>.json
```

It reads `od_x`/`vn_na`/`vn_ts` from `testbench/tb.json` (the harness's record
provenance carries the manifest's sha256, not its `params`) and **refuses** a
record whose `manifest_sha256` no longer matches that file — so a future
recalibration cannot leave an old aperture or an old `od_x` silently in
circulation.

**The estimator itself is tested, not trusted by inspection**, since it is
what converts this bench's raw evidence into the σ the repo-root `README.md`
quotes:

```bash
python3 sim/comparator-transient-noise/probit.py --selftest
```

It synthesizes hit rates *forward* from a chosen `(σ, θ)` — no sampling, so
the inversion must return the inputs to machine precision — and asserts the
slope estimator recovers σ and θ exactly at `θ = 0` **and** at `θ = ±150…300
µV`, that the per-rung diagnostics are biased in *opposite* directions there
(the claim below, stated as a check rather than as prose), that `Φ⁻¹`
round-trips `Φ` across the whole `p = 0.001…0.999` band, and that a saturated
rung *raises* instead of quietly returning σ = 0. It has teeth: swapping the
primary estimator for the per-rung form — the exact regression the section
below argues against — turns the `θ ≠ 0` cases red while the `θ = 0` case
still passes, which is precisely the failure signature that makes the
per-rung form look fine on a symmetric point.

Model the decision as a comparison of `(overdrive + noise)` against an
effective threshold `θ`, so `p(od) = Φ((od − θ)/σ)`. Two rungs at `±od_x`
then give two equations in two unknowns, and the **difference of the two
probits eliminates `θ` exactly**:

```
PRIMARY (two-rung slope; threshold-offset-immune):
  sigma = 2 * od_x / ( Phi^-1(frac_high_plus) - Phi^-1(frac_high_minus) )

SECONDARY (per-rung, reported only as a consistency check):
  sigma_plus  = od_x / Phi^-1(frac_high_plus)
  sigma_minus = od_x / Phi^-1(1 - frac_high_minus)

INCIDENTALLY RECOVERED (a diagnostic, not a spec number):
  theta = -(sigma/2) * ( Phi^-1(frac_high_plus) + Phi^-1(frac_high_minus) )
```

where `Φ⁻¹` is the standard normal inverse-CDF (probit function) and
`od_x = 1.0 mV`.

**Why the slope form is the primary one, and the per-rung form is not.**
The per-rung forms assume `θ = 0` exactly. Mismatch *is* off here (plain
`mos` corner set), so there is no device-mismatch offset — but `θ` is not
identically zero at `N = 80`: it absorbs both real residual asymmetry and,
much more importantly, the sampling fluctuation of that corner's own two
draws. The effect is not academic. At the nominal corner the two estimators
behave completely differently across two independent runs of the *same*
calibrated density (the `TS` cross-check below):

| run | `sigma_plus` | `sigma_minus` | **slope `sigma`** |
|---|---|---|---|
| `TS = 20 ps` (production calibration) | 0.965 mV | 1.400 mV | **1.142 mV** |
| `TS = 10 ps` (rescaled `NA`, same density) | 1.254 mV | 1.070 mV | **1.155 mV** |

The per-rung numbers swing by ±20–30 % and even swap which rung is larger;
the slope estimator reproduces to **1.1 %**. That is the whole argument: a
common-mode shift in the pair of hit rates is exactly what `θ` is, and the
slope form cancels it while the per-rung form converts it straight into
apparent noise. `sigma_plus`/`sigma_minus` are still worth reporting — their
*spread* is a live readout of how much of any one corner's number is
sampling scatter — but they are a diagnostic, not the measurement.

**Precision at `N = 80` is not a flat percentage.** The binomial standard
error on `frac_high` is ~5.6 % at `p = 0.5` (smaller at the tails), but it
propagates through `Φ⁻¹`'s derivative, which is steep near `p = 0.5` and
shallow in the `p ≈ 0.7–0.95` band `od_x` puts these rungs in. Propagating
both rungs through the slope form gives roughly **±13 % (1σ) of sampling
scatter on a single corner's** implied sigma — better than either per-rung
number, but still coarse. The **grid-wide mean across all 45 corners** is
the defensible summary statistic; no single corner's number should be quoted
as a corner-specific result, and the grid's min/max are sampling-dominated
extremes, not a measured PVT envelope.

### Implied aperture — an independent physical cross-check

The probit σ and the injected density together imply an **effective decision
noise bandwidth**, and that number is worth reading back out because it is
the one place this bench's answer can be checked against circuit physics
rather than against itself:

```
ENBW_implied = ( sigma / S_injected )^2          S_injected = 36.27 nV/√Hz
```

At the nominal corner σ ≈ 1.1 mV gives **ENBW ≈ 0.9 GHz**. A StrongARM latch
integrates its input noise onto the output capacitance during the
integration phase before regeneration takes over, so a first-order estimate
is `1/(4·t_int)` — landing ~0.9 GHz for `t_int` of a few hundred picoseconds,
which is the right order for this DUT's measured `τ` (42.6–167.3 ps across
the grid, [`comparator-regeneration/`](../comparator-regeneration/records/20260916-113309-180cca7.md))
and its 0.60–0.85 ns measured 50 mV decision time.

**This is a sanity check, not a measurement**: it is a single-pole
idealization of an aperture that is neither single-pole nor
time-invariant. Its value is falsification, not precision — an implied ENBW
of 60 MHz (the AC sub-model's own band, i.e. the density never saw the
latch's aperture at all) or of 25 GHz (the injected source's own `1/TS`
knot rate leaking through, i.e. the deck responding to the source instead of
the circuit) would each be a specific, diagnosable bug. Neither is what comes
out.

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
total, which is exactly what DR-0002's *proposed* framing of that number as a
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
whole-latch path exists, or is retired. **Decision: RETAIN, not retire.**

**This is not a re-litigation of the sibling decision — that one did not
cover this row.** The sibling issue (#23, the transient Monte-Carlo offset
bench) landed first ([PR #33](https://github.com/2AMLogic/sg13g2-comparator/pull/33))
and reached the same *retain* answer, but it
[scoped itself explicitly to the offset row](../comparator-offset-transient-mc/README.md#relationship-to-comparator-offset-mc)
— "the noise row's equivalent choice is out of scope — a separate future
issue, not #23". So the noise half was still open when this bench was
written, and is decided here. Its reasoning is also not merely #23's
reasoning restated: #23's decisive arguments were cost-per-point and
common-mode-axis coverage, neither of which applies to the noise pair; this
row's decisive argument (point 1 below) has no offset-row counterpart at all.

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
   nothing beyond what already exists, and DR-0002's proposal already frames
   it as a *reportable lower bound*, not a claim of completeness — a framing
   this decision leaves intact rather than needing to revise.

## Debugging notes

- **`dout` is read *inside* the evaluate phase (at 5 ns, with `CLK` falling
  at 5.1 ns) — and *not* because the output cannot be read later.** An
  earlier draft of this file asserted that reading after `CLK` falls returns
  the reset value rather than the held decision. **That is wrong, and is
  corrected here rather than carried forward.** Both the netlist and this
  repo's own committed evidence say the opposite:
  - *Netlist.* During reset (`CLK` low) `XM7`/`XM8` pull `ln`/`lp` to `VDD`,
    so the isolation inverters drive `lnb = lpb = 0` — which is exactly the
    **hold** input condition of the NOR SR pair (`doutb = NOR(lnb, dout)`,
    `dout = NOR(lpb, doutb)` degenerate to a cross-coupled inverter pair).
    Holding between strobes is the interface contract `sim/dut/README.md`
    states for `dout`/`doutb`, and the topology implements it.
  - *Committed measurement.* [`comparator-regeneration/`](../comparator-regeneration/)
    reads `dout` at **55 ns** against a `CLK` that fell at **50.1 ns** and
    requires the held value to be ≥ 0.9 of its own supply — passing at
    **45/45** PVT points on this same DUT
    ([record `20260916-113309-180cca7`](../comparator-regeneration/records/20260916-113309-180cca7.md)).

  The real reasons for the in-phase readout are narrower and both hold:
  (1) it samples the **regenerative decision itself** rather than the output
  latch's retention of it, which is the quantity this bench is about, and
  (2) it lets the transient stop at 5.1 ns instead of running past the
  falling edge and through the reset — worth having across
  `240 runs × 45 points`. Either readout would give the same answer; this one
  is cheaper and assumes less.
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

| record | DUT | grid | verdict |
|---|---|---|---|
| [`20260921-154729-41cbc7f`](records/20260921-154729-41cbc7f.md) | `comparator-dr0001` (**schematic**, `design/comparator.spice`) | 45/45, plain `mos` (no mismatch) × 3 T × 3 V | PASS |

All 45 points pass the manifest's three checks **and the record's corners
logs carry zero harness-surfaced warnings** (checked in the record's JSON
`points[].warnings`, not asserted — the sibling offset bench's one benign
`sf_mismatch_125c_1.32v` convergence warning has no counterpart here).
`frac_high_plus` never saturates anywhere on the grid: it spans
**0.6625 … 0.8875**, so every corner sits in the informative band where the
probit slope is resolvable — the failure mode the saturation-ceiling checks
exist to catch did not occur.

**Every σ this section quotes is [`probit.py`](probit.py)'s output against
this record** (`python3 sim/comparator-transient-noise/probit.py
sim/comparator-transient-noise/records/20260921-154729-41cbc7f.json`):

- **Slope σ (primary estimator)**: min **0.8890 mV** (`tt_27c_1.20v`) …
  max **2.7104 mV** (`tt_125c_1.08v`), **grid-wide mean 1.3346 mV** — the
  summary statistic this bench's own precision analysis directs the reader
  to (±13 % 1σ sampling scatter per corner at N=80; "Probit inversion").
- **Per-rung diagnostics** (`sig+_mV`/`sig-_mV`) drift from the slope value
  by ±15–40 % at typical corners and by half or more at the
  least-converged ones (e.g. `sf_-40c_1.20v`: `sig+` 2.3850 vs `sig−`
  0.9649 around a 1.3739 slope σ) — the documented live readout of
  corner-local sampling scatter, the exact behaviour the estimator
  comparison in "Probit inversion" predicts.
- **Implied aperture ENBW**: mean **1.437 GHz** across the grid — the
  independent physical cross-check ("Implied aperture") lands in the band
  this DUT's measured regeneration τ (42.6–167 ps, `comparator-regeneration/`)
  predicts, far from either named failure band (≈60 MHz: the density never
  seeing the latch's aperture; ≈25 GHz: the source's knot rate leaking
  through).
- **Zero-rung guard**: `frac_high_zero` spans **0.3375 … 0.6625**, mean
  **0.5078** — straddling 0.5 at both grid extremes, the in-record evidence
  that noise was genuinely injected at every corner ("Negative control").

**The honest outlier structure of the grid.** The three hottest,
lowest-supply corners carry the three largest slope σ — 2.7104 mV
(`tt_125c_1.08v`), 2.3795 mV (`ff_125c_1.08v`), 1.9058 mV
(`sf_125c_1.08v`) — and those same three corners are exactly where the
per-rung diagnostics pull farthest from the slope number (e.g.
`tt_125c_1.08v`: `sig+` 2.3851 vs `sig-` 3.1384, two rungs 32 % apart, which
the slope form cancels and the per-rung form converts into noise). That is
the signature of corners whose N=80 sample has not fully converged, sitting
on top of whatever real hot/low-supply PVT effect exists — not a clean
measurement of either. The grid mean is the defensible summary; per-corner
rank claims below the sampling floor are not supported at N=80.

## Implications for DR-0002's review

[DR-0002](../../spec/decision-records/) ([issue #12](https://github.com/2AMLogic/sg13g2-comparator/issues/12)
/ [PR #18](https://github.com/2AMLogic/sg13g2-comparator/pull/18)) proposes
ratifying the input-referred-noise row at **Target ≤ 1.0 mV rms, Stretch
≤ 0.6 mV rms**. This bench hands that proposal's eventual review the number
it currently has to leave blank — with three honest qualifiers governing how
it may be read:

1. **Nothing here contradicts a ratified bound, because none exists.** PR
   #18 is open and deliberately held for a human at the time this record is
   committed, so this bench files no new decision record — the constraint
   its own banner states. There is no ratified AR-anything for this
   measurement to contradict on physics grounds.
2. **The number exceeds the DRAFT row's Target — and it is still a lower
   bound.** The slope-σ grid mean is **1.335 mV** against the proposed
   1.0 mV Target (min 0.889 mV, max 2.710 mV), and the complete figure's
   regeneration-stage device noise is not even injected yet ("What this
   bench adds, and does not add"). The honest reading is therefore not
   "the spec fails"; it is that the draft Target was set when the only
   measurement was a 0.278 mV band-limited lower bound, and the first
   whole-latch compliance-path number comes out ~5× that lower bound — in
   exactly the direction DR-0002's own demotion of the AC number predicts
   for a strictly-more-complete measurement. Whether the row's numbers
   need re-derivation, the front end needs re-sizing, or the evidence
   chain needs the regeneration-noise injection closed before the row is
   judged is the conversation PR #18 exists to hold — now with real
   numbers on both sides. No sizing change is proposed or made here.
3. **The AC bench's number remains consistent, not contradictory.** The
   `.noise` lower bound (277.8 µV rms over its own 58.7 MHz band) is
   smaller than the whole-latch figure for the two structural reasons
   DR-0002's proposal already names (fewer noise sources, narrower
   integration band, multiplied by the white-only injection argument in
   "Why white only"). Ordering the two benches `278 µV < 1.335 mV` is
   expected; inverting them would have been the finding that required a
   physics re-examination.

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
