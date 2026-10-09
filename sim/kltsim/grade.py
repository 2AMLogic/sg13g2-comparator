"""Grade DR-0002's rows literally from committed ``klt sim`` envelopes.

The rules, in the order they bind:

1. **The DUT must be the schematic DUT.** A bench's committed body must hash
   to the envelope's own ``provenance.input.content_hash``, must embed a DUT
   block whose bytes are exactly today's ``design/comparator.spice``, and
   ``sim/dut.json`` must bind that netlist with ``provenance: schematic``.
   Otherwise every row resting on that bench is ``INVALID_DUT``.
2. **Every grid point must be present, trustworthy and actually applied.**
   A corner that is missing, errored, lacks the measurement, failed a
   validity gate (a wrong decision, an offset clamped at the edge of the
   swept window), or whose supply / temperature probe disagrees with the
   corner it claims to be, contributes no value.
3. **Verdicts keep their causes apart.** ``FAIL`` means at least one
   trustworthy value violates the bound (a numerical spec miss, whatever
   else is missing). ``INCOMPLETE`` means no violation was seen but the grid
   is not fully, validly covered -- never ``PASS``. ``GAP`` is a sub-bound
   with no klt evidence at all (with the retained non-klt record and its
   own verdict quoted). ``NOT SPECIFIED`` is a column DR-0002 ratifies no
   bound for. ``REPORTED`` is a reporting requirement (unbounded).
4. **Statistics keep their ratified basis.** Row 1 is graded on DR-0002's
   own per-point statistic (3 x population sigma of the whole-latch offset,
   net of the staircase's step^2/12 quantization variance -- the original
   bench's ``vos_3sig_mv``) computed from ``klt sim``'s own per-corner
   moments, at exactly the ratified N per point; klt's own mean +/- 3 sigma
   window is reported beside it, not substituted for it.

Nothing here edits an envelope, and nothing here invents a value: every
number graded is one ``klt sim`` reported (or a closed-form function of its
reported per-corner moments, for Row 1).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist

from . import build as build_mod

PASS = "PASS"
FAIL = "FAIL"
INCOMPLETE = "INCOMPLETE"
GAP = "GAP"
NOT_SPECIFIED = "NOT SPECIFIED"
REPORTED = "REPORTED"
INVALID_DUT = "INVALID_DUT"
REJECTED_EVIDENCE = "REJECTED_EVIDENCE"

SUPPLY_TOL_V = 1e-3
TEMP_TOL_C = 0.01

# --------------------------------------------------------------------------- #
# units
# --------------------------------------------------------------------------- #

_SCALE = {
    # time
    "s": ("time", 1.0), "ms": ("time", 1e-3), "us": ("time", 1e-6),
    "ns": ("time", 1e-9), "ps": ("time", 1e-12),
    # voltage
    "V": ("voltage", 1.0), "mV": ("voltage", 1e-3), "uV": ("voltage", 1e-6),
    "nV": ("voltage", 1e-9),
    # charge
    "C": ("charge", 1.0), "pC": ("charge", 1e-12), "fC": ("charge", 1e-15),
    "aC": ("charge", 1e-18),
    # power
    "W": ("power", 1.0), "mW": ("power", 1e-3), "uW": ("power", 1e-6),
    "nW": ("power", 1e-9),
    # current
    "A": ("current", 1.0), "mA": ("current", 1e-3), "uA": ("current", 1e-6),
}


class UnitError(ValueError):
    pass


def _norm_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    unit = unit.strip()
    for suffix in (" rms",):
        if unit.endswith(suffix):
            unit = unit[: -len(suffix)]
    return unit.replace("µ", "u")


class NonFiniteError(ValueError):
    """A value that is not a finite real number (NaN, +/-inf, non-numeric)."""


def finite(value, what: str = "value") -> float:
    """``value`` as a finite float, or ``NonFiniteError``.

    Evidence that is NaN, infinite, a bool, or not convertible to a number is
    invalid: comparisons against a bound are meaningless for it (every
    comparison with NaN is False; -inf passes any upper bound).
    """
    if isinstance(value, bool):
        raise NonFiniteError(f"{what} is not a number ({value!r})")
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        raise NonFiniteError(f"{what} is not a number ({value!r})") from None
    if not math.isfinite(x):
        raise NonFiniteError(f"{what} is not finite ({value!r})")
    return x


def _finite_or_none(value) -> float | None:
    try:
        return finite(value)
    except NonFiniteError:
        return None


def json_safe(obj):
    """Copy of ``obj`` with every non-finite float replaced by None, so the
    serialised report never contains NaN / Infinity tokens."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return obj


def dumps_strict(obj, **kw) -> str:
    """Strict (RFC 8259) JSON: non-finite floats become null, never tokens."""
    return json.dumps(json_safe(obj), allow_nan=False, **kw)


def convert(value: float, from_unit: str | None, to_unit: str | None) -> float:
    """Convert ``value`` between two units of one dimension.

    Identical units (including both ``None``) pass through; anything the
    table cannot place, or two different dimensions, is a ``UnitError`` --
    never a silent pass-through.
    """
    a, b = _norm_unit(from_unit), _norm_unit(to_unit)
    if a == b:
        return value
    if a not in _SCALE or b not in _SCALE:
        raise UnitError(f"cannot convert {from_unit!r} to {to_unit!r}")
    dim_a, scale_a = _SCALE[a]
    dim_b, scale_b = _SCALE[b]
    if dim_a != dim_b:
        raise UnitError(f"{from_unit!r} ({dim_a}) is not convertible to {to_unit!r} ({dim_b})")
    return value * scale_a / scale_b


# --------------------------------------------------------------------------- #
# bounds
# --------------------------------------------------------------------------- #


def margin(value: float, bound: dict) -> float:
    """Signed headroom to the nearest limit: positive passes, negative fails."""
    margins = []
    if bound.get("max") is not None:
        margins.append(float(bound["max"]) - value)
    if bound.get("min") is not None:
        margins.append(value - float(bound["min"]))
    if not margins:
        raise ValueError(f"bound {bound!r} has neither min nor max")
    return min(margins)


def describe_bound(bound: dict | None) -> str:
    if bound is None:
        return "not specified"
    if bound.get("coverage"):
        return "full grid exercised"
    parts = []
    if bound.get("min") is not None:
        parts.append(f">= {bound['min']:g}")
    if bound.get("max") is not None:
        parts.append(f"<= {bound['max']:g}")
    return " and ".join(parts)


# --------------------------------------------------------------------------- #
# evidence model
# --------------------------------------------------------------------------- #


@dataclass
class BenchEvidence:
    """Everything grading needs about one bench, already loaded."""

    name: str
    envelopes: list[tuple[str, dict]]          # (tag, envelope json)
    body_text: str | None                      # committed body, or None
    envelope_files: dict[str, str] = field(default_factory=dict)  # tag -> sha256
    # Saved request/invocation chain (issue #107). Empty for in-memory fixtures;
    # `load_campaign` fills it. Any chain problem rejects the bench's evidence.
    chain_problems: list[str] = field(default_factory=list)
    chain_checked: dict[str, dict] = field(default_factory=dict)  # tag -> checked hashes


