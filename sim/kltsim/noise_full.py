"""Issue #81 analysis: whole-latch transient noise with internal-node injection.

Reads the three ``klt sim`` configurations of a campaign directory --

* ``tn_full_fe``   front-end (input-referred) source only; the issue #62
                   ``transient_noise`` bench re-run in the same campaign,
* ``tn_full_int_probed`` regenerative-pair + reset-device sources only,
* ``tn_full_both`` complete injection,

computes each configuration's per-point two-rung probit-slope sigma with the
SAME rules ``kltsim.grade`` applies to DR-0002 Row 2 (exactly N = 80 samples,
trusted corner probes, independent raw-noise draws, zero-rung injection
guard, no saturated rung -- ``grade.mc_probit_noise`` is reused as is), adds
a per-point statistical precision, and splits the total in quadrature.

Also analysed when their envelopes are present (never graded): the negative
control ``tn_full_zero`` (internal densities scaled to 0, front end on --
must reproduce ``fe``), and the sensitivity runs ``tn_full_int_x4`` /
``tn_full_int_x8`` (internal noise only, scaled up so the rungs stop
saturating; the 1x internal term is read as sigma(xK)/K, the linearity of
that read-out being checked by x4 against x8).

Saturated rungs. At 1x the internal-only +od_x / -od_x rungs are 80/80 and
0/80, so the probit slope is undefined; the module then reports a one-sided
95 % UPPER BOUND, sigma <= od_x / PhiInv(0.05**(1/N)) (a rung that is 80/80
has p >= 0.05**(1/80) with 95 % confidence), never a point value.

THIS MODULE GRADES NOTHING AGAINST THE SPEC. It reports the measured grid
mean next to the unchanged DR-0002 Target (1.0 mV) and Stretch (0.6 mV)
bounds, read from ``rows.json`` so they are never restated here.

Precision (delta method). With rung hit fractions p over N trials,
z = PhiInv(p) has variance p(1-p) / (N phi(z)^2); sigma = 2 od_x /
(z+ - z-) therefore has relative variance (var z+ + var z-) / (z+ - z-)^2.
Per-point only: the grid mean's standard error is the quadrature sum of the
per-point errors / 45 -- CONDITIONAL on the points being independent. The
grader's cross-point shared-draw note and per-point counts are carried into the
result, and the conservative fully-correlated bound (sum of the per-point
errors / included points; no correlation coefficient or effective sample size
is invented) is reported beside it. Failing to detect a repeated draw is not
evidence of independence.
"""

from __future__ import annotations

import gzip
import json
import math
from pathlib import Path
from statistics import NormalDist

from . import build as build_mod
from . import grade as grade_mod

CONFIGS = {
    "fe": "tn_full_fe",
    "int": "tn_full_int_probed",
    "both": "tn_full_both",
}
EXTRA = {"zero": "tn_full_zero", "int_x4": "tn_full_int_x4", "int_x8": "tn_full_int_x8"}
UNCERTAINTY_BASIS = (
    "grid_mean_se assumes independent grid points. Cross-point shared noise draws detected by "
    "the grader are reported per configuration (shared_draw_*, grader_notes); absence of a "
    "detected repeat does not establish independence. grid_mean_se_fully_correlated_bound is "
    "the conservative upper bound (sum of per-point SEs / included points). No correlation "
    "coefficient or effective sample size is estimated."
)
PROCESSES = ("mos_tt", "mos_ff", "mos_ss", "mos_fs", "mos_sf")


def sigma_upper_bound_95(n: int, od_x: float) -> float:
    """One-sided 95 % upper bound on sigma when a +od_x rung is n/n high and
    the -od_x rung 0/n high (both rungs saturated)."""
    p_lo = 0.05 ** (1.0 / n)
    return od_x / NormalDist().inv_cdf(p_lo)


