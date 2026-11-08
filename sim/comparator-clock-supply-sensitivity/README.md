# `sim/comparator-clock-supply-sensitivity/`

Clock-edge, strobe-width and supply-disturbance sensitivity of the whole-latch
`comparator_dut` (issue [#173](https://github.com/2AMLogic/sg13g2-comparator/issues/173)),
as paired `klt sim` campaigns on the batch fleet.

**Characterization, not compliance.** DR-0002 ratifies every row at one clock
shape (100 ps edges, 10 ns strobe in a 30 ns period) on a DC supply. Nothing here
is a verdict, no bound is graded, and no `spec/` file is touched. The
recommendation below is a recommendation only.

## Conditions (one at a time around `base`)

| condition | what |
|---|---|
| `base` | ratified clock, DC supply (inert 0 V disturbance source) |
| `edge-500p`, `edge-2n` | 500 ps / 2 ns rise and fall |
| `strobe-5n`, `strobe-15n` | 5 ns / 15 ns strobe flat-top |
| `supmid-p50`, `supmid-m50` | +/-50 mV supply step, 1 ns edge, at the strobe midpoint (the issue's specification) |
| `supeval-p50`, `supeval-m50` | the same step centred on the clock's 50 % rising crossing, i.e. during regeneration |

`supeval` is an addition: the latch decides 0.6-0.9 ns after the edge, so a step
at the strobe midpoint (5 ns later) can only disturb an already-held answer.
Both are reported. The mechanism (a series `vdist` source between a clean rail
and the DUT supply; clock amplitude and all supply-normalised probes referenced
to the clean rail) is documented in `sim/kltsim/clocksupply.py`; no klt feature
beyond a plain netlist source was needed.

## Benches and statistical basis

- **Regeneration** (decision time at 50 mV / 1 mV / 0.1 mV overdrive, tau, decision
  polarity): the full 45-point PVT grid (5 process x 1.08/1.20/1.32 V x
  -40/27/125 C), mismatch off, deterministic, so no sigma is claimed.
- **Offset** (paired-seed): the reduced 20-point grid, 5 process (`mos_*_mismatch`)
  x {1.08, 1.32} V x {-40, 125} C, the voltage x temperature extremes of the
  ratified box. N = 16 draws per point (320 per condition), klt base seed
  `20260916`. Each draw's seed depends only on (base seed, corner index, sample
  index), so draw k at a point is the same mismatch in every condition; seed
  equality is checked per sample. Resolution is one 3 mV staircase level, so the
  statistic is the mean paired shift (condition minus base) with its standard
  error over 320 pairs, plus
  the count of draws that moved by more than half a level. A pooled within-point
  spread is shown for context; it is not a single-point 3-sigma and no offset
  3-sigma is claimed from N = 16.
- The reduced offset grid is a stated subset (20 of 45 points, 16 of 60 draws)
  chosen to keep 9 conditions inside `sim/evidence-size-budget.json`; the offset
  shift is a paired difference, whose precision is the SEM column, not the
  precision of a sigma.

## Results

Full generated tables: [`campaigns/20261011-ce8cb93/comparison.md`](campaigns/20261011-ce8cb93/comparison.md)
(machine form `comparison.json`; every PVT point is in it). Summary:

| condition | td50 range (ns) | max shift vs base (ns) | correct 50 / 1 / 0.1 mV | offset mean shift +/- SEM (mV) | draws moved a level |
|---|---|---|---|---|---|
| `base` | 0.596 ... 0.850 | | 45/45 all | | |
| `edge-500p` | 0.577 ... 0.830 | -0.049 / +0.014 | 45/45 all | -0.009 +/- 0.047 | 25/320 |
| `edge-2n` | 0.395 ... 0.837 | -0.283 / +0.176 | 45/45 all | +0.131 +/- 0.112 | 103/320 |
| `strobe-5n` | 0.598 ... 0.852 | +0.002 | 45/45 all | 0.000 +/- 0.000 | 0/320 |
| `strobe-15n` | 0.595 ... 0.847 | -0.003 | 45/45 all | 0.000 +/- 0.000 | 0/319 (1 errored draw) |
| `supmid-p50` / `-m50` | 0.597 / 0.596 ... 0.850 | < 0.001 | 45/45 all | 0.000 +/- 0.000 | 0/320 each |
| `supeval-p50` | 0.579 ... 0.839 | -0.030 / -0.006 | 45/45 all | +0.019 +/- 0.019 | 4/320 |
| `supeval-m50` | 0.617 ... 0.872 | +0.007 / +0.040 | 45/45 all | +0.037 +/- 0.035 | 14/320 |

Reading:

- Decision correctness holds at every one of the 45 points for every condition,
  down to 0.1 mV overdrive.
- Slower clock edges move decision time most (td is timed from the clock's 50 %
  crossing, so the 2 ns edge shifts it down to 0.395 ns at the fast corners and
  up by up to 0.18 ns), and shift the offset by +0.13 +/- 0.11 mV (not
  distinguishable from zero at 1.2 SEM, with 103/320 draws moving a level).
- Strobe width (5-15 ns) and a mid-strobe supply step leave decision time and offset
  unchanged to within 2 ps and 0 mV, as expected once the decision is made.
- A 50 mV step during regeneration moves td50 by -30 to +40 ps and the offset
  by < 0.04 mV mean (within 2 SEM).
- Worst td50 anywhere is 0.872 ns (`supeval-m50`, `ss_125c_1.08v`), inside the 1.5 ns reference.

## Recommendation (no spec change made)

The ratified rows are not fragile to the characterized clock-edge (up to 2 ns),
strobe-width (5-15 ns) and +/-50 mV supply-step range: correctness is 45/45 and
the largest decision-time shift (+0.18 ns) leaves the worst td50 at 0.87 ns
against the 1.5 ns Target. **No new spec row or decision record is warranted by
these data.** If the project wants the edge-rate and supply-step conditions to
be part of the block's stated interface, a documentation-only DR recording this
range as the characterized application envelope would suffice; that is the
curator's call. Not covered: ripple during the evaluation phase (steps only),
steps larger than 50 mV, duty below 5 ns / above 15 ns, N > 16 offset draws, and
the PEX netlist.

## Known gaps and honest notes

- `offset.strobe-15n` has one errored draw (`mos_ff_mismatch/1.320V/-40C/mc9`,
  envelope status `error`, 319 of 320 pairs used). It is dropped from the
  pairing, not repaired or substituted (same policy as `comparator-offset-cm-band`).
- Baseline reproduction: `base` regeneration is bit-identical (45/45 points) to the
  issue #62 campaign `20261009-d73a9ac`, i.e. the 100 ps / 10 ns / DC point
  reproduces the existing regeneration evidence. `base` offset draws agree to
  0.0004 mV with the issue #62 draws that share a seed (32 draws; the reduced
  grid changes the corner index so the other draws have different seeds and are
  not compared). The 0.4 uV difference is most plausibly the offset bench's output
  sampling instant moved from 27 ns to 29 ns of each period (so a 15 ns strobe has
  ended); this was not isolated separately.
- Spot fleet capacity refusals (`BATCH_MAX_CONCURRENT_INSTANCES`) were retried and are
  in each condition's `attempts.jsonl`. The `base`, `edge-*`, `strobe-5n` and `regen.strobe-15n` runs were made by a
  prior builder session under the CI pin; the remainder were run under the same
  pin (`klt 0.5.0+ge8ca621a6961`, a throwaway venv, not the host's 0.7.0). One
  submission made with the host's klt 0.7.0 was aborted client-side before any
  envelope was written and is not part of the evidence.
- klt friction: the capacity-refusal behaviour (`capacity_wait_s` not honoured) and
  the client/runner version mismatch are already tracked at
  `2AMLogic/klayout-tools` #2917 and #2948; no new tool gap was found (the supply
  disturbance is expressible as a plain netlist source), so no new issue was filed.

## Reproduce

Use the CI-pinned klt (`0.5.0+ge8ca621a6961`) in a throwaway venv. From the repo root:

```bash
S=20261011-ce8cb93
python3 sim/run_clock_supply_sensitivity.py build   --series $S
python3 sim/run_clock_supply_sensitivity.py run     --series $S --klt $KLT --retry-refused 8
python3 sim/run_clock_supply_sensitivity.py compare --series $S
python3 sim/run_clock_supply_sensitivity.py smoke --kind regen --condition edge-2n --osdi-dir DIR --klt $KLT  # one corner, local
```

`build` and `run` write only new files; existing envelopes are skipped. Offset
draw seeds are derived by klt from base seed `20260916` and are in each envelope.
