# Retire the incremental evidence-size raises; evidence lives in the artifact store — issue #323

- **Status**: proposed. **Evidence-budget record only.** It ratifies no bound
  and relaxes no Target or Stretch number in `spec/` or `README.md`. It takes
  effect with the reviewed merge of the PR that lands it; the operator
  ratifies it at merge.
- **Decided by**: operator direction (rjwalters, 2026-10-23, attended
  `fleet:decide` round 20261023-holds-r1, Q9): the per-PR cap raises were "a
  half solution"; simulation artifacts belong in the artifact store.
- **Supersedes**: the evidence-size exceptions DR-0005 through DR-0032 listed
  below, and the open question in issue #322 (DR-0031, which was never merged
  to `main`; its text is superseded with the rest). **Superseded by**: none.
- **Builds on**: [`318-manifest-store-rebaseline.md`](318-manifest-store-rebaseline.md)
  (re-baseline at `4c0db1c86`, `exceptions` cleared) and
  [`312-suspend-evidence-size-ceiling.md`](312-suspend-evidence-size-ceiling.md).

## Decision

1. **The incremental-raise approach is retired.** Raising the `sim/` ceiling
   one decision record per PR is over. Most of the growth those records
   authorized was code, tests and docs, not evidence, and each one cost an
   operator ratification. The #318 re-baseline already absorbed every byte
   they authorized and cleared `exceptions`, so none of their authorizations
   is in force.