def two_proportion_z(p1: float, p2: float, n: int) -> float:
    """z of the difference of two independent binomial fractions, both over
    n trials (pooled variance); 0 when both are saturated identically."""
    pooled = (p1 + p2) / 2
    var = pooled * (1 - pooled) * 2 / n
    return 0.0 if var == 0 else (p1 - p2) / math.sqrt(var)


def sigma_se(p_plus: float, p_minus: float, n: int, od_x: float) -> tuple[float, float]:
    """(sigma, standard error) of the two-rung probit-slope sigma."""
    nd = NormalDist()
    zp, zm = nd.inv_cdf(p_plus), nd.inv_cdf(p_minus)
    dz = zp - zm
    if dz <= 0:
        raise ValueError("rungs not ordered")
    sigma = 2.0 * od_x / dz
    var = sum(p * (1 - p) / (n * nd.pdf(z) ** 2) for p, z in ((p_plus, zp), (p_minus, zm)))
    return sigma, sigma * math.sqrt(var) / dz


def quadrature_split(sig_fe: float, sig_int: float | None, sig_both: float) -> dict:
    """Quadrature bookkeeping for one point (all in the same unit).

    ``increment`` is the internal term's contribution to the total as seen on
    top of the front end: sqrt(both^2 - fe^2), 0 when both <= fe (then the
    difference is within sampling scatter). ``closure`` is
    sqrt(fe^2 + int^2) / both: 1 when independent noise sources add in power.
    """
    inc2 = sig_both**2 - sig_fe**2
    return {
        "front_end": sig_fe,
        "internal_alone": sig_int,
        "total": sig_both,
        "internal_increment": math.sqrt(inc2) if inc2 > 0 else 0.0,
        "internal_increment_negative": inc2 <= 0,
        "closure": None if sig_int is None else math.sqrt(sig_fe**2 + sig_int**2) / sig_both,
    }


def read_envelope_bytes(path: Path) -> bytes | None:
    """The envelope exactly as klt printed it. The issue #81 campaign commits
    its envelopes gzip-compressed (``<tag>.envelope.json.gz``, deterministic,
    4 MB -> ~0.4 MB each); the decompressed bytes are the original, so the
    ``envelope_sha256`` in each ``.invocation.json`` still matches them."""
    if path.is_file():
        return path.read_bytes()
    gz = path.with_name(path.name + ".gz")
    if gz.is_file():
        return gzip.decompress(gz.read_bytes())
    return None


def _details(campaign_dir: Path, bench_name: str, ev: dict, grid: dict
             ) -> tuple[list[dict], list[str]]:
    envelopes = []
    shas = {}
    for section in PROCESSES:
        tag = f"{bench_name}.{section}"
        raw = read_envelope_bytes(campaign_dir / f"{tag}.envelope.json")
        if raw is not None:
            envelopes.append((tag, json.loads(raw)))
            shas[tag] = build_mod.sha256_bytes(raw)
    # Reuse the Row 2 rules verbatim: they key their per-sample gates and
    # independence probes by the bench name `transient_noise`, whose
    # measurement names these circuits share.
    evidence = grade_mod.BenchEvidence("transient_noise", envelopes, None, shas)
    details, notes = grade_mod.mc_probit_noise(evidence, ev, grid)
    for d in details:
        if d["sigma"] is not None:
            _, d["sigma_se"] = sigma_se(d["p_plus"], d["p_minus"], d["n"], float(ev["od_x_mv"]))
    return details, notes


def _present(campaign_dir: Path, bench_name: str) -> bool:
    return any(read_envelope_bytes(campaign_dir / f"{bench_name}.{sec}.envelope.json") is not None
               for sec in PROCESSES)


def grid_mean_se_bounds(ses: list[float]) -> tuple[float, float]:
    """(independent-points SE, fully-correlated upper bound) of the mean of
    len(ses) per-point estimates with standard errors ``ses``: quadrature sum
    / n, and plain sum / n (the maximum possible for any correlation)."""
    n = len(ses)
    return math.sqrt(sum(e * e for e in ses)) / n, sum(ses) / n


