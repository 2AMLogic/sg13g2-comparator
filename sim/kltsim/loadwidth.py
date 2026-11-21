"""Matched PMOS load-width study (issue #498).

The Phase 1 loop-broken model attributes 85.4-92.4 % of differential
output noise power to the diode-connected loads XM5A/XM6A across 12
measured cells (``sim/comparator-preamp-noise/reports/20261120-issue477/
pvt-batch.md``). This study tests whether resizing ONLY the matched PMOS
loads (XM5/XM6 in the whole-latch DUT, their counterparts XM5A/XM6A in
the reduced model) moves Row 2 and the input-referred density, with
XM3/XM4, the input pair, the switch and the bias held at the archived
``ib10_sw20lat6`` geometry.

Two evidence layers, both from ``klt sim`` batch requests:

``scr_<name>/``  SCREENING on the issue #92 reduced 18-point grid
                 (tt/ff/ss x 1.08/1.32 V x -40/27/125 C). The fast
                 benches (kickback, regeneration) use the standard
                 ``sizesweep`` screening requests. The Row 2 screen adds
                 transient-noise Monte Carlo (N = 80 per rung) as THREE
                 per-process requests (tt, ff, ss) derived from the
                 candidate's process-specific full requests -- the
                 builder's own ``--screen`` rewrite cannot be used there
                 because it replaces the process list AFTER the builder
                 has split requests, which would emit byte-identical
                 files covering all three processes three times over.
``full_<name>/``  FINALIST: the complete 45-point grid for every bench,
                 graded by the SAME ``kltsim.grade`` rules (issue #62).
                 Built with the standard ``build``/``run``/``grade``
                 commands once the screen advances a setting.

    python3 sim/run_klt_corner_verification.py loadwidth-build --campaign ID
    # submit each scr_<name> part (batch fleet), then:
    python3 sim/run_klt_corner_verification.py sizesweep --campaign ID
    python3 sim/run_klt_corner_verification.py loadwidth-report --campaign ID

Nothing here proposes a bound, edits the DUT, the spec or ``sim/dut.json``:
it is the evidence an operator decision (#479) would be founded on.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import artifacts as artifacts_mod
from . import build as build_mod
from . import grade as grade_mod
from . import sizesweep as sizesweep_mod
from .benches import TRANSIENT_NOISE

#: the archived control: full 45-point grid AND its 18-point screen subset
#: already exist in the issue #92 bias campaign, so the control is reused,
#: never re-run (issue #498: "Reuse the archived control wherever the
#: conditions match").
CONTROL_CAMPAIGN = "20261115-issue92-bias"
CONTROL_NAME = "ib10_sw20lat6"
CONTROL_WIDTH = "6u"

#: the declared candidate set (issue #498: "a small, declared set of
#: previously unmeasured widths"). 3 um and 6 um are already measured
#: (latch_w of the committed design / the #92 W-L campaign, and the bias
#: campaign's lat6 family); every width below is new as a PMOS load width.
#: 4 um probes just below the control, 8/10/12 um continue the measured
#: 3 -> 6 um direction (41.45 -> 36.78 nV/rtHz at TT) with the spacing
#: that resolved that step.
CANDIDATES: tuple[tuple[str, str], ...] = (
    ("w4", "4u"),
    ("w8", "8u"),
    ("w10", "10u"),
    ("w12", "12u"),
)

#: the fixed part of every candidate's geometry: the archived
#: ``ib10_sw20lat6`` DUT (8 um / 0.34 um pair, 6 um XM3/XM4, 20 um switch)
#: with ``dut_ib = 10 uA``. Only XM5/XM6 differ, set to the candidate width.
BASE_GEOMETRY = {"XM1.w": "8u", "XM2.w": "8u", "XM3.w": "6u", "XM4.w": "6u",
                 "XMSW.w": "20u"}
BASE_PARAM_OVERRIDES = {"dut_ib": 1e-05}

#: screening fast-bench metrics -> the DR-0002 row whose Target bound gates
#: advancement (bounds are read from ``rows.json`` at report time, so this
#: mapping cannot drift from the ratified spec).
GATE_METRICS = {
    "td50_worst": "3a",
    "tau_worst": "3b",
    "td01_worst": "3c",
    "qkick_worst": "4a",
    "qkick_binding": "4a",
    "sigdep_worst": "4b",
}

#: the Row 2 grid statistic on the 18-point screen grid (process names as
#: ``grid_keys`` wants them: no ``mos_`` prefix).
SCREEN_GRID = {"process": ["tt", "ff", "ss"],
               "supply_v": list(sizesweep_mod.SCREEN_SUPPLIES_V),
               "temperature_c": list(sizesweep_mod.SCREEN_TEMPERATURES_C)}


def candidate_geometry(width: str) -> dict:
    """The full geometry override of one candidate (XM5/XM6 at ``width``)."""
    return {**BASE_GEOMETRY, "XM5.w": width, "XM6.w": width}


def candidate_identity(width: str) -> dict:
    """Geometry + param overrides as one candidate-identity mapping (the
    ``sizesweep`` geometry report merges the two; so does this)."""
    return {**candidate_geometry(width), **{k: repr(v) for k, v in BASE_PARAM_OVERRIDES.items()}}


def tn_screen_corners(process_section: str) -> dict:
    """The expected corners of one derived transient-noise screen request:
    its ONE process (kept from the split), the two screen supplies and the
    three screen temperatures -- what :func:`grade_mod.check_chain` compares
    the saved request against."""
    return {"process": [process_section],
            "supply_v": {k: list(sizesweep_mod.SCREEN_SUPPLIES_V) for k in TRANSIENT_NOISE.supply_keys},
            "temperature_c": list(sizesweep_mod.SCREEN_TEMPERATURES_C)}


def tn_screen_request(full_request: dict, process_section: str) -> dict:
    """Derive one transient-noise screen request from the candidate's
    process-specific FULL request (issue #498 verified correction): keep the
    process, the Monte-Carlo settings, the measurements and the analysis;
    keep only the two screen supplies. Returns a request dict (not bytes)."""
    request = json.loads(json.dumps(full_request))  # deep copy, prose kept
    request["corners"] = tn_screen_corners(process_section)
    request.pop("remote", None)
    request.setdefault("_comment", []).append(
        "SCREENING GRID (issue #498 Row 2 screen): one process (from the split "
        "request), 1.08/1.32 V x -40/27/125 C = 6 points, Monte Carlo N = 80 per "
        "rung as in the full bench. Derived from the process-specific full "
        "request; the builder's own --screen rewrite cannot produce this "
        "(it replaces the process list after the split). Not a 45-point "
        "verdict; never graded as one.")
    return request


def plan_scr_inputs(campaign_dir: Path, name: str, width: str) -> list[tuple[Path, bytes]]:
    """Compose (without writing) every input of one candidate's ``scr_``
    directory: the two standard screening benches plus the three derived
    transient-noise screen requests, all sharing the candidate's geometry.

    Before returning, the union of the three transient-noise requests'
    grid points is verified to cover the 18 screening points exactly once
    (issue #498 verified correction), so a mis-derived request can never
    reach the fleet.
    """
    geometry = candidate_geometry(width)
    sub = campaign_dir / f"scr_{name}"
    planned: list[tuple[Path, bytes]] = []
    # fast benches: the standard screening path, exactly as `build --screen`
    for bench_name in sizesweep_mod.SCREEN_BENCHES:
        bench = grade_mod._bench_spec(bench_name)
        _body, _requests, files = build_mod.plan_bench_inputs(
            bench, sub, target="batch", param_overrides=BASE_PARAM_OVERRIDES,
            geometry_overrides=geometry)
        planned += [(path, sizesweep_mod.screen_request(data) if path.name.endswith(".request.json")
                     else data) for path, data in files]
    # transient noise: derive the three per-process screen requests
    bench = TRANSIENT_NOISE
    _body, _requests, files = build_mod.plan_bench_inputs(
        bench, sub, target="batch", param_overrides=BASE_PARAM_OVERRIDES,
        geometry_overrides=geometry)
    planned.append(files[0])  # the one shared body
    seen: dict[tuple, int] = {}
    for section in sizesweep_mod.SCREEN_PROCESSES:
        tag = f"{bench.name}.{section}"
        full = next((json.loads(data) for path, data in files[1:]
                     if path.name == f"{tag}.request.json"), None)
        if full is None:
            raise build_mod.BuildError(f"split builder produced no {tag} request")
        request = tn_screen_request(full, section)
        for process in request["corners"]["process"]:
            for supply in request["corners"]["supply_v"]["vsup"]:
                for temp in request["corners"]["temperature_c"]:
                    key = sizesweep_mod._pt(process, supply, temp)
                    seen[key] = seen.get(key, 0) + 1
        planned.append((sub / f"{tag}.request.json",
                        (json.dumps(request, indent=2) + "\n").encode("utf-8")))
    expected = {key: 1 for key in sizesweep_mod.EXPECTED_POINTS}
    if seen != expected:
        raise build_mod.BuildError(
            "derived transient-noise screen grid is not the 18 screening points "
            f"covered exactly once (offending keys: "
            f"{sorted(k for k in set(seen) | set(expected) if seen.get(k) != expected.get(k))})")
    return planned


def plan_all_scr_inputs(campaign_dir: Path,
                        candidates: tuple[tuple[str, str], ...] = CANDIDATES) -> list[tuple[Path, bytes]]:
    """Compose (without writing) EVERY candidate's ``scr_`` inputs; the CLI
    commits the whole set append-only in one preflighted step."""
    planned: list[tuple[Path, bytes]] = []
    for name, width in candidates:
        planned += plan_scr_inputs(campaign_dir, name, width)
    return planned


def _rows_spec() -> dict:
    return json.loads((build_mod.EXPERIMENT_DIR / "rows.json").read_text(encoding="utf-8"))


def _row_bound(row_id: str) -> float | None:
    spec = _rows_spec()
    row = next(r for r in spec["rows"] if r["id"] == row_id)
    bound = row.get("target") or {}
    return bound.get("max")


def _row2_evidence() -> dict:
    return next(r for r in _rows_spec()["rows"] if r["id"] == "2")["evidence"]


def tn_screen_evidence(sub: Path) -> grade_mod.BenchEvidence:
    """Load one candidate's transient-noise screen envelopes with the full
    request/invocation/envelope chain checked against the DERIVED screen
    corners (one process, two supplies, three temperatures per request)."""
    problems: list[str] = []
    envelopes: list[tuple[str, dict]] = []
    shas: dict[str, str] = {}
    checked: dict[str, dict] = {}
    for section in sizesweep_mod.SCREEN_PROCESSES:
        tag = f"{TRANSIENT_NOISE.name}.{section}"
        path = sub / f"{tag}.envelope.json"
        if not path.is_file():
            problems.append(f"{tag}: no envelope (submit the screen request first)")
            continue
        raw = path.read_bytes()
        shas[tag] = hashlib.sha256(raw).hexdigest()
        envelope = json.loads(raw)
        if not isinstance(envelope, dict):
            problems.append(f"{tag}: envelope is not a JSON object")
            continue
        envelopes.append((tag, envelope))
        checked[tag] = grade_mod.check_chain(TRANSIENT_NOISE, tag, sub, shas[tag],
                                             problems, corners=tn_screen_corners(section))
    body_path = sub / f"{TRANSIENT_NOISE.name}.body.spice"
    return grade_mod.BenchEvidence(
        name=TRANSIENT_NOISE.name, envelopes=envelopes,
        body_text=body_path.read_text(encoding="utf-8") if body_path.is_file() else None,
        envelope_files=shas, chain_problems=problems, chain_checked=checked)


def screen_row2(sub: Path) -> dict:
    """The Row 2 screen of one candidate: the DR-designated statistic
    (grid-wide mean of the per-point two-rung probit-slope sigma) computed
    by the SAME grader path as a full-grid verdict, on the 18 screening
    points, with the DUT and evidence-chain checks applied."""
    bench = tn_screen_evidence(sub)
    dut = grade_mod.load_dut_reference()
    result = {"dir": sub.name,
              "evidence_problems": list(bench.chain_problems),
              "dut_problems": grade_mod.check_dut(bench, dut) if bench.envelopes else
              ["no transient-noise screen envelope"]}
    if result["evidence_problems"] or result["dut_problems"]:
        result["statistic"] = None
        return result
    details, notes = grade_mod.mc_probit_noise(bench, _row2_evidence(), SCREEN_GRID)
    target = grade_mod.grade_grid_mean(details, {"max": _row_bound("2")})
    result["statistic"] = target
    result["monte_carlo_per_point"] = details
    if notes:
        result["notes"] = notes
    return result


def control_screen_row2(campaigns_dir: Path) -> dict:
    """Recompute the control's Row 2 screen numbers from the archived
    45-point grading (the 18 screening points are a subset of its grid;
    the bench is unchanged, so the archived values ARE the screen values).
    Issue #498's curated figure for this mean is 1.053 mV rms."""
    grading_path = campaigns_dir / CONTROL_CAMPAIGN / f"full_{CONTROL_NAME}" / "grading.json"
    grading = json.loads(grading_path.read_text(encoding="utf-8"))
    row2 = next(r for r in grading["rows"] if r["id"] == "2")
    points = row2["monte_carlo_per_point"]
    wanted = set(sizesweep_mod.EXPECTED_POINTS)
    selected = []
    for point in points:
        key = _parse_point_label(point["point"])
        if key is not None and key in wanted:
            selected.append(point)
    valid = [p["sigma"] for p in selected if p["sigma"] is not None]
    out = {"campaign": CONTROL_CAMPAIGN, "dir": f"full_{CONTROL_NAME}",
           "width": CONTROL_WIDTH, "identity": candidate_identity(CONTROL_WIDTH),
           "source": grading_path.relative_to(build_mod.REPO_ROOT).as_posix(),
           "points_selected": len(selected),
           "points_valid": len(valid), "grid45_mean": row2["target"]["grid_mean"]}
    out["screen_mean"] = sum(valid) / len(valid) if valid else None
    return out


def _parse_point_label(label: str) -> tuple[str, float, float] | None:
    """``tt_-40c_1.08v`` -> ``("tt", 1.08, -40.0)`` (the ``key_label`` form),
    or None when the label does not parse."""
    m = re.match(r"^([a-z]+)_(-?\d+(?:\.\d+)?)c_(\d+(?:\.\d+)?)v$", label)
    if m is None:
        return None
    return (m.group(1), round(float(m.group(3)), 6), float(m.group(2)))


def load_density(path: Path) -> dict:
    """The committed candidate-density table (Phase 1 method, issue #498
    reduced-model characterization). Validates the shape; returns
    ``{"widths": {...}}`` with per-width per-PVT density entries."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("widths"), dict) or not data["widths"]:
        raise ValueError(f"{path}: no widths table")
    for width, entry in data["widths"].items():
        if not isinstance(entry, dict) or not isinstance(entry.get("points"), dict) \
                or not entry["points"]:
            raise ValueError(f"{path}: width {width!r} has no points table")
        for pvt, cell in entry["points"].items():
            for field in ("white_out_v_rthz", "gain_dc_v_per_v", "density_nv_rthz"):
                if not isinstance(cell.get(field), (int, float)):
                    raise ValueError(f"{path}: {width}/{pvt}.{field} is missing or not a number")
    return data


def _fast_gates(screen_row: dict) -> tuple[list[str], list[str]]:
    """(breaches, unavailable) for one candidate's fast-bench screen row,
    against the Target bounds of the gated DR-0002 rows. A MEASURED breach
    eliminates; an unavailable metric (fewer than 18 valid points) is a
    carried caveat, not an elimination -- the archived control itself had a
    17/18 sigdep screen and a clean full grid."""
    breaches: list[str] = []
    unavailable: list[str] = []
    for metric, row_id in GATE_METRICS.items():
        cell = screen_row["metrics"].get(metric)
        if cell is None:
            unavailable.append(f"{metric}: not tabulated")
            continue
        bound = _row_bound(row_id)
        if bound is None:
            continue
        if cell["available"]:
            if cell["value"] > bound:
                breaches.append(f"Row {row_id} gate {metric} = {cell['value']:.4g} "
                                f"> Target {bound:g} ({cell['point']})")
        else:
            unavailable.append(f"{metric}: unavailable ({cell['valid']}/{cell['expected']} valid)")
    return breaches, unavailable


def _verdicts(campaign_dir: Path, screen_rows: list[dict], densities: dict | None,
              control: dict) -> list[dict]:
    """Apply the declared advance/eliminate rule to every candidate.

    A width is ELIMINATED when its Row 2 screen evidence is invalid, when a
    gated fast-bench Target bound is breached at a screened point (that
    point is in the 45-point grid, so the full verdict would fail), or when
    its 18-point Row 2 screen mean does not improve on the control's (the
    unchanged bench is the Target statistic; no improvement there means no
    lever on Row 2). At most ONE width advances: the lowest screen mean
    among the survivors (tie: lowest own TT density; then the narrower
    width). A negative result -- every width eliminated -- completes the
    study."""
    by_mean = {}
    out = []
    for row in screen_rows:
        sub = campaign_dir / row["dir"]
        entry = {"name": row["name"], "geometry": row["geometry"],
                 "geometry_problems": row["geometry_problems"]}
        reasons: list[str] = []
        if row["geometry_problems"]:
            reasons.append("candidate geometry unreadable/inconsistent: "
                           + "; ".join(row["geometry_problems"]))
        row2 = screen_row2(sub)
        entry["row2"] = {k: row2[k] for k in ("evidence_problems", "dut_problems")}
        entry["row2"]["statistic"] = row2.get("statistic")
        breaches, unavailable = _fast_gates(row)
        if breaches:
            reasons.extend(breaches)
        if unavailable:
            entry["gates_unavailable"] = unavailable
        stat = row2.get("statistic")
        if row2["evidence_problems"] or row2["dut_problems"]:
            reasons.append("Row 2 screen evidence rejected: "
                           + (row2["evidence_problems"] + row2["dut_problems"])[0])
        elif stat is None or stat["points_valid"] != stat["points_expected"]:
            first = (stat or {}).get("points_missing_or_invalid") or [{"why": "no statistic"}]
            reasons.append(f"Row 2 screen incomplete ({(stat or {}).get('points_valid', 0)}/"
                           f"{(stat or {}).get('points_expected', 18)} valid; first: "
                           f"{first[0].get('why')})")
        elif control["screen_mean"] is not None and stat["grid_mean"] >= control["screen_mean"]:
            reasons.append(f"Row 2 screen mean {stat['grid_mean']:.4g} mV does not improve on "
                           f"the control's {control['screen_mean']:.4g} mV at the same "
                           "injection (36.27 nV/rtHz)")
        entry["elimination_reasons"] = reasons
        if not reasons and stat is not None:
            density = (densities or {}).get("widths", {}).get(row["name"], {})
            # ascending: screen mean, then own TT density, then width
            by_mean[row["name"]] = (stat["grid_mean"],
                                    _tt_density(density),
                                    _width_um(row))
        out.append(entry)
    if by_mean:
        best = min(by_mean, key=lambda n: by_mean[n])
        for entry in out:
            if entry["name"] == best:
                entry["advanced"] = True
    return out


def _tt_density(density_entry: dict) -> float:
    points = density_entry.get("points") or {}
    tt = points.get("tt") or {}
    value = tt.get("density_nv_rthz")
    return float(value) if isinstance(value, (int, float)) else float("inf")


def _width_um(row: dict) -> float:
    for key, value in sorted((row.get("geometry") or {}).items()):
        if key in ("XM5.w", "XM6.w"):
            return float(value.rstrip("u"))
    return 0.0


def _projection(control: dict, density_nv_rthz: float) -> float | None:
    """The Phase 1 nominal recalibration applied to a candidate: the
    control's 45-point bench mean rescaled by the candidate's own TT
    density ratio (PROJECTION, never a verdict)."""
    if control.get("grid45_mean") is None:
        return None
    s0 = 36.27
    return control["grid45_mean"] * density_nv_rthz / s0


def run(campaign: str, campaigns_dir: Path, report_name: str = "loadwidth",
        density_path: Path | None = None) -> dict:
    cdir = campaigns_dir / campaign
    densities = None
    if density_path is not None and Path(density_path).is_file():
        densities = load_density(Path(density_path))
    control = control_screen_row2(campaigns_dir)
    screen_rows = sizesweep_mod.screen(cdir)
    candidates = _verdicts(cdir, screen_rows, densities, control)
    advanced = [c["name"] for c in candidates if c.get("advanced")]
    result = {"campaign": campaign, "control": control,
              "density_source": str(density_path) if densities else None,
              "candidates": candidates, "advanced": advanced[:1]}
    js = json.dumps(grade_mod.json_safe(result), indent=2, allow_nan=False) + "\n"
    md = render_markdown(result, densities)
    jpath, mpath = cdir / f"{report_name}.json", cdir / f"{report_name}.md"
    try:
        artifacts_mod.commit([(jpath, js.encode("utf-8")), (mpath, md.encode("utf-8"))],
                             differs="already exists with different content")
    except artifacts_mod.ArtifactConflict as exc:
        raise FileExistsError(
            "; ".join(exc.conflicts) + "; evidence is append-only. "
            "Write the revised report under a fresh name (--report-name).") from exc
    return result


def _fmt(x, d=4):
    return "-" if x is None else f"{x:.{d}g}"


def render_markdown(result: dict, densities: dict | None) -> str:
    control = result["control"]
    L = [f"# Matched PMOS load-width screen -- campaign `{result['campaign']}` (issue #498)", "",
         "GENERATED by `python3 sim/run_klt_corner_verification.py loadwidth-report`. "
         "Proposes no bound, changes no spec row, no DUT and not `sim/dut.json`. The study "
         "varies only XM5/XM6 (and their reduced-model counterparts XM5A/XM6A); XM3/XM4, "
         "the input pair, the switch and the 10 uA bias stay at the archived "
         f"`{CONTROL_NAME}` geometry. Adopting any candidate is a #479 decision, not made "
         "here.", "",
         f"Control: archived `{CONTROL_CAMPAIGN}/full_{CONTROL_NAME}` "
         f"({CONTROL_WIDTH} loads), reused, never re-run. Its Row 2 screen mean over the 18 "
         f"screening points is {_fmt(control['screen_mean'])} mV rms at the unchanged "
         "36.27 nV/rtHz injection (recomputed here from the committed per-point grades: "
         f"{control['points_valid']}/{control['points_selected']} selected points valid); "
         f"its 45-point bench mean is {_fmt(control['grid45_mean'])} mV.", "",
         "## Row 2 screen (transient noise, 18 points, N = 80 per rung, unchanged bench)", "",
         "The DR-designated statistic computed by the full-grid grader path on the screening "
         "grid. The unchanged bench injects 36.27 nV/rtHz, so these numbers measure the "
         "decision-response (bandwidth) factor at fixed density; they are NOT a 45-point "
         "verdict. Screen requests: three per-process derived requests per candidate "
         "(tt, ff, ss), whose union covers the 18 points exactly once.", "",
         "| candidate | loads | valid pts | 18-pt mean [mV rms] | vs control | own S(TT) [nV/rtHz] | projected 45-pt mean [mV] |",
         "|---|---|---|---|---|---|---|"]
    densities = (densities or {}).get("widths", {})
    for cand in result["candidates"]:
        stat = cand["row2"].get("statistic")
        name = cand["name"]
        geo = cand.get("geometry") or {}
        loads = geo.get("XM5.w", "?")
        if cand.get("geometry_problems"):
            loads = "INCONSISTENT"
        mean = (stat or {}).get("grid_mean") if stat else None
        valid = f"{stat['points_valid']}/{stat['points_expected']}" if stat else "0/18"
        if mean is not None and control["screen_mean"] is not None:
            ratio = mean / control["screen_mean"]
            vs = f"x{ratio:.3f}"
        else:
            vs = "-"
        density = densities.get(name, {}).get("points", {}).get("tt", {}).get("density_nv_rthz")
        proj = _projection(control, density) if isinstance(density, (int, float)) else None
        L.append(f"| {name} | {loads} | {valid} | {_fmt(mean)} | {vs} | {_fmt(density)} | "
                 f"{_fmt(proj)} (projection) |")
    L += ["", "## Fast-bench screen gates (Target bounds at the screened points)", "",
          "A MEASURED value above a gated Target bound eliminates the width (the screened "
          "point is in the 45-point grid, so the full verdict would fail). An unavailable "
          "metric is a carried caveat, not an elimination. Values: "
          "`sizesweep.md` in this campaign.", "",
          "| candidate | elimination reasons | carried caveats |", "|---|---|---|"]
    for cand in result["candidates"]:
        reasons = "; ".join(cand["elimination_reasons"]) or "-"
        caveats = "; ".join(cand.get("gates_unavailable") or []) or "-"
        L.append(f"| {cand['name']} | {reasons} | {caveats} |")
    advanced = result.get("advanced") or []
    L += ["", "## Advance / eliminate", ""]
    if advanced:
        L.append(f"Advanced (at most one): **{advanced[0]}** -- lowest valid Row 2 screen mean "
                 "among the widths not eliminated. Its full 45-point campaign is "
                 f"`full_{advanced[0]}/`, graded by `kltsim.grade`. Full-grid rows are "
                 "UNMEASURED (not run) for every eliminated width: `full_*` campaigns exist "
                 "only for the advanced finalist.")
    else:
        L.append("No width advanced (negative result): every tested width is eliminated above. "
                 "Per the issue, a negative result completes the study; no full-grid run "
                 "was made for this family.")
    L += ["", "## Disclosures", "",
          "Monte-Carlo seeds and run counts are the bench defaults committed in each request "
          "(transient noise: N = 80 per rung, base seed 20260916; the seed is recorded "
          "only). ngspice's TRNOISE source seed limitation applies as in every campaign "
          "run: draws are independent within a point but not reproducible, and separate "
          "batch jobs can share noise streams "
          "([klayout-tools#5772](https://github.com/2AMLogic/klayout-tools/issues/5772), "
          "[klayout-tools#2963](https://github.com/2AMLogic/klayout-tools/issues/2963)). "
          "Every grid ran on the batch fleet with `--wait-for-capacity`; nothing ran "
          "locally. Candidate input-referred densities come from the reduced-model "
          "characterization (Phase 1 method: output white density at 1 MHz divided by "
          "|Av(1 Hz)|); see the linked report for its PVT coverage. Projections rescale "
          "the control's 45-point mean by the candidate's own TT density ratio and are "
          "labelled as projections, never verdicts.",
          "",
          "The transient-noise screen envelopes and the finalist's Monte-Carlo evidence "
          "are stored, not committed (issue #318): summary "
          "[`../../20261121-issue498-mc.md`](../../20261121-issue498-mc.md), manifest "
          "`manifests/artifacts/klt-corner-verification-20261121-issue498-mc.manifest.json`. "
          "The deterministic kickback/regeneration envelopes and the finalist's grading "
          "are committed in this campaign directory.", ""]
    return "\n".join(L)
