#!/usr/bin/env bash
# guard_index_scope.sh - on-demand diagnostic for the alternate-index wrapper
# symptom (issue #188).
#
# Feeds a fixed set of literal command strings, serialized as normal Claude
# Code PreToolUse JSON with `jq --arg`, to a destructive-command guard and
# reports, per input: the guard's process exit status and its parsed decision.
#
# The submitted command strings are DATA. They are never eval'd, sourced, or
# executed; the only program run per case is the guard itself, reading the
# JSON on stdin. See scripts/diagnostics/README.md.
#
# Usage:
#   scripts/diagnostics/guard_index_scope.sh [--guard PATH] [--canonical PATH]
#                                             [--reasons] [-h|--help]
#
#   --guard PATH      guard to observe (default: the installed vendored guard,
#                     <repo>/.loom/hooks/guard-destructive-generic.sh)
#   --canonical PATH  optional second guard (e.g. a local checkout of
#                     rjwalters/repo hooks/repo/guard-destructive.sh) observed
#                     with the identical inputs, for comparison
#   --reasons         also print permissionDecisionReason for ask/deny
#
# Decision interpretation (strict):
#   exit 0 + zero-byte stdout                      -> allow
#   exit 0 + one JSON object whose
#     .hookSpecificOutput.permissionDecision is
#     "ask" | "deny"                               -> that decision
#     "allow"                                      -> allow-json (explicit
#                                                     allow; bypasses the
#                                                     prompt, so kept distinct
#                                                     from empty-stdout allow)
#   anything else (payload serialization failure,
#     nonzero exit, timeout, invalid JSON,
#     missing/unknown decision field)              -> ERROR (never allow)
#   any case during which the guard's own
#     <guard dir>/../logs/hook-errors.log grew     -> ERROR (the guard's ERR
#                                                     trap masks internal
#                                                     errors as empty stdout)
#   The payload is built with jq into a file and checked (jq exit 0, non-empty,
#   .tool_input.command round-trips) before the guard is run; on failure the
#   guard is not run and the exit column shows "-".
#
# Exit status:
#   0  every case on every guard produced a valid observation
#   1  at least one case was a diagnostic ERROR, or the Git index / worktree
#      status changed while the diagnostic ran
#   2  usage error or missing prerequisite (jq, guard path)

set -uo pipefail

PROG="${0##*/}"

die_prereq() {
    printf '%s: error: %s\n' "$PROG" "$1" >&2
    exit 2
}

usage() {
    sed -n '2,/^$/{s/^# \{0,1\}//;p}' "$0"
}

