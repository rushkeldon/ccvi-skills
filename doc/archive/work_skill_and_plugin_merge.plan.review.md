---
plan: "work_skill_and_plugin_merge.plan.md"
model: "claude-opus-5-5"
---
# Review: work_skill_and_plugin_merge

**Overall: needs revision before build.** The merge and fold phases are close to ready.
The /work phase has two real gaps on the requester (dpp) side: how a `.response.md`
reaches a running requester, and how a new worktree's IDE window gets opened. It also
uses Node where this repo mandates `python3`. Reviewed from dpp's side as the requester,
by dpp-00.

| Dimension | Grade | Notes |
|---|---|---|
| Execution-readiness | ⚠️ | response delivery and window opening are unspecified; the requester-side resume is missing |
| Stale assumptions | ⚠️ | an AIX reference is already in the moved pr skill; the monitor uses Node, against CLAUDE.md |
| Cross-surface risk | ⚠️ | the compliance gate's scope doesn't cover the morning job |
| Rails present | ✅ | strong anchors, whys, and done-whens throughout |
| TODO hygiene | ⚠️ | merge-uninstall is listed before merge-bbpi but must run after it; history handling unstated |
| Mechanical lint | ⚠️ | 8 em dashes, against the plan's own conventions |

## Findings

**merge-inventory** `[hygiene-issue]` - The plan says "move" but not how. dpp-skills has
real history: 5+ commits of the v1 build (`d931d7d`, `99957bd`, `c51fc9a`, `2ee80fb`,
`6a8691f`). A file copy loses that history; `git subtree add` or a `git filter-repo`
import keeps it. Decide, and say so. Also add a fence: the `rushkeldon/dpp-skills` GitHub
repo is **not** archived or deleted by this plan. That's Keldon's call.
Action: state the history method (recommend `git subtree add --prefix=<tmp>` then `git mv`, or a plain copy if Keldon prefers a clean start) and add the GitHub-repo fence to Out of scope.

