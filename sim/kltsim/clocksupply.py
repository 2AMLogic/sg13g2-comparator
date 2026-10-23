"""Clock-edge, strobe-width and supply-disturbance sensitivity (issue #173).

CHARACTERIZATION, NOT COMPLIANCE. DR-0002 ratifies every row at one clock
shape (100 ps edges, 10 ns strobe in a 30 ns period) on a DC supply. This
module measures how the whole-latch ``comparator_dut`` moves when that clock
or supply is disturbed. No bound is graded; the output is a table and a
recommendation.

CONDITIONS (one-at-a-time around the baseline, nine in all):

    base         100 ps edges, 10 ns strobe, DC supply   (= ratified shape)
    edge-500p    500 ps rise AND fall
    edge-2n      2 ns rise AND fall
    strobe-5n    5 ns strobe (flat-top width)
    strobe-15n   15 ns strobe
    supmid-p50 / supmid-m50   +/-50 mV supply step, 1 ns edge, centred on the
                 strobe midpoint (the issue's specification)
    supeval-p50 / supeval-m50 +/-50 mV supply step, 1 ns edge, centred on the
                 clock's 50 % rising crossing, i.e. DURING regeneration

WHY TWO SUPPLY TIMINGS. At the baseline the latch resolves ~0.6-0.9 ns after
the clock edge, so a step at the 5 ns strobe midpoint arrives after the
decision: it can only disturb a HELD answer. ``supeval`` is the extra
condition that lands the step inside the regeneration window. Both are
reported; neither replaces the other.

HOW A CONDITION IS APPLIED. The two benches are the issue #62 ``regeneration``
and ``offset_mc`` circuits (``sim/klt-corner-verification/benches``) with a
fixed set of line rewrites (asserted one-for-one, see ``_sub``):

* the supply source ``vsup`` now feeds a CLEAN rail ``vddr`` (klt's
  ``alter vsup=<V>`` still reaches it); the DUT's ``vdd`` is ``vddr`` plus a
  series ``vdist`` source, a 1 ns-edge pulse of height ``vstep`` that returns
  to zero before the sampling instant (period 30 ns, so every strobe sees it);
* the clock amplitude and every supply-normalised probe use the CLEAN rail, so
  neither the clock nor the 0.5 thresholds move with the disturbance;
* ``pulse(0 1 10n tr tf pw 30n)`` carries the edge time and strobe width;
* strobe-width conditions move the regeneration bench's input flip (kept at
  the clock's falling edge) and its "first decision" gate with the strobe;
* the offset bench samples the output at 29 ns (was 27 ns) of each 30 ns
  period, so a 15 ns strobe has fully ended and the staircase step
  (29.8-30 ns) has not started. ``base`` is compared with the issue #62
  campaign to prove the move changes nothing.

``base`` has ``vstep = 0``: the same netlist, with an inert source.
"""

from __future__ import annotations

import dataclasses
import json
import math
from dataclasses import dataclass
from pathlib import Path

from . import build as build_mod
from . import grade as grade_mod
from .benches import (OFFSET_MC, OFFSET_MC_STEP_V, PROCESSES,
                      REGENERATION, SUPPLIES_V, TEMPERATURES_C)

EXPERIMENT_DIR = build_mod.SIM_DIR / "comparator-clock-supply-sensitivity"
SERIES_DIR = EXPERIMENT_DIR / "campaigns"

PERIOD_N = 30.0  # ns, clock period in both benches
STROBE_START_N = 10.0
BASE_TR_N = 0.1
BASE_PW_N = 10.0
DIST_EDGE_N = 1.0
DIST_FALL_START_N = 22.0  # disturbance has fully returned to 0 by 23 ns
STEP_V = 0.05

#: reduced offset grid (justified in the experiment README): the voltage x
#: temperature extremes of the ratified box, all five process corners.
OFFSET_SUPPLIES_V = (1.08, 1.32)
OFFSET_TEMPERATURES_C = (-40, 125)
#: draws per PVT point; the same seed contract as every other offset campaign
OFFSET_N = 16
OFFSET_SAMPLE_SHIFT_N = 2.0  # offset bench samples at 29 ns, was 27 ns
STEP_MV = OFFSET_MC_STEP_V * 1e3
OFFSET_SEED = OFFSET_MC.monte_carlo["seed"]

