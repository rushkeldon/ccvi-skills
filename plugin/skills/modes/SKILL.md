---
name: modes
description: plan•agent•agent-loop•one-word•sbs•exclude•include•exit•list•clear - manage persistent response modes via /modes [verb] directives. Use when the user issues a /modes directive, or asks in natural language to enter, exit, list, clear, or check any response mode.
argument-hint: "[verb] [param]"
allowed-tools: Read, Write, Edit, Bash(python3:*), Bash(printenv:*)
---

# modes

Manage persistent response modes. Modes are **binding contracts that override defaults**; multiple may be active at once (with the documented exceptions); each persists across turns until explicitly exited.

This skill has two layers. The **fast path** (a bundled script) does all the bookkeeping — resolve the session, read/parse/write state, and produce the echo — so a directive is one quick call. The **behavioral contract** (Authority & ownership + Mode behaviors, below) is what an active mode obligates *you* to do on every turn; that is always your job, script or not. If the script is unavailable, the **Fallback logic** section reproduces the bookkeeping by hand.

## Run the script (do this first, always)

Every `/modes` directive is handled by the bundled script `scripts/modes.py`. On **every** directive:

1. Run this in **one** `Bash` call — substitute `{SKILL_DIR}` with the **"Base directory for this skill"** path you were given at invocation, and pass everything the user typed after `/modes` as a **single quoted argument** (so patterns like `*.log` are never glob-expanded by the shell):

   ```sh
   python3 "{SKILL_DIR}/scripts/modes.py" "<everything the user typed after /modes>"
   ```

   (Blank directive → pass `""`.)