**merge-doctrine** `[risky]` - The "No Disney-specific content enters the plugin" fence
is stated, but nothing enforces it on the files being moved, and one already violates it:
`plugin/skills/pr/SKILL.md` hard-codes reading tickets "through the AIX `jira` CLI" (around
line 182, beside `settings.ticketKeyPattern`). ccvi-idea ships this zip, so the reference
ships with it.
Action: add a step (or extend merge-inventory's done-when) to make the ticket source a `PR_REVIEW.md` setting (e.g. `settings.ticketCommand`, beside `ticketKeyPattern`), move the AIX value to Keldon's `~/.dpp/PR_REVIEW.md` layer, and add a done-when of `grep -rniE 'aix|jira --agent|twdcgrid' plugin/` returning nothing.

**merge-guard** `[hygiene-issue]` - The guard refuses to run without
`~/.dpp/guard_patterns.txt`. That's right for Keldon's machine, but it now gates commits
to ccvi-skills, the CCVI plugin repo, on a dpp file. That's an assumption worth stating:
a ccvi-skills clone without `~/.dpp` can't commit until `guard_install.sh` seeds the file.
Action: add to Conventions: "ccvi-skills commits require `~/.dpp/guard_patterns.txt`; guard_install.sh seeds it." Also add `issue: Read and Write` to `/repos init` step 6 while you're in this repo: `prune` currently gets HTTP 403 "token does not have at least one of required scope(s): [write:issue]" on every forge PR delete.

**merge-uninstall** `[hygiene-issue]` - The body says to uninstall dpp-skills "after the
merged build is installed, not before," but the todo list orders merge-uninstall
**before** merge-bbpi, and merge-bbpi is where the merged build gets installed (the unzip).
A literal implementer runs them in list order and leaves a window with no pr or idioms skill.
Action: move merge-uninstall after merge-bbpi in the todos list.

**fold-pr-verb** `[hygiene-issue]` - The done-when checks dispatch, but not the leftover
references to `/pr`. `pr/SKILL.md` alone contains 15 occurrences of `/pr ` (the help
output, the later-verbs "designed in a later plan" messages, and cross-references), and
dpp's docs and the dpp-skills plan cite `/pr start`.
Action: add to the done-when: `grep -rn '/pr ' plugin/` returns nothing (every reference reads `/repos pr`). dpp-00 repoints dpp's own docs separately.

**work-skill** `[hygiene-issue]` - **The response leg isn't delivered.** The chain ends
with `worktree -> /work response {requesterDir} {md}`, and the sidecar hand-off only polls
`*.request.md`. Nothing says what happens when a `.response.md` lands in a requester's
per-worktree git dir: does the requester's CCVI inject it as a turn, or must the requester
poll its receipts? For dpp this is the whole point, since dpp is the requester and needs to
act on results.
Action: specify response delivery: either the sidecar poller also consumes `*.response.md` (injecting it as a turn with the same claim-before-inject rule), or the requester polls `~/.ccvi/work/` for `responded` receipts whose `requesterDir` is its own. Add it to work-sidecar-handoff's list if it's the former.

**work-skill** `[hygiene-issue]` - **Requester-side resume is missing.** The requester owns
closure in both outcomes, but a requester session can end (rollover, IDE restart; dpp's
session name has rotated three times today). Who closes a receipt whose requester died?
The orphan rule covers only `claimed` work on the worker side.
Action: add a requester-side scan, run on session start in the requester's cwd, for receipts with `requesterDir` == this cwd in state `responded` or past `expires`: process and close them. Same one-readdir shape as `orphans`.

**work-skill** `[hygiene-issue]` - **Opening the IDE window is unspecified.** The routing
doctrine says "create a new one if under the per-repo cap", but not how the new worktree's
window gets opened, or by whom. Keldon's chain has "open a window of IntelliJ IDEA or
Android Studio to that directory" as an explicit step, and ccvi-idea's own lesson is that
`open <projectPath>` can raise a macOS TCC prompt for Desktop access, which stalls an
unattended chain silently.
Action: add a step naming the opener (recommend: the receiving agent asks its own running IDE to open the directory, or IntelliJ's command-line launcher, never `open <path>` from a background process) and a done-when that opening a worktree under `~/Desktop/working` produces no TCC dialog.

**work-monitor** `[stale]` - The monitor is specified in Node
(`spawn(..., { detached: true, stdio: 'ignore' }).unref()`), but this repo's CLAUDE.md says
the skills may assume `python3` and "do not port the scripts to Node". The stated reason
for Node, that `setsid` is absent on macOS, applies to the `setsid` *command*, not the
syscall: Python's `subprocess.Popen(..., start_new_session=True, stdin/stdout/stderr=DEVNULL)`
calls `setsid()` on macOS and detaches the child from CCVI's process group.
Action: specify the monitor in python3 with `start_new_session=True` and DEVNULL stdio; keep the doze-proof tick-against-stored-deadline rule.

**work-sidecar-handoff** `[risky]` - The compliance decision is qualified to "a freshly
launched CCVI instance, where opening the IDE window on a directory is itself the human
action". dpp's morning job (launchd at 05:00, two PR reviews) would open windows with
**no** human action, so it falls outside that decision. Recording that boundary now keeps a
later builder from treating the morning job as covered.
Action: add one sentence: "This decision does not cover unattended dispatch (e.g. dpp's scheduled morning job opening windows with no human present); that needs its own decision from Keldon."

**work-contract** `[ready]` - The at-least-once invariant, claim-by-cwd, and
tombstone-not-delete reasoning are right, and match what dpp needs. One confirmation from
the requester side: dpp will treat a receipt reaching `claimed` as the acknowledgment it
asked for (the "did they take it?" receipt), so no separate ack message is needed. Worth
one line in the contract so requesters know that's the intended signal.
Action: add to the contract: "A requester reads `state: claimed` (with `claimedCwd`) as acceptance."

**work-receipts** `[lint]` - "All four durable-tier reads and writes" sits under a list of
five operations (open, claim, respond, close, orphans).
Action: change "All four" to "All five".

**fold-pr-schema** `[lint]` - The plan's conventions say no em dashes; it has 8. Two are in
this todo's body (lines 334 and 346), one is in work-contract (line 457), and five are in
work-receipts (lines 529 to 534).
Action: replace each em dash in the plan with a hyphen or rephrase.

Clean, no action: merge-paths, merge-manifest, merge-bbpi, fold-pr-references,
fold-pr-defaults.
