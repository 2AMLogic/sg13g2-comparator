#!/usr/bin/env python3
"""Probit inversion of a comparator-transient-noise record.

    python3 sim/comparator-transient-noise/probit.py records/<id>.json

The bench's deck deliberately emits NO sigma measurement: the probit
inversion is singular at a saturated hit rate of exactly 1.0, and ngspice's
`let` has no clamp with which the deck could guard it (see this experiment's
README.md, "Why no sigma_uv measure in this deck"). The committed record
therefore carries the RAW, directly-observed quantities -- frac_high_zero /
frac_high_plus / frac_high_minus -- and the conversion to an implied 1-sigma
input-referred decision noise is this post-hoc step.

It is a script, not a paragraph, on purpose: this repo's CLAUDE.md makes
verification the product, and a number quoted in README.md that can only be
reproduced by re-deriving someone's arithmetic by hand is not evidence. Every
sigma this experiment's README.md and the repo-root README.md quote is an
output of this file, run against a committed record.

METHOD (README.md "Probit inversion" carries the full derivation):

    p(od) = Phi((od - theta)/sigma)         od = +/- od_x, theta = effective
                                            threshold offset

    PRIMARY   sigma = 2*od_x / (Phi^-1(p_plus) - Phi^-1(p_minus))
              -- the DIFFERENCE of the two probits cancels theta exactly.

    DIAGNOSTIC (per-rung; assumes theta == 0, so it converts each corner's
    own sampling fluctuation straight into apparent noise -- reported only
    so its SPREAD reads out how much of a corner's number is scatter):
              sigma_plus  = od_x / Phi^-1(p_plus)
              sigma_minus = od_x / Phi^-1(1 - p_minus)

    DIAGNOSTIC theta = -(sigma/2) * (Phi^-1(p_plus) + Phi^-1(p_minus))

    IMPLIED APERTURE  enbw = (sigma / S_injected)^2, with S_injected the
    injected one-sided density NA*sqrt(2*TS).

od_x / vn_na / vn_ts are read from testbench/tb.json, NOT hardcoded here, so
a re-calibrated bench cannot silently keep quoting the old aperture. The
harness's record provenance does not carry the manifest's `params` map, only
its sha256 -- so this script CHECKS that sha256 against the tb.json on disk
and REFUSES to analyze a record whose manifest has since changed (pass
--allow-manifest-drift to override, e.g. when deliberately re-reading an
older record after a recalibration; the params then used are stamped in the
output so the mismatch cannot pass unnoticed).

`--selftest` runs the estimator's own closed-loop check (hit rates
synthesized forward from a known sigma/theta, inverted back) and needs no
record; see README.md "Probit inversion".

Stdlib only (math.erf / a bisection inverse), matching the harness's
no-dependency rule.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


def phi(x: float) -> float:
    """Standard-normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def probit(p: float) -> float:
    """Standard-normal inverse CDF, by bisection on phi().

    Bisection rather than a rational approximation: it is exact to machine
    precision in ~60 iterations, has no coefficient table to typo, and this
    runs 45 times, not 45 million.
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"probit() needs 0 < p < 1, got {p!r} (saturated rung)")
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def load_params(record: dict, manifest_path: Path, allow_drift: bool) -> tuple[dict, bool]:
    """Read the injection params from tb.json, gated on the record's own sha256."""
    raw = manifest_path.read_bytes()
    on_disk = hashlib.sha256(raw).hexdigest()
    recorded = record["testbench"].get("manifest_sha256")
    drifted = recorded is not None and on_disk != recorded
    if drifted and not allow_drift:
        raise SystemExit(
            f"{manifest_path} has changed since record {record['record_id']} was minted\n"
            f"  record : {recorded}\n"
            f"  on disk: {on_disk}\n"
            "The params this inversion needs (od_x, vn_na, vn_ts) are not carried in the\n"
            "record itself, so analyzing it with a drifted manifest would silently quote\n"
            "the wrong injected density. Re-run --allow-manifest-drift only deliberately."
        )
    return json.loads(raw).get("params", {}), drifted