def _summarise(details: list[dict], notes: list[str] | None = None) -> dict:
    valid = [d for d in details if d["sigma"] is not None]
    item: dict = {"points_valid": len(valid), "points_expected": len(details)}
    shared = [d.get("samples_sharing_a_draw_with_another_point") or 0 for d in details]
    item["shared_draw_samples"] = sum(shared)
    item["shared_draw_points"] = sum(1 for c in shared if c)
    item["grader_notes"] = list(notes or [])
    if valid:
        mean = sum(d["sigma"] for d in valid) / len(valid)
        se_ind, se_corr = grid_mean_se_bounds([d["sigma_se"] for d in valid])
        item.update({
            "grid_mean": mean,
            "grid_mean_se": se_ind,
            "grid_mean_se_assumption": "independent points (conditional)",
            "grid_mean_se_fully_correlated_bound": se_corr,
            "grid_mean_se_fully_correlated_bound_definition":
                "sum of per-point delta-method SEs / included points; upper bound for any "
                "inter-point correlation, not an estimate",
            "min": min(d["sigma"] for d in valid), "max": max(d["sigma"] for d in valid),
            "complete": len(valid) == len(details),
        })
        if not item["complete"]:
            item["partial"] = True
            item["partial_label"] = (f"PARTIAL: mean and both SEs cover {len(valid)} of "
                                     f"{len(details)} points only; ungraded")
    bounded = [d["sigma_ub95"] for d in details if d.get("sigma_ub95") is not None]
    if bounded:
        item["saturated_points"] = len(bounded)
        item["sigma_ub95_mv"] = max(bounded)
    return item