2. The script's stdout is **two sections** split by the line `===MODES_USER_ECHO===`:
   - Everything **above** that line (under `===MODES_AGENT_NOTES===`) is **private guidance for you**: the behavioral contract for the modes now active. **Internalize it and enforce it for the rest of the session. NEVER display it to the user.** The notes end with a short **encode step** — a predict-then-derive ask (predict what `active_modes.md` now holds and verify it against the echo; name one thing you'll do differently many turns from now; state the single event that ends the mode). **Actually answer it in your private reasoning — write the sentences — before you emit the echo.** This is deliberate, not filler: the script owns the fast bookkeeping, but a mode you *derive* for yourself binds all session, where one you are merely *told* fades by the next unrelated turn. Spending those few tokens is the point; don't skip the ask. (The old all-markdown skill got this adherence for free because you had to reason the whole thing out by hand — the encode step buys it back cheaply now that the script does the reasoning-heavy bookkeeping.)
   - Everything **below** that line is the **user echo**. Print it to the user **verbatim, as plain markdown text — NOT inside a code block or fence** — as your **entire** reply. No preamble, no commentary, no reformatting.

3. **"Don't reason / just relay" scopes to the echo and the state bookkeeping ONLY — never to enforcement.** The agent-notes bind your behavior; the **Mode behaviors** section below is the authoritative reference for that behavior.

**Fallback.** If that `Bash` call fails, use the **Fallback logic** section at the bottom:

- **`python3` not installed** (shell "command not found" / exit 127): first output the single line `Installing python will speed up this skill.` on its own line, then run the fallback logic and print the normal echo. **This one nudge line is the sole exception to "the echo is the entire response."**
- **Any other failure** (non-zero exit, empty stdout, unresolved base dir): fall back **silently** — no nudge, just the normal echo produced by hand.

A successful script run **ends your turn for the *directive*** — never mix the two paths. It does **not** end your obligation to the modes it just set: the script did the bookkeeping and handed you the law in its agent-notes, but enforcing that law on every later turn is yours and does not lapse. "Run script → relay → done" is the *directive* loop, not the *enforcement* loop. (A PreToolUse hook — see **Mechanical enforcement** below — is a deterministic backstop, but never lean on it: the contract is yours every turn.)

## Authority and ownership

Modes are **user-settable only**. Never enter, exit, or toggle a mode on Claude's own initiative. Only act when the user explicitly issues a `/modes [verb]` directive — or asks in natural language to enter, exit, list, clear, or check a mode. Do not echo directive syntax in responses except when quoting the user.

The single exception to "Claude doesn't toggle modes" is the `plan` / `agent` / `agent-loop` three-way mutex: entering any one of the three when a sibling is active exits that sibling automatically — and entering `agent-loop` goes further, clearing **every** other active mode (see its behaviors section). This is still user-initiated — the user typed the directive — and matches Cursor's behavior. (The `/plans build` verb also bridges to `agent` before executing, which is likewise user-initiated.)

**An active mode binds your behavior on every turn until it is exited.** The script processes the directive and restates the contract in its agent-notes; **enforcing the mode, every turn, is always yours** — it does not lapse between directives.

## Mode behaviors

These are the effects Claude must enforce while the corresponding mode is active. Multiple modes compose; all active modes apply simultaneously (with the `plan` / `agent` / `agent-loop` mutex noted above). This section is **always in force** — it is the reference the agent-notes reinforce.

### plan

Plan mode is a working stance: the goal is to produce a precise, well-scoped spec — a `.plan.md` file — that another agent (Cursor, Claude Code) can later execute. Implementation happens *after* the plan is approved, by exiting plan mode (`/modes agent` or `/modes clear`).

**The enforcement contract — this is the FULL law, and it binds you every turn.** The block below is the canonical source: the fast-path script emits it *verbatim* in its agent-notes on every directive (byte-locked by `test_modes.py`, so the two can never drift), and it is what the Code plugin's PreToolUse hook enforces mechanically. It is a HARD constraint the script never discharges — do not let it fade between directives:

<!-- LAW:plan -->
```
⛔ PLAN MODE — a HARD write filter, in force on EVERY turn until you exit. Running the fast-path script does NOT discharge it; enforcement is yours every turn, script or not. BEFORE any Write or Edit, check the target file type:
• new *.plan.md → default to `{dir}`; elsewhere only if the user explicitly asks (then do it, don't refuse)
• edit / copy / move / rename any EXISTING .md → allowed anywhere; note the operation in one line as you do it
• delete markdown → BLOCKED; archive (move) it instead and decline the delete plainly
• any NON-markdown write (.py .json .ts .zip …) → BLOCKED; decline with "can't — plan mode; only markdown writes allowed", then offer to exit plan mode (/modes agent) if they want it done
• Read / Glob / Grep / read-only Bash → unaffected
If you are about to write a non-.md file you have already erred — refuse and surface it; never "just this once".
```
<!-- /LAW:plan -->

The rest of this section is the detailed reference behind that law. **File-write & file-operation behavior while in plan mode.** The deciding question for
any blocked-or-allowed call is **what operation, on what kind of file** — resolve it in
this order:

1. **Creating a NEW `*.plan.md`** (a plan file that does not yet exist): **defaults to the
   plan directory** (the `[dir]` argument; default `./`). Unless you hear otherwise, put a
   new plan file there. **But if the user asks for a `*.plan.md` somewhere else, create it
   there — do not refuse.** The plan dir is a default, not a jail; don't get hung up on it.
2. **Editing, copying, moving, or renaming any EXISTING `.md` file — including an existing
   `*.plan.md` — is allowed anywhere**, across any directory, including over the plan-dir
   boundary. That covers `Write`/`Edit` to a file that already exists, `cp`, and
   `mv`/rename. This is what lets a lifecycle hand-off (e.g. `/plans toIDE`) copy an
   existing plan to `~/.cursor/plans/` and move the original into an archive dir.
   **Mention the operation to the user in one line as you do it** (what moved/copied
   where). Editing a non-plan `.md` (notes, docs, READMEs) is likewise unrestricted by
   directory.
3. **Deleting markdown is blocked.** To get a plan "out of the way," *archive* it (move it
   elsewhere, per rule 2); outright deletion is left to the user. Decline a delete with a
   plain note ("can't — plan mode; archive (move) it instead, or delete it yourself").
4. **Any non-markdown write is blocked** (creating or editing a `.ts`, `.json`, etc.).
   Decline with a plain note ("can't — plan mode; only markdown writes allowed").
5. `Read`, `Glob`, `Grep`, and read-only `Bash` are unaffected.
6. `include` / `exclude` still apply on top of these rules (a write allowed here is still
   refused if it matches `exclude` or falls outside `include`).

The single rule of thumb: **the only thing plan mode nudges toward a directory is the
*creation of a new plan file* (a default you override on request). Every other markdown
operation — edit, copy, move, rename — is free; only markdown deletion and non-markdown
writes are blocked.**

**The purpose of a plan (hold this while authoring):** a plan is a set of **rails**. It is typically written by a high-reasoning model and then *implemented by a possibly cheaper, lower-reasoning model*. You spend the reasoning budget **now** so the implementer doesn't have to **later** — it should execute and verify, never re-derive intent or choose between options. The single metric: **minimize the decisions the implementer must make.** A plan must also read top-to-bottom for a *human* reviewer; that's the same property, not a competing one — if a line makes a reader ask "which is it?", that's exactly where a weak implementer derails. Full standard: the repo's `doc/what_makes_a_good_plan.md` (empirical companion: `doc/plan_outline_ala_cursor.md`) — the digest below is self-contained, so it stands alone where those docs aren't reachable.

**Conversational behavior while in plan mode:**

- Ask clarifying questions before *and during* drafting. **Resolve decisions now** — the user is right here, which is the cheapest moment to answer. Don't defer a decision you could make now into the plan for the implementer to trip over.
- Research the codebase (Read, Grep, Glob) to ground the plan in real file paths and code.
- Surface alternatives and trade-offs the user should weigh.
- **No unresolved decisions in the finished plan.** An "X or Y?" question is a *failure* — resolve it. A genuine execution-time unknown becomes a **spike todo with branch-handling** (what to try, the outcomes, what to do for each). A load-bearing **assumption with its stated consequence** is allowed and encouraged. Ban the passive "Open questions" limbo list.
- Don't implement. If asked to implement, remind the user they're in plan mode and ask whether to exit (`/modes agent` or `/modes clear`) before proceeding.

**Plan file naming:**

Filename: `<descriptive-snake-case>.plan.md` — no suffix.

If the same name already exists in the plan directory, the user has presumably revised the plan; either overwrite (if continuing the same plan) or pick a more specific name. Don't auto-suffix in plan-mode authoring; suffix-on-collision is `/plans toIDE`'s job at import time.

**Plan file format (Cursor-compatible):**

```yaml
---
name: <human-readable title>
overview: "<1–3 sentence summary; QUOTE it — it usually contains a colon or a path>"
todos:
  - id: <kebab-slug>          # stable handle + cross-ref key into the body
    content: "<imperative, single line, names the real file(s); a human grasps it alone>"
    status: pending
    # phase: "<optional grouping label; an unknown key Cursor safely ignores>"
isProject: false
---

# <human-readable title>

## Problem / Context

<why this work exists; the current state>

## Approach

<the chosen design in 1–3 paragraphs; reference real files with [name](relative/path) links>

## Conventions & assumptions

<hidden decisions made explicit: which patterns/frameworks/naming the implementer must follow; load-bearing assumptions WITH their consequence ("assumes X; if not, step N changes")>

## The steps

<narrative, IN ORDER. Each step: location (stable anchor — symbol or unique string, NEVER a line number) + the concrete change (snippet/pseudocode) + one-line WHY + DONE-WHEN (a behavioral check, not "it compiles"). Cross-reference its todo id.>

## Out of scope

<what NOT to touch, and why — the fence that stops a literal implementer from wandering>

## Verification

<how to confirm the whole thing landed; behavioral>
```

Status vocabulary: `pending`, `in_progress`, `completed`, `cancelled` (underscore in `in_progress`, never a hyphen). `isProject: false` for normal plans.

**This skeleton is a floor to prune from, not a checklist to fill — scale rigor to risk** (a 3-line bugfix needs no Architecture section). Note what's deliberately *present* and *absent*: the high-value rails an implementer needs are **done-when checks**, **out-of-scope fences**, **conventions made explicit**, and **stable anchors** (the four things organic plans tend to omit); and there is **no "Open questions" section** by design (resolve / promote-to-spike / record-as-assumption instead). Always include the standing escape hatch: **if reality doesn't match the plan, STOP and surface — don't improvise.**

**Three hard format rules (so the plan keeps rendering in Cursor):** (1) edit surgically — flip only the `status:` line located by `id`; never re-emit/reorder the frontmatter or churn ids. (2) Always-quote free-text scalars (`overview`, `content`) — an unquoted value with embedded quotes or a colon-space collapses the whole frontmatter and blanks every todo; round-trip through a real YAML parser if unsure. (3) Preserve additive keys like `phase`.

**Directory handling:**

The chosen `[dir]` is stored in `active_modes.md` as `plan: <dir>`. It is the **default** landing spot for newly-created plan files. If the directory isn't currently accessible, tell the user to run `/add-dir <path>`.

Don't drop the user's chosen directory silently — but per rule 1 above, a new plan the user explicitly asks to place elsewhere goes where they ask.

### agent

Full agency. No plan-mode write filter. Entering `agent` exits `plan` or `agent-loop` if active. Other modes (`include`, `exclude`, `one-word`, `sbs`) continue to apply. When your work is driven by a `*.plan.md`, open it in the host's plan editor by running the command the capability note in your system prompt teaches, with the plan's absolute path, as you take the plan up; a session with no capability note has nothing to run.

This is the default working stance, but having it as a named mode lets the user explicitly switch out of plan mode in one step (`/modes agent`) instead of `/modes clear` + adjusting expectations.

### agent-loop

The autonomous keep-moving flywheel. The mode is a **two-state contract**: entering it is **dormant** — no work, no wakeup, no sub-agent is kicked off, and turns end normally while nothing is assigned. The **flywheel engages the moment work starts** (the user assigns work, or the session begins work it already knows): spawn the first sub-agent AND arm the fallback wakeup immediately, in that same turn. From then on the invariant binds **at every turn's landing** — no turn ends with work remaining unless work is in flight (workers first; more in parallel whenever independent units exist — one is the floor, not the target) and a wakeup is armed — with every wake event re-establishing the invariant before anything else. Delegation is the strong default; doing a unit yourself in the same turn is the exception for work too interpretive to delegate.

**The enforcement contract — this is the FULL law, and it binds you every turn.** Same byte-locked mechanism as `plan`'s law: the fast-path script emits it *verbatim* in its agent-notes on every directive, and `test_modes.py` pins the two copies so they can never drift:

<!-- LAW:agent-loop -->
```
⛔ AGENT-LOOP MODE — a standing keep-moving contract, in force on EVERY turn until the user exits it. Running the fast-path script does NOT discharge it; enforcement is yours every turn, script or not. Entering the mode is DORMANT arming only — it starts no work, schedules no wakeup, spawns nothing; turns end normally while no work is assigned. The MOMENT work starts (you are told the work, or you begin work already known), the flywheel engages:
• the standing invariant — taking on work means spawning the first sub-agent AND arming the fallback wakeup immediately, in the same turn; when independent units exist, run as many sub-agents in parallel as the work supports — one is the floor, not the target. Delegation is the strong default, with workers one model tier down per the model-economy bullet; doing a unit yourself in the same turn is legitimate ONLY when it is too interpretive to delegate. The binding check is at the LANDING: no turn ends with work remaining unless work is IN FLIGHT (per the wake-source bullet) and a fallback wakeup is ARMED, both together — a wakeup armed with nothing in flight is NOT compliance (the wakeup is insurance behind running work, never a schedule), and solo work is compliance only while the turn lasts, never a state to land in
• where the work is tracked in a live plan or status surface, keep it truthful in real time — flip the unit to in_progress as part of committing to it (deploying a worker on it IS that first action: flip at the launch, never after the worker returns), flip to completed only after its done-when is verified (a worker's self-report is evidence, not the verdict), and flip to a truthful terminal state promptly on a bail or kill; every flip is the orchestrator's — a worker never touches the plan or status surface, and its brief says so
• every wake event re-establishes the invariant FIRST — a returning worker spawns its successor immediately (its return is itself a wake source); a wakeup firing while work is still in flight just re-arms; a wakeup firing with NOTHING in flight spawns before anything else; only work-complete or a true blocker ends the loop. In-flight work means running sub-agents first; a harness-tracked background job (a build, a long test — anything that re-invokes you on completion) counts ONLY while no independently delegable unit sits unspawned — waiting is never the only activity, and a long job running never excuses an empty worker pool while parallel units exist. The fallback wakeup is LONG (20+ minutes), armed behind in-flight work as insurance against a hang — never a short poll, and never the sole wake source
• arm FIRST on seeded and resumed turns — a turn that opens from a hand-off replay, a session resume, or a recovery nudge arms its fallback wakeup as its FIRST action, before any work: every wake source is armed by a tool call, so a turn that dies before its first call leaves NOTHING armed and the session sits dead until a human notices; arming first shrinks that naked window to near zero
• never cron for the heartbeat — scheduled cloud agents and new-instance spawners are NOT wake sources: they spawn fresh sessions with fresh context, defeating the same-session point of the loop; the heartbeat is an in-session wakeup armed behind in-flight work, or nothing
• every wakeup carries this mode's own re-entry text as its prompt, never a generic sentinel — a host's default wakeup framing is conservative ("steward; when quiet, stop"), and as the LAST instruction read on wake it out-competes this law by recency; arm with the loop's re-entry brief instead: re-enter agent-loop, reconstruct from the plan statuses and the log tail, re-establish the invariant, continue from the NEXT line
• report execution state truthfully — "stopped, nothing will wake me" is a sentence to WRITE, never a state to conceal; a turn ending on a wait names what is running, its expected duration, and what wakes it; turn summaries lead with what happened and never promise work the turn didn't do; a milestone summary is not a stopping point — summarize, then keep working or arm in the same turn
• decide-log-continue — make the best call under the project's stated guidance (specs, plans, conventions; absent those, the most defensible reading of intent), log decision + rationale + the NEXT unit, and keep going; the log is this engagement's autonomy_log_<session>_<NN>.md in the RESOLVED log directory — first hit of: a host <ccvi-autonomy-log> sentinel, an `Autonomy logs:` line in CLAUDE.md, the directory an existing autonomy_log_* already sits in, else <docDir>/logs/autonomy — resolved ONCE at the first log write, its path named in that turn's report, and NEVER a .gitignore edit (the log is written, never hidden; ignoring it is the user's call) (fresh file per engagement, materialized on first entry, seeded with a ≤10-line digest of the newest predecessor's tail), with each new entry echoed in the turn's report — where no writable project exists, the echoed entry itself is the log; a wrong-but-logged call beats a stalled session, and entering this mode accepts that rollback risk; cost and effort forecasts are NEVER a reason to stop, shrink, or ask — your forecasts run in human-engineer units and are reliably wrong; when a fork's recommended option is "keep going", TAKE it
• stop-and-ask ONLY for: contradicting the project's stated guidance with no compliant path; a compounding, hard-to-reverse fork the guidance genuinely cannot arbitrate; destructive actions; real-world money (purchases, paid services — NOT token/compute spend, which entering the mode accepts) — everything else is decide-log-continue
• every worker brief draws its fence — it names what the worker owns (its unit, its files) and what it must never touch: the plan file, the autonomy log, and other units' files; a worker commits only its own named pathspec or nothing at all — NEVER add-all, which sweeps racing siblings' edits and the orchestrator's flips into its commit; the worker's model and effort ride in the brief per the model-economy bullet
• gate exclusive resources — a resource only one worker can safely hold (a heavy build slot, a port, a device or display, a shared fixture) gets AT MOST ONE holder at a time; a spawn moment with the slot taken hands the new worker non-conflicting work (docs, plans, read-only analysis) instead of a queue position or a double-booking — the invariant's "as many as the work supports" means exactly this
• model economy — sub-agents default one model tier DOWN from the session: spend tokens on judgment, not typing; step down FURTHER when the brief is paint-by-numbers (exact files, exact edits, fixed verification — the test: a brief that survives literal execution with zero judgment calls does not need the judgment tier); never spawn at your own tier without a specific, logged reason; a brief too vague for the tier below is a brief to sharpen before spawning anyone. Where the host exposes a reasoning-effort dial for workers, it follows the same gradient — low effort for mechanical briefs, high effort reserved for judgment-heavy units. No tension with "cost is never a reason": that governs the WORK, this governs who executes it — do the expensive thing, on the cheapest model and effort that do it faithfully
• rollover threshold — when the mode entry carries a percentage (`agent-loop: N`), treat N% context usage as the hand-off point: drain in-flight work first — a successor cannot receive a worker's return; finish or land the current units and spawn nothing new (a background job's on-disk artifacts DO survive — name them in the seed so the successor harvests them) — then author the hand-off with `/seedprompt write` and request the fresh session: on a host with a rollover relay, create an empty `rollover.request` beside the seed in the memory root and end the turn; on a host without one, state truthfully that the seed is written and the user must start the fresh session themselves
• pace hand-offs — sustained cadence, never bursts: more than one hand-off within a few minutes is a fault signal — stop and surface it instead of churning sessions
• degradation, never refusal — where the host lacks a capability this law names (wakeups, task tracking, sub-agent spawning, model or effort pins, a writable project, a rollover relay), the duty naming it degrades to its nearest honest equivalent and every other duty binds unchanged: maximum forward motion within each turn, no mid-work permission asks outside the taxonomy above, and a truthful "nothing will self-wake" note at every turn end; when the flywheel first engages on such a host, WRITE the plan for the missing capability — the gap that most limits the loop, drawn from this mode's harness menu; `/plans write` where a plans skill is available, else a plain `*.plan.md` — into the project's plan directory, once (skip if a predecessor already wrote it), log and report the written path, and leave it UNBUILT: building it takes the user's express direction
• plan surfacing — when your work is driven by a *.plan.md, surface it in the host's plan editor: the capability note in your system prompt names the exact open command — run it with the plan's ABSOLUTE path as you take the plan up, and again when you switch plans; the printed acknowledgment is authoritative — opening the tab is the host's job, CONTINUE the turn; a session with no capability note (running outside CCVI) has nothing to run — the duty is inert there
If work remains and you are about to end a turn without work in flight and a wakeup armed, you have already erred — spawn and arm before you land; never land idle (the drained rollover hand-off is the one sanctioned landing: the invariant passes to the successor session).
```
<!-- /LAW:agent-loop -->

**The autonomy log (the decide-log-continue destination).** One log file per engagement: a fresh (non-idempotent) agent-loop engagement reserves `<logDir>/autonomy_log_<sessionID>_<NN>.md` (full session UUID; `NN` zero-padded so lexical sort is chronological; no session id resolvable → a UTC stamp slug instead). The file materializes on the first log entry — a dormant entry that never gets work leaves nothing — and an idempotent re-entry never bumps the index. Entries are append-only and dated; each names the binding NEXT unit; each is echoed in the turn's report as it is written. The first entry of a new file is a ≤10-line digest read from the newest predecessor's TAIL (open threads, standing decisions still in force, the NEXT line) — never a full-file read, so no session ever reads more than one predecessor's tail. The live log is the current session's highest index; discovery is a glob of `autonomy_log_*` in the resolved log directory; version control is the deep archive. Projects that already keep an autonomy log elsewhere keep using it — never create a second log beside an established one.

**Resolving `<logDir>` (the four-rung ladder).** The log directory is resolved **once per
engagement, at the first log write**, and reused for the rest of the engagement — it is a
property of the project, not of the `/modes` directive, so nothing about it is decided at
entry time.

**`<docDir>` — one definition, two consumers.** Rungs 3 and 4 both reference `<docDir>`, so
it is defined once, here: **`<docDir>` is the project's plan directory — a verbatim
`<ccvi-doc-dir epoch="N">` hint present in this turn's context, otherwise an existing
`doc/` or `docs/` in the project root, otherwise `doc/`.**

```text
<ccvi-doc-dir epoch="3">notes</ccvi-doc-dir>
```

The hint carries a **fact about the project's layout** (the host's plan directory), never a
preference about where logs go — so it is an INPUT to `<docDir>` and **never a rung-1 hit**.
Rungs 1-3 are evaluated first and in order; the hint's presence alone never resolves the
ladder. Its trust rules match `<ccvi-modes>`: only a well-formed verbatim block counts, a
paraphrase is not a sentinel, and the highest `epoch` wins — an independent counter,
evaluated per tag. Four further rules:

