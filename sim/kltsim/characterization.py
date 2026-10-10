"""T1 item 8: one aggregated, reproducible characterization report (issue #64).

This module AGGREGATES committed schematic evidence; it simulates nothing and
re-derives nothing. The per-row reductions are ``kltsim.grade``'s (the DR-0002
rules); this module calls its read-only ``grade_campaign`` on an explicitly
named campaign, checks the result against the campaign's committed
``grading.json``, and writes four deterministic artifacts into a NEW report
directory (never into the campaign):

``input-index.json``  the selected evidence paths + sha256 digests, the DR-0002
                      bounds, the DUT identity and the grader digest. Its file
                      hash is the generic envelope's ``provenance.input``
                      ``content_hash`` and the manifest pin.
``report.json``       the machine-readable per-row report.
``report.md``         the same, as a readable table.
``envelope.json``     the ``kind: generic`` / ``t1_item: 8`` envelope.

What the envelope's top-level ``status`` asserts (and what it does not):
``pass`` only if EVERY DR-0002 sub-bound that has a ratified Target bound has
Target verdict PASS on valid, complete, correctly-keyed schematic evidence.
Anything else (FAIL, INCOMPLETE, GAP, INVALID_DUT, REJECTED_EVIDENCE) is
``fail``. It is a circuit-compliance statement about the SCHEMATIC DUT at the
named campaign, mirroring bounded-Target compliance; it is not "report
generation succeeded" and it is not a yield or post-layout claim. Structurally
inconsistent, stale, tampered, non-finite or mixed inputs raise
``CharacterizationError`` and produce no artifacts at all.

Why a freshness check exists: the pinned ``klt signoff`` compares the
envelope's ``provenance.input.content_hash`` with the manifest pin but never
re-hashes a generic envelope's ``source``. ``check`` here re-hashes every
indexed source and the index itself, so a changed record cannot hide behind a
self-reported hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from . import build as build_mod
from . import grade as grade_mod

SCHEMA_INDEX = "sg13g2-comparator/characterization-input-index/1"
SCHEMA_REPORT = "sg13g2-comparator/characterization-report/1"
INDEX_NAME = "input-index.json"
REPORT_JSON_NAME = "report.json"
REPORT_MD_NAME = "report.md"
ENVELOPE_NAME = "envelope.json"
ARTIFACT_NAMES = (INDEX_NAME, REPORT_JSON_NAME, REPORT_MD_NAME, ENVELOPE_NAME)

#: The one explicit selection the repository ships (never "newest").
DEFAULT_CAMPAIGN = "20261009-d73a9ac"

#: Verdicts that are not PASS and must stay distinct (never merged).
VERDICTS = (grade_mod.PASS, grade_mod.FAIL, grade_mod.INCOMPLETE, grade_mod.GAP,
            grade_mod.INVALID_DUT, grade_mod.REJECTED_EVIDENCE, grade_mod.REPORTED,
            grade_mod.NOT_SPECIFIED)

SCOPE = (
    "Schematic DUT only (design/comparator.spice, sim/dut.json provenance "
    "'schematic'). No extracted/post-layout number is in this report; a later "
    "post-layout characterization is a NEW report directory that supersedes this "
    "one by being cited instead of it, and nothing here or in the source campaign "
    "is rewritten."
)

#: Statements the report must carry beside the numbers they qualify.
STATUS_MEANING = (
    "Top-level status 'pass' iff every DR-0002 sub-bound with a ratified Target "
    "has Target verdict PASS on complete, valid schematic evidence; any FAIL, "
    "INCOMPLETE, GAP, INVALID_DUT or REJECTED_EVIDENCE gives 'fail'. A per-row "
    "PASS is a per-point sample statistic against the bound (Row 1: 3 x sample "
    "sigma at N = 60 per point; Row 2: grid-wide mean of probit-slope sigma), "
    "not a yield or population-compliance claim (that is issue #63)."
)

ROW_CAVEATS = {
    "1": [
        "Offset method uncertainty (issue #82, UNRESOLVED): this campaign's "
        "grid-mean 3-sigma offset reads about 13 % above the DR-0002 record "
        "(9.51 vs 8.40 mV, uniform across process corners, undetermined cause). "
        "The Target verdict is the same under either population (met at 45/45); "
        "the Stretch miss is wider here (40/45 vs 27/45). The less favourable of "
        "the two estimates is the one reported; neither population is edited. See "
        "sim/klt-corner-verification/README.md.",
    ],
}


class CharacterizationError(RuntimeError):
    """Inputs are stale, tampered, inconsistent or unusable: no report is made."""


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _dumps(obj) -> str:
    """Deterministic, strict JSON (sorted keys, trailing newline)."""
    return json.dumps(obj, indent=2, sort_keys=True, allow_nan=False,
                      ensure_ascii=True) + "\n"


def _assert_finite(obj, where: str = "grading") -> None:
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise CharacterizationError(f"non-finite number in {where}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_finite(v, f"{where}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_finite(v, f"{where}[{i}]")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise CharacterizationError(f"{path} is outside the repository root {root}") from exc


def _hash_file(rel: str, root: Path) -> str:
    path = root / rel
    if not path.is_file():
        raise CharacterizationError(f"indexed source is missing: {rel}")
    return sha256_bytes(path.read_bytes())


# --------------------------------------------------------------------------- #
# input index
# --------------------------------------------------------------------------- #


def _bench_files(bench_name: str, campaign_rel: str) -> list[tuple[str, str]]:
    """(role, repo-relative path) of one bench's graded chain."""
    from .benches import BENCHES

    bench = BENCHES[bench_name]
    out = [("body", f"{campaign_rel}/{bench_name}.body.spice")]
    for tag in build_mod.part_tags(bench):
        for role in ("envelope", "request", "invocation"):
            out.append((role, f"{campaign_rel}/{tag}.{role}.json"))
    return out


