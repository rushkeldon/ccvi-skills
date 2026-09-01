---
humanEngineerDifficulty: 7
name: /repos skill - local-forge PR pipeline
overview: "New /repos skill in ccvi-skills: iterate a PR to polish on a LOCAL forge (Forgejo), then export the refined result - branch, description, and only the UNRESOLVED review comments - to the origin (GitHub) as a pending review. Verbs: init, config, open, review, status, export."
version: "1.1"
todos:
  - id: scaffold-skill
    content: "Scaffold plugin/skills/repos/SKILL.md: frontmatter (name, description, argument-hint, allowed-tools, verbs schema) + invocation table + shared sections (forge adapter contract, config root, tokens)"
    status: completed
    phase: "P1 skeleton"
  - id: config-verb
    content: "Write the config verb section in SKILL.md: /repos config {kind} [origin] [value], kinds template|directions|base, import-not-reference, show-when-no-value"
    status: completed
    phase: "P1 skeleton"
  - id: init-verb
    content: "Write the init verb section in SKILL.md: brew install forgejo, localhost-only + SQLite first-run, org namespaces, token provisioning into ~/.config/repos/, idempotent re-run"
    status: completed
    phase: "P2 plumbing"
  - id: run-init
    content: "Run /repos init on this machine following the just-written section: brew install forgejo, localhost-only + SQLite first-run, brew services start, admin user, org namespaces, token into ~/.config/repos/forge_token (0600), manifest.json scaffolded; fix the section wherever the runbook and reality diverge"
    status: completed
    phase: "P2 plumbing"
  - id: spike-resolved-flag
    content: "SPIKE: probe the live localhost Forgejo (stood up by run-init) for the resolved flag on PR review comment threads via API; record the field name in SKILL.md, or fall back to the reply-marker convention if absent"
    status: completed
    phase: "P2 plumbing"
  - id: api-tool
    content: "Build tools/repos_api.py: zero-dep python3 CLI wrapping the Forgejo REST API (repo create, PR create/get, reviews+comments list with resolved state, branch sync check) and the GitHub export primitives via gh api (PR create, pending review with inline comments)"
    status: completed
    phase: "P2 plumbing"
  - id: open-verb
    content: "Write the open verb section in SKILL.md: bootstrap forge counterpart + remote, sync base, push branch, draft description through template + directions, create-or-refresh the forge PR"
    status: completed
    phase: "P3 verbs"
  - id: review-verb
    content: "Write the review verb section in SKILL.md: inline Claude review of the forge PR diff, findings posted as inline forge comments via tools/repos_api.py, phrased per directions"
    status: completed
    phase: "P3 verbs"
  - id: status-verb
    content: "Write the status verb section in SKILL.md: thread counts, export preview, base drift, AI-trailer preflight scan"
    status: completed
    phase: "P3 verbs"
  - id: export-verb
    content: "Write the export verb section in SKILL.md: preflight (directions + trailer scan), push to origin, create origin PR with description verbatim, replay unresolved root comments as a PENDING review; dryRun prints the full payload"
    status: completed
    phase: "P3 verbs"
  - id: manifest-and-bbp
    content: "Add repos to MANIFEST_SKILLS in build.py (verbs + ordered params) plus a STAMPS entry for the repos help header; flip the plans review/verify out-param manifest defaults from ./ to plan-dir; run python3 build.py && --check && test/test_modes.py, then BBP (bump plugin/.claude-plugin/plugin.json to the next version, build, commit, push)"
    status: in_progress
    phase: "P4 ship"
isProject: false
updates:
  - type: review
    model: "claude-fable-5"
    at: "2026-08-31T18:02Z"
    version: "1.1"
---

# /repos skill - local-forge PR pipeline

## Problem / Context

Keldon works on feature branches in company (Disney) and personal repos. He wants to
iterate a PR to a polished state **privately, locally** - open it on a local forge,
have Claude review it as durable inline comments, fix and resolve threads - and then
**export the refined result** to the real origin (GitHub / GitHub Enterprise): the
branch, the PR description verbatim, and **only the root comments of threads still
unresolved** at export time. Resolved threads transfer nothing (their result is
already in the code). The export lands as a **pending review** on GitHub so a human
submits it - the skill stages, never publishes.

