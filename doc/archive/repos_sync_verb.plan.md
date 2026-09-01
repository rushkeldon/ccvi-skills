---
humanEngineerDifficulty: 3
name: "repos: add a sync verb so the forge never lags the origin"
version: "1.1"
overview: "The repos skill can already refresh the forge, but only as a side effect of open, which also drafts prose and creates a PR. Add a dedicated sync verb that pushes origin's base and the current branch to the forge and stops there - base always, branch fast-forward-only unless explicitly forced, because force-pushing a rebased branch can strand the inline review comments the forge exists to hold."
todos:
  - id: sync-verb-section
    content: "Write the `## Verb: sync` section in plugin/skills/repos/SKILL.md, placed between the config and open sections"
    status: completed
    phase: "Skill prose"
  - id: verbs-frontmatter
    content: "Add sync to the machine-readable verbs: block in SKILL.md frontmatter and renumber order for open through export"
    status: completed
    phase: "Skill prose"
  - id: invocation-table
    content: "Add the sync row to SKILL.md's Invocation table, between config and open"
    status: completed
    phase: "Skill prose"
  - id: help-output
    content: "Add the sync bullet to SKILL.md's Help output cheat-sheet"
    status: completed
    phase: "Skill prose"
  - id: cross-references
    content: "Point open and status at sync - open's idempotent-re-run note and status's base-drift line"
    status: completed
    phase: "Skill prose"
  - id: readme-verb-list
    content: "Add sync to the repos row of README.md's verb list"
    status: completed
    phase: "Skill prose"
  - id: manifest-skills
    content: "Add the sync verb to the repos entry of MANIFEST_SKILLS in build.py, between config and open"
    status: completed
    phase: "Skill prose"
  - id: version-and-build
    content: "Bump the canonical version in plugin/.claude-plugin/plugin.json, run build.py, then build.py --check"
    status: completed
    phase: "Verification"
isProject: false
updates:
  - type: review
    model: "claude-fable-5"
    at: "2026-09-01T16:48Z"
    version: "1.1"
---

# repos: add a sync verb so the forge never lags the origin

## Problem / Context

The forge only earns its keep if it reflects the real repo. Today refreshing it is possible
but awkward: it happens as **steps 4 and 5 of `open`**, whose own note reads *"Idempotent
re-run: pushes again, re-syncs the base, refreshes the drift note; the existing PR is
reused."* So the capability exists - but reaching it means running a verb that also drafts a
title and description and creates-or-gets a PR. Three consequences:

1. **Nobody reaches for it.** "Re-run `open` to sync" is not a thing a user thinks of, and
   `status` reports base drift without offering a way to fix it.
2. **It is not cheap.** `open` generates prose, which costs tokens and produces output a
   human may feel obliged to read, for an operation that should be two pushes.
3. **It is not safe to run reflexively.** Because it can create a PR, it is not something
   you would wire to a hook or run in a loop.

Observed on 2026-09-01 against `disney/android-dmgz` on a live instance: after rebasing the
feature branch onto a base that had moved 49 commits, bringing the forge current took a
manual `git push forge origin/development:refs/heads/development` plus a
`git push --force-with-lease forge <branch>` - the exact two operations `sync` should own.

**The asymmetry that shapes the design.** The base branch can only ever be *behind* origin,
so pushing it is always safe and always right. The feature branch is different: the skill's
load-bearing primitive is inline comments anchored to `path` + line with a resolved flag,
and `export` transfers only the unresolved ones. **Force-pushing a rebased branch can strand
those anchors**, which destroys exactly the artifact the forge exists to accumulate. So
"never let it lag" is true of the base and conditionally true of the branch, and the verb
must encode that rather than paper over it.

## Approach

**A new top-level verb, not a flag.** `/repos sync` does two things and stops: push
`origin/<base>` to the forge, then push the current branch. No template resolution, no
drafting, no PR call. Discoverability is the point - a flag on `open` would work identically
and nobody would find it.

