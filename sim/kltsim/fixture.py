"""Known-charge fixture checks for the Q_kick instrument (issue #78).

Two independent things live here, both stdlib only:

* ``check_envelope``: compare the engine's measured value for every fixture
  case against the analytic charge in ``benches.FIXTURE_CASES``;
* ``reference_response``: an ngspice-free reference of the instrument's
  measurement semantics (29 ns reference, 30 ... 45 ns window) applied to the
  PWL currents parsed out of the fixture deck, used by the unit test so a
  window/offset/sign error in either the deck or the expectations fails
  without needing a simulator.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import build as build_mod
from .benches import FIXTURE_CASES, FIXTURE_TOL_FC, Bench

REF_NS = 29.0
WIN_LO_NS = 30.0
WIN_HI_NS = 45.0
END_NS = 45.0


def _si(text: str) -> float:
    mult = {"n": 1e-9, "u": 1e-6, "p": 1e-12, "f": 1e-15}
    if text and text[-1] in mult:
        return float(text[:-1]) * mult[text[-1]]
    return float(text)


def parse_pwl_sources(circuit_text: str) -> dict[str, list[tuple[float, float]]]:
    """``{case: [(t_s, i_A), ...]}`` summed over every ``Iinj<case>*`` card,
    keyed by case letter, returned as a merged list of breakpoints per card
    (cards are returned separately as ``case`` + index when several)."""
    out: dict[str, list[list[tuple[float, float]]]] = {}
    for line in circuit_text.splitlines():
        m = re.match(r"\s*Iinj([a-z])\d*\s+\S+\s+\S+\s+pwl\((.*)\)\s*$", line, re.I)
        if not m:
            continue
        nums = [_si(tok) for tok in m.group(2).split()]
        out.setdefault(m.group(1), []).append(list(zip(nums[0::2], nums[1::2])))
    return {case: cards for case, cards in out.items()}  # type: ignore[return-value]


def _current(cards: list[list[tuple[float, float]]], t: float) -> float:
    total = 0.0
    for pts in cards:
        if t <= pts[0][0]:
            total += pts[0][1]
        elif t >= pts[-1][0]:
            total += pts[-1][1]
        else:
            for (t0, i0), (t1, i1) in zip(pts, pts[1:]):
                if t0 <= t <= t1:
                    total += i0 + (i1 - i0) * (t - t0) / (t1 - t0) if t1 > t0 else i1
                    break
    return total


def reference_response(cards, dt_s: float = 1e-12, ref_ns: float = REF_NS,
                       win_lo_ns: float = WIN_LO_NS, win_hi_ns: float = WIN_HI_NS) -> dict:
    """Integrate the injected current and apply the instrument's measure
    semantics. Returned charges are in fC; sign is + for charge pushed into
    the pin node (the deck's ``Iinj 0 pin`` direction)."""
    n = int(round(70e-9 / dt_s))
    q = 0.0
    qs: list[tuple[float, float]] = [(0.0, 0.0)]
    prev = _current(cards, 0.0)
    for k in range(1, n + 1):
        t = k * dt_s
        cur = _current(cards, t)
        q += 0.5 * (prev + cur) * dt_s
        prev = cur
        qs.append((t, q))

    def at(ns: float) -> float:
        return qs[int(round(ns * 1e-9 / dt_s))][1]

    ref = at(ref_ns)
    window = [qv - ref for t, qv in qs if win_lo_ns * 1e-9 <= t <= win_hi_ns * 1e-9]
    pos, neg = max(window), min(window)
    return {
        "peak_fc": max(abs(pos), abs(neg)) * 1e15,
        "pos_fc": pos * 1e15,
        "neg_fc": neg * 1e15,
        "net_fc": (at(win_hi_ns) - ref) * 1e15,
    }


def end_window_estimator_fc(net_fc: float) -> float:
    """The deliberately wrong estimator: |q(45 ns) - q(29 ns)|."""
    return abs(net_fc)


def check_envelope(bench: Bench, envelope: dict) -> dict:
    corners = envelope.get("corners") or []
    if len(corners) != 1:
        return {"ok": False, "problem": f"expected one fixture unit, got {len(corners)}", "cases": []}
    values = {m["name"]: m.get("value") for m in corners[0].get("measurements", [])}
    cases = []
    ok = True
    for case, spec in FIXTURE_CASES.items():
        peak = values.get(f"qkick_{case}_fc")
        net = values.get(f"qnet_{case}_fc")
        pos = values.get(f"qpos_{case}_fc")
        neg = values.get(f"qneg_{case}_fc")
        if None in (peak, net, pos, neg):
            cases.append({"case": case, "what": spec["what"], "ok": False, "problem": "measurement missing"})
            ok = False
            continue
        dominant = pos if abs(pos) >= abs(neg) else neg
        sign = 1 if dominant > 0 else -1
        checks = {
            "peak": abs(peak - spec["q_fc"]) <= FIXTURE_TOL_FC,
            "net": abs(net - spec["net_fc"]) <= FIXTURE_TOL_FC,
            "sign": sign == spec["sign"],
        }
        naive = end_window_estimator_fc(net)
        naive_ok = abs(naive - spec["q_fc"]) <= FIXTURE_TOL_FC
        cases.append({
            "case": case, "what": spec["what"],
            "expected_peak_fc": spec["q_fc"], "measured_peak_fc": peak,
            "expected_net_fc": spec["net_fc"], "measured_net_fc": net,
            "measured_pos_fc": pos, "measured_neg_fc": neg,
            "expected_sign": spec["sign"], "measured_sign": sign,
            "end_window_estimator_fc": naive, "end_window_estimator_ok": naive_ok,
            "checks": checks, "ok": all(checks.values()),
        })
        if case == "d":
            cases[-1]["vc_estimator_fc"] = values.get("vcest_d_fc")
        ok = ok and all(checks.values())
    # Negative control: the end-of-window estimator must FAIL the bipolar case.
    bipolar = next((c for c in cases if c["case"] == "c" and "end_window_estimator_ok" in c), None)
    neg_control = bipolar is not None and not bipolar["end_window_estimator_ok"]
    return {"ok": ok and neg_control, "tolerance_fc": FIXTURE_TOL_FC,
            "end_window_estimator_fails_bipolar": neg_control,
            "corner_id": corners[0].get("corner_id"), "cases": cases}


def render_markdown(report: dict) -> str:
    lines = [
        "| case | injected | expected Q (fC) | measured Q (fC) | expected net (fC) | measured net (fC) | sign | end-window estimator (fC) | ok |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in report.get("cases", []):
        if "measured_peak_fc" not in c:
            lines.append(f"| {c['case']} | {c['what']} | - | - | - | - | - | - | {c.get('problem')} |")
            continue
        lines.append(
            f"| {c['case']} | {c['what']} | {c['expected_peak_fc']:.3f} | {c['measured_peak_fc']:.4f} "
            f"| {c['expected_net_fc']:.3f} | {c['measured_net_fc']:.4f} "
            f"| {'+' if c['measured_sign'] > 0 else '-'} (exp {'+' if c['expected_sign'] > 0 else '-'}) "
            f"| {c['end_window_estimator_fc']:.4f} | {'PASS' if c['ok'] else 'FAIL'} |")
    lines.append("")
    d = next((c for c in report.get("cases", []) if c["case"] == "d"), None)
    if d and d.get("vc_estimator_fc") is not None:
        lines.append(f"Case d restoration: peak node volts x C_in reads {d['vc_estimator_fc']:.4f} fC "
                     f"for the {d['expected_peak_fc']:.1f} fC actually delivered; the instrument reads "
                     f"{d['measured_peak_fc']:.4f} fC.")
        lines.append("")
    lines.append(f"Tolerance {report.get('tolerance_fc')} fC. End-window estimator fails the bipolar case "
                 f"(negative control): {report.get('end_window_estimator_fails_bipolar')}. "
                 f"Overall: {'PASS' if report.get('ok') else 'FAIL'}.")
    return "\n".join(lines) + "\n"


def fixture_circuit_text() -> str:
    return Path(build_mod.BENCH_DIR / "kickback_fixture.circuit.spice").read_text(encoding="utf-8")
