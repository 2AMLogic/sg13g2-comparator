"""Comparison and rendering for the issue #173 clock/supply sensitivity
campaign. Reads only committed envelopes; GENERATED output, do not edit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import build as build_mod
from . import clocksupply as cs
from . import grade as grade_mod

#: the issue #62 campaign the baseline must reproduce
REFERENCE_CAMPAIGN = "20261009-d73a9ac"


def _load(path: Path):
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _source(env: dict, sha: str, tag: str) -> dict:
    prov = env.get("provenance") or {}
    remote = (env.get("environment") or {}).get("remote") or {}
    return {"tag": tag, "envelope_sha256": sha, "status": env.get("status"),
            "corner_count": env.get("corner_count"), "errored": env.get("errored"),
            "job_id": remote.get("job_id"), "klt_version": prov.get("klt_version"),
            "content_hash": (prov.get("input") or {}).get("content_hash")}


def _reference_checks(base_regen: dict, base_off: dict, ref_dir: Path) -> dict:
    out = {"reference": f"sim/klt-corner-verification/campaigns/{REFERENCE_CAMPAIGN}",
           "regen": None, "offset": None}
    p = ref_dir / "regeneration.envelope.json"
    if p.is_file():
        ref = cs.regen_points(_load(p)[0])
        diffs = []
        for k, v in base_regen.items():
            r = ref.get(k)
            if (r and not r["problem"] and not v["problem"]
                    and v["td50_ns"] is not None and r["td50_ns"] is not None):
                diffs.append((abs(v["td50_ns"] - r["td50_ns"]),
                              abs((v["tau_ps"] or 0) - (r["tau_ps"] or 0)),
                              abs((v["td01_ns"] or 0) - (r["td01_ns"] or 0))))
        out["regen"] = {"points_compared": len(diffs),
                        "max_abs_d_td50_ns": max((d[0] for d in diffs), default=None),
                        "max_abs_d_tau_ps": max((d[1] for d in diffs), default=None),
                        "max_abs_d_td01_ns": max((d[2] for d in diffs), default=None)}
    ref_samples: dict = {}
    for proc in cs.PROCESSES:
        q = ref_dir / f"offset_mc.mos_{proc}_mismatch.envelope.json"
        if q.is_file():
            for k, v in cs.offset_samples(_load(q)[0]).items():
                ref_samples[k] = v
    if ref_samples:
        compared = identical = seed_mismatch = seed_absent = 0
        max_diff = 0.0
        for k, mine in base_off.items():
            theirs = ref_samples.get(k)
            if not theirs:
                continue
            for i, s in mine.items():
                t = theirs.get(i)
                if (t is None or s["problem"] or t["problem"]
                        or s["vos_mv"] is None or t["vos_mv"] is None):
                    continue
                if s["seed"] is None or t["seed"] is None:
                    seed_absent += 1
                    continue
                if s["seed"] != t["seed"]:
                    seed_mismatch += 1
                    continue
                compared += 1
                d = abs(s["vos_mv"] - t["vos_mv"])
                max_diff = max(max_diff, d)
                identical += d == 0.0
        out["offset"] = {"samples_compared": compared, "identical": identical,
                         "seed_mismatches_not_compared": seed_mismatch,
                         "seed_absent_not_compared": seed_absent, "max_abs_diff_mv": max_diff}
    return out


def compare_series(series_dir: Path) -> dict:
    regen, offs, sources = {}, {}, []
    for c in cs.CONDITIONS:
        for kind, store in (("regen", regen), ("offset", offs)):
            path = series_dir / c.name / f"{kind}.{c.name}.envelope.json"
            if not path.is_file():
                continue
            env, sha = _load(path)
            sources.append({"condition": c.name, "kind": kind, **_source(env, sha, f"{kind}.{c.name}")})
            store[c.name] = (cs.regen_points(env) if kind == "regen" else cs.offset_samples(env))
    base_r, base_o = regen.get(cs.BASELINE), offs.get(cs.BASELINE)
    result = {
        "issue": 173,
        "series": series_dir.name,
        "scope": ("CHARACTERIZATION: DR-0002 ratifies every row at one clock shape on a DC "
                  "supply. No bound is graded here and none is changed."),
        "basis": {
            "regen_grid": "5 process x {1.08,1.20,1.32} V x {-40,27,125} C = 45 points, mismatch off",
            "offset_grid": (f"5 process x {list(cs.OFFSET_SUPPLIES_V)} V x "
                            f"{list(cs.OFFSET_TEMPERATURES_C)} C = 20 points, mismatch on"),
            "offset_n_per_point": cs.OFFSET_N, "offset_seed": cs.OFFSET_SEED,
            "step_mv": cs.STEP_MV,
        },
        "conditions": {c.name: c.metadata() for c in cs.CONDITIONS},
        "regen": {}, "offset": {}, "sources": sources, "reference": None,
    }
    for name, pts in regen.items():
        result["regen"][name] = cs.regen_summary(pts, base_r if name != cs.BASELINE else None)
        result["regen"][name]["per_point"] = {
            grade_mod.key_label(k): {kk: vv for kk, vv in p.items()} for k, p in sorted(pts.items(), key=str)}
    for name, smp in offs.items():
        if base_o is None or name == cs.BASELINE:
            continue
        pair = cs.offset_pair(smp, base_o)
        pair["per_point"] = {grade_mod.key_label(k): v for k, v in sorted(pair["per_point"].items(), key=str)}
        pair["clipped"] = sum(1 for pt in smp.values() for s in pt.values() if s["clipped"])
        pair["coverage"] = cs.offset_coverage(smp)
        pair["untrusted"] = sum(1 for pt in smp.values() for s in pt.values() if s["problem"])
        result["offset"][name] = pair
    if base_o is not None:
        b = cs.offset_pair(base_o, base_o)
        result["offset"][cs.BASELINE] = {
            "n_pairs": b["n_pairs"], "pooled_sigma_mv": b["pooled_sigma_mv"],
            "coverage": cs.offset_coverage(base_o),
            "clipped": sum(1 for pt in base_o.values() for s in pt.values() if s["clipped"]),
            "untrusted": sum(1 for pt in base_o.values() for s in pt.values() if s["problem"]),
        }
    if base_r is not None and base_o is not None:
        result["reference"] = _reference_checks(
            base_r, base_o, build_mod.EXPERIMENT_DIR / "campaigns" / REFERENCE_CAMPAIGN)
    return result


def dumps_report(result: dict) -> str:
    """Strict JSON (RFC 8259): ``allow_nan=False``; any stray non-finite
    float is written as null rather than a NaN/Infinity token."""
    return grade_mod.dumps_strict(result, indent=2) + "\n"


def _f(x, nd=3) -> str:
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def _rng(s, nd=3):
    return "—" if not s else f"{s['min']:.{nd}f} … {s['max']:.{nd}f}"


def render_markdown(r: dict) -> str:
    out = [f"# Clock-edge, strobe-width and supply-disturbance sensitivity — series `{r['series']}`",
           "", "GENERATED by `python3 sim/run_clock_supply_sensitivity.py compare` from the committed",
           "envelopes; do not edit.", "", "## Scope", "",
           f"**Characterization, not compliance.** {r['scope']}", "",
           "## Statistical basis", "",
           f"- Regeneration bench: {r['basis']['regen_grid']}. Deterministic (no Monte Carlo), so no sigma is claimed.",
           f"- Offset bench: {r['basis']['offset_grid']}; N = {r['basis']['offset_n_per_point']} mismatch draws "
           f"per point, klt base seed {r['basis']['offset_seed']}. Each draw's seed derives from (base seed, corner "
           "index, sample index) only, so draw k at a point is the same mismatch in every condition; pairing is "
           "checked per sample (seed equality), not assumed.",
           "- The offset resolution is one staircase level (3 mV). The paired statistic is the mean shift of "
           "(condition − base) over all paired draws with its standard error, plus how many draws moved a level. "
           "A pooled within-point spread (RMS about each point's own mean, dof = N_total − n_points, minus step²/12) "
           "is reported for the spread; it is NOT a single-point 3σ and no offset 3σ is claimed from N = 16.", ""]
    ref = r.get("reference")
    out += ["## Baseline reproduction (sanity)", ""]
    if ref:
        g = ref.get("regen")
        if g:
            out.append(f"- `base` regeneration vs `{ref['reference']}` (same circuit, ratified clock): over "
                       f"{g['points_compared']} points, max |Δtd50| = {g['max_abs_d_td50_ns']:.3g} ns, max |Δtau| = "
                       f"{g['max_abs_d_tau_ps']:.3g} ps, max |Δtd(0.1 mV)| = {g['max_abs_d_td01_ns']:.3g} ns.")
        o = ref.get("offset")
        if o:
            out.append(f"- `base` offset draws vs the same campaign's draws with an identical seed "
                       f"({o['samples_compared']} compared; {o['seed_mismatches_not_compared']} seed-mismatched and "
                       f"{o.get('seed_absent_not_compared', 0)} seed-absent, not compared): {o['identical']} bit-identical, max |Δvos| = {o['max_abs_diff_mv']:.3g} mV.")
    else:
        out.append("Not evaluated.")
    out += ["", "## Decision time, tau and decision correctness (45-point PVT grid)", "",
            "td in ns from the clock's 50 % rising crossing to the output's 50 % crossing, supply-normalised. "
            "Correct = both polarities decided right (first strobe low, second high). ≤ 1.5 ns is quoted as a "
            "reference only (the ratified Target is stated at the ratified clock).", "",
            "| condition | td50 min … max (ns) | binding point | Δtd50 vs base min … max | td(1 mV) min … max | tau min … max (ps) | td50 ≤ 1.5 ns | correct 50 mV | correct 1 mV | correct 0.1 mV | untrusted | coverage (usable/expected) |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in cs.CONDITIONS:
        s = r["regen"].get(c.name)
        if not s:
            out.append(f"| `{c.name}` | not run ||||||||||")
            continue
        td = s["td50_ns"]
        d = s.get("d_td50_ns")
        dtxt = "—" if not d else "%+.3f … %+.3f" % (d["min"], d["max"])
        out.append(
            f"| `{c.name}` | {_rng(td)} | `{td['binding'] if td else '—'}` | "
            f"{dtxt} | {_rng(s['td1_ns'])} | "
            f"{_rng(s['tau_ps'], 1)} | {s['td50_within_1p5ns']}/{s['points']} | {s['correct50']}/{s['points']} | "
            f"{s['correct1']}/{s['points']} | {s['correct01']}/{s['points']} | {len(s['untrusted'])} | "
            f"{s['coverage']['usable']}/{s['coverage']['expected']} {s['coverage']['label']} |")
    fails = [(n, s) for n, s in r["regen"].items() if s["failed_1mv_points"]]
    if fails:
        out += ["", "Points where the 1 mV decision was not correct:", ""]
        for n, s in fails:
            out.append(f"- `{n}`: {', '.join(f'`{p}`' for p in s['failed_1mv_points'])}")
    out += ["", "## Offset shift (paired draws against `base`)", "",
            "| condition | pairs | mean shift ± SEM (mV) | sd of Δ (mV) | draws that moved a level | pooled spread (mV) | base pooled spread (mV) | clipped | untrusted | seed-absent | coverage (usable/expected) |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    base_sig = (r["offset"].get(cs.BASELINE) or {}).get("pooled_sigma_mv")
    for c in cs.CONDITIONS:
        if c.name == cs.BASELINE:
            continue
        o = r["offset"].get(c.name)
        if not o:
            out.append(f"| `{c.name}` | not run ||||||||||")
            continue
        out.append(
            f"| `{c.name}` | {o['n_pairs']} | {_f(o['mean_shift_mv'])} ± {_f(o['sem_mv'])} | "
            f"{_f(o['sd_delta_mv'])} | {o['changed']}/{o['n_pairs']} | {_f(o['pooled_sigma_mv'])} | "
            f"{_f(base_sig)} | {o['clipped']} | {o['untrusted']} | "
            f"{o['seed_absent']} | {o['coverage']['usable']}/{o['coverage']['expected']} "
            f"{o['coverage']['label']} |")
    out += ["", "## Envelopes", ""]
    for e in r["sources"]:
        out.append(f"- `{e['tag']}`: status `{e['status']}`, {e['corner_count']} units, errored {e['errored']}, "
                   f"job `{e['job_id']}`, klt {e['klt_version']}, sha256 `{e['envelope_sha256'][:16]}…`")
    return "\n".join(out) + "\n"
