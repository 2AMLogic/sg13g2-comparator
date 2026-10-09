#!/usr/bin/env bash
# One-command layout flow for the comparator (issue #58, T1 item 2).
#
#   layout/run_flow.sh            regenerate layout/comparator/comparator.gds,
#                                 then run every check below against it
#   layout/run_flow.sh --check    leave the committed GDS alone: regenerate into
#                                 a temp dir and require it to be byte-identical
#                                 to the committed one, then run the checks
#
# Stages:
#   1. generate      layout/comparator/generate.py -> comparator.gds. The
#                    generator first reconciles its device table with the
#                    `.subckt comparator` block of design/comparator.spice
#                    (24 devices, LV flavour, nets, W, L, pins, matched-pair
#                    geometry) and refuses to draw on any disagreement.
#   2. reproduce     generate a second time from scratch into a temp dir;
#                    the two streams must be byte-identical (`cmp`).
#   3. stream        layout/comparator/check_stream.py: one top cell named
#                    `comparator`, non-empty, all eight ports pinned on Metal3,
#                    no host paths, boxes only.
#   4. lvs           `klt extract --deck sg13g2` + `klt lvs` against the
#                    comparator subcircuit cut from design/comparator.spice.
#                    Writes the COMMITTED lvs_extracted.spice,
#                    lvs_reference.spice, lvs_request.json and lvs_report.json
#                    under layout/comparator/ (issue #60, T1 item 4); with
#                    --check, requires a fresh re-derivation to be
#                    byte-identical to the committed files, `klt lvs --check`
#                    and a fresh run of the committed request to reproduce the
#                    committed envelope, and the verdict to be a complete match.
#   5. controls      two mutated references (one topology, one W) that MUST
#                    mismatch, so a `match` in stage 4 is known to mean
#                    something. Temp dir only.
#   6. drc           `klt drc --deck sg13g2 --top comparator` on the GDS, run
#                    from the repo root with the repo-relative path so the
#                    envelope records no host path. Writes the COMMITTED
#                    layout/comparator/drc_report.json (issue #59, T1 item 3);
#                    with --check, instead requires the committed envelope to
#                    be fresh (`klt drc --check`) and `status: clean`. The
#                    deck's coverage gaps are printed, and are quoted in
#                    manifests/README.md.
#
# Tooling: everything runs on the klayout-tools build this repo pins (see
# manifests/README.md and .github/workflows/ci.yml), and on the KLayout
# Python module that build installs; no PDK install is read. By default the
# pinned build is fetched into an isolated uv cache via `uvx`; set
# KLT_NATIVE=1 to use `python3`/`klt` from PATH instead (CI does, after
# `pip install`-ing the same pin).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/.." && pwd)"
CELL_DIR="${HERE}/comparator"
GDS="${CELL_DIR}/comparator.gds"
TOP="comparator"
PORTS="vinp,vinn,clk,vbias,dout,doutb,vdd,vss"

KLT_PIN="e8ca621a6961879cec1af60cc932c3b3d58ddcaa"
KLAYOUT_PIN="0.30.10"  # the KLayout this klt build was tested against

MODE="run"
case "${1:-}" in
  "") ;;
  --check) MODE="check" ;;
  -h|--help) sed -n '2,52p' "${BASH_SOURCE[0]}"; exit 0 ;;
  *) echo "usage: $0 [--check]" >&2; exit 2 ;;
esac

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

if [[ "${KLT_NATIVE:-0}" == "1" ]]; then
  PY=(python3)
  KLT=(klt)
else
  command -v uvx >/dev/null || {
    echo "uvx not found: install uv, or set KLT_NATIVE=1 with the pinned klt on PATH" >&2
    exit 1
  }
  SRC="klayout-tools @ git+https://github.com/2AMLogic/klayout-tools@${KLT_PIN}"
  PY=(uvx --quiet --with "klayout==${KLAYOUT_PIN}" --from "${SRC}" python)
  KLT=(uvx --quiet --with "klayout==${KLAYOUT_PIN}" --from "${SRC}" klt)
fi

say() { printf '\n=== %s\n' "$*"; }

