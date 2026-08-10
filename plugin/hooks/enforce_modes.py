#!/usr/bin/env python3
"""
enforce_modes.py — PreToolUse hook for the /modes skill (Claude Code plugin).

Makes the write-blocking modes MECHANICAL. SKILL.md + the fast-path script
(scripts/modes.py) tell the AGENT what an active mode forbids, but that relies on the
agent remembering the contract across turns — and across a directive-less gap it can
decay (the failure this hook exists to prevent: a non-markdown write slipping through
while plan mode is active). This hook fires before every Write/Edit/MultiEdit/
NotebookEdit, reads the session's active_modes.md, and DENIES the call if it violates an
active mode. Compliance no longer depends on the agent's memory.

Rules enforced (mirror SKILL.md "Mode behaviors"):
  • plan     — block any write whose target is NOT a .md file (markdown-only writes).
  • exclude  — block any write whose target matches an active exclude glob.
  • include  — block any write whose target matches NONE of the active include globs.

Fail-OPEN: any error, missing file, or unresolved session -> allow (exit 0). A hook must
never wedge the user's ability to edit files; enforcement is a floor, not a tripwire.

Contract (Claude Code PreToolUse hook):
  stdin  = JSON with tool_name, tool_input.file_path, session_id, cwd, ...
  stdout = on a block, JSON {"hookSpecificOutput":{"hookEventName":"PreToolUse",
           "permissionDecision":"deny","permissionDecisionReason": "..."}}; else nothing.
  exit 0 always — a deny is expressed in the JSON, never via the exit code.

Stdlib only. No third-party imports (no jq). Targets Python 3.9+.
"""

import os
import re
import sys
import json
import glob


WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def resolve_active_modes_path(cwd, sid):
    """Locate <auto-memory>/<sid>/active_modes.md. Mirrors scripts/modes.py resolution."""
    if not sid:
        return None
    home = os.path.expanduser("~")
    slug = (cwd or os.getcwd()).replace("/", "-")
    primary = os.path.join(
        home, ".claude", "projects", slug, "memory", sid, "active_modes.md")
    if os.path.isfile(primary):
        return primary
    # Session ids are globally unique, so a cross-project glob is safe when the cwd-derived
    # slug misses (e.g. the tool was invoked from a subdir of the project).
    matches = glob.glob(
        os.path.join(home, ".claude", "projects", "*", "memory", sid, "active_modes.md"))
    if len(matches) == 1:
        return matches[0]
    return None


def read_modes(path):
    """Parse active_modes.md -> {mode: param}; param is a glob list for exclude/include."""
    state = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh.read().splitlines():
            line = line.strip()
            if not line.startswith("- "):
                continue
            body = line[2:].strip()
            if ":" in body:
                name, param = body.split(":", 1)
                name, param = name.strip().lower(), param.strip()
            else:
                name, param = body.lower(), None
            if name in ("exclude", "include"):
                state[name] = [p.strip() for p in (param or "").split(",") if p.strip()]
            else:
                state[name] = param
    return state


def target_path(tool_input):
    """Best-effort target file path from a write tool's input (Write/Edit/Notebook)."""
    if not isinstance(tool_input, dict):
        return None
    return tool_input.get("file_path") or tool_input.get("notebook_path")


def glob_to_regex(pattern):
    """Translate a gitignore-ish glob to an anchored regex. `**/` spans zero or more dirs,
    `**` spans anything, `*`/`?` stay within a path segment (do not cross `/`)."""
    if pattern.startswith("./"):
        pattern = pattern[2:]
    out = ["^"]
    i, n = 0, len(pattern)
    while i < n:
        if pattern[i:i + 3] == "**/":
            out.append("(?:.*/)?")
            i += 3
        elif pattern[i:i + 2] == "**":
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    out.append("$")
    return "".join(out)


def candidate_paths(path, cwd):
    """The path forms to test a pattern against: as-given, basename, and cwd-relative."""
    cands = [path, os.path.basename(path)]
    if cwd and os.path.isabs(path):
        try:
            rel = os.path.relpath(path, cwd)
            if not rel.startswith(".."):
                cands.append(rel)
        except ValueError:  # different drive on Windows, etc.
            pass
    return cands


def matches_glob(path, pattern, cwd):
    """True if any candidate form of `path` matches the gitignore-ish `pattern`."""
    rx = re.compile(glob_to_regex(pattern))
    return any(rx.match(c) for c in candidate_paths(path, cwd))


def violation(state, path, cwd):
    """Return a deny reason if `path` violates an active write-mode, else None."""
    ext = os.path.splitext(path)[1].lower()

    if "plan" in state and ext != ".md":
        return ("plan mode is active — it allows only markdown (.md) writes, and `{p}` is "
                "not markdown. To make this change, exit plan mode first: `/modes agent` "
                "(or `/modes clear`).").format(p=path)

    if "exclude" in state:
        for pat in state["exclude"]:
            if matches_glob(path, pat, cwd):
                return ("`{p}` matches the active exclude pattern `{pat}` — writes to it "
                        "are blocked. Adjust with `/modes exit exclude`.").format(
                            p=path, pat=pat)

    if state.get("include"):
        if not any(matches_glob(path, pat, cwd) for pat in state["include"]):
            return ("include mode is active and `{p}` matches no include pattern ({pats}) "
                    "— writes outside the include set are blocked. Adjust with "
                    "`/modes exit include`.").format(p=path, pats=", ".join(state["include"]))

    return None


def deny(reason):
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Blocked by /modes: " + reason,
        }
    }, sys.stdout)
    sys.stdout.write("\n")


def main():
    data = json.loads(sys.stdin.read())

    if data.get("tool_name") not in WRITE_TOOLS:
        return 0
    path = target_path(data.get("tool_input"))
    if not path:
        return 0

    cwd = data.get("cwd")
    sid = data.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID")
    modes_path = resolve_active_modes_path(cwd, sid)
    if not modes_path:
        return 0

    reason = violation(read_modes(modes_path), path, cwd)
    if reason:
        deny(reason)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # fail-OPEN: never block the user on our own error
        sys.stderr.write("enforce_modes hook error: {}\n".format(exc))
        sys.exit(0)