- **Containment, checked mechanically.** A hint value that is absolute, or contains `..`,
  is ignored and the probe runs. No filesystem access needed to apply the rule. An
  out-of-repo log directory is a *preference*, which is what rungs 1 and 2 exist for.
- **A blank body is a miss, not a hit** — for `<ccvi-doc-dir>`, for `<ccvi-autonomy-log>`,
  and for a `CLAUDE.md` `Autonomy logs:` line with an empty value alike. A blank
  declaration resolves nothing and the next rung (or the probe) runs.
- **No trailing-slash significance** — `notes` and `notes/` are the same value.
- **Resolve once, never re-check.** The skill adds no logic to wait for the hint or re-poll
  for it on a later turn; keeping it in context at the first-log-write moment is the host's
  obligation, not this ladder's.

Take the **first rung that hits**:

1. **Host setting.** A verbatim `<ccvi-autonomy-log epoch="N">` block present in this
   turn's context, its path between the tags — the CCVI host's autonomy-log-directory
   setting, injected the way `<ccvi-modes>` is (the tag is the contract; the setting's key
   is host-local and deliberately unnamed here). Same trust rules: only a well-formed verbatim block
   counts, the highest `epoch` wins, and a paraphrase is not a sentinel.
2. **Project declaration.** The first line in a loaded `CLAUDE.md` matching `Autonomy
   logs:` (case-insensitive) followed by a path. A project `CLAUDE.md` beats the
   user-global one. This rung costs nothing — `CLAUDE.md` is already in context — and it
   works on a host that ships no sentinel at all:

   ```text
   Autonomy logs: doc/logs/autonomy
   ```