@dataclass
class DutReference:
    netlist_bytes: bytes
    netlist_rel: str
    dut_json: dict


def grid_keys(grid: dict) -> list[tuple[str, float, float]]:
    return [
        (p, float(v), float(t))
        for p in grid["process"]
        for v in grid["supply_v"]
        for t in grid["temperature_c"]
    ]


def key_label(key: tuple[str, float, float]) -> str:
    p, v, t = key
    return f"{p}_{t:g}c_{v:.2f}v"


def _process_name(section: str | None) -> str | None:
    if section is None:
        return None
    name = section[4:] if section.startswith("mos_") else section
    return name[: -len("_mismatch")] if name.endswith("_mismatch") else name


def _corner_key(corner: dict) -> tuple[str, float, float] | None:
    supplies = corner.get("supply_v") or {}
    if not supplies:
        return None
    first = supplies[sorted(supplies)[0]]
    v, t = _finite_or_none(first), _finite_or_none(corner.get("temperature_c"))
    if v is None or t is None:
        return None  # an unplaceable corner can never cover a grid point
    return (_process_name(corner.get("process")), round(v, 6), t)


def check_dut(bench: BenchEvidence, dut: DutReference) -> list[str]:
    """Return the reasons this bench's DUT is NOT the schematic DUT (empty = ok)."""
    problems: list[str] = []
    if dut.dut_json.get("provenance") != "schematic":
        problems.append(
            f"sim/dut.json provenance is {dut.dut_json.get('provenance')!r}, not 'schematic'")
    if bench.body_text is None:
        return problems + ["committed netlist body is missing"]
    body_sha = hashlib.sha256(bench.body_text.encode("utf-8")).hexdigest()
    path, declared_sha, embedded = build_mod.extract_dut_block(bench.body_text)
    if embedded is None:
        problems.append("netlist body embeds no DUT block")
    else:
        embedded_sha = hashlib.sha256(embedded.encode("utf-8")).hexdigest()
        reference_bytes = dut.netlist_bytes
        geometry = build_mod.extract_geometry(bench.body_text)
        if geometry:
            # issue #92 sizing candidate: today's DUT + the declared geometry
            try:
                reference_bytes = build_mod.apply_geometry(
                    dut.netlist_bytes.decode("utf-8"), geometry).encode("utf-8")
            except build_mod.BuildError as exc:
                problems.append(f"declared geometry override is not applicable: {exc}")
        reference_sha = hashlib.sha256(reference_bytes).hexdigest()
        if declared_sha != embedded_sha:
            problems.append("embedded DUT block does not match its own declared sha256")
        if embedded_sha != reference_sha:
            problems.append(
                f"embedded DUT ({embedded_sha[:12]}) is not today's {dut.netlist_rel} "
                f"({reference_sha[:12]})")
        if path != dut.netlist_rel:
            problems.append(f"embedded DUT names {path!r}, not {dut.netlist_rel!r}")
        placeholder = build_mod.SIM_DIR / "dut" / "placeholder_comparator.spice"
        if placeholder.is_file() and embedded.encode("utf-8") == placeholder.read_bytes():
            problems.append("embedded DUT is the retired placeholder (sim/dut/placeholder_comparator.spice)")
        for subckt in (".subckt comparator ", ".subckt comparator_dut "):
            if subckt not in embedded:
                problems.append(f"embedded DUT lacks `{subckt.strip()}` (DR-0001 topology + contract wrapper)")
    for tag, env in bench.envelopes:
        prov = ((env.get("provenance") or {}).get("input") or {}).get("content_hash")
        if prov != f"sha256:{body_sha}":
            problems.append(
                f"{tag}: envelope provenance.input.content_hash {prov!r} is not the "
                f"committed body's sha256:{body_sha[:12]}...")
        source = (env.get("environment") or {}).get("netlist_source")
        if source != "schematic":
            problems.append(f"{tag}: environment.netlist_source is {source!r}")
    return problems


@dataclass
class CornerValue:
    key: tuple[str, float, float]
    value: float | None
    corner_id: str | None
    problem: str | None = None


def _bench_names() -> list[str]:
    from .benches import BENCHES

    return list(BENCHES)


def _bench_spec(name: str):
    from .benches import BENCHES

    return BENCHES.get(name)


def _corner_problems(corner: dict, bench_name: str, gates: list[str]) -> str | None:
    """Why this (non-MC) corner's numbers cannot be trusted, or None."""
    if corner.get("status") == "error":
        codes = ",".join(sorted({d.get("code", "?") for d in corner.get("diagnostics") or []}))
        return f"errored ({codes or 'no diagnostic'})"
    values = {m["name"]: m for m in corner.get("measurements") or []}
    bench = _bench_spec(bench_name)
    probes = bench.probes if bench is not None else {}
    supplies = corner.get("supply_v") or {}
    for probe in probes.get("supply", ()):
        m = values.get(probe)
        if m is None or m.get("value") is None:
            return f"supply probe {probe} missing"
        try:
            pv = finite(m["value"], f"supply probe {probe}")
            sv = [finite(v, "corner supply") for v in supplies.values()]
        except NonFiniteError as exc:
            return f"invalid numeric evidence: {exc}"
        if not any(abs(pv - v) <= SUPPLY_TOL_V for v in sv):
            return f"supply probe {probe}={m['value']} V does not match corner {supplies}"
    temp_probe = probes.get("temperature")
    if temp_probe:
        m = values.get(temp_probe)
        if m is None or m.get("value") is None:
            return f"temperature probe {temp_probe} missing"
        try:
            tv = finite(m["value"], f"temperature probe {temp_probe}")
            tc = finite(corner.get("temperature_c"), "corner temperature_c")
        except NonFiniteError as exc:
            return f"invalid numeric evidence: {exc}"
        if abs(tv - tc) > TEMP_TOL_C:
            return (f"temperature probe {temp_probe}={m['value']} C does not match "
                    f"corner {corner.get('temperature_c')} C")
    for gate in gates:
        m = values.get(gate)
        if m is None or m.get("value") is None:
            return f"validity gate {gate} missing"
        try:
            finite(m["value"], f"validity gate {gate}")
        except NonFiniteError as exc:
            return f"invalid numeric evidence: {exc}"
        if m.get("status") != "pass":
            return f"validity gate {gate}={m['value']} failed"
    return None