_self="${BASH_SOURCE[0]}"
[[ "$_self" == */* ]] || _self="./$_self"
SCRIPT_DIR="$(cd "${_self%/*}" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

GUARD="$REPO_ROOT/.loom/hooks/guard-destructive-generic.sh"
GUARD_LABEL="installed"
CANONICAL=""
SHOW_REASONS=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --guard)
            [[ $# -ge 2 ]] || die_prereq "--guard requires a path"
            GUARD="$2"; GUARD_LABEL="override"; shift 2 ;;
        --canonical)
            [[ $# -ge 2 ]] || die_prereq "--canonical requires a path"
            CANONICAL="$2"; shift 2 ;;
        --reasons)
            SHOW_REASONS=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            printf '%s: error: unknown argument: %s\n' "$PROG" "$1" >&2
            usage >&2
            exit 2 ;;
    esac
done

command -v jq >/dev/null 2>&1 || die_prereq "jq not found on PATH (required to build and parse hook JSON)"

check_guard_path() {
    local label="$1" path="$2"
    [[ -e "$path" ]] || die_prereq "$label guard not found: $path"
    [[ -f "$path" ]] || die_prereq "$label guard is not a regular file: $path"
    [[ -r "$path" ]] || die_prereq "$label guard is not readable: $path"
}
check_guard_path "$GUARD_LABEL" "$GUARD"
[[ -n "$CANONICAL" ]] && check_guard_path canonical "$CANONICAL"

# ---------------------------------------------------------------------------
# Fixed inputs. Single-quoted literals: nothing here is expanded by this
# script (note the literal `$INDEX_PATH` in case 7), and none of it is run.
# ---------------------------------------------------------------------------
CASE_IDS=(
    sh-wrapper
    bash-wrapper
    direct-scratch
    bare-read-tree
    assign-other-cmd
    live-index
    unresolved-var
    unisolated-after
)
# shellcheck disable=SC2016  # `$INDEX_PATH` is intentionally literal, never expanded
CASE_CMDS=(
    'GIT_INDEX_FILE=/tmp/doc176/idx sh -c '"'"'git read-tree HEAD && git add -A sim && git write-tree'"'"
    'GIT_INDEX_FILE=/tmp/doc176/idx bash -c '"'"'git read-tree HEAD && git add -A sim && git write-tree'"'"
    'GIT_INDEX_FILE=/tmp/doc176/idx git read-tree HEAD'
    'git read-tree HEAD'
    'GIT_INDEX_FILE=/tmp/doc176/idx git status && git read-tree HEAD'
    'GIT_INDEX_FILE=.git/index sh -c '"'"'git read-tree HEAD'"'"
    'GIT_INDEX_FILE=$INDEX_PATH sh -c '"'"'git read-tree HEAD'"'"
    'GIT_INDEX_FILE=/tmp/doc176/idx sh -c '"'"'git read-tree HEAD'"'"' && git read-tree HEAD'
)

# ---------------------------------------------------------------------------
# Scratch space: a fresh directory outside the checkout, removed on exit.
# Guard decision telemetry is redirected here via LOOM_GUARD_DECISION_LOG_FILE.
# ---------------------------------------------------------------------------
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/guard-index-scope.XXXXXX")" \
    || die_prereq "mktemp -d failed"
SCRATCH="$(cd "$SCRATCH" && pwd -P)"
case "$SCRATCH/" in
    "$(cd "$REPO_ROOT" && pwd -P)/"*)
        rm -rf -- "$SCRATCH"
        die_prereq "scratch dir $SCRATCH is inside the checkout; set TMPDIR elsewhere" ;;
esac
# shellcheck disable=SC2317  # invoked via trap
cleanup() { rm -rf -- "$SCRATCH"; }
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Real Git state snapshot (index file bytes + status), compared after the run.
# ---------------------------------------------------------------------------
INDEX_FILE=""
if git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    INDEX_FILE="$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-path index 2>/dev/null)"
fi
snapshot_state() {
    [[ -n "$INDEX_FILE" ]] || { echo "no-git"; return; }
    {
        if [[ -f "$INDEX_FILE" ]]; then sha256sum < "$INDEX_FILE"; else echo "index-absent"; fi
        git -C "$REPO_ROOT" status --porcelain=v1 --untracked-files=all 2>&1
    } | sha256sum | cut -d' ' -f1
}
STATE_BEFORE="$(snapshot_state)"

sha_of() { sha256sum < "$1" | cut -d' ' -f1; }

# Path of the guard's own internal-error log, resolved the way the guard
# resolves it (<guard dir>/../logs, or <repo>/.loom/logs for a guard under
# a `defaults/` source tree). Read-only: only its size is ever inspected.
guard_error_log() {
    local dir parent
    dir="$(cd "$(dirname "$1")" && pwd)"
    parent="${dir%/*}"
    if [[ "${parent##*/}" == "defaults" ]]; then
        printf '%s/.loom/logs/hook-errors.log' "${parent%/*}"
    else
        printf '%s/../logs/hook-errors.log' "$dir"
    fi
}
# Size in bytes, or "absent". Never fails.
log_size() {
    local f
    f="$(guard_error_log "$1")"
    if [[ -f "$f" ]]; then stat -c %s -- "$f" 2>/dev/null || echo unreadable; else echo absent; fi
}

ERRORS=0

