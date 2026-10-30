---
name: repos
description: init•config•sync•open•review•status•export•prune - iterate a PR to polish on a LOCAL forge (Forgejo), then export the refined result - branch, description, and only the unresolved review comments - to the origin (GitHub) as a pending review, via /repos [verb]. Use when the user issues a /repos directive or asks to open, review, or export a PR through the local forge.
argument-hint: "[verb] [args]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
# Machine-readable verb schema (host-facing). The prose below remains authoritative
# for the model; this block MIRRORS it for a host that renders a verb menu and
# generates each verb's dialog from `params`. Every fact here MUST also be stated in
# the prose - the skill stays fully usable in vanilla Claude Code.
verbs:
  init:    { order: 1, params: [] }
  config:  { order: 2, params: [ { name: kind,   type: string, required: true },
                                 { name: origin, type: string, required: false },
                                 { name: value,  type: string, required: false } ] }
  sync:    { order: 3, params: [ { name: force,  type: boolean, required: false } ] }
  open:    { order: 4, params: [ { name: branch, type: string, required: false },
                                 { name: base,   type: string, required: false } ] }
  review:  { order: 5, params: [ { name: pr, type: string, required: false } ] }
  status:  { order: 6, params: [ { name: pr, type: string, required: false } ] }
  export:  { order: 7, params: [ { name: pr,       type: string, required: true },
                                 { name: dryRun,   type: boolean, required: false },
                                 { name: originPr, type: string, required: false } ] }
  prune:   { order: 8, params: [ { name: dryRun, type: boolean, required: false } ] }
---

# repos

A local-forge PR pipeline: iterate a PR to a polished state **privately, on a local
forge** - open it there, review it as durable inline comments, fix and resolve threads -
then **export the refined result** to the real origin (GitHub / GitHub Enterprise): the
branch, the PR description verbatim, and **only the root comments of threads still
unresolved** at export time. Resolved threads transfer nothing (their result is already
in the code). The export lands as a **pending review** a human submits - the skill
stages, never publishes.

One entry point - **`/repos [verb] [args]`** - dispatching on the first arg.

## Invocation

| Form | Effect |
|---|---|
| `/repos init` | One-time: install + configure the local forge (idempotent re-run = verify & repair) |
| `/repos config {kind} [origin] [value]` | Per-repo config: `template` \| `directions` \| `base` |
| `/repos sync [force]` | Push the base and current branch to the forge - no drafting, no PR |
| `/repos open [branch] [base]` | Push branch to the forge, open/refresh the local PR |
| `/repos review [pr]` | Claude review of the forge PR → inline forge comments |
| `/repos status [pr]` | Threads, export preview, preflight warnings |
| `/repos export {pr} [dryRun] [originPr]` | Transfer to origin as a pending review (onto an existing origin PR with `originPr`) |
| `/repos prune [dryRun]` | Wipe the ephemeral forge: exported PRs + branches, and unexported ones past 14 days |
| `/repos` (blank/unknown verb) | Print the help cheat-sheet (see **Help output**) |

## Forge adapter contract

The skill is written against a **forge adapter contract**, not a vendor. The four
primitives every backend must provide:

1. **Pull requests** - create-or-get by branch, against a base.
2. **Inline comments** anchored to `path` + line.
3. **A per-thread resolved flag** - the load-bearing primitive: export transfers only
   unresolved root comments.
4. **A REST API** for all of the above.

`backend: forgejo` is the only implemented adapter. **Gitea is API-compatible** with it
(the two share a GitHub-shaped API) and is documented as covered by the same adapter.
GitLab is explicitly future work - a seam, not scaffolding.

**Resolved flag - probe evidence (branch (a) in force).** Probed 2026-08-31 against a
live Forgejo 16.0.3 (localhost, spike PR with an inline review comment, resolved in
the UI):

- **Read:** `GET /api/v1/repos/{owner}/{repo}/pulls/{index}/reviews/{id}/comments` -
  each comment carries a **`resolver`** field: `null` while the thread is unresolved;
  the resolving **user object** (`login`, `id`, ...) once resolved. `forge threads`
  emits `resolved: resolver != null`.
- **Write:** there is NO API endpoint to resolve a conversation - the instance's own
  `/swagger.v1.json` contains zero `resolve` paths (verified). Resolution happens in
  the Forgejo web UI ("Resolve conversation" on the PR). The reply-marker fallback
  (branch (b)) is NOT in force and is not implemented.