def per_corner_values(bench: BenchEvidence, measurement: str, unit: str | None,
                      grid: dict, gates: list[str]) -> tuple[list[CornerValue], list[str]]:
    """One CornerValue per expected grid point (in grid order) + notes."""
    notes: list[str] = []
    # Every placement of a deterministic PVT point, in any envelope. A repeated
    # key is ambiguous evidence: no result is selected (never first/last/worst),
    # so the verdict cannot depend on envelope order.
    seen: dict[tuple, list[tuple[str, dict]]] = {}
    for tag, env in bench.envelopes:
        for corner in env.get("corners") or []:
            if corner.get("monte_carlo") is not None:
                continue
            key = _corner_key(corner)
            if key is None:
                continue
            seen.setdefault(key, []).append((tag, corner))
    collisions = {k: sorted(f"{t}:{c.get('corner_id')}" for t, c in v)
                  for k, v in seen.items() if len(v) > 1}
    if collisions:
        grid_set = {(k[0], round(k[1], 6), k[2]) for k in grid_keys(grid)}
        for k in sorted(collisions, key=str):
            notes.append(f"ambiguous duplicate result for {key_label(k)}"
                         f"{'' if k in grid_set else ' (outside the grid)'}: "
                         f"{'; '.join(collisions[k])}; no result selected")
    out: list[CornerValue] = []
    for key in grid_keys(grid):
        k = (key[0], round(key[1], 6), key[2])
        if k in collisions:
            ids = sorted({str(c.get("corner_id")) for _, c in seen[k]})
            out.append(CornerValue(
                key, None, " | ".join(ids),
                "ambiguous duplicate PVT result, no value selected: " + "; ".join(collisions[k])))
            continue
        corner = seen[k][0][1] if k in seen else None
        if corner is None:
            out.append(CornerValue(key, None, None, "grid point not in any envelope"))
            continue
        problem = _corner_problems(corner, bench.name, gates)
        m = next((m for m in corner.get("measurements") or [] if m["name"] == measurement), None)
        if m is None or m.get("value") is None:
            problem = problem or f"measurement {measurement} not reported"
            out.append(CornerValue(key, None, corner.get("corner_id"), problem))
            continue
        try:
            value = finite(convert(finite(m["value"], f"measurement {measurement}"),
                                   m.get("unit"), unit), f"measurement {measurement} (converted)")
        except (UnitError, NonFiniteError) as exc:
            out.append(CornerValue(key, None, corner.get("corner_id"), str(exc)))
            continue
        out.append(CornerValue(key, None if problem else value, corner.get("corner_id"), problem))
    return out, notes


def grade_values(values: list[CornerValue], bound: dict | None) -> dict:
    # Last line of defence: a non-finite value is never usable evidence,
    # whatever produced it.
    values = [v if v.value is None or _finite_or_none(v.value) is not None
              else CornerValue(v.key, None, v.corner_id, f"non-finite value {v.value!r}")
              for v in values]
    present = [v for v in values if v.value is not None]
    missing = [v for v in values if v.value is None]
    result: dict = {
        "points_expected": len(values),
        "points_valid": len(present),
        "points_missing_or_invalid": [
            {"point": key_label(v.key), "corner_id": v.corner_id, "why": v.problem}
            for v in missing
        ],
    }
    if present:
        lo = min(present, key=lambda v: v.value)
        hi = max(present, key=lambda v: v.value)
        result["range"] = {
            "min": {"value": lo.value, "point": key_label(lo.key), "corner_id": lo.corner_id},
            "max": {"value": hi.value, "point": key_label(hi.key), "corner_id": hi.corner_id},
        }
    if bound is None:
        result["verdict"] = NOT_SPECIFIED
        return result
    if not present:
        result["verdict"] = INCOMPLETE
        return result
    scored = sorted(present, key=lambda v: margin(v.value, bound))
    worst = scored[0]
    failing = [v for v in present if margin(v.value, bound) < 0]
    result["binding"] = {
        "point": key_label(worst.key),
        "corner_id": worst.corner_id,
        "value": worst.value,
        "margin": margin(worst.value, bound),
    }
    result["points_failing"] = len(failing)
    result["failing_points"] = [key_label(v.key) for v in failing]
    if failing:
        result["verdict"] = FAIL
    elif missing:
        result["verdict"] = INCOMPLETE
    else:
        result["verdict"] = PASS
    return result


# --------------------------------------------------------------------------- #
# Row 1: Monte Carlo per-point 3 sigma
# --------------------------------------------------------------------------- #


def three_sigma_dr_basis(n: int, stddev: float, step: float) -> float | None:
    """DR-0002 Row 1's per-point statistic from klt's per-corner moments.

    klt reports the Bessel-corrected sample sigma ``s``. The ratified
    whole-latch number is 3 x the POPULATION sigma net of the staircase's
    uniform quantization variance (``step**2 / 12``):
    ``3 * sqrt(s**2 * (n - 1) / n - step**2 / 12)``
    -- exactly ``vos_3sig_mv`` of sim/comparator-offset-transient-mc.
    A negative net variance (quantization-dominated) is reported as 0.
    """
    if n is None or n < 2 or stddev is None:
        return None
    var_pop = stddev * stddev * (n - 1) / n
    return 3.0 * math.sqrt(max(var_pop - step * step / 12.0, 0.0))


def _index_populations(bench: BenchEvidence, names: tuple[str, ...]
                       ) -> tuple[dict[str, dict[str, dict]], dict[str, dict[str, list[str]]]]:
    """measurement name -> base corner id -> klt's by_corner entry, plus
    measurement name -> base corner id -> sorted envelope tags of EVERY
    repeated summary. A repeated summary is ambiguous: it is left out of the
    index (no winner by iteration order) and reported as a collision."""
    found: dict[str, dict[str, list[tuple[str, dict]]]] = {name: {} for name in names}
    for tag, env in bench.envelopes:
        for m in env.get("measurements") or []:
            if m.get("name") in found and m.get("monte_carlo"):
                for entry in m["monte_carlo"].get("by_corner") or []:
                    found[m["name"]].setdefault(entry["corner_id"], []).append(
                        (tag, dict(entry, _unit=m.get("unit"))))
    index = {name: {cid: v[0][1] for cid, v in per.items() if len(v) == 1}
             for name, per in found.items()}
    collisions = {name: {cid: sorted(t for t, _ in v) for cid, v in per.items() if len(v) > 1}
                  for name, per in found.items()}
    return index, collisions


def _collision_text(name: str, cid: str, tags: list[str]) -> str:
    return f"{name} summary for {cid} reported {len(tags)} times ({', '.join(tags)})"


