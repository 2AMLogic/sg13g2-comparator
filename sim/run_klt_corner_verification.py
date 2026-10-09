#!/usr/bin/env python3
"""Entry point for the issue #62 klt sim corner-verification campaign.

See sim/kltsim/cli.py (and sim/klt-corner-verification/README.md) for usage.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kltsim.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
