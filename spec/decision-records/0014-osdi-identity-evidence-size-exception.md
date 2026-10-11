# 0014: Evidence-size exception for OSDI model identity code, tests and docs (issue #196)

- **Status**: proposed. **This record covers the evidence budget only, and the
  growth it covers is harness code, the OSDI build script, unit tests and
  documentation, not evidence.** It ratifies no bound and relaxes no Target or
  Stretch number. It authorizes one raise of the `sim/` total ceiling in
  `sim/evidence-size-budget.json` (issue #132's contract), exactly the
  measured overage of 14940 B. It takes effect with the reviewed merge of the
  PR that lands it, as for DR-0005 to DR-0013. The drafting agent does not
  merge it.
- **Date**: 2026-10-11
- **Decided by**: Builder agent, PR for issue #196. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0013-runner-timeout-diagnostics-evidence-size-exception.md`](0013-runner-timeout-diagnostics-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #196 makes local PVT records identify the compiled OSDI model bytes
they loaded (path-independent sha256 inventory, re-hashed after the grid, run
refused on change), and makes `sim/tools/build-osdi.sh` write a machine-local
build receipt and report reused binaries without one as unknown provenance.
Mocked unit tests and a short documentation section come with it. No
committed record, log or campaign output is modified or regenerated. After
DR-0013 `sim/` was exactly at its ceiling.

| Path | Bytes added |
|---|---|
| `sim/tools/build-osdi.sh` | 3576 |
| `sim/harness/tests/test_pdk.py` | 3640 |
| `sim/harness/pdk.py` | 2145 |
| `sim/harness/tests/test_runner.py` | 1727 |
| `sim/harness/README.md` | 1457 |
| `sim/harness/cli.py` | 1479 |
| `sim/harness/report.py` | 367 |
| `sim/README.md` | 334 |
| `sim/harness/toolchain.py` | 153 |
| `sim/evidence-size-budget.json` (this exception entry) | 62 |
| **Total** | **14940** |

## Decision

Raise the `sim/` total ceiling by exactly **14940 B**. The single `sim` entry
carries the cumulative 15630890 + 14940 = **15645830 B** and cites this record.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15645830}
```

(Cumulative: 15630890 B from DR-0005 to DR-0013 and 14940 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No `sim/` evidence file is modified.
