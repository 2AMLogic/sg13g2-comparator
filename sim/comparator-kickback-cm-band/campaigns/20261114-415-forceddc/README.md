# Forced-DC probe — series `20261114-415-forceddc` (issue #415)

**Supplementary characterization; no spec, window or DR-0004 change, no edit to
`20261011-165` or `20261108-405-probe`, no sigma, no pass for the Row 4b cell.**
This is the discriminating follow-up the #405 probe named and did not run: arms
that force a converged DC operating point (`.nodeset` / `.ic`, gmin/itl options).
Never merged into the #165 or #405 populations. Generated tables:
`comparison.md` / `comparison.json`
(`python3 sim/run_kickback_cm_band.py probe-compare --series 20261114-415-forceddc`).

## What ran

Exactly the two #165 rejects (`vcm-m050` ss/1.200 V/-40 C, `vcm-p050` ss/1.080 V/-40 C)
and the `vcm-nom` control at both PVT points, as `klt sim` requests submitted with
`--backend batch` and `batch.capacity_wait_s = 600`; client `klt 0.9.2.dev1029`
(accepted by the runner; no `*.unrun-*` refusals). Four arms per condition:

| arm | body vs #165 | cards / analysis | purpose |
|---|---|---|---|
| `repro` | byte-identical (checked at build) | #165, unchanged | reproduction gate |
| `obs` | byte-identical (checked at build) | + outputs over time + input differential at 1 ns / strobe | same-series baseline |
| `optdc` | + one `.options` block (below) | as `obs` | DC convergence aids only |
| `icdc` | + one `.nodeset`/`.ic` block (below) | as `obs` | forced DC operating point |

`repro`/`obs` keep the shared `kickback.body.spice` (byte-identical to the #165 body
of the same condition); the two arms that change the body reference per-arm body
files (`kickback-optdc.body.spice`, `kickback-icdc.body.spice`), because one
condition directory holds arms with different bodies and the shared file must stay
the #165 body.

### Body change against #165 (the whole diff)

`optdc` appends exactly (solver effort only; tolerances untouched, `gmin` pinned at
its 1e-12 default because the 1 GOhm / 1 pF floating network is sensitive to shunt
conductance; no `.nodeset`, no `.ic`, no analysis change):

```spice
.options itl1=500 gminsteps=500 srcsteps=500 gmin=1e-12
```

`icdc` appends exactly (values per condition; shown for `vcm-m050`, `vcm` = 0.55 V —
`vcm-nom` uses 0.6005/0.5995/0.65/0.55, `vcm-p050` uses 0.6505/0.6495/0.7/0.6):

```spice
.nodeset v(bpp)=0.5505 v(bpn)=0.5495 v(cpp)=0.6 v(cpn)=0.5
.ic v(douta)=0 v(doutb)=0 v(doutc)=0
```

`.nodeset` seeds the four floating DUT input pins at their analytic DC values (at DC
no current flows through `rfloat`, so `v(bpp)` must equal `v(bsp)` = `v(cm)` +
dv_small/2, and likewise for the other three); `.ic` states the SR latch's start
state. These are not interchangeable: the nodeset hints the DC solve, the `.ic`
states the latch output state. **No `uic` on the tran line** — the DC operating
point is still computed, which is what the "forced, stated initial condition" claim
needs. ngspice seeds (does not pin) both cards, and the bistable latch lands in the
seeded basin *when the solve converges*; the realized start state is therefore
re-read from evidence, not assumed — the committed `artifacts/*/ngspice.log` files
record both the homotopy outcome and the initial transient solution per corner.

### Forced output polarity, per point (do-not-beg-the-question statement)

At **all four points** every branch's non-inverting latch output is seeded to the
**LOW** rail (`.ic v(douta)=0 v(doutb)=0 v(doutc)=0`; 0 V is the one
supply-independent rail, which is why only `dout*` and not `dout*b` is seeded). LOW
is the **wrong polarity** for the programmed positive differential everywhere, and
it is the state the rejects already hold on their failing branch — so at the rejects
the seed changes nothing the bench was not already doing, and at the controls it is
a strict stress. **No arm forces any output toward the expected answer; an arm whose
outputs were forced toward the expected answer could not support a "bench artifact
confirmed" verdict, and none of these arms does that.** A 55 ns gate pass therefore
requires either a genuine post-strobe decision from the wrong state, or — if the
start state did not survive the DC solve — it shows exactly that, as below. The
engine logs of this series are committed (all 16 `artifacts/*/ngspice.log`, forced
past the repo-wide `*.log` ignore on purpose): they are the evidence for the
homotopy-outcome and initial-transient-solution claims below, which the envelopes
alone do not carry.

