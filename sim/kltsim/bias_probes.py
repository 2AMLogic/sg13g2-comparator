"""Grading a swept-bias campaign whose regeneration requests carry the issue
#80 bias probes (issue #440).

``kltsim.grade`` carries the bench-contract requests exactly as ``build``
composes them, and is itself an indexed source of the committed item 8
characterization report, so -- exactly as the declared offset draw count
before it (issue #167, ``declared_n.py``) -- the declared superset lives here
and loads campaigns through the shared declared-contract loop
(``declared_contract.py``, issue #452) with ``grade``'s chain checks
unchanged: the swept sub-campaigns' saved
``regeneration`` requests must carry exactly the ``BIAS_PROBES`` superset
``build --bias-probes`` composes via ``benches.regeneration_with_bias_probes``
(any other extra measurement, or a missing probe, is a chain problem that
rejects the bench's evidence), and every other rule is ``grade``'s. The issue
#62 campaign, deliberately built without the probes, stays on ``grade``'s
undeclared contract.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import build as build_mod
from . import declared_contract
from . import grade
from .benches import regeneration_with_bias_probes


def load_campaign(campaign_dir: Path,
                  bench_names: tuple[str, ...] | None = None) -> dict[str, grade.BenchEvidence]:
    """``grade.load_campaign`` with the ``regeneration`` request contract at
    the declared ``BIAS_PROBES`` superset, compared exactly."""
    return declared_contract.load_declared_campaign(
        campaign_dir,
        lambda name, bench: regeneration_with_bias_probes(bench) if name == "regeneration" else bench,
        bench_names=bench_names)


def grade_campaign(campaign_dir: Path) -> dict:
    """``grade.grade_campaign`` for a swept-bias campaign (its regeneration
    requests declare the bias probes; everything else is ``grade``'s)."""
    rows_spec = json.loads((build_mod.EXPERIMENT_DIR / "rows.json").read_text(encoding="utf-8"))
    result = grade.grade(rows_spec, load_campaign(campaign_dir), grade.load_dut_reference())
    result["campaign"] = campaign_dir.name
    return result