say "tools"
echo "  klt: $("${KLT[@]}" --version)"
echo "  klayout: $("${PY[@]}" -c 'import klayout.db as k; print(k.__version__)' 2>/dev/null || echo unknown)"

say "1. generate"
if [[ "${MODE}" == "check" ]]; then
  "${PY[@]}" "${CELL_DIR}/generate.py" -o "${WORK}/first.gds"
  cmp "${WORK}/first.gds" "${GDS}" || {
    echo "  FAIL: regenerated stream differs from the committed ${GDS#"${REPO}/"}" >&2
    echo "        run layout/run_flow.sh (no --check) and commit the result" >&2
    exit 1
  }
  echo "  committed ${GDS#"${REPO}/"} reproduces byte-for-byte"
  TARGET="${GDS}"
else
  "${PY[@]}" "${CELL_DIR}/generate.py" -o "${GDS}"
  TARGET="${GDS}"
fi

say "2. reproduce"
"${PY[@]}" "${CELL_DIR}/generate.py" -o "${WORK}/second.gds" > /dev/null
cmp "${WORK}/second.gds" "${TARGET}"
echo "  two independent runs are byte-identical ($(sha256sum "${TARGET}" | cut -c1-16)...)"

say "3. stream"
"${PY[@]}" "${CELL_DIR}/check_stream.py" "${TARGET}"

say "4. lvs (klt extract + klt lvs; T1 item 4 evidence)"
# Committed inputs/outputs, all under layout/comparator/ and all derived:
#   lvs_extracted.spice  klt extract of comparator.gds (deck sg13g2, 8 pins)
#   lvs_reference.spice  the `.subckt comparator` block cut verbatim out of
#                        design/comparator.spice (never edited by hand)
#   lvs_request.json     the klt.lvs.request/1 document; its paths are
#                        relative to the request file itself, so the committed
#                        request and the envelope's echoed paths are portable
#   lvs_report.json      the klt lvs envelope (the citation target)
# The reference is cut out because `klt lvs` crashes when the reference file
# also holds subcircuits that instantiate the selected top (here
# comparator_dut, comparator_dut_latch): 2AMLogic/klayout-tools#2852.
# `klt lvs --check` only re-hashes the extracted and reference netlists, so
# this flow additionally proves the GDS -> extraction and
# design/comparator.spice -> reference links itself (cmp against a fresh
# derivation), which --check alone cannot see.
LVS_FILES=(lvs_extracted.spice lvs_reference.spice lvs_request.json)
REL_CELL="${CELL_DIR#"${REPO}/"}"
REL_GDS="${GDS#"${REPO}/"}"
cd "${REPO}"  # klt records the input path as given: keep it repo-relative

derive_lvs_inputs() {  # <outdir>
  local out="$1"
  "${KLT[@]}" extract --deck sg13g2 --top "${TOP}" --pins "${PORTS}" \
    -o "${out}/lvs_extracted.spice" --format json "${REL_GDS}" > "${out}/extract.json"
  awk '/^\.subckt comparator /{on=1} on{print} on && /^\.ends/{exit}' \
    design/comparator.spice > "${out}/lvs_reference.spice"
  [[ -s "${out}/lvs_reference.spice" ]] || {
    echo "  FAIL: no .subckt comparator block in design/comparator.spice" >&2; exit 1; }
  cat > "${out}/lvs_request.json" <<EOF
{"schema": "klt.lvs.request/1", "engine": "klayout",
 "layout": {"netlist": "lvs_extracted.spice", "top": "${TOP}"},
 "reference": {"netlist": "lvs_reference.spice", "top": "${TOP}",
               "form": "subckt-call", "deck": "sg13g2"},
 "options": {"combine_devices": true}}
EOF
}