BASELINE = "base"


class SensitivityError(RuntimeError):
    pass


@dataclass(frozen=True)
class Condition:
    name: str
    what: str
    tr_n: float = BASE_TR_N
    pw_n: float = BASE_PW_N
    vstep: float = 0.0
    timing: str = "none"  # none | mid | eval

    def t_s_n(self) -> float:
        """Start of the 1 ns disturbance ramp (ns), within each period."""
        if self.timing == "mid":
            return STROBE_START_N + self.tr_n + self.pw_n / 2 - DIST_EDGE_N / 2
        if self.timing == "eval":
            return STROBE_START_N + self.tr_n / 2 - DIST_EDGE_N / 2
        return 5.0  # inert (vstep = 0)

    def pw_d_n(self) -> float:
        return DIST_FALL_START_N - self.t_s_n() - DIST_EDGE_N

    def shift_n(self) -> float:
        """How far this clock shape moves the first strobe's trailing edge
        from the baseline's (ns)."""
        return (self.pw_n - BASE_PW_N) + 2 * (self.tr_n - BASE_TR_N)

    def metadata(self) -> dict:
        return {"issue": 173, "name": self.name, "what": self.what, "edge_ns": self.tr_n,
                "strobe_ns": self.pw_n, "vstep_v": self.vstep, "step_timing": self.timing,
                "step_start_ns": self.t_s_n(), "step_hold_ns": self.pw_d_n()}


CONDITIONS = (
    Condition("base", "ratified clock (100 ps edges, 10 ns strobe), DC supply"),
    Condition("edge-500p", "500 ps rise/fall", tr_n=0.5),
    Condition("edge-2n", "2 ns rise/fall", tr_n=2.0),
    Condition("strobe-5n", "5 ns strobe", pw_n=5.0),
    Condition("strobe-15n", "15 ns strobe", pw_n=15.0),
    Condition("supmid-p50", "+50 mV supply step, 1 ns edge, at strobe midpoint",
              vstep=STEP_V, timing="mid"),
    Condition("supmid-m50", "-50 mV supply step, 1 ns edge, at strobe midpoint",
              vstep=-STEP_V, timing="mid"),
    Condition("supeval-p50", "+50 mV supply step, 1 ns edge, across the regeneration window",
              vstep=STEP_V, timing="eval"),
    Condition("supeval-m50", "-50 mV supply step, 1 ns edge, across the regeneration window",
              vstep=-STEP_V, timing="eval"),
)


def condition(name: str) -> Condition:
    for c in CONDITIONS:
        if c.name == name:
            return c
    raise SensitivityError(f"unknown condition {name!r}; known: {[c.name for c in CONDITIONS]}")


def _n(x: float) -> str:
    """ns value -> SPICE literal, exact and short."""
    return f"{round(x, 6):g}n"


# --------------------------------------------------------------------------- #
# circuit rewrites
# --------------------------------------------------------------------------- #


def _sub(text: str, old: str, new: str, count: int = 1) -> str:
    if text.count(old) != count:
        raise SensitivityError(
            f"expected {count} occurrence(s) of {old!r} in the bench circuit, found {text.count(old)}")
    return text.replace(old, new)


def _clock_and_supply(text: str, c: Condition, rails: tuple[str, ...]) -> str:
    """Shared rewrites. ``rails`` lists the supply source names (vsup[, vsupa])."""
    clk_old = "vclku clku 0 pulse(0 1 10n 100p 100p 10n 30n)"
    clk_new = (f"vclku clku 0 pulse(0 1 {_n(STROBE_START_N)} {_n(c.tr_n)} {_n(c.tr_n)} "
               f"{_n(c.pw_n)} {_n(PERIOD_N)})")
    text = _sub(text, clk_old, clk_new)
    text = _sub(text, "Bclk  clk  0 v = 'v(clku)*v(vdd)'", "Bclk  clk  0 v = 'v(clku)*v(vddr)'")
    dist = (f"pulse(0 {c.vstep:g} {_n(c.t_s_n())} {_n(DIST_EDGE_N)} {_n(DIST_EDGE_N)} "
            f"{_n(c.pw_d_n())} {_n(PERIOD_N)})")
    if rails == ("vsup",):
        text = _sub(text, "vsup vdd 0 dc 1.2",
                    f"vsup vddr 0 dc 1.2\nvdist vdd vddr {dist}")
    else:
        text = _sub(text, "vsup  vdd  0 dc 1.2", f"vsup  vddr  0 dc 1.2\nvdist vdd vddr {dist}")
        text = _sub(text, "vsupa vdda 0 dc 1.2", f"vsupa vddar 0 dc 1.2\nvdista vdda vddar {dist}")
    return text