def analyse(campaign_dir: Path) -> dict:
    rows = json.loads((build_mod.EXPERIMENT_DIR / "rows.json").read_text(encoding="utf-8"))
    grid = rows["grid"]
    row2 = next(r for r in rows["rows"] if r["id"] == "2")
    ev = row2["evidence"]
    od_x = float(ev["od_x_mv"])
    names = {**CONFIGS, **{c: b for c, b in EXTRA.items() if _present(campaign_dir, b)}}
    got = {cfg: _details(campaign_dir, bench, ev, grid) for cfg, bench in names.items()}
    per_cfg = {cfg: g[0] for cfg, g in got.items()}
    for details in per_cfg.values():
        for d in details:
            if (d["sigma"] is None and (d.get("problem") or "").startswith("probit needs")
                    and d.get("p_plus") == 1.0 and d.get("p_minus") == 0.0):
                d["sigma_ub95"] = sigma_upper_bound_95(d["n"], od_x)
    keys = ("sigma", "sigma_se", "sigma_ub95", "p_plus", "p_minus", "p_zero", "n", "problem",
            "samples_sharing_a_draw_with_another_point")
    points = []
    for i, d_fe in enumerate(per_cfg["fe"]):
        entry: dict = {"point": d_fe["point"],
                       **{cfg: {k: per_cfg[cfg][i].get(k) for k in keys} for cfg in names}}
        # 1x internal term: measured only through the scaled run (sigma(8x)/8).
        sig_int = None
        if "int_x8" in per_cfg and per_cfg["int_x8"][i]["sigma"] is not None:
            sig_int = per_cfg["int_x8"][i]["sigma"] / 8.0
            entry["internal_1x_from_x8"] = sig_int
            if "int_x4" in per_cfg and per_cfg["int_x4"][i]["sigma"] is not None:
                entry["linearity_x8_over_2x4"] = per_cfg["int_x8"][i]["sigma"] / (
                    2.0 * per_cfg["int_x4"][i]["sigma"])
        if per_cfg["fe"][i]["sigma"] is not None and per_cfg["both"][i]["sigma"] is not None:
            entry["split"] = quadrature_split(d_fe["sigma"], sig_int, per_cfg["both"][i]["sigma"])
        if "zero" in per_cfg:
            z = {}
            for rung in ("p_plus", "p_minus", "p_zero"):
                a, b = per_cfg["fe"][i].get(rung), per_cfg["zero"][i].get(rung)
                if a is not None and b is not None:
                    z[rung] = two_proportion_z(a, b, per_cfg["fe"][i]["n"])
            entry["negative_control_z"] = z
        points.append(entry)
    out: dict = {
        "od_x_mv": ev["od_x_mv"], "expected_n": ev["expected_n"],
        "target_max_mv": row2["target"]["max"], "stretch_max_mv": row2["stretch"]["max"],
        "unit": "mV rms", "points": points,
        "configs": {cfg: _summarise(d, got[cfg][1]) for cfg, d in per_cfg.items()},
        "uncertainty_basis": UNCERTAINTY_BASIS,
    }
    splits = [p["split"] for p in points if "split" in p]
    if splits:
        out["split_grid"] = {
            "points": len(splits),
            "mean_front_end": sum(s["front_end"] for s in splits) / len(splits),
            "mean_total": sum(s["total"] for s in splits) / len(splits),
            "mean_internal_increment": sum(s["internal_increment"] for s in splits) / len(splits),
            "points_internal_increment_within_scatter": sum(
                1 for s in splits if s["internal_increment_negative"]),
        }
        withint = [s for s in splits if s["internal_alone"] is not None]
        if withint:
            out["split_grid"]["internal_points"] = len(withint)
            out["split_grid"]["mean_internal_1x_from_x8"] = (
                sum(s["internal_alone"] for s in withint) / len(withint))
            out["split_grid"]["mean_closure"] = sum(s["closure"] for s in withint) / len(withint)
            # Prediction of the complete-injection result from the two separately
            # measured terms, vs the directly measured `both`: independent noise
            # sources add in power, so these should agree within the SE.
            pred = [math.sqrt(s["front_end"] ** 2 + s["internal_alone"] ** 2) for s in withint]
            out["split_grid"]["mean_predicted_total"] = sum(pred) / len(pred)
    lin = [p["linearity_x8_over_2x4"] for p in points if "linearity_x8_over_2x4" in p]
    if lin:
        out["linearity"] = {"points": len(lin), "mean_ratio": sum(lin) / len(lin),
                            "min": min(lin), "max": max(lin)}
    if "zero" in per_cfg:
        zs = [abs(v) for p in points for v in p["negative_control_z"].values()]
        out["negative_control"] = {
            "comparisons": len(zs), "abs_z_gt_2": sum(1 for z in zs if z > 2.0),
            "abs_z_gt_3": sum(1 for z in zs if z > 3.0),
            "expected_abs_z_gt_2_if_identical": 0.0455 * len(zs),
        }
        both_ok = [(a["sigma"], b["sigma"]) for a, b in zip(per_cfg["fe"], per_cfg["zero"])
                   if a["sigma"] is not None and b["sigma"] is not None]
        out["negative_control"]["points_compared_sigma"] = len(both_ok)
    ts = timestep_convergence(campaign_dir / "smoke", od_x)
    if ts["steps"]:
        out["timestep"] = ts
    both = out["configs"]["both"]
    if both.get("complete"):
        m = both["grid_mean"]
        out["as_measured"] = {
            "statistic": "grid-wide mean of per-point two-rung probit-slope sigma, complete injection",
            "grid_mean_mv": m,
            "target": "MET" if m <= out["target_max_mv"] else "NOT MET",
            "stretch": "MET" if m <= out["stretch_max_mv"] else "NOT MET",
        }
    else:
        out["as_measured"] = {"incomplete": True,
                              "why": "not every grid point of the `both` configuration is valid"}
    return out