def mc_per_corner(bench: BenchEvidence, measurement: str, unit: str | None, grid: dict,
                  expected_n: int, step: float, gates: list[str]) -> tuple[list[CornerValue], list[dict], list[str]]:
    notes: list[str] = []
    # Per-sample trust: probes + gates, grouped by base corner key.
    sample_problems: dict[tuple, list[str]] = {}
    base_ids: dict[tuple, str] = {}
    for tag, env in bench.envelopes:
        for corner in env.get("corners") or []:
            if corner.get("monte_carlo") is None:
                continue
            key = _corner_key(corner)
            base_ids[key] = corner["corner_id"].rsplit("/mc", 1)[0]
            problem = _corner_problems(corner, bench.name, gates)
            if problem:
                sample_problems.setdefault(key, []).append(f"{corner['corner_id']}: {problem}")
    pops, pop_collisions = _index_populations(bench, (measurement,))
    by_corner, dup_summaries = pops[measurement], pop_collisions[measurement]
    for cid in sorted(dup_summaries):
        notes.append("ambiguous duplicate population summary, no statistic selected: "
                     + _collision_text(measurement, cid, dup_summaries[cid]))
    details: list[dict] = []
    out: list[CornerValue] = []
    for key in grid_keys(grid):
        k = (key[0], round(key[1], 6), key[2])
        base = base_ids.get(k)
        if base in dup_summaries:
            out.append(CornerValue(key, None, base, "ambiguous duplicate population summary: "
                                   + _collision_text(measurement, base, dup_summaries[base])))
            continue
        entry = by_corner.get(base) if base else None
        if entry is None:
            out.append(CornerValue(key, None, base, "no Monte-Carlo population for this grid point"))
            continue
        try:
            s = entry.get("stddev")
            s = None if s is None else finite(
                convert(finite(s, "Monte-Carlo stddev"), entry["_unit"], unit),
                "Monte-Carlo stddev (converted)")
            q = finite(step, "quantization step")  # declared in the row's own unit
        except (UnitError, NonFiniteError) as exc:
            out.append(CornerValue(key, None, base, str(exc)))
            continue
        n = entry.get("n")
        stat_problem = None
        n_ok = _finite_or_none(n)
        if n_ok is None or n_ok != int(n_ok):
            stat_problem = f"Monte-Carlo sample count n is not a finite integer ({n!r})"
        else:
            n = int(n_ok)
        if entry.get("mean") is not None and _finite_or_none(entry.get("mean")) is None:
            stat_problem = stat_problem or f"Monte-Carlo mean is not finite ({entry.get('mean')!r})"
        if stat_problem:
            three = None
        else:
            three = three_sigma_dr_basis(n, s, q)
            if three is not None and not math.isfinite(three):
                three, stat_problem = None, "derived 3-sigma statistic is not finite"
        window = entry.get("sigma_window") or {}
        detail = {
            "point": key_label(key), "corner_id": base, "n": n,
            "errored": entry.get("errored"), "mean": _finite_or_none(entry.get("mean")),
            "stddev_bessel": s,
            "three_sigma_dr_basis": three,
            "three_s_raw": None if s is None else 3.0 * s,
            "klt_sigma_window": {k2: window.get(k2) for k2 in ("k", "low", "high", "status", "margin")},
        }
        details.append(detail)
        problem = None
        if stat_problem:
            problem = stat_problem
        elif n != expected_n or entry.get("errored"):
            problem = (f"{n} usable draws (+{entry.get('errored')} errored), ratified basis "
                       f"is N = {expected_n} per point")
        elif sample_problems.get(k):
            problem = f"{len(sample_problems[k])} draw(s) untrusted: {sample_problems[k][0]}"
        elif s is None or three is None:
            problem = "no usable Monte-Carlo spread (stddev missing)"
        elif not s:
            problem = "zero spread: mismatch not applied (the sabotage signature)"
        out.append(CornerValue(key, None if problem else three, base, problem))
    return out, details, notes


# --------------------------------------------------------------------------- #
# Row 2: transient-noise decision statistics, two-rung probit slope
# --------------------------------------------------------------------------- #


def probit(p: float) -> float:
    """Standard-normal inverse CDF; a saturated rung (p = 0 or 1) has no
    finite probit and must never read as sigma = 0 or infinity."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"probit needs 0 < p < 1, got {p!r} (saturated rung)")
    return NormalDist().inv_cdf(p)


def probit_slope_sigma(p_plus: float, p_minus: float, od_x: float) -> float:
    """DR-0002 Row 2's per-point statistic (sim/comparator-transient-noise
    README, "Probit inversion"): sigma = 2*od_x / (PhiInv(p+) - PhiInv(p-)),
    threshold-offset-immune. Raises on a saturated or inverted rung pair."""
    dz = probit(p_plus) - probit(p_minus)
    if dz <= 0:
        raise ValueError(f"rungs not ordered (p+ = {p_plus}, p- = {p_minus}): no positive slope")
    return 2.0 * od_x / dz


def _mc_samples(bench: BenchEvidence) -> dict[tuple, list[dict]]:
    """grid key -> that point's Monte-Carlo sample corners."""
    samples: dict[tuple, list[dict]] = {}
    for tag, env in bench.envelopes:
        for corner in env.get("corners") or []:
            if corner.get("monte_carlo") is None:
                continue
            key = _corner_key(corner)
            if key is not None:
                samples.setdefault(key, []).append(corner)
    return samples


