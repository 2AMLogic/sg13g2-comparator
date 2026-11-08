# 0032: Evidence-size exception for Monte Carlo sample-population validation (issue #245)

- **Status**: proposed, **awaiting explicit operator/maintainer
  authorization of the final byte figure (117933 B)**. Not yet authorized.
  **This record covers the evidence budget only.** It ratifies no bound and
  relaxes no Target or Stretch number. It proposes one raise of the `sim/`
  total ceiling in `sim/evidence-size-budget.json` (issue #132's contract),
  exactly the measured overage of 117933 B. It takes effect only if a human
  operator or maintainer explicitly authorizes that figure on the PR that
  lands it; the PR must not be approved or merged before that authorization
  exists. No agent authorizes it, and the drafting agent does not merge it.
- **Date**: 2026-10-12
- **Drafted by**: Builder agent, PR for issue #245; revised by the Doctor
  agent after review (populations.py indexed as a grader source, report
  re-minted once in the same `-r2` directory, overage recomputed).
- **Decided by**: pending; requires an explicit operator/maintainer
  authorization comment on the PR for the final byte figure.
- **Related**:
  [`0023-pex-decision-validity-evidence-size-exception.md`](0023-pex-decision-validity-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: [`evidence-size/323-retire-incremental-evidence-size-raises.md`](evidence-size/323-retire-incremental-evidence-size-raises.md) (the authorization below no longer applies)

## Context

Issue #245 makes the offset and transient-noise compliance reducers validate
each PVT point's actual Monte Carlo sample records (unique sample indices,
one base corner, exactly the declared N, consistent summary counts) before
using a klt summary, sharing one validator with the yield collector. After
DR-0023 `sim/` was exactly at its ceiling, so any addition needs this
exception. The grader's sha256 is an indexed source of the T1 item 8
characterization report, and report directories are append-only, so the
report is re-minted in a NEW directory; the earlier one is untouched. Its
numbers are identical (the grader still equals the committed `grading.json`);
only the grader digests (`grade.py`, and `populations.py`, which is now an
indexed grader source) and hence the input-index hash differ.

| Path | Nature | Bytes |
|---|---|---|
| `sim/characterization/20261009-d73a9ac-schematic-r2/` | re-minted derived report (4 files) | see below |
| `sim/kltsim/populations.py` | shared validator (new) | see below |
| `sim/kltsim/tests/test_populations.py` | regression tests (new) | see below |
| `sim/kltsim/{grade,yield_reports,characterization}.py`, `sim/README.md` | integration, report-id map, docs | see below |
| `sim/evidence-size-budget.json` | extended cumulative entry | see below |

The total is the measured overage, 117933 B (blob bytes at the PR head, from
`python3 scripts/check_evidence_size.py --tree HEAD`). This record lives under
`spec/` and adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **117933 B**. The single `sim` entry
carries the cumulative 28263838 + 117933 = **28381771 B** and cites this record. No
ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28381771}
```

(Cumulative: 28263838 B from DR-0005 to DR-0030 and 117933 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.
