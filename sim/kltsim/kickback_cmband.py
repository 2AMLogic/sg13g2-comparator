"""Kickback residue across a bounded input common-mode band (issue #165).

CHARACTERIZATION FOR THE CANDIDATE DR-0004 COMMON-MODE ROW, NOT RATIFICATION.
Every kickback record to date runs at ``dut_vcm`` only. This module builds,
validates and grades three deterministic ``klt sim`` corner campaigns of the
issue #62 ``kickback`` bench at ``dut_vcm`` -/+ 50 mV and at ``dut_vcm`` (the
reproduction gate), and compares them per PVT point.

CONDITION. The bench is unchanged in every respect but one source line

    vcm  cm 0 dc {dut_vcm}              (note the two spaces in the body)

which becomes

    .param vcm_delta=<delta>
    vcm cm 0 dc {dut_vcm+vcm_delta}

for all three conditions, the nominal one included (``vcm_delta=0.0``). The
match is whitespace tolerant and must hit exactly ONE line (zero or several
is an error). This is deliberately a separate transform from
``cmband.apply_transform``, which rewrites the offset bench's single-space
line and builds a Monte-Carlo bench; the kickback bench is deterministic
(``tran 5p 60n``, no Monte Carlo, no seeds).

VALIDITY. A grid point is VALID only if its corner reported, exactly once,
every measurement the reference request names with a finite value; did not
error; carries supply and temperature probes that match the corner; carries
a ``vcm_meas`` probe equal to the condition's common mode; and passed the
three decision-correctness gates. A charge-limit (``qkick_fc``) failure does
NOT invalidate a point: the Q_kick sub-bound is already NOT MET at nominal
(DR-0003), is not part of the candidate row's hold list, and is reported
beside the residue, never folded into it. A rejected point is named with its
reason; nothing is substituted for it.

GRADING. Only valid ``kick_sigdep_uv`` values are graded, against the
unchanged ratified Row 4 residue Target (<= 100 uV) and Stretch (<= 30 uV).
A condition with fewer than 45 valid points is INCOMPLETE, never MET.

REPRODUCTION GATE. ``vcm-nom`` must equal the issue #62 campaign's kickback
envelope on every ORIGINAL measurement value (exact float equality) at all
45 PVT keys, with matching model library, engine, analysis, corner grid,
original measurement cards and limits, and declared circuit/DUT hashes. The
added probe and the new netlist/invocation metadata are excluded. If it
fails, the series is excluded from DR-0004 evidence.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from pathlib import Path

from . import artifacts as artifacts_mod
from . import build as build_mod
from . import cmband
from . import grade as grade_mod
from .benches import KICKBACK, PROCESSES, SUPPLIES_V, TEMPERATURES_C

EXPERIMENT_DIR = build_mod.SIM_DIR / "comparator-kickback-cm-band"
SERIES_DIR = EXPERIMENT_DIR / "campaigns"

BENCH_NAME = KICKBACK.name  # "kickback" (grade.py looks the bench up by name)
TAG = BENCH_NAME
BODY_NAME = f"{BENCH_NAME}.body.spice"

REFERENCE_CAMPAIGN = "20261009-d73a9ac"
REFERENCE_DIR = build_mod.EXPERIMENT_DIR / "campaigns" / REFERENCE_CAMPAIGN

#: Match the one common-mode source whatever the spacing.
VCM_RE = re.compile(r"^vcm\s+cm\s+0\s+dc\s+\{dut_vcm\}\s*$")
VCM_LINE_CM = cmband.VCM_LINE_CM
CONDITION_MARK = "* ---- CM-band condition (issue #165):"

#: Ratified DR-0002 Row 4 residue bounds (unchanged; quoted, not edited).
RESIDUE_TARGET_UV = 100.0
RESIDUE_STRETCH_UV = 30.0
RESIDUE = "kick_sigdep_uv"
GATES = ("dout_1k_end", "dout_float_small_end", "dout_float_big_end")
REPORTED = ("kick_sigdep_uv", "qkick_p_fc", "qkick_n_fc", "qkick_fc", "kick_1k_peak_mv",
            "kick_cm_uv")

VCM_PROBE = cmband.VCM_PROBE
VCM_TOL_V = cmband.VCM_TOL_V


class KickbackCmBandError(RuntimeError):
    pass


Condition = cmband.Condition
CONDITIONS = cmband.CONDITIONS
NOMINAL = cmband.NOMINAL
condition = cmband.condition


def expected_keys() -> list[tuple[str, float, float]]:
    """The 45 grid points, in the reference request's order."""
    return [(p, round(float(v), 6), float(t))
            for p in PROCESSES for v in SUPPLIES_V for t in TEMPERATURES_C]


def key_str(key) -> str:
    return f"{key[0]}/{key[1]:.3f}V/{key[2]:g}C"


# --------------------------------------------------------------------------- #
# body + request
# --------------------------------------------------------------------------- #


def bench_for(cond: Condition):
    """The #62 kickback bench plus the ``vcm_meas`` probe; nothing else."""
    return dataclasses.replace(
        KICKBACK, measurements=KICKBACK.measurements + (VCM_PROBE,),
        description=(
            f"CHARACTERIZATION (issue #165), condition {cond.name}: kickback residue at input "
            f"common mode dut_vcm{cond.delta_v * 1e3:+.0f} mV. Unchanged issue #62 kickback "
            "bench except the common-mode source and one added probe."))


