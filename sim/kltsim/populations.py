"""Shared structural validation of one PVT point's Monte-Carlo sample records.

Stdlib only and import-free of ``grade`` / ``yield_reports`` so both can use
it without a cycle. The compliance reducers (``grade.mc_per_corner``,
``grade.mc_probit_noise``) and the yield collector
(``yield_reports.collect_populations``) apply the same population policy:

* every sample carries a nonnegative integer ``monte_carlo.sample_index``
  (booleans are not integers here);
* no sample identity repeats at a point, across all envelopes and in any
  order (a duplicate is never resolved by picking a copy);
* the point holds exactly the declared number of attempted samples;
* all samples of a point map to one base corner id;
* a consumed klt summary agrees with that validated population.

Nothing here computes a statistic.
"""

from __future__ import annotations

import math


class PopulationError(ValueError):
    """A point's sample records are not the declared population.

    ``kind`` is one of ``index``, ``base``, ``duplicate``, ``count``,
    ``summary``; ``message`` carries no bench/point prefix."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def sample_index(corner) -> int:
    mc = corner.get("monte_carlo") if isinstance(corner, dict) else None
    idx = mc.get("sample_index") if isinstance(mc, dict) else None
    if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0:
        cid = corner.get("corner_id") if isinstance(corner, dict) else corner
        raise PopulationError(
            "index", f"corner {cid!r} has no valid monte_carlo.sample_index ({idx!r})")
    return idx


def base_corner_id(corner) -> str:
    cid = corner.get("corner_id") if isinstance(corner, dict) else None
    if not isinstance(cid, str) or not cid:
        raise PopulationError("base", f"sample has a malformed corner_id ({cid!r})")
    return cid.rsplit("/mc", 1)[0]


def validate_point(corners: list[dict], expected_n: int) -> tuple[str, list[int]]:
    """Validate one point's sample corners (all envelopes pooled).

    Returns ``(base_corner_id, sorted sample indices)`` or raises
    :class:`PopulationError`. Deterministic across envelope/sample order."""
    bases = {base_corner_id(c) for c in corners}
    if len(bases) != 1:
        raise PopulationError("base", f"maps to several base corners {sorted(bases)}")
    indices = sorted(sample_index(c) for c in corners)
    if len(set(indices)) != len(indices):
        raise PopulationError(
            "duplicate", "reports a sample index more than once (duplicate population)")
    if len(indices) != expected_n:
        raise PopulationError(
            "count", f"has {len(indices)} sample records, the ratified basis is "
                     f"N = {expected_n}")
    return bases.pop(), indices


def _count(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and (not math.isfinite(value) or value != int(value)):
        return None
    return int(value) if value >= 0 else None


def check_summary(entry: dict, corners: list[dict], name: str = "summary") -> str | None:
    """Why a klt per-corner summary does not describe ``corners`` (already
    validated), or None. usable + errored must equal the attempted records and
    cover every sample the records themselves mark as errored."""
    n, errored = _count(entry.get("n")), _count(entry.get("errored"))
    if n is None or errored is None:
        return (f"{name} counts are malformed (n={entry.get('n')!r}, "
                f"errored={entry.get('errored')!r})")
    attempted = len(corners)
    if n + errored != attempted:
        return (f"{name} counts n={n} + errored={errored} do not match "
                f"{attempted} sample records")
    record_errors = sum(1 for c in corners if c.get("status") == "error")
    if errored < record_errors:
        return (f"{name} reports {errored} errored but {record_errors} sample records "
                "are errored")
    return None