# Judge a klt lvs envelope: exits 0 only for a complete, portable match.
# With a label as 2nd argument it is a negative control instead: exits 0
# only for a well-formed envelope whose status is not `match`.
verdict() {  # <report> [control-label]
  "${PY[@]}" - "$1" "${2:-}" <<'PY'
import json, pathlib, sys
path, label = sys.argv[1], sys.argv[2]
raw = pathlib.Path(path).read_text() if pathlib.Path(path).exists() else ""
if not raw.strip():
    print(f"  FAIL: {path}: empty or missing lvs report", file=sys.stderr); sys.exit(1)
d = json.loads(raw)
if "error" in d or "status" not in d:
    print(f"  FAIL: error/odd envelope: {str(d)[:300]}", file=sys.stderr); sys.exit(1)
if label:
    cats = sorted({m["category"] for m in d.get("mismatches", []) if m["severity"] == "error"})
    print(f"  {label}: status={d['status']} {cats}")
    sys.exit(0 if d["status"] != "match" and cats else 1)
print(f"  engine: {d['engine']} {d['environment']['engine_version']}  status: {d['status']}")
print(f"  counts: {d['counts']}")
pc = d["power_connectivity"]
print(f"  power_connectivity: {pc['status']} -- {pc['reason']}")
print(f"  body_verification: {d['body_verification']['status']}")
print(f"  mismatches/warnings: {d['mismatch_count']} (errors {d['error_count']})")
for m in d.get("mismatches", []):
    print(f"    {m['severity']}: {m['category']}: {m['description']}")
bad = []
if d["status"] != "match": bad.append(f"status {d['status']}")
if d["engine"] != "klayout": bad.append("engine not klayout")
if d["power_connectivity"]["status"] == "mismatch": bad.append("power_connectivity mismatch")
if d["mismatch_count"] or d["error_count"]: bad.append("mismatches present")
c = d["counts"]
for k, n in (("pins", 8), ("devices", 24)):
    if not (c[k]["layout"] == c[k]["reference"] == c[k]["matched"] == n):
        bad.append(f"{k} coverage {c[k]} != {n}")
if c["nets"]["layout"] != c["nets"]["matched"] or c["nets"]["reference"] != c["nets"]["matched"]:
    bad.append(f"nets not all matched {c['nets']}")
nc = {(x["layout"], x["reference"]) for x in d["net_correspondence"] if x["pin"]}
want = {(p.upper(), p.upper()) for p in "vinp vinn clk vbias dout doutb vdd vss".split()}
if nc != want: bad.append(f"pin correspondence {sorted(nc)}")
if d["layout"].startswith("/") or d["reference"].startswith("/") or "/home/" in raw:
    bad.append("host-absolute path in envelope")
if bad:
    print("  FAIL: " + "; ".join(bad), file=sys.stderr); sys.exit(1)
print("  verdict: match, all 8 pins (incl. vdd/vss and independent vbias), 24 devices, all nets")
PY
}

REPORT_LVS="${REL_CELL}/lvs_report.json"
if [[ "${MODE}" == "check" ]]; then
  mkdir "${WORK}/fresh"
  derive_lvs_inputs "${WORK}/fresh"
  for f in "${LVS_FILES[@]}"; do
    cmp "${WORK}/fresh/${f}" "${REL_CELL}/${f}" || {
      echo "  FAIL: committed ${REL_CELL}/${f} is stale (GDS, design/comparator.spice or request changed)" >&2
      echo "        run layout/run_flow.sh (no --check) and commit the result" >&2
      exit 1; }
  done
  echo "  committed extraction, reference, request reproduce byte-for-byte"
  # Cheap `klt lvs --check`: re-hash the netlists the envelope names against
  # its recorded layout_sha256/reference_sha256. The envelope echoes those
  # paths relative to the request (= report) directory and --check resolves
  # them against the cwd, so run it there. (`--rerun` is not used: it cannot
  # reconstruct reference.form from the envelope and rejects the
  # subckt-call reference; see the tool-gap issue cited in layout/README.md.)
  (cd "${REL_CELL}" && "${KLT[@]}" lvs --check lvs_report.json > /dev/null) || {
    echo "  FAIL: klt lvs --check: ${REPORT_LVS} is stale or drifted from its netlists" >&2; exit 1; }
  echo "  klt lvs --check: ${REPORT_LVS} matches the hashes of its netlists"
  # Replace --rerun with our own: the committed envelope must equal a fresh
  # run of the committed request (modulo tool-build version stamps).
  "${KLT[@]}" lvs "${REL_CELL}/lvs_request.json" --format json > "${WORK}/lvs_fresh.json" 2>/dev/null || true
  "${PY[@]}" - "${WORK}/lvs_fresh.json" "${REPORT_LVS}" <<'PY'
