#!/usr/bin/env python3
"""
modes.py — the fast path for the /modes skill.

Does everything the modes SKILL.md describes, deterministically, in one process:
- resolve the session id
- read the per-session active_modes.md
- parse a /modes directive
- compute the next state(s)
- write the file
- print a TWO-SECTION stdout: agent-facing notes, a delimiter, then the exact
  user-facing echo

The model's job around this script is trivial: run it, read the agent-notes above the
`===MODES_USER_ECHO===` delimiter and enforce them, print everything below the delimiter
verbatim, and only if the script fails (non-zero exit / no python / empty stdout) fall
back to the markdown logic in SKILL.md.

Contract:
  argv[1] = the raw directive — everything the user typed after "/modes", passed as a
            SINGLE quoted argument so the shell never glob-expands patterns like *.log.
            Examples: "plan ./doc", "exit sbs", "list", "clear", "exclude *.log, *.tmp",
            "" (blank -> help).

  stdout  = two sections split by delimiters:

              ===MODES_AGENT_NOTES===
              <private guidance for the agent — the behavioral contract for the modes
               active after this change; the agent internalizes and enforces it but
               NEVER displays it>
              ===MODES_USER_ECHO===
              <the exact echo-contract text, printed to the user verbatim>

  exit 0  = success (relay the user-echo section).
  exit !0 = failure (model falls back to SKILL.md logic). We print nothing to stdout on
            failure; any diagnostic goes to stderr.

Stdlib only. No third-party imports. Targets Python 3.9+ (the macOS Command Line Tools
system Python is frozen at 3.9.6; avoid 3.10+-only syntax).
"""

import os
import re
import sys
import glob


# --------------------------------------------------------------------------------------
# Delimiters — the dual-section contract. Blunt and collision-proof so the split
# instruction in SKILL.md is unambiguous and the agent-notes never leak to the user.
# --------------------------------------------------------------------------------------

AGENT_DELIM = "===MODES_AGENT_NOTES==="
ECHO_DELIM = "===MODES_USER_ECHO==="


# --------------------------------------------------------------------------------------
# Constants — the echo strings are load-bearing and mirror SKILL.md's contract; the
# golden tests assert byte-equality, so do not "improve" the wording or punctuation.
# --------------------------------------------------------------------------------------

DEFAULT_MODE = "agent"

# Simple (non-compound) modes and the mutually-exclusive stance group. plan / agent /
# agent-loop are a three-way mutex: entering any one displaces whichever sibling is
# active. agent-loop needs no MUTEX entry of its own — entering it clears EVERY other
# active mode (clear-on-entry subsumes the mutex).
SIMPLE_MODES = {"agent", "plan", "agent-loop", "one-word", "sbs", "exclude", "include"}
# Modes that render with a param. `agent-loop`'s is OPTIONAL — a bare `- agent-loop`
# entry (no threshold) is equally valid, so it renders compound only when one is stored.
COMPOUND_MODES = {"plan", "exclude", "include", "agent-loop"}

# agent-loop's optional rollover threshold: an integer percentage of context usage at
# which the session hands off to a fresh one. Floor 20 (below that a session rolls over
# before doing meaningful work), ceiling 99. Out-of-range is REFUSED, never clamped.
AGENT_LOOP_PCT_MIN = 20
AGENT_LOOP_PCT_MAX = 99
MUTEX = {"plan": ("agent", "agent-loop"), "agent": ("plan", "agent-loop")}

# One-line blurb emitted with each enter echo. `plan` is a template: {dir} is the active
# plan directory, substituted at render time. The plan blurb reflects the softened rule
# (default to the dir, not confined to it).
PLAN_BLURB = ("new `*.plan.md` default to `{dir}` (default `./`), or elsewhere if you ask; "
              "create/edit/copy/move/rename any existing `.md` anywhere — only delete is "
              "forbidden; non-markdown writes blocked. Produce a `*.plan.md`")
BLURBS = {
    "agent": "full agency; the default working stance",
    "agent-loop": "the autonomous flywheel — dormant until work starts, then at least "
                  "one sub-agent always running + a wakeup always armed; only the "
                  "blocker taxonomy stops forward motion",
    "one-word": "responses are a single word",
    "sbs": "step-by-step; one step then wait for 'done'",
    "exclude": "block writes matching listed patterns",
    "include": "only allow writes matching listed patterns",
}

