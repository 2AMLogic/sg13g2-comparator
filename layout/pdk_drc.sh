#!/usr/bin/env bash
# Supplemental check of the committed layout against IHP's own DRC deck
# (issue #180). Separate from layout/run_flow.sh: that flow needs only the
# pinned klt + klayout wheel; this one also needs the PDK checkout and a real
# KLayout executable, so it is not part of CI.
#
#   layout/pdk_drc.sh            run, write layout/comparator/pdk_drc_report.json
#   layout/pdk_drc.sh --check    require the committed report to reproduce
#   (extra flags go to layout/comparator/pdk_drc.py: --strict, --no-controls,
#    --pdk DIR, --klayout BIN, -o FILE)
#
# Prerequisites (any missing one gives status `unavailable`, exit 3, and the
# committed report is left alone; it is never reported as clean):
#   * uv (uvx) -- fetches the klayout Python module into an isolated cache
#   * IHP-Open-PDK v0.3.0 (sim/pdk.json) at --pdk, $IHP_PDK_DIR,
#     $PDK_ROOT/ihp-sg13g2 or ~/share/pdk/ihp-sg13g2; its deck tree hash is
#     verified against the pin in pdk_drc.py
#   * a KLayout >= 0.29.11 *executable* (the deck is Ruby): $KLAYOUT_BIN or
#     `klayout` on PATH. The pip `klayout` wheel is a module only.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v uvx >/dev/null || { echo "UNAVAILABLE (uv_missing): uvx not found" >&2; exit 3; }
exec uvx --quiet --from "klayout==0.30.12" python -I "${HERE}/comparator/pdk_drc.py" "$@"