**Base always; branch fast-forward-only.** The base push is unconditional. The branch push
is attempted as a normal (non-forced) push: when it fast-forwards, it succeeds silently.
When it is rejected as a non-fast-forward - which means the branch was rebased or amended -
`sync` **stops and reports** that forcing would update the forge but may strand inline
review threads, and waits for an explicit `force` argument. This is the whole safety model,
and it costs one boolean.

**Current repo only.** Every other verb operates on the repo the session stands in, and the
manifest records config per origin URL but **not** a local clone path. Manifest-wide sync
would need that field added and populated, plus handling for dirty trees and detached HEADs
in repos nobody is looking at. Deliberately deferred; the verb takes no repo argument.

**Reuse the credential preflight.** `sync` is pure git, so it hits the same wall `open` did
before the credential step existed. Run `forge check-git-credentials` first and stop on a
non-zero exit with its `next_action`, exactly as `open`'s preflight does.

## Conventions & assumptions

- **Files that change:** `plugin/skills/repos/SKILL.md`, `README.md`, `build.py`
  (the `MANIFEST_SKILLS` repos entry), and `plugin/.claude-plugin/plugin.json` (version
  only). **`tools/repos_api.py` does not change** - `sync` is git-only, and the tool
  already provides the one call it needs (`forge check-git-credentials`).
- **Adding a top-level verb touches four surfaces in SKILL.md** - the `verbs:` frontmatter
  block, the Invocation table, the verb's own section, and the Help output cheat-sheet -
  **plus a fifth outside it: `MANIFEST_SKILLS` in `build.py`**, the canonical source of
  `manifest.json`, the signatures contract ccvi-idea consumes; CLAUDE.md requires that
  update in the same commit as the SKILL.md change. Note the limits of the tripwire:
  `build.py --check`'s `manifest_drift()` only verifies that every MANIFEST verb appears
  in the prose (manifest → prose) - a new verb present in the prose but missing from
  `MANIFEST_SKILLS` passes `--check` clean, so the manifest step cannot be caught by the
  build; it has to be done deliberately.
- **Verb ordering matters.** The `verbs:` block carries an explicit `order:` a host uses to
  render its verb menu. `sync` belongs at **order 3** - after `config`, before `open` -
  because that is its place in the lifecycle: configure, sync, open. Every later verb's
  `order` shifts by one.
- **Casing:** plain lowercase, per the cross-skill rule. `sync` names no proper noun.
- **Prose style matches the existing verb sections:** a one-line summary, then numbered
  steps in order, then edge cases. Follow `open`'s shape closely - `sync` is a subset of it.
- **Assumes the canonical version is `0.0.12`** (`plugin/.claude-plugin/plugin.json`) at the
  time of writing, and that `build.py` stamps it into each skill's help header. If the
  version has moved on, bump from whatever is current rather than to a literal - the plan
  must not hard-code a release number.
- **Assumes `--force-with-lease` is the force flavour**, never bare `--force`: it refuses
  when the forge has commits the local clone has not seen, which is the one case where
  forcing would destroy someone else's push rather than just re-anchoring comments.
- **Assumes the `forge` remote already exists.** `sync` does not create the forge repo or
  wire the remote - that is `open` steps 2 and 3. A missing `forge` remote is an error that
  tells the user to run `open` first, not something `sync` silently fixes.

## The steps

### 1. `sync-verb-section`

**Anchor:** in `plugin/skills/repos/SKILL.md`, insert a new `## Verb: sync` section between
the end of `## Verb: config` and the line `## Verb: open`.

Write the section with this content, matching the surrounding prose style:

```text
## Verb: sync

**`/repos sync [force]`** - bring the forge current with the origin. Pushes the base
branch and the current branch to the forge and stops: no drafting, no PR call. Cheap,
deterministic, and safe to run as often as you like.

Steps, in order:

1. **Preflight credentials:** `forge check-git-credentials`. Non-zero exit → STOP and
   surface its `next_action`; push nothing.
2. **Require the forge remote.** No `forge` remote → STOP and say to run `/repos open`
   first; `sync` never creates the repo or wires the remote.
3. **Sync the base** (always): `git fetch origin <base>` then
   `git push forge origin/<base>:refs/heads/<base>`. The base can only ever be behind,
   so this is unconditional. Report the commit range it moved.
4. **Sync the branch** (fast-forward only): `git push forge <branch>`. On success,
   report it. On a non-fast-forward rejection - meaning the branch was rebased or
   amended - **STOP** and report that forcing would bring the forge current but may
   strand inline review threads anchored to the old commits; name `force` as the way to
   proceed.
5. **With `force`:** `git push --force-with-lease forge <branch>`. Never bare `--force`.
   Say plainly in the report that forge review anchors may now be stale.
```

