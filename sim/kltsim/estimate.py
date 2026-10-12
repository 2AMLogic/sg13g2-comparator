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
#: The yield reference's offset report; its per-measurement ``n`` is the yield denominator.
YIELD_OFFSET_REPORT = f"{YIELD_REFERENCE}/offset.yield.json"
#: Expected process parts of an offset_mc reference campaign (one request each).
OFFSET_PARTS = ("tt", "ff", "fs", "sf", "ss")


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


def _git_show(tree: str, path: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(build_mod.REPO_ROOT), "show", f"{tree}:{path}"],
                          capture_output=True, check=False)
    if proc.returncode != 0:
        raise EstimateError(f"cannot read {path} at {tree}")
    return proc.stdout


def _positive_int(value, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 2:
        raise EstimateError(f"{what} is not a valid draw count (integer >= 2): {value!r}")
    return value


def reference_offset_n(reference: str, tree: str, read=None) -> int:
    """Offset draw count declared by the reference campaign's committed requests at ``tree``.

    Every expected process part must carry ``monte_carlo.n`` and all must agree;
    anything else is an error (never a silent default). ``read(path)`` returns the
    bytes of a path at the tree (default: ``git show``)."""
    read = read or (lambda path: _git_show(tree, path))
    found: dict[str, int] = {}
    for part in OFFSET_PARTS:
        path = f"{CAMPAIGNS}/{reference}/offset_mc.mos_{part}_mismatch.request.json"
        try:
            doc = json.loads(read(path))
        except ValueError as exc:
            raise EstimateError(f"{path} at {tree} is not valid JSON: {exc}") from exc
        mc = doc.get("monte_carlo") if isinstance(doc, dict) else None
        if not isinstance(mc, dict) or "n" not in mc:
            raise EstimateError(f"{path} at {tree} declares no monte_carlo.n")
        found[part] = _positive_int(mc["n"], f"{path} monte_carlo.n")
    if len(set(found.values())) != 1:
        raise EstimateError(f"reference campaign {reference} at {tree} declares conflicting offset "
                            f"draw counts across parts: {found}")
    return next(iter(found.values()))


def reference_yield_n(tree: str, read=None) -> int:
    """Population count of the yield reference: the per-measurement ``n`` of its
    committed offset report at ``tree`` (all measurements must agree)."""
    read = read or (lambda path: _git_show(tree, path))
    try:
        doc = json.loads(read(YIELD_OFFSET_REPORT))
        ns = {_positive_int(m["n"], f"{YIELD_OFFSET_REPORT} measurement n") for m in doc["measurements"]}
    except (ValueError, KeyError, TypeError) as exc:
        raise EstimateError(f"{YIELD_OFFSET_REPORT} at {tree} has no valid measurement counts: {exc!r}") from exc
    if len(ns) != 1:
        raise EstimateError(f"{YIELD_OFFSET_REPORT} at {tree} declares conflicting counts: {sorted(ns)}")
    return ns.pop()


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
    return estimate_from_sizes(n, reference, tree, ref_files, yield_files, json.loads(raw.stdout), current,
                               ref_n=reference_offset_n(reference, tree), yield_ref_n=reference_yield_n(tree))


def estimate_from_sizes(n: int, reference: str, tree: str, ref_files: list[tuple[str, int]],
                        yield_files: list[tuple[str, int]], budget: dict, current: int, *, ref_n: int, yield_ref_n: int) -> dict:
    """Pure estimate from listed sizes (no git): ``ref_files`` are the reference
    campaign's ``(path relative to the campaign, bytes)``. ``ref_n`` is the
    reference campaign's declared offset N and ``yield_ref_n`` the yield
    reference's own population count (resolved from committed metadata)."""
    offset = [(p, s) for p, s in ref_files if p.startswith(("offset_mc.", "artifacts/offset_mc."))]
    if not offset:
        raise EstimateError(f"reference campaign {reference} holds no offset_mc evidence in {tree}")
    fixed = sum(s for name, s in offset if name.endswith(FIXED_SUFFIXES) and "/" not in name)
    scaling = sum(s for name, s in offset if not (name.endswith(FIXED_SUFFIXES) and "/" not in name))
    campaign_bytes = round(fixed + scaling * n / ref_n) + GRADING_ALLOWANCE
    offset_side = [s for p, s in yield_files if "/offset" in p or p.endswith(("index.json", "index.md"))]
    # offset report + samples + index: scale the whole offset side by n / yield_ref_n
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