def mc_probit_noise(bench: BenchEvidence, ev: dict, grid: dict) -> tuple[list[dict], list[str]]:
    """Per grid point: the two-rung probit-slope sigma from klt's per-corner
    MEANS of the 0/1 trial outcomes, or the reason there is none.

    A point contributes no value when its population is not exactly the
    ratified N (or has errored samples), when any sample is untrusted
    (supply/temperature probe, unresolved decision), when two samples drew
    the identical raw noise (duplicated random streams -- the trials are
    then not independent), when the zero-overdrive rung shows the noise was
    not demonstrably injected, or when a rung is saturated.
    """
    plus, minus, zero = ev["plus"], ev["minus"], ev["zero"]
    od_x = float(ev["od_x_mv"])
    expected_n = int(ev["expected_n"])
    guard = ev.get("zero_guard") or {}
    spec = _bench_spec(bench.name)
    gates = [m.name for m in spec.measurements if m.role == "gate"] if spec else []
    indep = tuple((spec.probes.get("independence") if spec else None) or ())
    pops, pop_collisions = _index_populations(bench, (plus, minus, zero))
    notes: list[str] = []
    for name in (plus, minus, zero):
        for cid in sorted(pop_collisions[name]):
            notes.append("ambiguous duplicate population summary, no statistic selected: "
                         + _collision_text(name, cid, pop_collisions[name][cid]))
    samples = _mc_samples(bench)
    # Raw draw -> the grid points it appears at, across ALL envelopes: a draw
    # repeated at a different point (a different batch job) shares one noise
    # stream between two points' estimates. Within one point that would void
    # the binomial count (checked below); across points it leaves each
    # point's estimate valid and unbiased but correlates them, which widens
    # the grid mean's sampling error. Reported, not graded.
    draw_points: dict[tuple, set] = {}
    if indep:
        for k, corners in samples.items():
            for c in corners:
                vals = {m["name"]: _finite_or_none(m.get("value")) for m in c.get("measurements") or []}
                d = tuple(vals.get(name) for name in indep)
                if None not in d:
                    draw_points.setdefault(d, set()).add(k)
    details: list[dict] = []
    for key in grid_keys(grid):
        k = (key[0], round(key[1], 6), key[2])
        point = {"point": key_label(key), "corner_id": None, "sigma": None, "problem": None}
        corners = samples.get(k) or []
        if not corners:
            point["problem"] = "no Monte-Carlo population for this grid point"
            details.append(point)
            continue
        base = corners[0]["corner_id"].rsplit("/mc", 1)[0]
        point["corner_id"] = base
        dup = [_collision_text(name, base, pop_collisions[name][base])
               for name in (plus, minus, zero) if base in pop_collisions[name]]
        if dup:
            point["problem"] = "ambiguous duplicate population summary: " + "; ".join(dup)
            details.append(point)
            continue
        entries = {name: pops[name].get(base) for name in (plus, minus, zero)}
        if any(e is None for e in entries.values()):
            missing = [name for name, e in entries.items() if e is None]
            point["problem"] = f"measurement(s) {', '.join(missing)} not reported"
            details.append(point)
            continue
        ns = {name: e.get("n") for name, e in entries.items()}
        raw_p = {"p_plus": entries[plus].get("mean"), "p_minus": entries[minus].get("mean"),
                 "p_zero": entries[zero].get("mean")}
        nonfinite_p = [k2 for k2, v in raw_p.items() if _finite_or_none(v) is None]
        # An invalid population statistic is retained as a diagnostic only
        # (None), never as a usable number.
        point.update({"n": _finite_or_none(ns[plus]) if ns[plus] is not None else None,
                      **{k2: _finite_or_none(v) for k2, v in raw_p.items()}})
        bad_n = [f"{name}: n = {n} (+{entries[name].get('errored')} errored)"
                 for name, n in ns.items() if n != expected_n or entries[name].get("errored")]
        untrusted = [f"{c['corner_id']}: {p}" for c in corners
                     if (p := _corner_problems(c, bench.name, gates))]
        draws = []
        for c in corners:
            vals = {m["name"]: _finite_or_none(m.get("value")) for m in c.get("measurements") or []}
            draws.append(tuple(vals.get(name) for name in indep))
        duplicated = len(draws) - len(set(draws)) if indep else 0
        missing_draws = sum(1 for d in draws if any(v is None for v in d)) if indep else 0
        point["samples_sharing_a_draw_with_another_point"] = sum(
            1 for d in draws if len(draw_points.get(d, ())) > 1)
        if bad_n:
            point["problem"] = f"sampling basis is not N = {expected_n}: {'; '.join(bad_n)}"
        elif nonfinite_p:
            point["problem"] = ("non-finite population statistic(s) "
                                f"{', '.join(nonfinite_p)}: {[raw_p[k2] for k2 in nonfinite_p]!r}")
        elif untrusted:
            point["problem"] = f"{len(untrusted)} sample(s) untrusted: {untrusted[0]}"
        elif missing_draws:
            point["problem"] = f"{missing_draws} sample(s) lack the raw-noise independence probe"
        elif duplicated:
            point["problem"] = (f"{duplicated} sample(s) repeat another sample's raw noise draw: "
                                "trials are not independent")
        elif not (float(guard.get("min", 0.0)) <= point["p_zero"] <= float(guard.get("max", 1.0))):
            point["problem"] = (f"zero-overdrive rung fraction {point['p_zero']} outside "
                                f"[{guard.get('min')}, {guard.get('max')}]: noise not "
                                "demonstrably injected")
        else:
            try:
                point["sigma"] = finite(
                    probit_slope_sigma(point["p_plus"], point["p_minus"], od_x),
                    "derived probit-slope sigma")
            except ValueError as exc:  # includes NonFiniteError
                point["sigma"] = None
                point["problem"] = str(exc)
        details.append(point)
    shared = sum(d.get("samples_sharing_a_draw_with_another_point", 0) for d in details)
    total = sum(len(c) for c in samples.values())
    if shared:
        notes.append(
            f"{shared}/{total} samples repeat a raw noise draw also seen at ANOTHER grid point "
            "(never within one point). Each point's estimate is valid and unbiased; the points "
            "are not mutually independent, so the grid mean's sampling error is wider than an "
            "independent-points estimate (bounded above by the per-point error if fully "
            "correlated).")
    return details, notes


def grade_grid_mean(details: list[dict], bound: dict | None) -> dict:
    """Grade the DR-designated statistic -- the grid-wide MEAN of the
    per-point sigma -- against one column's bound. The mean exists only when
    every grid point has a valid value; otherwise the column is INCOMPLETE
    (the partial mean is reported, never graded)."""
    details = [d if d["sigma"] is None or _finite_or_none(d["sigma"]) is not None
               else dict(d, sigma=None, problem=f"non-finite sigma {d['sigma']!r}")
               for d in details]
    valid = [d for d in details if d["sigma"] is not None]
    invalid = [d for d in details if d["sigma"] is None]
    result: dict = {
        "statistic": "grid-wide mean of the per-point two-rung probit-slope sigma",
        "points_expected": len(details),
        "points_valid": len(valid),
        "points_missing_or_invalid": [
            {"point": d["point"], "corner_id": d["corner_id"], "why": d["problem"]} for d in invalid
        ],
    }
    if valid:
        lo = min(valid, key=lambda d: d["sigma"])
        hi = max(valid, key=lambda d: d["sigma"])
        result["range"] = {
            "min": {"value": lo["sigma"], "point": lo["point"], "corner_id": lo["corner_id"]},
            "max": {"value": hi["sigma"], "point": hi["point"], "corner_id": hi["corner_id"]},
        }
        mean = sum(d["sigma"] for d in valid) / len(valid)
        if math.isfinite(mean):
            result["grid_mean" if not invalid else "partial_mean_ungraded"] = mean
        else:
            result["mean_problem"] = "grid mean is not finite (overflow)"
            mean = None
    else:
        mean = None
    if bound is None:
        result["verdict"] = NOT_SPECIFIED
        return result
    if invalid or not valid or mean is None:
        result["verdict"] = INCOMPLETE
        return result
    result["binding"] = {"point": "grid-wide mean (DR-designated statistic)", "corner_id": None,
                         "value": mean, "margin": margin(mean, bound)}
    result["worst_point"] = result["range"]["max"]
    result["points_failing"] = None  # the bound is on the mean, not per point
    result["verdict"] = FAIL if margin(mean, bound) < 0 else PASS
    return result


def mc_points_exercised(bench: BenchEvidence, grid: dict, expected_n: int) -> list[CornerValue]:
    """Coverage for a Monte-Carlo bench: a grid point is exercised when it
    carries exactly ``expected_n`` samples and every sample's supply and
    temperature probes match the corner it claims to be."""
    samples = _mc_samples(bench)
    out = []
    for key in grid_keys(grid):
        corners = samples.get((key[0], round(key[1], 6), key[2])) or []
        if not corners:
            out.append(CornerValue(key, None, None, "no Monte-Carlo population for this grid point"))
            continue
        base = corners[0]["corner_id"].rsplit("/mc", 1)[0]
        problems = [p for c in corners if (p := _corner_problems(c, bench.name, []))]
        errored = [c for c in corners if c.get("status") == "error"]
        if len(corners) != expected_n:
            out.append(CornerValue(key, None, base, f"{len(corners)} samples, expected {expected_n}"))
        elif problems or errored:
            out.append(CornerValue(key, None, base, (problems or ["errored sample"])[0]))
        else:
            out.append(CornerValue(key, 1.0, base))
    return out


# --------------------------------------------------------------------------- #
# the campaign
# --------------------------------------------------------------------------- #