HELP_TEXT = """Modes · v0.0.0:
• plan [dir] — new *.plan.md created in [dir] (default ./); edit/copy/move any existing .md anywhere; md-delete & non-md writes blocked; mutex with agent
• agent — full agency; mutex with plan
• agent-loop [pct] — autonomous keep-moving loop; hand-off at pct% context (20-99); clears all modes on entry; mutex with plan/agent
• one-word — single-word responses
• sbs — step-by-step; one step then wait
• exclude <globs> — block writes matching globs
• include <globs> — only allow writes matching globs

Enter:      /modes <mode-name> [param]
Exit:       /modes exit <mode-name>
List:       /modes list
Clear all:  /modes clear
"""


# --------------------------------------------------------------------------------------
# State model
#
# The active modes are a dict mapping mode-name -> param (or None for simple modes).
# Insertion order does not matter — the echo always alphabetizes.
#   `exclude` / `include` -> a list of glob patterns.
#   `plan`                -> the directory string.
#   others                -> None.
# --------------------------------------------------------------------------------------


def resolve_memory_root():
    """
    Return (session_dir, sid) where session_dir is `<auto-memory>/<session_id>/`, or
    (None, None) if there is no resolvable session id — in which case
    we run in-context only and never touch the filesystem.

    Auto-memory root is `$HOME/.claude/projects/<slug>/memory`, where <slug> is the
    project directory with '/' replaced by '-'. For robustness on reads, if the
    cwd-derived path has no session dir yet, we glob every project for the session id.
    """
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid:
        return None, None

    home = os.path.expanduser("~")

    # Primary: derive the project slug from the current working directory.
    cwd = os.getcwd()
    slug = cwd.replace("/", "-")
    primary = os.path.join(home, ".claude", "projects", slug, "memory")
    session_dir = os.path.join(primary, sid)

    # If a session dir already exists under the primary slug, use it.
    if os.path.isdir(session_dir):
        return session_dir, sid

    # Read-robustness: the file may live under a different project slug (e.g. the skill
    # was invoked from a subdir). Session ids are globally unique, so a glob is safe.
    pattern = os.path.join(home, ".claude", "projects", "*", "memory", sid, "active_modes.md")
    matches = glob.glob(pattern)
    if len(matches) == 1:
        return os.path.dirname(matches[0]), sid

    # Nothing exists yet (first run) — create under the cwd-derived slug.
    return session_dir, sid


def normalize_mode_name(name):
    """
    Pre-2.0.0 normalization: `one word` (space) -> `one-word`; lowercase everything
    (so `SBS` -> `sbs`). Also folds `agent loop` (space) -> `agent-loop`, covering
    hand-edited state files and multi-word `exit` targets. Returns the canonical name.
    """
    n = name.strip().lower()
    if n == "one word":
        return "one-word"
    if n == "agent loop":
        return "agent-loop"
    return n


def read_state(session_dir):
    """
    Read active_modes.md into a dict {mode: param}. Absent file / no session -> default
    (`agent`). Applies pre-2.0.0 normalization on read.
    """
    if session_dir is None:
        return {DEFAULT_MODE: None}

    path = os.path.join(session_dir, "active_modes.md")
    if not os.path.isfile(path):
        return {DEFAULT_MODE: None}

    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    # The file is a markdown bullet list under a "# Active modes" header (see
    # render_state_file). We scan only the "- <name>[: <param>]" bullets and ignore
    # everything else (header, blanks), so a stray hand-edit to the file can't crash us.
    state = {}
    for line in lines:
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:].strip()  # drop the "- " bullet marker
        # A compound mode carries a param after a colon ("plan: ./doc",
        # "exclude: *.log, *.tmp"); a simple mode is just its bare name.
        if ":" in body:
            name, param = body.split(":", 1)
            name = name.strip()
            param = param.strip()
        else:
            name, param = body, None

        name = normalize_mode_name(name)  # fold pre-2.0 spellings on read

        # Store the param in the shape each mode expects: a pattern LIST for
        # exclude/include, the dir STRING for plan, the threshold STRING (or None when
        # the entry is bare) for agent-loop, None for the simple modes.
        if name in ("exclude", "include"):
            patterns = [p.strip() for p in param.split(",")] if param else []
            state[name] = [p for p in patterns if p]  # drop empties
        elif name == "plan":
            state[name] = param if param else "./"
        elif name == "agent-loop":
            state[name] = param if param else None  # optional threshold; bare is valid
        else:
            state[name] = None

    # An empty or fully malformed file is equivalent to "no state" -> default agent mode.
    if not state:
        state = {DEFAULT_MODE: None}

    return state