Add an **edge cases** tail to the section: base and branch identical (nothing to do for step
4); branch not present on the forge yet (a normal push creates it, no force needed); the
lease failing under `--force-with-lease` (someone else pushed - stop, do not retry with
`--force`).

**Why:** this is the verb. Everything else in the plan is registration and cross-reference.

**Done when:** the section states the base-always / branch-fast-forward-only rule and names
the review-anchor risk explicitly, and a reader can execute all five steps without leaving
the section.

### 2. `verbs-frontmatter`

**Anchor:** the `verbs:` block in SKILL.md's YAML frontmatter, currently `init` order 1
through `export` order 6.

Insert `sync` at order 3 and shift the rest:

```yaml
  sync:    { order: 3, params: [ { name: force, type: boolean, required: false } ] }
```

`open` becomes 4, `review` 5, `status` 6, `export` 7. Match the existing block's alignment -
the values line up in a column.

**Why:** a host renders its verb menu and generates each verb's dialog from this block, so an
unregistered verb is invisible there even though the prose documents it.

**Done when:** the block round-trips through a YAML parser, orders read 1-7 with no
duplicates, and `force` is the only param on `sync`.

### 3. `invocation-table`

**Anchor:** the Invocation table's row beginning `| `/repos config {kind}`.

Add beneath it:

```text
| `/repos sync [force]` | Push the base and current branch to the forge - no drafting, no PR |
```

**Why:** the table is the first thing a reader sees; a verb absent from it reads as
undocumented.

**Done when:** the table lists seven verbs plus the blank-verb row, in the same order as the
`verbs:` block.

### 4. `help-output`

**Anchor:** inside the `## Help output` fenced block, the line beginning
`• config {kind} [origin] [value]`.

Add beneath it, matching the existing column alignment exactly (the descriptions align on a
single column across all bullets):

```text
• sync [force]                      — push base + current branch to the forge; no PR
```

Leave the version line alone - `build.py` owns that string.

**Why:** the cheat-sheet is what prints on a blank or unknown verb, and `build.py --check`
compares verb names here against the prose.

**Done when:** the bullet's description starts in the same column as its neighbours, and the
version line is byte-identical to before.

### 5. `cross-references`

**Anchor:** two places. First, `## Verb: open`'s closing note beginning `**Idempotent
re-run:**`. Second, in `## Verb: status`, the numbered item whose literal text is
`**Base drift:**` (the bold sits on the words, not the number).

- In `open`: after the idempotent-re-run sentence, add that when only a refresh is wanted,
  `sync` does steps 4 and 5 alone without drafting or touching the PR.
- In `status`: after the base-drift line, name `sync` as the fix - `status` currently reports
  drift and leaves the reader to work out what to do about it.

**Why:** the capability already half-existed and nobody found it; the fix is as much
signposting as it is a new verb.

**Done when:** both sections mention `sync` by name, and `open`'s note no longer reads as the
only way to refresh the forge.

### 6. `readme-verb-list`

**Anchor:** `README.md`, the table row beginning `| repos | ` - specifically its `<ul>` of
verbs, between the `config` and `open` `<li>` entries.

Add an `<li>` for `sync` with its one `force` param, matching the nested-list style the other
verbs use.

**Why:** the README table is the out-of-session surface where someone decides whether the
skill does what they need.

**Done when:** the repos row lists seven verbs and the HTML nesting still renders.

### 7. `manifest-skills`

**Anchor:** in `build.py`, the `"repos"` entry of `MANIFEST_SKILLS` - its `"verbs"` list,
between the `config` and `open` entries.

