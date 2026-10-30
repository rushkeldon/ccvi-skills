---
name: work_skill_and_plugin_merge
version: "1.0"
overview: "Absorb dpp-skills into ccvi-skills (one plugin, one version, one BBPI), fold /pr into /repos as a noun verb, and add /work - a two-verb agent-to-agent work-assignment skill whose durable receipts guarantee a .response.md eventually reaches the requester. Three phases, independently landable in order: the merge is packaging, the fold is refactor, /work is new capability."
isProject: false
todos:
  - id: merge-inventory
    content: "Move dpp-skills' skills and script into ccvi-skills/plugin/"
    status: pending
    phase: Merge
  - id: merge-paths
    content: "Rewire the two path couplings that break on the move (CLAUDE_PLUGIN_ROOT script ref, DEFAULTS_REVIEW)"
    status: pending
    phase: Merge
  - id: merge-guard
    content: "Bring dpp-skills' pre-commit guard and .gitignore-as-allowlist posture across"
    status: pending
    phase: Merge
  - id: merge-doctrine
    content: "Merge the CLAUDE.md doctrine, keeping the generic-skill-text rule verbatim"
    status: pending
    phase: Merge
  - id: merge-manifest
    content: "Consolidate to one plugin.json and marketplace.json; confirm build.py packages the new skills"
    status: pending
    phase: Merge
  - id: merge-uninstall
    content: "Retire the dpp-skills plugin install so no skill double-registers"
    status: pending
    phase: Merge
  - id: merge-bbpi
    content: "BBPI and verify the installed skill set is the merged one"
    status: pending
    phase: Merge
  - id: fold-pr-verb
    content: "Make pr a /repos noun verb with a required action param"
    status: pending
    phase: PR fold
  - id: fold-pr-references
    content: "Push per-action pr depth into references/ so the merged SKILL.md stays thin"
    status: pending
    phase: PR fold
  - id: fold-pr-schema
    content: "Update /repos' verbs schema, description, and help diagram for the pr verb"
    status: pending
    phase: PR fold
  - id: fold-pr-defaults
    content: "Relocate the layer-1 review defaults and repoint dpp_api.py plus its selftest"
    status: pending
    phase: PR fold
  - id: work-contract
    content: "Write the /work contract doc: the two document types and the receipt record"
    status: pending
    phase: Work skill
  - id: work-skill
    content: "Author /work SKILL.md with the request and response verbs"
    status: pending
    phase: Work skill
  - id: work-receipts
    content: "Implement the receipt lifecycle helper: claim, respond, close, orphan scan"
    status: pending
    phase: Work skill
  - id: work-monitor
    content: "Implement the detached pickup monitor that survives the IDE closing"
    status: pending
    phase: Work skill
  - id: work-sidecar-handoff
    content: "Hand the ccvi-idea side (drop poller plus orphan resume) across the seam with a written spec"
    status: pending
    phase: Work skill
---

# work_skill_and_plugin_merge

Three phases. They are ordered but independently landable: **Merge** is packaging,
**PR fold** is a refactor inside the merged plugin, and **Work skill** is new capability
that only needs the merge to have happened so it lands in the right repo.

## Why all three are one plan

They share one cause. `/work` is the mechanism dpp uses to reach a repo agent, dpp already
hard-requires CCVI, and CCVI owns the `.{suffix}.md` namespace that `.request.md` and
`.response.md` join. Once `/work` belongs in ccvi-skills, dpp-skills has nothing left that
is meaningfully independent, so the merge and the new skill are the same decision seen from
two ends.

## Decisions already made (do not re-open)

- **ccvi-skills is the surviving plugin, repo, and marketplace.** dpp-skills is absorbed.
- **`/pr` folds into `/repos`** as a noun verb, `/repos pr <action>`.
- **`/idioms` stays its own skill.** It is not folded into `/cleancode`: cleancode is gated
  to a stabilized project with a green verdict, and "how does this repo usually do this?" is
  a mid-construction question, so the merge would make the skill's own gate forbid one of
  its verbs.
