"""Git plumbing shared by the evidence CI checkers (stdlib only).

``check_evidence_size.py``, ``check_append_only_evidence.py`` and
``check_artifact_manifests.py`` each need the same two helpers; they differ
only in the exception type they raise, so the caller passes it as ``error``.

All three run only in the ``append-only-evidence`` CI job, whose sparse cone is
the whole ``/scripts/`` directory, so this module needs no cone entry of its
own (``scripts/tests/test_sparse_checkout.py`` proves the job runs them).

``GIT_NO_LAZY_FETCH=1`` is set for every checker. Without it a missing object
in a blob-filtered partial clone is fetched from the promisor remote one round
trip at a time (CI run 38029844566 hung on ~97k of them); with it the read
fails closed. The append-only checker previously did not set it. That looked
accidental: it runs in the same complete (non-partial) clone as the size
checker, where the variable changes nothing, and in a partial clone failing
closed is the wanted behaviour for a policy gate.
"""

from __future__ import annotations

import os
import subprocess


def git_env() -> dict:
    return {**os.environ, "GIT_NO_LAZY_FETCH": "1"}


def git(repo: str, *args: str, error: type[Exception] = RuntimeError,
        check: bool = True) -> bytes:
    """Run ``git -C repo args`` and return stdout.

    A non-zero exit raises ``error`` when ``check`` is true; otherwise it
    returns ``b""``. A failure to execute git always raises ``error``.
    """
    try:
        proc = subprocess.run(["git", "-C", repo, *args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=False, env=git_env())
    except OSError as exc:
        raise error(f"cannot run git: {exc}") from exc
    if proc.returncode != 0:
        if check:
            msg = proc.stderr.decode("utf-8", "replace").strip()
            raise error(f"git {' '.join(args)} failed: {msg}")
        return b""
    return proc.stdout


def resolve_tree(repo: str, rev: str, error: type[Exception] = RuntimeError,
                 label: str = "") -> str:
    """Resolve ``rev`` to a tree id, raising ``error`` if it is unavailable."""
    what = f"{label} revision" if label else "revision"
    if rev.startswith("-"):
        raise error(f"invalid {what} {rev!r}")
    try:
        out = git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options",
                  f"{rev}^{{tree}}", error=error)
    except error as exc:
        raise error(f"{what} {rev!r} is unavailable: {exc}") from exc
    oid = out.decode().strip()
    if not oid:
        raise error(f"{what} {rev!r} is unavailable")
    return oid
