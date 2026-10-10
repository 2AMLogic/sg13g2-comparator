# `klt-yield/`: `klt yield` evidence for the statistical DR-0002 rows (T1 item 6)

Issue [#63](https://github.com/2AMLogic/sg13g2-comparator/issues/63). The
Monte Carlo evidence in `sim/comparator-offset-mc/`,
`sim/comparator-offset-transient-mc/` and the whole-latch `klt sim` campaign
`sim/klt-corner-verification/campaigns/20261009-d73a9ac/` is real, but `klt
signoff` item 6 accepts one kind of evidence: a `klt yield` JSON report. This
directory mints those reports from the committed campaign. It runs **no
simulation** (nothing new is submitted to the batch fleet) and edits no source
envelope.

## Verdict

**Item 6 is cited and renders `unmet` / `undersized_sample`.** The pinned
`klt signoff` refuses a report whose own `sample_size.verdict` is
`insufficient`. Every one of the 45 offset populations is: N = 60 draws with
zero failures gives a 95 % Clopper-Pearson lower bound of 94.0 %, and `klt
yield`'s default precision target (interval half-width 0.01) needs N = 183.
Nothing here relaxes that target, declares a yield target the spec does not
ratify, or reads zero failures at N = 60 as 100 % yield. The negative control
is declared and `detected` at all 45 points. Reaching `met` needs a larger
campaign at the same ratified seeds-and-N discipline or a ratified
statement of the precision wanted; both are out of scope here and are not
claimed.

## The statistical rows

| DR-0002 row | Ratified statistic | What the `klt yield` report holds | Cited for item 6 |
|---|---|---|---|
| 1 Offset | 3 x population sigma of `vos_mv`, net of the 3 mV staircase's `step^2/12`, worst PVT point <= 15 mV (Stretch <= 8 mV) | per PVT point (N = 60): the fraction of `vos_mv` draws inside +/-15 mV, Clopper-Pearson interval, normal fit and Cpk, derived over-limit negative control | yes (`offset.yield.json`) |
| 2 Noise | grid-wide mean of the per-point two-rung probit-slope sigma, <= 1.0 mV rms (Stretch <= 0.6) | per PVT point and rung (N = 80): the fraction of 0/1 trials that resolve in the correct direction at +/-1 mV overdrive (`hit_plus >= 0.5`, `hit_minus <= 0.5`); `hit_zero` is the injection guard and is not a yield measurement | no (`noise.yield.json`) |

A yield is **not** either ratified statistic:

- The per-draw +/-15 mV fraction is not the quantization-corrected 3-sigma
  criterion. Both appear together in `index.json` (`ratified_statistic`,
  recomputed here and required to equal the existing grader's value at all 45
  points). The worst point is 12.09 mV against the 15 mV Target.
- A Bernoulli hit fraction is not an input-referred noise sigma. The ratified
  noise statistic is in each point's `ratified_statistic`; its grid-wide mean
  is 1.289 mV against a 1.0 mV Target, which **fails**. The noise report
  declares no target yield and no negative control, so it is committed as
  evidence of the populations but is not cited, and nothing borrows the passing
  offset report to imply a noise claim.

## Reproduce

```bash
# One command: validates the source chain, derives the inputs, runs the pinned
# native engine, writes sim/klt-yield/campaigns/<id>/ (refuses an existing id).
python3 sim/run_klt_yield.py generate --campaign-id 20261010-d73a9ac

# Engine-free consistency check (what CI's unit tests run): inputs regenerate
# byte-for-byte from the source, hashes match the index, the manifest pin matches.
python3 sim/run_klt_yield.py check
# ... and re-run the engine, requiring byte-identical reports:
python3 sim/run_klt_yield.py check --rerun
```

The engine defaults to the pinned build,
`uvx --from 'klayout-tools[yield] @ git+https://github.com/2AMLogic/klayout-tools@<manifests/klt-pin.json commit>' klt`.
The `yield` extra is required (`klt yield` needs the `klt_yield_native` Rust
extension; the pinned git form builds it from source and needs a Rust
toolchain). Override with `--klt` or `$KLT_YIELD_CMD`. Before relying on any
output the workflow checks the reported version against `manifests/klt-pin.json`
and runs a known-answer sample set; a missing extension, wrong version or wrong
answer is an execution failure and writes nothing.

Tests: `PYTHONPATH=sim python3 -m unittest kltsim.tests.test_yield_reports`.
The tests that execute the native engine run only when `KLT_YIELD_CMD` is set
(they are skipped, never passed, otherwise).

## What is in a campaign directory

```
campaigns/20261010-d73a9ac/
  inputs/offset.samples.json   derived sample-set document, one measurement per PVT point
  inputs/noise.samples.json
  offset.yield.json            klt yield output, verbatim
  noise.yield.json
  index.json / index.md        report -> spec row / PVT point map
```

`index.json` records, per population: the source corner, the attempted, usable,
errored and inconclusive counts, every excluded draw with its reason, the
per-sample seed, the limits, confidence, the empirical yield with its interval,
the sample-size and negative-control verdicts, the per-measurement warnings,
and the ratified statistic. It also records the source envelope and request
hashes (the saved invocation chain `kltsim.grade` already validates), the tool
pin, and the report and samples hashes.

Provenance and exclusions:

- Source: campaign `20261009-d73a9ac` (`offset_mc` N = 60, `transient_noise`
  N = 80 per PVT point, base seed 20260916). The same `kltsim.grade` validation
  as the grader applies: request/invocation hash chain, DUT, supply and
  temperature probes, validity gates, malformed or duplicate measurement lists.
  A draw that fails it is **excluded and counted** (`errored` when no value,
  `inconclusive` when a value exists but is not trusted), never analysed; a
  population that is missing, duplicated, not N, or has fewer than 2 usable
  draws stops generation. All 45 + 45 populations are complete today: no
  exclusions.
- Deterministic (non-sampled) corners are ignored; the PVT populations are
  never pooled (the engine itself warns that a pooled estimate is a worst-case
  envelope, not a distribution anyone sampled).
- Original envelopes are read only and stay byte-identical. The derived
  `inputs/*.samples.json` are new files.
- Noise draws are not reproducible (ngspice-46 TRNOISE ignores klt's per-sample
  seed, klayout-tools#2963), so the recorded seeds identify samples, not
  noise streams.

## Negative controls

- **Derived over-limit control (the yield control).** Each offset population
  declares `negative_control`: the same draws plus a forced offset of twice the
  limit (30 mV), checked at generation to be entirely outside +/-15 mV. `klt
  yield` reports it `detected` at 45/45 points. The unit tests prove the control
  is derived from, and shifts, exactly the nominal draws, that a draw on the
  boundary is refused, that an in-limit "control" is `not_detected`, and that
  an over-limit population with a declared target yield makes the analysis
  `fail`.
- **Mismatch-off smoke (the injection control).** The committed smoke
  evidence `.../smoke/offset_mc-mismatch-vs-negctrl.envelope.json` (N = 4,
  `tt` 1.2 V 27 C) shows zero spread with mismatch models off and a non-zero
  spread with them on. It shows the injection mechanism moves the spread. It
  is **not** a known-bad yield control: the off population sits inside the
  limits. It is referenced from `index.json` by hash.
- Upstream `klt yield-samples` ([klayout-tools#2563](https://github.com/2AMLogic/klayout-tools/issues/2563),
  open as of 2026-10-10) is not assumed. The controls here are caller-derived
  sample-set documents consumed by the supported `klt yield` input; the
  nominal-equivalence tests analyse the real committed envelope directly
  (one base corner kept) and require the derived document to give an identical
  `n`, distribution, yield and capability.

## How signoff pins it

`klt yield` reports carry no `provenance`; the pinned `klt signoff` pins the
document named by the report's `samples` field, so the manifest's item 6
`content_hash` is the sha256 of `inputs/offset.samples.json`, not of the
report. The report was produced from the repo root so `samples` is a
repo-relative path. Because the native grader answers `undersized_sample`
before it compares pins, a stale pin is not visible in its output while the
item is `unmet`; `python3 sim/run_klt_yield.py check` (which unit tests run)
compares the manifest pin, the index and the files, and fails if any differs.
Tampering with the samples copy was verified to fail it.

## Limits and open questions

- **Realization and issue [#82](https://github.com/2AMLogic/sg13g2-comparator/issues/82).**
  This analyses the already-committed `klt sim` realization. That campaign's
  offset reads about 13 % above the DR-0002 historical record, and the
  cause (old harness loop versus new process) is undetermined. This work does
  not settle it and does not replace the ratified record.
- N = 60 per point is the ratified Row 1 basis; the yield-precision target is
  therefore unmet at every point (see Verdict).
- Row 2 noise is a lower bound in the DR-0002 sense (the regeneration stage's
  own noise is not injected); the Target already fails on the ratified statistic.
- Related, not blocking: #132 (evidence budgets and sparse CI) governs the
  size of this directory; klayout-tools#2960 and #2963 are the existing noted
  tool gaps for population statistics and the TRNOISE seed contract.