def _provenance(bench: BenchEvidence) -> list[dict]:
    out = []
    for tag, env in bench.envelopes:
        environment = env.get("environment") or {}
        remote = environment.get("remote") or {}
        prov = env.get("provenance") or {}
        out.append({
            "tag": tag,
            "envelope": f"{tag}.envelope.json",
            "envelope_sha256": bench.envelope_files.get(tag),
            "chain_checked": bench.chain_checked.get(tag),
            "status": env.get("status"),
            "corner_count": env.get("corner_count"),
            "passed": env.get("passed"), "failed": env.get("failed"), "errored": env.get("errored"),
            "input_content_hash": (prov.get("input") or {}).get("content_hash"),
            "klt_version": prov.get("klt_version"),
            "engine_version": environment.get("engine_version"),
            "models_lib_sha256": environment.get("models_lib_sha256"),
            "monte_carlo": {k: (environment.get("monte_carlo") or {}).get(k)
                            for k in ("n", "seed", "vary")} if environment.get("monte_carlo") else None,
            "batch_job": {k: remote.get(k) for k in
                          ("job_id", "instance_type", "ami_id", "state", "exit_code", "elapsed_seconds")}
            if remote and "fleet" not in remote else remote or None,
        })
    return out


def grade(rows_spec: dict, benches: dict[str, BenchEvidence], dut: DutReference) -> dict:
    grid = rows_spec["grid"]
    dut_problems = {name: check_dut(b, dut) for name, b in benches.items()}
    rows_out = []
    for row in rows_spec["rows"]:
        ev = row["evidence"]
        unit = row.get("unit")
        entry = {k: row.get(k) for k in ("id", "row", "sub_bound", "unit", "condition",
                                         "statistical_basis")}
        entry["target_bound"] = describe_bound(row.get("target"))
        entry["stretch_bound"] = describe_bound(row.get("stretch"))
        entry["evidence_kind"] = ev["kind"]
        if ev["kind"] == "gap":
            rec = ev.get("retained_record") or {}
            entry.update({
                "target_verdict": GAP if row.get("target") else NOT_SPECIFIED,
                "stretch_verdict": GAP if row.get("stretch") else NOT_SPECIFIED,
                "gap_reason": ev.get("reason"),
                "tool_gap": ev.get("tool_gap"),
                "retained_record": rec,
            })
            rows_out.append(entry)
            continue
        if ev["kind"] == "coverage":
            covered, why = [], []
            for name in ev["benches"]:
                bench = benches.get(name)
                if bench is not None and bench.chain_problems:
                    why.append(f"{name}: rejected evidence ({bench.chain_problems[0]})")
                    continue
                if bench is None or not bench.envelopes:
                    why.append(f"{name}: no envelope")
                    continue
                if dut_problems.get(name):
                    why.append(f"{name}: wrong DUT ({dut_problems[name][0]})")
                    continue
                probe_meas = (_bench_spec(name).probes.get("supply") or ("",))[0]
                if _bench_spec(name).monte_carlo:
                    vals = mc_points_exercised(bench, grid, _expected_n(rows_spec, name))
                else:
                    vals, _ = per_corner_values(bench, probe_meas, "V", grid, [])
                bad = [v for v in vals if v.value is None]
                if bad:
                    why.append(f"{name}: {len(bad)}/{len(vals)} grid points not validly exercised "
                               f"(first: {key_label(bad[0].key)}: {bad[0].problem})")
                else:
                    covered.append(name)
            entry.update({
                "target_verdict": PASS if not why else INCOMPLETE,
                "stretch_verdict": NOT_SPECIFIED,
                "benches_fully_covered": covered,
                "coverage_problems": why,
            })
            rows_out.append(entry)
            continue
        bench_name = ev["bench"]
        bench = benches.get(bench_name)
        entry["bench"] = bench_name
        entry["measurement"] = ev["measurement"]
        if bench is not None and bench.chain_problems:
            entry.update({"target_verdict": REJECTED_EVIDENCE, "stretch_verdict": REJECTED_EVIDENCE,
                          "chain_problems": list(bench.chain_problems)})
            if row.get("reporting_requirement"):
                entry["report_verdict"] = REJECTED_EVIDENCE
            rows_out.append(entry)
            continue
        if bench is None or not bench.envelopes:
            entry.update({"target_verdict": INCOMPLETE if row.get("target") else NOT_SPECIFIED,
                          "stretch_verdict": INCOMPLETE if row.get("stretch") else NOT_SPECIFIED,
                          "problem": f"no klt sim envelope for bench {bench_name!r} in this campaign"})
            if row.get("reporting_requirement"):
                entry["report_verdict"] = INCOMPLETE
            rows_out.append(entry)
            continue
        if dut_problems.get(bench_name):
            entry.update({"target_verdict": INVALID_DUT, "stretch_verdict": INVALID_DUT,
                          "dut_problems": dut_problems[bench_name]})
            rows_out.append(entry)
            continue
        gates = list(ev.get("gates") or [])
        if ev["reduction"] == "mc_probit_slope_grid_mean":
            details, notes = mc_probit_noise(bench, ev, grid)
            target = grade_grid_mean(details, row.get("target"))
            stretch = grade_grid_mean(details, row.get("stretch"))
            entry.update({"target": target, "stretch": stretch,
                          "target_verdict": target["verdict"],
                          "stretch_verdict": stretch["verdict"],
                          "monte_carlo_per_point": details})
            if ev.get("retained_record"):
                entry["retained_record"] = ev["retained_record"]
            if ev.get("tool_gap"):
                entry["tool_gap"] = ev["tool_gap"]
            if notes:
                entry["notes"] = notes
            rows_out.append(entry)
            continue
        if ev["reduction"] == "per_corner":
            values, notes = per_corner_values(bench, ev["measurement"], unit, grid, gates)
            mc_details = None
        elif ev["reduction"] == "mc_per_corner_3sigma":
            bench_gates = [m.name for m in _bench_spec(bench_name).measurements if m.role == "gate"]
            values, mc_details, notes = mc_per_corner(
                bench, ev["measurement"], unit, grid, int(ev["expected_n"]),
                float(ev["quantization_step"]), gates or bench_gates)
        else:
            entry.update({"target_verdict": INCOMPLETE, "stretch_verdict": INCOMPLETE,
                          "problem": f"unsupported reduction {ev['reduction']!r}"})
            rows_out.append(entry)
            continue
        target = grade_values(values, row.get("target"))
        stretch = grade_values(values, row.get("stretch"))
        entry["target"] = target
        entry["stretch"] = stretch
        entry["target_verdict"] = target["verdict"]
        entry["stretch_verdict"] = stretch["verdict"]
        if row.get("reporting_requirement"):
            entry["report_verdict"] = REPORTED if not target["points_missing_or_invalid"] else INCOMPLETE
        if notes:
            entry["notes"] = notes
        if mc_details is not None:
            entry["monte_carlo_per_point"] = mc_details
            windows = [d["klt_sigma_window"]["status"] for d in mc_details]
            entry["klt_window_fail_points"] = [d["point"] for d in mc_details
                                               if d["klt_sigma_window"]["status"] == "fail"]
            entry["klt_window_note"] = (
                "klt's own per-corner window (|mean| + 3 x Bessel sample sigma, raw quantized "
                "values) is a stricter statistic than DR-0002's; reported, not graded. "
                f"{windows.count('pass')}/{len(windows)} points pass it.")
        rows_out.append(entry)

    target_rows = [r for r in rows_out if r["target_verdict"] != NOT_SPECIFIED]
    blockers = [
        {"id": r["id"], "sub_bound": r["sub_bound"], "target_verdict": r["target_verdict"]}
        for r in target_rows if r["target_verdict"] != PASS
    ]
    return json_safe({
        "schema": "sg13g2-comparator/klt-corner-grading/1",
        "spec_source": rows_spec.get("spec_source"),
        "dut": {"netlist": dut.netlist_rel,
                "sha256": hashlib.sha256(dut.netlist_bytes).hexdigest(),
                "dut_json_id": dut.dut_json.get("id"),
                "provenance": dut.dut_json.get("provenance")},
        "grid_points": len(grid_keys(grid)),
        "benches": {name: {"dut_problems": dut_problems[name], "chain_problems": list(b.chain_problems),
                           "envelopes": _provenance(b)}
                    for name, b in benches.items()},
        "rows": rows_out,
        "t1_item5": {
            "all_target_rows_pass": not blockers,
            "blocking_sub_bounds": blockers,
        },
    })