import json, sys
try:
    a, b = (json.load(open(p)) for p in sys.argv[1:3])
except ValueError as e:
    print(f"  FAIL: unreadable lvs envelope: {e}", file=sys.stderr); sys.exit(1)
if a != b:
    print("  FAIL: committed lvs_report.json differs from a fresh run of the committed request", file=sys.stderr); sys.exit(1)
print("  committed envelope equals a fresh run of the committed request")
PY
  verdict "${REPORT_LVS}"
else
  derive_lvs_inputs "${WORK}"
  for f in "${LVS_FILES[@]}"; do cp "${WORK}/${f}" "${REL_CELL}/${f}"; done
  "${KLT[@]}" lvs "${REL_CELL}/lvs_request.json" --format json > "${WORK}/lvs_report.json" 2> "${WORK}/lvs.err" || true
  verdict "${WORK}/lvs_report.json" || { cat "${WORK}/lvs.err" >&2; exit 1; }
  cp "${WORK}/lvs_report.json" "${REPORT_LVS}"
fi

say "5. connectivity negative controls (each mutated reference MUST mismatch)"
control() {  # <name> <sed expression> <what it breaks>
  local name="$1" expr="$2" what="$3"
  mkdir "${WORK}/${name}"
  cp "${REL_CELL}/lvs_extracted.spice" "${REL_CELL}/lvs_request.json" "${WORK}/${name}/"
  sed "${expr}" "${REL_CELL}/lvs_reference.spice" > "${WORK}/${name}/lvs_reference.spice"
  if cmp -s "${REL_CELL}/lvs_reference.spice" "${WORK}/${name}/lvs_reference.spice"; then
    echo "  ${name}: mutation did not change the reference -- control is void" >&2
    exit 1
  fi
  "${KLT[@]}" lvs "${WORK}/${name}/lvs_request.json" --format json > "${WORK}/${name}.out" 2>/dev/null || true
  # an empty/error output is not a mismatch verdict: verdict() rejects it
  verdict "${WORK}/${name}.out" "${name} (${what})"
}
# Topology: rewire one latch device's gate. Nothing in the drawn geometry
# changes -- only the reference's claim about it.
control topology-control 's/^XM3 ln lp np vss/XM3 ln ln np vss/' "M3 gate lp -> ln"
# Parameter: input-device W 12u -> 11.5u, less than one 3u finger, so a
# compare that tolerated or mis-summed fingers would not see it.
control parameter-control \
  's/^XM1 np vinp tail vss sg13_lv_nmos w=12u/XM1 np vinp tail vss sg13_lv_nmos w=11.5u/' \
  "M1 W 12u -> 11.5u"

say "6. drc (klt drc --deck sg13g2; T1 item 3 evidence)"
REPORT="${CELL_DIR}/drc_report.json"
REL_GDS="${GDS#"${REPO}/"}"
REL_REPORT="${REPORT#"${REPO}/"}"
cd "${REPO}"  # klt records the input path as given: keep it repo-relative
if [[ "${MODE}" == "check" ]]; then
  "${KLT[@]}" drc --check "${REL_REPORT}" > /dev/null
  echo "  committed ${REL_REPORT} is fresh for ${REL_GDS}"
else
  # exit 3 = violations found; the report is still written, then judged below
  "${KLT[@]}" drc --deck sg13g2 --top "${TOP}" --format json "${REL_GDS}" \
    > "${WORK}/drc_report.json" || [[ $? -eq 3 ]]
  cp "${WORK}/drc_report.json" "${REPORT}"
fi
"${PY[@]}" - "${REPORT}" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
c = d["coverage"]
print(f"  status: {d['status']}  violations: {d['violation_count']}  deck: {d['provenance']['deck']['content_hash'][:23]}...")
print(f"  rules checked: {len(c['rules_checked'])}  skipped: {len(c['rules_skipped'])}")
print(f"  layers in stream without rules: {', '.join(c['layers_in_stream_without_rules'])}")
if d["file"].startswith("/"):
    print(f"  FAIL: envelope embeds a host-absolute path: {d['file']}", file=sys.stderr); sys.exit(1)
sys.exit(0 if d["status"] == "clean" else 1)
PY

say "done (${MODE})"
