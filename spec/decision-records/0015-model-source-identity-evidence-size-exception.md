# 0015: Evidence-size exception for runtime SPICE model-source identity code, tests and docs (issue #203)

- **Status**: proposed. **This record covers the evidence budget only, and the
  growth it covers is harness code, unit tests and documentation, not
  evidence.** It ratifies no bound and relaxes no Target or Stretch number. It
  authorizes one raise of the `sim/` total ceiling in
  `sim/evidence-size-budget.json` (issue #132's contract), exactly the
  measured overage of 19404 B. It takes effect with the reviewed merge of the
  PR that lands it, as for DR-0005 to DR-0014. The drafting agent does not
  merge it.
- **Date**: 2026-10-11
- **Decided by**: Doctor agent, PR #206 for issue #203. The operator reviews
  the raise as a governance item at merge.
- **Related**:
  [`0014-osdi-identity-evidence-size-exception.md`](0014-osdi-identity-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #203 makes local PVT records identify the runtime SPICE model sources
they loaded (path-independent sha256 inventory of the model tree, re-hashed
after the grid, run refused on change, incomplete scope disclosed). Mocked
unit tests and a short documentation section come with it. No committed
record, log or campaign output is modified or regenerated. After DR-0014
`sim/` was exactly at its ceiling.

| Path | Bytes added |
|---|---|
| `sim/harness/pdk.py` | 5858 |
| `sim/harness/tests/test_pdk.py` | 5317 |
| `sim/harness/tests/test_runner.py` | 3248 |
| `sim/harness/README.md` | 1959 |
| `sim/harness/cli.py` | 1708 |
| `sim/harness/report.py` | 988 |
| `sim/harness/runner.py` | 226 |
| `sim/evidence-size-budget.json` (this exception entry) | 100 |
| **Total** | **19404** |

## Decision

Raise the `sim/` total ceiling by exactly **19404 B**. The single `sim` entry
carries the cumulative 15645830 + 19404 = **15665234 B** and cites this record.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15665234}
```

(Cumulative: 15645830 B from DR-0005 to DR-0014 and 19404 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No `sim/` evidence file is modified.