def _spec_meas(bench_name: str) -> str:
    bench = _bench_spec(bench_name)
    return next(m.name for m in bench.measurements if m.role == "spec")


def _expected_n(rows_spec: dict, bench_name: str) -> int:
    for row in rows_spec["rows"]:
        ev = row["evidence"]
        if ev.get("bench") == bench_name and ev.get("expected_n"):
            return int(ev["expected_n"])
    bench = _bench_spec(bench_name)
    return int((bench.monte_carlo or {}).get("n", 0))


_HEX64 = re.compile(r"[0-9a-f]{64}")


def _load_json_file(path: Path, what: str, tag: str, problems: list[str]):
    """Read a JSON object companion; append an actionable problem and return None on failure."""
    if not path.is_file():
        problems.append(f"{tag}: {what} {path.name} is missing")
        return None, None
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        problems.append(f"{tag}: {what} {path.name} is not valid JSON ({exc})")
        return raw, None
    if not isinstance(data, dict):
        problems.append(f"{tag}: {what} {path.name} is not a JSON object")
        return raw, None
    return raw, data


def _expected_request(bench, tag: str) -> dict:
    """The request `build` would compose for this part (batch form), minus prose."""
    body_name = f"{bench.name}.body.spice"
    processes = None
    if bench.split_by_process:
        processes = (tag[len(bench.name) + 1:],)
    request = build_mod.compose_request(bench, body_name, "batch", processes=processes)
    request.pop("_comment", None)
    return request


def _brief(value) -> str:
    text = json.dumps(value, sort_keys=True)
    return text if len(text) <= 120 else text[:117] + "..."


def _by_name(measurements):
    if not isinstance(measurements, list) or not all(
            isinstance(m, dict) and "name" in m for m in measurements):
        return measurements
    return sorted(measurements, key=lambda m: str(m["name"]))


def check_request_semantics(bench, tag: str, request: dict,
                            corners: dict | None = None) -> list[str]:
    """Reasons a saved request cannot support grading this part (empty = ok).

    ``corners`` (default None = the bench's full contract grid) names the one
    intentionally different grid a caller may expect instead, e.g. the issue
    #92 reduced screening grid. Every other contract field is still compared
    exactly, and an explicit ``corners`` is compared exactly too, so the
    full-grid check is not weakened by the existence of this parameter.
    """
    expected = _expected_request(bench, tag)
    if corners is not None:
        expected["corners"] = corners
    problems = []
    if request.get("netlist") != expected["netlist"]:
        problems.append(f"{tag}: request names body {request.get('netlist')!r}, "
                        f"expected {expected['netlist']!r}")
    for key in ("netlist_source", "corners", "analysis", "monte_carlo", "measurements"):
        got, want = request.get(key), expected.get(key)
        if key == "measurements":  # order is not part of the contract
            got, want = _by_name(got), _by_name(want)
        if got != want:
            problems.append(f"{tag}: request {key} {_brief(request.get(key))} does not match the "
                            f"bench contract {_brief(expected.get(key))}")
    return problems


def check_chain(bench, tag: str, campaign_dir: Path, envelope_sha: str,
                problems: list[str], corners: dict | None = None) -> dict:
    """Validate <tag>.request.json / <tag>.invocation.json against the envelope bytes."""
    checked: dict = {"envelope_sha256": envelope_sha}
    _, inv = _load_json_file(campaign_dir / f"{tag}.invocation.json", "invocation", tag, problems)
    req_raw, req = _load_json_file(campaign_dir / f"{tag}.request.json", "request", tag, problems)
    if req_raw is not None:
        checked["request_sha256"] = hashlib.sha256(req_raw).hexdigest()
    if inv is not None:
        for field_name, actual in (("request_sha256", checked.get("request_sha256")),
                                   ("envelope_sha256", envelope_sha)):
            saved = inv.get(field_name)
            if not isinstance(saved, str) or not _HEX64.fullmatch(saved):
                problems.append(f"{tag}: invocation {field_name} is missing or not a "
                                f"64-char lowercase hex sha256 ({saved!r})")
            elif actual is not None and saved != actual:
                problems.append(f"{tag}: {field_name} mismatch: invocation records "
                                f"{saved[:12]}..., file bytes hash to {actual[:12]}...")
            else:
                checked[f"invocation_{field_name}"] = saved
        if inv.get("tag") not in (None, tag):
            problems.append(f"{tag}: invocation names tag {inv.get('tag')!r}")
    if req is not None:
        problems.extend(check_request_semantics(bench, tag, req, corners))
    return checked


def load_campaign(campaign_dir: Path, corners: dict | None = None,
                  bench_names: tuple[str, ...] | None = None) -> dict[str, BenchEvidence]:
    """Load a campaign's evidence with the saved request/invocation chain checked.

    ``corners`` / ``bench_names`` are for reduced-grid callers (issue #122):
    they pass the explicit expected grid and the benches the directory holds.
    Defaults reproduce the full-campaign load exactly.
    """
    from .benches import BENCHES

    benches: dict[str, BenchEvidence] = {}
    for name, bench in BENCHES.items():
        if bench_names is not None and name not in bench_names:
            continue
        body_path = campaign_dir / f"{name}.body.spice"
        envelopes: list[tuple[str, dict]] = []
        shas: dict[str, str] = {}
        problems: list[str] = []
        checked: dict[str, dict] = {}
        for tag in build_mod.part_tags(bench):
            path = campaign_dir / f"{tag}.envelope.json"
            if path.is_file():
                raw = path.read_bytes()
                shas[tag] = hashlib.sha256(raw).hexdigest()
                try:
                    envelope = json.loads(raw)
                except (ValueError, UnicodeDecodeError) as exc:
                    problems.append(f"{tag}: envelope {path.name} is not valid JSON ({exc})")
                    continue
                if not isinstance(envelope, dict):
                    problems.append(f"{tag}: envelope {path.name} is not a JSON object")
                    continue
                envelopes.append((tag, envelope))
                checked[tag] = check_chain(bench, tag, campaign_dir, shas[tag], problems, corners)
        benches[name] = BenchEvidence(
            name=name,
            envelopes=envelopes,
            body_text=body_path.read_text(encoding="utf-8") if body_path.is_file() else None,
            envelope_files=shas,
            chain_problems=problems,
            chain_checked=checked,
        )
    return benches