def _retained_paths(grading: dict) -> list[str]:
    paths = []
    for row in grading["rows"]:
        rec = row.get("retained_record") or {}
        if rec.get("path"):
            paths.append(rec["path"])
    return sorted(set(paths))


def build_index(grading: dict, rows_spec: dict, campaign_dir: Path,
                root: Path | None = None) -> dict:
    """The deterministic input index for a graded campaign."""
    root = root or build_mod.REPO_ROOT
    campaign_rel = _rel(campaign_dir, root)
    sources: list[dict] = []
    seen: set[str] = set()

    def add(rel: str, role: str, bench: str | None = None) -> None:
        if rel in seen:
            return
        seen.add(rel)
        entry = {"path": rel, "role": role, "sha256": _hash_file(rel, root)}
        if bench:
            entry["bench"] = bench
        sources.append(entry)

    for bench_name in grading["benches"]:
        for role, rel in _bench_files(bench_name, campaign_rel):
            add(rel, role, bench_name)
    add(f"{campaign_rel}/grading.json", "committed-grading")
    add(f"{campaign_rel}/attempts.jsonl", "attempt-log")
    add("sim/klt-corner-verification/rows.json", "dr0002-row-inventory")
    add("sim/dut.json", "dut-binding")
    add(grading["dut"]["netlist"], "dut-netlist")
    add(rows_spec["spec_source"], "ratified-spec")
    add("sim/kltsim/grade.py", "grader")
    for rel in _retained_paths(grading):
        add(rel, "retained-record")
    sources.sort(key=lambda s: s["path"])

    bounds = [{"id": r["id"], "row": r["row"], "sub_bound": r["sub_bound"],
               "unit": r.get("unit"), "target": r.get("target"),
               "stretch": r.get("stretch")} for r in rows_spec["rows"]]
    return {
        "schema": SCHEMA_INDEX,
        "campaign": campaign_dir.name,
        "campaign_path": campaign_rel,
        "dut": dict(grading["dut"]),
        "grid": rows_spec["grid"],
        "grid_points": grading["grid_points"],
        "spec_source": rows_spec["spec_source"],
        "spec_bounds": bounds,
        "sources": sources,
    }


