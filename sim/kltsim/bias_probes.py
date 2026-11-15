"""Grading a swept-bias campaign whose regeneration requests carry the issue
#80 bias probes (issue #440).

``kltsim.grade`` carries the bench-contract requests exactly as ``build``
composes them, and is itself an indexed source of the committed item 8
characterization report, so -- exactly as the declared offset draw count
before it (issue #167, ``declared_n.py``) -- the declared superset lives here
and calls into ``grade`` unchanged: the swept sub-campaigns' saved
``regeneration`` requests must carry exactly the ``BIAS_PROBES`` superset
``build --bias-probes`` composes via ``benches.regeneration_with_bias_probes``
(any other extra measurement, or a missing probe, is a chain problem that
rejects the bench's evidence), and every other rule is ``grade``'s. The issue
#62 campaign, deliberately built without the probes, stays on ``grade``'s
undeclared contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import build as build_mod
from . import grade
from .benches import BENCHES, regeneration_with_bias_probes


def load_campaign(campaign_dir: Path,
                  bench_names: tuple[str, ...] | None = None) -> dict[str, grade.BenchEvidence]:
    """``grade.load_campaign`` with the ``regeneration`` request contract at
    the declared ``BIAS_PROBES`` superset, compared exactly."""
    benches: dict[str, grade.BenchEvidence] = {}
    for name, bench in BENCHES.items():
        if bench_names is not None and name not in bench_names:
            continue
        if name == "regeneration":
            bench = regeneration_with_bias_probes(bench)
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


def grade_campaign(campaign_dir: Path) -> dict:
    """``grade.grade_campaign`` for a swept-bias campaign (its regeneration
    requests declare the bias probes; everything else is ``grade``'s)."""
    rows_spec = json.loads((build_mod.EXPERIMENT_DIR / "rows.json").read_text(encoding="utf-8"))
    result = grade.grade(rows_spec, load_campaign(campaign_dir), grade.load_dut_reference())
    result["campaign"] = campaign_dir.name
    return result