def analyze(record: dict, params: dict) -> dict:
    od_x = float(params["od_x"])
    na = float(params["vn_na"])
    ts = float(params["vn_ts"])
    # One-sided density of ngspice TRNOISE(NA TS 0 0)'s linearly-interpolated
    # white component: S = NA*sqrt(2*TS)  (README.md "NA/TS calibration").
    s_inj = na * math.sqrt(2.0 * ts)

    rows = []
    for point in record["points"]:
        if point.get("status") != "ok":
            rows.append({"corner_id": point["corner_id"], "status": point.get("status")})
            continue
        m = point["measurements"]
        p_plus = m["frac_high_plus"]
        p_minus = m["frac_high_minus"]
        z_plus = probit(p_plus)
        z_minus = probit(p_minus)
        sigma = 2.0 * od_x / (z_plus - z_minus)
        rows.append(
            {
                "corner_id": point["corner_id"],
                "status": "ok",
                "frac_high_zero": m["frac_high_zero"],
                "frac_high_plus": p_plus,
                "frac_high_minus": p_minus,
                "sigma_mv": sigma * 1e3,
                "sigma_plus_mv": (od_x / z_plus) * 1e3,
                "sigma_minus_mv": (od_x / probit(1.0 - p_minus)) * 1e3,
                "theta_uv": -0.5 * sigma * (z_plus + z_minus) * 1e6,
                "enbw_ghz": (sigma / s_inj) ** 2 / 1e9,
            }
        )

    ok = [r for r in rows if r.get("status") == "ok"]
    sigmas = [r["sigma_mv"] for r in ok]
    zeros = [r["frac_high_zero"] for r in ok]
    mean = sum(sigmas) / len(sigmas) if sigmas else float("nan")
    return {
        "record_id": record["record_id"],
        "params": {"od_x": od_x, "vn_na": na, "vn_ts": ts},
        "od_x_mv": od_x * 1e3,
        "s_injected_nv_rthz": s_inj * 1e9,
        "n_points": len(rows),
        "n_ok": len(ok),
        "rows": rows,
        "sigma_min_mv": min(sigmas) if sigmas else None,
        "sigma_max_mv": max(sigmas) if sigmas else None,
        "sigma_mean_mv": mean,
        "at_min": min(ok, key=lambda r: r["sigma_mv"])["corner_id"] if ok else None,
        "at_max": max(ok, key=lambda r: r["sigma_mv"])["corner_id"] if ok else None,
        "enbw_mean_ghz": sum(r["enbw_ghz"] for r in ok) / len(ok) if ok else None,
        "frac_high_zero_min": min(zeros) if zeros else None,
        "frac_high_zero_max": max(zeros) if zeros else None,
        "frac_high_zero_mean": sum(zeros) / len(zeros) if zeros else None,
    }


