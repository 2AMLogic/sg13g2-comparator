"""Pre-submission evidence-size estimate for a larger offset campaign (issue #167).

The budget (``sim/evidence-size-budget.json``, ``scripts/check_evidence_size.py``)
caps a NEW evidence unit and all of ``sim/``; going over needs a decision record
and an exact exception, so the size is estimated from a committed reference
campaign BEFORE submission. Blob bytes (``git ls-tree -rl``) and metadata are
read from the selected tree, never the working tree.

Model: per-sample files (envelope, per-corner artifacts) scale linearly with N
over the reference's own declared N (#247); bodies, requests and invocations are
fixed. An estimate: the checker's measurement of the committed result rules.
"""

from __future__ import annotations

import json
import subprocess

from . import build as build_mod

CAMPAIGNS = "sim/klt-corner-verification/campaigns"
BUDGET = "sim/evidence-size-budget.json"
#: Files of the new campaign unit that do not scale with N.
FIXED_SUFFIXES = (".body.spice", ".request.json", ".invocation.json")
#: grading.json/md and attempts log of the new campaign: small, bounded.
GRADING_ALLOWANCE = 200_000
#: Yield campaign (inputs + report + index): per-sample values scale with N.
YIELD_REFERENCE = "sim/klt-yield/campaigns/20261010-d73a9ac"
#: Its per-measurement ``n`` is the yield denominator.
YIELD_OFFSET_REPORT = f"{YIELD_REFERENCE}/offset.yield.json"
OFFSET_PARTS = ("tt", "ff", "fs", "sf", "ss")


class EstimateError(Exception):
    pass