2. **New evidence goes to the artifact store; the repo commits manifests**
   (#318, 2AMLogic/2am#5553 consumer 1).
3. **No new exception records.** No PR may add an evidence-size exception:
   not an `exceptions` entry in `sim/evidence-size-budget.json`, not a file in
   `sim/evidence-size-exceptions/`, and no `*-evidence-size-exception.md`
   record. `scripts/check_evidence_size.py` now fails (exit 1) on any of
   these, so this is enforced, not advisory. A real overage is fixed by
   storing the bytes (item 2), not by an exception.
4. **The check counts committed evidence bytes only.** The total ceiling is
   compared against the sum of the evidence units (`sim/<bench>/{records,
   corners,netlist-snapshots,campaigns,reports}/...`), not all of `sim/`, so
   `*.py`, tests and docs under `sim/` can never trip it. The ceiling numbers
   and the per-unit grandfathering are unchanged.
5. **End state: retire the cap.** Once the remaining committed evidence
   (about 567 MB under `sim/`) has been migrated to the store, the budget file
   and the checker are removed. Migration is follow-on work under
   2AMLogic/2am#5553 (tracked from this repo in the PR for this record). Until
   then the grandfathered units and the ceilings above stay as a no-growth
   guard.

## Superseded records

Each record keeps its text as history. Only its `Superseded by` line changed.
DR-0004 is not an evidence-size record and is unaffected. DR-0028, DR-0031
and DR-0033 never landed on `main`; there is nothing to mark.

| DR | Record | Subject |
|---|---|---|
| 0005 | [`0005-offset-n200-evidence-size-exception.md`](../0005-offset-n200-evidence-size-exception.md) | the N = 200 offset campaign (issue #167) |
| 0006 | [`0006-offset-significance-evidence-size-exception.md`](../0006-offset-significance-evidence-size-exception.md) | the klt-vs-record offset significance analysis (issue #82) |
| 0007 | [`0007-repeated-measurement-harness-evidence-size-exception.md`](../0007-repeated-measurement-harness-evidence-size-exception.md) | the repeated-measurement harness fix (issue #177) |
| 0008 | [`0008-harness-bound-validation-evidence-size-exception.md`](../0008-harness-bound-validation-evidence-size-exception.md) | harness check-bound validation code (issue #178) |
| 0009 | [`0009-pex-delta-table-evidence-size-exception.md`](../0009-pex-delta-table-evidence-size-exception.md) | the PEX delta-table renderer (issue #181) |
| 0010 | [`0010-harness-frozen-inputs-evidence-size-exception.md`](../0010-harness-frozen-inputs-evidence-size-exception.md) | harness frozen-input capture code (issue #179) |
| 0011 | [`0011-cm-band-runner-tests-evidence-size-exception.md`](../0011-cm-band-runner-tests-evidence-size-exception.md) | CM-band runner unit tests (issue #186) |
| 0012 | [`0012-noise-uncertainty-evidence-size-exception.md`](../0012-noise-uncertainty-evidence-size-exception.md) | noise-analysis uncertainty code and tests (issue #192) |
| 0013 | [`0013-runner-timeout-diagnostics-evidence-size-exception.md`](../0013-runner-timeout-diagnostics-evidence-size-exception.md) | runner timeout-diagnostics code and tests (issue #197) |
| 0014 | [`0014-osdi-identity-evidence-size-exception.md`](../0014-osdi-identity-evidence-size-exception.md) | OSDI model identity code, tests and docs (issue #196) |
| 0015 | [`0015-model-source-identity-evidence-size-exception.md`](../0015-model-source-identity-evidence-size-exception.md) | runtime SPICE model-source identity code, tests and docs (issue #203) |
| 0016 | [`0016-clock-supply-sensitivity-evidence-size-exception.md`](../0016-clock-supply-sensitivity-evidence-size-exception.md) | the clock-edge and supply-disturbance sensitivity campaign (issue #173) |
| 0017 | [`0017-decision-cm-band-evidence-size-exception.md`](../0017-decision-cm-band-evidence-size-exception.md) | the decision-time common-mode band campaign (issue #164) |
| 0018 | [`0018-pex-delta-table-evidence-size-exception-2.md`](../0018-pex-delta-table-evidence-size-exception-2.md) | the PEX delta-table renderer fix (issue #211) |
| 0019 | [`0019-cm-band-preflight-evidence-size-exception.md`](../0019-cm-band-preflight-evidence-size-exception.md) | the CM-band preflight run-submission guard (issue #194) |
| 0020 | [`0020-sparse-lint-population-evidence-size-exception.md`](../0020-sparse-lint-population-evidence-size-exception.md) | the sparse lint-population preflight docs (issue #216) |
| 0021 | [`0021-cm-decision-validation-evidence-size-exception.md`](../0021-cm-decision-validation-evidence-size-exception.md) | the CM decision-band validation fix (issue #209) |
| 0022 | [`0022-noise-full-provenance-evidence-size-exception.md`](../0022-noise-full-provenance-evidence-size-exception.md) | noise-full provenance validation (issue #236) |
| 0023 | [`0023-pex-decision-validity-evidence-size-exception.md`](../0023-pex-decision-validity-evidence-size-exception.md) | PEX delta-table decision-state validity (issue #240) |
| 0024 | [`0024-report-preserve-evidence-size-exception.md`](../0024-report-preserve-evidence-size-exception.md) | derived report-pair preservation (issue #237) |
| 0025 | [`0025-cm-offset-draw-validation-evidence-size-exception.md`](../0025-cm-offset-draw-validation-evidence-size-exception.md) | CM-offset draw validation (issue #250) |
| 0026 | [`0026-cm-band-empty-reproduction-evidence-size-exception.md`](../0026-cm-band-empty-reproduction-evidence-size-exception.md) | CM-band empty-reproduction verdict (issue #252) |
| 0027 | [`0027-yield-index-rederivation-evidence-size-exception.md`](../0027-yield-index-rederivation-evidence-size-exception.md) | yield index re-derivation check (issue #255) |
| 0029 | [`0029-ibsweep-validation-evidence-size-exception.md`](../0029-ibsweep-validation-evidence-size-exception.md) | I_B sweep probe validation (issue #267) |
| 0030 | [`0030-sizesweep-geometry-gate-evidence-size-exception.md`](../0030-sizesweep-geometry-gate-evidence-size-exception.md) | sizing-finalist geometry gate (issue #269) |
| 0032 | [`0032-population-validation-evidence-size-exception.md`](../0032-population-validation-evidence-size-exception.md) | Monte Carlo sample-population validation (issue #245) |

## What does not change

- The append-only guard and the measurement (`git ls-tree -rl` blob bytes).
- Ratified Target/Stretch spec bounds.

## Machine-checked

`scripts/tests/test_evidence_size.py` covers: code under `sim/` never counts,
oversized evidence still fails, and every exception route is rejected.