Insert, matching the surrounding entries' style:

```python
      {"name": "sync", "params": [_param("force", False, "flag")]},
```

**Why:** `MANIFEST_SKILLS` is the canonical source of `manifest.json`, the machine-readable
signatures contract ccvi-idea consumes to render verb menus and dialogs - a verb absent
here is invisible to the host even with all four SKILL.md surfaces done. CLAUDE.md requires
this edit in the same commit as the SKILL.md verb change, and `--check` cannot catch its
omission (its tripwire runs manifest → prose only), so this step is load-bearing, not
belt-and-braces.

**Done when:** the repos entry lists seven verbs with `sync` third, and the rebuilt
`manifest.json` (after step 8's build) shows `sync` with a single optional `force` param of
kind `flag`.

### 8. `version-and-build`

A new verb is a capability change, so bump the canonical version and re-stamp.

```bash
# bump "version" in plugin/.claude-plugin/plugin.json to the next patch
python3 build.py
python3 build.py --check
```

**Why:** the canonical version lives in the plugin manifest and `build.py` stamps it into
every version display, including each skill's help header. `--check` then verifies the
displays are in sync and, via its manifest → prose tripwire, that every manifest verb
(including the new `sync` from step 7) is named in the SKILL.md prose. It does NOT catch a
verb present in prose but missing from `MANIFEST_SKILLS` - that is why step 7 exists as an
explicit step.

**Done when:** `python3 build.py --check` exits 0, and `/repos` with no verb prints a
cheat-sheet containing the `sync` bullet and the new version.

## Out of scope

- **Manifest-wide or named-repo sync.** Needs a local clone path per manifest entry, plus
  dirty-tree and detached-HEAD handling for repos nobody is standing in. A follow-up.
- **Pulling *from* the forge.** `sync` is one-directional: origin → forge. The forge is a
  review surface, never a source of truth for code.
- **Pushing to origin.** `export` owns the only outward-facing push, and that stays gated.
- **Creating the forge repo or the `forge` remote.** `open` steps 2 and 3; `sync` requires
  them and says so.
- **Any change to `tools/repos_api.py`**, including a `sync` subcommand. The verb is git
  plus one existing tool call.
- **Re-anchoring or migrating inline comments after a force-push.** There is no API for it
  (the resolved flag is read-only per the skill's own probe evidence), so the verb warns
  rather than repairs.
- **Automatic invocation.** Nothing runs `sync` as a side effect - not `status`, not
  `review`. It stays a verb the user calls, consistent with the skill's no-auto-chaining
  rule.

## Verification

1. `python3 build.py --check` exits 0.
2. `/repos` with no verb prints a cheat-sheet whose bullets include `sync [force]`, aligned
   with its neighbours.
3. The `verbs:` block parses and reads `order:` 1-7 with `sync` at 3.
4. `grep -c "sync" plugin/skills/repos/SKILL.md` shows hits in all four required surfaces:
   frontmatter, Invocation table, its own section, Help output.
4b. The rebuilt `manifest.json` lists `sync` in the repos entry, third, with one optional
   `force` param - `python3 -c "import json; print([v['name'] for s in
   json.load(open('manifest.json'))['skills'] if s['name']=='repos' for v in s['verbs']])"`.
5. Behavioural, on a repo whose forge branch is behind by a fast-forward: `/repos sync`
   pushes base and branch, reports both, and creates no PR - verified by the forge PR count
   being unchanged.
6. Behavioural, on a **rebased** branch: `/repos sync` pushes the base, refuses the branch,
   and names the review-anchor risk. `/repos sync force` then completes it via
   `--force-with-lease`.
7. With no `forge` remote: `/repos sync` stops at step 2 and points at `open`, having pushed
   nothing.

**Escape hatch:** if the skill's structure has moved - a different `verbs:` shape, a
renumbered runbook, `build.py` no longer cross-checking verb names - **STOP and surface it.
Do not improvise**; steps 2 through 4 and step 7 are registration against exact surfaces,
and a partial registration is worse than none.