- **The namespace is deliberately asymmetric.** `pr` gets a noun layer; `init`, `config`,
  `sync`, `prune`, `open`, `review`, `status`, and `export` stay flat. The fully consistent
  alternative (`/repos forge <verb>` beside `/repos pr <verb>`) is **rejected**: the existing
  eight are a coherent set the picker and the user already know, and retrofitting a namespace
  onto them is churn for symmetry. Do not "fix" this asymmetry.
- **Receipts live under `~/.ccvi/work/`**, not `~/.dpp/work/`. The shared root is already a
  documented cross-platform contract with pruning, and it is where `agent_state/` lives,
  which the orphan rule reads.
- **`/work` is ONE skill with two verbs**, never two skills. `request` and `response` share
  the vacate-after-write invariant, and separate skills are exactly how one rule ends up
  stated twice and drifts.

## Out of scope (fences)

- **No new mode.** The return address does not become an `active_modes.md` entry. That file
  is keyed by session id, so a rollover gets a fresh one by design; the obligation is carried
  by the receipt on disk instead. See "Durability tiers" below.
- **No edit to the agent-loop re-entry brief.** `REENTRY_BRIEF` is hand-mirrored between
  `ccvi-skills` SKILL.md and `ccvi-idea`'s `sidecar/src/agent_loop_wakeup.ts`, with an explicit
  do-not-reword comment. The wakeup's existing `note` payload carries the pointer instead.
- **CCVI does not reopen IDE windows on its own** to finish queued work. An orphan in a
  worktree nobody reopens stays an orphan; the requester's `expires` makes that failure loud
  and bounded. Closing that hole is a separate, bigger decision.
- **No `/repos forge` namespace.** See the asymmetry decision above.
- **No Disney-specific content enters the plugin.** ccvi-skills ships inside a distributable
  IntelliJ plugin zip. Site-specific material stays in `~/.dpp/`.

## Conventions this plan assumes

- 2-space soft tabs; Yoda naming (common part left); booleans prefixed `is`/`has`/`should`;
  no em dashes; Oxford comma.
- Skill shape follows the rule committed to `CLAUDE.md`: **one skill per noun, references per
  verb.** A SKILL.md body loads whole on invocation, so verb-specific depth goes in
  `references/` loaded on demand.
- Never name a specific release version in a step. Say "bump to the next version."
- `python3` may be assumed; the host guarantees it.

---

## Phase: Merge

### merge-inventory

**Anchor:** `dpp-skills/plugin/skills/{pr,idioms}/` and `dpp-skills/plugin/scripts/dpp_api.py`.

Move both skills and the shared script into `ccvi-skills/plugin/`, preserving
`skills/pr/defaults/PR_REVIEW.md`. Keep `pr` as its own skill directory for this todo; the
fold into `/repos` is Phase 2 and must not be entangled with the move, so that a failure in
either is attributable.

Sizes, for reference: `pr/SKILL.md` ~22.4 KB, `idioms/SKILL.md` ~13.7 KB,
`defaults/PR_REVIEW.md` ~5.8 KB, `dpp_api.py` ~48 KB and zero-dependency.

**Done when:** both skills are present under `ccvi-skills/plugin/skills/`, `dpp_api.py` is
under `ccvi-skills/plugin/scripts/`, and `python3 plugin/scripts/dpp_api.py selftest` exits 0
from the ccvi-skills checkout (all 7 suites).

### merge-paths

**Anchor:** the `${CLAUDE_PLUGIN_ROOT}/scripts/dpp_api.py` invocations in both SKILL.md files,
and the `DEFAULTS_REVIEW` constant in `dpp_api.py`.

Two couplings break on the move and must be fixed together:

1. Both SKILL.md files call `${CLAUDE_PLUGIN_ROOT}/scripts/dpp_api.py`. `CLAUDE_PLUGIN_ROOT`
   now resolves to the ccvi-skills plugin root, so the path is correct only once the script
   actually sits at `scripts/dpp_api.py` there.
2. `dpp_api.py` resolves layer-1 review defaults at `../skills/pr/defaults/PR_REVIEW.md`
   relative to itself. That relative path survives `merge-inventory` unchanged, but **not**
   `fold-pr-defaults` in Phase 2. Leave it alone here and change it there, in one commit with
   the file move.

**Done when:** `selftest` passes (it checks the shipped defaults parse), and invoking each
skill's script path from an installed build resolves without a "no such file" error.

