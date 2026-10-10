"""Pre-submission evidence-size estimate for a larger offset campaign (issue #167).

The budget contract (``sim/evidence-size-budget.json``, checked by
``scripts/check_evidence_size.py``) caps a NEW evidence unit at
``new_unit_ceiling_bytes`` and all of ``sim/`` at ``total_ceiling_bytes``.
A fleet submission that lands over either needs a decision record and an exact
budget exception, so the size is estimated from a committed reference campaign
BEFORE anything is submitted. Blob bytes (``git ls-tree -rl``), never the
working tree, same accounting as the checker.

Model: per-sample files (the envelope and every per-corner artifact) scale
linearly with the draw count; the bodies, requests and invocations are fixed.
It is an estimate, labelled as such; the checker's measurement of the
committed result is authoritative.
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


class EstimateError(Exception):
    pass


def _ls_tree(tree: str, path: str) -> list[tuple[str, int]]:
    proc = subprocess.run(["git", "-C", str(build_mod.REPO_ROOT), "ls-tree", "-r", "-l", "-z", tree, path],
                          capture_output=True, check=False)
    if proc.returncode != 0:
        raise EstimateError(f"git ls-tree failed: {proc.stderr.decode(errors='replace').strip()}")
    out = []
    for rec in proc.stdout.split(b"\0"):
        if not rec:
            continue
        meta, _, name = rec.partition(b"\t")
        out.append((name.decode(), int(meta.split()[3])))
    return out


def estimate_offset_campaign(n: int, reference: str, tree: str = "HEAD") -> dict:
    """Read the sizes from git (``git ls-tree -rl``) and estimate."""
    prefix = f"{CAMPAIGNS}/{reference}/"
    ref_files = [(p[len(prefix):], s) for p, s in _ls_tree(tree, f"{CAMPAIGNS}/{reference}")
                 if p.startswith(prefix)]
    yield_files = [(p, s) for p, s in _ls_tree(tree, YIELD_REFERENCE)]
    raw = subprocess.run(["git", "-C", str(build_mod.REPO_ROOT), "show", f"{tree}:{BUDGET}"],
                         capture_output=True, check=False)
    if raw.returncode != 0:
        raise EstimateError(f"cannot read {BUDGET} at {tree}")
    current = sum(s for _, s in _ls_tree(tree, "sim"))
    return estimate_from_sizes(n, reference, tree, ref_files, yield_files, json.loads(raw.stdout), current)


def estimate_from_sizes(n: int, reference: str, tree: str, ref_files: list[tuple[str, int]],
                        yield_files: list[tuple[str, int]], budget: dict, current: int) -> dict:
    """Pure estimate from listed sizes (no git): ``ref_files`` are the reference
    campaign's ``(path relative to the campaign, bytes)``."""
    ref_n = _reference_n()
    offset = [(p, s) for p, s in ref_files if p.startswith(("offset_mc.", "artifacts/offset_mc."))]
    if not offset:
        raise EstimateError(f"reference campaign {reference} holds no offset_mc evidence in {tree}")
    fixed = sum(s for name, s in offset if name.endswith(FIXED_SUFFIXES) and "/" not in name)
    scaling = sum(s for name, s in offset if not (name.endswith(FIXED_SUFFIXES) and "/" not in name))
    campaign_bytes = round(fixed + scaling * n / ref_n) + GRADING_ALLOWANCE
    offset_side = [s for p, s in yield_files if "/offset" in p or p.endswith(("index.json", "index.md"))]
    # offset report + samples + index: scale the whole offset side by n / ref_n
    yield_bytes = round(sum(offset_side) * n / ref_n)
    unit_ceiling = budget["new_unit_ceiling_bytes"]
    total_ceiling = budget["total_ceiling_bytes"]
    new_total = current + campaign_bytes + yield_bytes
    units = {"campaign": campaign_bytes, "yield": yield_bytes}
    over_unit = {k: v - unit_ceiling for k, v in units.items() if v > unit_ceiling}
    return {
        "offset_n": n, "reference_campaign": reference, "reference_n": ref_n, "tree": tree,
        "model": "fixed files + linear-in-N per-sample files (envelope + artifacts) + grading allowance",
        "campaign_unit_bytes": campaign_bytes, "yield_unit_bytes": yield_bytes,
        "new_unit_ceiling_bytes": unit_ceiling,
        "units_over_ceiling": over_unit,
        "sim_bytes_now": current, "sim_bytes_after": new_total,
        "total_ceiling_bytes": total_ceiling,
        "total_over_ceiling_bytes": max(0, new_total - total_ceiling),
        "within_budget": not over_unit and new_total <= total_ceiling,
    }


def _reference_n() -> int:
    from .benches import OFFSET_MC_N

    return OFFSET_MC_N


def render(est: dict) -> str:
    mib = lambda b: f"{b / 1048576:.1f} MiB"  # noqa: E731
    lines = [
        f"Evidence-size ESTIMATE (not a measurement) for offset N = {est['offset_n']} "
        f"(reference {est['reference_campaign']} at N = {est['reference_n']}, tree {est['tree']})",
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