def _git(*args: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(build_mod.REPO_ROOT), *args], capture_output=True, check=False)
    if proc.returncode != 0:
        raise EstimateError(f"git {args[0]} {args[-1]} failed: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def _ls_tree(tree: str, path: str) -> list[tuple[str, int]]:
    recs = [r.partition(b"\t") for r in _git("ls-tree", "-r", "-l", "-z", tree, path).split(b"\0") if r]
    return [(name.decode(), int(meta.split()[3])) for meta, _, name in recs]


def _n(value, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 2:
        raise EstimateError(f"{what} is not a valid draw count (integer >= 2): {value!r}")
    return value


def _one(ns: dict, what: str) -> int:
    if len(set(ns.values())) != 1:
        raise EstimateError(f"{what} declares conflicting draw counts: {ns}")
    return next(iter(ns.values()))


def reference_offset_n(reference: str, tree: str, read=None) -> int:
    """``monte_carlo.n`` of every part's committed request at ``tree``; all must
    agree, else an error (never a default). ``read(path)``: bytes at the tree."""
    read = read or (lambda p: _git("show", f"{tree}:{p}"))
    found = {}
    for part in OFFSET_PARTS:
        path = f"{CAMPAIGNS}/{reference}/offset_mc.mos_{part}_mismatch.request.json"
        try:
            found[part] = _n(json.loads(read(path))["monte_carlo"]["n"], f"{path} monte_carlo.n")
        except (ValueError, KeyError, TypeError) as exc:
            raise EstimateError(f"{path} at {tree} declares no valid monte_carlo.n: {exc!r}") from exc
    return _one(found, f"reference {reference} at {tree}")


def reference_yield_n(tree: str, read=None) -> int:
    """The yield reference's own population: per-measurement ``n`` of its report."""
    read = read or (lambda p: _git("show", f"{tree}:{p}"))
    try:
        ms = json.loads(read(YIELD_OFFSET_REPORT))["measurements"]
        ns = {i: _n(m["n"], "yield measurement n") for i, m in enumerate(ms)}
    except (ValueError, KeyError, TypeError) as exc:
        raise EstimateError(f"{YIELD_OFFSET_REPORT} at {tree} has no valid counts: {exc!r}") from exc
    if not ns:
        raise EstimateError(f"{YIELD_OFFSET_REPORT} at {tree} has no measurements")
    return _one(ns, f"{YIELD_OFFSET_REPORT} at {tree}")


def estimate_offset_campaign(n: int, reference: str, tree: str = "HEAD") -> dict:
    """Read sizes and reference counts from ``tree`` and estimate."""
    prefix = f"{CAMPAIGNS}/{reference}/"
    ref_files = [(p[len(prefix):], s) for p, s in _ls_tree(tree, prefix[:-1]) if p.startswith(prefix)]
    budget = json.loads(_git("show", f"{tree}:{BUDGET}"))
    current = sum(s for _, s in _ls_tree(tree, "sim"))
    return estimate_from_sizes(n, reference, tree, ref_files, _ls_tree(tree, YIELD_REFERENCE), budget, current,
                               ref_n=reference_offset_n(reference, tree), yield_ref_n=reference_yield_n(tree))


def estimate_from_sizes(n: int, reference: str, tree: str, ref_files: list[tuple[str, int]],
                        yield_files: list[tuple[str, int]], budget: dict, current: int, *,
                        ref_n: int, yield_ref_n: int) -> dict:
    """Pure (no git): ``ref_files`` are ``(path relative to the campaign, bytes)``;
    ``ref_n``/``yield_ref_n`` the offset and yield references' own counts."""
    offset = [(p, s) for p, s in ref_files if p.startswith(("offset_mc.", "artifacts/offset_mc."))]
    if not offset:
        raise EstimateError(f"reference campaign {reference} holds no offset_mc evidence in {tree}")
    fixed = sum(s for name, s in offset if name.endswith(FIXED_SUFFIXES) and "/" not in name)
    scaling = sum(s for _, s in offset) - fixed
    campaign_bytes = round(fixed + scaling * n / ref_n) + GRADING_ALLOWANCE
    # offset report + samples + index scale by n / yield_ref_n
    offset_side = [s for p, s in yield_files if "/offset" in p or p.endswith(("index.json", "index.md"))]
    yield_bytes = round(sum(offset_side) * n / yield_ref_n)
    unit_ceiling = budget["new_unit_ceiling_bytes"]
    total_ceiling = budget["total_ceiling_bytes"]
    new_total = current + campaign_bytes + yield_bytes
    units = {"campaign": campaign_bytes, "yield": yield_bytes}
    over_unit = {k: v - unit_ceiling for k, v in units.items() if v > unit_ceiling}
    return {
        "offset_n": n, "reference_campaign": reference, "reference_n": ref_n, "yield_reference": YIELD_REFERENCE,
        "yield_reference_n": yield_ref_n, "tree": tree,
        "model": "fixed files + linear-in-N per-sample files (envelope + artifacts) + grading allowance",
        "campaign_unit_bytes": campaign_bytes, "yield_unit_bytes": yield_bytes,
        "new_unit_ceiling_bytes": unit_ceiling,
        "units_over_ceiling": over_unit,
        "sim_bytes_now": current, "sim_bytes_after": new_total,
        "total_ceiling_bytes": total_ceiling,
        "total_over_ceiling_bytes": max(0, new_total - total_ceiling),
        "within_budget": not over_unit and new_total <= total_ceiling,
    }


def render(est: dict) -> str:
    mib = lambda b: f"{b / 1048576:.1f} MiB"  # noqa: E731
    lines = [
        f"Evidence-size ESTIMATE (not a measurement) for offset N = {est['offset_n']} "
        f"(reference {est['reference_campaign']} at N = {est['reference_n']}, "
        f"yield reference {est['yield_reference']} at N = {est['yield_reference_n']}, tree {est['tree']})",
        f"  model: {est['model']}",
        f"  campaign unit: {est['campaign_unit_bytes']} B ({mib(est['campaign_unit_bytes'])})"
        f" vs new-unit ceiling {est['new_unit_ceiling_bytes']} B ({mib(est['new_unit_ceiling_bytes'])})",
        f"  yield unit:    {est['yield_unit_bytes']} B ({mib(est['yield_unit_bytes'])})",
        f"  sim/ total:    {est['sim_bytes_now']} B -> {est['sim_bytes_after']} B"
        f" vs ceiling {est['total_ceiling_bytes']} B",
    ]
    for k, over in est["units_over_ceiling"].items():
        lines.append(f"  OVER: {k} unit exceeds the new-unit ceiling by {over} B: needs an exact "
                     "budget exception backed by a decision record before submission")
    if est["total_over_ceiling_bytes"]:
        lines.append(f"  OVER: sim/ total exceeds the ceiling by {est['total_over_ceiling_bytes']} B")
    lines.append("  verdict: " + ("within budget" if est["within_budget"] else "EXCEPTION REQUIRED"))
    return "\n".join(lines)