def regeneration_circuit(c: Condition) -> str:
    text = (build_mod.BENCH_DIR / REGENERATION.circuit).read_text(encoding="utf-8")
    text = _clock_and_supply(text, c, ("vsup", "vsupa"))
    # input flip stays at the first strobe's trailing edge (baseline: 20 ns)
    text = _sub(text, ".param t_flip=20n", f".param t_flip={_n(20.0 + c.shift_n())}")
    text = _sub(text, "Bclkn clkn 0 v = 'v(clk)/v(vdd)'", "Bclkn clkn 0 v = 'v(clk)/v(vddr)'")
    text = _sub(text, "Bdan  dan  0 v = 'v(douta)/v(vdda)'", "Bdan  dan  0 v = 'v(douta)/v(vddar)'")
    text = _sub(text, "Bdbn  dbn  0 v = 'v(doutb)/v(vdd)'", "Bdbn  dbn  0 v = 'v(doutb)/v(vddr)'")
    text = _sub(text, "Bdcn  dcn  0 v = 'v(doutc)/v(vdd)'", "Bdcn  dcn  0 v = 'v(doutc)/v(vddr)'")
    return text


def offset_circuit(c: Condition) -> str:
    text = (build_mod.BENCH_DIR / OFFSET_MC.circuit).read_text(encoding="utf-8")
    text = _clock_and_supply(text, c, ("vsup",))
    text = _sub(text, "Bdoutn doutn 0 v = 'v(dout)/v(vdd)'", "Bdoutn doutn 0 v = 'v(dout)/v(vddr)'")
    for k in range(33):
        old = f"at={27 + 30 * k:.4f}n"
        text = _sub(text, f".meas tran dlev{k} find v(doutn) {old}",
                    f".meas tran dlev{k} find v(doutn) at={27 + 30 * k + OFFSET_SAMPLE_SHIFT_N:.4f}n")
    return text


# --------------------------------------------------------------------------- #
# benches
# --------------------------------------------------------------------------- #

REGEN_SPEC_NAMES = ("td_od50_ns", "td_od01_ns", "tau_ps")


def regeneration_bench(c: Condition):
    t1 = 18.0 + c.shift_n()
    meas = []
    for m in REGENERATION.measurements:
        if m.name in ("i_stat", "i_static_ua", "p_avg", "p_avg_uw"):
            continue  # power is not part of this characterization
        if m.name.endswith("_first"):
            m = dataclasses.replace(m, spice=m.spice.replace("at=18n", f"at={_n(t1)}"))
        elif m.name.endswith("_end"):
            m = dataclasses.replace(m, spice=m.spice.replace("at=55n", "at=58n"))
        elif m.name in REGEN_SPEC_NAMES:
            m = dataclasses.replace(m, limits=None, role="reported")  # no verdict here
        meas.append(m)
    return dataclasses.replace(
        REGENERATION,
        name="clocksupply_regen",
        measurements=tuple(meas),
        description=(
            f"CHARACTERIZATION (issue #173), condition {c.name} ({c.what}): decision time at "
            "50 mV / 1 mV / 0.1 mV overdrive, tau and decision-polarity gates over the "
            "ratified 45-point PVT grid. Not a DR-0002 compliance measurement."),
    )


def offset_bench(c: Condition, n: int = OFFSET_N):
    return dataclasses.replace(
        OFFSET_MC,
        name="clocksupply_offset",
        measurements=tuple(
            dataclasses.replace(m, limits=None, k_sigma=None, role="reported")
            if m.name == "vos_mv" else m for m in OFFSET_MC.measurements),
        monte_carlo={**OFFSET_MC.monte_carlo, "n": n},
        split_by_process=False,
        description=(
            f"CHARACTERIZATION (issue #173), condition {c.name} ({c.what}): whole-latch "
            f"input-referred offset, N = {n} paired draws per PVT point on the reduced "
            "grid. Not a DR-0002 compliance measurement."),
    )


