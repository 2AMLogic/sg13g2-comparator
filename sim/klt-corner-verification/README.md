# `klt-corner-verification/`: DR-0002 graded on `klt sim` corner envelopes (T1 item 5)

Issue [#62](https://github.com/2AMLogic/sg13g2-comparator/issues/62). This
directory re-measures every row of the ratified spec
([DR-0002](../../spec/decision-records/0002-target-spec-ratification.md))
on the **schematic DUT** (`design/comparator.spice`, bound by
`sim/dut.json`, `provenance: schematic`). Each bench is a `klt sim`
corner-matrix request over the full ratified grid: process
{tt, ff, ss, fs, sf} × {1.08, 1.20, 1.32} V × {−40, 27, 125} °C, 45 points.
`sim/kltsim/grade.py` then grades every row and sub-bound literally against
DR-0002.

It is a **new, separate evidence trail** in `klt`'s own envelope format. It
does not relabel, convert or replace the six harness experiments in `sim/`
(their records are untouched, and `sim/` is append-only). Where this
campaign and a DR-0002 record measure the same thing, both numbers are
shown below.

## Verdict (campaign `20261009-d73a9ac`)

**T1 item 5 is NOT met.** Two ratified Targets fail on numerical evidence:
the noise row (2) and the kickback charge clause (4a). Every other bounded
Target passes, and the full grid is covered by all four benches. Full table:
[`campaigns/20261009-d73a9ac/grading.md`](campaigns/20261009-d73a9ac/grading.md)
(machine form: `grading.json`).

| Row | Sub-bound | Target | Stretch | Measured on klt sim (45/45 points valid) | Binding point | DR-0002 record, for comparison |
|---|---|---|---|---|---|---|
| 1 | offset 3σ, every point | ≤ 15 mV **PASS** | ≤ 8 mV **FAIL** (40/45) | 6.91 … 12.09 mV | `ff_125c_1.08v` | 7.46 … 10.54 mV, Stretch missed 27/45 (see "Offset reads 13 % high") |
| 2 | input-referred noise, grid-wide mean of per-point σ | ≤ 1.0 mV rms **FAIL** | ≤ 0.6 mV rms **FAIL** | grid mean **1.289 mV**; per point 0.846 … 1.843 mV | grid-wide mean (DR-designated statistic); worst point `ff_125c_1.08v` | grid mean 1.335 mV (0.889 … 2.710), NOT MET |
| 3a | decision time @ 50 mV | ≤ 1.5 ns **PASS** | ≤ 0.8 ns **FAIL** (9/45, every `ss`) | 0.597 … 0.850 ns | `ss_125c_1.32v` | identical: 0.596 … 0.850 ns |
| 3b | regeneration τ | ≤ 250 ps **PASS** | not specified | 42.6 … 167.3 ps | `ss_-40c_1.08v` | identical |
| 3c | decision time @ 0.1 mV | ≤ 2.0 ns **PASS** | not specified | 0.910 … 1.662 ns | `ss_-40c_1.08v` | identical |
| 4a | peak injected charge Q_kick per side, branch A | ≤ 25 fC **FAIL** (39/45) | ≤ 8 fC **FAIL** (45/45) | **23.58 … 31.46 fC** (direct) | `ff_125c_1.32v` | not measured; estimated 8.8 … 14.3 fC with a 1.3 … 2.9× under-reporting bias, "CONSISTENT, NOT CERTIFIED" |
| 4b | signal-dependent residue, 1 GΩ / 1 pF | ≤ 100 µV **PASS** | ≤ 30 µV **PASS** | 2.03 … 15.63 µV | `ss_-40c_1.08v` | 1.70 … 15.40 µV |
| 4c | peak excursion into 1 kΩ / 100 fF (reporting only) | not specified (REPORTED) | not specified | 87.7 … 143.3 mV | — | identical |
| 5a | supply 1.2 V ±10 %, −40 … 125 °C exercised | **PASS** (full grid, all 4 benches, supply/temperature verified as applied) | not specified | — | — | exercised |
| 5b | average power @ 33.3 MHz incl. bias branch | **not specified** (DR-0002 ratifies no Target) | ≤ 20 µW **FAIL** (45/45) | 27.90 … 38.78 µW (full 30 ns cycle) | `ff_125c_1.32v` | 22.9 … 29.5 µW (see "Power reads higher") |

How the verdicts are kept apart (`sim/kltsim/grade.py`):

- **FAIL** means at least one trustworthy value violates the bound. For Row 2,
  the bound is on the grid-wide mean, so FAIL means the mean violates it.
- **INCOMPLETE** means no violation was seen, but the grid is not fully or
  validly covered. Causes include a missing or errored corner, a failed
  decision gate, a supply or temperature probe that disagrees with its corner,
  a Monte-Carlo population short of the ratified N, zero spread, duplicated
  noise draws, or a saturated probit rung. INCOMPLETE is never PASS.
- **NOT SPECIFIED** means DR-0002 ratifies no bound in that column.
- A harness sanity envelope is never used as a spec verdict.

## The citation `klt signoff` sees

`klt signoff` accepts a single `sim` envelope for item 5, and it marks the
item passed only when that one envelope's own `status` is `pass`. The
envelopes here encode **only DR-0002 Target bounds and validity gates** as
`limits`. Stretch bounds are deliberately not encoded, so an envelope's own
status is the Target verdict of the rows it carries. Two consequences follow:

- `manifests/sg13g2-comparator.json` cites
  [`campaigns/20261009-d73a9ac/kickback.envelope.json`](campaigns/20261009-d73a9ac/kickback.envelope.json).
  Its own status is `fail` (39/45 corners over the 25 fC Q_kick Target), and
  the grader renders item 5 `unmet` / `check_failed`. Citing the passing
  regeneration envelope instead would have rendered item 5 **met** on one
  row's evidence, which is a false claim.
- The Row 1 and Row 2 statistics are caller-side reductions of klt's
  per-corner Monte-Carlo moments. Their envelopes' `status` reflects only
  per-sample gates and limits, never the row verdict. They therefore must
  never be cited as item 5 passes. See
  [klayout-tools#2960](https://github.com/2AMLogic/klayout-tools/issues/2960):
  only a pooled mean ± kσ window is gradeable, so a per-corner population
  statistic or a statistic over two measurements cannot be expressed.

## Layout

```
rows.json                     DR-0002 row/sub-bound inventory: bounds, units, conditions and
                              statistical basis COPIED from the DR; the evidence mapping per sub-bound
benches/*.circuit.spice       bench circuits, each a port of one sim/comparator-*/ testbench
                              (header of each: what changed and why)
campaigns/<id>/
  <bench>.body.spice          generated netlist body: OSDI pre-load + DUT inlined verbatim with its
                              sha256 + circuit. Its hash is the envelope's provenance.input.content_hash
  <tag>.request.json          the exact klt sim request submitted (backend: batch)
  <tag>.envelope.json         klt sim's JSON output, byte for byte as printed
  <tag>.invocation.json       command, cwd, klt version, request/envelope sha256, start/finish, exit
  attempts.jsonl              every submission, including refusals at the fleet's instance cap and one
                              abandoned attempt (below)
  artifacts/<tag>/<corner>/   per-corner (per-sample) generated deck and raw ngspice.log, as returned
  grading.json / grading.md   generated by `grade`
  smoke/                      fleet smoke and verification runs (reduced grids; never graded)
```

Sibling code: `sim/kltsim/` (`benches.py` defines the measurements,
`build.py` composes bodies and requests, `grade.py` holds the rules,
`cli.py` is the driver, `tests/` holds the rules' regression tests) and
`sim/run_klt_corner_verification.py` (entry point).

## Reproducing

From the repository root, with the **CI-pinned** klt. The host's own `klt`
may be a different build, so install the pin into a throwaway venv:

```bash
python3 -m venv .venv
.venv/bin/pip install "klayout-tools @ git+https://github.com/2AMLogic/klayout-tools@e8ca621a6961879cec1af60cc932c3b3d58ddcaa"
export KLT_SIM_BACKEND=batch   # the requests say backend: batch anyway

python3 sim/run_klt_corner_verification.py build --campaign <new-id>    # bodies + requests
python3 sim/run_klt_corner_verification.py run   --campaign <new-id> --bench regeneration --klt .venv/bin/klt
python3 sim/run_klt_corner_verification.py run   --campaign <new-id> --bench kickback     --klt .venv/bin/klt
python3 sim/run_klt_corner_verification.py run   --campaign <new-id> --bench offset_mc    --klt .venv/bin/klt --retry-refused 30 --retry-wait 60
python3 sim/run_klt_corner_verification.py run   --campaign <new-id> --bench transient_noise --klt .venv/bin/klt --retry-refused 30 --retry-wait 60
python3 sim/run_klt_corner_verification.py grade --campaign <new-id>
```

Re-grading the committed campaign needs no simulator:
`python3 sim/run_klt_corner_verification.py grade --campaign 20261009-d73a9ac`.
Rules tests (stdlib only, also run in CI and in `sim/selftest.sh`):
`PYTHONPATH=sim python3 -m unittest discover -t sim -s sim/kltsim/tests -p 'test_*.py'`.

Evidence is append-only. `run` refuses to overwrite an existing envelope, so
a re-run uses a **new** campaign id. The Monte-Carlo benches are split into
one request per process corner, so each fits one batch job and can be retried
on its own.

### Toolchain and provenance actually used

| | |
|---|---|
| klt (client and batch runner) | `0.5.0+ge8ca621a6961`, the CI pin (`envelope.provenance.klt_version`) |
| engine | ngspice 46 on the batch runner image (`environment.engine_version`) |
| models | `cornerMOSlv.lib` sha256 `03d50584…5d67` on the runner, **byte-identical** to this repo's pinned IHP-Open-PDK 0.3.0 install (`sim/pdk.json`). klt hashes only the top-level corner library, not the files it includes. |
| OSDI | PSP103 / PSP103-NQS / r3_cmc / mosvar, `pre_osdi`-loaded from the runner image's `/opt/pdk/ihp-sg13g2/libs.tech/ngspice/osdi/` by a `.control` block inside each body. The pinned klt has no `osdi_preload` field; see `sim/kltsim/build.py` and klayout-tools#2666. |
| DUT | `design/comparator.spice` sha256 `b31b936d…`, inlined verbatim. The grader re-derives it from each committed body and refuses a body whose DUT is not today's schematic, or whose hash is not the envelope's `provenance.input.content_hash`. |
| batch jobs | one per envelope, with job id, instance and spot lifecycle in `environment.remote` (listed in `grading.md`) |

## Benches, and what each one changes from its source

All four benches keep their source's circuit element for element. Every
bench makes the same forced change: klt sim sweeps supply with
`alter vsup=<V>`, which does not reach a `.param`'d pulse amplitude, so the
strobe is a unit pulse scaled by the live supply node. Every bench also adds
corner-application probes, `v(vdd)` and a `temper` B-source. The grader
refuses any corner whose probes disagree with the supply or temperature the
corner claims.

- **`regeneration`** (from `comparator-regeneration/`) covers Rows 3 and 5.
  It reproduces DR-0002's Row 3 numbers to four digits at all 45 points,
  which is the strongest check that the port and the corner application are
  right. It adds `p_avg_uw`, the average supply power over the full
  30 … 60 ns cycle on instance A's own supply, core plus its `dut_ib`
  reference branch.
- **`kickback`** (from `comparator-kickback/`) covers Row 4. It adds the
  direct **Q_kick** measurement that DR-0002 names as an open item: 0 V
  ammeters at both branch-A DUT input pins, each pin current integrated onto
  1 pF, and Q_kick = max over 30 … 45 ns of |q(t) − q(29 ns)|, per side, worst
  side graded. Pin current is the capacitor displacement plus the restoring
  resistor current, so source restoration is included and opposite lobes
  cannot cancel. **Validation done:** at the binding corner (`ff_125c_1.32v`)
  a 1 ps max-step re-run moves Q_kick by +0.03 % (31.46 → 31.47 fC), and both
  sides exceed 25 fC on their own (30.87 / 31.46 fC). The re-run is
  `smoke/kickback-timestep-ff-1p32-125.*`, run under the campaign's same
  `reltol=1e-4`. The direct value is 2.2× the DR's peak-voltage × C_in
  estimate (14.3 fC), inside the 1.3 … 2.9× bias DR-0002 derived for that
  estimator. **Known-charge fixture (done, issue
  [#78](https://github.com/2AMLogic/sg13g2-comparator/issues/78)):** the
  same instrument block, driven by ideal currents of analytic charge, reads
  back to within 0.0002 fC, including a zero-net bipolar case; see
  [Q_kick instrument validation](#q_kick-instrument-validation-issue-78). The
  tiny residue (4b) moved 7 % at that corner under the tighter step
  (2.28 → 2.12 µV), which is 40× under its bound.
- **`offset_mc`** (from `comparator-offset-transient-mc/`) covers Row 1. One
  mismatch draw per klt Monte-Carlo sample on the `mos_<p>_mismatch`
  sections, N = 60 per point, base seed 20260916, a per-draw range gate
  (offset strictly inside the swept ±48 mV staircase), and the ratified
  statistic 3·√(s²·(N−1)/N − step²/12) computed from klt's per-corner σ. A
  smoke negative control (`smoke/offset_mc-mismatch-vs-negctrl.*`) shows
  σ = 4.24 mV on `mos_tt_mismatch` and exactly 0 on plain `mos_tt` with the
  same seeds, and the grader treats zero spread as sabotage. klt's own pooled
  mean ± 3σ window (a stricter statistic) passes at all 45 points as well,
  but it is reported only.
- **`transient_noise`** (from `comparator-transient-noise/`) covers Row 2.
  The density (36.27 nV/√Hz, `vn_na = 5.735e-3`, `vn_ts = 20 ps`), the
  ±1 mV and 0 rungs, the 5 ns read and mismatch off are all unchanged. The
  original ran 80 trials in one process via `reset`. Here each klt
  Monte-Carlo sample is one trial, N = 80 per point, and klt's per-corner
  mean of a 0/1 outcome probe is the hit fraction. `grade.py` computes the
  DR-designated statistic from those means: the per-point two-rung probit
  slope σ = 2·od / (Φ⁻¹(p+) − Φ⁻¹(p−)), then the grid-wide mean. The
  zero-overdrive rung is the noise-injection guard; its fractions land in
  0.400 … 0.575 at every point, inside the original's 0.1 … 0.9 check.

## Q_kick instrument validation (issue #78)

Evidence is under
[`campaigns/20261009-issue78/`](campaigns/20261009-issue78/), appended beside
the campaign (nothing under `20261009-d73a9ac/` was touched). Client: the
CI-pinned klt `0.5.0+ge8ca621a6961`.

**Known-charge fixture.**
[`benches/kickback_fixture.circuit.spice`](benches/kickback_fixture.circuit.spice)
drives the kickback bench's own ammeter + 1 pF integrator block (and the
1 kohm / 100 fF source network) from ideal PWL currents of analytic charge,
with no DUT. The measure strings come from the same template as the real
bench (`qkick_measurements` in `sim/kltsim/benches.py`; a unit test pins
both to the strings in the submitted campaign request). One unit, local
backend; `python3 sim/run_klt_corner_verification.py fixture --campaign <id>`.

| case | injected | expected Q | measured Q | expected net v(q) | measured net v(q) |
|---|---|---|---|---|---|
| a | +10 fC at 33 ns, with +7 fC at 20 ns (before the 29 ns reference) and +4 fC at 50 ns (after the window) | 10 fC | 9.9999 fC | -10 fC | -9.9998 fC |
| b | -10 fC at 33 ns | 10 fC | 10.0000 fC | +10 fC | +9.9999 fC |
| c | **bipolar** +20 fC (31 ... 36 ns) then -20 fC (38 ... 43 ns) | 20 fC | 19.9999 fC | 0 fC | +0.0001 fC |
| d | +10 fC as 1 uA for 10 ns into the restoring 1 kohm / 100 fF node | 10 fC | 10.0000 fC | -10 fC | -9.9999 fC |

Tolerance 0.02 fC (200x looser than the observed error). Case c has zero
net charge and a 20 fC peak: the deliberately wrong end-of-window estimator
|q(45 ns) - q(29 ns)| reads 0.0001 fC there and fails, and the instrument
does not, so the instrument measures the peak and not the net. Case d: peak
node volts x C_in reads 0.1000 fC for the 10 fC actually delivered, because the
source resistor restores the node while the pulse is on; the instrument reads
the full 10 fC. Case a shows the 29 ns reference and the 45 ns window edge
are enforced (a reference at 19 ns or a window to 60 ns would give 17 fC /
14 fC; checked in the unit test). Full table and per-case signed values:
[`fixture/kickback_fixture.check.md`](campaigns/20261009-issue78/fixture/kickback_fixture.check.md).

**Sign convention correction.** The fixture shows that charge pushed INTO the
pin node makes v(q) FALL (the ammeter's positive terminal is the source
network side, so i(vk) < 0 for that direction). The header of
`benches/kickback.circuit.spice` says v(q) rises; it was left unedited
because the submitted campaign bodies embed that file's hash. The sign never
enters the graded number, which is an absolute value.

**Decisions unchanged.** One-corner A/B at `mos_tt / 1.2 V / 27 C` on the
batch fleet (this host's ngspice 42 cannot load the PDK's OSDI v0.4 models):
the bench with and without the ammeters and integrators
([`ab/ab.json`](campaigns/20261009-issue78/ab/ab.json); jobs
`klt-sim-664f084f5cc4` with, `klt-sim-ee516621175d` without). `dout_1k_end`,
`dout_float_small_end` and `dout_float_big_end` are 1.0 in both arms,
bit-identical; the branch-A peak excursion differs by 0.02 mV of 115.8 mV
(0.02 %), the same order as the timestep convergence figure.

**Timestep convergence.** Not redone: the fixture found no defect. See the
`smoke/kickback-timestep-ff-1p32-125.*` re-run cited above (+0.03 %).

**Harness bench.** Not ported: `sim/comparator-kickback/testbench/` stays as
the historical harness measurement (its README now points here). A `checks:`
entry of 25 fC would turn that bench red at 39/45 points, which is the honest
result already recorded here; the harness runs on the host's ngspice, which
cannot load the PDK's OSDI models, so a port could not be validated locally,
and a second grid would duplicate this campaign. The 45-point Q_kick result
remains `20261009-d73a9ac`; 4a is still **NOT MET** (binding `ff_125c_1.32v`,
30.87 / 31.46 fC per side). No bound, DUT or decision record was changed.

## Bias-point sweep of `dut_ib` (issue #80)

Issue [#80](https://github.com/2AMLogic/sg13g2-comparator/issues/80).
DR-0002 ratifies no Target-column power bound (Row 5), and its Open items
ask for a bias-point sizing study to found one. This sweep supplies that
evidence. It **proposes no bound** and changes no spec row, no DUT and not
`sim/dut.json` (its default stays `dut_ib` = 20 µA). A follow-up decision
record, filed separately, would use this table as its basis.

Evidence is under
[`campaigns/20261009-issue80/`](campaigns/20261009-issue80/). Each
`ib_<X>uA/` subdirectory is a normal campaign directory (bodies, requests,
envelopes, invocations, `attempts.jsonl`, per-corner `artifacts/` with deck
and `ngspice.log`). Nothing under `20261009-d73a9ac/` was touched. The
generated table is
[`ibsweep.md`](campaigns/20261009-issue80/ibsweep.md) (machine form:
`ibsweep.json`). Client: the CI-pinned klt `0.5.0+ge8ca621a6961`, batch
backend.

**What changes between bias points.** Only the emitted `.param dut_ib=…`
line in each body changes. Each body's header states the override (`OVERRIDE
(issue #80 sweep; sim/dut.json untouched): dut_ib=…`), and the override is
part of the hashed netlist that each envelope's
`provenance.input.content_hash` covers. The DUT is inlined byte for byte as
in the issue #62 campaign. The tail current is 4 × `dut_ib`, set by the fixed
4:1 mirror (`XMB` 10u/0.5u → `XMT` 40u/0.5u). Tail width was not swept.

**Coverage.**

- **Regeneration bench** (Rows 3a/3b/3c and 5b): seven values, `dut_ib` ∈
  {2.5, 5, 7.5, 10, 15, 20, 40} µA, each a full 45-point `klt sim` corner
  request with 45/45 points valid. At 20 µA every measurement matches the issue
  #62 envelope exactly at all 45 points. The bodies differ only by the
  override header and the two added probes.
- **Monte-Carlo benches** (Row 1 offset, N = 60, and Row 2 noise, N = 80
  per rung): run only for the two best candidate currents below the
  baseline, 15 µA and 10 µA, as the issue specifies. At 20 µA they are taken
  from campaign `20261009-d73a9ac`, whose bodies were built with the same
  `dut_ib` = 20 µA, so they already are the 20 µA measurement.
- **Not swept:** kickback (Row 4) was not run at any bias.

| `dut_ib` (µA) | 3a t_d @ 50 mV ≤ 1.5 ns | 3b τ ≤ 250 ps | 3c t_d @ 0.1 mV ≤ 2.0 ns | 1 offset 3σ ≤ 15 mV | 2 noise grid mean ≤ 1.0 mV | 5b power, worst point (no Target; Stretch ≤ 20 µW) |
|---|---|---|---|---|---|---|
| 2.5 | 2.564 ns FAIL | 389.6 ps FAIL | 4.357 ns FAIL | not swept | not swept | 18.69 µW |
| 5 | 1.764 ns FAIL | 255.5 ps FAIL | 3.025 ns FAIL | not swept | not swept | 20.58 µW |
| 7.5 | 1.416 ns PASS | 210.2 ps PASS | 2.474 ns FAIL (9/45) | not swept | not swept | 23.27 µW |
| 10 | 1.212 ns PASS | 190.2 ps PASS | 2.169 ns FAIL (2/45) | 11.31 mV PASS | 1.074 mV FAIL | 26.22 µW |
| 15 | 0.984 ns PASS | 173.8 ps PASS | 1.838 ns PASS | 11.89 mV **INCOMPLETE** (44/45; see below) | 1.238 mV FAIL | 32.41 µW |
| 20 (baseline) | 0.850 ns PASS | 167.3 ps PASS | 1.662 ns PASS | 12.09 mV PASS | 1.289 mV FAIL | 38.78 µW |
| 40 | 0.637 ns PASS | 160.3 ps PASS | 1.389 ns PASS | not swept | not swept | 64.75 µW |

Worst PVT point of 45 throughout, except Row 2, which is the DR-designated
grid-wide mean. Read the table as follows:

- **No swept value meets every ratified Target.** Row 2 (noise) fails at all
  three biases where it was measured, which matches the baseline verdict.
  Among the rows that do pass at 20 µA, 3c is the first to fail as the bias
  falls: it fails at 10 µA (2/45 points, `ss` at 1.08 V, −40 and 27 °C) and below. 3a
  and 3b hold down to 7.5 µA.
- **15 µA Row 1 is INCOMPLETE, not PASS.** One of 60 mismatch draws at
  `ff_-40c_1.08v` (sample 12) ended in ngspice "Timestep too small", with
  the trouble node on the tail drain (`xa.x1.tmid`). That leaves 59 usable
  draws against the ratified N = 60, and the grader does not round this
  up. The other 44 points are all ≤ 11.89 mV. The pinned klt cannot re-run
  one Monte-Carlo unit with its recorded seeds
  ([klayout-tools#2973](https://github.com/2AMLogic/klayout-tools/issues/2973)),
  so completing that point would mean resubmitting the whole 540-unit
  `mos_ff` request under a new campaign id. That was not done.
- **Row 2 falls as the bias falls** (1.289 → 1.238 → 1.074 mV). This is
  plausible for a StrongARM latch, where slower integration narrows the
  noise bandwidth, but each value carries the probit statistic's N = 80
  sampling error. The TRNOISE streams are also pid-seeded across jobs
  (klayout-tools#2963; see Limitations), so the per-bias differences are not
  claimed as a trend.
- **Power** is klt's full 30 ns-cycle average on instance A's supply,
  including the reference branch. It is the same instrument as the issue
  #62 campaign, so it reads higher than DR-0002's harness record (see "Power
  reads higher"). Compare bias points with each other, not with the 22.9 …
  29.5 µW DR figure. Only 2.5 µA lands under the ≤ 20 µW Stretch, and it
  fails Rows 3a/3b/3c.

**Mirror and headroom screening.** Two probes are added to each
regeneration body: `vref_v`, the diode-connected reference's Vgs, and
`tmid_eval_v`, the tail drain voltage early in evaluation. The tail current
itself is not probed, so the 4:1 ratio is never measured directly. A value
is **flagged** when the tail drain drops below 0.1 V (near triode, so the
current falls below 4×) or when tail Vds / reference Vds leaves 0.5 … 2
(the mirror gain departs from 4 by CLM/DIBL). Weak inversion (reference Vgs
< 0.3 V) is a note only, because a fixed W/L ratio still sets 4:1 at equal
Vgs. Results:

- 40 µA is the only value with a near-triode point (1/45), and it has the
  largest Vds mismatch (28/45 points). Its comparison is the least
  like-for-like.
- Every value has some Vds-ratio flags: 20/45 points at 2.5 µA, falling to
  2/45 at 15 µA, and 7/45 at the 20 µA baseline. The flagged points sit at
  the extremes of the 0.23 … 5.27 ratio range in `ibsweep.md`.
- Weak inversion covers 21/45 points at 20 µA and 42/45 at 2.5 µA.

The per-value table in `ibsweep.md` lists the flags next to the met / failed
/ incomplete / not-swept Target rows.

**Reproducing.**

```bash
C=<new-id>
for ib in 2.5 5 7.5 10 15 20 40; do
  python3 sim/run_klt_corner_verification.py build --campaign $C/ib_${ib}uA \
      --bench regeneration --bench offset_mc --bench transient_noise \
      --dut-param dut_ib=${ib}e-6 --bias-probes
done
# one klt sim request at a time (each goes to the batch fleet):
python3 sim/run_klt_corner_verification.py run --campaign $C/ib_10uA --bench regeneration --klt .venv/bin/klt
python3 sim/run_klt_corner_verification.py run --campaign $C/ib_10uA --bench offset_mc --klt .venv/bin/klt --retry-refused 30 --retry-wait 60
# ... likewise per bias / bench; then tabulate (no simulator needed):
python3 sim/run_klt_corner_verification.py ibsweep --campaign $C
```

The 20 µA Monte-Carlo reuse is coded in `sim/kltsim/ibsweep.py`
(`REUSE_MC`). A new campaign either runs those benches at 20 µA or points
`REUSE_MC` at its own baseline. `run` refuses to overwrite an envelope. A
run interrupted part-way through can be resumed with `--skip-existing`
(or `--part <tag>`), and the interruption stays visible in
`attempts.jsonl`.

## Limitations and disclosures

- **Noise draws are independent but not reproducible.** ngspice-46's TRNOISE
  ignores `setseed`, `set rndseed` and `.options seed`
  (`comparator-transient-noise/README.md`). So klt's per-sample seed, recorded
  in each envelope as `monte_carlo.seed = 20260916`, does **not** reproduce
  these draws. The run count is the load-bearing input, as for the original.
  Independence was checked, not assumed: every sample records three raw
  source values, and the grader refuses any point where two samples repeat a
  draw. **No point did**, so every per-point hit fraction is a count over 80
  independent trials. **Between batch jobs the streams are not
  independent.** The generator falls back to a pid-derived seed, and the five
  per-process jobs run on fresh instances with similar pid sequences. As a
  result, 1,383 of 3,600 samples repeat, bit for bit, a draw also seen at a
  point in another job (`grading.md`, Row 2 note). This leaves each point's
  σ estimate valid and unbiased, but points in different process corners are
  correlated. The grid mean's sampling error is therefore wider than an
  independent-points figure. At worst (fully correlated) it is the per-point
  ±13 %, i.e. 1.289 ± 0.17 mV, which is still above the 1.0 mV Target. The
  independently run DR-0002 record agrees (1.335 mV). Filed generically as
  [klayout-tools#2963](https://github.com/2AMLogic/klayout-tools/issues/2963).
  The noise row also inherits the original bench's own caveat that the
  regeneration stage's internal noise is not injected
  ([#81](https://github.com/2AMLogic/sg13g2-comparator/issues/81)), so the
  figure is a lower bound on the true decision noise. It already fails the
  Target.
  **Update (issue #81, appended, nothing above edited):** the injection was
  then extended to the regenerative pair and reset devices; with it the
  grid mean is 1.305 mV (Target still NOT MET) and the internal term is about
  0.18 mV rms by a model-based estimate. See
  [`../comparator-transient-noise-full/README.md`](../comparator-transient-noise-full/README.md).
- **Offset reads 13 % high against the DR-0002 record** (grid-mean 3σ
  9.51 vs 8.40 mV, uniform across process corners, about 5 standard errors):
  a systematic difference with an undetermined cause, tracked in
  [#82](https://github.com/2AMLogic/sg13g2-comparator/issues/82). Verdicts
  are the same either way (Target met at 45/45, Stretch missed), but the
  Stretch miss is wider here (40/45 vs 27/45). Neither population is edited.
- **Power reads higher than DR-0002's figure, by definition, not by
  disagreement.** Static current matches the DR exactly (20.22 … 20.83 µA).
  DR-0002's total was static current × V plus `e_dec`, and `e_dec` integrates
  the supply only over 39.9 … 48 ns: the evaluation phase, which gives
  31 … 61 fJ. The klt bench averages the whole 30 ns cycle, which DR-0002's
  "average power at 33.3 MHz" literally names. That cycle contains
  182 … 338 fJ of dynamic energy. The difference is attributed to supply
  current outside the evaluation window, mainly the reset-phase recharge
  after the 50 ns strobe fall. Waveforms were not kept, so this split is
  inferred, not separately measured. The Stretch verdict is FAIL under
  either accounting.
- **Common mode** is fixed at `dut_vcm = 0.6 V`, as in every source bench.
  DR-0002 ratifies no common-mode claim (#79).
- **One abandoned attempt.** The first `offset_mc.mos_tt_mismatch` submission
  lost its driving session: the batch job completed, but its envelope was
  never captured. It is logged by hand in `attempts.jsonl` as "ABANDONED, NOT
  A RESULT", its partial artifacts were discarded, and the unchanged request
  was resubmitted. The committed tt envelope is that resubmission's.
- **Not in scope here:** post-layout (#61), the `klt yield` report (#63),
  the aggregate characterization artifact (#64), and any spec change.