- **Closing a thread = deleting its comment.** Because the API cannot resolve, the
  supported way for the agent to close a finding is to **delete the comment**
  (`forge delete-comment`) once the fix is verified. Export transfers only unresolved
  threads, so a deleted thread drops out exactly as a resolved one would. Resolving
  in the web UI still works and counts the same.

## Config root

`~/.config/repos/` holds all per-repo configuration:

- **`manifest.json`** maps **origin URL → entry dir**; each entry holds `template.md`,
  `directions.md`, and settings (`base` branch, forge org). Keyed by origin URL so a
  re-clone still matches.
- Config files are **imported** - copied into the entry dir, the copy canonical -
  never referenced at their source path.
- The forge base URL lives in the manifest (written by `init`).

## Tokens

- **GitHub side:** the already-authenticated `gh` CLI owns origin auth - the skill
  never touches a GitHub token.
- **Forge side:** the Forgejo API token lives at `~/.config/repos/forge_token`
  (mode 0600), written by `init`, read by the bundled tool.
- Tokens never enter any repo and never appear in the skill or its output.

## Stage directions

Per-repo standing instructions (e.g. "keep PR descriptions under 200 words") stored
as the entry's `directions.md`. Consumed by every verb that writes prose (`open`
drafting, `review` phrasing), and checked by `status` and `export` wherever a
direction can be checked statically against the PR title, description, and comments.

## Templates

Resolution order for PR description drafting:

1. The repo's committed `.github/PULL_REQUEST_TEMPLATE.md` wins;
2. else the config entry's `template.md`;
3. else a bare default.

Templates seed `open`'s drafting only; `export` copies the refined description
**verbatim** and never re-applies a template. A `{{ticket}}` placeholder fills from a
`PROJ-1234`-style branch-name prefix when present.

## The bundled tool