def apply_transform(body: str, cond: Condition) -> str:
    return cmband.rewrite_vcm_line(
        body, cond,
        is_vcm_line=lambda line: bool(VCM_RE.match(line)),
        mark=CONDITION_MARK,
        header=(f"* {BENCH_NAME} -- klt sim netlist BODY (sim/comparator-kickback-cm-band, "
                f"issue #165) condition={cond.name} vcm_delta={cond.delta_v!r}",
                "* GENERATED by `python3 sim/run_kickback_cm_band.py build` from the issue #62 "
                "kickback body (sim/kltsim/kickback_cmband.py) -- do not edit;"),
        error=lambda n: KickbackCmBandError(
            f"expected exactly one common-mode source line (vcm cm 0 dc {{dut_vcm}}) in the "
            f"kickback body, found {n}"))


undo_transform = cmband.undo_transform


def compose_body(cond: Condition, osdi_dir: str = build_mod.BATCH_OSDI_DIR) -> str:
    return apply_transform(build_mod.compose_body(KICKBACK, osdi_dir), cond)


def condition_metadata(cond: Condition) -> dict:
    return {
        "issue": 165,
        "name": cond.name,
        "vcm_delta_v": cond.delta_v,
        "vcm_v": cond.vcm_v(),
        "scope": "characterization for candidate DR-0004 CM row (no ratified CM range)",
    }


def _reference_order(measurements: list[dict]) -> list[dict]:
    """Order the measurement cards exactly as the reference (#62) request has
    them, the added probe last. The committed reference was generated before
    benches.py's Q_kick cards were reordered; the cards are identical but the
    request must be the reference's own, not a lookalike. Any content
    difference (not just order) is an error."""
    ref = json.loads((REFERENCE_DIR / f"{TAG}.request.json").read_text(encoding="utf-8"))
    ordered = list(ref["measurements"]) + [VCM_PROBE.request_entry()]
    key = lambda m: json.dumps(m, sort_keys=True)  # noqa: E731
    if sorted(map(key, ordered)) != sorted(map(key, measurements)):
        raise KickbackCmBandError(
            "the kickback bench's measurement cards differ in content from the reference "
            f"request {REFERENCE_CAMPAIGN}; refusing to build a non-identical campaign")
    return ordered


def compose_request(cond: Condition, body_name: str = BODY_NAME, backend: str = "batch") -> dict:
    bench = bench_for(cond)
    request = build_mod.compose_request(bench, body_name, backend)
    request["measurements"] = _reference_order(request["measurements"])
    request["_comment"] = [
        f"sg13g2-comparator -- klt sim request, CM-band kickback condition `{cond.name}` "
        "(issue #165).",
        "GENERATED by `python3 sim/run_kickback_cm_band.py build`; the committed copy is "
        "byte-for-byte what was submitted.",
        bench.description,
        "Grid, analysis, measurements and limits are the issue #62 kickback bench's, "
        "unchanged, plus the vcm_meas probe. Deterministic: no monte_carlo.",
    ]
    request["_condition"] = condition_metadata(cond)
    return request


def input_bytes(cond: Condition, osdi_dir: str = build_mod.BATCH_OSDI_DIR,
                backend: str = "batch") -> dict[str, bytes]:
    """File name -> exact bytes of the body and the request for a condition."""
    return {
        BODY_NAME: compose_body(cond, osdi_dir).encode("utf-8"),
        f"{TAG}.request.json": (json.dumps(compose_request(cond, BODY_NAME, backend), indent=2)
                                + "\n").encode("utf-8"),
    }


def commit_inputs(files: list[tuple[Path, bytes]], *, evidence: str = "evidence") -> list[Path]:
    """Append-only batch write of a complete, precomputed input set through
    the shared ``artifacts.commit`` contract: a symlink or non-regular
    destination, or any content difference, rejects the WHOLE set before
    anything is written; identical files are reused without a write; absent
    files are created with exclusive creation (no check-then-write window).
    Returns the paths newly created."""
    try:
        return artifacts_mod.commit(
            files,
            differs=f"exists and differs -- {evidence} is append-only; use a new --series",
            dup="two different contents proposed for one input file")
    except artifacts_mod.ArtifactConflict as exc:
        raise KickbackCmBandError("; ".join(exc.conflicts)) from None


def write_condition_inputs(cond: Condition, out_dir: Path, **kw) -> list[Path]:
    """Write body + request; refuse to change anything already there."""
    files = input_bytes(cond, **kw)
    commit_inputs([(out_dir / name, data) for name, data in files.items()],
                  evidence="campaign evidence")
    return [out_dir / name for name in files]


# --------------------------------------------------------------------------- #
# validity
# --------------------------------------------------------------------------- #


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _num(index: dict, name: str):
    m = index.get(name)
    if m is None or m.get("value") is None:
        return None
    try:
        return grade_mod.finite(m["value"], name)
    except grade_mod.NonFiniteError:
        return None


def point_problem(corner: dict, vcm_v: float, required: list[str]) -> str | None:
    """Why this corner's numbers cannot be trusted, or None."""
    problem = grade_mod._corner_problems(corner, BENCH_NAME, list(GATES))
    if problem:
        return problem
    index, bad = grade_mod.measurement_index(corner)
    if bad:
        return bad
    probe = index.get(VCM_PROBE.name)
    if probe is None or probe.get("value") is None:
        return "common-mode probe vcm_meas missing"
    try:
        pv = grade_mod.finite(probe["value"], "vcm_meas")
    except grade_mod.NonFiniteError as exc:
        return f"invalid numeric evidence: {exc}"
    if abs(pv - vcm_v) > VCM_TOL_V:
        return f"common-mode probe vcm_meas={probe['value']} V is not the condition's {vcm_v} V"
    for name in required:
        if _num(index, name) is None:
            return f"measurement {name} missing or not finite"
    return None


