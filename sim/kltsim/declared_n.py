"""Grading a campaign whose offset draw count is explicitly declared (issue #167).

``kltsim.grade`` carries the historical contract (offset N = 60) and is itself
an indexed source of the committed item 8 characterization report, so the
declared-N variant lives here and calls into ``grade`` unchanged: the saved
offset requests must carry exactly the declared N (any other value is a chain
problem that rejects the bench's evidence), the offset row's ``expected_n`` is
replaced by the same declared N, and every other rule is ``grade``'s.

``offset_n=None`` is the historical campaign and returns what ``grade`` itself
returns.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from . import build as build_mod
from . import grade
from .benches import BENCHES, offset_mc_with_n, validate_offset_n


def with_offset_n(rows_spec: dict, offset_n: int | None) -> dict:
    """``rows_spec`` with the offset row's ratified ``expected_n`` replaced by an
    explicitly declared campaign N. ``None`` returns it untouched."""
    if offset_n is None:
        return rows_spec
    validate_offset_n(offset_n)
    spec = copy.deepcopy(rows_spec)
    for row in spec["rows"]:
        ev = row["evidence"]
        if ev.get("bench") == "offset_mc" and ev.get("expected_n"):
            ev["expected_n"] = int(offset_n)
    return spec


def load_campaign(campaign_dir: Path, offset_n: int | None = None,
                  bench_names: tuple[str, ...] | None = None) -> dict[str, grade.BenchEvidence]:
    """``grade.load_campaign`` with the offset_mc request contract at ``offset_n``."""
    if offset_n is None:
        return grade.load_campaign(campaign_dir, bench_names=bench_names)
    validate_offset_n(offset_n)
    benches: dict[str, grade.BenchEvidence] = {}
    for name, bench in BENCHES.items():
        if bench_names is not None and name not in bench_names:
            continue
        if name == "offset_mc":
            bench = offset_mc_with_n(offset_n)
        body_path = campaign_dir / f"{name}.body.spice"
        envelopes: list[tuple[str, dict]] = []
        shas: dict[str, str] = {}
        problems: list[str] = []
        checked: dict[str, dict] = {}
        for tag in build_mod.part_tags(bench):
            path = campaign_dir / f"{tag}.envelope.json"
            if not path.is_file():
                continue
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
            checked[tag] = grade.check_chain(bench, tag, campaign_dir, shas[tag], problems)
        benches[name] = grade.BenchEvidence(
            name=name, envelopes=envelopes,
            body_text=body_path.read_text(encoding="utf-8") if body_path.is_file() else None,
            envelope_files=shas, chain_problems=problems, chain_checked=checked)
    return benches


def grade_campaign(campaign_dir: Path, offset_n: int | None = None) -> dict:
    """``grade.grade_campaign`` for a declared offset N; the result records it."""
    if offset_n is None:
        return grade.grade_campaign(campaign_dir)
    rows_spec = with_offset_n(
        json.loads((build_mod.EXPERIMENT_DIR / "rows.json").read_text(encoding="utf-8")), offset_n)
    result = grade.grade(rows_spec, load_campaign(campaign_dir, offset_n), grade.load_dut_reference())
    result["campaign"] = campaign_dir.name
    result["declared_offset_n"] = int(offset_n)
    return result