def verify_index(index: dict, root: Path | None = None) -> list[str]:
    """Re-hash every indexed source; return one problem per stale/tampered/missing."""
    root = root or build_mod.REPO_ROOT
    problems = []
    if index.get("schema") != SCHEMA_INDEX:
        problems.append(f"index schema is {index.get('schema')!r}, expected {SCHEMA_INDEX}")
    for src in index.get("sources") or []:
        path = root / src["path"]
        if not path.is_file():
            problems.append(f"{src['path']}: indexed source is missing")
        elif sha256_bytes(path.read_bytes()) != src["sha256"]:
            problems.append(f"{src['path']}: content differs from the indexed sha256 "
                            f"{src['sha256'][:16]}... (stale or tampered)")
    return problems


# --------------------------------------------------------------------------- #
# grading -> report
# --------------------------------------------------------------------------- #


def validate_grading(grading: dict, rows_spec: dict) -> None:
    """Refuse results that cannot honestly be aggregated at all."""
    _assert_finite(grading)
    spec_ids = [r["id"] for r in rows_spec["rows"]]
    got_ids = [r["id"] for r in grading["rows"]]
    if got_ids != spec_ids:
        raise CharacterizationError(
            f"graded rows {got_ids} are not exactly the DR-0002 inventory {spec_ids}")
    n_points = len(grade_mod.grid_keys(rows_spec["grid"]))
    if grading.get("grid_points") != n_points:
        raise CharacterizationError(
            f"grid_points {grading.get('grid_points')} != ratified grid {n_points}")
    for row in grading["rows"]:
        for column in ("target_verdict", "stretch_verdict"):
            if row.get(column) not in VERDICTS:
                raise CharacterizationError(f"row {row['id']}: unknown {column} {row.get(column)!r}")
        if row["target_verdict"] != grade_mod.PASS and row["stretch_verdict"] == grade_mod.PASS \
                and row.get("target_bound") != "not specified":
            # A Stretch can only be tighter than a Target; PASS beyond a failed
            # Target means the inputs are inconsistent, never favourable.
            if row.get("evidence_kind") == "klt_sim" and row["target_verdict"] != grade_mod.NOT_SPECIFIED:
                raise CharacterizationError(f"row {row['id']}: Stretch PASS with Target {row['target_verdict']}")
        for column in ("target", "stretch"):
            verdict = row[f"{column}_verdict"]
            part = row.get(column)
            if verdict == grade_mod.PASS and part is not None and "points_expected" in part:
                if (part["points_valid"] != part["points_expected"] or part["points_expected"] != n_points
                        or part.get("points_missing_or_invalid")):
                    raise CharacterizationError(
                        f"row {row['id']} {column}: PASS without full valid coverage "
                        f"({part['points_valid']}/{part['points_expected']} of {n_points})")
                if part.get("points_failing"):
                    raise CharacterizationError(f"row {row['id']} {column}: PASS with failing points")
        mc = row.get("monte_carlo_per_point")
        if mc is not None:
            expected = _row_expected_n(rows_spec, row["id"])
            for p in mc:
                if p.get("n") != expected or p.get("errored"):
                    if row["target_verdict"] == grade_mod.PASS or row["stretch_verdict"] == grade_mod.PASS:
                        raise CharacterizationError(
                            f"row {row['id']}: PASS on an inadequate Monte-Carlo population at "
                            f"{p.get('point')} (n={p.get('n')}, expected {expected}, "
                            f"errored={p.get('errored')})")


def _row_expected_n(rows_spec: dict, row_id: str) -> int | None:
    for r in rows_spec["rows"]:
        if r["id"] == row_id:
            n = r["evidence"].get("expected_n")
            return int(n) if n else None
    return None


