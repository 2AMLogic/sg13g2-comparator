"""Whole-latch offset across a bounded input common-mode band (issue #79).

CHARACTERIZATION, NOT COMPLIANCE. DR-0002 ratifies the Offset-sigma row at
the DUT's own ``dut_vcm`` only and ratifies no whole-latch common-mode
range. This module measures the same whole-latch statistic at three input
common modes -- ``dut_vcm - 50 mV``, ``dut_vcm``, ``dut_vcm + 50 mV`` -- and
reports how it moves. It never grades a non-nominal condition as a spec
verdict; the 15 mV Target is quoted beside each number as a reference
only. A binding operating range needs its own decision record.

HOW A CONDITION IS SELECTED. Each condition is its own ``klt sim`` campaign
built from the issue #62 ``offset_mc`` bench (``sim/kltsim/benches.py``),
unchanged in every respect but one line of its netlist body: the
common-mode source

    vcm cm 0 dc {dut_vcm}

becomes

    .param vcm_delta=<delta>
    vcm cm 0 dc {dut_vcm+vcm_delta}

for all three conditions, the nominal one included (``vcm_delta=0.0``), so
the three bodies differ only in that one ``.param`` value and their header.
The condition is recorded in the body header, in the request (``_comment``
and ``_condition``) and in every invocation record; nothing historical is
edited.

PAIRING. ``klt sim`` derives each sample's ngspice seed from
``(monte_carlo.seed, corner_index, sample_index)`` only (its SHA-256 seed
contract), never from the netlist, and the three conditions use the same
base seed (20260916), the same per-process request split and the same
corner order. Sample ``k`` at a grid point therefore carries the same seed
-- the same mismatch draw -- under all three conditions, so per-sample
differences are paired. ``paired()`` verifies that from the envelopes
rather than assuming it.

STATISTICS. Per grid point and condition: N, clipped draws (the bench's
own range-adequacy gate: a draw whose offset lands outside the swept
+/-48 mV staircase), mean offset, raw (population) sigma, Bessel sigma, and
the ratified quantization-corrected 3-sigma,
``3*sqrt(pop_var - step^2/12)`` -- the same statistic as
``sim/comparator-offset-transient-mc``'s ``vos_3sig_mv`` and
``kltsim.grade.three_sigma_dr_basis``. A population with any clipped,
errored or probe-inconsistent draw, with N other than the ratified 60, or
with zero spread (mismatch not applied) is REJECTED: no sigma is reported
for it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from . import build as build_mod
from . import grade as grade_mod
from .benches import (OFFSET_MC, Meas, OFFSET_MC_N, OFFSET_MC_STEP_V, PROCESSES, SUPPLIES_V,
                      TEMPERATURES_C)

EXPERIMENT_DIR = build_mod.SIM_DIR / "comparator-offset-cm-band"
SERIES_DIR = EXPERIMENT_DIR / "campaigns"

#: The per-condition bench name / body stem / request-tag prefix.
BENCH_NAME = "offset_cm"
BODY_NAME = f"{BENCH_NAME}.body.spice"

VCM_LINE = "vcm cm 0 dc {dut_vcm}"
VCM_LINE_CM = "vcm cm 0 dc {dut_vcm+vcm_delta}"
CONDITION_MARK = "* ---- CM-band condition (issue #79):"

#: DR-0002 Row 1 Target, quoted as a reference only (see module docstring).
TARGET_3SIGMA_MV = 15.0
STEP_MV = OFFSET_MC_STEP_V * 1e3
#: bootstrap for the paired sigma-ratio interval: fixed seed, so the
#: committed comparison regenerates bit for bit.
BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 79

#: The issue #62 campaign whose offset_mc envelopes the nominal condition
#: must reproduce sample for sample (same seed contract, same circuit).
REFERENCE_CAMPAIGN = "20261009-d73a9ac"
#: The DR-0002 Row 1 record (harness, in-process setseed + reset loop).
HARNESS_RECORD = (build_mod.SIM_DIR / "comparator-offset-transient-mc" / "records"
                  / "20260917-060858-ea40b57.json")


class CmBandError(RuntimeError):
    pass


@dataclass(frozen=True)
class Condition:
    name: str
    delta_v: float

    def vcm_v(self) -> float:
        base = float((build_mod.load_dut_binding().get("params") or {})["dut_vcm"])
        return round(base + self.delta_v, 9)


CONDITIONS = (
    Condition("vcm-m050", -0.05),
    Condition("vcm-nom", 0.0),
    Condition("vcm-p050", 0.05),
)
NOMINAL = "vcm-nom"


def condition(name: str) -> Condition:
    for cond in CONDITIONS:
        if cond.name == name:
            return cond
    raise CmBandError(f"unknown condition {name!r}; known: {[c.name for c in CONDITIONS]}")


#: Condition-application probe: the input common mode actually simulated.
#: A sample whose probe disagrees with its condition is untrusted.
VCM_PROBE = Meas("vcm_meas", ".meas tran vcm_meas find v(cm) at=5n", "V", role="probe")
VCM_TOL_V = 1e-6


def bench_for(cond: Condition):
    """The #62 offset_mc bench, renamed, with the condition in its description
    and one added probe (``vcm_meas``). Analysis, the offset measurements,
    limits, timeout and Monte-Carlo basis are unchanged."""
    return dataclasses.replace(
        OFFSET_MC,
        name=BENCH_NAME,
        measurements=OFFSET_MC.measurements + (VCM_PROBE,),
        description=(
            f"CHARACTERIZATION (issue #79), condition {cond.name}: whole-latch "
            f"input-referred offset at input common mode dut_vcm{cond.delta_v * 1e3:+.0f} mV, "
            "one mismatch draw per klt sim Monte-Carlo sample, N = 60 per PVT point. "
            "Not a DR-0002 compliance measurement: no whole-latch common-mode range is "
            "ratified."
        ),
    )


# --------------------------------------------------------------------------- #
# body + request
# --------------------------------------------------------------------------- #


def apply_transform(body: str, cond: Condition) -> str:
    """Rewrite the one common-mode source line and stamp the header."""
    lines = body.split("\n")
    hits = [i for i, line in enumerate(lines) if line == VCM_LINE]
    if len(hits) != 1:
        raise CmBandError(
            f"expected exactly one `{VCM_LINE}` line in the offset body, found {len(hits)}")
    i = hits[0]
    lines[i:i + 1] = [
        f"{CONDITION_MARK} {cond.name}, input common mode = dut_vcm + vcm_delta",
        f".param vcm_delta={cond.delta_v!r}",
        VCM_LINE_CM,
    ]
    if len(lines) < 2:
        raise CmBandError("offset body has no header")
    lines[0] = (f"* {BENCH_NAME} -- klt sim netlist BODY (sim/comparator-offset-cm-band, "
                f"issue #79) condition={cond.name} vcm_delta={cond.delta_v!r}")
    lines[1] = ("* GENERATED by `python3 sim/run_offset_cm_band.py build` from the issue #62 "
                "offset_mc body (sim/kltsim/cmband.py) -- do not edit;")
    return "\n".join(lines)


def undo_transform(body: str) -> str:
    """Inverse of the line rewrite (header excepted) -- for tests/audit."""
    out = []
    for line in body.split("\n"):
        if line.startswith(CONDITION_MARK) or line.startswith(".param vcm_delta="):
            continue
        out.append(VCM_LINE if line == VCM_LINE_CM else line)
    return "\n".join(out)


def compose_cm_body(cond: Condition, osdi_dir: str) -> str:
    return apply_transform(build_mod.compose_body(OFFSET_MC, osdi_dir), cond)


def condition_metadata(cond: Condition) -> dict:
    return {
        "issue": 79,
        "name": cond.name,
        "vcm_delta_v": cond.delta_v,
        "vcm_v": cond.vcm_v(),
        "scope": "characterization (no ratified whole-latch common-mode range)",
        "pairing": "same monte_carlo.seed, request split and corner order as every other "
                   "condition: sample k at a grid point is the same mismatch draw",
    }


def compose_cm_request(cond: Condition, body_name: str, section: str,
                       backend: str = "batch") -> dict:
    bench = bench_for(cond)
    request = build_mod.compose_request(bench, body_name, backend, processes=(section,))
    request["_comment"] = [
        f"sg13g2-comparator -- klt sim request, CM-band offset condition `{cond.name}` "
        "(issue #79).",
        "GENERATED by `python3 sim/run_offset_cm_band.py build`; the committed copy is "
        "byte-for-byte what was submitted.",
        bench.description,
        "Measurements, limits, analysis and monte_carlo are the issue #62 offset_mc "
        "bench's, unchanged.",
    ]
    request["_condition"] = condition_metadata(cond)
    return request


def write_condition_inputs(cond: Condition, out_dir: Path, *,
                           osdi_dir: str = build_mod.BATCH_OSDI_DIR,
                           backend: str = "batch") -> tuple[Path, list[Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    body = out_dir / BODY_NAME
    body.write_text(compose_cm_body(cond, osdi_dir), encoding="utf-8")
    requests = []
    for section in OFFSET_MC.process_sections:
        path = out_dir / f"{BENCH_NAME}.{section}.request.json"
        req = compose_cm_request(cond, BODY_NAME, section, backend)
        path.write_text(json.dumps(req, indent=2) + "\n", encoding="utf-8")
        requests.append(path)
    return body, requests


def part_tags() -> list[str]:
    return [f"{BENCH_NAME}.{section}" for section in OFFSET_MC.process_sections]


# --------------------------------------------------------------------------- #
# analysis
# --------------------------------------------------------------------------- #


def load_points(envelopes: list[dict], vcm_v: float | None = None) -> dict[tuple, list[dict]]:
    """Per grid point, its Monte-Carlo samples (sorted by sample index).

    With ``vcm_v``, a sample whose ``vcm_meas`` probe is missing or differs
    from it is untrusted (the condition was not applied)."""
    points: dict[tuple, list[dict]] = {}
    for env in envelopes:
        for corner in env.get("corners") or []:
            mc = corner.get("monte_carlo")
            if mc is None:
                continue
            key = grade_mod._corner_key(corner)
            values = {m["name"]: m for m in corner.get("measurements") or []}
            lc = values.get("lowcount") or {}
            vos = values.get("vos_mv") or {}
            problem = grade_mod._corner_problems(corner, OFFSET_MC.name, gates=[])
            clipped = lc.get("value") is not None and lc.get("status") != "pass"
            if lc.get("value") is None and problem is None:
                problem = "lowcount not reported"
            if vos.get("value") is None and problem is None:
                problem = "vos_mv not reported"
            if vcm_v is not None and problem is None:
                probe = (values.get(VCM_PROBE.name) or {}).get("value")
                if probe is None:
                    problem = "common-mode probe vcm_meas missing"
                elif abs(float(probe) - vcm_v) > VCM_TOL_V:
                    problem = f"common-mode probe vcm_meas={probe} V is not the condition's {vcm_v} V"
            points.setdefault(key, []).append({
                "corner_id": corner.get("corner_id"),
                "sample_index": mc.get("sample_index"),
                "seed": mc.get("seed"),
                "vos_mv": vos.get("value"),
                "lowcount": lc.get("value"),
                "clipped": bool(clipped),
                "problem": problem,
                "runtime_s": corner.get("runtime_s"),
            })
    for samples in points.values():
        samples.sort(key=lambda s: s["sample_index"])
    return points


def population_stats(values: list[float]) -> dict:
    n = len(values)
    mean = sum(values) / n
    var_pop = sum((v - mean) ** 2 for v in values) / n
    var_bessel = var_pop * n / (n - 1) if n > 1 else 0.0
    var_corr = var_pop - STEP_MV * STEP_MV / 12.0
    return {
        "n": n,
        "mean_mv": mean,
        "sigma_raw_mv": math.sqrt(var_pop),
        "sigma_bessel_mv": math.sqrt(var_bessel),
        "sigma_corr_mv": math.sqrt(max(var_corr, 0.0)),
        "three_sigma_mv": 3.0 * math.sqrt(max(var_corr, 0.0)),
    }


def point_stats(samples: list[dict], expected_n: int = OFFSET_MC_N) -> dict:
    n = len(samples)
    clipped = sum(1 for s in samples if s["clipped"])
    untrusted = [s for s in samples if s["problem"]]
    runtimes = [s["runtime_s"] for s in samples if s.get("runtime_s") is not None]
    out = {
        "n": n, "clipped": clipped, "untrusted": len(untrusted),
        "mean_mv": None, "sigma_raw_mv": None, "sigma_bessel_mv": None,
        "sigma_corr_mv": None, "three_sigma_mv": None, "rejected": None,
        "runtime_max_s": max(runtimes) if runtimes else None,
        "runtime_mean_s": sum(runtimes) / len(runtimes) if runtimes else None,
    }
    values = [s["vos_mv"] for s in samples if s["vos_mv"] is not None and not s["problem"]]
    if values and len(values) > 1:
        out.update({k: v for k, v in population_stats(values).items() if k != "n"})
    if untrusted:
        out["rejected"] = (f"{len(untrusted)} untrusted draw(s): "
                           f"{untrusted[0]['corner_id']}: {untrusted[0]['problem']}")
    elif clipped:
        out["rejected"] = (f"{clipped} clipped draw(s) (offset outside the swept "
                           "+/-48 mV staircase)")
    elif n != expected_n:
        out["rejected"] = f"N = {n}, ratified basis is N = {expected_n}"
    elif not out["sigma_raw_mv"]:
        out["rejected"] = "zero spread: mismatch not applied"
    if out["rejected"]:
        # Informational only, and only when every in-hand draw is trusted and
        # in-window (a solver abort / missing draw, not a clipped one): the
        # statistic over the draws that did complete. Never a valid population.
        partial = out["three_sigma_mv"] if (not clipped and len(values) > 1) else None
        out["three_sigma_partial_mv"] = partial
        out["n_partial"] = len(values) if partial is not None else None
        out["sigma_corr_mv"] = None
        out["three_sigma_mv"] = None
    return out


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def paired(cm: list[dict], nom: list[dict]) -> dict:
    """Paired comparison of one grid point under a condition vs nominal."""
    a = {s["sample_index"]: s for s in cm}
    b = {s["sample_index"]: s for s in nom}
    seeds_paired = set(a) == set(b) and all(a[k]["seed"] == b[k]["seed"] for k in a)
    out = {"seeds_paired": seeds_paired, "n_pairs": len(set(a) & set(b)),
           "delta_mean_mv": None, "delta_sd_mv": None, "delta_sem_mv": None,
           "corr": None, "ratio_3sigma": None, "ratio_ci95": None, "delta_3sigma_mv": None}
    st_a, st_b = point_stats(cm), point_stats(nom)
    if not seeds_paired or st_a["rejected"] or st_b["rejected"]:
        return out
    idx = sorted(a)
    xs = [a[k]["vos_mv"] for k in idx]
    ys = [b[k]["vos_mv"] for k in idx]
    d = [x - y for x, y in zip(xs, ys)]
    n = len(d)
    dm = sum(d) / n
    dsd = math.sqrt(sum((v - dm) ** 2 for v in d) / (n - 1)) if n > 1 else 0.0
    ratio = st_a["three_sigma_mv"] / st_b["three_sigma_mv"] if st_b["three_sigma_mv"] else None
    rng = random.Random(BOOTSTRAP_SEED)
    ratios = []
    for _ in range(BOOTSTRAP_N):
        pick = [rng.randrange(n) for _ in range(n)]
        ta = population_stats([xs[i] for i in pick])["three_sigma_mv"]
        tb = population_stats([ys[i] for i in pick])["three_sigma_mv"]
        if tb > 0:
            ratios.append(ta / tb)
    ratios.sort()
    ci = None
    if len(ratios) >= 40:
        ci = [ratios[int(0.025 * len(ratios))], ratios[int(0.975 * len(ratios)) - 1]]
    out.update({
        "delta_mean_mv": dm, "delta_sd_mv": dsd, "delta_sem_mv": dsd / math.sqrt(n),
        "corr": _pearson(xs, ys), "ratio_3sigma": ratio, "ratio_ci95": ci,
        "delta_3sigma_mv": st_a["three_sigma_mv"] - st_b["three_sigma_mv"],
    })
    return out


def reproduction(a: dict[tuple, list[dict]], b: dict[tuple, list[dict]]) -> dict:
    """Sample-for-sample comparison of two populations over shared points."""
    compared = identical = seed_mismatch = 0
    max_diff = 0.0
    missing = sorted(set(a) ^ set(b), key=str)
    for key in sorted(set(a) & set(b), key=str):
        bmap = {s["sample_index"]: s for s in b[key]}
        for s in a[key]:
            t = bmap.get(s["sample_index"])
            if t is None or s["vos_mv"] is None or t["vos_mv"] is None:
                continue
            compared += 1
            if s["seed"] != t["seed"]:
                seed_mismatch += 1
            diff = abs(s["vos_mv"] - t["vos_mv"])
            max_diff = max(max_diff, diff)
            if diff == 0.0:
                identical += 1
    return {"points_compared": len(set(a) & set(b)), "points_unmatched": len(missing),
            "samples_compared": compared, "identical": identical,
            "seed_mismatches": seed_mismatch, "max_abs_diff_mv": max_diff}


def _load_envelopes(directory: Path, pattern: str) -> list[tuple[str, dict, str]]:
    out = []
    for path in sorted(directory.glob(pattern)):
        raw = path.read_bytes()
        out.append((path.name[: -len(".envelope.json")], json.loads(raw),
                    hashlib.sha256(raw).hexdigest()))
    return out


def _grid_keys(grid) -> list[tuple]:
    procs, supplies, temps = grid
    return [(p, round(float(v), 6), float(t)) for p in procs for v in supplies for t in temps]


def _label(key) -> str:
    return grade_mod.key_label(key)


def _summary(values: list[tuple[tuple, float]]) -> dict:
    if not values:
        return {"min": None, "max": None, "mean": None, "binding": None}
    lo = min(values, key=lambda kv: kv[1])
    hi = max(values, key=lambda kv: kv[1])
    return {"min": lo[1], "min_point": _label(lo[0]), "max": hi[1],
            "binding": _label(hi[0]), "mean": sum(v for _, v in values) / len(values)}


def _harness_points(path: Path) -> dict[tuple, float]:
    record = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for p in record.get("points") or []:
        proc = p["corner"][: -len("_mismatch")] if p["corner"].endswith("_mismatch") else p["corner"]
        out[(proc, round(float(p["vdd"]), 6), float(p["temp_c"]))] = \
            float(p["measurements"]["vos_3sig_mv"])
    return out


def compare_series(series_dir: Path, *, grid=None, reference_campaign: str | None = REFERENCE_CAMPAIGN,
                   harness_record: Path | None = None) -> dict:
    grid = grid or (PROCESSES, SUPPLIES_V, TEMPERATURES_C)
    keys = _grid_keys(grid)
    loaded: dict[str, dict[tuple, list[dict]]] = {}
    sources: dict[str, list[dict]] = {}
    for cond in CONDITIONS:
        envs = _load_envelopes(series_dir / cond.name, f"{BENCH_NAME}.*.envelope.json")
        loaded[cond.name] = load_points([e for _, e, _ in envs], vcm_v=cond.vcm_v())
        sources[cond.name] = [{
            "tag": tag, "envelope_sha256": sha,
            "status": env.get("status"),
            "job_id": ((env.get("environment") or {}).get("remote") or {}).get("job_id"),
            "content_hash": ((env.get("provenance") or {}).get("input") or {}).get("content_hash"),
            "klt_version": (env.get("provenance") or {}).get("klt_version"),
        } for tag, env, sha in envs]

    points = []
    per_cond_vals: dict[str, list] = {c.name: [] for c in CONDITIONS}
    per_cond_stats: dict[str, list] = {c.name: [] for c in CONDITIONS}
    for key in keys:
        row = {"point": _label(key), "stats": {}, "paired": {}}
        for cond in CONDITIONS:
            samples = loaded[cond.name].get(key)
            if samples is None:
                st = {"n": 0, "clipped": 0, "untrusted": 0, "three_sigma_mv": None,
                      "rejected": "grid point not in any envelope"}
            else:
                st = point_stats(samples)
            row["stats"][cond.name] = st
            per_cond_stats[cond.name].append(st)
            if st.get("three_sigma_mv") is not None:
                per_cond_vals[cond.name].append((key, st["three_sigma_mv"]))
        nom = loaded[NOMINAL].get(key)
        for cond in CONDITIONS:
            if cond.name == NOMINAL:
                continue
            cm = loaded[cond.name].get(key)
            row["paired"][cond.name] = paired(cm, nom) if (cm and nom) else None
        points.append(row)

    conditions = {}
    for cond in CONDITIONS:
        stats = per_cond_stats[cond.name]
        vals = per_cond_vals[cond.name]
        runtimes = [s.get("runtime_max_s") for s in stats if s.get("runtime_max_s") is not None]
        conditions[cond.name] = {
            "vcm_delta_v": cond.delta_v,
            "vcm_v": cond.vcm_v(),
            "points_expected": len(keys),
            "points_valid": len(vals),
            "points_rejected": [{"point": points[i]["point"], "reason": s["rejected"],
                                 "three_sigma_partial_mv": s.get("three_sigma_partial_mv"),
                                 "n_partial": s.get("n_partial")}
                                for i, s in enumerate(stats) if s.get("rejected")],
            "clipped_draws": sum(s.get("clipped") or 0 for s in stats),
            "three_sigma_mv": _summary(vals),
            "points_within_target": sum(1 for _, v in vals if v <= TARGET_3SIGMA_MV),
            "sample_runtime_max_s": max(runtimes) if runtimes else None,
            "envelopes": sources[cond.name],
        }

    pair_summary = {}
    for cond in CONDITIONS:
        if cond.name == NOMINAL:
            continue
        pairs = [r["paired"][cond.name] for r in points if r["paired"].get(cond.name)]
        good = [p for p in pairs if p["ratio_3sigma"] is not None]
        pair_summary[cond.name] = {
            "points_paired": len(good),
            "seeds_paired_everywhere": bool(pairs) and all(p["seeds_paired"] for p in pairs),
            "ratio_mean": (sum(p["ratio_3sigma"] for p in good) / len(good)) if good else None,
            "ratio_min": min((p["ratio_3sigma"] for p in good), default=None),
            "ratio_max": max((p["ratio_3sigma"] for p in good), default=None),
            "ci_excludes_1_up": sum(1 for p in good if p["ratio_ci95"] and p["ratio_ci95"][0] > 1),
            "ci_excludes_1_down": sum(1 for p in good if p["ratio_ci95"] and p["ratio_ci95"][1] < 1),
            "delta_mean_mv_min": min((p["delta_mean_mv"] for p in good), default=None),
            "delta_mean_mv_max": max((p["delta_mean_mv"] for p in good), default=None),
            "corr_min": min((p["corr"] for p in good if p["corr"] is not None), default=None),
        }

    result = {
        "issue": 79,
        "series": series_dir.name,
        "scope": ("CHARACTERIZATION: DR-0002 ratifies the whole-latch offset at dut_vcm only "
                  "and no whole-latch common-mode range; the 15 mV Target is quoted as a "
                  "reference, never as a verdict on a non-nominal condition."),
        "basis": {"n_per_point": OFFSET_MC_N, "seed": OFFSET_MC.monte_carlo["seed"],
                  "sigma_relative_precision": 1 / math.sqrt(2 * OFFSET_MC_N),
                  "step_mv": STEP_MV, "statistic": "3*sqrt(pop_var - step^2/12)",
                  "bootstrap": {"n": BOOTSTRAP_N, "seed": BOOTSTRAP_SEED}},
        "conditions": conditions,
        "paired_summary": pair_summary,
        "points": points,
        "nominal_reproduction": None,
        "harness_record": None,
        "controls": None,
    }

    if reference_campaign:
        ref_dir = build_mod.EXPERIMENT_DIR / "campaigns" / reference_campaign
        ref = _load_envelopes(ref_dir, "offset_mc.*.envelope.json")
        if ref:
            ref_points = load_points([e for _, e, _ in ref])
            rep = reproduction(loaded[NOMINAL], ref_points)
            rep["reference"] = f"sim/klt-corner-verification/campaigns/{reference_campaign}"
            result["nominal_reproduction"] = rep

    if harness_record and Path(harness_record).is_file():
        hp = _harness_points(Path(harness_record))
        rows = []
        for key in keys:
            st = next(r for r in points if r["point"] == _label(key))["stats"][NOMINAL]
            h = hp.get(key)
            k = st.get("three_sigma_mv")
            rows.append({"point": _label(key), "harness_3sigma_mv": h, "klt_nominal_3sigma_mv": k,
                         "ratio": (k / h) if (h and k) else None})
        ratios = [r["ratio"] for r in rows if r["ratio"] is not None]
        hs = [r["harness_3sigma_mv"] for r in rows if r["harness_3sigma_mv"] is not None]
        ks = [r["klt_nominal_3sigma_mv"] for r in rows if r["klt_nominal_3sigma_mv"] is not None]
        result["harness_record"] = {
            "record": Path(harness_record).relative_to(build_mod.REPO_ROOT).as_posix()
            if Path(harness_record).is_absolute() else str(harness_record),
            "grid_mean_harness_mv": sum(hs) / len(hs) if hs else None,
            "grid_mean_klt_nominal_mv": sum(ks) / len(ks) if ks else None,
            "ratio_mean": sum(ratios) / len(ratios) if ratios else None,
            "points": rows,
        }

    controls_dir = series_dir / "controls"
    if controls_dir.is_dir():
        result["controls"] = _controls(controls_dir, loaded)
    return result


def _controls(controls_dir: Path, loaded: dict) -> dict:
    out = {"negative": [], "repeat": []}
    for tag, env, sha in _load_envelopes(controls_dir, "negctrl.*.envelope.json"):
        pts = load_points([env])
        for key, samples in sorted(pts.items(), key=lambda kv: str(kv[0])):
            vals = [s["vos_mv"] for s in samples if s["vos_mv"] is not None]
            st = population_stats(vals) if len(vals) > 1 else {}
            out["negative"].append({
                "tag": tag, "envelope_sha256": sha, "point": _label(key),
                "n": len(samples), "distinct_values": len(set(vals)),
                "sigma_raw_mv": st.get("sigma_raw_mv"), "mean_mv": st.get("mean_mv"),
                "collapsed": len(set(vals)) == 1 and len(vals) == len(samples),
            })
    for tag, env, sha in _load_envelopes(controls_dir, "repeat.*.envelope.json"):
        cond = tag.split(".")[1]
        pts = load_points([env])
        rep = reproduction(pts, {k: v for k, v in loaded.get(cond, {}).items() if k in pts})
        rep.update({"tag": tag, "envelope_sha256": sha, "condition": cond,
                    "points": [_label(k) for k in sorted(pts, key=str)]})
        out["repeat"].append(rep)
    return out


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #


def _f(value, nd=3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{nd}f}"
    return str(value)


def render_markdown(result: dict) -> str:
    conds = [c.name for c in CONDITIONS]
    others = [c for c in conds if c != NOMINAL]
    b = result["basis"]
    out = [
        f"# Whole-latch offset vs input common mode — series `{result['series']}`",
        "",
        "GENERATED by `python3 sim/run_offset_cm_band.py compare` from the committed",
        "envelopes; do not edit.",
        "",
        "## Scope",
        "",
        f"**Characterization, not compliance.** {result['scope']}",
        "The DR-0002 Row 1 compliance basis stays the nominal-common-mode record.",
        "",
        "## Statistical basis",
        "",
        f"- Monte Carlo over SG13G2's shipped `mos_<p>_mismatch` sections, N = {b['n_per_point']}"
        f" draws per PVT point per condition, klt base seed {b['seed']}.",
        f"- Statistic: {b['statistic']} (step = {b['step_mv']:g} mV), the ratified Row 1 statistic.",
        f"- Precision of each per-point sigma: 1/sqrt(2N) = {100 * b['sigma_relative_precision']:.1f} %.",
        "- Paired comparisons: sample k at a grid point is the same mismatch draw under every"
        " condition (same seed contract), checked per point below. Ratio intervals are a"
        f" paired bootstrap ({b['bootstrap']['n']} resamples, seed {b['bootstrap']['seed']}),"
        " 95 %.",
        "- A population with any clipped (outside ±48 mV), errored or probe-inconsistent draw,"
        " N ≠ 60, or zero spread is REJECTED and reports no sigma.",
        "",
        "## Per condition",
        "",
        "| condition | input CM | valid points | clipped draws | 3σ min … max (mV) | grid mean 3σ | binding point | ≤ 15 mV (reference) | max sample runtime |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in conds:
        s = result["conditions"][c]
        t = s["three_sigma_mv"]
        out.append(
            f"| `{c}` | {s['vcm_v']:.3f} V | {s['points_valid']}/{s['points_expected']} | "
            f"{s['clipped_draws']} | {_f(t['min'])} … {_f(t['max'])} | {_f(t['mean'])} | "
            f"`{t['binding']}` | {s['points_within_target']}/{s['points_valid']} | "
            f"{_f(s['sample_runtime_max_s'], 1)} s |")
    rejected = [(c, r) for c in conds for r in result["conditions"][c]["points_rejected"]]
    if rejected:
        out += ["", "Rejected populations:", ""]
        for c, r in rejected:
            line = f"- `{c}` `{r['point']}`: {r['reason']}"
            if r.get("three_sigma_partial_mv") is not None:
                line += (f". Informational only, NOT a valid population: 3σ over the "
                         f"{r['n_partial']} completed draws = {r['three_sigma_partial_mv']:.3f} mV")
            out.append(line)
    out += ["", "## Paired sensitivity vs nominal", ""]
    out += ["| condition | points paired | seeds paired | 3σ ratio mean (min … max) | CI > 1 | CI < 1 | Δmean min … max (mV) | min paired corr |",
            "|---|---|---|---|---|---|---|---|"]
    for c in others:
        p = result["paired_summary"][c]
        out.append(
            f"| `{c}` | {p['points_paired']} | {'yes' if p['seeds_paired_everywhere'] else '**NO**'} | "
            f"{_f(p['ratio_mean'])} ({_f(p['ratio_min'])} … {_f(p['ratio_max'])}) | "
            f"{p['ci_excludes_1_up']} | {p['ci_excludes_1_down']} | "
            f"{_f(p['delta_mean_mv_min'])} … {_f(p['delta_mean_mv_max'])} | {_f(p['corr_min'])} |")
    out += ["", "## Per PVT point", "",
            "3σ in mV (ratified statistic); ratio = condition / nominal with its paired 95 % "
            "interval; Δmean = paired mean offset shift vs nominal ± its standard error.", "",
            "| point | " + " | ".join(f"3σ `{c}`" for c in conds) + " | "
            + " | ".join(f"ratio `{c}`" for c in others) + " | "
            + " | ".join(f"Δmean `{c}`" for c in others) + " |",
            "|---" * (1 + len(conds) + 2 * len(others)) + "|"]
    for row in result["points"]:
        cells = [f"`{row['point']}`"]
        for c in conds:
            st = row["stats"][c]
            cells.append("REJECTED" if st.get("rejected") else _f(st.get("three_sigma_mv")))
        for c in others:
            p = row["paired"].get(c)
            if p and p["ratio_3sigma"] is not None:
                ci = p["ratio_ci95"]
                cells.append(f"{p['ratio_3sigma']:.3f} [{_f(ci[0])}, {_f(ci[1])}]" if ci
                             else f"{p['ratio_3sigma']:.3f}")
            else:
                cells.append("—")
        for c in others:
            p = row["paired"].get(c)
            cells.append(f"{p['delta_mean_mv']:+.3f} ± {p['delta_sem_mv']:.3f}"
                         if p and p["delta_mean_mv"] is not None else "—")
        out.append("| " + " | ".join(cells) + " |")

    out += ["", "## Nominal reproduction", ""]
    rep = result.get("nominal_reproduction")
    if rep:
        out.append(
            f"`{NOMINAL}` against `{rep['reference']}` (issue #62 `offset_mc`, same seed, same "
            f"circuit): {rep['identical']}/{rep['samples_compared']} draws bit-identical over "
            f"{rep['points_compared']} points, {rep['seed_mismatches']} seed mismatches, max "
            f"|Δvos| = {rep['max_abs_diff_mv']:.6g} mV.")
    else:
        out.append("Not evaluated (no reference campaign envelopes found).")
    hr = result.get("harness_record")
    if hr:
        out += ["",
                f"Against the DR-0002 Row 1 harness record `{hr['record']}` (in-process "
                "`setseed` + `reset` loop): grid-mean 3σ "
                f"{_f(hr['grid_mean_klt_nominal_mv'])} mV here vs {_f(hr['grid_mean_harness_mv'])} mV "
                f"there, mean per-point ratio {_f(hr['ratio_mean'])}. **This is the systematic "
                "klt-per-draw vs harness difference tracked in "
                "[#82](https://github.com/2AMLogic/sg13g2-comparator/issues/82), cause not "
                "determined.** All three conditions here share the klt per-draw method, so the "
                "paired common-mode comparisons above are within one basis; absolute levels "
                "inherit whatever #82 resolves."]
    ctl = result.get("controls")
    out += ["", "## Controls", ""]
    if ctl:
        for neg in ctl["negative"]:
            out.append(
                f"- Mismatch-off (`{neg['tag']}`, `{neg['point']}`): N = {neg['n']}, "
                f"{neg['distinct_values']} distinct offset value(s), σ = {_f(neg['sigma_raw_mv'], 6)} mV "
                f"→ {'collapsed as required' if neg['collapsed'] else '**NOT collapsed**'}.")
        for r in ctl["repeat"]:
            out.append(
                f"- Same-seed repeat (`{r['tag']}`, {', '.join(f'`{p}`' for p in r['points'])}): "
                f"{r['identical']}/{r['samples_compared']} draws bit-identical to the campaign, "
                f"{r['seed_mismatches']} seed mismatches, max |Δvos| = {r['max_abs_diff_mv']:.6g} mV.")
        if not ctl["negative"] and not ctl["repeat"]:
            out.append("None committed.")
    else:
        out.append("None committed.")
    out += ["", "## Envelopes", ""]
    for c in conds:
        for e in result["conditions"][c]["envelopes"]:
            out.append(f"- `{c}/{e['tag']}`: status `{e['status']}`, job `{e['job_id']}`, "
                       f"klt {e['klt_version']}, sha256 `{e['envelope_sha256'][:16]}…`")
    return "\n".join(out) + "\n"