BENCHES = {"regen": regeneration_bench, "offset": offset_bench}
CIRCUITS = {"regen": regeneration_circuit, "offset": offset_circuit}
BASE_BENCH = {"regen": REGENERATION, "offset": OFFSET_MC}


def tag(kind: str) -> str:
    return f"{kind}"


# --------------------------------------------------------------------------- #
# body + request
# --------------------------------------------------------------------------- #


def compose_body(kind: str, c: Condition, osdi_dir: str) -> str:
    base = build_mod.compose_body(BASE_BENCH[kind], osdi_dir)
    lines = base.split("\n")
    end = next(i for i, ln in enumerate(lines) if ln.startswith(build_mod.DUT_END))
    head = lines[: end + 1]
    circuit = CIRCUITS[kind](c)
    head[0] = (f"* clocksupply_{kind} -- klt sim netlist BODY (sim/comparator-clock-supply-"
               f"sensitivity, issue #173) condition={c.name}")
    head[1] = ("* GENERATED by `python3 sim/run_clock_supply_sensitivity.py build` from the issue "
               "#62 bench circuit (sim/kltsim/clocksupply.py) -- do not edit;")
    bench_rel = (build_mod.BENCH_DIR / BASE_BENCH[kind].circuit).relative_to(build_mod.REPO_ROOT)
    for i, ln in enumerate(head):
        if ln.startswith("*   circuit:"):
            head[i] = (f"*   circuit: {bench_rel.as_posix()} + issue #173 rewrites  "
                       f"sha256={build_mod.sha256_bytes(circuit.encode('utf-8'))} (as emitted below)")
    cond_lines = [
        "",
        f"* ---- condition (issue #173): {c.name}: {c.what}",
        f"*      edge {c.tr_n:g} ns, strobe {c.pw_n:g} ns, supply step {c.vstep * 1e3:+g} mV "
        f"({c.timing}), step ramp starts {c.t_s_n():g} ns into each 30 ns period",
        "",
    ]
    return "\n".join(head + cond_lines + [circuit.rstrip("\n"), ""])


def compose_request(kind: str, c: Condition, body_name: str, backend: str = "batch") -> dict:
    bench = BENCHES[kind](c)
    if kind == "offset":
        grid = {"process": [f"mos_{p}_mismatch" for p in PROCESSES],
                "supply_v": {k: list(OFFSET_SUPPLIES_V) for k in bench.supply_keys},
                "temperature_c": list(OFFSET_TEMPERATURES_C)}
    else:
        grid = {"process": [f"mos_{p}" for p in PROCESSES],
                "supply_v": {k: list(SUPPLIES_V) for k in bench.supply_keys},
                "temperature_c": list(TEMPERATURES_C)}
    request = build_mod.compose_request(bench, body_name, backend)
    request["corners"] = grid
    # per-corner logs/decks are not kept: the envelope carries every value and
    # seed, and this keeps the unit inside the evidence-size budget.
    request["options"] = {"timeout_s": bench.timeout_s, "keep_artifacts": False}
    request["_comment"] = [
        f"sg13g2-comparator -- klt sim request, clock/supply sensitivity `{kind}` condition "
        f"`{c.name}` (issue #173).",
        "GENERATED by `python3 sim/run_clock_supply_sensitivity.py build`; the committed copy "
        "is byte-for-byte what was submitted.",
        bench.description,
        "Measurement limits on the DR-0002 spec rows are dropped (characterization); "
        "decision-polarity and range gates are kept.",
    ]
    request["_condition"] = c.metadata()
    return request


def write_inputs(kind: str, c: Condition, out_dir: Path, *, osdi_dir: str = build_mod.BATCH_OSDI_DIR,
                 backend: str = "batch") -> list[tuple[Path, bytes]]:
    body_name = f"{kind}.{c.name}.body.spice"
    files = [(out_dir / body_name, compose_body(kind, c, osdi_dir).encode("utf-8"))]
    req = compose_request(kind, c, body_name, backend)
    files.append((out_dir / f"{kind}.{c.name}.request.json",
                  (json.dumps(req, indent=2) + "\n").encode("utf-8")))
    return files


