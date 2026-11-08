"""Append-only writer for a complete, precomputed set of artifact bytes.

Shared by the campaign-input builder (``build.commit_inputs``), the
characterization report (``characterization.generate``) and the derived
report pairs (``grading.*``, ``noise_full.*``, ``comparison.*``).

Contract (stdlib only):

* Every artifact is composed in memory BEFORE any filesystem mutation.
* Preflight the whole set: an existing member must be a regular, non-symlink
  file holding exactly the proposed bytes, otherwise the whole set is
  rejected (:class:`ArtifactConflict`) before ANY member is touched.
* Identical members are left alone (bytes and timestamps preserved).
* Absent members are created with exclusive creation (``x``), so a concurrent
  writer is never clobbered. A concurrent winner with different bytes raises
  :class:`ArtifactConflict` (``concurrent=True``); no whole-set rollback is
  promised after a race.
* :func:`check` is the read-only twin: it reports missing / different /
  unsafe members and never creates a file or directory.
"""

from __future__ import annotations

from pathlib import Path

Files = list[tuple[Path, bytes]]


class ArtifactConflict(RuntimeError):
    """Preservation refused. ``conflicts`` holds one line per offending member."""

    def __init__(self, conflicts: list[str], *, concurrent: bool = False):
        self.conflicts = list(conflicts)
        self.concurrent = concurrent
        super().__init__("; ".join(self.conflicts))


def _dedupe(files: Files, dup: str) -> tuple[dict[Path, bytes], list[str]]:
    proposed: dict[Path, bytes] = {}
    problems: list[str] = []
    for path, data in files:
        if path in proposed and proposed[path] != data:
            problems.append(f"{path}: {dup}")
        proposed.setdefault(path, data)
    return proposed, problems


def _inspect(proposed: dict[Path, bytes], differs: str,
             require_dir: Path | None) -> tuple[list[str], list[Path]]:
    """Return (unsafe-or-different problems, absent paths). Never writes."""
    problems: list[str] = []
    absent: list[Path] = []
    if require_dir is not None and (
            require_dir.is_symlink() or (require_dir.exists() and not require_dir.is_dir())):
        return [f"{require_dir}: exists and is not a directory"], absent
    for path, data in proposed.items():
        if path.is_symlink() or (path.exists() and not path.is_file()):
            problems.append(f"{path}: exists and is not a regular file")
        elif path.exists():
            if path.read_bytes() != data:
                problems.append(f"{path}: {differs}")
        else:
            absent.append(path)
    return problems, absent


def check(files: Files, *, differs: str = "existing content differs from the proposed content",
          dup: str = "two different contents proposed",
          require_dir: Path | None = None) -> list[str]:
    """Read-only comparison; returns problems (empty = every member present and identical)."""
    proposed, problems = _dedupe(files, dup)
    bad, absent = _inspect(proposed, differs, require_dir)
    return problems + bad + [f"{p}: missing" for p in absent]


def commit(files: Files, *, differs: str = "existing content differs from the proposed content",
           dup: str = "two different contents proposed",
           race: str = "created concurrently with different content",
           require_dir: Path | None = None) -> list[Path]:
    """Append-only write; returns the paths newly created.

    Raises :class:`ArtifactConflict` (before any write) on any conflict.
    """
    proposed, problems = _dedupe(files, dup)
    bad, _ = _inspect(proposed, differs, require_dir)
    problems += bad
    if problems:
        raise ArtifactConflict(problems)
    created: list[Path] = []
    for path, data in proposed.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "xb") as handle:
                handle.write(data)
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
                raise ArtifactConflict([f"{path}: {race}"], concurrent=True) from None
            continue
        created.append(path)
    return created


def publish(label: str, files: Files, *, check_only: bool = False, namespace_hint: str,
            require_dir: Path | None = None, err=None, out=None) -> int:
    """CLI helper for derived report sets. Returns a process exit code.

    ``check_only``: read-only; 0 only if every member is present and
    byte-identical to the freshly composed bytes, else 1 (nothing written, no
    directory created). Otherwise append-only :func:`commit`; 1 on conflict
    with nothing written.
    """
    import sys
    err = err or sys.stderr
    out = out or sys.stdout
    differs = "existing content differs from the regenerated content"
    if check_only:
        problems = check(files, differs=differs, require_dir=require_dir)
        if problems:
            print(f"{label}: check FAILED (read-only; nothing written):\n  "
                  + "\n  ".join(problems) + f"\n{namespace_hint}", file=err)
            return 1
        print(f"{label}: check ok ({len(files)} artifact(s) identical to a fresh regeneration)",
              file=out)
        return 0
    try:
        created = commit(files, differs=differs, require_dir=require_dir)
    except ArtifactConflict as exc:
        what = ("conflicting concurrent creation (left unchanged)" if exc.concurrent
                else "refusing to overwrite append-only evidence; nothing was written")
        print(f"{label}: {what}:\n  " + "\n  ".join(exc.conflicts) + f"\n{namespace_hint}",
              file=err)
        return 1
    for path in created:
        print(f"{label}: wrote {path}", file=err)
    return 0