# observe LABEL GUARD_PATH IDX
observe() {
    local label="$1" guard="$2" idx="$3"
    local id="${CASE_IDS[$idx]}" cmd="${CASE_CMDS[$idx]}"
    local out="$SCRATCH/$label.$id.out" err="$SCRATCH/$label.$id.err"
    local payload="$SCRATCH/$label.$id.json"
    local status="-" decision reason="" jq_rc echoed log_before log_after

    # Payload is serialized only, into a file, and verified before the guard
    # sees it: a failed serialization must never reach the guard as empty
    # stdin (which the guard would answer with an empty-stdout "allow").
    jq -n --arg cmd "$cmd" --arg cwd "$REPO_ROOT" \
        '{hook_event_name:"PreToolUse", tool_name:"Bash",
          tool_input:{command:$cmd}, cwd:$cwd}' >"$payload" 2>"$err"
    jq_rc=$?
    echoed=""
    if [[ $jq_rc -eq 0 && -s "$payload" ]]; then
        echoed="$(jq -j '.tool_input.command' "$payload" 2>/dev/null && printf x)"
        echoed="${echoed%x}"
    fi

    if [[ $jq_rc -ne 0 || ! -s "$payload" || "$echoed" != "$cmd" ]]; then
        decision="ERROR"
        reason="payload serialization failed (jq exit $jq_rc); guard not run"
    else
        log_before="$(log_size "$guard")"
        LOOM_GUARD_DECISION_LOG_FILE="$SCRATCH/$label.decisions.jsonl" \
            timeout 60 bash "$guard" <"$payload" >"$out" 2>"$err"
        status=$?
        log_after="$(log_size "$guard")"
    fi

    if [[ "${decision:-}" == "ERROR" ]]; then
        :
    elif [[ "$status" -ne 0 ]]; then
        decision="ERROR"
        reason="guard exited $status$( [[ $status -eq 124 ]] && echo ' (timeout)')"
    elif [[ ! -s "$out" ]]; then
        decision="allow"
    elif ! jq -e 'type == "object"' "$out" >/dev/null 2>&1 \
         || [[ "$(jq -s 'length' "$out" 2>/dev/null)" != "1" ]]; then
        decision="ERROR"
        reason="stdout is not a single JSON object: $(head -c 120 "$out" | tr '\n' ' ')"
    else
        decision="$(jq -r '.hookSpecificOutput.permissionDecision // empty' "$out")"
        case "$decision" in
            allow|ask|deny)
                # An explicit JSON allow bypasses the permission prompt; it is
                # a different hook outcome from empty stdout, so keep it apart.
                [[ "$decision" == "allow" ]] && decision="allow-json"
                reason="$(jq -r '.hookSpecificOutput.permissionDecisionReason // ""' "$out")" ;;
            *)
                reason="missing/unknown permissionDecision: '${decision}'"
                decision="ERROR" ;;
        esac
    fi

    # The guard's ERR trap turns its own internal errors into exit 0 + empty
    # stdout, logging only to hook-errors.log. Growth during a case means the
    # observation cannot be trusted, whatever the decision looked like.
    if [[ "$status" != "-" && "$log_before" != "$log_after" ]]; then
        reason="guard internal-error log grew ($(guard_error_log "$guard"): $log_before -> $log_after bytes); observed: $decision${reason:+ ($reason)}"
        decision="ERROR"
    fi

    if [[ "$decision" == "ERROR" ]]; then
        ERRORS=$((ERRORS + 1))
        if [[ -s "$err" ]]; then
            reason="$reason; stderr: $(head -c 200 "$err" | tr '\n' ' ')"
        fi
    fi

    printf '%-9s  %-16s  %4s  %-10s  %s\n' "$label" "$id" "$status" "$decision" "$cmd"
    if [[ "$decision" == "ERROR" || ( $SHOW_REASONS -eq 1 && -n "$reason" ) ]]; then
        printf '%-9s  %-16s  %4s  %-10s  reason: %s\n' "" "" "" "" "$reason"
    fi
}

printf '# guard_index_scope.sh  date=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
printf '# repo=%s  head=%s\n' "$REPO_ROOT" \
    "$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo n/a)"
printf "# %s=%s  sha256=%s\n" "$GUARD_LABEL" "$GUARD" "$(sha_of "$GUARD")"
if [[ -n "$CANONICAL" ]]; then
    printf '# canonical=%s  sha256=%s\n' "$CANONICAL" "$(sha_of "$CANONICAL")"
fi
printf '# bash=%s  jq=%s  telemetry=%s (removed on exit)\n' \
    "${BASH_VERSION}" "$(jq --version)" "$SCRATCH"
printf '%-9s  %-16s  %4s  %-10s  %s\n' "guard" "case" "exit" "decision" "command (data only, not executed)"

for i in "${!CASE_IDS[@]}"; do
    observe "$GUARD_LABEL" "$GUARD" "$i"
done
if [[ -n "$CANONICAL" ]]; then
    for i in "${!CASE_IDS[@]}"; do
        observe canonical "$CANONICAL" "$i"
    done
fi

STATE_AFTER="$(snapshot_state)"
if [[ "$STATE_BEFORE" != "$STATE_AFTER" ]]; then
    printf '%s: error: Git index or worktree status changed during the run (%s -> %s)\n' \
        "$PROG" "$STATE_BEFORE" "$STATE_AFTER" >&2
    ERRORS=$((ERRORS + 1))
else
    printf '# git index+status fingerprint unchanged: %s\n' "$STATE_AFTER"
fi

if [[ $ERRORS -gt 0 ]]; then
    printf '%s: %d diagnostic error(s); errors are never reported as allow\n' "$PROG" "$ERRORS" >&2
    exit 1
fi
exit 0