## Results per point

Floating-input differential `b_vd` (branch B, programmed 1 mV) and `c_vd`
(branch C, programmed 100 mV) at 1 ns and at the 30 ns strobe, the DC warning
state, and the decision gate (`min 0.9` on `dout_1k_end` / `dout_float_small_end`
/ `dout_float_big_end` at 55 ns). Full tables: `comparison.md`.

| point | arm | b_vd @1n / @strobe | c_vd @1n / @strobe | DC warning gone? | gate |
|---|---|---|---|---|---|
| m050 ss/1.200 V | `repro` | 23.5 µV / 23.6 µV | 2.353 mV / 2.356 mV | no (`Dynamic gmin stepping failed`) | **FAIL** (`dout_float_big_end` 6.8e-9) |
| m050 ss/1.200 V | `obs` | 23.5 µV / 23.6 µV | 2.353 mV / 2.356 mV | no | **FAIL** (same) |
| m050 ss/1.200 V | `optdc` | — no values — | — no values — | worse: hard abort, no op point | **ERROR** |
| m050 ss/1.200 V | `icdc` | 21.9 µV / 21.9 µV | 2.189 mV / 2.191 mV | no (all homotopies still fail) | **PASS** (all three = 1.0) |
| nom ss/1.080 V | `repro` | — | — | yes (clean) | PASS |
| nom ss/1.080 V | `obs` | 0.9996 mV / 0.9996 mV | 99.96 mV / 99.96 mV | yes | PASS |
| nom ss/1.080 V | `optdc` | — no values — | — no values — | worse: hard abort | **ERROR** |
| nom ss/1.080 V | `icdc` | 0.9996 mV / 0.9996 mV | 99.96 mV / 99.96 mV | yes | PASS |
| nom ss/1.200 V | `repro` | — | — | yes | PASS |
| nom ss/1.200 V | `obs` | 0.9993 mV / 0.9993 mV | 99.93 mV / 99.93 mV | yes | PASS (starts degenerate mid-rail, decides at strobe) |
| nom ss/1.200 V | `optdc` | — no values — | — no values — | worse: hard abort | **ERROR** |
| nom ss/1.200 V | `icdc` | 0.9993 mV / 0.9993 mV | 99.93 mV / 99.93 mV | yes | PASS |
| p050 ss/1.080 V | `repro` | 16.9 µV / 16.9 µV | 1.686 mV / 1.689 mV | no (`Dynamic gmin stepping failed`) | **FAIL** (`dout_float_small_end` 6.2e-9) |
| p050 ss/1.080 V | `obs` | 16.9 µV / 16.9 µV | 1.686 mV / 1.689 mV | no | **FAIL** (same) |
| p050 ss/1.080 V | `optdc` | — no values — | — no values — | worse: hard abort | **ERROR** |
| p050 ss/1.080 V | `icdc` | 21.4 µV / 21.5 µV | 2.144 mV / 2.147 mV | no (all homotopies still fail) | **PASS** (all three = 1.0) |

`repro` and `obs` equal the #165 envelope on every original card at all four
points (bit-for-bit): the reproduction gate passes in-series, and the extra cards
do not perturb the solution.

## What the arms show

**`optdc` is a clean negative result — and a warning.** The added solver budgets
did not converge anything: at all four corners (the two controls included, which
converge untouched without the options) ngspice's DC homotopies now hard-fail —
`spice3 gmin stepping failed`, then `Transient op failed, timestep too small`, no
operating point, transient aborted, every measurement valueless. The failure is
not a step-budget problem, and "help" options change which homotopy ngspice
attempts and can degrade corners that previously converged. Solver options are
not a fix for this bench.

**`icdc` at the controls: the latch genuinely decides.** The clean control solves
honor the seed — the committed `ngspice.log` initial transient solutions show
`douta = doutb = doutc = 0` at both supplies (`Dynamic gmin stepping completed`,
no warning) — and the strobe flips all branches to the correct HIGH answer by
55 ns from a healthy 0.9993-0.9996 mV / 99.93-99.96 mV differential. That is a
post-strobe decision overriding a stated wrong-polarity held state, at ss/1.080 V
and ss/1.200 V, -40 C: the latch can decide and override at these PVT points.