### merge-guard

**Anchor:** `dpp-skills/scripts/guard_staged.sh`, `guard_install.sh`, and the
`.gitignore`-as-allowlist rules.

Bring the guard across and make it the merged repo's pre-commit hook. It is strictly additive
safety for the CCVI skills, and it has already earned its keep: during the dpp-skills v1 build
it refused an internal hostname in `doc/probes.md`.

Preserve the shape, not just the file: `.gitignore` is an **allowlist**, so a new top-level
path is invisible to git until un-ignored; `git check-ignore -v <path>` names the rule hiding a
path. The guard shares site-specific patterns from `~/.dpp/guard_patterns.txt` and runs
gitleaks, and a fresh clone needs `scripts/guard_install.sh` once.

**Done when:** the hook is installed in the ccvi-skills checkout, a deliberate test commit
containing a known-bad pattern is refused, and `git check-ignore -v` explains a newly added
top-level path.

### merge-doctrine

**Anchor:** `ccvi-skills/CLAUDE.md`, and `dpp-skills/CLAUDE.md` as the source to merge from.

Fold dpp-skills' doctrine in. Three items are load-bearing and must survive verbatim in
substance:

- **The generic-skill-text rule.** Site-specific material (approvers, slot counts, local
  idioms, skip paths, markers) lives in `~/.dpp/repos/<remote>/PR_REVIEW.md`, Keldon's own
  voice in `~/.dpp/PR_REVIEW.md`, runtime state under `~/.dpp`, credentials nowhere in the
  repo. **This is what makes the merge safe at all**: ccvi-idea bundles the skills zip into a
  distributable, so the moment this lapses, Disney-specific text starts riding inside it.
- **The layering framing.** dpp is the Program Manager and Personal Assistant; CCVI is the
  Developer. Keep it as the statement of what each skill is *for*, now that both live in one
  plugin and the repo boundary no longer carries that meaning.
- **The dependency-tier table**, newly written here, as the only remaining record of what
  could be lifted out later and what it would cost:

| tier | assumes | examples |
|---|---|---|
| 0 | nothing beyond Claude Code's model | `cleancode`, most of `plans` |
| 1 | Claude Code conventions (auto-memory dir, session ids) | `modes`, `seedprompt` |
| 2 | the CCVI host (sentinels, `~/.ccvi`, the sidecar poller) | `work`, `repos pr`, parts of `modes` |

The table is falsifiable, which is the point: a tier-0 skill can be grepped for `~/.ccvi` and
a violation caught.

Also record the namespace-ownership rule: **ccvi-skills owns the `.{suffix}.md` namespace**, so
one owner mints file types and two skills can never collide.

**Done when:** `CLAUDE.md` states all four items, and the "What this repo is" section lists six
skills rather than three.

### merge-manifest

**Anchor:** `ccvi-skills/.claude-plugin/marketplace.json`,
`ccvi-skills/plugin/.claude-plugin/plugin.json`, and `build.py`.

One plugin, one canonical version. Update the plugin description to cover all six skills. Bump
to the next version. Confirm `build.py` discovers and packages the two new skill directories
and the new `scripts/` entry without a change to its logic; if it enumerates skills explicitly
rather than by glob, extend that list.

**Done when:** `python3 build.py --check` exits 0, and the built zip contains both new skills,
`scripts/dpp_api.py`, and `skills/pr/defaults/PR_REVIEW.md`.

### merge-uninstall

**Anchor:** `~/.claude/plugins/installed_plugins.json`, entry `dpp-skills@dpp-skills`, and
`~/.claude/plugins/marketplaces/dpp-skills/`.

With both plugins installed, `pr` and `idioms` would register twice and the resolution order is
not something to leave to chance. Remove the dpp-skills plugin and its marketplace registration
after the merged build is installed, not before, so there is never a window with neither.

**Why this ordering:** `claude plugin install` is a no-op on an already-installed plugin;
`update` is what upgrades. So install-then-uninstall is the sequence that never leaves the
machine without the skills.

**Done when:** a fresh Claude Code session lists `pr` and `idioms` exactly once each, sourced
from ccvi-skills, and `installed_plugins.json` has no `dpp-skills` entry.

