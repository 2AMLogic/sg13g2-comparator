#!/usr/bin/env bash
# Provision the two external inputs of `python3 design/netlist.py --check`
# (issue #224): a pinned xschem and the pinned SG13G2 PDK. CI-side helper; it
# only writes under the prefix/root directory it is given, never host-wide.
#
#   scripts/provision_netlist_env.sh xschem <prefix>   # builds xschem into <prefix>/bin
#   scripts/provision_netlist_env.sh pdk <pdk-root>    # lays out <pdk-root>/ihp-sg13g2
#
# The PDK release, URL and tarball sha256 are read from sim/pdk.json (the
# single source of truth); the xschem pin lives here. Every download is
# sha256-verified; any failure exits nonzero (nothing here skips).
# Build dependencies (CI installs them via apt before calling this script):
#   build-essential tcl-dev tk-dev libx11-dev libxpm-dev libcairo2-dev
#   bison flex gawk
set -euo pipefail

XSCHEM_VERSION=3.4.7
XSCHEM_URL="https://github.com/StefanSchippers/xschem/archive/refs/tags/${XSCHEM_VERSION}.tar.gz"
XSCHEM_SHA256=8f6c7165c38f528b6cbae8f9fae72cde3b765652df90597011a5f7b5e7fdb273

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
what=${1:?usage: $0 xschem <prefix> | pdk <pdk-root>}
dest=${2:?usage: $0 xschem <prefix> | pdk <pdk-root>}

fetch_verified() { # url sha256 out
  curl -fsSL --retry 3 -o "$3" "$1"
  echo "$2  $3" | sha256sum -c -
}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

case "$what" in
  xschem)
    fetch_verified "$XSCHEM_URL" "$XSCHEM_SHA256" "$work/xschem.tar.gz"
    tar -xzf "$work/xschem.tar.gz" -C "$work"
    (cd "$work/xschem-${XSCHEM_VERSION}" \
      && ./configure --prefix="$dest" >/dev/null \
      && make -j2 >/dev/null \
      && make install >/dev/null)
    got=$("$dest/bin/xschem" --version 2>&1 | head -1)
    test "$got" = "XSCHEM V${XSCHEM_VERSION}" || { echo "xschem version is '$got', pinned ${XSCHEM_VERSION}" >&2; exit 1; }
    echo "provisioned $got in $dest"
    ;;
  pdk)
    read -r tag url sha variant < <(python3 -I - "$repo_root/sim/pdk.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(d["release_tag"], d["release_url"], d["tarball_sha256"], d["variant"])
PY
)
    fetch_verified "$url" "$sha" "$work/pdk.tar.gz"
    mkdir -p "$dest/$variant"
    # Only what the harness discovery contract and xschem netlisting read.
    tar -xzf "$work/pdk.tar.gz" -C "$dest/$variant" --strip-components=2 \
      --wildcards "*/$variant/libs.tech/*" "*/$variant/libs.ref/*"
    # Same marker klt's fetch-ihp-sg13g2.sh writes (sim/toolchain.json checks it).
    printf '%s\n' "${tag#v}" > "$dest/$variant/.fetched-version"
    echo "provisioned $variant ${tag} in $dest"
    ;;
  *) echo "usage: $0 xschem <prefix> | pdk <pdk-root>" >&2; exit 2 ;;
esac