def load_points(envelope: dict) -> tuple[dict, list[str]]:
    """key -> corner for the expected grid; plus structural findings
    (duplicates, unplaceable and off-grid corners)."""
    seen: dict[tuple, list[dict]] = {}
    notes: list[str] = []
    for corner in envelope.get("corners") or []:
        if corner.get("monte_carlo") is not None:
            notes.append(f"unexpected Monte-Carlo corner {corner.get('corner_id')}")
            continue
        key = grade_mod._corner_key(corner)
        if key is None:
            notes.append(f"unplaceable corner {corner.get('corner_id')}")
            continue
        seen.setdefault(key, []).append(corner)
    grid = set(expected_keys())
    for key in sorted(seen, key=str):
        if key not in grid:
            notes.append(f"off-grid corner {key_str(key)}")
    for key, v in sorted(seen.items(), key=lambda kv: str(kv[0])):
        if len(v) > 1:
            notes.append(f"duplicate result for {key_str(key)}: "
                         f"{sorted(str(c.get('corner_id')) for c in v)}; no result selected")
    return {k: v[0] for k, v in seen.items() if len(v) == 1}, notes


def required_measurements() -> list[str]:
    return [m.name for m in KICKBACK.measurements]


def evaluate_condition(cond: Condition, envelope: dict) -> dict:
    """Per-point validity + values, and condition-level residue statistics."""
    corners, notes = load_points(envelope)
    dupes = {n.split(" for ")[1].split(":")[0] for n in notes if n.startswith("duplicate")}
    vcm_v = cond.vcm_v()
    required = required_measurements()
    points = []
    for key in expected_keys():
        label = key_str(key)
        corner = corners.get(key)
        entry = {"key": label, "process": key[0], "supply_v": key[1], "temperature_c": key[2],
                 "valid": False, "reason": None, "corner_status": None, "values": {},
                 "qkick_limit_failed": None}
        if label in dupes:
            entry["reason"] = "ambiguous duplicate PVT result, no value selected"
        elif corner is None:
            entry["reason"] = "grid point not in the envelope"
        else:
            entry["corner_status"] = corner.get("status")
            problem = point_problem(corner, vcm_v, required)
            index, _ = grade_mod.measurement_index(corner)
            if index:
                entry["values"] = {n: _num(index, n) for n in (*REPORTED, "vcm_meas")}
                q = index.get("qkick_fc")
                entry["qkick_limit_failed"] = (None if q is None else q.get("status") != "pass")
            if problem:
                entry["reason"] = problem
            else:
                entry["valid"] = True
        points.append(entry)
    valid = [p for p in points if p["valid"]]
    resid = [(p["values"][RESIDUE], p["key"]) for p in valid]
    stats = {
        "points_expected": len(points), "points_valid": len(valid),
        "rejected": [{"key": p["key"], "reason": p["reason"]} for p in points if not p["valid"]],
        "structural_notes": notes,
        "residue_uv": {
            "min": min(resid)[0] if resid else None, "min_at": min(resid)[1] if resid else None,
            "max": max(resid)[0] if resid else None, "max_at": max(resid)[1] if resid else None,
        },
    }
    for name in ("qkick_p_fc", "qkick_n_fc", "qkick_fc", "kick_1k_peak_mv"):
        vals = [(p["values"][name], p["key"]) for p in valid]
        stats[name] = {"min": min(vals)[0] if vals else None,
                       "max": max(vals)[0] if vals else None}
    stats["qkick_limit_failures"] = sum(1 for p in valid if p["qkick_limit_failed"])
    stats["verdict"] = grade_residue(stats)
    return {"condition": cond.name, "vcm_v": vcm_v, "vcm_delta_v": cond.delta_v,
            "envelope_status": envelope.get("status"), "points": points, **stats}


def grade_residue(stats: dict) -> dict:
    """Residue-only verdict (the fleet's aggregate status is not consulted)."""
    n_ok, n_all = stats["points_valid"], stats["points_expected"]
    mx = stats["residue_uv"]["max"]
    if n_ok != n_all or stats["structural_notes"]:
        return {"target": "INCOMPLETE", "stretch": "INCOMPLETE",
                "basis": f"{n_ok}/{n_all} valid points; rejected points are named, not repaired"}

    def v(bound):
        return "MET" if mx <= bound else "NOT MET"
    return {"target": v(RESIDUE_TARGET_UV), "stretch": v(RESIDUE_STRETCH_UV),
            "basis": f"max over {n_all}/{n_all} valid points = {mx} uV vs Target "
                     f"<= {RESIDUE_TARGET_UV:g} uV / Stretch <= {RESIDUE_STRETCH_UV:g} uV"}


# --------------------------------------------------------------------------- #
# nominal reproduction gate
# --------------------------------------------------------------------------- #

_DECLARED = re.compile(r"^\*\s+(circuit|DUT):\s+(\S+)\s+sha256=([0-9a-f]{64})", re.M)


def declared_hashes(body_text: str) -> dict:
    return {m.group(1): (m.group(2), m.group(3)) for m in _DECLARED.finditer(body_text)}


def _strip_request(req: dict, drop_probe: bool) -> dict:
    out = {k: v for k, v in req.items() if k not in ("_comment", "_condition", "netlist")}
    if drop_probe:
        out["measurements"] = [m for m in out["measurements"] if m["name"] != VCM_PROBE.name]
    return out