def _comparable(result: dict) -> dict:
    """Drop the grader's request/invocation-chain bookkeeping (added by issue
    #107 after the committed grading.json was written; an empty problem list
    is the only value that bookkeeping may have for a graded row) so the
    verdicts, values and populations are compared like for like."""
    out = json.loads(json.dumps(result))
    for bench in out.get("benches", {}).values():
        if bench.pop("chain_problems", []):
            bench["chain_problems"] = ["<present>"]
        for env in bench.get("envelopes", []):
            env.pop("chain_checked", None)
    return out


def _column(entry: dict | None, verdict: str, bound: str) -> dict:
    entry = entry or {}
    out = {"bound": bound, "verdict": verdict}
    for key in ("statistic", "points_expected", "points_valid", "points_failing",
                "failing_points", "grid_mean", "binding", "worst_point", "range",
                "points_missing_or_invalid", "partial_mean_ungraded"):
        if key in entry:
            out[key] = entry[key]
    return out


def _population(row: dict, rows_spec: dict) -> dict | None:
    mc = row.get("monte_carlo_per_point")
    if mc is None:
        return None
    ns = [p.get("n") for p in mc]
    return {
        "points": len(mc),
        "n_per_point_expected": _row_expected_n(rows_spec, row["id"]),
        "n_per_point_min": min(ns) if ns else None,
        "n_per_point_max": max(ns) if ns else None,
        "draws_total": sum(n for n in ns if isinstance(n, int)),
        "errored_total": sum(p.get("errored") or 0 for p in mc),
    }


def _row_sources(row: dict, index: dict) -> list[dict]:
    bench = row.get("bench")
    out = []
    for src in index["sources"]:
        if bench and src.get("bench") == bench:
            out.append(src)
        elif src["role"] in ("dr0002-row-inventory", "dut-netlist", "committed-grading"):
            out.append(src)
        elif src["role"] == "retained-record" and \
                src["path"] == (row.get("retained_record") or {}).get("path"):
            out.append(src)
    return out


def _derived(row: dict) -> dict:
    """Value summaries that are pure functions of the graded row."""
    out = {}
    mc = row.get("monte_carlo_per_point")
    if row["id"] == "1" and mc:
        vals = [p["three_sigma_dr_basis"] for p in mc if p.get("three_sigma_dr_basis") is not None]
        if vals:
            out["grid_mean_of_per_point_3sigma"] = sum(vals) / len(vals)
    return out


