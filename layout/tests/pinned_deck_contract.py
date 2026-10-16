"""Re-derive pdk_drc.REQUIRED_CATEGORIES from a local pinned deck (issue #253).

Static source analysis of the pinned IHP deck; the deck is not run. It needs a
local PDK checkout whose deck tree matches DECK_TREE_SHA256, which CI does not
have, so this module is deliberately outside the CI discovery pattern
(`test_*.py`) and runs by hand:

    python3 -I layout/tests/pinned_deck_contract.py

A missing or non-pinned deck is an error (exit 1), never a skip or a pass:
the contract was not checked.
"""

import importlib.util
import re
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "test_pdk_drc_for_contract", Path(__file__).resolve().with_name("test_pdk_drc.py"))
_tests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tests)
pd = _tests.pd


def derive_required(drc_dir: Path) -> dict:
    """Re-derive REQUIRED_CATEGORIES from a deck checkout: literal
    ``.output('<name>'`` calls whose enclosing blocks are only switches the
    pdk_drc.py invocation turns on (see the comment on REQUIRED_CATEGORIES)."""
    opener = re.compile(r"^\s*(if|unless|while|until|case|begin|def|class|module)\b")
    do_block = re.compile(r"\bdo\s*(\|[^|]*\|)?\s*$")
    literal = re.compile(r"""\.output\(\s*(['"])([^'"#]+)\1""")
    enabled = re.compile(
        r"^(if TABLES\.include\?\('[a-z0-9]+'\) \|\| (FEOL|BEOL|PIN|FORBIDDEN)"
        r"|unless PRECHECK_DRC|if !PRECHECK_DRC( && CONNECTIVITY_RULES)?|if RECOMMENDED"
        r"|if \$(fillerRules|latchUpRules|recommendedRules)|-> (\(;[a-z, ]+\) )?do)$")
    out = {"main": [], "sg13g2_maximal": []}
    decks = drc_dir / "rule_decks"
    files = sorted(p for sub in ("feol", "beol", "forbidden", "geometry", "pin")
                   for p in (decks / sub).glob("*.drc"))
    for f in files + [decks / "sg13g2_maximal.drc"]:
        stack = []
        for raw in f.read_text().splitlines():
            line = "" if raw.strip().startswith("#") else raw.split(" #")[0]
            s = line.strip()
            if not s:
                continue
            if s.startswith(("elsif", "else", "when")):
                if stack:
                    stack[-1] += " (else)"
                continue
            if re.match(r"^end\b", s) and stack:
                stack.pop()
            for m in literal.finditer(line):
                if all(enabled.match(c) for c in stack):
                    out["sg13g2_maximal" if f.stem == "sg13g2_maximal" else "main"].append(m.group(2))
            if not re.match(r"^end\b", s) and (opener.match(line) or do_block.search(line)):
                stack.append(s)
    return out


class PinnedDeckContract(unittest.TestCase):
    """The emission contract against the real pinned deck source. Kept out of
    CI discovery (this file does not match `test_*.py`); run by hand. Static:
    the deck is not run."""

    def setUp(self):
        try:
            self.pdk = pd.find_pdk(None)
        except pd.Unavailable as e:
            self.fail(f"cannot check: pinned PDK deck not available locally: {e.detail}")
        if pd.deck_tree_sha256(self.pdk) != pd.DECK_TREE_SHA256:
            self.fail("cannot check: local PDK deck is not the pinned tree")

    def test_required_categories_match_pinned_deck(self):
        got = derive_required(self.pdk / pd.DECK_REL)
        for rule_set, rules in pd.REQUIRED_CATEGORIES.items():
            self.assertEqual(sorted(got[rule_set]), sorted(rules), rule_set)


if __name__ == "__main__":
    unittest.main()