def reproduction_check(nominal_env: dict, nominal_request: dict, nominal_body: str,
                       ref_env: dict, ref_request: dict, ref_body: str) -> dict:
    """Original-measurement equality at every PVT key plus provenance match.
    ``ok`` is False on ANY discrepancy; every discrepancy is listed."""
    problems: list[str] = []
    if _strip_request(nominal_request, True) != _strip_request(ref_request, False):
        problems.append("request (grid, analysis, models, measurements, limits, options) "
                        "differs from the reference beyond the added probe")
    if declared_hashes(nominal_body) != declared_hashes(ref_body):
        problems.append("declared circuit/DUT hashes differ from the reference body")
    for field in ("engine", "engine_version", "models_lib_sha256", "netlist_source"):
        a = (nominal_env.get("environment") or {}).get(field)
        b = (ref_env.get("environment") or {}).get(field)
        if a != b:
            problems.append(f"environment.{field}: {a!r} != reference {b!r}")
    nom, n_notes = load_points(nominal_env)
    ref, r_notes = load_points(ref_env)
    problems += [f"nominal: {n}" for n in n_notes] + [f"reference: {n}" for n in r_notes]
    names = [m["name"] for m in ref_request["measurements"]]
    compared = 0
    mismatches = []
    for key in expected_keys():
        a, b = nom.get(key), ref.get(key)
        if a is None or b is None:
            problems.append(f"{key_str(key)}: missing in {'nominal' if a is None else 'reference'}")
            continue
        ai, abad = grade_mod.measurement_index(a)
        bi, bbad = grade_mod.measurement_index(b)
        if abad or bbad:
            problems.append(f"{key_str(key)}: unreliable measurement list ({abad or bbad})")
            continue
        for name in names:
            x, y = ai.get(name), bi.get(name)
            if x is None or y is None:
                problems.append(f"{key_str(key)}: {name} missing")
                continue
            compared += 1
            if x.get("value") != y.get("value") or x.get("status") != y.get("status"):
                mismatches.append({"key": key_str(key), "measurement": name,
                                   "nominal": x.get("value"), "reference": y.get("value"),
                                   "nominal_status": x.get("status"),
                                   "reference_status": y.get("status")})
    return {"ok": not problems and not mismatches, "values_compared": compared,
            "expected_values": len(expected_keys()) * len(names),
            "mismatches": mismatches, "problems": problems}


# --------------------------------------------------------------------------- #
# comparison (offline, deterministic)
# --------------------------------------------------------------------------- #


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _remote(env: dict) -> dict:
    r = (env.get("environment") or {}).get("remote") or {}
    return {k: r.get(k) for k in ("provider", "job_id", "instance_type", "lifecycle", "state")}


def compare_series(series: Path, reference_dir: Path = REFERENCE_DIR) -> dict:
    conds, envs = {}, {}
    for cond in CONDITIONS:
        cdir = series / cond.name
        env_path = cdir / f"{TAG}.envelope.json"
        if not env_path.is_file():
            raise KickbackCmBandError(f"missing envelope {env_path}")
        envs[cond.name] = _load(env_path)
        c = evaluate_condition(cond, envs[cond.name])
        c["inputs"] = {"body_sha256": _sha(cdir / BODY_NAME),
                       "request_sha256": _sha(cdir / f"{TAG}.request.json"),
                       "envelope_sha256": _sha(env_path)}
        inv = cdir / f"{TAG}.invocation.json"
        if inv.is_file():
            invocation = _load(inv)
            c["invocation"] = {k: invocation.get(k) for k in
                               ("klt_version", "env", "request_sha256", "exit_code",
                                "started_utc", "finished_utc", "envelope_sha256")}
            c["invocation"]["request_sha256_matches"] = (
                invocation.get("request_sha256") == c["inputs"]["request_sha256"])
        c["remote"] = _remote(envs[cond.name])
        conds[cond.name] = c
    nom = conds[NOMINAL]
    repro = reproduction_check(
        envs[NOMINAL], _load(series / NOMINAL / f"{TAG}.request.json"),
        (series / NOMINAL / BODY_NAME).read_text(encoding="utf-8"),
        _load(reference_dir / f"{TAG}.envelope.json"),
        _load(reference_dir / f"{TAG}.request.json"),
        (reference_dir / f"{TAG}.body.spice").read_text(encoding="utf-8"))
    per_point = []
    for i, key in enumerate(expected_keys()):
        row = {"key": key_str(key)}
        for name, c in conds.items():
            p = c["points"][i]
            row[name] = {"valid": p["valid"], "reason": p["reason"], **p["values"]}
            if name != NOMINAL and p["valid"] and nom["points"][i]["valid"]:
                row[name]["residue_delta_vs_nom_uv"] = round(
                    p["values"][RESIDUE] - nom["points"][i]["values"][RESIDUE], 6)
        per_point.append(row)
    usable = repro["ok"]
    return {
        "issue": 165, "series": series.name, "reference_campaign": reference_dir.name,
        "residue_target_uv": RESIDUE_TARGET_UV, "residue_stretch_uv": RESIDUE_STRETCH_UV,
        "reproduction": repro,
        "series_usable_for_dr0004": usable,
        "conditions": {n: {k: v for k, v in c.items() if k != "points"} for n, c in conds.items()},
        "per_point": per_point,
    }


def _f(x, nd=3):
    return "-" if x is None else f"{x:.{nd}f}"


