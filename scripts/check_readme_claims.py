#!/usr/bin/env python3
"""README target-spec-table figures must match the committed characterization report.

The README "target-spec table" (rows from `| Parameter |` on) quotes
hand-copied figures from the aggregated report
`sim/characterization/20261009-d73a9ac-schematic/report.json` (the T1 item 8
evidence, itself gated by `sim/characterize.sh report check`). This script
keeps the prose from drifting from that evidence: for a small, explicit
allowlist of claims (`CLAIMS` below -- the one reviewed pattern/field mapping
table) it extracts each figure from the README with a fixed regex, reads the
corresponding value from the report, and compares them *at the precision the
README quotes* (round-half-up to the README's decimal places).

  exit 0   every allowlisted claim was found in the README and equals the
           report value.
  exit 1   a claim disagrees, a claim's pattern no longer matches the README
           (the prose moved: update the pattern table deliberately), or the
           report/README could not be read.

Anything in the table that is NOT in the allowlist is listed as UNCHECKED,
never silently passed: every `N/45`, `N of 45` count, and the number of
unit-bearing figures (fC, uV, mV, ns, ps, uW) not covered by a claim. Several
README figures deliberately quote a different population than the aggregated
report (e.g. the offset row quotes the DR-0002 whole-latch record, the noise
row the issue #81 campaign, the power row an earlier record) and so cannot be
compared with it; they are not mapped here. Mapping them is a spec/curation
question, not something this guard decides.

Zero dependencies beyond the Python 3 standard library; needs no PDK,
ngspice or klt.

Usage:
    python3 scripts/check_readme_claims.py
    python3 scripts/check_readme_claims.py --readme README.md --report report.json
Exit codes: 0 all allowlisted claims match, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_README = REPO_ROOT / "README.md"
DEFAULT_REPORT = (
    REPO_ROOT / "sim" / "characterization" / "20261009-d73a9ac-schematic" / "report.json"
)

#: Column of the README table that carries the measured figures.
MEASURED_COLUMN = 3

# Each claim: (name, row prefix of the README table row, regex with exactly
# one capture group applied to the "Measured" cell, report path, kind).
# Report path: (row id, tier, *keys) walked from the report row; "int"
# claims compare exactly, "num" claims compare at the README's precision,
# "str" claims compare as strings.
_KICK = "| **Kickback**"
_DEC = "| Decision time"
CLAIMS = [
    ("kickback: points over 25 fC (Target)", _KICK, r"\((\d+)/45 points over 25 fC\)",
     ("4a", "target", "points_failing"), "int"),
    ("kickback: charge Stretch points failing", _KICK, r"charge Stretch NOT MET \((\d+)/45\)",
     ("4a", "stretch", "points_failing"), "int"),
    ("kickback: Q_kick min fC/side", _KICK, r"\*\*([\d.]+) … [\d.]+ fC/side\*\*",
     ("4a", "target", "range", "min", "value"), "num"),
    ("kickback: Q_kick max fC/side", _KICK, r"\*\*[\d.]+ … ([\d.]+) fC/side\*\*",
     ("4a", "target", "range", "max", "value"), "num"),
    ("kickback: binding point", _KICK, r"binding point `([^`]+)`",
     ("4a", "target", "binding", "point"), "str"),
    ("kickback: binding Q_kick fC", _KICK, r"binding point `[^`]+` \(([\d.]+) fC;",
     ("4a", "target", "binding", "value"), "num"),
    ("decision: Stretch points failing (50 mV)", _DEC, r"Stretch NOT MET at (\d+)/45",
     ("3a", "stretch", "points_failing"), "int"),
    ("decision: 50 mV min ns", _DEC, r"50 mV: ([\d.]+) ns",
     ("3a", "target", "range", "min", "value"), "num"),
    ("decision: 50 mV max ns", _DEC, r"50 mV: [\d.]+ ns \(`[^`]+`\) … \*\*([\d.]+) ns\*\*",
     ("3a", "target", "range", "max", "value"), "num"),
    ("decision: tau min ps", _DEC, r"τ: ([\d.]+) … [\d.]+ ps",
     ("3b", "target", "range", "min", "value"), "num"),
    ("decision: tau max ps", _DEC, r"τ: [\d.]+ … ([\d.]+) ps",
     ("3b", "target", "range", "max", "value"), "num"),
    ("decision: 0.1 mV min ns", _DEC, r"0\.1 mV: ([\d.]+) … ",
     ("3c", "target", "range", "min", "value"), "num"),
    ("decision: 0.1 mV max ns", _DEC, r"0\.1 mV: [\d.]+ … \*\*([\d.]+) ns\*\*",
     ("3c", "target", "range", "max", "value"), "num"),
]

_COUNT_RE = re.compile(r"\b\d+/45\b|\b\d+ of 45\b")
_FIG_RE = re.compile(r"\d+(?:\.\d+)?\s?(?:fC|µV|mV|ns|ps|µW)\b")


def load_report(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def table_rows(readme_text: str) -> list[list[str]]:
    """Cells of every row of the target-spec table (header onward)."""
    rows, inside = [], False
    for line in readme_text.splitlines():
        if line.startswith("| Parameter |"):
            inside = True
        elif inside and not line.startswith("|"):
            break
        if inside:
            rows.append(line)
    return rows


def _walk(report: dict, path: tuple):
    rid, *keys = path
    node = next((r for r in report.get("rows", []) if r.get("id") == rid), None)
    if node is None:
        raise KeyError(f"report has no row id {rid!r}")
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            raise KeyError(f"report row {rid!r} has no field {'.'.join(keys)}")
        node = node[k]
    return node


def _round_to(value: float, text: str) -> str:
    places = len(text.split(".", 1)[1]) if "." in text else 0
    q = Decimal(1).scaleb(-places)
    return str(Decimal(repr(float(value))).quantize(q, rounding=ROUND_HALF_UP))


def check(readme_text: str, report: dict, claims=CLAIMS):
    """Return (failures, checked, unchecked); failures are printable strings."""
    rows = table_rows(readme_text)
    failures, checked = [], 0
    covered: dict[tuple[int, int], set] = {}  # (row idx, span start) -> span
    for name, prefix, pattern, path, kind in claims:
        idx = next((i for i, ln in enumerate(rows) if ln.startswith(prefix)), None)
        if idx is None:
            failures.append(f"{name}: README table row {prefix!r} not found")
            continue
        cells = [c.strip() for c in rows[idx].strip().strip("|").split(" | ")]
        cell = cells[MEASURED_COLUMN] if len(cells) > MEASURED_COLUMN else ""
        m = re.search(pattern, cell)
        if not m:
            failures.append(f"{name}: pattern {pattern!r} no longer matches the README")
            continue
        try:
            raw = _walk(report, path)
        except KeyError as exc:
            failures.append(f"{name}: {exc.args[0]}")
            continue
        claimed = m.group(1)
        if kind == "int":
            ok, shown = int(claimed) == raw, str(raw)
        elif kind == "num":
            shown = _round_to(raw, claimed)
            ok = shown == claimed
        else:
            ok, shown = claimed == raw, str(raw)
        checked += 1
        covered.setdefault((idx, 0), set()).add(m.span())
        if not ok:
            failures.append(
                f"{name}: README says {claimed}, report ({'/'.join(map(str, path))}) says {shown}"
            )
    # Unchecked: counts/figures in the table's data rows that no claim spans.
    # Claim spans are relative to the Measured cell; overlap means covered.
    unchecked = []
    for i, ln in enumerate(rows[2:], start=2):
        cells = [c.strip() for c in ln.strip().strip("|").split(" | ")]
        cell = cells[MEASURED_COLUMN] if len(cells) > MEASURED_COLUMN else ""
        spans = covered.get((i, 0), set())
        for rx in (_COUNT_RE, _FIG_RE):
            for fm in rx.finditer(cell):
                if not any(fm.start() < e and s < fm.end() for s, e in spans):
                    unchecked.append((cells[0][:40], fm.group(0)))
    return failures, checked, unchecked


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--readme", type=Path, default=DEFAULT_README)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = ap.parse_args(argv)
    try:
        text = args.readme.read_text(encoding="utf-8")
        report = load_report(args.report)
    except (OSError, ValueError) as exc:
        print(f"FAIL: cannot read inputs: {exc}", file=sys.stderr)
        return 1
    failures, checked, unchecked = check(text, report)
    for f in failures:
        print(f"FAIL: {f}", file=sys.stderr)
    counts = [u for u in unchecked if _COUNT_RE.fullmatch(u[1])]
    figs = len(unchecked) - len(counts)
    print(f"checked {checked}/{len(CLAIMS)} allowlisted README claims against {args.report.name}")
    for row, c in counts:
        print(f"UNCHECKED count in row {row!r}: {c}")
    print(f"UNCHECKED unit-bearing figures not in the allowlist: {figs}")
    if failures:
        print(f"FAIL: {len(failures)} README claim(s) disagree with the report", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