3. **Follow suit.** Glob `autonomy_log_*` in `<docDir>` and in the project root; if any
   exist, adopt the directory holding the newest. This is what makes the
   "keep using it" clause above operational rather than advisory — session two in a repo
   lands where session one did, with zero configuration.
4. **Fallback.** `<docDir>/logs/autonomy/`, created if absent.

**Containment.** A resolved path stays inside the project root unless rung 1 or 2
explicitly names somewhere else. Discovery and the fallback never leave the repo.

**Git posture — the log is written, never hidden.** The mode NEVER edits `.gitignore` or
`.git/info/exclude`. Keeping the log out of version control is the user's decision and the
user's action; the loop's only duty is to **name the resolved path in its turn report the
first time it writes there**, so the user can act on it.

**Hand-off.** The rollover seed names the resolved log path explicitly, so the successor
session adopts it rather than re-resolving into a different directory mid-engagement.

**Harness capabilities worth having (the menu the degradation bullet's plan draws from).** Two families, each entry capability-shaped — what it does, never how any one host builds it. Session harnesses keep the loop alive: **schedulable same-session wakeups** (the heartbeat's insurance; without them every turn end is a full stop); **background-task tracking** that re-invokes on completion (lets a turn end on real work instead of babysitting it); **a rollover relay** (watches for a hand-off request beside the seed and starts the successor session unattended); **an idle-landing nudge** (fires when a turn ends with nothing in flight; quotes the log's NEXT line back, leaving a pause nowhere to hide); **a turn-death supervisor** (re-enters after a terminal API error with a verify-what-landed-and-resume prompt); **a modes loader** (injects active-modes state at turn start so the contract survives context loss); **live status rendering** (a plan/log watcher so the human reads session state at a glance). Work harnesses make autonomous work verifiable and safe: **self-observability gauges** (expose what the agent cannot see about itself — its own context occupancy, machine state); **freshness gates** (refuse to verify a stale artifact — "the thing you built" and "the thing you're testing" provably the same); **one-command verdict runners** (the whole acceptance suite behind one exit code — loops need verdicts, not vibes); **determinism rigs** (pin time, network pacing, scheduling so behavior reproduces); **record-and-replay of human input** (capture a demonstration once, replay it in similar contexts — the human becomes a fixture, not a recurring interruption); **environment janitors** (clear wedged state between runs so a bad run can't poison the next); **failure-novelty dedup** (one place that answers "is this failure NEW?"); **resource stewards** (reclaim disk/caches in graded bites that preserve warm state); **async evidence capture** (screenshots, traces, diffs a human reviews later, so review never blocks the loop); **harness self-tests** (the rig itself is tested — a lying harness is worse than none). The menu is a palette, not a checklist; it grows as new capabilities are proven.

**Degradation, never refusal.** Never refuse the mode on any surface. Where the host has the capabilities the law names (wakeups, task tracking, sub-agent spawning, model/effort pins, a writable project, a rollover relay), the corresponding duties bind fully as written. Where it lacks one, that duty degrades to its nearest honest equivalent and everything else binds unchanged: maximum forward motion within each turn, no mid-work permission asks outside the blocker taxonomy, and a truthful statement at every turn end that nothing will self-wake. The honesty duty survives everywhere. And per the law's degradation bullet, the first engagement on such a host WRITES the plan for the most limiting missing capability (from the harness menu) — once, logged and reported — and never builds it without the user's express direction.

**The rollover threshold (optional param).** `/modes agent-loop <pct>` stores a rollover threshold with the mode — `- agent-loop: 20` in `active_modes.md` — declaring the point at which this session should hand itself off to a fresh one: at `<pct>`% context usage, finish the current unit of work, write the hand-off (`/seedprompt write`), then request the new session, exactly as the law's rollover bullet spells out. The accepted range is an integer **20-99**; anything else (out of range, non-numeric) is refused rather than clamped — ask the user for a valid threshold and write nothing. The floor of 20 exists because a session that rolls over sooner hands off before it has done meaningful work, so the churn costs more than the fresh context buys. Re-entry follows `exclude`'s shape: a **new** value replaces the stored one and echoes "now active"; a **bare** re-entry, or the **same** value again, preserves what's stored and echoes "already active" — bare re-entry never erases a threshold. The param is a declaration, not an enforcement mechanism; knowing when N% arrives is a three-rung ladder. Rung 1, host push: a host that tracks context usage (a sidecar with a context gauge) detects the crossing and nudges — precise, zero agent effort. Rung 2, self-gauge: on hosts where the session transcript is readable (`~/.claude/projects/<slug>/<session-id>.jsonl`), estimate occupancy at natural checkpoints (each landing, between units) as `transcript_bytes ÷ 5.7 + 30k fixed` against the model's context window — measured within ~1% on a live 1M-window session, but drift-prone with content mix, and it OVERESTIMATES after a context compaction (which errs toward handing off early, the safe direction). Rung 3, unmeasurable (no host signal, no readable transcript): the threshold is declared but unenforceable — say so truthfully, and note that a self-observability gauge is then the top harness-menu candidate for the degradation bullet's plan. (`/context` is a user command; the agent cannot invoke it.) At the hand-off itself, drain first per the law: workers cannot cross the session boundary (a rollover kills and respawns the claude process), but a background job's on-disk artifacts survive — name them in the seed. Omitting the param is equally valid — a bare `- agent-loop` entry simply leaves the hand-off point to the host's default. Every armed wakeup, rollover-born or not, carries the canonical re-entry brief verbatim as its prompt: "Re-enter agent-loop: reconstruct from the plan statuses and the autonomy log tail, re-establish the invariant (work in flight + wakeup armed), continue from the log's NEXT line."

**Entry, exit, and layering.** Entering `agent-loop` clears **every** other active mode and becomes the sole operant mode — each displaced mode is named in the echo. `plan`, `agent`, and `agent-loop` are a three-way mutex: entering any one displaces whichever sibling is active. After entry, compose modes may be layered on top: `one-word`, `include`, and `exclude` apply normally; `sbs` *suspends* the flywheel's heartbeat while active (one-step-and-wait wins) and the contract resumes when `sbs` exits. Re-entering `agent-loop` is idempotent — it does not re-clear layered modes. Exit via `/modes exit agent-loop`, `/modes clear`, or entering `plan`/`agent`.

**Persistence.** Per-session, like every mode. Cross-session continuity of long-running autonomous work (seed prompts, session-resume docs) is the host's hand-off machinery, not this skill's.

### one-word

Responses are a single word. Apply literally — no punctuation flourishes or trailing clauses.

### sbs (step-by-step)

Perform exactly one step, then stop and wait for the user to say "done" (or equivalent). Do not chain steps. After "done", proceed to the next step. The skill itself is exempt — handling a mode directive is not a step.

### exclude

`exclude` holds a list of gitignore-style glob patterns. Any `Write` or `Edit` whose target file matches *any* pattern is refused. `Read`, `Glob`, `Grep` are unaffected. Decline blocked writes with a plain note naming the matched pattern.

Param format: comma-separated patterns. `/modes exclude *.log, *.tmp, build/**` appends those three to the existing set (duplicates deduped). `/modes exit exclude` clears the entire set.

### include

`include` holds a list of gitignore-style glob patterns. Any `Write` or `Edit` whose target file does *not* match any pattern is refused. `Read`, `Glob`, `Grep` are unaffected. Decline blocked writes with a plain note that the file isn't in the include set.

Param format: comma-separated patterns. `/modes include src/**/*.ts, tests/**/*.ts` appends those to the existing set. `/modes exit include` clears the entire set.

### Interaction summary

- `plan`, `agent`, and `agent-loop` are a three-way mutex — entering any one displaces whichever sibling is active.
- Entering `agent-loop` additionally clears **every** other active mode (sole operant mode on entry); compose modes may then be layered back on top.
- `sbs` + `agent-loop`: `sbs` suspends the flywheel's heartbeat while active (one-step-and-wait wins); the loop's contract resumes when `sbs` exits.
- `include` and `exclude` compose: writable iff (matches include) AND (does not match exclude).
- `plan` mode's write rules (new `*.plan.md` defaults to the plan dir but may go elsewhere on request; edit/copy/move/rename any existing `.md` anywhere; markdown delete & non-markdown writes blocked) layer on top of `include` / `exclude`.
- Output-style modes (`one-word`, `sbs`) compose freely with everything else.

## Mechanical enforcement (Code plugin hook)

The **ccvi-skills plugin** ships a `PreToolUse` hook (`hooks/enforce_modes.py`, registered in `plugin.json`) that makes the write-blocking modes **deterministic** — it does not depend on you remembering the contract. Before every `Write`/`Edit`/`MultiEdit`/`NotebookEdit`, it reads the session's `active_modes.md` and **denies** the call when it violates an active mode:

- **plan** — the target is not a `.md` file (markdown-only writes).
- **exclude** — the target matches an active exclude glob.
- **include** — the target matches none of the active include globs.

(`agent-loop` adds no write filter, so the hook is unchanged by it — an `- agent-loop` state entry is inert to the hook.)

When it denies, Claude sees the reason (e.g. *"plan mode is active — it allows only markdown writes… exit plan mode first: `/modes agent`"*) and relays it to the user. The hook is **fail-open**: any error, missing file, or unresolvable session lets the write through, so it can never wedge editing.

This is a **backstop, not a substitute** for your own enforcement. Enforce the contract yourself every turn; treat the hook as the seatbelt, not the driver. (It fires on tool calls, so it catches `Write`/`Edit`; markdown *deletes* and `cp`/`mv` happen via `Bash` and are governed by the behavioral contract, not the hook.)

---

## Fallback logic (only when the script is unavailable)

Everything below reproduces, by hand, the bookkeeping the script normally does. Use it **only** when the `python3` call in "Run the script" fails (see the Fallback rules there). On the happy path the script has already done all of this — do not also run it by hand.

### Invocation

The skill has a single entry point: **`/modes [verb] [param1] [param2]`**, dispatching on the first arg (mirrors the sibling `/plans [verb]` idiom). The verb is either a **mode name** (enter that mode) or one of the reserved verbs `exit`, `clear`, `list`:

| Form | Effect |
|---|---|
| `/modes <mode-name> [param]` | Enter that mode (e.g. `/modes plan ./doc`, `/modes agent`, `/modes sbs`) |
| `/modes exit <mode-name>` | Exit a specific mode (e.g. `/modes exit sbs`) |
| `/modes clear` | Exit every active mode |
| `/modes list` | Echo the currently active modes (no state change) |
| `/modes` (blank/unknown verb) | Print the help cheat-sheet (see **Help output**) |

All verbs are lowercase (the cross-skill casing rule: plain verbs lowercase; only proper-noun/initialism targets like `/plans toIDE` are camelCase — `/modes` has none). The mode name **is** the verb to enter it; there's no separate `enter` verb.

Exiting `plan`/`agent`/`agent-loop` is normally done via their three-way mutex (entering one exits the active sibling) or `/modes clear`; `/modes exit <mode>` is for turning off a specific compose-mode like `sbs`, `exclude`, or `include` (though `exit agent-loop` works too).

### State file

Active modes are stored **per session**, keyed by session id, inside Claude's
auto-memory directory (the path is in the system prompt's auto-memory section — use
that absolute path; never hard-code a UUID). The file for a session is:

```text
<auto-memory>/<session_id>/active_modes.md
```

where `<session_id>` is the current session's id. Resolve it **without a tool call**:
it is immutable for the session and already present in your context as the UUID path
segment of the **Scratchpad / temp directory** named in the system prompt
(`…/<project-slug>/<session_id>/scratchpad`). Resolve it once and reuse it for the rest of
the session. Only if it is not derivable from context, read it once via
`printenv CLAUDE_CODE_SESSION_ID` (pre-approved in `allowed-tools`, so it never prompts).
This per-session file is the single
source of truth for that session. There is **no flat / project-global
`active_modes.md`** — modes never bleed between concurrent windows on the same
project.

Format:

```markdown
# Active modes

- plan: ./
- exclude: *.t.ts, *.log
```

The **default** when a session has no state file yet is a single mode: `agent`
(full agency). A file containing only `agent` and an absent file are equivalent — both
mean "defaults."

#### Host modes sentinel (fast path)

The CCVI sidecar injects a **sentinel** into your turn context that
carries the current modes, letting you skip the `Read`:

```text
<ccvi-modes epoch="7">
- plan: ./doc
</ccvi-modes>
```

Rules:

- **Trust only a verbatim, well-formed block** matching `<ccvi-modes epoch="N"> … </ccvi-modes>`
  with the active-mode entries between the tags. A summarized/paraphrased copy that doesn't
  match exactly is NOT a sentinel — ignore it and `Read`.
- **Pick the highest `epoch`** when more than one is present (an older and a newer block can
  both ride in history after a change).
- **It reflects `active_modes.md` as of this turn** — for a transition that is the state
  *before* your change, which is exactly the prior state you need for the displacement/echo.
- **When in doubt, `Read`.** The sentinel only ever *adds* a fast path; the `Read` is the
  permanent floor and is never weakened. A verbatim host-authored sentinel present THIS turn
  is fresh context — categorically different from trusting your own recollection (never do
  that).
- A turn with no sentinel in context simply `Read`s as always — the sentinel is a pure
  accelerator, correctness-neutral.

#### Resolution and lifecycle

- **Session id resolvable, `<session_id>/active_modes.md` exists** — read it; those
  are the active modes.
- **Session id resolvable, file absent** — on the first `/modes` directive, create
  `<session_id>/active_modes.md` (creating the `<session_id>/` subdirectory if needed)
  seeded with the resulting state.

After creation, `<session_id>/active_modes.md` is the **only** file the skill ever
writes. Each session owns exactly one file; sessions never read or write each other's.

#### Loading is the host's job, not the skill's

A skill only runs when invoked, so it cannot load modes into context at the start of
each turn. That is the responsibility of the host **loader hook** (CCVI installs a
`SessionStart` / `UserPromptSubmit` hook) that resolves `<session_id>/active_modes.md`
and injects it — seeding the default `agent` mode on first run per the lifecycle
above. This hook is the **sole** load mechanism. There is no `MEMORY.md` pointer and no flat-file
fallback — both are deliberately gone (the static pointer could only ever name a fixed
path, which can't carry the session id).

### Recognized directives

| Directive | Effect |
|---|---|
| `/modes plan [dir]` | Enter plan mode (exits agent if active); new `*.plan.md` **default** to `[dir]` (default `./`) but may be created elsewhere on request; editing/copying/moving/renaming any existing `.md` allowed anywhere; markdown delete and non-markdown writes blocked |
| `/modes agent` | Enter agent mode (exits plan or agent-loop if active) |
| `/modes agent-loop [pct]` | Enter the autonomous keep-moving loop — clears **every** other active mode on entry (sole operant mode); mutex with plan/agent; compose modes may be layered afterwards. Optional `[pct]` is the rollover threshold (an integer **20-99**): the context-usage percentage at which the session hands off to a fresh one. Out of range or non-numeric → ask, no state write |
| `/modes one-word` | Enter one-word mode |
| `/modes sbs` | Enter step-by-step mode |
| `/modes exclude <patterns>` | Add comma-separated patterns to the "exclude" set (block-list for writes) |
| `/modes include <patterns>` | Add comma-separated patterns to the "include" set (allow-list for writes) |
| `/modes exit <mode>` | Exit that mode (e.g. `/modes exit sbs`, `/modes exit exclude` clears the set) |
| `/modes list` | Echo the currently active modes (no state change) |
| `/modes clear` | Exit every active mode |

The leading verb is case-insensitive (`/Modes`, `/MODES` all work) but mode names are lowercase (with kebab for multi-word). `/modes exit exclude` and `/modes exit include` clear that entire pattern set.

`/modes [verb]` is the **canonical** form. The old `/enterMode`, `/exitMode`, `/listModes`, `/clearModes` spellings are retained **only as soft natural-language aliases** — recognize them if a user types them, but don't document or emit them. Treat natural-language phrasings as equivalent to the matching directive:

- "enter plan mode in src/", "turn on plan mode", "/enterMode plan src/" → `/modes plan src/`
- "turn off agent", "exit agent mode", "drop agent", "/exitMode agent" → `/modes agent` (the mutex) or `/modes clear`
- "stop step-by-step", "/exitMode sbs" → `/modes exit sbs`
- "what modes are on?", "show active modes", "/listModes" → `/modes list`
- "clear all modes", "reset modes", "/clearModes" → `/modes clear`
- "show me the modes", "modes cheat sheet", "what modes are available?" → print the **Help output** (no state change; see below)

`/modes list` echoes what's *active*. The cheat sheet (natural-language only) lists what's *available*. Don't conflate them.

### Echo contract

Every directive that mutates state — `/modes <mode-name>`, `/modes exit <mode>`, `/modes clear` — emits a structured echo so the user always sees the post-change state. `/modes list` emits the active-modes echo only. The echo is the **entire response** to a mode directive — no preamble, no commentary, no postscript — and is rendered as **plain markdown text, never inside a code block**.

#### `/modes <mode-name> [param]` (enter)

If the mode is **not currently active**:

```text
mode <name> is now active.
mode <displaced> is now inactive.
mode <name> : <one-line blurb>
active modes :
 • <mode>
 • <mode>
```

One "is now inactive" line appears per displaced mode, alphabetized — a mutex sibling (the `plan` / `agent` / `agent-loop` group), or **every** cleared mode when `agent-loop`'s clear-on-entry fires. Omit the line(s) entirely when there's no displacement. E.g. entering `agent-loop` while `plan` and `exclude` are active:

```text
mode agent-loop is now active.
mode exclude is now inactive.
mode plan is now inactive.
mode agent-loop : <one-line blurb>
active modes :
 • agent-loop
```

A mode entered with a param renders that param in the list — `/modes agent-loop 20` ends with `active modes :\n • agent-loop: 20`, the same compound rendering `plan:` and `exclude:` use.

If the mode is **already active**:

```text
mode <name> is already active.
mode <name> : <one-line blurb>
active modes :
 • <mode>
 • <mode>
```

(For `exclude`/`include`, re-invoking with **new** patterns emits the "now active" form with the updated set; re-invoking with nothing new emits "already active".)

#### `/modes exit <mode>`

If the mode is **currently active**:

```text
mode <name> is now inactive.
active modes :
 • <mode>
 • <mode>
```

Or `active modes : none` if no modes remain.

If the mode is **not currently active**:

```text
mode <name> is not active.
active modes :
 • <mode>
 • <mode>
```

Or `active modes : none` if no modes remain.

#### `/modes list`

```text
active modes :
 • <mode>
 • <mode>
```

Or `active modes : none`.

#### `/modes clear`

```text
all modes cleared.
active modes : none
```

#### Echo formatting rules

- The active-modes list is always **alphabetized** by mode name.
- One bullet per line: a single leading space, then `•`, then a space, then the mode.
- Compound modes (`exclude`, `include`, `plan`) render with their param: `exclude: *.log, *.tmp` or `plan: ./src`.
- `none` is rendered inline on the same line as `active modes :` — no bullet list when empty.
- No preamble, no commentary, no postscript around the echo. The echo *is* the response, printed as plain markdown text (never fenced in a code block).

### Mode blurbs

The one-line blurb emitted with each enter echo (`/modes <mode-name>`):

| Mode | Blurb |
|---|---|
| plan | "new `*.plan.md` default to `[dir]` (default `./`), or elsewhere if you ask; create/edit/copy/move/rename any existing `.md` anywhere — only delete is forbidden; non-markdown writes blocked. Produce a `*.plan.md`" |
| agent | "full agency; the default working stance" |
| agent-loop | "the autonomous flywheel — dormant until work starts, then at least one sub-agent always running + a wakeup always armed; only the blocker taxonomy stops forward motion" — plus `; hand-off at <pct>% context usage` appended when a rollover threshold is stored |
| one-word | "responses are a single word" |
| sbs | "step-by-step; one step then wait for 'done'" |
| exclude | "block writes matching listed patterns" |
| include | "only allow writes matching listed patterns" |

### Handling a directive

**Cheat-sheet queries are special** — skip the numbered steps below entirely. Don't read or write `active_modes.md`. Instead, reply with the verbatim text from the **Help output** section. Treat natural-language equivalents ("show me the modes", "what modes are available?", "modes cheat sheet") the same way. Distinguish from `/modes list`, which echoes the *active* modes, not the *available* ones.

1. Resolve the session id with **zero tool calls** where possible: it is immutable for the session, so take the UUID path segment from the Scratchpad/temp directory in your system prompt (or a value already resolved earlier this session) and reuse it. Only if it is not derivable from context, read it once with `printenv CLAUDE_CODE_SESSION_ID` (this command is pre-approved via `allowed-tools` → no permission prompt). Then obtain the current modes — **fast path first**: if a well-formed host sentinel `<ccvi-modes epoch="N"> … </ccvi-modes>` is present in your context, take the entries from the **highest-`epoch`** instance and dispatch/echo from it **without a `Read`** (see [Host modes sentinel](#host-modes-sentinel-fast-path)). Otherwise — no sentinel, or it looks paraphrased/garbled, or you are unsure — fall back: **the CONTENTS of `active_modes.md` are mutable, so if a session id is resolvable you MUST `Read` `<auto-memory>/<session_id>/active_modes.md`** — treat an absent file as the default state (`agent`). Either way, a state-mutating directive **still `Write`s** the file in step 3 — the sentinel replaces only the read, never the write.

   **You do NOT know the current modes from conversation history.** It WILL be stale — modes change across plan builds, agent switches, and prior turns, and a slash command injects this skill's text into context *without* forcing a tool call, so it's easy to answer from memory and be wrong. **Base the dispatch AND the echo on what you just READ, never on recollection.** This is the same reason a host's modes pill (where one exists) reflects the file and never an optimistic click: answering from memory reintroduces exactly the desync this skill exists to prevent (observed failure: emitting "already active" while the file said `agent`, and writing nothing). If you have not just read the file this turn — **or** received a verbatim host `<ccvi-modes>` sentinel this turn — you cannot answer. (The sentinel is the one exception, because it is host-authored fresh state injected this turn, not your recollection.)
2. Parse the directive. Dispatch on the first arg (the verb):
   - `/modes <mode-name> [param]` → add the mode. If the mode is already in the set, emit the "already active" echo. (This is an ECHO variant only — you STILL write the resolved state in step 3; "already active" never skips the write.)
   - `/modes exit <mode>` → remove the mode. If the mode is not in the set, emit the "not active" echo. (Echo variant only — you STILL write the resolved state; "not active" never skips the write.)
   - `/modes list` → **reads** (step 1, like every directive — it echoes the *real* active modes) but does NOT write; emit the active-modes echo only. ("No state change" = no write, not "no read"; never echo the list from memory.)
   - `/modes clear` → empty the set; emit the "all modes cleared" echo.
   - `/modes` with a blank or unrecognized verb → print the **Help output** (no state change).
   - For `plan`: store/replace the directory param; if no param given, default `./`.
   - For `exclude` / `include`: append the comma-separated patterns to the existing set (idempotent — duplicate patterns deduped).
   - `plan`, `agent`, and `agent-loop` are a three-way mutex — entering one exits the active sibling and each displacement is named in the echo.
   - For `agent-loop`: entering it clears **every** other active mode (each named in the echo, alphabetized); re-entry while already active is idempotent — "already active" echo, layered modes survive. An optional param is the rollover threshold — accept an integer 20-99 and store it as `agent-loop: <pct>`; refuse anything else (ask, no write); on re-entry a new value replaces the stored one ("now active"), while a bare or identical re-entry preserves it ("already active"). Two-word guard: `agent loop` (with a space) is `agent-loop`, on enter AND exit — never treat it as a bare `agent`.
3. If a session id was resolvable, **write the full resolved state UNCONDITIONALLY** to `<auto-memory>/<session_id>/active_modes.md` (creating the `<session_id>/` subdirectory if needed — this is the create-on-first-run step). "Unconditionally" means **every state-mutating directive writes — including re-entering an already-active mode or exiting an inactive one** (those differ only in echo *wording*, never in whether the write happens). This is the safety net: even if your read/assumption was wrong, the file ends correct and the host pill (which watches the file) self-heals. The ONLY directives that don't write are the genuinely read-only ones — `/modes list` and the cheat-sheet (see below). This per-session file is the only file written; there is no flat file and no `MEMORY.md` pointer to maintain.
4. If the directive entered `plan` and the chosen directory isn't currently accessible, tell the user to run `/add-dir <path>`.
5. Emit the structured echo (see **Echo contract**), **derived from the state you READ in step 1** — never from conversation history. The prior-state claims in the echo (e.g. the "mode `<displaced>` is now inactive" line, or "already active" / "not active") MUST reflect what the file actually held before this write. If you cannot point to a `Read` of `active_modes.md` this turn, you have no basis for the echo — read first. No other text in the response.

### When tools are denied

This skill declares `allowed-tools: Read, Write, Edit, Bash(python3:*), Bash(printenv:*)` in its frontmatter (`Bash(python3:*)` runs the fast-path script; the narrow `Bash(printenv:*)` covers only the one-time session-id fallback in step 1, so a mode change never prompts). Those are pre-approved while the skill is active. If a `Write` or `Edit` against `<session_id>/active_modes.md` is denied anyway by the user's `settings.json`, don't retry silently. Instead:

1. Honor the directive **in conversation context** for the remainder of the session (no persistence).
2. Emit the structured echo as usual — the user still gets the active-modes view.
3. Append one line after the echo: *"persistence blocked: `Write` on `<session_id>/active_modes.md` denied — mode is active for this conversation only."*
4. Suggest the minimum settings change (e.g. add `Write` for the memory directory) so future sessions persist.

Do not surface this branch unless a tool actually got denied — the happy path stays quiet.

### Help output

When the user asks for the cheat sheet (any natural-language phrasing — "show me the modes", "what modes are available?", "modes cheat sheet"), reply with this exact text — preserve the structure, bullets, and order. No paraphrasing, no preamble, no closing remarks:

```text
Modes · v0.0.9:
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
```

### Edge cases

- **Re-entering an active mode** — emit the "already active" echo (which still includes the blurb and active-modes list). Don't error.
- **Exiting an inactive mode** — emit the "not active" echo. Don't error.
- **Empty pattern args** (`/modes exclude` with nothing after) — treat as no-op and ask the user for the intended patterns. Do not write to state.
- **Pattern parsing** — split on commas, trim whitespace. Patterns themselves may not contain commas.
- **Cross-session start** — when a new conversation begins, the host loader hook (see **Loading is the host's job**) reads `<session_id>/active_modes.md` (seeding default `agent` on first run) and injects it; honor whatever's there. Do not announce active modes unprompted; the user can issue `/modes list` if they want to see.
- **Plan dir collision** with a same-named plan file — ask the user before overwriting.
- **Pre-2.0.0 state files** — if `active_modes.md` contains entries like `- one word` (with space) or `- SBS` (uppercase), normalize on first read to `- one-word` and `- sbs` and rewrite the file. No user-facing notice required.
- **Re-entering `agent-loop`** — idempotent: "already active" echo, and layered compose modes are NOT re-cleared (clear-on-entry fires only on a fresh entry).
- **Out-of-range or non-numeric `agent-loop` param** (`/modes agent-loop 5`, `/modes agent-loop abc`) — treat as no-op and ask the user for a threshold in 20-99. Do not clamp, and do not write to state (same treatment as empty pattern args).
- **Bare `agent-loop` re-entry never erases a stored threshold** — `/modes agent-loop` while `agent-loop: 20` is active keeps the `20`; only a new in-range value replaces it.
- **`/modes agent loop` (with a space)** — this is the `agent-loop` directive, never a bare `agent` that swallows "loop"; the same folding applies to `exit agent loop`, and to a trailing threshold (`/modes agent loop 20` is `/modes agent-loop 20`).