def build_report(grading: dict, rows_spec: dict, index: dict, index_sha256: str,
                 index_rel: str) -> dict:
    validate_grading(grading, rows_spec)
    rows = []
    for g in grading["rows"]:
        row = {
            "id": g["id"], "row": g["row"], "sub_bound": g["sub_bound"], "unit": g.get("unit"),
            "condition": g["condition"], "statistical_basis": g["statistical_basis"],
            "evidence_kind": g["evidence_kind"], "bench": g.get("bench"),
            "measurement": g.get("measurement"),
            "target": _column(g.get("target"), g["target_verdict"], g["target_bound"]),
            "stretch": _column(g.get("stretch"), g["stretch_verdict"], g["stretch_bound"]),
            "report_verdict": g.get("report_verdict"),
            "population": _population(g, rows_spec),
            "derived": _derived(g),
            "retained_record": g.get("retained_record"),
            "tool_gap": g.get("tool_gap"),
            "gap_reason": g.get("gap_reason"),
            "chain_problems": g.get("chain_problems") or [],
            "dut_problems": g.get("dut_problems") or [],
            "coverage_problems": g.get("coverage_problems") or [],
            "benches_fully_covered": g.get("benches_fully_covered"),
            "klt_window_note": g.get("klt_window_note"),
            "notes": list(g.get("notes") or []) + ROW_CAVEATS.get(g["id"], []),
            "sources": [{"path": s["path"], "sha256": s["sha256"], "role": s["role"]}
                        for s in _row_sources(g, index)],
        }
        rows.append(row)
    bounded = [r for r in rows if r["target"]["verdict"] != grade_mod.NOT_SPECIFIED]
    passing = [r["id"] for r in bounded if r["target"]["verdict"] == grade_mod.PASS]
    blocking = [{"id": r["id"], "sub_bound": r["sub_bound"], "target_verdict": r["target"]["verdict"]}
                for r in bounded if r["target"]["verdict"] != grade_mod.PASS]
    if not bounded:
        raise CharacterizationError("no DR-0002 sub-bound has a ratified Target bound")
    all_pass = not blocking
    counts = {}
    for column in ("target", "stretch"):
        c: dict[str, int] = {}
        for r in rows:
            c[r[column]["verdict"]] = c.get(r[column]["verdict"], 0) + 1
        counts[column] = dict(sorted(c.items()))
    return {
        "schema": SCHEMA_REPORT,
        "t1_item": 8,
        "campaign": grading["campaign"],
        "scope": SCOPE,
        "status_meaning": STATUS_MEANING,
        "dut": grading["dut"],
        "grid_points": grading["grid_points"],
        "spec_source": rows_spec["spec_source"],
        "input_index": {"path": index_rel, "sha256": index_sha256},
        "status": "pass" if all_pass else "fail",
        "target_compliance": {
            "bounded_target_rows": [r["id"] for r in bounded],
            "passing": passing,
            "blocking": blocking,
            "all_bounded_targets_pass": all_pass,
        },
        "verdict_counts": counts,
        "rows": rows,
    }


def build_envelope(report: dict, index_sha256: str, index_rel: str, report_md_rel: str) -> dict:
    blocking = report["target_compliance"]["blocking"]
    if blocking:
        detail = "; ".join(f"Row {b['id']} Target {b['target_verdict']}" for b in blocking)
        summary = (f"Schematic characterization of campaign {report['campaign']}: "
                   f"{len(report['target_compliance']['passing'])}/"
                   f"{len(report['target_compliance']['bounded_target_rows'])} bounded DR-0002 "
                   f"Targets pass; blocking: {detail}.")
    else:
        summary = (f"Schematic characterization of campaign {report['campaign']}: every "
                   "bounded DR-0002 Target passes on schematic evidence.")
    return {
        "schema_version": 1,
        "kind": "generic",
        "t1_item": 8,
        "status": report["status"],
        "summary": summary + " Schematic-only scope; per-row PASS is not a yield claim.",
        "source": report_md_rel,
        "status_meaning": STATUS_MEANING,
        "provenance": {
            "input": {
                "content_hash": "sha256:" + index_sha256,
                "role": "characterization-input-index",
                "path": index_rel,
            },
            "generator": "sim/kltsim/characterization.py",
            "campaign": report["campaign"],
        },
    }


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #


def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def _value_text(col: dict, row: dict) -> str:
    rng = col.get("range")
    if not rng:
        if row["evidence_kind"] == "gap":
            return (row.get("retained_record") or {}).get("recorded_value", "-")
        if row["evidence_kind"] == "coverage":
            return "benches fully covered: " + (", ".join(row.get("benches_fully_covered") or []) or "none")
        return "-"
    pre = ""
    if col.get("grid_mean") is not None:
        pre = f"grid-wide mean {_fmt(col['grid_mean'])}; per point "
    elif col.get("partial_mean_ungraded") is not None:
        pre = f"partial mean {_fmt(col['partial_mean_ungraded'])} (UNGRADED); per point "
    return (f"{pre}{_fmt(rng['min']['value'])} ({rng['min']['point']}) ... "
            f"{_fmt(rng['max']['value'])} ({rng['max']['point']}); "
            f"{col['points_valid']}/{col['points_expected']} valid")