The local forge is **Forgejo** (brew, single binary, SQLite, localhost-only), but the
skill is named `/repos` and written against a **forge adapter contract**, not a
vendor: PRs, inline comments anchored to path+line, a resolved flag on threads, and a
REST API. Forgejo and Gitea share a GitHub-shaped API, so one adapter covers both.

This skill joins the ccvi-skills suite (`plugin/skills/repos/`), shipped by the same
build/manifest/zip pipeline as `modes`/`plans`/`seedprompt`/`cleancode`.

## Approach

The skill is **prose-driven orchestration + one bundled tool**. The SKILL.md
instructs the session (git operations, drafting, review judgment, conversation);
deterministic API plumbing lives in a bundled zero-dependency python3 CLI,
[tools/repos_api.py](../plugin/skills/repos/tools/repos_api.py) (python3 is the
suite's established script runtime - `modes.py` precedent; node is NOT reliably on
the agent PATH in this environment).

Verb surface (final, from the design conversation):

```text
/repos init                              one-time: install + configure the forge
/repos config {kind} [origin] [value]    per-repo config: template | directions | base
/repos open [branch] [base]              push branch to forge, open/refresh local PR
/repos review [pr]                       Claude review -> inline forge comments
/repos status [pr]                       threads, export preview, preflight warnings
/repos export {pr} [dryRun]              transfer to origin as a pending review
```

Key structures:

- **Config root `~/.config/repos/`** - `manifest.json` maps origin URL -> entry dir;
  each entry holds `template.md`, `directions.md`, and settings (`base` branch, forge
  org). Keyed by origin URL so a re-clone still matches. Config files are **imported**
  (copied in, the copy canonical), never referenced at their source path.
- **Tokens** - GitHub side uses the already-authenticated `gh` CLI; the Forgejo token
  lives at `~/.config/repos/forge_token` (0600), written by `init`, read by the tool.
  Tokens never enter any repo or the skill itself.
- **Namespacing** - one Forgejo instance, one DB; `open`'s bootstrap creates the forge
  counterpart under the org named in the repo's config entry (e.g. `personal`,
  `disney`), giving per-origin separation inside a single instance.