Deterministic API plumbing lives in `tools/repos_api.py` (zero-dependency python3;
resolve it against this skill's base dir). Run `python3 tools/repos_api.py selftest`
to sanity-check it. Subcommands print JSON to stdout, exit 0/1:

```text
forge ensure-repo --org O --name N              create if absent -> {full_name, clone_url}
forge pr          --repo R --branch B [--base BASE] [--title T --body-file F]
                                                create-or-get -> {number, url, existing}
forge threads     --repo R --pr N               all inline comments -> see shape below
forge comment     --repo R --pr N --path P --line L --body-file F
forge delete-comment --repo R --pr N --comment C
                                                finds the comment's review, DELETEs it
                                                -> {deleted: true, comment_id}
forge prune       [--dry-run]                   classify + delete forge PRs and branches
                                                (see Verb: prune); exit 1 if any delete
                                                failed
forge check-git-credentials [--remote NAME]     helper + keychain + ls-remote probe
                                                -> {ok, next_action}; exit 0 iff ok
github export     --repo R --branch B --base BASE --title T --body-file F
                  --comments-file J [--dry-run]  push is the CALLER's job; creates the
                                                origin PR + ONE pending review;
                                                replays comments by head_line (required);
                                                gh runs with GH_HOST derived from the
                                                origin remote (a preset GH_HOST wins)
github export     --repo R --pr N --comments-file J [--dry-run]
                                                attach ONE pending review to existing
                                                origin PR N; creates no PR, so branch,
                                                base, title, and body are not needed;
                                                --dry-run prints target.existing_pr
                                                instead of target.create_pr
```

**`forge threads` output shape** (the export pipeline's input):

```json
{"pr": 1,
 "threads": [{"review_id": 1, "comment_id": 2, "path": "spike.txt", "line": 2,
              "head_line": 2, "outdated": false,
              "body": "...", "resolved": true, "author": "rushkeldon",
              "created_at": "..."}],
 "unresolved": 0, "resolved": 1}
```

`line` is the new-file line **as of the comment's own anchor commit**
(`commit_id`), derived from the frozen `diff_hunk` by `@@`-header arithmetic
(`comment_line`/`line_from_hunk`, covered by `selftest`) - still the right value
for the DELETE + repost amend path, but NOT the current line once later commits
shift the file. `head_line` is that line re-anchored to the current PR head via
local `git diff` (`remap_line`, also selftest-covered); it is `null` when
`outdated: true`, meaning the anchored code was itself rewritten. Export
consumers keep unresolved entries and replay by `head_line`, never `line`.
The API's `position` is only a stand-in when the hunk is unparseable: its
meaning varies by provenance (probed v16.0.3 - a diff offset for UI-created
comments, but API-written comments echo `new_position` back as a true file
line), so the hunk arithmetic stays authoritative.
`resolved` is `resolver != null` per the probe above. Export consumers keep only
`threads[]` entries with `resolved == false`.

## Verb: init

**`/repos init`** - one-time forge installation and configuration. Interactive and
**idempotent**: a re-run verifies each step and repairs what's missing - it never
reinstalls over a working step. Every outward step is stated to the user before it
runs; nothing here is destructive.

**The runbook, in order** (each step: do → verify; on re-run: verify → repair only if
the check fails):

1. **Install:** `brew install forgejo`. Requires brew (macOS is the only target); if
   brew is absent, STOP and name the manual install
   (https://forgejo.org/download/) - do not script around it.
   *Verify:* `forgejo --version` prints a version.
2. **First-run config - localhost-only + SQLite.** Two routes, prefer the installer:
   - **Installer (preferred):** `brew services start forgejo`, open
     `http://127.0.0.1:3000`, and walk the web installer: database `SQLite3`; set
     "HTTP Listen Address" to `127.0.0.1`; leave everything else default.
   - **app.ini (fallback, headless):** before first start, write
     `<work-path>/custom/conf/app.ini` - the work path is the one `brew info
     forgejo` prints after `--work-path`, e.g. `/opt/homebrew/var/forgejo` - with
     `[server] HTTP_ADDR = 127.0.0.1` and `[database] DB_TYPE = sqlite3`, then
     `brew services start forgejo`. (Probed 2026-08-31 on forgejo 16.0.3: brew
     manages no `etc/forgejo/`; the work-path `custom/conf/` location is the one the
     server actually reads. Best of both: seed this app.ini BEFORE first start so the
     bind is loopback from the first boot, then finish setup in the web installer -
     the installer respects pre-seeded values.)
   *Verify:* `curl -s http://127.0.0.1:3000/api/v1/version` answers, and the listen
   address is loopback (`lsof -iTCP:3000 -sTCP:LISTEN` shows `127.0.0.1`).
3. **Service:** `brew services start forgejo` (a no-op if already running).
   *Verify:* `brew services list` shows forgejo `started`.
4. **Admin user - the USER's step, in the USER's browser.** This account is a
   **local identity on the user's own forge instance** - unrelated to any GitHub
   or enterprise account - and its username is the username half of the git
   credential seeded in step 7. Bring the user to the installer
   (`http://127.0.0.1:3000`, "Administrator account settings" at the bottom); the
   user fills the form and submits. **Credentials never transit the agent**: no
   passwords in chat, in CLI args, or in a form the agent fills - the skill
   states what is needed, then waits. (The installer calls this section
   "optional" - first registered user becomes admin - but that path assumes
   self-registration; with self-registration DISABLED, as this runbook configures,
   nobody can register, so create the admin here. The escape hatch if skipped:
   `forgejo admin user create --admin ...`, run by the user.)
   *Verify:* checkable right now, no token needed - the installer redirects to a
   logged-in session at `http://127.0.0.1:3000`, or the user runs
   `forgejo admin user list` and sees the account.
5. **Org namespaces:** ask which orgs to create - suggest `personal` + `disney` -
   and create each (UI, or `POST /api/v1/orgs` once the token exists). Orgs give
   per-origin separation inside the single instance, and the org name is what
   first `/repos open` asks for when it files a repo under the forge - choosing
   now avoids that prompt later.
   *Verify:* while logged in, `http://127.0.0.1:3000/<org>` loads for each org
   (or `GET /api/v1/orgs/{org}` once the step-6 token exists).
6. **API token - the USER's step, same rule as step 4.** This token authorizes
   the **REST calls made by the bundled tool** (creating repos, PRs, comments);
   it is **not** what git uses when it pushes - that is a separate credential,
   which is why step 7 exists. In the user's browser:
   Settings → Applications → **New access token** (the top section - NOT "Create a
   new OAuth2 application", which is a different mechanism). Name it, leave access
   "All", set exactly three permission dropdowns - **repository: Read and Write**,
   **organization: Read and Write**, **user: Read** - the rest No access; Generate.
   The value shows ONCE; the user saves it themselves:
   `mkdir -p ~/.config/repos && printf '%s' '<token>' > ~/.config/repos/forge_token && chmod 600 ~/.config/repos/forge_token`.
   *Verify:* `curl -s -H "Authorization: token $(cat ~/.config/repos/forge_token)"
   http://127.0.0.1:3000/api/v1/user` returns the admin user.
7. **Git credentials for the forge remote - the USER's step.** The API token from
   step 6 authenticates REST calls; **git does not use it**. Without a git
   credential the first `/repos open` fails at its push with
   `could not read Username`. Present the choice below, have the user pick and
   seed; credentials never transit the agent.

   **Ask, don't prescribe.** Lay out the problem space in prose first, then
   collect the answer with the AskUserQuestion tool - neither mechanism is right
   for everyone:

   - **HTTPS plus a credential helper (recommend this).** The credential is the
     forge username with an access token as the password. A helper may already be
     active and inherited from a config file the user never wrote (on macOS,
     Xcode's gitconfig ships `osxkeychain` machine-wide) - run
     `python3 tools/repos_api.py forge check-git-credentials` to see the effective
     helper AND the config file it came from. The forge is plain `http` on
     loopback: the exchange is unencrypted but never leaves the machine.
     Recommended because on a machine with a working helper it needs no
     configuration change at all.
   - **SSH.** Keeps tokens out of git entirely and matches how many people
     already reach an enterprise host - at the cost of a forge *server* change:
     enable the SSH listener in the work-path `app.ini`, register a public key on
     the forge account, and re-point the `forge` remote at the SSH URL.

   **Seeding, HTTPS route** (the user runs it, either way): one interactive
   `git push forge <branch>` - git prompts, the user enters the forge username
   and an access token as the password, the helper stores it and later pushes are
   silent - or a printed one-liner the user runs with their own token
   substituted:
   `printf 'protocol=http\nhost=127.0.0.1:3000\nusername=<forge-user>\npassword=<token>\n' | git credential approve`.
   *Verify:* `python3 tools/repos_api.py forge check-git-credentials` exits 0.
8. **Config root:** scaffold `~/.config/repos/manifest.json` if absent:
   `{ "forge_url": "http://127.0.0.1:3000", "repos": {} }`.
   *Verify:* the file parses as JSON and names `forge_url`.

## Verb: config

**`/repos config {kind} [origin] [value]`** - read or write one facet of a repo's
config entry. `kind` ∈ `{template, directions, base}`.

**Argument semantics:**

- **`origin`** defaults to the origin URL of the repo the session is standing in.
  **Disambiguation rule** (two optional positionals in sequence): `origin` is
  recognized by URL shape - it contains `://` or starts with `git@`; anything else in
  that slot is the `value`.
- **`value` present = set.**
  - `template` / `directions`: **import** the file at that path into the entry dir
    (`template.md` / `directions.md`) - the copy is canonical; the source path is
    never referenced again.
  - `base`: store the branch name.
- **`value` absent = show** the currently effective value, naming its source
  (committed repo template vs entry template vs bare default; entry base vs origin
  default branch).
- **Bare `/repos config`** dumps the whole entry for the current repo.

**Entry auto-creation:** a missing entry is created on first `config` or first `open`,
identically (manifest row + entry dir; the forge org is asked for on first `open`).

**Edge case:** run outside any git repo → no origin to default to; ask for `origin`
explicitly.

## Verb: sync

**`/repos sync [force]`** - bring the forge current with the origin. Pushes the base
branch and the current branch to the forge and stops: no drafting, no PR call. Cheap,
deterministic, and safe to run as often as you like.

**Steps, in order:**

1. **Preflight credentials:** `python3 tools/repos_api.py forge
   check-git-credentials`. Non-zero exit → STOP and surface its `next_action`; push
   nothing.
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

**Edge cases:**

- **Base and branch identical** → nothing to do for step 4; the base push covered it.
- **Branch not yet on the forge** → a normal push creates it; no force needed.
- **The lease fails under `--force-with-lease`** → someone else pushed to the forge
  branch; STOP and surface - do not retry with bare `--force`.

## Verb: open

**`/repos open [branch] [base]`** - push the branch to the forge and open (or
refresh) the local PR. Defaults: `branch` = the current branch; `base` = the entry's
`base`, else the origin's default branch.

**Steps, in order:**

0. **Preflight credentials:** `python3 tools/repos_api.py forge
   check-git-credentials`. On a non-zero exit, STOP and surface its
   `next_action` - do not create the forge repo, do not touch the remote set, do
   not attempt a push. Point the user at `/repos init` step 7. (Failing here
   costs nothing; failing at step 4's push leaves a half-built forge repo and a
   mutated remote set behind.)
1. **Ensure the config entry** (create on first use - ask which forge org this repo
   belongs under).
2. **Ensure the forge counterpart:** `forge ensure-repo --org <org> --name <repo>`.
3. **Ensure the `forge` git remote** points at the counterpart's clone URL (add or
   fix; never touch `origin`).
4. **Sync the base:** fetch `base` from origin, push it to the forge
   (`git push forge origin/<base>:refs/heads/<base>`). If the base has moved since
   the branch diverged, note the drift: "base moved N commits since you branched -
   consider rebasing."
5. **Push the branch:** `git push forge <branch>`.
6. **Draft title + description** from the branch's commits and diff, through the
   template resolution order (committed template > entry template > bare default)
   and the entry's stage directions. Fill `{{ticket}}` from a `PROJ-1234`-style
   branch-name prefix when present.
7. **Create-or-refresh the PR:** `forge pr --repo <org>/<repo> --branch <branch>
   --base <base> --title ... --body-file ...` (create-or-get; a re-run never
   duplicates). Echo the forge PR URL.

**Idempotent re-run:** pushes again, re-syncs the base, refreshes the drift note;
the existing PR is reused. When only a refresh is wanted, `/repos sync` does steps 4
and 5 alone - no drafting, and the PR is untouched.

## Verb: review

**`/repos review [pr]`** - review the forge PR and post findings as durable inline
comments. `pr` defaults to the current branch's open forge PR.

- The session reviews the PR diff itself - correctness plus the entry's stage
  directions (the style law) - reading the code as needed for context.
- **Each finding = one root inline comment** via `forge comment --repo R --pr N
  --path P --line L --body-file F`: what's wrong, why it matters, and a one-line
  suggested action at the end. Phrased per the stage directions.
- **Posted comments cannot be edited** - the forge API has no PATCH for review
  comments (regardless of token scope; probed v16.0.3). To amend one: DELETE
  `/repos/{owner}/{repo}/pulls/{index}/reviews/{id}/comments/{comment}` (works
  with the provisioned scopes), then repost via `forge comment`. The comment id
  changes; the thread's resolved state starts over.
- **Close fixed findings by deleting them.** On a re-review, for each open thread
  whose fix you have verified in the current code, delete its comment with `forge
  delete-comment --repo R --pr N --comment C` (the forge API has no resolve
  endpoint; see the Forge adapter contract). Leave unverified fixes open. A thread
  the user resolved in the web UI is already closed - leave it alone.
- No severity theater. A finding the session is unsure of says so plainly.
- **Chat output is a summary; the forge comments are the durable artifact.**
- (Wrapping the built-in /code-review skill was considered and REJECTED for v1: its
  findings surface is not a stable consumable contract; revisit only if that
  changes.)

## Verb: status

**`/repos status [pr]`** - the dashboard. `pr` defaults like `review`. Reports:

1. **Thread counts:** open vs resolved, from `forge threads --repo R --pr N`. A
   thread closed by deleting its comment no longer appears at all, so it counts
   exactly like one resolved in the web UI: it is not open and does not export.
2. **Export preview:** each unresolved root comment as `path:head_line - body`
   (exactly what `export` would replay). An `outdated: true` thread renders as
   `path - body [OUTDATED - will be excluded from export]`; the summary counts
   replayable vs outdated.
3. **Base drift:** `git fetch origin <base>` then
   `git rev-list --count <branch>..origin/<base>` - commits the base has gained.
   Drifted? `/repos sync` brings the forge's copy of the base current.
4. **Preflight warnings:** any stage-directions violations checkable statically
   (scan the PR title, description, and comment drafts against the directions).

## Verb: export

**`/repos export {pr} [dryRun] [originPr]`** - the one outward-facing verb; `pr` (the
FORGE PR) is REQUIRED (naming it is the guard). Transfers the polished result to the
origin as a PENDING review.

**`originPr`** names an EXISTING origin PR - typically someone else's PR whose review
was polished on the forge. With it, export creates no PR and pushes nothing: it
attaches the single pending review to PR `originPr` (`github export --pr
<originPr>`), still replaying comments by `head_line`. The existing PR keeps its own
title and description; the forge PR's are not transferred.

**Steps, in order:**

1. **Preflight:** the directions check from `status`. **Any hit = STOP and
   surface**; the user fixes the title, description, or comment on the forge, then
   re-invokes export.
2. **Collect the payload:** `forge threads`, keep `resolved == false` entries only,
   root comments only; the forge PR's title + description **verbatim** (no template
   re-application). Comments-JSON entries carry the thread fields as `forge
   threads` emitted them - `github export` replays each at its **`head_line`**
   (the head-anchored line - never the as-of-comment `line`) and **refuses** an
   entry with no `head_line`, no silent fallback. Any entry with
   `outdated: true` is **excluded** from the JSON, with a warning printed per
   exclusion naming its `path` and the first line of its `body` - the user
   resolves or rewords those comments on the forge first. (`github export` also
   refuses a comments file carrying `outdated` entries - belt and braces.)
3. **`dryRun`:** print the target - the PR to create (branch, base, title,
   description) or, with `originPr`, the existing PR number - and every surviving
   comment with its `path:line` anchor, via `github export ... --dry-run`; touch
   nothing, end.
4. **Live run:** confirm with the user (outward action), then:
   - **With `originPr`:** skip the push and run `github export --repo
     <owner>/<repo> --pr <originPr> --comments-file ...` - ONE pending review on that
     PR. Echo its URL + "pending review staged - submit it in the GitHub UI". Done.
   - `git push origin <branch>`
   - `github export --repo <owner>/<repo> --branch <branch> --base <base> --title
     ... --body-file ... --comments-file ...` - creates the origin PR and ONE
     pending review holding the unresolved root comments.
   - Echo the origin PR URL + "pending review staged - submit it in the GitHub UI".

**Nothing resolved transfers.** Resolved threads transfer nothing; reply chains
transfer nothing - root comments of unresolved threads only.

## Verb: prune

**`/repos prune [dryRun]`** - wipe the ephemeral forge. The forge exists only to get
a PR into shape before it goes to the origin, so finished and abandoned work is
cleared periodically. Run `python3 tools/repos_api.py forge prune [--dry-run]` and
relay its report.

**What it does, per forge repo** (every repo the forge token can see):

- **Matching the origin:** a forge repo maps to the manifest origin whose repo
  basename equals the forge repo's name (`open` names the forge repo after the
  origin's basename). An unmatched forge repo is reported as such
  (`origin_check`), and all its branches are treated as unexported.
- **Items** are the repo's branches plus the head branches of its PRs (open or
  closed); each item carries its forge PR numbers.
- **The base branch is never deleted** - the forge repo's default branch and the
  manifest entry's `base`.
- **Exported** = the origin has a PR (any state) for that branch, checked with `gh
  api` against the origin's own host (`GH_HOST` from the origin URL). Exported items
  are deleted - PRs and branch - at any time.
- **Unexported** items are deleted only once **stale: 14 days or more** since the
  newest of the branch head commit and its PRs' `updated_at`. Fresher ones are kept
  and listed with a warning. A failed origin check counts as unexported (reported in
  `origin_check`); an item with no timestamp at all is kept.
- **Deleting** a PR uses the issue DELETE endpoint (`DELETE
  /repos/{owner}/{repo}/issues/{index}`; a PR is an issue), then the branch is
  deleted. A failed delete is reported per item and the run continues; the tool
  exits 1 if any failed.

**`dryRun`** prints the same classification (`would_delete`, `kept`) and changes
nothing. Prune deletes local forge data only - never anything on the origin - so a
live run needs no outward-action confirmation, but a first prune on a forge is
best previewed with `dryRun`.

## Help output

When the user runs `/repos` with a blank or unrecognized verb (or asks "what can
/repos do?"), reply with exactly this - no preamble, no postscript:

```text
/repos · v0.0.26 — local-forge PR pipeline:
• init                              — one-time: install + configure the local forge
• config {kind} [origin] [value]    — per-repo config: template | directions | base
• sync [force]                      — push base + current branch to the forge; no PR
• open [branch] [base]              — push branch to forge, open/refresh local PR
• review [pr]                       — Claude review -> inline forge comments
• status [pr]                       — threads, export preview, preflight warnings
• export {pr} [dryRun] [originPr]   — transfer to origin as a pending review
• prune [dryRun]                    — wipe exported + stale (14d+) forge PRs and branches

Polish locally, export deliberately: only unresolved root comments transfer,
as a PENDING GitHub review a human submits.
```

## Edge cases

- **Unknown/blank verb** → print the **Help output**. Don't guess at a verb.

## What this skill does NOT do

- **No auto-submit of the GitHub review, ever** - a pending review is the ceiling; a
  human submits it in the GitHub UI.
- **No transfer of reply threads, review history, or resolved anything** - root
  comments of unresolved threads only.
- **No GitLab adapter** - Forgejo (Gitea-compatible) is the only backend.
- **No delegation** - every verb runs inline in the session.