### merge-bbpi

**Anchor:** the BBPI ritual in `ccvi-skills/CLAUDE.md`.

Run it: bump `plugin/.claude-plugin/plugin.json`, `python3 build.py`, push, then
`unzip -o -q ccvi-skills.zip -d ~/.ccvi/ccvi-skills/plugin/`.

**The unzip is the step that matters.** The live copy this machine runs is the extracted
artifact at `~/.ccvi/ccvi-skills/plugin/`; the zip inside a ccvi-idea build is only a
provisioning seed for fresh installs. A plugin restart alone never picks up a new suite
version.

**Done when:** `python3 test/test_modes.py` exits 0, `python3 build.py --check` exits 0, and a
**new** Claude Code session (not this one) lists all six skills. New and changed skills register
in the next session, not the current one.

---

## Phase: PR fold

### fold-pr-verb

**Anchor:** `plugin/skills/repos/SKILL.md` frontmatter and its invocation table.

`pr` becomes a `/repos` noun verb taking a required action from a closed set:

```text
/repos pr {start|create|followup|test|approve|merge} [args]
```

This is the shape `/cleancode` already uses (`argument-hint: "[noun] [verb] [args]"`), so it is
the plugin's established pattern rather than a new one.

**Why a noun layer and not a flat merge.** `/repos`' own verbs operate on the local Forgejo
round-trip; `pr`'s operate on GitHub through the repo's own agent. Those are different machines
doing different work, and a flat 14-verb list hides that. The noun layer also means nothing is
renamed: `/repos review` (local forge) and `/repos pr start` (dispatch) coexist.

**Note the overlap is NOT a name collision.** `/pr` has no `review` verb. Its verbs are `start`,
`create`, `followup`, `test`, `approve`, and `merge`, and `/pr create` already drives `/repos`'
`open`, `review`, `status`, and `export`. So `pr` is a **layer calling** `/repos`, which is the
actual argument for folding them, and that internal call path must keep working after the fold:
it becomes an intra-skill dispatch rather than a cross-skill one.

**Done when:** `/repos pr start` and `/repos pr create` dispatch correctly in a session, each
reaching the same behavior as the pre-fold `/pr` equivalent, and `/pr` as a standalone skill no
longer exists.

### fold-pr-references

**Anchor:** the numbered step sequence in the pre-fold `pr/SKILL.md` (steps 4 through 15).

Push per-action depth into `plugin/skills/repos/references/pr_<action>.md`, leaving the merged
SKILL.md carrying dispatch plus shared doctrine only.

**Why:** the rule in `CLAUDE.md` is one skill per noun, references per verb, precisely because a
SKILL.md body loads whole on invocation. `/repos` is ~7.7k tokens today and `pr` adds ~5.6k;
unmanaged, the merged skill approaches `modes`' 16.6k, which is the one skill already flagged as
an outlier. The noun layer gives a clean file-per-action boundary, and steps 4-15 are the
natural split.

Shared PR doctrine (the layered-defaults resolution, the repo-agent dispatch convention) stays in
the body: it is shared, so it must be single-sourced.

**Done when:** `repos/SKILL.md` is at or below roughly its pre-fold size, each
`references/pr_<action>.md` exists, and running each action reads only its own reference.

### fold-pr-schema

**Anchor:** the `verbs:` block in `repos/SKILL.md` frontmatter, its `description:`, and the
help-output diagram.

Add `pr` to the host-facing `verbs:` schema with the action as a suggested-value param:

```yaml
  pr: { order: 9, params: [ { name: action, type: string, required: true,
                              suggestions: [ start, create, followup, test, approve, merge ] },
                            { name: args, type: string, required: false } ] }
```

**There is no PR action picker, and this work does not imply one.** Probed in ccvi-idea: the
`verbs:` frontmatter is consumed two ways, and only one of them is structured.

- `sidecar/src/skills_manifest.ts` harvests verbs for **every** skill, but takes only `v?.name`
  — a flat list of names, rendered as text by `SettingsModal.tsx` in the skills display.