**`icdc` at the rejects: the gate passes, but not via a decision.** At both
rejects all three DC homotopies still fail (dynamic gmin, true gmin, source
stepping — quoted from the committed logs), the transient-op fallback picks its
own landing spot, and the initial transient solution has `doutb = 1.2` (m050;
`doutc = 1.2` at p050): the LOW seed is overridden and the bistable latch is
parked in the HIGH basin before the strobe. Outputs sit at the correct polarity
from 30 ns on; nothing transitions; the gate passes at 55 ns without the latch
deciding anything. The floating-input differential is **still collapsed ~46x**
(21.9 µV / 2.19 mV against the programmed 1 mV / 100 mV at m050; 21.4 µV /
2.14 mV at p050) — the `.nodeset` hint cannot make a failing solve accept the
analytic point.

## Conclusion: bench artifact confirmed (for the recorded rejects)

**The two recorded rejects are solver-state artifacts, not latch decisions, and
must not be counted as design rejections in the draft DR-0004 Row 4b record.**
The evidence, in order of strength:

1. **The 55 ns gate value at a reject is set by which basin the failing DC solve
   parks the bistable SR latch in, not by the latch.** Same bench, same corner,
   same collapsed differential: `repro` lands branch C (m050) / branch B (p050)
   in the LOW basin -> gate fail at ~1e-9; `icdc`, differing only in the solver's
   iterate path, lands the same branch HIGH -> gate pass at 1.0. A real decision
   margin cannot flip sign with the solver's landing spot.
2. **The strobe decision itself is demonstrated healthy at the same PVT supplies.**
   The controls (identical ss/-40 C supplies, seeded to the wrong state) decide
   correctly at the strobe at both 1.080 V and 1.200 V: the latch can override a
   wrong held state at these points, so "the latch cannot flip at cold/ss" is
   directly refuted.
3. **The bench's DC op is broken exactly at the reject corners, and the bench
   still does not deliver the programmed differential there** (~46x collapse,
   unchanged under `.nodeset`), while delivering it at the controls with the same
   1 GOhm / 1 pF network and the same supplies. The collapse tracks the failing
   solve (the input pair ends up conducting), not a property of the design.

**Residual open point, stated honestly:** at the reject common modes (0.55 V /
0.65 V) the forced-DC arm could not construct its own discriminating test — the
DC op still fails there even with the hints, so "the latch decides correctly at
vcm = 0.55/0.65 V if the bench delivered the programmed differential" is inferred
from the same-supply controls (only the common mode differs), not measured at the
reject common modes themselves. Closing that last gap needs a bench whose DC
operating point converges at those corners; fixing the bench was out of scope for
#405 and remains out of scope here. `optdc` shows solver options are not that fix.

## Run notes

- One batch job per arm; `environment.remote.job_id` per condition/arm:
  m050 repro klt-sim-b39258a6e962, obs klt-sim-a805d95f8511,
  optdc klt-sim-bc2bfd0d04b4, icdc klt-sim-d78d8f0da569; nom repro
  klt-sim-5d01ee6d2400, obs klt-sim-d6b8896434c1, optdc klt-sim-df4edae60f8c,
  icdc klt-sim-2fb9fc5912ec; p050 repro klt-sim-5d0ad2aae97e, obs
  klt-sim-81ad3d2d9811, optdc klt-sim-92ed59689de2, icdc klt-sim-4b615d1b0bf0.
  `state: failed` on reject/optdc rows is the envelope's reflection of the failed
  gate or aborted analysis, not a runner failure.
- Two submit passes raced once during collection; the duplicates were refused
  client-side by klt's artifact-dir lock (`outdir_locked`, exit 1) **before** any
  fleet submission — one refused attempt per optdc/icdc arm is kept in
  `attempts.jsonl`, and no arm has more than one fleet job.
- `equals_165_on_original_cards` is `True` by construction only for `repro`/`obs`
  (byte-identical body); `optdc` produced no values and `icdc` legitimately
  differs on the gate cards (that difference is the experiment).
- The `xing`-style "no crossing" precedent (#405) does not arise here: no arm
  carries crossing cards.
