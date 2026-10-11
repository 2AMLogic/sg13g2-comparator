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

A second, separate table (`SOURCE_CLAIMS`, issue #193) maps claims that quote a
DIFFERENT evidence population than the aggregated report to their own reviewed
source, named per claim through the `SOURCES` registry:

  * `noise-full-issue81`  -- the issue #81 complete-injection campaign summary
    `sim/klt-corner-verification/campaigns/20261009-issue81/noise_full.json`
    (README "Current evidence" noise figures: N, valid points, grid mean/min/max,
    front-end-only term, internal-term estimate; configuration `both`).
  * `offset-whole-latch-ea40b57` -- the DR-0002 whole-latch offset record
    `sim/comparator-offset-transient-mc/records/20260917-060858-ea40b57.json`
    (its machine-readable twin of the `.md` record the README cites): 3 sigma
    min/max/mean, Target/Stretch point counts, N per point.

Each source is identity-checked before any figure is compared (record/campaign
id, bench name, N, point count), so a changed or substituted campaign cannot
satisfy a claim by coincidence; failures name the claim, the source id/path and
the expected value. Only committed files are read (stdlib, offline).

Anything in the table that is NOT in either allowlist is listed as UNCHECKED,
never silently passed: every `N/45`, `N of 45` count, and the number of
unit-bearing figures (fC, uV, mV, ns, ps, uW) not covered by a claim. Still
unmapped (no reliable source mapping reviewed): the front-end-only offset
record, the common-mode characterization, the historical `.noise`/TRNOISE
figures, the earlier power record, and the Monte-Carlo seeds. Mapping more is a
spec/curation question, not something this guard decides.

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

# --------------------------------------------------------------------------
# Per-claim source registry (issue #193). Each entry is a reviewed evidence
# population: `path`, the identity it must carry, and a loader that validates
# structure and returns {statistic name: value}. Claims below name a source id.
# --------------------------------------------------------------------------
NOISE_PATH = (REPO_ROOT / "sim" / "klt-corner-verification" / "campaigns"
              / "20261009-issue81" / "noise_full.json")
OFFSET_PATH = (REPO_ROOT / "sim" / "comparator-offset-transient-mc" / "records"
               / "20260917-060858-ea40b57.json")

#: Ratified whole-latch offset limits (3 sigma, mV): Target <= 15, Stretch <= 8.
OFFSET_TARGET_MV, OFFSET_STRETCH_MV = 15.0, 8.0
#: Grid size of every PVT campaign this guard maps.
N_POINTS = 45


class SourceError(Exception):
    """A registered evidence source is missing, malformed or the wrong population."""


def _need(node, *keys):
    """Walk `keys` through nested dicts; SourceError naming the missing field."""
    cur = node
    for i, k in enumerate(keys):
        if not isinstance(cur, dict) or k not in cur:
            raise SourceError(f"missing field {'.'.join(map(str, keys[:i + 1]))}")
        cur = cur[k]
    return cur


def _num(node, *keys) -> float:
    v = _need(node, *keys)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise SourceError(f"field {'.'.join(map(str, keys))} is not a number: {v!r}")
    return float(v)


def _expect(cond: bool, msg: str):
    if not cond:
        raise SourceError(msg)


def _read_json(path: Path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise SourceError(f"cannot read: {exc.strerror or exc}") from None
    except ValueError as exc:
        raise SourceError(f"not valid JSON: {exc}") from None


def load_noise_full(path: Path) -> dict:
    """Issue #81 complete-injection noise summary (`both` = whole injection)."""
    d = _read_json(path)
    _expect(isinstance(d, dict), "top level is not an object")
    _expect(_need(d, "campaign") == "20261009-issue81",
            f"campaign is {d.get('campaign')!r}, expected '20261009-issue81'")
    n = _need(d, "expected_n")
    _expect(n == 80, f"expected_n is {n!r}, expected 80 trials per rung")
    pts = _need(d, "points")
    _expect(isinstance(pts, list) and len(pts) == N_POINTS,
            f"points has {len(pts) if isinstance(pts, list) else '?'} entries, expected {N_POINTS}")
    both = _need(d, "configs", "both")
    _need(d, "configs", "fe")
    for i, p in enumerate(pts):
        _expect(_need(p, "both", "n") == n,
                f"point {i} ({p.get('point')!r}) has both.n != expected_n {n}")
    sig = [_num(p, "both", "sigma") for p in pts if p["both"].get("sigma") is not None]
    _expect(_need(both, "points_valid") == len(sig),
            f"configs.both.points_valid {both['points_valid']} != {len(sig)} valid points in points[]")
    _expect(_need(both, "complete") is True, "configs.both is not complete")
    stats = {
        "n": n,
        "valid": _need(both, "points_valid"),
        "expected": _need(both, "points_expected"),
        "mean": _num(d, "configs", "both", "grid_mean"),
        "min": _num(d, "configs", "both", "min"),
        "max": _num(d, "configs", "both", "max"),
        "fe_mean": _num(d, "configs", "fe", "grid_mean"),
        "internal_1x": _num(d, "split_grid", "mean_internal_1x_from_x8"),
    }
    _expect(abs(stats["mean"] - sum(sig) / len(sig)) < 1e-9
            and abs(stats["min"] - min(sig)) < 1e-9 and abs(stats["max"] - max(sig)) < 1e-9,
            "configs.both grid_mean/min/max disagree with the per-point sigmas")
    return stats


def load_offset_record(path: Path) -> dict:
    """DR-0002 whole-latch transient Monte-Carlo offset record (45 points, N=60)."""
    d = _read_json(path)
    _expect(isinstance(d, dict), "top level is not an object")
    _expect(_need(d, "record_id") == "20260917-060858-ea40b57",
            f"record_id is {d.get('record_id')!r}, expected '20260917-060858-ea40b57'")
    _expect(_need(d, "testbench", "name") == "comparator-offset-transient-mc",
            f"testbench is {d['testbench']['name']!r}, expected 'comparator-offset-transient-mc'")
    pts = _need(d, "points")
    _expect(isinstance(pts, list) and len(pts) == N_POINTS,
            f"points has {len(pts) if isinstance(pts, list) else '?'} entries, expected {N_POINTS}")
    v3, ids = [], []
    for i, p in enumerate(pts):
        _expect(_need(p, "status") == "ok", f"point {i} status is {p['status']!r}")
        _expect(_num(p, "measurements", "n_samples") == 60,
                f"point {i} ({p.get('corner_id')!r}) n_samples != 60")
        v3.append(_num(p, "measurements", "vos_3sig_mv"))
        ids.append(_need(p, "corner_id"))
    _expect(len(set(ids)) == N_POINTS, "corner_ids are not 45 distinct points")
    summ = _need(d, "summary", "vos_3sig_mv")
    stats = {
        "n_samples": 60,
        "points": len(pts),
        "min": _num(summ, "min"), "max": _num(summ, "max"), "mean": _num(summ, "mean"),
        "min_point": _need(summ, "at_min"), "max_point": _need(summ, "at_max"),
        "target_met": sum(x <= OFFSET_TARGET_MV for x in v3),
        "stretch_missed": sum(x > OFFSET_STRETCH_MV for x in v3),
        "record_id": d["record_id"],
    }
    _expect(abs(stats["min"] - min(v3)) < 1e-6 and abs(stats["max"] - max(v3)) < 1e-6
            and abs(stats["mean"] - sum(v3) / len(v3)) < 1e-6
            and ids[v3.index(min(v3))] == stats["min_point"]
            and ids[v3.index(max(v3))] == stats["max_point"],
            "summary.vos_3sig_mv min/max/mean/at_* disagree with the per-point values")
    return stats


#: id -> (default path, loader). The reviewed population list; adding a source
#: or changing which population a claim reads is a deliberate edit here.
SOURCES = {
    "noise-full-issue81": (NOISE_PATH, load_noise_full),
    "offset-whole-latch-ea40b57": (OFFSET_PATH, load_offset_record),
}

_NOISE = "| Input-referred noise"
_OFF = "| Offset sigma"
_CUR = r"complete-injection campaign.*?"  # anchors a pattern to the issue #81 text
_WL = r"Whole latch \([^)]*\): "          # anchors a pattern to the whole-latch figures
# (name, source id, row prefix, column, regex with one group, statistic, kind)
SOURCE_CLAIMS = [
    ("noise(#81): N trials per rung", "noise-full-issue81", _NOISE, 3,
     _CUR + r"N = (\d+) trials per rung", "n", "int"),
    ("noise(#81): valid points", "noise-full-issue81", _NOISE, 3,
     r"\*\*(\d+)/\d+ valid points, grid-wide mean", "valid", "int"),
    ("noise(#81): grid points", "noise-full-issue81", _NOISE, 3,
     r"\*\*\d+/(\d+) valid points, grid-wide mean", "expected", "int"),
    ("noise(#81): grid mean mV rms", "noise-full-issue81", _NOISE, 3,
     r"valid points, grid-wide mean ([\d.]+) mV rms\*\*", "mean", "num"),
    ("noise(#81): grid min mV rms", "noise-full-issue81", _NOISE, 3,
     r"valid points, grid-wide mean [\d.]+ mV rms\*\* \(min ([\d.]+) … max", "min", "num"),
    ("noise(#81): grid max mV rms", "noise-full-issue81", _NOISE, 3,
     r"valid points, grid-wide mean [\d.]+ mV rms\*\* \(min [\d.]+ … max ([\d.]+) mV\)",
     "max", "num"),
    ("noise(#81): front-end-only term mV", "noise-full-issue81", _NOISE, 3,
     r"front-end-only term \(([\d.]+) mV\)", "fe_mean", "num"),
    ("noise(#81): internal-term estimate mV", "noise-full-issue81", _NOISE, 3,
     r"internal term alone is ([\d.]+) mV", "internal_1x", "num"),
    ("offset(whole latch): cited record id", "offset-whole-latch-ea40b57", _OFF, 3,
     r"Stretch at \d+/\d+\. Record \[`([^`]+)`\]", "record_id", "str"),
    ("offset(whole latch): Target met points", "offset-whole-latch-ea40b57", _OFF, 3,
     r"Target MET at (\d+)/\d+ points on the whole latch", "target_met", "int"),
    ("offset(whole latch): Target points in grid", "offset-whole-latch-ea40b57", _OFF, 3,
     r"Target MET at \d+/(\d+) points on the whole latch", "points", "int"),
    ("offset(whole latch): points inside Target", "offset-whole-latch-ea40b57", _OFF, 3,
     r"inside the 15 mV Target at every one of the (\d+) points", "target_met", "int"),
    ("offset(whole latch): Stretch missed points", "offset-whole-latch-ea40b57", _OFF, 3,
     r"Stretch NOT MET at (\d+)/\d+\.\*\* Whole latch", "stretch_missed", "int"),
    ("offset(whole latch): Stretch missed (prose)", "offset-whole-latch-ea40b57", _OFF, 3,
     r"above the 8 mV Stretch at (\d+)/\d+\.", "stretch_missed", "int"),
    ("offset(whole latch): 3 sigma min mV", "offset-whole-latch-ea40b57", _OFF, 3,
     _WL + r"3σ ([\d.]+) mV \(`[^`]+`\) … ", "min", "num"),
    ("offset(whole latch): 3 sigma min point", "offset-whole-latch-ea40b57", _OFF, 3,
     _WL + r"3σ [\d.]+ mV \(`([^`]+)`\) … ", "min_point", "str"),
    ("offset(whole latch): 3 sigma max mV", "offset-whole-latch-ea40b57", _OFF, 3,
     _WL + r"3σ [\d.]+ mV \(`[^`]+`\) … \*\*([\d.]+) mV\*\*", "max", "num"),
    ("offset(whole latch): 3 sigma max point", "offset-whole-latch-ea40b57", _OFF, 3,
     _WL + r"3σ [\d.]+ mV \(`[^`]+`\) … \*\*[\d.]+ mV\*\* \(`([^`]+)`\)", "max_point", "str"),
    ("offset(whole latch): 3 sigma mean mV", "offset-whole-latch-ea40b57", _OFF, 3,
     _WL + r"3σ [\d.]+ mV \(`[^`]+`\) … \*\*[\d.]+ mV\*\* \(`[^`]+`\), mean ([\d.]+) mV",
     "mean", "num"),
    ("offset(whole latch): N draws per point", "offset-whole-latch-ea40b57", _OFF, 1,
     r"whole-latch `comparator-offset-transient-mc`: N = (\d+) draws per point",
     "n_samples", "int"),
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


def load_sources(paths: dict | None = None):
    """Load every registered source: {id: stats dict | SourceError}."""
    paths = paths or {}
    out = {}
    for sid, (default, loader) in SOURCES.items():
        path = Path(paths.get(sid, default))
        try:
            out[sid] = loader(path)
        except SourceError as exc:
            out[sid] = SourceError(f"{path}: {exc}")
    return out


def check_sources(rows, sources, source_claims=SOURCE_CLAIMS):
    """Check SOURCE_CLAIMS against the loaded sources.

    Returns (failures, checked, covered) where covered maps
    (row idx, 3) -> spans in the Measured cell, for UNCHECKED accounting.
    """
    failures, checked, covered = [], 0, {}
    for sid, src in sources.items():
        if isinstance(src, SourceError):
            failures.append(f"source {sid}: {src.args[0]}")
    for name, sid, prefix, col, pattern, stat, kind in source_claims:
        idx = next((i for i, ln in enumerate(rows) if ln.startswith(prefix)), None)
        if idx is None:
            failures.append(f"{name} [source {sid}]: README table row {prefix!r} not found")
            continue
        cells = [c.strip() for c in rows[idx].strip().strip("|").split(" | ")]
        cell = cells[col] if len(cells) > col else ""
        m = re.search(pattern, cell, re.S)
        if not m:
            failures.append(f"{name} [source {sid}]: pattern {pattern!r} no longer matches the README")
            continue
        src = sources.get(sid)
        if src is None or isinstance(src, SourceError):
            failures.append(f"{name}: source {sid} unavailable, claim {m.group(1)!r} cannot be verified")
            continue
        if stat not in src:
            failures.append(f"{name} [source {sid}]: source has no statistic {stat!r}")
            continue
        raw, claimed = src[stat], m.group(1)
        if kind == "int":
            ok, shown = int(claimed) == raw, str(raw)
        elif kind == "num":
            shown = _round_to(raw, claimed)
            ok = shown == claimed
        else:
            ok, shown = claimed == raw, str(raw)
        checked += 1
        covered.setdefault((idx, col), set()).add(m.span(1))
        if not ok:
            failures.append(f"{name}: README says {claimed}, source {sid} ({stat}) says {shown}")
    return failures, checked, covered


def check(readme_text: str, report: dict, claims=CLAIMS, sources=None,
          source_claims=SOURCE_CLAIMS):
    """Return (failures, checked, unchecked, source_checked).

    `sources` is load_sources() output; None skips the source-registry claims.
    Failures are printable strings.
    """
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
    source_checked = 0
    if sources is not None:
        sf, source_checked, scov = check_sources(rows, sources, source_claims)
        failures += sf
        for (i, col), spans in scov.items():
            if col == MEASURED_COLUMN:
                covered.setdefault((i, 0), set()).update(spans)
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
    return failures, checked, unchecked, source_checked


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--readme", type=Path, default=DEFAULT_README)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--noise-full", type=Path, default=NOISE_PATH,
                    help="issue #81 noise_full.json (source noise-full-issue81)")
    ap.add_argument("--offset-record", type=Path, default=OFFSET_PATH,
                    help="whole-latch offset record JSON (source offset-whole-latch-ea40b57)")
    args = ap.parse_args(argv)
    try:
        text = args.readme.read_text(encoding="utf-8")
        report = load_report(args.report)
    except (OSError, ValueError) as exc:
        print(f"FAIL: cannot read inputs: {exc}", file=sys.stderr)
        return 1
    sources = load_sources({"noise-full-issue81": args.noise_full,
                            "offset-whole-latch-ea40b57": args.offset_record})
    failures, checked, unchecked, src_checked = check(text, report, sources=sources)
    for f in failures:
        print(f"FAIL: {f}", file=sys.stderr)
    counts = [u for u in unchecked if _COUNT_RE.fullmatch(u[1])]
    figs = len(unchecked) - len(counts)
    print(f"checked {checked}/{len(CLAIMS)} allowlisted README claims against {args.report.name}")
    ids = ", ".join(sorted(SOURCES))
    print(f"checked {src_checked}/{len(SOURCE_CLAIMS)} source-registry README claims against {ids}")
    for row, c in counts:
        print(f"UNCHECKED count in row {row!r}: {c}")
    print(f"UNCHECKED unit-bearing figures not in the allowlist: {figs}")
    if failures:
        print(f"FAIL: {len(failures)} README claim(s) disagree with their evidence", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
