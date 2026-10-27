#!/usr/bin/env python3
"""Drift guard for the pinned klt / KLayout build (issue #135).

`manifests/klt-pin.json` is the single source of truth for the pinned
`klt` build (`klt_commit`, `klt_version`) and the KLayout it was tested
against (`klayout_version`). This script asserts that every machine-read
copy of those values agrees with it:

  - `.github/workflows/ci.yml`: every klt install line (at least two: the
    signoff and layout jobs) -- `klayout-tools==<klt_version>` for a release
    pin, `klayout-tools@<klt_commit>` for a git (dev-build) pin and every `klayout==<ver>`
    pin (at least one);
  - `layout/run_flow.sh`: `KLT_PIN="..."` (version or commit, per the form) and `KLAYOUT_PIN="..."`;
  - `manifests/t1-signoff-report.json`: `build.git_commit`, `build.version`;
  - `layout/comparator/{drc,lvs,erc}_report.json`: `provenance.klt_version`
    and `provenance.klayout_version`.

It also asserts the pin file is self-consistent. Two forms are accepted: a
release pin (`klt_version` is a bare `X.Y.Z`, PyPI `klayout-tools==X.Y.Z`;
`klt_commit` is the release tag's commit, provenance only) and a git pin
(`klt_version` ends in `+g<klt_commit[:12]>`).

`layout/comparator/pex_report.json` is deliberately NOT checked: it was
produced by a different (newer) klt/KLayout build on purpose. Prose mentions
in READMEs are out of scope (documentation, covered by review).

A missing copy (file absent, pattern not found, key absent) is a failure,
not a skip. Every problem is reported, then:

  exit 0   all copies agree with the pin file
  exit 1   at least one mismatch or missing copy

Standard library only; no klt, KLayout or PDK needed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PIN_FILE = "manifests/klt-pin.json"
CI_YML = ".github/workflows/ci.yml"
RUN_FLOW = "layout/run_flow.sh"
SIGNOFF = "manifests/t1-signoff-report.json"
LAYOUT_REPORTS = (
    "layout/comparator/drc_report.json",
    "layout/comparator/lvs_report.json",
    "layout/comparator/erc_report.json",
)

CI_KLT_GIT_RE = re.compile(r"klayout-tools@([0-9A-Za-z._-]+)")
CI_KLT_REL_RE = re.compile(r"klayout-tools==([0-9A-Za-z._+-]+)")
RELEASE_VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
CI_KLAYOUT_RE = re.compile(r"\bklayout==([0-9A-Za-z._+-]+)")
CI_KLT_MIN = 2  # signoff-manifest-parity + layout-reproducibility
CI_KLAYOUT_MIN = 1  # layout-reproducibility

PIN_KEYS = ("klt_commit", "klt_version", "klayout_version")


class Checker:
    def __init__(self, root: Path):
        self.root = root
        self.errors: list[str] = []
        self.checked = 0

    def fail(self, msg: str) -> None:
        self.errors.append(msg)

    def compare(self, pin_key: str, want: str, where: str, got: object) -> None:
        self.checked += 1
        if got != want:
            self.fail(
                f"{PIN_FILE}:{pin_key} = {want!r} but {where} = {got!r}"
            )

    def read_text(self, rel: str) -> str | None:
        p = self.root / rel
        try:
            return p.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.fail(f"missing copy: {rel} does not exist")
        except OSError as e:
            self.fail(f"missing copy: cannot read {rel}: {e}")
        return None

    def read_json(self, rel: str) -> object | None:
        text = self.read_text(rel)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            self.fail(f"{rel}: invalid JSON: {e}")
            return None

    # -- source of truth ---------------------------------------------------

    def load_pin(self) -> dict[str, str] | None:
        data = self.read_json(PIN_FILE)
        if data is None:
            return None
        if not isinstance(data, dict):
            self.fail(f"{PIN_FILE}: top level must be an object")
            return None
        pin = {}
        for k in PIN_KEYS:
            v = data.get(k)
            if not isinstance(v, str) or not v:
                self.fail(f"{PIN_FILE}: key {k!r} missing or not a non-empty string")
                continue
            pin[k] = v
        if len(pin) != len(PIN_KEYS):
            return None
        commit = pin["klt_commit"]
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            self.fail(f"{PIN_FILE}:klt_commit = {commit!r} is not a full 40-hex sha")
        suffix = "+g" + commit[:12]
        if "+g" in pin["klt_version"]:
            if not pin["klt_version"].endswith(suffix):
                self.fail(
                    f"{PIN_FILE}:klt_version = {pin['klt_version']!r} does not end in "
                    f"{suffix!r} (the 12-char prefix of {PIN_FILE}:klt_commit)"
                )
        elif not RELEASE_VERSION_RE.fullmatch(pin["klt_version"]):
            self.fail(
                f"{PIN_FILE}:klt_version = {pin['klt_version']!r} is neither a release "
                f"version (X.Y.Z) nor a git build (...+g<sha12>)"
            )
        return pin

    @staticmethod
    def is_release(pin) -> bool:
        return "+g" not in pin["klt_version"]

    # -- copies -------------------------------------------------------------

    def check_regex_copies(self, rel, text, rx, pin_key, want, minimum, label):
        hits = []
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in rx.finditer(line):
                hits.append((lineno, m.group(1)))
        if len(hits) < minimum:
            self.fail(
                f"missing copy: {rel} has {len(hits)} {label} occurrence(s), "
                f"expected at least {minimum} (pin {PIN_FILE}:{pin_key} = {want!r})"
            )
        for lineno, got in hits:
            self.compare(pin_key, want, f"{rel}:{lineno} ({label})", got)

    def check_ci(self, pin):
        text = self.read_text(CI_YML)
        if text is None:
            return
        if self.is_release(pin):
            self.check_regex_copies(CI_YML, text, CI_KLT_REL_RE, "klt_version",
                                    pin["klt_version"], CI_KLT_MIN,
                                    "klayout-tools==<version>")
            for lineno, line in enumerate(text.splitlines(), 1):
                if CI_KLT_GIT_RE.search(line):
                    self.fail(f"{CI_YML}:{lineno}: git-form klayout-tools@<sha> "
                              f"install but {PIN_FILE} pins release {pin['klt_version']!r}")
        else:
            self.check_regex_copies(CI_YML, text, CI_KLT_GIT_RE, "klt_commit",
                                    pin["klt_commit"], CI_KLT_MIN,
                                    "klayout-tools@<sha>")
        self.check_regex_copies(CI_YML, text, CI_KLAYOUT_RE, "klayout_version",
                                pin["klayout_version"], CI_KLAYOUT_MIN,
                                "klayout==<version>")

    def check_run_flow(self, pin):
        text = self.read_text(RUN_FLOW)
        if text is None:
            return
        klt_key = "klt_version" if self.is_release(pin) else "klt_commit"
        for var, key in (("KLT_PIN", klt_key), ("KLAYOUT_PIN", "klayout_version")):
            rx = re.compile(rf"^\s*{var}=(['\"]?)([^'\"\s#]*)\1", re.M)
            hits = [(text.count("\n", 0, m.start()) + 1, m.group(2))
                    for m in rx.finditer(text)]
            if not hits:
                self.fail(
                    f"missing copy: {RUN_FLOW} has no {var}=... assignment "
                    f"(pin {PIN_FILE}:{key} = {pin[key]!r})"
                )
            for lineno, got in hits:
                self.compare(key, pin[key], f"{RUN_FLOW}:{lineno} ({var})", got)

    def check_json_key(self, rel, data, path, pin_key, want):
        cur = data
        for part in path:
            if not isinstance(cur, dict) or part not in cur:
                self.fail(
                    f"missing copy: {rel} has no key {'.'.join(path)} "
                    f"(pin {PIN_FILE}:{pin_key} = {want!r})"
                )
                return
            cur = cur[part]
        self.compare(pin_key, want, f"{rel}:{'.'.join(path)}", cur)

    def check_signoff(self, pin):
        data = self.read_json(SIGNOFF)
        if data is None:
            return
        self.check_json_key(SIGNOFF, data, ("build", "git_commit"),
                            "klt_commit", pin["klt_commit"])
        self.check_json_key(SIGNOFF, data, ("build", "version"),
                            "klt_version", pin["klt_version"])

    def check_layout_reports(self, pin):
        for rel in LAYOUT_REPORTS:
            data = self.read_json(rel)
            if data is None:
                continue
            self.check_json_key(rel, data, ("provenance", "klt_version"),
                                "klt_version", pin["klt_version"])
            self.check_json_key(rel, data, ("provenance", "klayout_version"),
                                "klayout_version", pin["klayout_version"])

    def run(self) -> int:
        pin = self.load_pin()
        if pin is not None:
            self.check_ci(pin)
            self.check_run_flow(pin)
            self.check_signoff(pin)
            self.check_layout_reports(pin)
        if self.errors:
            print(f"klt pin drift: {len(self.errors)} problem(s) "
                  f"(source of truth: {PIN_FILE})", file=sys.stderr)
            for e in self.errors:
                print(f"  - {e}", file=sys.stderr)
            print("Move the pin file, every copy, and the frozen reports in one "
                  "change (manifests/README.md).", file=sys.stderr)
            return 1
        print(f"klt pin OK: {self.checked} copies agree with {PIN_FILE} "
              f"(klt {pin['klt_commit']}, {pin['klt_version']}; "
              f"KLayout {pin['klayout_version']})")
        return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path,
                    default=Path(__file__).resolve().parents[1],
                    help="repository root (default: this script's repo)")
    args = ap.parse_args(argv)
    return Checker(args.root).run()


if __name__ == "__main__":
    sys.exit(main())
