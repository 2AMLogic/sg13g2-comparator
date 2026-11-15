"""The chain-loading loop shared by the declared-contract loaders (issue #452).

``kltsim.grade.load_campaign`` is an indexed source of the committed item 8
characterization report, so a per-campaign contract deviation cannot edit it
(``sim/README.md`` "Characterization report (T1 item 8)"). ``declared_n`` and
``bias_probes`` instead declare their deviation by loading the campaign
through this module, which carries the loop once; the only difference between
the declaring loaders is the bench swap — a ``(name, bench) -> bench``
callable applied to each bench before its evidence is loaded. Every other
rule is ``grade``'s, and ``CampaignChainTests`` and its per-loader subclasses
(``sim/kltsim/tests/test_grade.py``) keep all three loaders' chain-check
detection surface in step, so a hardening of one cannot silently miss the
others.

The declared-contract path deliberately does not support the reduced-grid
call (issue #122): ``grade.load_campaign``'s ``corners`` parameter is not
forwarded here, so a declared campaign's saved requests are always compared
against the bench's full contract grid exactly. No declared-contract caller
passes a reduced grid today (issue #452); adding the capability is a
separate, reviewed change.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from . import build as build_mod
from . import grade
from .benches import BENCHES, Bench


def load_declared_campaign(campaign_dir: Path,
                           bench_swap: Callable[[str, Bench], Bench],
                           bench_names: tuple[str, ...] | None = None
                           ) -> dict[str, grade.BenchEvidence]:
    """``grade.load_campaign``'s chain-loading loop, with ``bench_swap``
    declaring the per-campaign contract deviation (issue #452)."""
    benches: dict[str, grade.BenchEvidence] = {}
    for name, bench in BENCHES.items():
        if bench_names is not None and name not in bench_names:
            continue
        bench = bench_swap(name, bench)
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