# --------------------------------------------------------------------------- #
# analysis
# --------------------------------------------------------------------------- #

TOL_V = 1e-6


def _values(corner: dict) -> dict:
    return grade_mod.measurement_index(corner)[0] or {}


def _val(values: dict, name: str):
    m = values.get(name)
    return None if m is None else m.get("value")


def regen_points(env: dict) -> dict[tuple, dict]:
    """Per grid point: decision times, tau and gate verdicts (None where the
    measurement did not evaluate), plus a ``problem`` string when the corner
    is untrusted (errored, or its supply/temperature probe disagrees)."""
    out = {}
    for corner in env.get("corners") or []:
        key = grade_mod._corner_key(corner)
        values = _values(corner)
        problem = None
        if corner.get("status") == "error":
            problem = "corner errored"
        sup = corner.get("supply_v") or {}
        for probe, src in (("vdd_meas", "vsup"), ("vdda_meas", "vsupa")):
            v = _val(values, probe)
            if v is None or src not in sup or abs(v - sup[src]) > TOL_V:
                problem = problem or f"{probe}={v} is not the corner's {src}={sup.get(src)}"
        t = _val(values, "temp_meas")
        if t is None or abs(t - corner["temperature_c"]) > 1e-3:
            problem = problem or f"temp_meas={t} is not the corner's {corner['temperature_c']} C"

        def ok(tag_):
            first, end = _val(values, f"dout_{tag_}_first"), _val(values, f"dout_{tag_}_end")
            if first is None or end is None:
                return None
            return bool(first < 0.1 and end > 0.9)

        out[key] = {
            "td50_ns": _val(values, "td_od50_ns"), "td1_ns": _val(values, "td_od1_ns"),
            "td01_ns": _val(values, "td_od01_ns"), "tau_ps": _val(values, "tau_ps"),
            "ok50": ok("od50"), "ok1": ok("od1"), "ok01": ok("od01"),
            "first50": _val(values, "dout_od50_first"), "end50": _val(values, "dout_od50_end"),
            "first1": _val(values, "dout_od1_first"), "end1": _val(values, "dout_od1_end"),
            "problem": problem,
        }
    return out


def offset_samples(env: dict) -> dict[tuple, dict[int, dict]]:
    """Per grid point: sample_index -> {vos_mv, seed, clipped, problem}."""
    out: dict[tuple, dict[int, dict]] = {}
    for corner in env.get("corners") or []:
        mc = corner.get("monte_carlo")
        if mc is None:
            continue
        key = grade_mod._corner_key(corner)
        values = _values(corner)
        lc, vos = _val(values, "lowcount"), _val(values, "vos_mv")
        problem = None
        if corner.get("status") == "error":
            problem = "sample errored"
        elif lc is None or vos is None:
            problem = "lowcount/vos_mv not reported"
        v = _val(values, "vdd_meas")
        if problem is None and (v is None or abs(v - corner["supply_v"]["vsup"]) > TOL_V):
            problem = f"vdd_meas={v} is not the corner supply"
        clipped = lc is not None and not (0.5 <= lc <= 32.5)
        out.setdefault(key, {})[mc["sample_index"]] = {
            "vos_mv": vos, "seed": mc.get("seed"), "lowcount": lc,
            "clipped": bool(clipped), "problem": problem,
        }
    return out


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def _sd(xs):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def offset_pair(cond: dict[tuple, dict[int, dict]], base: dict[tuple, dict[int, dict]]) -> dict:
    """Paired statistics of one condition against ``base`` over all shared
    (point, sample) pairs. A pair is used only if both draws share a seed and
    both are trusted and un-clipped."""
    deltas, per_point, seed_mismatch, dropped = [], {}, 0, 0
    cv, bv = [], []
    for key in sorted(set(cond) & set(base), key=str):
        d = []
        for k in sorted(set(cond[key]) & set(base[key])):
            a, b = cond[key][k], base[key][k]
            if a["seed"] != b["seed"]:
                seed_mismatch += 1
                continue
            if a["problem"] or b["problem"] or a["clipped"] or b["clipped"]:
                dropped += 1
                continue
            d.append(a["vos_mv"] - b["vos_mv"])
            cv.append((key, a["vos_mv"]))
            bv.append((key, b["vos_mv"]))
        per_point[key] = {"n": len(d), "mean": _mean(d), "sem": (_sd(d) / math.sqrt(len(d)))
                          if len(d) > 1 else None, "changed": sum(1 for x in d if abs(x) > STEP_MV / 2)}
        deltas += d
    n = len(deltas)
    sd = _sd(deltas)
    return {
        "n_pairs": n, "dropped": dropped, "seed_mismatch": seed_mismatch,
        "mean_shift_mv": _mean(deltas), "sd_delta_mv": sd,
        "sem_mv": (sd / math.sqrt(n)) if sd is not None else None,
        "changed": sum(1 for x in deltas if abs(x) > STEP_MV / 2),
        "pooled_sigma_mv": _pooled_sigma(cv), "pooled_sigma_base_mv": _pooled_sigma(bv),
        "per_point": per_point,
    }


