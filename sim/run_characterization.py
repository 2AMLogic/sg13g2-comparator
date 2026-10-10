#!/usr/bin/env python3
"""Entry point for the issue #64 T1 item 8 characterization report.

See sim/kltsim/characterization.py and sim/README.md ("Characterization
report"). Normally invoked through ``sim/characterize.sh report``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kltsim.characterization import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