def render_markdown(result: dict) -> str:
    L = ["# Whole-latch transient noise with internal injection (issue #81)", ""]
    L += ["Per-point sigma = two-rung probit slope (od_x = "
          f"{result['od_x_mv']} mV, N = {result['expected_n']} per rung); +/- is one standard error "
          "(delta method). `fe` = front-end source only, `int` = regenerative-pair + reset-device "
          "sources only (1x), `both` = complete injection; `zero` = negative control (internal "
          "densities scaled to 0, front end on); `int_x4` / `int_x8` = internal only, every "
          "internal density scaled up (sensitivity runs, not spec configurations).", ""]
    L += ["**Uncertainty basis.** " + result.get("uncertainty_basis", UNCERTAINTY_BASIS), ""]
    L += ["| config | valid points | grid mean (mV) | +/- SE of mean (independent points assumed) | "
          "+/- SE bound (fully correlated) | min | max | samples sharing a draw across points | "
          "saturated points | 95 % upper bound (mV) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for cfg, c in result["configs"].items():
        part = " (PARTIAL, ungraded)" if c.get("partial") else ""
        mean = (f"{c['grid_mean']:.3f}{part} | {c['grid_mean_se']:.3f} | "
                f"{c['grid_mean_se_fully_correlated_bound']:.3f} | {c['min']:.3f} | {c['max']:.3f}"
                if "grid_mean" in c else "- | - | - | - | -")
        mean += f" | {c.get('shared_draw_samples', 0)} ({c.get('shared_draw_points', 0)} points)"
        sat = (f"{c['saturated_points']} | <= {c['sigma_ub95_mv']:.2f}"
               if "saturated_points" in c else "- | -")
        L.append(f"| {cfg} | {c['points_valid']}/{c['points_expected']} | {mean} | {sat} |")
    for cfg, c in result["configs"].items():
        for note in c.get("grader_notes") or []:
            L.append(f"\n- `{cfg}` grader note: {note}")
    L += ["", "Significance calculations below (`zero` vs `fe` z-scores, timestep moves in SE units, "
          "linearity and closure ratios) treat their inputs as independent; none certifies "
          "independence of the underlying noise draws."]
    sg = result.get("split_grid")
    if sg:
        L += ["", f"Quadrature split over {sg['points']} points with `fe` and `both` valid "
              "(grid means of the per-point values, mV):", "",
              f"- front end alone: {sg['mean_front_end']:.3f}",
              f"- total (both): {sg['mean_total']:.3f}",
              f"- internal increment sqrt(both^2 - fe^2): {sg['mean_internal_increment']:.3f} "
              f"({sg['points_internal_increment_within_scatter']} points had both <= fe, counted as 0)"]
        if "mean_internal_1x_from_x8" in sg:
            L += [f"- internal alone at 1x, read as sigma(8x)/8 over {sg['internal_points']} points: "
                  f"{sg['mean_internal_1x_from_x8']:.3f}",
                  f"- predicted total sqrt(fe^2 + int^2), grid mean: {sg['mean_predicted_total']:.3f} "
                  f"(measured `both` grid mean {sg['mean_total']:.3f}; the per-point increment above is "
                  "dominated by sampling scatter, +/- 0.2 mV per point, and is NOT a measurement of the "
                  "internal term)",
                  f"- mean per-point closure sqrt(fe^2 + int^2)/both: {sg['mean_closure']:.3f}"]
    lin = result.get("linearity")
    if lin:
        L += ["", f"Linearity of the x8 read-out, sigma(8x)/(2 sigma(4x)), {lin['points']} points: "
              f"mean {lin['mean_ratio']:.3f} (min {lin['min']:.3f}, max {lin['max']:.3f}); 1.000 is exactly linear."]
    nc = result.get("negative_control")
    if nc:
        L += ["", f"Negative control (`zero` vs `fe`, same N, two-proportion z on every rung of every point): "
              f"{nc['comparisons']} comparisons, |z| > 2 in {nc['abs_z_gt_2']} "
              f"(identical populations would give about {nc['expected_abs_z_gt_2_if_identical']:.1f}), "
              f"|z| > 3 in {nc['abs_z_gt_3']}."]
    ts = result.get("timestep")
    if ts:
        L += ["", "## Timestep convergence (tt / 1.20 V / 27 C, `both`, front end + internal)", "",
              "| tran args | N | p(+od_x) | p(-od_x) | p(0) | sigma (mV) | +/- SE | move vs 20p (in SE) |",
              "|---|---|---|---|---|---|---|---|"]
        for step, t in ts["steps"].items():
            sg = f"{t['sigma']:.3f} | {t['sigma_se']:.3f}" if "sigma" in t else "- | -"
            z = f"{t['z_vs_20p']:+.2f}" if "z_vs_20p" in t else "-"
            L.append(f"| {t['tran_args']} | {t['n']} | {t['p_plus']:.3f} | {t['p_minus']:.3f} | "
                     f"{t['p_zero']:.3f} | {sg} | {z} |")
    am = result["as_measured"]
    L += ["", "## As measured against the unchanged DR-0002 Row 2 bounds", ""]
    if am.get("incomplete"):
        L.append(f"INCOMPLETE: {am['why']}.")
    else:
        L.append(f"Grid-wide mean, complete injection: **{am['grid_mean_mv']:.3f} mV rms**; "
                 f"Target <= {result['target_max_mv']} mV: **{am['target']}**; "
                 f"Stretch <= {result['stretch_max_mv']} mV: **{am['stretch']}**.")
    cfgs = list(result["configs"])
    L += ["", "## Per point (sigma, mV)", "", "| point | " + " | ".join(cfgs) + " | internal increment |",
          "|---|" + "---|" * (len(cfgs) + 1)]
    for p in result["points"]:
        def cell(cfg):
            c = p[cfg]
            if c["sigma"] is not None:
                return f"{c['sigma']:.3f} +/- {c['sigma_se']:.3f}"
            if c.get("sigma_ub95") is not None:
                return f"<= {c['sigma_ub95']:.2f} (sat.)"
            return "invalid: " + (c["problem"] or "?")[:40]
        sp = p.get("split")
        inc = f"{sp['internal_increment']:.3f}" if sp else "-"
        L.append(f"| {p['point']} | " + " | ".join(cell(c) for c in cfgs) + f" | {inc} |")
    return "\n".join(L) + "\n"


def _request_tran_args(path: Path) -> str | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("analysis", {}).get("args")


def timestep_convergence(smoke_dir: Path, od_x_mv: float,
                         steps: tuple[str, ...] = ("20p", "10p", "5p")) -> dict:
    """Max-timestep convergence at ONE corner from ``smoke/timestep-<step>``
    envelopes (identical request, ``tran`` step and max step the only change,
    N samples per rung). sigma is the two-rung probit slope with its delta-
    method standard error; ``z_vs_20p`` is (sigma - sigma_20p)/sqrt(se^2 +
    se_20p^2): the move expressed in units of its own statistical precision."""
    out: dict = {"steps": {}}
    for step in steps:
        path = smoke_dir / f"timestep-{step}.envelope.json"
        if not path.is_file():
            continue
        env = json.loads(path.read_text(encoding="utf-8"))
        corners = [c for c in env.get("corners") or [] if c.get("monte_carlo") is not None]
        vals = [{m["name"]: m.get("value") for m in c.get("measurements") or []} for c in corners]
        n = len(vals)
        p = {k: sum(v[f"hit_{k}"] for v in vals) / n for k in ("plus", "minus", "zero")}
        item = {"n": n, "statuses": dict.fromkeys({c["status"] for c in corners}, 0),
                "p_plus": p["plus"], "p_minus": p["minus"], "p_zero": p["zero"],
                "tran_args": _request_tran_args(smoke_dir / f"timestep-{step}.request.json")}
        for c in corners:
            item["statuses"][c["status"]] += 1
        if 0 < p["plus"] < 1 and 0 < p["minus"] < 1:
            item["sigma"], item["sigma_se"] = sigma_se(p["plus"], p["minus"], n, od_x_mv)
        out["steps"][step] = item
    base = out["steps"].get("20p", {})
    for step, item in out["steps"].items():
        if "sigma" in item and "sigma" in base and step != "20p":
            item["z_vs_20p"] = (item["sigma"] - base["sigma"]) / math.hypot(
                item["sigma_se"], base["sigma_se"])
    return out