def load_dut_reference() -> DutReference:
    dut_json = json.loads(build_mod.DUT_JSON.read_text(encoding="utf-8"))
    netlist = (build_mod.DUT_JSON.parent / dut_json["netlist"]).resolve()
    return DutReference(netlist.read_bytes(),
                        netlist.relative_to(build_mod.REPO_ROOT).as_posix(), dut_json)


def grade_campaign(campaign_dir: Path) -> dict:
    rows_spec = json.loads((build_mod.EXPERIMENT_DIR / "rows.json").read_text(encoding="utf-8"))
    result = grade(rows_spec, load_campaign(campaign_dir), load_dut_reference())
    result["campaign"] = campaign_dir.name
    return result


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _measured(entry: dict) -> str:
    target = entry.get("target") or {}
    rng = target.get("range")
    if not rng:
        if entry.get("evidence_kind") == "gap":
            return (entry.get("retained_record") or {}).get("recorded_value", "-")
        if entry.get("evidence_kind") == "coverage":
            return ", ".join(entry.get("benches_fully_covered") or []) or "-"
        return "-"
    prefix = ""
    if target.get("grid_mean") is not None:
        prefix = f"grid-wide mean {_fmt(target['grid_mean'])}; per point "
    elif target.get("partial_mean_ungraded") is not None:
        prefix = (f"partial mean {_fmt(target['partial_mean_ungraded'])} (UNGRADED: grid "
                  "incomplete); per point ")
    return (f"{prefix}{_fmt(rng['min']['value'])} ({rng['min']['point']}) ... "
            f"{_fmt(rng['max']['value'])} ({rng['max']['point']}); "
            f"{target['points_valid']}/{target['points_expected']} points valid")


def _binding(entry: dict) -> str:
    for column in ("target", "stretch"):
        b = (entry.get(column) or {}).get("binding")
        if b:
            worst = (entry.get(column) or {}).get("worst_point")
            tail = f"; worst single point {worst['point']} ({_fmt(worst['value'])})" if worst else ""
            return f"{b['point']} ({_fmt(b['value'])}){tail}"
    if entry.get("evidence_kind") == "gap":
        return (entry.get("retained_record") or {}).get("binding", "-")
    return "-"


def render_markdown(result: dict) -> str:
    lines = [
        f"# klt sim corner grading -- campaign `{result.get('campaign')}`",
        "",
        "GENERATED by `python3 sim/run_klt_corner_verification.py grade` from the",
        "committed envelopes in this directory and `sim/klt-corner-verification/rows.json`",
        f"(DR-0002 bounds, copied). DUT: `{result['dut']['netlist']}` sha256 "
        f"`{result['dut']['sha256'][:16]}...` (`sim/dut.json` id "
        f"`{result['dut']['dut_json_id']}`, provenance `{result['dut']['provenance']}`).",
        f"Grid: {result['grid_points']} PVT points.",
        "",
        "| Row | Sub-bound | Unit | Target | Target verdict | Stretch | Stretch verdict | Measured (klt sim) | Binding point |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in result["rows"]:
        tv = r["target_verdict"]
        if r.get("report_verdict"):
            tv = f"{tv} (reporting requirement: {r['report_verdict']})"
        lines.append(
            f"| {r['id']} | {r['sub_bound']} | {r.get('unit') or '-'} | {r['target_bound']} | "
            f"**{tv}** | {r['stretch_bound']} | **{r['stretch_verdict']}** | "
            f"{_measured(r)} | {_binding(r)} |")
    item5 = result["t1_item5"]
    lines += ["", "## T1 item 5", ""]
    if item5["all_target_rows_pass"]:
        lines.append("Every sub-bound with a ratified Target passes on klt sim evidence.")
    else:
        lines.append("Not every ratified Target is met on klt sim evidence:")
        lines.append("")
        for b in item5["blocking_sub_bounds"]:
            lines.append(f"- **{b['id']}** {b['sub_bound']}: {b['target_verdict']}")
    lines += ["", "## Gaps and incomplete points", ""]
    for r in result["rows"]:
        rec = r.get("retained_record") or {}
        if r.get("evidence_kind") == "klt_sim" and rec:
            lines.append(f"- **{r['id']}** -- statistic computed by `sim/kltsim/grade.py` from klt "
                         f"sim's per-corner means (klt cannot grade it: {r.get('tool_gap')}). "
                         f"Cross-check against the retained non-klt record `{rec.get('path')}`: "
                         f"{rec.get('recorded_value')}; Target {rec.get('recorded_verdict_target')}, "
                         f"Stretch {rec.get('recorded_verdict_stretch')}.")
        if r.get("evidence_kind") == "gap":
            rec = r.get("retained_record") or {}
            lines.append(f"- **{r['id']}** -- GAP: {r.get('gap_reason')} Tool gap: {r.get('tool_gap')}. "
                         f"Retained non-klt record `{rec.get('path')}`: {rec.get('recorded_value')}; "
                         f"Target {rec.get('recorded_verdict_target')}, Stretch "
                         f"{rec.get('recorded_verdict_stretch')}.")
        for column in ("target",):
            missing = (r.get(column) or {}).get("points_missing_or_invalid") or []
            if missing:
                lines.append(f"- **{r['id']}** -- {len(missing)} point(s) without a valid value; "
                             f"first: {missing[0]['point']}: {missing[0]['why']}")
        for note in r.get("notes") or []:
            lines.append(f"- **{r['id']}** -- note: {note}")
        if r.get("coverage_problems"):
            for p in r["coverage_problems"]:
                lines.append(f"- **{r['id']}** -- {p}")
        if r.get("chain_problems"):
            lines.append(f"- **{r['id']}** -- rejected evidence: {'; '.join(r['chain_problems'])}")
        if r.get("dut_problems"):
            lines.append(f"- **{r['id']}** -- wrong DUT: {'; '.join(r['dut_problems'])}")
    lines += ["", "## Evidence", ""]
    for name, info in result["benches"].items():
        for env in info["envelopes"]:
            job = env.get("batch_job") or {}
            lines.append(
                f"- `{env['envelope']}` (sha256 `{(env.get('envelope_sha256') or '')[:16]}...`): "
                f"status `{env['status']}`, {env['corner_count']} units "
                f"({env['passed']} pass / {env['failed']} fail / {env['errored']} error), "
                f"input `{env['input_content_hash']}`, klt `{env['klt_version']}`, "
                f"ngspice {env['engine_version']}, batch job `{job.get('job_id')}`")
    return "\n".join(lines) + "\n"


def render_summary(result: dict) -> str:
    out = []
    for r in result["rows"]:
        out.append(f"{r['id']:>3}  target={r['target_verdict']:<14} stretch={r['stretch_verdict']:<14} "
                   f"{_binding(r)}")
    item5 = result["t1_item5"]
    out.append(f"T1 item 5 all Target rows pass: {item5['all_target_rows_pass']}")
    return "\n".join(out)
