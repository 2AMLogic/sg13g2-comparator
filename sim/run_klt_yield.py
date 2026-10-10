#!/usr/bin/env python3
"""Entry point for the issue #63 `klt yield` evidence workflow.

See sim/kltsim/yield_reports.py and sim/klt-yield/README.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kltsim.yield_reports import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
