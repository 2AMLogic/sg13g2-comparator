"""PVT corner-simulation harness for sg13g2-comparator.

Ported from ``2AMLogic/gf180-comparator``'s ``sim/harness/`` (itself ported
from ``2AMLogic/gf180-sar-adc``), per this repo's own ``CLAUDE.md`` ("two-PDK
twin with sg13g2-comparator ... keep benches structurally identical") and
``spec/porting-plan.md`` next steps 3-4. See ``sim/harness/README.md`` for
what transferred unchanged, what was adapted for IHP SG13G2, and what was
deliberately left behind.
"""

__all__ = [
    "cli",
    "corners",
    "dut",
    "pdk",
    "report",
    "runner",
    "testbench",
    "toolchain",
]