def render_markdown(result: dict) -> str:
    r = result["reproduction"]
    out = ["# Kickback residue across the input common-mode band (issue #165)", "",
           "Characterization for the candidate DR-0004 CM row; not ratification. "
           f"Residue graded against the unchanged Row 4 Target <= {result['residue_target_uv']:g} uV, "
           f"Stretch <= {result['residue_stretch_uv']:g} uV. Q_kick and peak excursion are "
           "reported, not graded here.", "",
           f"Series `{result['series']}`; reference campaign `{result['reference_campaign']}`.", "",
           "## Nominal reproduction gate", "",
           f"**{'PASS' if r['ok'] else 'FAIL'}**: {r['values_compared']}/{r['expected_values']} "
           f"original measurement values compared exactly at 45 PVT keys; "
           f"{len(r['mismatches'])} value mismatch(es), {len(r['problems'])} other problem(s).", ""]
    for p in r["problems"]:
        out.append(f"- {p}")
    for m in r["mismatches"][:50]:
        out.append(f"- {m['key']} {m['measurement']}: {m['nominal']} vs reference {m['reference']}")
    if not result["series_usable_for_dr0004"]:
        out += ["", "**This series is EXCLUDED from DR-0004 evidence (reproduction failed).**"]
    out += ["", "## Per condition", "",
            "| condition | vcm (V) | valid | residue min ... max (uV) | Target | Stretch | "
            "Q_kick max (fC) | qkick limit fails | peak max (mV) | fleet job |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for n, c in result["conditions"].items():
        ru = c["residue_uv"]
        out.append(
            f"| `{n}` | {c['vcm_v']} | {c['points_valid']}/{c['points_expected']} | "
            f"{_f(ru['min'])} ({ru['min_at']}) ... {_f(ru['max'])} ({ru['max_at']}) | "
            f"{c['verdict']['target']} | {c['verdict']['stretch']} | "
            f"{_f(c['qkick_fc']['max'])} | {c['qkick_limit_failures']} | "
            f"{_f(c['kick_1k_peak_mv']['max'], 1)} | {c['remote'].get('job_id')} |")
    out += ["", "Q_kick per side (min ... max over valid points, fC):", "",
            "| condition | p side | n side |", "|---|---|---|"]
    for n, c in result["conditions"].items():
        out.append(f"| `{n}` | {_f(c['qkick_p_fc']['min'])} ... {_f(c['qkick_p_fc']['max'])} | "
                   f"{_f(c['qkick_n_fc']['min'])} ... {_f(c['qkick_n_fc']['max'])} |")
    for n, c in result["conditions"].items():
        if c["rejected"] or c["structural_notes"]:
            out += ["", f"### Rejected points, `{n}`", ""]
            out += [f"- {x['key']}: {x['reason']}" for x in c["rejected"]]
            out += [f"- {x}" for x in c["structural_notes"]]
    names = list(result["conditions"])
    out += ["", "## Per PVT point: residue (uV), Q_kick (fC), peak (mV)", "",
            "| point | " + " | ".join(f"{n} resid | {n} Q | {n} peak" for n in names) + " |",
            "|---|" + "---|---|---|" * len(names)]
    for row in result["per_point"]:
        cells = []
        for n in names:
            d = row[n]
            if d["valid"]:
                cells += [_f(d.get(RESIDUE)), _f(d.get("qkick_fc")), _f(d.get("kick_1k_peak_mv"), 1)]
            else:
                cells += [f"REJECTED ({d['reason']}); unvalidated residue {_f(d.get(RESIDUE))}", "-", "-"]
        out.append(f"| {row['key']} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# issue #405: supplementary probe of the two Row 4b band-edge rejects
# --------------------------------------------------------------------------- #
#
# SUPPLEMENTARY CHARACTERIZATION, NOT A DR-0004 VERDICT. The #165 campaign has
# two points that fail the decision-correctness gate (vcm-m050 ss/1.200V/-40C
# dout_float_big_end; vcm-p050 ss/1.080V/-40C dout_float_small_end). This
# section builds a separately labelled series that re-runs exactly those two
# points plus the vcm-nom control at the same two PVT points, in four labelled
# ARMS. The circuit body is byte-identical to the #165 body of the same
# condition (checked at build time); arms differ only in the request's
# measurement cards and analysis args. Nothing here edits, or is merged into,
# the #165 populations.

PROBE_ISSUE = 405
PROBE_PROCESS = "mos_ss"
PROBE_TEMPERATURE_C = -40.0
#: condition -> supplies run (the edge points, and the control at both).
PROBE_SUPPLIES_V = {"vcm-m050": (1.2,), "vcm-p050": (1.08,), "vcm-nom": (1.08, 1.2)}
PROBE_CAPACITY_WAIT_S = 600
PROBE_STROBE_NS = 30
PROBE_SAMPLE_NS = (30, 31, 32, 34, 36, 40, 45, 50, 55)
#: branch label -> (dp node, dn node, normalized-decision node, input-diff node)
PROBE_BRANCHES = {"b": ("doutb", "doutbb", "dbn", "bd"), "c": ("doutc", "doutbc", "dcn", "cd")}
PROBE_ARMS = ("repro", "obs", "xing", "step20p")
STEP_ARM_ARGS = {"step20p": "5p 60n 0 20p"}
PROBE_REFERENCE_SERIES = "20261011-165"

# --------------------------------------------------------------------------- #
# issue #415: supplement arms that force a converged DC operating point
# --------------------------------------------------------------------------- #
# DISCRIMINATING FOLLOW-UP to the #405 probe, which left "no arm forced a
# converged DC point (.nodeset/.ic, gmin/itl options)" undone. The supplement
# runs the same two rejected points plus the vcm-nom control in a NEW series;
# repro/obs keep the #165 body byte-identical (reproduction gate) and the two
# new arms append ONE declared block to the body (probe_body_supplement):
#
#   optdc  DC convergence aids only (.options itl1/gminsteps/srcsteps, gmin
#          kept at its 1e-12 default); no .nodeset, no .ic. If the DC warning
#          clears and the programmed differential appears on bd/cd on its own,
#          the artifact is confirmed with no circularity to argue about.
#   icdc   .nodeset of the four floating input pins at their analytic DC
#          values (at DC no current flows through rfloat, so v(bpp) must
#          equal v(bsp) = v(cm) + dv_small/2, and likewise for the other
#          three) and .ic of every branch output at the LOW polarity
#          (dout=0) -- the wrong answer for the programmed differential, and
#          the state the rejects already hold on their failing branch. No
#          arm is forced toward the expected answer, so a 55 ns gate pass
#          needs a genuine post-strobe decision from a stated wrong-polarity
#          start.
#
# Because optdc/icdc bodies differ from the repro/obs body while one condition
# directory holds all four arms, the supplement arms reference per-arm body
# files (kickback-<arm>.body.spice); the shared kickback.body.spice stays the
# #165 body, written by repro/obs. The AC-2 diff against #165 is exactly the
# declared block.
#
# ngspice semantics (verified against the pinned ngspice-47, no uic on the
# tran): .nodeset and .ic without uic seed the DC solve rather than pinning
# nodes; in a bistable circuit the seed selects the basin the solve lands
# in. The realized start state is therefore re-read from the 1 ns
# observables instead of assumed; the series README interprets against it.

SUPPLEMENT_ISSUE = 415
#: The arm set the #415 forced-DC supplement series runs. repro/obs are shared
#: with the #405 probe (identical cards and body; only the issue label differs).
PROBE_ARMS_415 = ("repro", "obs", "optdc", "icdc")
#: Every arm the probe-build / probe-run / probe-compare CLI accepts (#405+#415).
ALL_PROBE_ARMS = PROBE_ARMS + tuple(a for a in PROBE_ARMS_415 if a not in PROBE_ARMS)
#: Arms whose body is the #165 body plus exactly probe_body_supplement().
PROBE_BODY_SUPPLEMENT_ARMS = ("optdc", "icdc")

PROBE_ARM_NOTES = {
    "repro": "arm repro: the #165 measurement cards and analysis, unchanged "
             "(reproduction gate).",
    "obs": "arm obs: #165 cards + outputs over time + input differential probes.",
    "xing": "arm xing: arm obs + decision-threshold crossing times.",
    "step20p": "arm step20p: arm obs with tran max step 20p (as the #89 supplement).",
    "optdc": "arm optdc: arm obs + DC convergence aids only (.options itl1/gminsteps/"
             "srcsteps, gmin kept at its 1e-12 default); no .nodeset, no .ic.",
    "icdc": "arm icdc: arm obs + .nodeset of the four floating input pins at their "
            "analytic DC values and .ic of every branch output at the LOW (dout=0) "
            "state -- the wrong polarity for the programmed differential.",
}


def probe_arm_tag(arm: str) -> str:
    return f"{TAG}-{arm}"


def _find(name: str, expr: str, at_ns: int, unit: str) -> dict:
    return {"name": name, "spice": f".meas tran {name} find {expr} at={at_ns}n", "unit": unit}


def probe_observables(with_crossings: bool) -> list[dict]:
    """Extra measurement cards: both outputs of branches B and C over time, the
    input differential at the strobe edge and at 1 ns (initial state), and
    (optionally) the time each branch first crosses a decision threshold."""
    cards = []
    for br, (dp, dn, norm, vd) in PROBE_BRANCHES.items():
        for t in PROBE_SAMPLE_NS:
            cards.append(_find(f"{br}_dp_{t}n", f"v({dp})", t, "V"))
            cards.append(_find(f"{br}_dn_{t}n", f"v({dn})", t, "V"))
        cards.append(_find(f"{br}_vd_strobe", f"v({vd})", PROBE_STROBE_NS, "V"))
        cards.append(_find(f"{br}_vd_1n", f"v({vd})", 1, "V"))
    if with_crossings:
        for br, (dp, dn, norm, vd) in PROBE_BRANCHES.items():
            cards.append({"name": f"{br}_t_half", "unit": "s", "spice":
                          f".meas tran {br}_t_half when v({norm})=0.5 td={PROBE_STROBE_NS}n cross=1"})
            cards.append({"name": f"{br}_t_pair", "unit": "s", "spice":
                          f".meas tran {br}_t_pair when v({dp})=v({dn}) td={PROBE_STROBE_NS}n cross=1"})
    return cards


def probe_request(cond: Condition, arm: str, *, issue: int = PROBE_ISSUE) -> dict:
    """The #165 request of ``cond`` restricted to the probe PVT points, with the
    arm's cards/analysis. Always batch (the body's OSDI path exists only on the
    fleet), with capacity_wait_s so a burst waits instead of failing. ``issue``
    labels the request's provenance: the #405 probe default; the #415
    forced-DC supplement passes SUPPLEMENT_ISSUE."""
    if arm not in ALL_PROBE_ARMS:
        raise KickbackCmBandError(f"unknown probe arm {arm!r}")
    req = compose_request(cond, probe_body_name(arm))
    req["corners"]["process"] = [PROBE_PROCESS]
    req["corners"]["supply_v"] = {"vsup": list(PROBE_SUPPLIES_V[cond.name])}
    req["corners"]["temperature_c"] = [PROBE_TEMPERATURE_C]
    if arm != "repro":
        req["measurements"] = req["measurements"] + probe_observables(with_crossings=(arm == "xing"))
    if arm in STEP_ARM_ARGS:
        req["analysis"] = {**req["analysis"], "args": STEP_ARM_ARGS[arm]}
    req["batch"] = {"capacity_wait_s": PROBE_CAPACITY_WAIT_S}
    if arm in PROBE_BODY_SUPPLEMENT_ARMS:
        body_note = (f"Body file `{probe_body_name(arm)}` is the issue #165 body of this "
                     "condition plus exactly the declared "
                     f"`{arm}` supplement block (see the series README); restricted to the probe "
                     "PVT points; separately labelled, never merged into the #165 populations.")
    else:
        body_note = ("Same body as the issue #165 campaign of this condition; restricted to the "
                     "probe PVT points; separately labelled, never merged into the #165 populations.")
    req["_comment"] = [
        f"sg13g2-comparator -- SUPPLEMENTARY probe request (issue #{issue}), condition "
        f"`{cond.name}`, arm `{arm}`.",
        "GENERATED by `python3 sim/run_kickback_cm_band.py probe-build`; the committed copy is "
        "byte-for-byte what was submitted.",
        body_note,
        PROBE_ARM_NOTES[arm],
    ]
    req["_condition"] = {**condition_metadata(cond), "issue": issue,
                         "probe_arm": arm, "reference_series": PROBE_REFERENCE_SERIES}
    if arm in PROBE_BODY_SUPPLEMENT_ARMS:
        req["_condition"]["body_supplement"] = arm
    return req


def probe_body_name(arm: str) -> str:
    """The body file this arm's request references. Arms with a declared
    supplement block get a per-arm body file -- several arms with different
    bodies share one condition directory, and the shared
    ``kickback.body.spice`` must stay the #165 body (repro/obs write it)."""
    return (f"{probe_arm_tag(arm)}.body.spice"
            if arm in PROBE_BODY_SUPPLEMENT_ARMS else BODY_NAME)


def probe_body_supplement(cond: Condition, arm: str) -> str:
    """The exact text appended to the #165 body for ``arm``; '' for arms that
    keep the #165 body byte-identical. The block is the ONLY permitted body
    change, so the AC-2 diff against #165 is exactly this text."""
    if arm == "optdc":
        return (
            "\n"
            "* ---- issue #415 supplement (arm optdc): DC convergence aids only --------\n"
            "* Appended verbatim after the issue #165 body; nothing else changed. Solver\n"
            "* effort only, so the graded values stay comparable to #165: reltol/vntol/\n"
            "* abstol/chgtol untouched, gmin pinned at its 1e-12 default (the 1 GOhm /\n"
            "* 1 pF floating network is sensitive to shunt conductance), no .nodeset,\n"
            "* no .ic, no analysis change.\n"
            ".options itl1=500 gminsteps=500 srcsteps=500 gmin=1e-12\n"
        )
    if arm == "icdc":
        cm = cond.vcm_v()
        half_small, half_big = 0.5e-3, 50.0e-3  # dv_small/2, dv_big/2 (body .param values)
        nodeset = (f".nodeset v(bpp)={cm + half_small:.4g} v(bpn)={cm - half_small:.4g}"
                   f" v(cpp)={cm + half_big:.4g} v(cpn)={cm - half_big:.4g}\n")
        return (
            "\n"
            "* ---- issue #415 supplement (arm icdc): forced DC operating point ----------\n"
            "* Appended verbatim after the issue #165 body; nothing else changed.\n"
            "* .nodeset: at DC no current flows through rfloat, so each floating pin sits\n"
            "* at its ideal source's value v(cm) +/- dv/2; the hint starts the DC solve\n"
            "* there instead of letting gmin stepping fail. .ic: every branch output is\n"
            "* seeded LOW (dout=0) -- the WRONG polarity for the programmed differential\n"
            "* and the state the rejects already hold on their failing branch; the\n"
            "* complementary nodes are left to the latch. No arm is forced toward the\n"
            "* expected answer, so a 55 ns gate pass needs a real post-strobe decision.\n"
            "* No uic on the tran: ngspice seeds (does not pin) the solve, the bistable\n"
            "* latch lands in the seeded basin, and the realized start state is re-read\n"
            "* from the 1 ns observables (series README).\n"
            f"{nodeset}"
            ".ic v(douta)=0 v(doutb)=0 v(doutc)=0\n"
        )
    return ""


def probe_expected_body(cond: Condition, arm: str) -> str:
    """The exact body this arm is allowed to write: the #165 body, plus the
    arm's declared supplement block if it declares one."""
    return compose_body(cond) + probe_body_supplement(cond, arm)


def probe_input_bytes(cond: Condition, arm: str, *, issue: int = PROBE_ISSUE) -> dict[str, bytes]:
    body = probe_body_name(arm)
    return {body: probe_expected_body(cond, arm).encode("utf-8"),
            f"{probe_arm_tag(arm)}.request.json":
            (json.dumps(probe_request(cond, arm, issue=issue), indent=2) + "\n").encode("utf-8")}


def check_probe_reference_body(cond: Condition, arm: str, files: dict[str, bytes]) -> None:
    """An arm without a supplement block must reference the shared body and
    that body must be byte-identical to the #165 body."""
    ref_body = SERIES_DIR / PROBE_REFERENCE_SERIES / cond.name / BODY_NAME
    if probe_body_name(arm) == BODY_NAME and files[BODY_NAME] != ref_body.read_bytes():
        raise KickbackCmBandError(
            f"probe body for {cond.name} differs from the #165 body {ref_body}; refusing")


def write_probe_inputs(cond: Condition, arm: str, out_dir: Path,
                       *, issue: int = PROBE_ISSUE) -> list[Path]:
    """Write body + arm request; refuse to change anything already there. An
    arm without a supplement block must reference the shared body and that
    body must be byte-identical to the #165 body."""
    files = probe_input_bytes(cond, arm, issue=issue)
    check_probe_reference_body(cond, arm, files)
    commit_inputs([(out_dir / name, data) for name, data in files.items()])
    return [out_dir / name for name in files]


def _meas_map(corner: dict) -> dict:
    return {m["name"]: m for m in corner.get("measurements") or []}


def probe_compare(series: Path, *, arms: tuple[str, ...] = PROBE_ARMS,
                  issue: int = PROBE_ISSUE) -> dict:
    """Offline comparison of every committed probe envelope against the #165
    envelope of the same condition at the same PVT key. ``arms`` is the arm set
    to look for: a listed arm without an envelope is a problem, so a series is
    only ever compared against its own arm set (the #405 probe default; the
    #415 supplement passes PROBE_ARMS_415)."""
    ref_root = SERIES_DIR / PROBE_REFERENCE_SERIES
    out: dict = {"issue": issue, "series": series.name,
                 "reference_series": PROBE_REFERENCE_SERIES, "points": [], "arms": {},
                 "problems": []}
    for cond in CONDITIONS:
        ref_env = _load(ref_root / cond.name / f"{TAG}.envelope.json")
        ref_corners, _ = load_points(ref_env)
        arm_corners: dict[str, dict] = {}
        for arm in arms:
            env_path = series / cond.name / f"{probe_arm_tag(arm)}.envelope.json"
            if not env_path.is_file():
                out["problems"].append(f"missing envelope {cond.name}/{arm}")
                continue
            env = _load(env_path)
            out["arms"][f"{cond.name}/{arm}"] = {
                **_remote(env), "envelope_status": env.get("status"),
                "request_sha256": _sha(series / cond.name / f"{probe_arm_tag(arm)}.request.json"),
                "envelope_sha256": _sha(env_path)}
            arm_corners[arm], notes = load_points(env)
            out["problems"] += [f"{cond.name}/{arm}: {n}" for n in notes]
        for sup in PROBE_SUPPLIES_V[cond.name]:
            key = (PROBE_PROCESS.removeprefix("mos_"), round(sup, 6), PROBE_TEMPERATURE_C)
            ref = ref_corners.get(key)
            ref_m = _meas_map(ref) if ref else {}
            row = {"condition": cond.name, "key": key_str(key), "arms": {}}
            for arm, corners in arm_corners.items():
                c = corners.get(key)
                if c is None:
                    row["arms"][arm] = {"present": False}
                    continue
                m = _meas_map(c)
                orig = [n for n in ref_m]
                diffs = [n for n in orig if (m.get(n) or {}).get("value") != ref_m[n].get("value")]
                row["arms"][arm] = {
                    "present": True, "corner_status": c.get("status"),
                    "corner_id": c.get("corner_id"),
                    "values": {n: x.get("value") for n, x in m.items()},
                    "statuses": {n: x.get("status") for n, x in m.items()
                                 if x.get("status") not in (None, "pass")},
                    "equals_165_on_original_cards": not diffs and bool(orig),
                    "differs_from_165": diffs}
            out["points"].append(row)
    return out


PROBE_GATES = ("dout_1k_end", "dout_float_small_end", "dout_float_big_end")


def probe_render_markdown(res: dict) -> str:
    def f(x):
        return "-" if x is None else f"{x:.4g}"
    o = [f"# Row 4b band-edge kickback probe (issue #{res['issue']})", "",
         "Supplementary characterization of the two #165 decision-gate rejects; reported beside, "
         f"never merged into, the `{res['reference_series']}` populations. No spec verdict, no "
         "sigma, no DR-0004 row pass is claimed here.", "",
         f"Series `{res['series']}`. Generated by `python3 sim/run_kickback_cm_band.py "
         "probe-compare`; do not edit.", ""]
    if res["problems"]:
        o += ["## Problems", ""] + [f"- {p}" for p in res["problems"]] + [""]
    o += ["## Fleet jobs", "", "| condition/arm | job id | state | PVT | envelope status |",
          "|---|---|---|---|---|"]
    for k, a in res["arms"].items():
        o.append(f"| `{k}` | {a.get('job_id')} | {a.get('state')} | "
                 f"{PROBE_PROCESS}/{PROBE_TEMPERATURE_C:g}C | {a.get('envelope_status')} |")
    o += ["", "## Reproduction (arm `repro` must equal #165 on every original value)", "",
          "| condition | point | arm | equals #165 on original cards | differing cards |",
          "|---|---|---|---|---|"]
    for r in res["points"]:
        for arm, a in r["arms"].items():
            if a.get("present"):
                o.append(f"| `{r['condition']}` | {r['key']} | {arm} | "
                         f"{a['equals_165_on_original_cards']} | {', '.join(a['differs_from_165']) or '-'} |")
    o += ["", "## Decision gates and per-branch outputs", "",
          "| condition | point | arm | " + " | ".join(PROBE_GATES) + " | b dp/dn @55n | c dp/dn @55n |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in res["points"]:
        for arm, a in r["arms"].items():
            if not a.get("present"):
                continue
            v = a["values"]
            o.append(f"| `{r['condition']}` | {r['key']} | {arm} | "
                     + " | ".join(f(v.get(g)) for g in PROBE_GATES)
                     + f" | {f(v.get('b_dp_55n'))} / {f(v.get('b_dn_55n'))}"
                     + f" | {f(v.get('c_dp_55n'))} / {f(v.get('c_dn_55n'))} |")
    o += ["", "## Input differential and decision timing (arms with the extra cards)", "",
          "| condition | point | arm | b vd @1n | b vd @strobe | c vd @1n | c vd @strobe | "
          "b t_half | b t_pair | c t_half | c t_pair |", "|" + "---|" * 11]
    for r in res["points"]:
        for arm, a in r["arms"].items():
            if not a.get("present") or "b_vd_strobe" not in a["values"]:
                continue
            v = a["values"]
            o.append(f"| `{r['condition']}` | {r['key']} | {arm} | "
                     + " | ".join(f(v.get(n)) for n in (
                         "b_vd_1n", "b_vd_strobe", "c_vd_1n", "c_vd_strobe",
                         "b_t_half", "b_t_pair", "c_t_half", "c_t_pair")) + " |")
    o += ["", "## Outputs over time (V), arm `obs`", ""]
    for r in res["points"]:
        a = r["arms"].get("obs")
        if not a or not a.get("present"):
            continue
        v = a["values"]
        o += [f"### `{r['condition']}` {r['key']}", "",
              "| t (ns) | " + " | ".join(f"{b} dp | {b} dn" for b in PROBE_BRANCHES) + " |",
              "|---|" + "---|---|" * len(PROBE_BRANCHES)]
        for t in PROBE_SAMPLE_NS:
            o.append(f"| {t} | " + " | ".join(
                f"{f(v.get(f'{b}_dp_{t}n'))} | {f(v.get(f'{b}_dn_{t}n'))}"
                for b in PROBE_BRANCHES) + " |")
        o.append("")
    return "\n".join(o) + "\n"
