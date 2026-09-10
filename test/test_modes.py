#!/usr/bin/env python3
"""
Golden-case harness for scripts/modes.py.

Runs the real script as a subprocess against a throwaway HOME + a fixed session id, and
asserts BOTH the exact stdout (agent-notes + delimiters + user-echo) and the resulting
active_modes.md contents. This locks the echo contract before the SKILL.md fallback prose
is edited or the script is repackaged.

Run:  python3 modes/test/test_modes.py     (exit 0 = all green; exit 1 = failures)

Dev artifact — NOT shipped in any package (lives outside the skill dir).
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPT = os.path.join(REPO, "plugin", "skills", "modes", "scripts", "modes.py")
SKILL_MD = os.path.join(REPO, "plugin", "skills", "modes", "SKILL.md")
HOOK = os.path.join(REPO, "plugin", "hooks", "enforce_modes.py")
SID = "test-session-0000-1111"

# Import the script module so tests can assert against its LAW constants directly.
sys.path.insert(0, os.path.dirname(SCRIPT))
import modes as modes_mod  # noqa: E402

AGENT_DELIM = "===MODES_AGENT_NOTES==="
ECHO_DELIM = "===MODES_USER_ECHO==="

_failures = []
_count = 0


def slug_for(path):
    return path.replace("/", "-")


def run(directive, seed=None, with_session=True):
    """
    Run the script with a fresh temp HOME. `seed` is the active_modes.md body to
    pre-write (None -> no file). Returns (stdout, exitcode, final_file_or_None).
    """
    home = tempfile.mkdtemp()
    try:
        env = dict(os.environ)
        env["HOME"] = home
        memdir = os.path.join(home, ".claude", "projects", slug_for(REPO), "memory", SID)
        if with_session:
            env["CLAUDE_CODE_SESSION_ID"] = SID
            os.makedirs(memdir, exist_ok=True)
            if seed is not None:
                with open(os.path.join(memdir, "active_modes.md"), "w") as fh:
                    fh.write(seed)
        else:
            env.pop("CLAUDE_CODE_SESSION_ID", None)
        proc = subprocess.run(
            [sys.executable, SCRIPT, directive],
            cwd=REPO, env=env, capture_output=True, text=True)
        final = None
        fpath = os.path.join(memdir, "active_modes.md")
        if os.path.isfile(fpath):
            with open(fpath) as fh:
                final = fh.read()
        return proc.stdout, proc.returncode, final
    finally:
        shutil.rmtree(home, ignore_errors=True)


def echo_of(stdout):
    """Return the user-echo section (everything below the ECHO delimiter)."""
    assert ECHO_DELIM in stdout, "stdout missing ECHO delimiter"
    return stdout.split(ECHO_DELIM + "\n", 1)[1].rstrip("\n")


def notes_of(stdout):
    """Return the agent-notes section (between the two delimiters)."""
    assert stdout.startswith(AGENT_DELIM + "\n"), "stdout missing AGENT delimiter at top"
    mid = stdout.split(AGENT_DELIM + "\n", 1)[1]
    return mid.split(ECHO_DELIM, 1)[0].rstrip("\n")


def extract_law_block(md_text, key):
    """Pull the text between <!-- LAW:key -->/<!-- /LAW:key --> in SKILL.md, unwrapping a
    ``` fence, so it can be compared byte-for-byte to the script's LAW[key] template."""
    open_m = "<!-- LAW:{} -->".format(key)
    close_m = "<!-- /LAW:{} -->".format(key)
    inner = md_text.split(open_m, 1)[1].split(close_m, 1)[0].strip()
    lines = inner.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)


def run_hook(tool_name, file_path, seed):
    """Run enforce_modes.py with a seeded active_modes.md; return parsed stdout dict or None."""
    home = tempfile.mkdtemp()
    try:
        env = dict(os.environ)
        env["HOME"] = home
        memdir = os.path.join(home, ".claude", "projects", slug_for(REPO), "memory", SID)
        os.makedirs(memdir, exist_ok=True)
        if seed is not None:
            with open(os.path.join(memdir, "active_modes.md"), "w") as fh:
                fh.write(seed)
        payload = json.dumps({
            "tool_name": tool_name,
            "tool_input": {"file_path": file_path},
            "session_id": SID,
            "cwd": REPO,
        })
        proc = subprocess.run([sys.executable, HOOK], input=payload,
                              cwd=REPO, env=env, capture_output=True, text=True)
        out = proc.stdout.strip()
        return json.loads(out) if out else None
    finally:
        shutil.rmtree(home, ignore_errors=True)


def denied(hook_out):
    return bool(hook_out) and hook_out["hookSpecificOutput"]["permissionDecision"] == "deny"


def files_identical(paths):
    blobs = [open(p, "rb").read() for p in paths]
    return all(b == blobs[0] for b in blobs)


def check(name, cond, detail=""):
    global _count
    _count += 1
    if not cond:
        _failures.append("{}  {}".format(name, detail))


AGENT_ONLY = "# Active modes\n\n- agent\n"


def main():
    # 1. absent-file default (agent) — list shows agent
    out, rc, _ = run("list", seed=None)
    check("absent->agent/list", echo_of(out) == "active modes :\n • agent", repr(echo_of(out)))
    check("absent->agent/exit0", rc == 0)

    # 2. plan ./doc displaces agent (mutex line) + writes file
    out, rc, final = run("plan ./doc", seed=AGENT_ONLY)
    e = echo_of(out)
    check("plan/head", e.startswith("mode plan is now active.\nmode agent is now inactive."), repr(e))
    check("plan/list", e.endswith("active modes :\n • plan: ./doc"), repr(e))
    check("plan/file", final == "# Active modes\n\n- plan: ./doc\n", repr(final))
    n = notes_of(out)
    check("plan/notes", "PLAN MODE" in n and "only markdown writes allowed" in n and "BLOCKED" in n, repr(n))
    check("plan/notes-dir", "`./doc`" in n, "plan law must substitute the active dir")
    # the generative encode step must ride along with an active mode's notes
    check("plan/encode", "Predict what active_modes.md" in n and "DERIVE" in n, "encode prompt missing")

    # 3. plan with no dir -> ./
    out, _, final = run("plan", seed=AGENT_ONLY)
    check("plan-nodir/file", final == "# Active modes\n\n- plan: ./\n", repr(final))
    check("plan-nodir/echo", "plan: ./" in echo_of(out))

    # 4. re-entering an active mode -> already active
    out, _, _ = run("sbs", seed="# Active modes\n\n- sbs\n")
    check("already/sbs", echo_of(out).startswith("mode sbs is already active."), repr(echo_of(out)))

    # 5. exit sbs active vs inactive
    out, _, final = run("exit sbs", seed="# Active modes\n\n- agent\n- sbs\n")
    check("exit-active", echo_of(out) == "mode sbs is now inactive.\nactive modes :\n • agent", repr(echo_of(out)))
    check("exit-active/file", final == "# Active modes\n\n- agent\n", repr(final))
    out, _, _ = run("exit sbs", seed=AGENT_ONLY)
    check("exit-inactive", echo_of(out).startswith("mode sbs is not active."), repr(echo_of(out)))

    # 6. list does NOT write a file
    out, _, final = run("list", seed=None)   # no file seeded; list must not create one
    check("list/no-write", final is None, repr(final))

    # 7. clear
    out, _, final = run("clear", seed="# Active modes\n\n- plan: ./doc\n")
    check("clear/echo", echo_of(out) == "all modes cleared.\nactive modes : none", repr(echo_of(out)))
    check("clear/notes", notes_of(out) == "No modes active — full default agency.", repr(notes_of(out)))

    # 8. blank verb -> verbatim help (now ending with the stamped version line), empty notes
    version = json.load(open(os.path.join(REPO, "plugin", ".claude-plugin", "plugin.json")))["version"]
    out, _, final = run("", seed=AGENT_ONLY)
    check("help/version-header", echo_of(out).startswith("Modes · v" + version + ":\n• plan [dir]"), repr(echo_of(out)[:50]))
    check("help/clear-line", "Clear all:  /modes clear" in echo_of(out))
    check("help/empty-notes", notes_of(out) == "", repr(notes_of(out)))
    check("help/no-write", final == AGENT_ONLY, "help must not mutate state")

    # 8b. unknown verb -> help too
    out, _, _ = run("bogusverb", seed=AGENT_ONLY)
    check("unknown/help", echo_of(out).startswith("Modes · v"), repr(echo_of(out)[:30]))

    # 9. exclude appends + dedupes, NOT glob-expanded (single arg)
    out, _, final = run("exclude *.log, *.tmp", seed=AGENT_ONLY)
    check("exclude/echo", echo_of(out).startswith("mode exclude is now active."))
    check("exclude/file", final == "# Active modes\n\n- agent\n- exclude: *.log, *.tmp\n", repr(final))
    out, _, final = run("exclude *.tmp, *.bak", seed="# Active modes\n\n- exclude: *.log, *.tmp\n")
    check("exclude/append", final == "# Active modes\n\n- exclude: *.log, *.tmp, *.bak\n", repr(final))
    check("exclude/append-echo", echo_of(out).startswith("mode exclude is now active."), "added -> now active")
    out, _, final = run("exclude *.log", seed="# Active modes\n\n- exclude: *.log, *.tmp\n")
    check("exclude/nodup-echo", echo_of(out).startswith("mode exclude is already active."), "no new -> already")
    check("exclude/nodup-file", final == "# Active modes\n\n- exclude: *.log, *.tmp\n", repr(final))

    # 10. include
    out, _, final = run("include src/**/*.ts", seed=AGENT_ONLY)
    check("include/file", final == "# Active modes\n\n- agent\n- include: src/**/*.ts\n", repr(final))

    # 11. exit exclude clears the whole set
    out, _, final = run("exit exclude", seed="# Active modes\n\n- exclude: *.log, *.tmp\n")
    check("exit-exclude", final == "# Active modes\n\n", repr(final))
    check("exit-exclude/echo", echo_of(out) == "mode exclude is now inactive.\nactive modes : none", repr(echo_of(out)))

    # 12. alphabetized ordering + compound-param rendering
    out, _, _ = run("list", seed="# Active modes\n\n- plan: ./src\n- exclude: *.log, *.tmp\n")
    check("alpha", echo_of(out) == "active modes :\n • exclude: *.log, *.tmp\n • plan: ./src", repr(echo_of(out)))

    # 13. pre-2.0 normalization on read (one word / SBS) — normalized in echo
    out, _, final = run("list", seed="# Active modes\n\n- one word\n- SBS\n")
    check("norm/echo", echo_of(out) == "active modes :\n • one-word\n • sbs", repr(echo_of(out)))
    check("norm/no-rewrite-on-list", final == "# Active modes\n\n- one word\n- SBS\n", "list must not rewrite (decision 3)")
    # ...but a state-mutating verb rewrites normalized
    out, _, final = run("agent", seed="# Active modes\n\n- one word\n- SBS\n")
    check("norm/rewrite-on-write", final == "# Active modes\n\n- agent\n- one-word\n- sbs\n", repr(final))

    # 14. no session id -> prints echo, writes NO file
    out, rc, final = run("plan ./doc", with_session=False)
    check("no-session/echo", "mode plan is now active." in echo_of(out))
    check("no-session/no-file", final is None, "must not write without a session id")
    check("no-session/exit0", rc == 0)

    # 15. every stdout carries both delimiters
    out, _, _ = run("list", seed=AGENT_ONLY)
    check("delims", out.startswith(AGENT_DELIM + "\n") and ECHO_DELIM + "\n" in out)

    # 16. SKILL.md's LAW:plan block is byte-identical to the script's LAW["plan"] (no drift)
    with open(SKILL_MD, encoding="utf-8") as fh:
        md = fh.read()
    check("law/drift", extract_law_block(md, "plan") == modes_mod.LAW["plan"],
          "SKILL.md LAW:plan must match script LAW['plan'] verbatim (template form)")

    # 18. PreToolUse hook — mechanical enforcement of the write-blocking modes
    PLAN = "# Active modes\n\n- plan: ./doc\n"
    check("hook/plan-blocks-nonmd", denied(run_hook("Write", "/proj/foo.py", PLAN)))
    check("hook/plan-allows-md", run_hook("Write", "/proj/notes.md", PLAN) is None)
    check("hook/plan-allows-planmd", run_hook("Write", "/proj/x.plan.md", PLAN) is None)
    check("hook/agent-allows-py", run_hook("Write", "/proj/foo.py", AGENT_ONLY) is None)
    check("hook/non-write-ignored", run_hook("Read", "/proj/foo.py", PLAN) is None)
    EXC = "# Active modes\n\n- exclude: *.log\n"
    check("hook/exclude-blocks", denied(run_hook("Edit", "/proj/a.log", EXC)))
    check("hook/exclude-allows", run_hook("Edit", "/proj/a.txt", EXC) is None)
    INC = "# Active modes\n\n- include: src/**/*.ts\n"
    check("hook/include-blocks-nonmatch", denied(run_hook("Write", os.path.join(REPO, "other.py"), INC)))
    check("hook/include-allows-nested", run_hook("Write", os.path.join(REPO, "src/deep/a.ts"), INC) is None)
    check("hook/include-allows-shallow", run_hook("Write", os.path.join(REPO, "src/a.ts"), INC) is None)

    # 20. agent-loop — clear-on-entry, three-way mutex, layering, idempotent re-entry,
    # the two-word guard, the LAW byte-lock, and hook inertness.
    out, _, final = run("agent-loop", seed="# Active modes\n\n- exclude: *.log\n- plan: ./doc\n")
    e = echo_of(out)
    check("aloop/clear-echo", e.startswith(
        "mode agent-loop is now active.\nmode exclude is now inactive.\nmode plan is now inactive."), repr(e))
    check("aloop/clear-list", e.endswith("active modes :\n • agent-loop"), repr(e))
    check("aloop/clear-file", final == "# Active modes\n\n- agent-loop\n", repr(final))
    n = notes_of(out)
    check("aloop/notes-law", "AGENT-LOOP MODE" in n, repr(n[:80]))
    check("aloop/notes-invariant",
          "The binding check is at the LANDING" in n,
          "landing-bound invariant missing from notes")
    # the six bullets added in the portability pass, plus the write-don't-build and
    # drain clauses — one stable substring each, against the emitted notes
    LAW_AL = modes_mod.LAW["agent-loop"]
    # IN THE LAW — needed EVERY turn or EVERY spawn, so it must survive without a lookup.
    check("aloop/law-status-flips", "flip the unit to in_progress" in LAW_AL)
    check("aloop/law-arm-first", "arm FIRST on seeded and resumed turns" in LAW_AL)
    check("aloop/law-reentry-text", "never a generic sentinel" in LAW_AL)
    check("aloop/law-worker-fence", "NEVER add-all" in LAW_AL)
    check("aloop/law-resource-gates", "gate exclusive resources" in LAW_AL)
    # NEW — the measurement discipline. The first is a note (nothing forces it); the second
    # is the load-bearing half, because it puts the obligation in the OUTPUT FORMAT, where a
    # bare number is visibly incomplete to any reader rather than failing silently.
    check("aloop/law-spec-before-tool", "BEFORE NAMING ANY TOOL" in LAW_AL)
    check("aloop/law-number-carries-check",
          "WITH THE OUTPUT OF ITS CHECK BESIDE IT" in LAW_AL)
    check("aloop/law-retooling-is-work", "re-tooling produces nothing visible" in LAW_AL)
    # RELOCATED TO THE BODY — needed ONCE per engagement or on a rare event, so it is lookup
    # rather than law. These assertions still guarantee the lesson EXISTS; they no longer
    # guarantee it is in working memory on wake. That is a deliberate trade for density:
    # see "Where the mechanism went" in SKILL.md.
    check("aloop/body-never-cron", "never cron for the heartbeat" in md)
    check("aloop/body-write-dont-build", "leave it UNBUILT" in md)
    check("aloop/body-rollover-drain", "drain in-flight work first" in md)
    check("aloop/body-log-ladder", "<ccvi-autonomy-log>" in md)
    check("aloop/body-log-fallback", "<docDir>/logs/autonomy" in md)
    check("aloop/body-log-hands-off-git", "NEVER a .gitignore edit" in md)
    check("aloop/body-plan-surfacing", "plan surfacing" in md)
    # the instrument order-of-operations the measurement bullet points at
    check("aloop/body-instrument-steps", "Choosing an instrument" in md)
    check("aloop/body-instrument-spec-numbers", "A spec with no numbers in it is not a spec" in md)
    check("aloop/body-mechanism-relocation", "Where the mechanism went" in md)
    # SKILL.md prose (not LAW): the doc-dir hint and the phrase keeping it out of rung 1
    check("aloop/docdir-hint", "<ccvi-doc-dir>" in md,
          "the <ccvi-doc-dir> hint is missing from the ladder prose")
    check("aloop/docdir-not-a-rung", "never a rung-1 hit" in md,
          "the phrase keeping the doc-dir hint out of rung 1 is missing")
    # the machine-grabbing bookends bullet was cut with no trace
    for gone in ("Stop/Start bookends", "desktop hide", "machine-grabbing"):
        check("aloop/law-cut[{}]".format(gone), gone not in LAW_AL,
              "removed bookends text still present")
    # the project-root log destination was replaced by the resolution ladder
    for gone in ("at the project root",):
        check("aloop/law-cut[{}]".format(gone), gone not in LAW_AL,
              "old project-root log destination still present")
    check("aloop/notes-dormant", "DORMANT" in n, "dormant-entry clause missing from notes")
    check("aloop/encode", "Predict what active_modes.md" in n and "DERIVE" in n, "encode prompt missing")
    # The agent-loop-specific ask. The law block was cut ~60% on the argument that repetition
    # and derivation are substitutes; this is the derivation half. Shipping the cut without it
    # would leave the mode binding LESS than before. It is ONE question and FALSIFIABLE — a
    # prediction about this turn's landing, which reality settles minutes later.
    check("aloop/encode-landing-ask", "predict now, in one sentence, what THIS TURN'S LANDING" in n,
          "agent-loop's falsifiable landing ask missing from the notes")
    check("aloop/encode-ask-ordering", n.index("AGENT-LOOP — predict now") < n.index("If you jumped straight"),
          "the landing ask must read as item 4, before the closing exhortation")
    # mutex displacement both ways
    out, _, final = run("plan ./doc", seed="# Active modes\n\n- agent-loop\n")
    check("aloop/plan-displaces", "mode agent-loop is now inactive." in echo_of(out), repr(echo_of(out)))
    check("aloop/plan-file", final == "# Active modes\n\n- plan: ./doc\n", repr(final))
    out, _, final = run("agent", seed="# Active modes\n\n- agent-loop\n")
    check("aloop/agent-displaces", "mode agent-loop is now inactive." in echo_of(out), repr(echo_of(out)))
    check("aloop/agent-file", final == "# Active modes\n\n- agent\n", repr(final))
    # compose modes layer on AFTER entry
    out, _, final = run("include src/**/*.ts", seed="# Active modes\n\n- agent-loop\n")
    check("aloop/layering", final == "# Active modes\n\n- agent-loop\n- include: src/**/*.ts\n", repr(final))
    # idempotent re-entry: layered modes survive
    out, _, final = run("agent-loop", seed="# Active modes\n\n- agent-loop\n- sbs\n")
    check("aloop/reenter-echo", echo_of(out).startswith("mode agent-loop is already active."), repr(echo_of(out)))
    check("aloop/reenter-file", final == "# Active modes\n\n- agent-loop\n- sbs\n", repr(final))
    # two-word guard, enter + exit
    out, _, _ = run("agent loop", seed=AGENT_ONLY)
    check("aloop/two-word-enter", echo_of(out).startswith("mode agent-loop is now active."), repr(echo_of(out)))
    out, _, _ = run("exit agent loop", seed="# Active modes\n\n- agent-loop\n")
    check("aloop/two-word-exit", echo_of(out).startswith("mode agent-loop is now inactive."), repr(echo_of(out)))
    # LAW byte-lock (template form), alongside check 16's plan law
    check("aloop/law-drift", extract_law_block(md, "agent-loop") == modes_mod.LAW["agent-loop"],
          "SKILL.md LAW:agent-loop must match script LAW['agent-loop'] verbatim")
    # hook inertness — agent-loop is not a write filter
    check("aloop/hook-noop", run_hook("Write", "/proj/foo.py", "# Active modes\n\n- agent-loop\n") is None)

    # 21. agent-loop's optional rollover threshold — storage, validation (refuse, never
    # clamp), exclude-shaped re-entry, and the param's effect on echo/blurb/help/hook.
    out, _, final = run("agent-loop 20", seed=AGENT_ONLY)
    e = echo_of(out)
    check("pct/store-file", final == "# Active modes\n\n- agent-loop: 20\n", repr(final))
    check("pct/store-list", e.endswith("active modes :\n • agent-loop: 20"), repr(e))
    check("pct/blurb", "hand-off at 20% context usage" in e, "blurb must carry the threshold")
    check("pct/displaces", "mode agent is now inactive." in e, repr(e))
    # law bullets ride in the notes (byte-lock in check 20 guards drift; these guard removal)
    n = notes_of(out)
    check("pct/notes-rollover", "• rollover threshold — when the mode entry carries a percentage" in n,
          "rollover bullet missing from the agent-loop law")
    # RELOCATED: hand-off pacing matters only at a hand-off, so it is body lookup now.
    check("pct/body-pace", "pace hand-offs" in open(SKILL_MD, encoding="utf-8").read(),
          "pacing guidance missing from SKILL.md")
    # refuse out-of-range / non-numeric: non-zero exit (-> model asks), state untouched
    for bad in ("agent-loop 19", "agent-loop 5", "agent-loop 100", "agent-loop abc"):
        out, rc, final = run(bad, seed=AGENT_ONLY)
        check("pct/reject-rc[{}]".format(bad), rc != 0, "expected non-zero exit, got {}".format(rc))
        check("pct/reject-nowrite[{}]".format(bad), final == AGENT_ONLY, repr(final))
    # boundaries are INCLUSIVE
    _, _, final = run("agent-loop 99", seed=AGENT_ONLY)
    check("pct/ceiling-ok", final == "# Active modes\n\n- agent-loop: 99\n", repr(final))
    # bare re-entry preserves the stored threshold ("already active", nothing erased)
    out, _, final = run("agent-loop", seed="# Active modes\n\n- agent-loop: 20\n")
    check("pct/bare-reenter-echo", echo_of(out).startswith("mode agent-loop is already active."), repr(echo_of(out)))
    check("pct/bare-reenter-file", final == "# Active modes\n\n- agent-loop: 20\n", repr(final))
    check("pct/bare-reenter-blurb", "hand-off at 20% context usage" in echo_of(out), "stored pct must still render")
    # same-N re-entry is likewise idempotent
    out, _, final = run("agent-loop 20", seed="# Active modes\n\n- agent-loop: 20\n")
    check("pct/same-reenter", echo_of(out).startswith("mode agent-loop is already active."), repr(echo_of(out)))
    check("pct/same-reenter-file", final == "# Active modes\n\n- agent-loop: 20\n", repr(final))
    # a NEW value updates in place, echoes "now active", and does NOT re-clear layered modes
    out, _, final = run("agent-loop 35", seed="# Active modes\n\n- agent-loop: 20\n- one-word\n")
    e = echo_of(out)
    check("pct/update-echo", e.startswith("mode agent-loop is now active."), repr(e))
    check("pct/update-no-reclear", "is now inactive." not in e, "re-entry must not displace layered modes")
    check("pct/update-file", final == "# Active modes\n\n- agent-loop: 35\n- one-word\n", repr(final))
    # clear-on-entry still fires for a FRESH parameterized entry
    out, _, final = run("agent-loop 40", seed="# Active modes\n\n- exclude: *.log\n- plan: ./doc\n")
    e = echo_of(out)
    check("pct/fresh-clears", e.startswith(
        "mode agent-loop is now active.\nmode exclude is now inactive.\nmode plan is now inactive."), repr(e))
    check("pct/fresh-clears-file", final == "# Active modes\n\n- agent-loop: 40\n", repr(final))
    # the two-word guard carries a trailing threshold through
    _, _, final = run("agent loop 25", seed=AGENT_ONLY)
    check("pct/two-word-param", final == "# Active modes\n\n- agent-loop: 25\n", repr(final))
    # leading zeros normalize; the help line advertises the param
    _, _, final = run("agent-loop 020", seed=AGENT_ONLY)
    check("pct/normalize", final == "# Active modes\n\n- agent-loop: 20\n", repr(final))
    out, _, _ = run("", seed=AGENT_ONLY)
    check("pct/help-line", "• agent-loop [pct] — autonomous keep-moving loop; hand-off at pct% context (20-99);"
          in echo_of(out), repr(echo_of(out)))
    # a parameterized entry stays inert to the write hook
    check("pct/hook-noop", run_hook("Write", "/proj/foo.py", "# Active modes\n\n- agent-loop: 20\n") is None)

    # 22. THE ANTI-EROSION GUARD. Each pinned phrase in this file is a lesson someone decided
    # was load-bearing; prose lessons decay silently, a pinned one cannot. On 2026-09-10 this
    # harness refused two cuts during a law compression and was right both times.
    # The guard distinguishes EROSION from RELOCATION on purpose: deleting a check drops the
    # count and fails here, while re-pointing one (law -> body) keeps the count and passes,
    # because the lesson still exists. Raise MIN_CHECKS when you add checks; LOWERING it is
    # the move this guard exists to make visible, and it is a stop-and-ask, not a judgment
    # call.
    # the floor is asserted in the Report block below, outside check(), so the guard never
    # has to reason about whether it counts itself.
    # the agent-loop ask is scoped: other modes must not inherit it
    out, _, _ = run("plan ./doc", seed=AGENT_ONLY)
    check("harness/ask-scoped", "THIS TURN'S LANDING" not in notes_of(out),
          "the agent-loop landing ask leaked into a non-agent-loop mode")

    # THE ANTI-EROSION FLOOR (see the guard comment above). Deleting a check drops the count
    # and fails here; re-pointing one (law -> body) keeps it and passes, because the lesson
    # still exists. Raise it when you add checks. LOWERING it is the act this floor exists to
    # make visible — treat that as a stop-and-ask, not a judgment call.
    MIN_CHECKS = 124
    if _count < MIN_CHECKS:
        _failures.append(
            "harness/no-erosion  check count {} is below the floor {} — a tripwire was "
            "REMOVED rather than relocated".format(_count, MIN_CHECKS))

    # Report
    if _failures:
        print("plan/test FAIL — {} of {} checks failed:".format(len(_failures), _count))
        for f in _failures:
            print("  - " + f)
        return 1
    print("test_modes OK — {} checks passed".format(_count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