- `sidecar/src/webview.ts` reads the **plans** skill specifically (`if (!plans ||
  !Array.isArray(plans.verbs)) { return; }`) and posts `planVerbSchema`, which
  `webview/state/plan_phase.ts` turns into the plan-phase picker. That picker is plans-only.

So the schema entry buys two things here: the Settings skills display stays accurate, and a
future host that wants a repos picker has the params already described. It does **not** render a
dropdown today.

**This makes the `description:` line matter MORE, not less.** Because the manifest harvests only
verb names, folding six actions behind one `pr` verb makes them invisible to the Settings
display. The description must therefore list them inline the way cleancode's does
(`pr start/create/followup/test/approve/merge`) — that line is the only always-resident
discoverability the six actions get.

**Watch the two mirrored artifacts.** The `/plans` lifecycle diagram rule has a sibling here: the
help output and the README must agree, and `build.py --check` fails on drift. Also keep the
existing note that `verbs:` `order:` is a host MENU order, deliberately not execution order.

**Done when:** `build.py --check` exits 0, and the frontmatter round-trips through a YAML parser.

### fold-pr-defaults

**Anchor:** the `DEFAULTS_REVIEW` constant in `plugin/scripts/dpp_api.py`, and
`skills/pr/defaults/PR_REVIEW.md`.

Move the defaults to `skills/repos/defaults/PR_REVIEW.md` and repoint `DEFAULTS_REVIEW`, which
currently resolves `../skills/pr/defaults/PR_REVIEW.md` relative to the script.

**Do the move and the constant in one commit.** The script's `selftest` asserts the shipped
defaults parse, so a half-applied change fails loudly rather than silently reading a stale path,
but only if both halves are in the same change.

**Done when:** `python3 plugin/scripts/dpp_api.py selftest` exits 0 with all 7 suites passing,
and no path in the repo still references `skills/pr/`.

---

## Phase: Work skill

### Durability tiers (the reasoning the whole phase rests on)

| Survives | Mechanism | Dies when |
|---|---|---|
| turn to turn | context, `active_modes.md` | the session ends |
| session to session | the fired re-entry brief re-deriving the mode | the successor misreads it |
| session to session | sidecar-held live config (how YOLO crosses) | the IDE window closes |
| everything | files keyed by the **work** | never |

The response obligation outlives every session and window that touches it, so it sits in the
bottom tier. That is why there is no new mode: `active_modes.md` is keyed by session id and a
rollover legitimately gets a fresh one.

### work-contract