def render_mode_entry(name, param):
    """Render a single mode as it appears in a list — with its param when compound.

    Shared by the user echo ("plan: ./doc", "exclude: *.log, *.tmp") and the on-disk state
    file, so this render and the parse in read_state stay mirror images of each other.
    """
    if name in ("exclude", "include"):
        patterns = param or []
        return "{}: {}".format(name, ", ".join(patterns))
    if name == "plan":
        return "plan: {}".format(param if param else "./")
    if name == "agent-loop" and param:
        return "agent-loop: {}".format(param)  # threshold set; bare falls through below
    return name  # simple mode -> just its name


def render_state_file(state):
    """Serialize the state dict back to active_modes.md text (alphabetized)."""
    out = ["# Active modes", ""]
    for name in sorted(state.keys()):
        out.append("- " + render_mode_entry(name, state[name]))
    return "\n".join(out) + "\n"


def write_state(session_dir, state):
    """Write the state file, creating the session dir if needed."""
    os.makedirs(session_dir, exist_ok=True)
    path = os.path.join(session_dir, "active_modes.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_state_file(state))


# --------------------------------------------------------------------------------------
# Echo rendering (the USER-facing section)
# --------------------------------------------------------------------------------------


def blurb_for(mode, param):
    """The one-line blurb for an enter echo. `plan` substitutes its active directory;
    `agent-loop` appends its rollover threshold when one is stored (bare -> static blurb)."""
    if mode == "plan":
        return PLAN_BLURB.format(dir=(param if param else "./"))
    if mode == "agent-loop" and param:
        return BLURBS["agent-loop"] + "; hand-off at {}% context usage".format(param)
    return BLURBS.get(mode, "")


def render_active_list(state):
    """The 'active modes :' block. Alphabetized, one ' • ' bullet per line, or inline none."""
    if not state:
        return "active modes : none"
    lines = ["active modes :"]
    for name in sorted(state.keys()):
        lines.append(" • " + render_mode_entry(name, state[name]))
    return "\n".join(lines)


def enter_echo(mode, param, new_state, displaced, already):
    """Build the enter echo — the exact user-facing text for a `/modes <mode>` directive.

    `already`   -> the mode was already in the set (re-entered): the shorter echo variant.
    `displaced` -> the LIST of modes this enter turned off (a mutex sibling, or every
                   cleared mode for agent-loop's clear-on-entry); one "is now inactive"
                   line per entry, in the order given — no lines when nothing displaced.
    Wording/punctuation here is byte-locked by the golden tests — don't tweak it.
    """
    blurb = blurb_for(mode, param)
    if already:
        return "mode {m} is already active.\nmode {m} : {b}\n{lst}".format(
            m=mode, b=blurb, lst=render_active_list(new_state))
    lines = ["mode {} is now active.".format(mode)]
    for d in (displaced or []):  # mutex displacement or agent-loop's clear-on-entry
        lines.append("mode {} is now inactive.".format(d))
    lines.append("mode {} : {}".format(mode, blurb))
    lines.append(render_active_list(new_state))
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# Agent-notes rendering (the PRIVATE section — the per-mode behavioral contract).
#
# These LAW strings are the FULL, first-order enforcement contract — NOT a paraphrase.
# Pre-4.1 the notes were a 4-line summary and the strong prose lived only in SKILL.md;
# the summary was too weak to carry across a directive-less gap, so the agent would drift
# (e.g. do a non-markdown write while plan mode was active). The fix: emit the real law
# here, on EVERY directive, VERBATIM to the text between the matching
# <!-- LAW:x -->/<!-- /LAW:x --> markers in SKILL.md. test_modes.py locks byte-equality
# so the script and the markdown can never drift. `{dir}`/`{pats}` substitute at render.
#
# The script is only bookkeeping — it never discharges enforcement; that is the agent's
# job every turn. The plugin ALSO ships a PreToolUse hook (hooks/enforce_modes.py)
# that mechanically blocks a violating Write/Edit, so compliance does not rely on the
# agent's memory.
# --------------------------------------------------------------------------------------

LAW = {
    "plan": (
        "⛔ PLAN MODE — a HARD write filter, in force on EVERY turn until you exit. "
        "Running the fast-path script does NOT discharge it; enforcement is yours every "
        "turn, script or not. BEFORE any Write or Edit, check the target file type:\n"
        "• new *.plan.md → default to `{dir}`; elsewhere only if the user explicitly asks "
        "(then do it, don't refuse)\n"
        "• edit / copy / move / rename any EXISTING .md → allowed anywhere; note the "
        "operation in one line as you do it\n"
        "• delete markdown → BLOCKED; archive (move) it instead and decline the delete "
        "plainly\n"
        "• any NON-markdown write (.py .json .ts .zip …) → BLOCKED; decline with "
        "\"can't — plan mode; only markdown writes allowed\", then offer to exit plan mode "
        "(/modes agent) if they want it done\n"
        "• Read / Glob / Grep / read-only Bash → unaffected\n"
        "If you are about to write a non-.md file you have already erred — refuse and "
        "surface it; never \"just this once\"."
    ),
    "agent": (
        "AGENT MODE — full agency, the default working stance. No plan-mode write filter; "
        "any other active modes (include / exclude / one-word / sbs) still bind."
    ),
    "agent-loop": (
        "⛔ AGENT-LOOP MODE — a standing keep-moving contract, in force on EVERY turn until the "
        "user exits it. Running the fast-path script does NOT discharge it; enforcement is yours "
        "every turn, script or not. Entering the mode is DORMANT arming only — it starts no "
        "work, schedules no wakeup, spawns nothing; turns end normally while no work is "
        "assigned. The MOMENT work starts (you are told the work, or you begin work already "
        "known), the flywheel engages:\n"
        "• the standing invariant — taking on work means spawning the first sub-agent AND arming "
        "the fallback wakeup immediately, in the same turn; when independent units exist, run as "
        "many sub-agents in parallel as the work supports — one is the floor, not the target. "
        "Delegation is the strong default, with workers one model tier down per the "
        "model-economy bullet; doing a unit yourself in the same turn is legitimate ONLY when it "
        "is too interpretive to delegate. The binding check is at the LANDING: no turn ends with "
        "work remaining unless work is IN FLIGHT (per the wake-source bullet) and a fallback "
        "wakeup is ARMED, both together — a wakeup armed with nothing in flight is NOT "
        "compliance (the wakeup is insurance behind running work, never a schedule), and solo "
        "work is compliance only while the turn lasts, never a state to land in\n"
        "• where the work is tracked in a live plan or status surface, keep it truthful in real "
        "time — flip the unit to in_progress as part of committing to it (deploying a worker on "
        "it IS that first action: flip at the launch, never after the worker returns), flip to "
        "completed only after its done-when is verified (a worker's self-report is evidence, not "
        "the verdict), and flip to a truthful terminal state promptly on a bail or kill; every "
        "flip is the orchestrator's — a worker never touches the plan or status surface, and its "
        "brief says so\n"
        "• every wake event re-establishes the invariant FIRST — a returning worker spawns its "
        "successor immediately (its return is itself a wake source); a wakeup firing while work "
        "is still in flight just re-arms; a wakeup firing with NOTHING in flight spawns before "
        "anything else; only work-complete or a true blocker ends the loop. In-flight work means "
        "running sub-agents first; a harness-tracked background job (a build, a long test — "
        "anything that re-invokes you on completion) counts ONLY while no independently "
        "delegable unit sits unspawned — waiting is never the only activity, and a long job "
        "running never excuses an empty worker pool while parallel units exist. The fallback "
        "wakeup is LONG (20+ minutes), armed behind in-flight work as insurance against a hang — "
        "never a short poll, and never the sole wake source\n"
        "• arm FIRST on seeded and resumed turns — a turn that opens from a hand-off replay, a "
        "session resume, or a recovery nudge arms its fallback wakeup as its FIRST action, "
        "before any work: every wake source is armed by a tool call, so a turn that dies before "
        "its first call leaves NOTHING armed and the session sits dead until a human notices; "
        "arming first shrinks that naked window to near zero\n"
        "• never cron for the heartbeat — scheduled cloud agents and new-instance spawners are "
        "NOT wake sources: they spawn fresh sessions with fresh context, defeating the "
        "same-session point of the loop; the heartbeat is an in-session wakeup armed behind "
        "in-flight work, or nothing\n"
        "• every wakeup carries this mode's own re-entry text as its prompt, never a generic "
        "sentinel — a host's default wakeup framing is conservative (\"steward; when quiet, "
        "stop\"), and as the LAST instruction read on wake it out-competes this law by recency; "
        "arm with the loop's re-entry brief instead: re-enter agent-loop, reconstruct from the "
        "plan statuses and the log tail, re-establish the invariant, continue from the NEXT line\n"
        "• report execution state truthfully — \"stopped, nothing will wake me\" is a sentence to "
        "WRITE, never a state to conceal; a turn ending on a wait names what is running, its "
        "expected duration, and what wakes it; turn summaries lead with what happened and never "
        "promise work the turn didn't do; a milestone summary is not a stopping point — "
        "summarize, then keep working or arm in the same turn\n"
        "• decide-log-continue — make the best call under the project's stated guidance (specs, "
        "plans, conventions; absent those, the most defensible reading of intent), log decision "
        "+ rationale + the NEXT unit, and keep going; the log is this engagement's "
        "autonomy_log_<session>_<NN>.md at the project root (fresh file per engagement, "
        "materialized on first entry, seeded with a ≤10-line digest of the newest predecessor's "
        "tail) or wherever the project already keeps its log, with each new entry echoed in the "
        "turn's report — where no writable project exists, the echoed entry itself is the log; a "
        "wrong-but-logged call beats a stalled session, and entering this mode accepts that "
        "rollback risk; cost and effort forecasts are NEVER a reason to stop, shrink, or ask — "
        "your forecasts run in human-engineer units and are reliably wrong; when a fork's "
        "recommended option is \"keep going\", TAKE it\n"
        "• stop-and-ask ONLY for: contradicting the project's stated guidance with no compliant "
        "path; a compounding, hard-to-reverse fork the guidance genuinely cannot arbitrate; "
        "destructive actions; real-world money (purchases, paid services — NOT token/compute "
        "spend, which entering the mode accepts) — everything else is decide-log-continue\n"
        "• every worker brief draws its fence — it names what the worker owns (its unit, its "
        "files) and what it must never touch: the plan file, the autonomy log, and other units' "
        "files; a worker commits only its own named pathspec or nothing at all — NEVER add-all, "
        "which sweeps racing siblings' edits and the orchestrator's flips into its commit; the "
        "worker's model and effort ride in the brief per the model-economy bullet\n"
        "• gate exclusive resources — a resource only one worker can safely hold (a heavy build "
        "slot, a port, a device or display, a shared fixture) gets AT MOST ONE holder at a time; "
        "a spawn moment with the slot taken hands the new worker non-conflicting work (docs, "
        "plans, read-only analysis) instead of a queue position or a double-booking — the "
        "invariant's \"as many as the work supports\" means exactly this\n"
        "• model economy — sub-agents default one model tier DOWN from the session: spend tokens "
        "on judgment, not typing; step down FURTHER when the brief is paint-by-numbers (exact "
        "files, exact edits, fixed verification — the test: a brief that survives literal "
        "execution with zero judgment calls does not need the judgment tier); never spawn at "
        "your own tier without a specific, logged reason; a brief too vague for the tier below "
        "is a brief to sharpen before spawning anyone. Where the host exposes a reasoning-effort "
        "dial for workers, it follows the same gradient — low effort for mechanical briefs, high "
        "effort reserved for judgment-heavy units. No tension with \"cost is never a reason\": "
        "that governs the WORK, this governs who executes it — do the expensive thing, on the "
        "cheapest model and effort that do it faithfully\n"
        "• rollover threshold — when the mode entry carries a percentage (`agent-loop: N`), "
        "treat N% context usage as the hand-off point: drain in-flight work first — a successor "
        "cannot receive a worker's return; finish or land the current units and spawn nothing "
        "new (a background job's on-disk artifacts DO survive — name them in the seed so the "
        "successor harvests them) — then author the hand-off with `/seedprompt write` and "
        "request the fresh session: on a host with a rollover relay, create an empty "
        "`rollover.request` beside the seed in the memory root and end the turn; on a host "
        "without one, state truthfully that the seed is written and the user must start the "
        "fresh session themselves\n"
        "• pace hand-offs — sustained cadence, never bursts: more than one hand-off within a few "
        "minutes is a fault signal — stop and surface it instead of churning sessions\n"
        "• degradation, never refusal — where the host lacks a capability this law names "
        "(wakeups, task tracking, sub-agent spawning, model or effort pins, a writable project, "
        "a rollover relay), the duty naming it degrades to its nearest honest equivalent and "
        "every other duty binds unchanged: maximum forward motion within each turn, no mid-work "
        "permission asks outside the taxonomy above, and a truthful \"nothing will self-wake\" "
        "note at every turn end; when the flywheel first engages on such a host, WRITE the plan "
        "for the missing capability — the gap that most limits the loop, drawn from this mode's "
        "harness menu; `/plans write` where a plans skill is available, else a plain `*.plan.md` "
        "— into the project's plan directory, once (skip if a predecessor already wrote it), log "
        "and report the written path, and leave it UNBUILT: building it takes the user's express "
        "direction\n"
        "If work remains and you are about to end a turn without work in flight and a wakeup "
        "armed, you have already erred — spawn and arm before you land; never land idle (the "
        "drained rollover hand-off is the one sanctioned landing: the invariant passes to the "
        "successor session)."
    ),
    "one-word": (
        "ONE-WORD MODE — every response is exactly one word, on every turn until you exit. "
        "Apply literally: no punctuation flourishes, no trailing clause."
    ),
    "sbs": (
        "SBS MODE — do exactly ONE step, then STOP and wait for the user to say 'done' "
        "before the next. Never chain steps. Binds every turn until you exit."
    ),
    "exclude": (
        "⛔ EXCLUDE MODE — refuse any Write or Edit whose target matches: {pats}. Binds "
        "every turn until you exit. Name the matched pattern when you decline. "
        "Read / Glob / Grep are unaffected."
    ),
    "include": (
        "⛔ INCLUDE MODE — refuse any Write or Edit whose target does NOT match one of: "
        "{pats}. Binds every turn until you exit. Say the file isn't in the include set "
        "when you decline. Read / Glob / Grep are unaffected."
    ),
}


def mode_note(name, param):
    """The canonical enforcement law for one active mode, with its param substituted in.

    Returns LAW[name] verbatim (byte-locked to SKILL.md) with the `{dir}`/`{pats}` token
    filled. We use str.replace, NOT str.format: the law prose contains other literal
    braces/punctuation that would trip format(), whereas replace only touches our token.
    """
    text = LAW.get(name, "")
    if name == "plan":
        text = text.replace("{dir}", param if param else "./")
    elif name in ("exclude", "include"):
        text = text.replace("{pats}", ", ".join(param or []))
    return text


# The generative closer. The LAW above is a DECLARATION — passively read, and it fades by
# the next unrelated turn. This turns the moment into an ASK: a short predict-then-derive
# exercise the agent must actually ANSWER (generate tokens for) in its private reasoning
# before it replies. The point is the generation effect: a contract you DERIVE for yourself
# encodes and binds all session; one you are merely told does not. We deliberately spend a
# few tokens here to buy session-long adherence — this is the one thing the fast script
# gave up when it took over the bookkeeping the agent used to reason through by hand.
#
# Kept OUT of the per-mode LAW blocks (it is generic, not mode-specific) and off the
# empty/clear state (nothing to encode once no mode is active). Not byte-locked to SKILL.md
# the way LAW is — it is a generative prompt, not a contract whose wording tests pin.
ENCODE_PROMPT = (
    "Now ENCODE this; do not just read it. The script did the bookkeeping, but building the "
    "understanding is yours — and a contract you DERIVE sticks where one you are handed "
    "fades. Before you emit the echo, work these out in your own reasoning (never shown to "
    "the user), actually writing a sentence for each — do not answer them only in your head:\n"
    "  1. Predict what active_modes.md now holds, then verify it against the echo below.\n"
    "  2. Name one concrete thing you will do differently many turns from now, when no "
    "script has run and nothing is reminding you.\n"
    "  3. State the single event, and nothing short of it, that ends this obligation.\n"
    "If you jumped straight to the echo without answering, you have not encoded it: stop and "
    "answer now, then carry on. This mode is not a message that fades; it is a standing "
    "contract you just derived."
)


def render_agent_notes(state):
    """The private agent-notes block (above the echo delimiter) for the post-change modes.

    One law paragraph per active mode (alphabetized for stable output), then the generative
    ENCODE_PROMPT that makes the agent DERIVE the "standing until revoked" conclusion rather
    than be told it. Empty state is the `/modes clear` case -> a single "no modes" line (no
    ask: nothing is active to encode).
    """
    if not state:
        return "No modes active — full default agency."
    parts = [mode_note(n, state[n]) for n in sorted(state.keys())]
    parts.append(ENCODE_PROMPT)
    return "\n".join(parts)


# --------------------------------------------------------------------------------------
# Directive parsing + dispatch
# --------------------------------------------------------------------------------------


def parse_directive(raw):
    """
    Split the raw directive into (verb, rest). verb is lowercased; rest is the remainder.
    Blank -> ('', '').
    """
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    parts = raw.split(None, 1)
    verb = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""
    return verb, rest


def split_patterns(rest):
    """Comma-split a pattern param, trim, drop empties."""
    return [p.strip() for p in rest.split(",") if p.strip()]


def apply_directive(state, raw):
    """
    Compute (new_state, echo_text, should_write, agent_notes) for the directive.

    Raises ValueError for a directive we cannot handle (caller turns that into a
    non-zero exit -> fallback). should_write is False for read-only verbs (list, help);
    agent_notes is '' for the cheat-sheet (no active-mode change to reinforce).
    """
    verb, rest = parse_directive(raw)

    # Blank / unknown verb -> help cheat sheet (read-only: no notes, no write).
    if verb == "":
        return state, HELP_TEXT, False, ""

    # list: report the CURRENT modes. should_write=False (read-only), but notes ARE emitted
    # so a plain `/modes list` still re-reminds the agent of the active contract.
    if verb == "list":
        return state, render_active_list(state), False, render_agent_notes(state)

    # clear: drop every mode -> empty state (== defaults); writes the emptied file.
    if verb == "clear":
        return {}, "all modes cleared.\nactive modes : none", True, render_agent_notes({})

    if verb == "exit":
        if not rest:
            raise ValueError("exit needs a mode name")
        # Normalize the WHOLE rest first so a two-word target ("exit agent loop")
        # resolves to agent-loop instead of silently exiting bare `agent`; fall back
        # to the first token for the normal single-word targets.
        whole = normalize_mode_name(rest)
        target = whole if whole in SIMPLE_MODES else normalize_mode_name(rest.split(None, 1)[0])
        new_state, echo, should_write = apply_exit(state, target)
        return new_state, echo, should_write, render_agent_notes(new_state)

    # Two-word-verb guard: "/modes agent loop" parses as verb `agent`, rest `loop`,
    # and would otherwise silently enter plain agent mode. A threshold may trail it
    # ("agent loop 20"), so keep whatever follows `loop` as the param.
    if verb == "agent":
        tail = rest.split(None, 1)
        if tail and tail[0].lower() == "loop":
            verb, rest = "agent-loop", (tail[1].strip() if len(tail) > 1 else "")

    mode = normalize_mode_name(verb)
    if mode not in SIMPLE_MODES:
        # Unrecognized verb -> help (matches "blank or unrecognized verb -> Help output").
        return state, HELP_TEXT, False, ""

    new_state, echo, should_write = apply_enter(state, mode, rest)
    return new_state, echo, should_write, render_agent_notes(new_state)


def apply_enter(state, mode, rest):
    """Enter `mode` and return (new_state, echo, should_write=True).

    Three shapes: compound (exclude/include — APPEND + dedupe patterns), plan (stores its
    dir, displaces agent via the mutex), and the simple modes. Operates on a copy so the
    caller's state is never mutated in place.
    """
    new_state = dict(state)

    # Compound modes: exclude / include APPEND the given patterns to any existing set
    # (deduped) rather than replacing it — so successive directives build the set up.
    if mode in ("exclude", "include"):
        patterns = split_patterns(rest)
        already = mode in new_state
        if not patterns and not already:
            # Empty pattern args, mode not yet active -> no-op ask (routed to the model
            # via a non-zero exit / fallback). Draft decision: fallback-to-ask.
            raise ValueError("empty pattern args")
        existing = list(new_state.get(mode, []))
        added = [p for p in patterns if p not in existing]  # only genuinely new patterns
        new_state[mode] = existing + added
        # Patterns actually added -> "now active" with the updated set; nothing new
        # (re-invoke with all-existing patterns, or empty on an active set) -> "already".
        already_echo = not added
        return new_state, enter_echo(mode, new_state[mode], new_state, None, already_echo), True

    if mode == "plan":
        param = rest.strip() if rest.strip() else "./"  # no dir given -> default ./
        already = "plan" in new_state
        # plan / agent / agent-loop are mutually exclusive: entering plan turns the
        # active sibling off, and each displacement is named in the echo.
        displaced = []
        for sib in MUTEX.get("plan", ()):
            if sib in new_state:
                del new_state[sib]
                displaced.append(sib)
        new_state["plan"] = param
        return new_state, enter_echo("plan", param, new_state, displaced, already), True

    # agent-loop: the sole-operant stance — entering it clears EVERY other active mode,
    # not just the mutex siblings. Re-entry is idempotent: layered modes survive. The
    # optional param is the rollover threshold (a percentage of context usage); re-entry
    # semantics mirror exclude — a NEW value updates ("now active"), a bare or identical
    # re-entry preserves what's stored ("already active") and never erases it.
    if mode == "agent-loop":
        param = rest.strip() or None
        if param is not None:
            if (not re.fullmatch(r"\d{1,3}", param)
                    or not (AGENT_LOOP_PCT_MIN <= int(param) <= AGENT_LOOP_PCT_MAX)):
                # Out of range / non-numeric -> ask, don't clamp and don't write (same
                # fallback-to-ask treatment as empty pattern args).
                raise ValueError("agent-loop threshold must be an integer {}-{}".format(
                    AGENT_LOOP_PCT_MIN, AGENT_LOOP_PCT_MAX))
            param = str(int(param))  # normalize e.g. "020" -> "20"
        already = "agent-loop" in new_state
        if already:
            stored = new_state.get("agent-loop")
            if param is None or param == stored:
                # bare or same-N re-entry: idempotent, stored threshold preserved
                return new_state, enter_echo("agent-loop", stored, new_state, [], True), True
            new_state["agent-loop"] = param  # new N: update in place, layered modes survive
            return new_state, enter_echo("agent-loop", param, new_state, [], False), True
        displaced = sorted(new_state.keys())
        new_state = {"agent-loop": param}
        return new_state, enter_echo("agent-loop", param, new_state, displaced, False), True

    # Simple modes (agent, one-word, sbs). agent is a member of the three-way stance
    # mutex, handled generically through the MUTEX table below.
    already = mode in new_state
    displaced = []
    for sib in MUTEX.get(mode, ()):
        if sib in new_state:  # displace each active mutex sibling
            del new_state[sib]
            displaced.append(sib)
    new_state[mode] = None
    return new_state, enter_echo(mode, None, new_state, displaced, already), True


def apply_exit(state, target):
    """Exit `target` and return (new_state, echo, should_write=True).

    Deleting the key drops the mode entirely — for exclude/include that clears the WHOLE
    pattern set (there is no per-pattern removal). Exiting a mode that isn't active is not
    an error: it emits the "is not active" echo and still rewrites the file, so the on-disk
    state is always reasserted.
    """
    new_state = dict(state)
    if target in new_state:
        del new_state[target]
        echo = "mode {} is now inactive.\n{}".format(target, render_active_list(new_state))
        return new_state, echo, True
    echo = "mode {} is not active.\n{}".format(target, render_active_list(new_state))
    return new_state, echo, True


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------


def main(argv):
    raw = argv[1] if len(argv) > 1 else ""  # the raw directive, or "" -> help

    # 1-2. locate this session's state file, then read current modes (default agent if none).
    session_dir, _sid = resolve_memory_root()
    state = read_state(session_dir)

    # 3. compute the resulting state + the two output sections for this directive.
    new_state, echo, should_write, notes = apply_directive(state, raw)

    # 4. Persist state for state-mutating verbs when a session dir is resolvable. Read-only
    # verbs (list, help) never write; no-session surfaces run in-context only.
    if should_write and session_dir is not None:
        write_state(session_dir, new_state)

    # 5. Emit the dual-section stdout: AGENT_DELIM, [agent-notes], ECHO_DELIM, echo. The
    # notes line is omitted for the cheat-sheet (notes == ""), leaving an empty agent
    # section; the trailing newline keeps the echo a clean final line for the caller.
    out = [AGENT_DELIM]
    if notes:
        out.append(notes)
    out.append(ECHO_DELIM)
    out.append(echo)
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:  # any failure -> non-zero exit -> model falls back
        sys.stderr.write("modes.py error: {}\n".format(exc))
        sys.exit(1)
