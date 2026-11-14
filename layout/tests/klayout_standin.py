"""Load a klayout-importing layout tool with stand-ins for a missing klayout.

Single source for the loader that ``test_erc_tool.py`` (issue #117) and
``test_pdk_drc.py`` (issue #180) each carried a near-verbatim copy of before
issue #432. Both tools import ``klayout.db`` at module load but touch it only
at run time, so when real klayout is absent empty stand-in modules are
installed for the import and removed again in a ``finally``: nothing else in
the same discovery run may see a fake klayout.

The save/restore is process-global (``sys.modules`` and ``sys.path``), which is
why it is worth having exactly one copy of. Callers keep the returned
``used_standin`` flag to gate a ``TestStandinHygiene`` assertion that the
stand-ins really were removed.

This module's name begins with neither CI discovery prefix (``test_*.py`` at
`.github/workflows/ci.yml:396`, ``klayout_test_*.py`` at line 199), so it is
imported as a sibling helper and never collected as a test -- the same
convention as ``pinned_deck_contract.py`` (issue #253).

Importing it needs ``layout/tests`` on ``sys.path``. ``unittest discover -s
layout/tests`` inserts the start directory itself, but ``python3 -I`` implies
``-P`` (3.11+), so a direct ``python3 -I layout/tests/test_pdk_drc.py`` -- and
``pinned_deck_contract.py``, which loads ``test_pdk_drc.py`` by path -- would
not get it. Each importer therefore puts its own directory on ``sys.path``
first; that cannot live here, since finding this module is the problem it
solves.
"""

import importlib.util
import sys
import types

STANDINS = ("klayout", "klayout.db")


def load_tool(tool_path, module_name):
    """Exec the tool at *tool_path* under *module_name*.

    Returns ``(module, used_standin)``. ``used_standin`` is True when real
    ``klayout.db`` was unavailable and stand-ins were installed for the load.
    """
    try:
        import klayout.db  # noqa: F401
        standin = False
    except ImportError:
        standin = True
    path_before = list(sys.path)
    mods_before = set(sys.modules)
    if standin:
        pkg = types.ModuleType("klayout")
        pkg.__path__ = []
        db = types.ModuleType("klayout.db")
        pkg.db = db
        sys.modules["klayout"] = pkg
        sys.modules["klayout.db"] = db
    try:
        spec = importlib.util.spec_from_file_location(module_name, tool_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if standin:
            for name in STANDINS:
                sys.modules.pop(name, None)
            # common_sg13g2 got bound to the stand-in; do not leave it behind.
            for name in set(sys.modules) - mods_before:
                if name == "common_sg13g2":
                    sys.modules.pop(name, None)
            sys.path[:] = path_before
    return mod, standin