- **Stage directions** - per-repo standing instructions (e.g. "no mention of AI as a
  collaborator in commits, descriptions, or comments") consumed by every verb that
  writes prose (`open` drafting, `review` phrasing) and **enforced** by `export`/
  `status` preflight (commit-trailer scan for `Co-Authored-By: Claude` etc. before
  anything is pushed to origin).
- **Templates** - resolution order: the repo's committed
  `.github/PULL_REQUEST_TEMPLATE.md` wins; else the config entry's `template.md`;
  else a bare default. Templates seed `open`'s drafting only; `export` copies the
  refined description verbatim and never re-applies a template. A `{{ticket}}`
  placeholder fills from a `PROJ-1234`-style branch-name prefix when present.

## Conventions & assumptions

- **Repo doctrine binds**: tag every code fence; plans live in `doc/`; the release
  ritual is BBP per [CLAUDE.md](../CLAUDE.md) - bump
  `plugin/.claude-plugin/plugin.json` to the **next** version (never hard-code one);
  any verb/param change must update `MANIFEST_SKILLS` in [build.py](../build.py) in
  the same commit.
- **SKILL.md shape follows the suite**: YAML frontmatter with `name`, `description`
  ("init•config•open•review•status•export - ..."), `argument-hint: "[verb] [args]"`,
  `allowed-tools: Read, Write, Edit, Glob, Grep, Bash`, and a host-facing `verbs:`
  schema block mirroring the prose (the `plans` SKILL.md is the pattern to copy).
- **Forge adapter contract** (its own SKILL.md section): the four primitives are PRs,
  inline comments anchored path+line, a per-thread resolved flag, and a REST API.
  `backend: forgejo` is the only implemented adapter; `gitea` is documented as
  API-compatible with it. GitLab is explicitly future work, not scaffolding.
- **Assumes `gh` is installed and authenticated** for the origin; if not, `export`
  stops with the exact `gh auth login` instruction. Consequence if a repo's origin is
  a GitHub Enterprise host: `gh` supports `--hostname`, the tool passes it through
  from the origin URL - no design change.
- **Assumes brew is present** for `init` (macOS is the only current target;
  consequence if brew is absent: `init` stops and names the manual install, it does
  not script around it).
- **init runs once during this plan's execution** (`run-init`), on this machine -
  macOS/brew, localhost-only, nothing destructive; the user is present for its
  interactive steps (admin user, org names, token provisioning).
- **Compliance posture**: everything here is interactive and human-in-the-loop - a
  human triggers every verb, and `export` stages a pending review a human submits.
  No headless claude, no scheduling, no credential capture (the forge token is for
  the LOCAL forge only; `gh` owns GitHub auth).
- **One writer**: verbs run inline in the session (no delegation machinery in v1).

## The steps

### P1 - skeleton

**1. `scaffold-skill`** - Create `plugin/skills/repos/SKILL.md`.
Anchor: new file; copy the frontmatter shape from
[plugin/skills/plans/SKILL.md](../plugin/skills/plans/SKILL.md) (frontmatter keys and
the `verbs:` host-schema comment block). Content: frontmatter; an intro paragraph
stating the pipeline (local polish -> curated export); the invocation table (the six
verbs exactly as in Approach); shared sections: **Forge adapter contract**, **Config
root**, **Tokens**, **Stage directions**, **Templates** (content per Approach and
Conventions above); a **Help output** section (`/repos` bare prints the verb
cheat-sheet, same convention as the sibling skills — its header opens `/repos · v0.0.0`,
any version: build.py's STAMPS pass rewrites it on every build); an **Edge cases** stub
grown by later todos; a **What this skill does NOT do** section (no auto-submit on
GitHub, no review-thread history transfer, no GitLab adapter, no delegation).
Why: every later todo edits this file; land the shared context first.
DONE-WHEN: SKILL.md exists with all named sections; every fence tagged; the six-verb
table matches Approach byte-for-byte on verbs/params.

**2. `config-verb`** - Write the `## Verb: config` section.
Anchor: the invocation table's `config` row / a new `## Verb: config` heading.
Semantics (all decided): `kind` in `{template, directions, base}`; `origin` defaults
to the origin URL of the repo the session is standing in; `value` present = set
(template/directions: **import** the file at that path into the entry dir, the copy
canonical; base: store the branch name), `value` absent = **show** the currently
effective value, naming the source (committed repo template vs entry template vs
default); bare `/repos config` dumps the whole entry. Creating a missing entry on
first `config` or first `open` is allowed and identical. Positional disambiguation
(two optional args in sequence): `origin` is recognized by URL shape - it contains
`://` or starts with `git@`; anything else in that slot is the `value`. In the
manifest entry, `value` is kind `freeform` (its file-ness depends on `kind`).
DONE-WHEN: section covers set/show/dump, import semantics, entry auto-creation, the
URL-shape disambiguation rule, and an edge-case line for "run outside any git repo"
(ask for `origin` explicitly).

### P2 - forge up, then plumbing

**3. `init-verb`** - `/repos init`, interactive, idempotent.
Steps it prescribes: `brew install forgejo`; first-run config with
`HTTP_ADDR = 127.0.0.1` and SQLite (walk the web installer or write app.ini per the
Forgejo docs - state both, prefer the installer); `brew services start forgejo`;
create the admin user; create org namespaces (ask which - suggest `personal` +
`disney`); provision an API token scoped to repo+org and write it to
`~/.config/repos/forge_token` (0600); scaffold `~/.config/repos/manifest.json`.
Re-run = verify each step and repair, never reinstall. Every outward step is stated
to the user before it runs (it is the user's machine, but nothing here is
destructive).
DONE-WHEN: section is a complete runbook a fresh session can execute; idempotence
stated per step.

**4. `run-init`** - Execute `/repos init` on this machine, following the section
just written. This is both the install and the runbook's first real test: a fresh
read either works end-to-end or the section gets fixed on the spot. It touches the
machine (brew install, `brew services start forgejo`; nothing destructive), and it
is the ONE step that cannot run unattended - admin user creation, org names, and
token provisioning are interactive; the user must be at the keyboard.
Why: install-first - the spike and the api tool need a live forge, and the runbook
deserves a live exercise before it ships.
DONE-WHEN: Forgejo answers on 127.0.0.1, the provisioned token authenticates against
the API, and the init section required no further edits on a clean read-through.

**5. `spike-resolved-flag`** - SPIKE: probe the resolved flag on the live Forgejo.
What to try: against the live localhost forge that `run-init` just stood up, using
raw `curl` with the provisioned token (`repos_api.py` does not exist yet at spike
time): create a PR with an inline comment, resolve the conversation in the UI, then
`GET /api/v1/repos/{owner}/{repo}/pulls/{index}/reviews` + per-review comments and
inspect for a resolver/resolved field.
Branches: (a) field present -> record its exact name in the SKILL.md adapter section
and consume it in `forge threads`; (b) field absent from the API -> fall back to the
**reply-marker convention**: a thread counts as resolved when its latest reply body
begins with `[resolved]` (the skill posts that reply when Keldon says a finding is
handled, and `status` documents the convention); implement (b) in `forge threads`
behind the same output field so consumers never branch.
Why: the resolved flag is THE load-bearing claim of the whole design; probe it, don't
trust docs.
DONE-WHEN: the SKILL.md adapter section states which branch is in force with the
probe evidence (endpoint + field name, or its absence) cited.

**6. `api-tool`** - Build `plugin/skills/repos/tools/repos_api.py`.
Anchor: new file. Zero-dep python3 (urllib, json, subprocess for `gh`). Subcommands
(argparse, one per line, each printing JSON to stdout, exit 0/1):

```text
forge ensure-repo   --org O --name N            create if absent, return clone URL
forge pr            --repo R --branch B [--base BASE] [--title T --body-file F]
                                                 create-or-get PR for branch
forge threads       --repo R --pr N              reviews + inline comments, each with
                                                 path, line info, body, resolved flag
forge comment       --repo R --pr N --path P --line L --body-file F   post inline comment
github export       --repo R --branch B --base BASE --title T --body-file F
                     --comments-file J [--dry-run]
                                                 push is the CALLER's job; this creates
                                                 the PR + ONE pending review from the
                                                 comments JSON (path, line, side, body)
```

Config/token reading (`~/.config/repos/`) is built in; the forge base URL comes from
the manifest. The `github export` subcommand shells to `gh api` (never raw tokens).
The position->line mapping for forge comments lives here: prefer the API's file-line
fields; where only a diff position is returned, derive the line from the comment's
diff hunk (`@@` header arithmetic) - this is the known-fiddly part, keep it in one
function with a unit-style self-test runnable as `python3 repos_api.py selftest`.
The `resolved` output field of `forge threads` implements whichever branch the spike
recorded ((a) the API's field, or (b) the reply-marker convention) - the spike's
answer is already known when this todo runs.
Why: deterministic plumbing in one testable place; the SKILL.md orchestrates it.
DONE-WHEN: `selftest` passes (hunk-mapping cases: added line, context line,
multi-hunk); `forge threads` output shape documented in the SKILL.md.

### P3 - verbs (each is a `## Verb:` section in SKILL.md; all decisions below are final)

**7. `open-verb`** - `/repos open [branch] [base]`.
Defaults: `branch` = current branch; `base` = entry's `base`, else origin's default
branch. Steps: ensure entry (create on first use, asking which org); `forge
ensure-repo`; ensure `forge` git remote; push base from origin to forge (note drift:
"base moved N commits since you branched - consider rebasing"); push branch; draft
title/description from commits + diff through template resolution + directions
({{ticket}} from branch prefix); `forge pr` create-or-refresh; echo the forge PR
URL. Re-run refreshes (push + base re-sync), never duplicates.
DONE-WHEN: section covers bootstrap, drift note, template/directions consumption, and
idempotent re-run.

**8. `review-verb`** - `/repos review [pr]`.
`pr` defaults to the current branch's open forge PR. The session reviews the PR diff
itself (correctness + the directions' style law), then posts each finding as an
inline comment via `forge comment` - one comment per finding, root comments only,
phrased per directions, each ending with a one-line suggested action. No severity
theater; findings the session is unsure of say so. The section states plainly: chat
output is a summary; the forge comments are the durable artifact. (Wrapping the
built-in /code-review skill was considered and REJECTED for v1: its findings surface
is not a stable consumable contract; revisit only if that changes.)
DONE-WHEN: section defines finding format, posting mechanics, and the
default-pr resolution.

**9. `status-verb`** - `/repos status [pr]`.
Reports: open vs resolved thread counts (from `forge threads`); the export preview
(each unresolved root comment with file:line); base drift vs origin; preflight
warnings - AI-attribution trailers in the branch's commits (`git log
base..branch --format=%B` grepped for `Co-Authored-By:.*Claude|Generated with`), and
any directions violations it can check statically.
DONE-WHEN: section lists the exact checks and their commands.

**10. `export-verb`** - `/repos export {pr} [dryRun]`.
`pr` is REQUIRED (the one outward-facing verb - naming it is the guard). Steps:
preflight (trailer scan + directions check; any hit = STOP and surface, offer the
history-rewrite fix, never auto-rewrite); `dryRun` -> print branch, base, title,
description, and every surviving comment with anchors, touch nothing, end; live run
-> confirm with the user (outward action), `git push origin <branch>`, `github
export` (PR + ONE pending review holding the unresolved root comments), echo the
origin PR URL + "pending review staged - submit it in the GitHub UI". Resolved
threads transfer nothing; reply chains transfer nothing (root comments only, per the
design conversation).
DONE-WHEN: section covers preflight-stop, dryRun, confirm gate, pending-review
staging, and the "nothing resolved transfers" rule stated verbatim.

### P4 - ship

**11. `manifest-and-bbp`** - Wire into the suite and release.
Anchor: `MANIFEST_SKILLS` list in [build.py](../build.py): append a
`repos` entry - invocation `/repos [verb] [args]`, the six verbs with ORDERED params
and kinds (`kind` from the existing vocabulary: freeform/file/dir/flag; `pr` is
freeform, `dryRun` is flag, template/directions paths are file, config's `value` is
freeform). Also in build.py: append a `STAMPS` entry for
`plugin/skills/repos/SKILL.md` matching `/repos · v\d+\.\d+\.\d+` (the help header
scaffolded in step 1), and flip the two plans-skill manifest defaults
`_param("out", False, "dir", "./")` (review and verify entries) to `"plan-dir"` - the
ride-along for the SKILL.md `[out]`-default change already made in prose on
2026-08-31 and blocked from code by plan mode at the time. Run `python3
build.py`, then `python3 build.py --check` and `python3 test/test_modes.py` (both
must exit 0). Then BBP: bump `plugin/.claude-plugin/plugin.json` to the next
version, rebuild, `git add -A`, commit ("add /repos skill - local-forge PR
pipeline"), push to main.
DONE-WHEN: `--check` and the modes harness exit 0; the new manifest.json carries the
`repos` signatures; pushed.

## Out of scope

- **No GitLab adapter, no adapter plugin machinery** - the contract section names the
  seam; only Forgejo (Gitea-compatible) is implemented.
- **No delegation/subagent variants of any verb** - v1 is inline-only.
- **No transfer of reply threads, review history, or resolved anything** - root
  comments of unresolved threads only.
- **No auto-submit of the GitHub review, ever** - pending review is the ceiling.
- **No commit-history rewriting by the skill** - preflight detects and instructs;
  the user runs the rewrite.
- **No changes to the other skills** (`modes`, `plans`, `seedprompt`, `cleancode`)
  beyond the shared build/manifest files named in step 11.

## Verification

- `python3 build.py --check` and `python3 test/test_modes.py` exit 0 after step 11.
- `python3 plugin/skills/repos/tools/repos_api.py selftest` exits 0.
- `manifest.json` contains the `repos` skill with six verbs whose names and param
  order match the SKILL.md invocation table exactly.
- SKILL.md walkthrough: a fresh read of each verb section answers "what exactly do I
  run, in what order, and when do I stop and ask" with no open choices.
- End-to-end behavioral proof, live in THIS plan (the forge is up after `run-init`):
  open a PR on a scratch repo, post a comment, resolve it, post another, export with
  `dryRun` - the dry run must list exactly the one unresolved comment.

**Escape hatch:** if reality diverges from this plan (an API shape, a build.py
structure, a doctrine rule), STOP and surface it - don't improvise.