def _pooled_sigma(pairs: list[tuple]) -> float | None:
    """RMS of draws about their own PVT point's mean, pooled over points with
    the degrees-of-freedom correction (N_total - n_points), minus the
    staircase quantization step^2/12. A pooled within-point spread, NOT a
    single-point sigma."""
    groups: dict[tuple, list[float]] = {}
    for key, v in pairs:
        groups.setdefault(key, []).append(v)
    ss = sum(sum((v - sum(vs) / len(vs)) ** 2 for v in vs) for vs in groups.values())
    dof = sum(len(vs) for vs in groups.values()) - len(groups)
    if dof <= 0:
        return None
    return math.sqrt(max(ss / dof - STEP_MV ** 2 / 12.0, 0.0))


def regen_summary(points: dict[tuple, dict], base: dict[tuple, dict] | None) -> dict:
    def rng(name):
        vals = [(k, p[name]) for k, p in points.items() if p[name] is not None and not p["problem"]]
        if not vals:
            return None
        lo, hi = min(vals, key=lambda kv: kv[1]), max(vals, key=lambda kv: kv[1])
        return {"min": lo[1], "max": hi[1], "binding": grade_mod.key_label(hi[0]),
                "mean": sum(v for _, v in vals) / len(vals), "n": len(vals)}

    out = {
        "points": len(points),
        "untrusted": sorted(grade_mod.key_label(k) for k, p in points.items() if p["problem"]),
        "td50_ns": rng("td50_ns"), "td1_ns": rng("td1_ns"), "td01_ns": rng("td01_ns"),
        "tau_ps": rng("tau_ps"),
        "correct50": sum(1 for p in points.values() if p["ok50"] and not p["problem"]),
        "correct1": sum(1 for p in points.values() if p["ok1"] and not p["problem"]),
        "correct01": sum(1 for p in points.values() if p["ok01"] and not p["problem"]),
        "td50_within_1p5ns": sum(1 for p in points.values()
                                 if p["td50_ns"] is not None and p["td50_ns"] <= 1.5
                                 and not p["problem"]),
        "failed_1mv_points": sorted(grade_mod.key_label(k) for k, p in points.items()
                                    if not p["ok1"] and not p["problem"]),
    }
    if base is not None:
        d50, d1 = [], []
        for k, p in points.items():
            b = base.get(k)
            if not b or p["problem"] or b["problem"]:
                continue
            if p["td50_ns"] is not None and b["td50_ns"] is not None:
                d50.append((k, p["td50_ns"] - b["td50_ns"]))
            if p["td1_ns"] is not None and b["td1_ns"] is not None:
                d1.append((k, p["td1_ns"] - b["td1_ns"]))
        for name, d in (("d_td50_ns", d50), ("d_td1_ns", d1)):
            if d:
                lo, hi = min(d, key=lambda kv: kv[1]), max(d, key=lambda kv: kv[1])
                out[name] = {"min": lo[1], "max": hi[1], "mean": sum(v for _, v in d) / len(d),
                             "max_at": grade_mod.key_label(hi[0]), "n": len(d)}
            else:
                out[name] = None
    return out