def selftest() -> int:
    """Closed-loop check: synthesize hit rates from a KNOWN sigma, recover it.

    The estimator is what turns this bench's raw evidence into the number
    README.md quotes, so it gets its own falsification test rather than
    being trusted by inspection. Hit rates are generated forward from a
    chosen (sigma, theta) via p = Phi((od - theta)/sigma) -- no sampling, so
    the inversion must return the inputs to machine precision.

    The load-bearing case is a NON-ZERO theta: that is precisely where the
    per-rung diagnostic is wrong and the slope estimator is not, and the
    whole argument for making the slope form primary (README.md "Probit
    inversion") rests on that difference being real.
    """
    failures: list[str] = []

    def check(label: str, got: float, want: float, tol: float) -> None:
        if not math.isclose(got, want, rel_tol=tol, abs_tol=tol * abs(want)):
            failures.append(f"{label}: got {got!r}, want {want!r} (rel_tol {tol})")

    od_x, na, ts = 1.0e-3, 5.735e-3, 20e-12
    params = {"od_x": od_x, "vn_na": na, "vn_ts": ts}
    s_inj = na * math.sqrt(2.0 * ts)

    for sigma_true, theta_true in ((1.0e-3, 0.0), (1.142e-3, 150e-6), (0.6e-3, -300e-6)):
        record = {
            "record_id": f"selftest-sigma{sigma_true}-theta{theta_true}",
            "testbench": {},
            "points": [
                {
                    "corner_id": "selftest",
                    "status": "ok",
                    "measurements": {
                        "frac_high_zero": phi((0.0 - theta_true) / sigma_true),
                        "frac_high_plus": phi((od_x - theta_true) / sigma_true),
                        "frac_high_minus": phi((-od_x - theta_true) / sigma_true),
                    },
                }
            ],
        }
        out = analyze(record, params)
        row = out["rows"][0]
        tag = f"sigma={sigma_true * 1e3:.3f}mV theta={theta_true * 1e6:.0f}uV"
        check(f"{tag} slope sigma", row["sigma_mv"], sigma_true * 1e3, 1e-9)
        check(f"{tag} theta", row["theta_uv"], theta_true * 1e6, 1e-6)
        check(f"{tag} implied ENBW", row["enbw_ghz"], (sigma_true / s_inj) ** 2 / 1e9, 1e-9)
        if theta_true == 0.0:
            # With theta == 0 the per-rung diagnostic is EXACT too ...
            check(f"{tag} sigma_plus", row["sigma_plus_mv"], sigma_true * 1e3, 1e-9)
            check(f"{tag} sigma_minus", row["sigma_minus_mv"], sigma_true * 1e3, 1e-9)
        else:
            # ... and with theta != 0 it is NOT: a positive theta inflates the
            # +rung's apparent sigma and deflates the -rung's, and vice versa.
            # If the two ever agreed here, the slope form would be pointless
            # and README.md's argument for making it primary would be wrong.
            straddles = (
                row["sigma_plus_mv"] > row["sigma_minus_mv"]
                if theta_true > 0
                else row["sigma_plus_mv"] < row["sigma_minus_mv"]
            )
            if not straddles:
                failures.append(
                    f"{tag}: per-rung diagnostics did not straddle as expected "
                    f"(sigma_plus {row['sigma_plus_mv']:.4f}, "
                    f"sigma_minus {row['sigma_minus_mv']:.4f})"
                )
            # Both per-rung numbers are biased, but the slope form recovered
            # sigma exactly above -- that is the claim, stated as a check.
            if math.isclose(row["sigma_plus_mv"], sigma_true * 1e3, rel_tol=1e-6):
                failures.append(
                    f"{tag}: sigma_plus matched the true sigma at theta != 0, "
                    "which contradicts the estimator's stated failure mode"
                )

    # Saturation must RAISE, not silently return a flattering zero sigma.
    try:
        probit(1.0)
    except ValueError:
        pass
    else:
        failures.append("probit(1.0) did not raise -- a saturated rung would read sigma = 0")

    # Phi/probit round trip over the band od_x actually puts these rungs in.
    for p in (0.001, 0.05, 0.16, 0.5, 0.8, 0.95, 0.999):
        check(f"phi(probit({p}))", phi(probit(p)), p, 1e-12)

    for line in failures:
        print(f"FAIL {line}")
    print(f"probit.py selftest: {'FAIL' if failures else 'PASS'} "
          f"({len(failures)} failure(s))")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("record", type=Path, nargs="?", help="path to a records/<id>.json")
    ap.add_argument(
        "--selftest",
        action="store_true",
        help="run the estimator's own closed-loop check and exit (no record needed)",
    )
    ap.add_argument("--json", action="store_true", help="emit the full analysis as JSON")
    ap.add_argument(
        "--allow-manifest-drift",
        action="store_true",
        help="analyze even if testbench/tb.json has changed since the record was minted",
    )
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.record is None:
        ap.error("a records/<id>.json path is required (or pass --selftest)")

    record = json.loads(args.record.read_text())
    manifest = Path(__file__).resolve().parent / "testbench" / "tb.json"
    params, drifted = load_params(record, manifest, args.allow_manifest_drift)
    out = analyze(record, params)
    out["manifest_drift"] = drifted

    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    if drifted:
        print("WARNING: tb.json has drifted from this record's manifest_sha256; "
              "params below are the CURRENT ones, not the ones simulated.")
    print(f"record        : {out['record_id']}")
    print(f"od_x          : {out['od_x_mv']:.3f} mV")
    print(f"injected S    : {out['s_injected_nv_rthz']:.2f} nV/rtHz (NA*sqrt(2*TS))")
    print(f"points        : {out['n_ok']}/{out['n_points']} ok")
    print()
    print(
        f"{'corner':<22}{'p0':>8}{'p+':>8}{'p-':>8}"
        f"{'sigma_mV':>11}{'sig+_mV':>10}{'sig-_mV':>10}{'theta_uV':>10}{'ENBW_GHz':>10}"
    )
    for r in out["rows"]:
        if r.get("status") != "ok":
            print(f"{r['corner_id']:<22}{'-- ' + str(r.get('status')):>65}")
            continue
        print(
            f"{r['corner_id']:<22}"
            f"{r['frac_high_zero']:>8.3f}{r['frac_high_plus']:>8.3f}{r['frac_high_minus']:>8.3f}"
            f"{r['sigma_mv']:>11.4f}{r['sigma_plus_mv']:>10.4f}{r['sigma_minus_mv']:>10.4f}"
            f"{r['theta_uv']:>10.1f}{r['enbw_ghz']:>10.3f}"
        )
    print()
    print(
        f"GRID sigma    : min {out['sigma_min_mv']:.4f} mV ({out['at_min']})  "
        f"max {out['sigma_max_mv']:.4f} mV ({out['at_max']})  "
        f"mean {out['sigma_mean_mv']:.4f} mV"
    )
    print(f"GRID ENBW mean: {out['enbw_mean_ghz']:.3f} GHz")
    print(
        f"GRID p0       : min {out['frac_high_zero_min']:.4f}  "
        f"max {out['frac_high_zero_max']:.4f}  mean {out['frac_high_zero_mean']:.4f}  "
        "(noise-injection guard; must straddle 0.5)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
