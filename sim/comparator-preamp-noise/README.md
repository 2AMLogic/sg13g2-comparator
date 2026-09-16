# `sim/comparator-preamp-noise/`

**Input-referred noise** of the comparator front end over the full PVT grid,
via ngspice `.noise`, reported as **total integrated output noise divided by
the measured DC gain**.

Backs [`README.md`'s noise row](../../README.md#target-specification-draft--engineering-to-ratify)
(≤ 1.0 mV rms differential, ≤ 0.6 mV stretch) and, together with
`sim/comparator-regeneration/`'s τ, the noise-floor half of the metastability
story.

> **`provenance: schematic` records here are a LOWER BOUND, not the design's
> real noise floor.** The chosen topology
> ([DR-0001](../../spec/decision-records/0001-comparator-topology.md)) has
> no DC-resolvable analog front end, so `comparator_dut_analog` (what this
> bench instantiates) is a diode-connected, loop-broken reduced sub-model —
> it excludes the regenerative loop's own noise contribution entirely. See
> [`design/README.md`](../../design/README.md) before quoting any number
> below.

```bash
python3 sim/run_corners.py comparator-preamp-noise -j 8
```

## Method

One `op`, two `.noise` runs (1 Hz–1 GHz and 1 kHz–1 GHz) and one `.ac`, per
PVT point.

**The quoted number is `onoise_total / A_v(DC)`, not ngspice's own
`inoise_total`.** That is the whole reason this bench was worth porting: the
methodology's own upstream (`gf180-sar-adc`, via `gf180-comparator`) documents
a prior **200× magnitude error** from reporting `sqrt(onoise_total)` directly
as the answer. Both referrals are in the record side by side:

| measurement | what it is |
|---|---|
| `vn_in_uv` | **the quoted number** — integrated output noise ÷ measured DC gain |
| `inoise_band_uv` | ngspice's own input referral over the same band |

**They are not expected to agree, and the record shows why.** ngspice refers
each frequency bin through the AC transfer function *at that frequency*, so
every bin above the front end's bandwidth is divided by a rolled-off gain and
inflates the total. Keeping both makes the divergence an explained property
of two referrals rather than an unexplained factor somebody rediscovers
later — which is precisely what the upstream 200× error was.

**Total integrated noise, not a density.** A comparator *samples* its input
noise at the decision instant rather than filtering it, so the band-limited
total is the relevant quantity. That is why the integration runs to 1 GHz
rather than to some assumed signal bandwidth, and why `enbw_mhz` is reported
so a reader can re-derive the total by hand as (density × √ENBW).

**The two-band split is the flicker story.** `vn_in_hf_uv` integrates from
1 kHz up; `flicker_frac_pct` is the sub-kHz share of the noise *power*.
Sub-kHz noise drifts slowly enough to behave as an offset rather than as
per-decision noise, so keeping the split visible is what lets a reader
separate the two. PSP103's own flicker-noise coefficients are used
as-shipped (no override), and the flicker fraction is what a reader rescales
to see whether the worst-case setting would change any verdict.

**The decision stage is instantiated, with its clock held low.** It draws no
current in reset, but its input capacitance is part of the load that sets the
front end's noise bandwidth. Omitting it would over-state the bandwidth and
therefore *over*-state the noise; replacing it with an invented lumped
capacitor would make the answer depend on the invention.

## What this bench cannot reach

`.noise` is a small-signal analysis about a DC operating point. A
reset-and-regenerate decision stage has none, and ngspice offers no
PSS/pnoise and no automatic device-level transient noise. So the decision
stage's own noise is **not in this record** and is not claimed. Referred to
the comparator input it is divided by the gain measured here, which is why
the front end is where a noise budget gets closed. See
[`sim/dut/README.md`](../dut/README.md) for what happens to this bench if the
ratified topology turns out to have no DC-resolvable front end at all — that
is a named consequence for the topology decision to weigh, not a gap to paper
over.

## Provenance

Methodology ported from
[`gf180-comparator/sim/comparator-preamp-noise/`](https://github.com/2AMLogic/gf180-comparator/tree/main/sim/comparator-preamp-noise)
(itself ported from `gf180-sar-adc`), per
[`spec/porting-plan.md`](../../spec/porting-plan.md) and issue #8.

**Ported, unchanged:** the divide-integrated-output-noise-by-measured-DC-gain
methodology and the units caution behind it; the two-band (full / >1 kHz)
split and its flicker-as-slow-offset rationale; instantiating the decision
stage in reset for its loading; reporting ENBW and the white density so the
integral can be checked by hand. Nothing in the testbench fragment names a
PDK-specific device or switch (`sim/harness/testbench.py`'s module docstring
notes the same for the module that loads it), so this bench needed no
structural adaptation for SG13G2 beyond running against `sg13_lv_nmos`
through the DUT netlist and the SG13G2 corner grid (`sim/harness/README.md`'s
divergence table).

**Deliberately NOT ported:**

- **The topology and its sizing**, and any upstream numeric result.
- **The 10-µs-conversion / ten-bit-trial argument** for which noise is
  correlated across decisions. That is a SAR sequencing property; a
  standalone comparator has no conversion to span, so the flicker split is
  reported as a property of the block and the correlation argument is left to
  whoever integrates it.
- **`.nodeset` operating-point hints.** This bench converges without one, and
  a hint that is not needed is a hidden dependency on a guess.
- **The `av_dc`/`f3db` pair's specific numeric bounds**, which are upstream's.
  `av_dc` is kept, but as a *sensitivity anchor* with a unity floor rather
  than as a gain specification.

## Records

| record | DUT | grid | verdict |
|---|---|---|---|
| [`20260910-232822-8148438`](records/20260910-232822-8148438.md) | `placeholder-v1` (**placeholder**) | 45/45, `mos` × 3 T × 3 V | PASS |
| [`20260916-021939-36773c7`](records/20260916-021939-36773c7.md) | `comparator-dr0001` (**schematic**, `design/comparator.spice`) | 45/45, `mos` × 3 T × 3 V | **FAIL** (`av_dc` process-axis floor only — recalibrated below, issue #16) |
| [`20260916-113303-180cca7`](records/20260916-113303-180cca7.md) | `comparator-dr0001` (**schematic**, `design/comparator.spice`) | 45/45, `mos` × 3 T × 3 V | PASS (post-recalibration, issue #16 — see below) |

**Read the banner on that record.** It was taken against the placeholder DUT
and substantiates the harness, not the noise row. It is also the record the
`av_dc` per-axis floors were originally calibrated from (observed weakest
slices: process 5.89 %, temperature 38.91 %).

### `av_dc` process-axis floor: RECALIBRATED against the real DUT (issue #16)

`design/README.md`'s "Open items" section previously documented that this
bench's `av_dc` process-axis floor (`>= 3.0 %`, calibrated against the
placeholder record above) FAILed against `20260916-021939-36773c7`'s
observed weakest process slice (`1.07 %`) — a real measured property of the
real design's front end, not a harness defect: `comparator_dut_analog`'s DC
gain is a `gm`-ratio between the input pair and its diode-connected loads
(see the `provenance: schematic` note at the top of this file), which
partly cancels process skew to first order, unlike the placeholder's
ideal-resistor-loaded front end. Per this repo's "do not relax a check to
make a result pass" rule, that FAIL was left committed as-is (append-only)
rather than silently patched, and the floor has now been recalibrated with
margin below the real DUT's own observed value — not loosened to make the
old record retroactively pass. The new floor (`>= 0.5 %`, ~53 % margin
below the observed `1.069 %`) is calibrated from `20260916-021939-36773c7`
(`testbench/tb.json`'s `av_dc` check comment carries the full citation) and
is confirmed by the fresh `20260916-113303-180cca7` record above — a
clean-tree (`dirty: false`) run taken *after* the recalibrated `tb.json` was
committed, so it is citable under `sim/README.md`'s "Record format" rule —
which PASSes against it. The temperature-axis floor (`>= 20.0 %`) is unchanged —
it still holds against the real DUT's own weakest observed temperature
slice (`21.06 %`).