**Anchor:** new file `doc/contracts/work.md` (mirroring ccvi-idea's `doc/contracts/` convention).

Write the contract another repo builds against, before writing the skill. It specifies:

**Two document types.** `.request.md` and `.response.md`, joining `.plan.md`, `.review.md`, and
`.verify.md`. Minimum frontmatter, with a named reader for each field, since a field with no
named reader should not exist:

| Field | Who reads it | What they do |
|---|---|---|
| `id` | the requester | matches an arriving response to the request it sent |
| `responseDir` | relay agents, and the monitor | where the response goes; survives every hop |
| `created` | the receiving agent | is this work from ten minutes ago or last Tuesday |
| `expires` | the receiving agent, before starting | declines stale work rather than doing it pointlessly |

A `.response.md` additionally carries `inResponseTo`, holding the request's `id`. That is the
email `Message-ID` / `In-Reply-To` shape, copied deliberately because it generalizes to chains
with no new machinery. Deliberately **absent**: a `from` field. `responseDir` already carries the
only operational fact, and `from` is where knowledge of a particular requester would creep back in.

**The receipt.** One file per work item at `~/.ccvi/work/<id>.md`, updated in place, accumulating
the request body, the claim, and finally the response body:

```yaml
id: <opaque>
state: open | claimed | responded | closed
requesterDir: <abs path>
responseDir: <abs path>
claimedCwd: <abs path>
claimedAt: <ISO 8601 UTC>
created: <ISO 8601 UTC>
expires: <ISO 8601 UTC>
```

**The guarantee, stated honestly: at-least-once delivery, deduped by the requester.** Not
exactly-once, which would need coordination we do not have.

**The invariant that makes loss impossible:**

> A request leaves `claimed` only after its response is durably written.

Walk the crash points: before the response, the receipt is still `claimed` and the obligation is
intact; after the response but before the state change, also still `claimed`, so the work is
picked up again and responds a **second** time; after, correct. The only bad outcome is a
duplicate, and a duplicate is deduped on `id` and `inResponseTo`. Reverse the order and the same
crash silently eats the work.

**The orphan rule, which reuses `agent_state` verbatim:**

> orphan = a receipt with `state: claimed` whose `claimedCwd` has no `agent_state` record
> fresher than 60s

Claim by **cwd**, never by session id: a rollover legitimately changes the session id while the
work continues in the same window, so a session-id claim would let an orphan sweep steal live
work. Claiming by cwd survives rollovers and sidecar respawns, needs no lease file and no
re-claim step an agent could forget, and fails exactly when the IDE closes, which is exactly when
the work *is* orphaned.

**Closure is single-writer and belongs to the requester**, in both outcomes: accepted response
→ `closed`, deadline passed with nothing → `closed` as expired. A worker never closes a receipt;
it only moves it to `responded`. That is what lets closure be a plain tmp-plus-rename with no
locking.

**Closing tombstones, it does not delete.** Shed the request and response bodies, keep `id`,
`inResponseTo`, and `closedAt`. **Deleting would destroy the dedupe key the at-least-once
guarantee rests on**: a worker that crashed after writing its response will respond again on
resume, and a requester with no record reads that as novel and may act twice. Tombstones prune on
the repo's existing 7-day convention. A write to a missing or closed receipt is a **no-op plus a
log line, never a recreate** — otherwise a late duplicate resurrects a closed item.

**Done when:** the doc states the two document types, the receipt shape, the guarantee, the
invariant, the orphan rule, and the closure rules, and a reader could implement the dpp side
against it without reading the skill.

### work-skill

**Anchor:** new `plugin/skills/work/SKILL.md`.

Two verbs, both arity 2, with the identical tuple `(destinationDir, documentPath)`:

```text
/work request  {dir} {mdPath}
/work response {dir} {mdPath}
```

**Why the response destination is in the document and not the signature.** A relay cannot lose
the return address: relaying becomes "copy this file to another dir" and `responseDir` travels
with the work by construction, rather than depending on a relay agent remembering to pass a third
argument. It also makes the document independently valid, and lets the detached monitor find the
destination without extra plumbing.

The chain, with the return address carried rather than rewritten:

```diagram
  requester  -> /work request  {repoDir}     {md}       responseDir: requesterDir
  main agent -> /work request  {worktreeDir} {md}       same md, verbatim
  worktree   -> /work response {requesterDir} {md}      leaf
```

**Why two verbs rather than one with an optional third argument.** Fixed arity per verb. The
earlier single-verb shape encoded "this message is terminal" in a *missing argument*, so a
recipient had to read the body to learn whether it was being asked to do something or told
something. Two verbs put that in the structure. It also names the relay's refusal correctly: when
the occupancy check finds no capacity, that is a `response` (the outcome of the request it
received), not a new request.

**The routing doctrine the SKILL.md carries, for the agent to apply:**

- Worktree discovery is `git worktree list --porcelain`, run from anywhere in the repo. It lists
  **every** worktree including the main checkout, so there is no "am I main or a worktree?"
  question and no registry. There are just N candidate directories.
- Occupancy is the `agent_state` record for each candidate's cwd, with the 60s staleness bound.
- Preference order: reuse an open-but-idle window, then an unoccupied existing worktree, then
  create a new one if under the per-repo cap, else respond "no capacity".
- **Do not special-case the main checkout.** `human-driven` already skips it when Keldon has been
  there and allows it when he has not, which is better than a blanket rule.
- The per-repo cap is config, default 5. Android repos want roughly 2.
- A created worktree's path follows a stated convention, named in config alongside the cap.

**Transport placement.** The drop that starts a turn goes in the **per-worktree git dir**, not
the working tree: these are Disney repos and a stray file in `git status` is noise at best and a
committed file at worst. Resolve it with the same logic as `paths.gitDir()` in ccvi-idea's
sidecar: `.git` for a plain clone, the `gitdir:` target for a worktree. Per-worktree is the
point, since a drop there is visible to exactly one window and two worktrees can never consume
each other's work.

Filename `<created>-<id>.request.md`, timestamp first so lexical sort gives oldest-first
consumption, which the many-to-one reply case needs.

**Done when:** a request issued in one repo reaches a second repo's window, is worked, and a
`.response.md` arrives back, with the receipt ending `closed` and the whole round trip visible in
`~/.ccvi/work/`.

### work-receipts

**Anchor:** new `plugin/skills/work/tools/` helper, invoked by both verbs.

Implement the receipt operations, each a single tmp-plus-rename so there is no multi-file
consistency to reason about:

- `open` — mint a receipt from a request document
- `claim` — record `claimedCwd` and `claimedAt`, state → `claimed`
- `respond` — append the response body, state → `responded`, **only after** the response
  document is durably written
- `close` — tombstone: shed bodies, keep `id`, `inResponseTo`, `closedAt`
- `orphans` — one readdir, returning receipts whose `claimedCwd` has no fresh `agent_state`

All four durable-tier reads and writes live under one filesystem so every state change is an
atomic rename.

**Done when:** a unit test covers the invariant (a simulated crash between response-write and
state-change yields a duplicate, never a loss), the orphan rule against a stale `agent_state`
record, and that a write to a closed receipt is a no-op.

### work-monitor

**Anchor:** new `plugin/skills/work/tools/` monitor, launched detached by `request`.

Scope it narrowly: the monitor covers the **short** window only. Did a window come up, and did
the request leave the drop directory within the pickup deadline. On lapse it writes a
`.response.md` saying "not picked up" and exits. It never tries to outlive the work, because
completion is reported by whoever does the work via its own `response`.

**Two mechanics that are not optional:**

- **It must survive the IDE closing.** `setsid` is absent on macOS and CCVI itself uses process-
  group kills, so `nohup` alone is insufficient. Use Node `spawn(..., { detached: true, stdio:
  'ignore' }).unref()`, which is also the Windows-portable choice.
- **It must survive sleep.** Compare `Date.now()` against a stored deadline on each tick; never a
  single long `setTimeout`. This is the doze-proof pattern `agent_loop_wakeup.ts` already uses.

**Done when:** the monitor outlives a deliberate IDE quit, a lapsed deadline produces a
`.response.md` at the carried `responseDir`, and a machine sleep across the deadline still fires.

### work-sidecar-handoff

**Anchor:** a written spec handed to the ccvi-idea session; **no code in this repo**.

The consuming half lives in ccvi-idea's sidecar and is not ours to write. Hand it across the
seam with the three things it needs:

1. **The drop poller.** Glob `*.request.md` in the per-worktree git dir on startup once ready,
   and on the existing tick. Consume oldest-first. This **replaces** the fixed `auto_prompt.md`
   filename from the earlier design, which is strictly better: the fixed name was what created
   the overwrite hazard when replies are many-to-one.
2. **Consumption is a claim, not a delete.** Record the claim in the receipt before injecting
   the turn, so a crash between the two is recoverable rather than a silent loss.
3. **Orphan resume on window open.** In the same pass that scans for new drops, check for
   receipts claimed by **this** cwd. Anything there is this window's own orphan and its
   obligation to resume, which makes recovery entirely local: the only window that can resume
   that work is the one that owns the directory.

Also name the free reminder channel: the agent-loop wakeup's existing `note` is appended verbatim
to the brief at `agent_loop_wakeup.ts:430`, so an outgoing session can hand its successor the
active receipt's path with no change to the frozen brief. It is a **per-generation relay**, not a
durable store, since each successor arms its own wakeup; the receipt is what makes a dropped link
recoverable.

**The compliance gate, recorded because it is a guardrail.** ccvi-idea's CLAUDE.md forbids
introducing automation that runs Claude without a per-turn user action, and says to stop and flag
it for a human. That was done, and **Keldon decided to proceed**, qualified: the target case is a
freshly launched CCVI instance, where opening the IDE window on a directory is itself the human
action that starts the work. Anyone revisiting the sidecar side must read that decision rather
than re-deriving it, and must not widen it.

**Done when:** the ccvi-idea session has the spec, has confirmed the three behaviors, and the
round-trip in `work-skill`'s done-when passes against an installed CCVI build.