def _binding_text(row: dict) -> str:
    for name in ("target", "stretch"):
        b = row[name].get("binding")
        if b:
            worst = row[name].get("worst_point")
            tail = f"; worst single point {worst['point']} ({_fmt(worst['value'])})" if worst else ""
            return f"{b['point']} ({_fmt(b['value'])}){tail}"
    return "-"


def _pop_text(row: dict) -> str:
    pop = row.get("population")
    if not pop:
        return "deterministic (no MC)"
    return (f"{pop['points']} pts x N={pop['n_per_point_min']}"
            f"{'' if pop['n_per_point_min'] == pop['n_per_point_max'] else '..' + str(pop['n_per_point_max'])}"
            f" (expected {pop['n_per_point_expected']}); {pop['draws_total']} draws, "
            f"{pop['errored_total']} errored")


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict) -> str:
    tc = report["target_compliance"]
    lines = [
        f"# Characterization report -- T1 item 8 -- campaign `{report['campaign']}`",
        "",
        "GENERATED by `sim/characterize.sh report` (`sim/kltsim/characterization.py`) from",
        "committed evidence only; do not edit. Reproduce and freshness-check with",
        "`sim/characterize.sh report` / `sim/characterize.sh report check`.",
        "",
        f"**Scope.** {report['scope']}",
        "",
        f"**Status: `{report['status']}`.** {report['status_meaning']}",
        "",
        f"DUT `{report['dut']['netlist']}` sha256 `{report['dut']['sha256']}` "
        f"(`sim/dut.json` id `{report['dut']['dut_json_id']}`, provenance "
        f"`{report['dut']['provenance']}`); grid {report['grid_points']} PVT points; spec "
        f"`{report['spec_source']}`; input index `{report['input_index']['path']}` sha256 "
        f"`{report['input_index']['sha256']}`.",
        "",
        f"Bounded Target rows: {', '.join(tc['bounded_target_rows'])}; passing: "
        f"{', '.join(tc['passing']) or 'none'}; blocking: "
        + ("; ".join(f"Row {b['id']} ({b['target_verdict']})" for b in tc["blocking"]) or "none") + ".",
        "",
        "| Row | Sub-bound | Unit | Target | Target verdict | Stretch | Stretch verdict | Value (Target column) | Binding | Population / basis | Sources |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report["rows"]:
        tv = r["target"]["verdict"]
        if r.get("report_verdict"):
            tv += f" (reporting requirement: {r['report_verdict']})"
        srcs = ", ".join(f"`{s['path'].rsplit('/', 1)[-1]}`@{s['sha256'][:8]}"
                         for s in r["sources"] if s["role"] in ("envelope", "retained-record"))
        if not srcs:
            srcs = "see the Row sources section"
        lines.append("| " + " | ".join(_cell(x) for x in (
            r["id"], r["sub_bound"], r.get("unit") or "-", r["target"]["bound"], f"**{tv}**",
            r["stretch"]["bound"], f"**{r['stretch']['verdict']}**",
            _value_text(r["target"], r), _binding_text(r),
            f"{_pop_text(r)}; {r['statistical_basis']}", srcs)) + " |")
    lines += ["", "## Conditions and per-row notes", ""]
    for r in report["rows"]:
        lines.append(f"- **{r['id']} {r['row']}** -- conditions: {r['condition']}")
        for name in ("target", "stretch"):
            fp = r[name].get("failing_points")
            if fp:
                lines.append(f"  - {name} fails at {len(fp)} point(s): {', '.join(fp)}")
        if r["derived"]:
            for k, v in r["derived"].items():
                lines.append(f"  - derived `{k}` = {_fmt(v)} (informational; the graded statistic is the worst point)")
        if r.get("klt_window_note"):
            lines.append(f"  - {r['klt_window_note']}")
        if r.get("retained_record"):
            rec = r["retained_record"]
            lines.append(f"  - retained non-klt record `{rec.get('path')}`: {rec.get('recorded_value')} "
                         f"(Target {rec.get('recorded_verdict_target')}, Stretch "
                         f"{rec.get('recorded_verdict_stretch')})")
        if r.get("tool_gap"):
            lines.append(f"  - tool gap: {r['tool_gap']}")
        for key in ("gap_reason",):
            if r.get(key):
                lines.append(f"  - GAP: {r[key]}")
        for key, label in (("chain_problems", "rejected evidence"), ("dut_problems", "wrong DUT"),
                           ("coverage_problems", "coverage problem")):
            for p in r.get(key) or []:
                lines.append(f"  - {label}: {p}")
        for n in r["notes"]:
            lines.append(f"  - note: {n}")
    lines += ["", "## Row sources (repo-relative path, sha256)", ""]
    for r in report["rows"]:
        lines.append(f"- **{r['id']}**")
        for s in r["sources"]:
            lines.append(f"  - `{s['path']}` `{s['sha256']}` ({s['role']})")
    lines += ["", "## Superseding this report", "",
              "This report covers the schematic DUT. A post-layout (extracted-netlist)",
              "characterization is generated into a new, separately named directory under",
              "`sim/characterization/` from its own campaign, and the manifest's item 8",
              "citation is repointed to it in one change. This directory and the source",
              "campaign are never edited.", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #


def default_out_dir(campaign_id: str, root: Path | None = None) -> Path:
    return (root or build_mod.REPO_ROOT) / "sim" / "characterization" / f"{campaign_id}-schematic"


def build_artifacts(campaign_dir: Path, out_dir: Path, root: Path | None = None,
                    grading: dict | None = None, rows_spec: dict | None = None) -> dict[str, bytes]:
    """Return {filename: bytes} for the four artifacts. Writes nothing.

    ``grading`` / ``rows_spec`` are injectable for tests; by default the
    campaign is graded by the committed grader and must equal its committed
    ``grading.json`` (a stale or hand-edited grading.json is refused).
    """
    root = root or build_mod.REPO_ROOT
    campaign_dir = Path(campaign_dir)
    if not campaign_dir.is_dir():
        raise CharacterizationError(f"campaign directory {campaign_dir} does not exist")
    if rows_spec is None:
        rows_spec = json.loads((root / "sim/klt-corner-verification/rows.json").read_text(encoding="utf-8"))
    if grading is None:
        grading = grade_mod.grade_campaign(campaign_dir)
        committed_path = campaign_dir / "grading.json"
        if not committed_path.is_file():
            raise CharacterizationError(f"{committed_path} is missing")
        committed = json.loads(committed_path.read_text(encoding="utf-8"))
        if _comparable(json.loads(grade_mod.dumps_strict(grading))) != _comparable(committed):
            raise CharacterizationError(
                "fresh grading of the campaign differs from its committed grading.json "
                "(stale grading, or evidence/DUT/grader changed since it was written)")
    if grading.get("campaign") != campaign_dir.name:
        raise CharacterizationError("grading names a different campaign than the one selected")
    index = build_index(grading, rows_spec, campaign_dir, root)
    if grading["dut"]["sha256"] != _hash_file(grading["dut"]["netlist"], root):
        raise CharacterizationError("graded DUT digest does not match the DUT netlist on disk")
    index_text = _dumps(index)
    index_sha = sha256_bytes(index_text.encode("utf-8"))
    out_rel = _rel(out_dir, root)
    index_rel = f"{out_rel}/{INDEX_NAME}"
    report = build_report(grading, rows_spec, index, index_sha, index_rel)
    envelope = build_envelope(report, index_sha, index_rel, f"{out_rel}/{REPORT_MD_NAME}")
    return {
        INDEX_NAME: index_text.encode("utf-8"),
        REPORT_JSON_NAME: _dumps(report).encode("utf-8"),
        REPORT_MD_NAME: render_markdown(report).encode("utf-8"),
        ENVELOPE_NAME: _dumps(envelope).encode("utf-8"),
    }


def generate(campaign_dir: Path, out_dir: Path, root: Path | None = None) -> dict[str, bytes]:
    artifacts = build_artifacts(campaign_dir, out_dir, root)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        (out_dir / name).write_bytes(data)
    return artifacts


def check(campaign_dir: Path, out_dir: Path, root: Path | None = None,
          manifest: Path | None = None) -> list[str]:
    """Freshness check; returns problems (empty = fresh). Writes nothing."""
    root = root or build_mod.REPO_ROOT
    problems: list[str] = []
    committed = {}
    for name in ARTIFACT_NAMES:
        p = out_dir / name
        if not p.is_file():
            problems.append(f"{name}: committed artifact is missing")
        else:
            committed[name] = p.read_bytes()
    if problems:
        return problems
    try:
        index = json.loads(committed[INDEX_NAME])
        problems += [f"index: {p}" for p in verify_index(index, root)]
        envelope = json.loads(committed[ENVELOPE_NAME])
    except ValueError as exc:
        return [f"committed artifact is not valid JSON: {exc}"]
    pinned = "sha256:" + sha256_bytes(committed[INDEX_NAME])
    got = ((envelope.get("provenance") or {}).get("input") or {}).get("content_hash")
    if got != pinned:
        problems.append(f"envelope provenance.input.content_hash {got} != index file hash {pinned}")
    if envelope.get("kind") != "generic" or envelope.get("t1_item") != 8 \
            or envelope.get("schema_version") != 1:
        problems.append("envelope is not schema_version 1 / kind generic / t1_item 8")
    if problems:
        return problems
    try:
        fresh = build_artifacts(campaign_dir, out_dir, root)
    except CharacterizationError as exc:
        return [str(exc)]
    for name, data in fresh.items():
        if committed[name] != data:
            problems.append(f"{name}: differs from a fresh regeneration (stale; run "
                            "`sim/characterize.sh report`)")
    if manifest is not None:
        cited = json.loads(Path(manifest).read_text(encoding="utf-8"))["evidence"].get("8")
        want_file = _rel(out_dir / ENVELOPE_NAME, root)
        want_hash = "sha256:" + sha256_bytes(committed[INDEX_NAME])
        if not isinstance(cited, dict) or cited.get("file") != want_file \
                or cited.get("content_hash") != want_hash:
            problems.append(f"manifest item 8 citation {cited!r} != "
                            f"{{file: {want_file}, content_hash: {want_hash}}}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, help_ in (("generate", "write the four artifacts into the report directory"),
                        ("check", "fail if the committed artifacts / indexed sources are stale")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--campaign", required=True,
                       help="explicit campaign id under sim/klt-corner-verification/campaigns/")
        p.add_argument("--out", help="report directory (default sim/characterization/<campaign>-schematic)")
        if name == "check":
            p.add_argument("--manifest", help="also require the manifest's item 8 citation to match")
    args = ap.parse_args(argv)
    campaign_dir = build_mod.EXPERIMENT_DIR / "campaigns" / args.campaign
    out_dir = Path(args.out).resolve() if args.out else default_out_dir(args.campaign)
    try:
        if args.cmd == "generate":
            art = generate(campaign_dir, out_dir)
            rep = json.loads(art[REPORT_JSON_NAME])
            print(f"wrote {_rel(out_dir, build_mod.REPO_ROOT)}/ ({', '.join(ARTIFACT_NAMES)})")
            print(f"envelope status: {rep['status']}; blocking: "
                  + (", ".join(f"Row {b['id']} {b['target_verdict']}"
                               for b in rep['target_compliance']['blocking']) or "none"))
            return 0
        problems = check(campaign_dir, out_dir, manifest=Path(args.manifest) if args.manifest else None)
    except CharacterizationError as exc:
        print(f"characterization: REFUSED: {exc}", file=sys.stderr)
        return 1
    if problems:
        for p in problems:
            print(f"characterization: STALE: {p}", file=sys.stderr)
        return 1
    print("characterization: fresh (index re-hashed, artifacts regenerate byte-for-byte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
