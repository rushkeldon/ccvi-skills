---
name: repos evolve - attribution allowed, delete-to-resolve, prune, and export onto an existing PR
version: "1.0"
overview: "Update the /repos skill to Keldon's current thinking: stop blocking AI attribution, treat deleting a fixed comment as resolving it, add a prune verb that wipes the ephemeral forge, and let export attach a pending review to an existing origin PR."
todos:
  - id: drop-attribution-preflight
    content: "In plugin/skills/repos/SKILL.md, remove the AI-attribution trailer scan from status and export, and its mentions in Stage directions and What this skill does NOT do"
    status: completed
    phase: "1. SKILL.md changes"
  - id: delete-to-resolve
    content: "In SKILL.md, make deleting a fixed comment the way a finding is closed (the forge has no resolve API), and update review and status to say so"
    status: completed
    phase: "1. SKILL.md changes"
  - id: forge-delete-subcommand
    content: "Add `forge delete-comment --repo R --pr N --comment C` to plugin/skills/repos/tools/repos_api.py, with selftest coverage of URL building"
    status: completed
    phase: "2. tool changes"
  - id: prune-verb
    content: "Add the prune [dryRun] verb: list forge PRs and branches, delete exported ones any time and unexported ones only past 14 days or after a warning"
    status: completed
    phase: "2. tool changes"
  - id: export-existing-pr
    content: "Let github export attach the pending review to an existing origin PR (new --pr N flag) instead of creating one, with selftest coverage"
    status: completed
    phase: "2. tool changes"
  - id: schema-help-manifest
    content: "Update the repos verbs schema, invocation table, help output, and build.py MANIFEST_SKILLS in the same commit"
    status: completed
    phase: "3. release"
  - id: release-bbpi
    content: "Bump plugin/.claude-plugin/plugin.json to the next patch version and run this repo's BBPI release procedure, with build.py --check passing"
    status: completed
    phase: "3. release"
isProject: false
---

# repos evolve - attribution allowed, delete-to-resolve, prune, and export onto an existing PR

## Problem / Context

`/repos` polishes a PR privately on a local Forgejo forge, then exports it to
the origin. Keldon's thinking has moved on since he wrote it, and his dpp work
(`~/Desktop/working/dpp`, design in `doc/dpp_brainstorm.md`, section "Own PRs:
forge first, then Disney's GitHub" and the `/repos` TODO) now builds on it:

- **AI attribution is no longer blocked.** The trailer preflight in `status` and
  `export` now gets in the way.
- **Forgejo has no API to resolve a review thread** (probed on 16.0.3).
  Deleting a fixed comment is the simple fix: export only transfers unresolved
  threads, so a deleted thread drops out exactly as a resolved one would.
- **The forge is ephemeral.** Its only purpose is getting a PR into good shape
  before it goes to the origin, so it needs a periodic wipe.
- **dpp's review skill may hold a review of someone else's PR** for Keldon to
  look at. Export needs to attach a pending review to an existing origin PR,
  not only to one it creates.

## Approach

Edit `plugin/skills/repos/SKILL.md` and
`plugin/skills/repos/tools/repos_api.py`. Keep the existing patterns: tool
subcommands print JSON and exit 0 or 1, every pure function has `selftest`
coverage, and the SKILL.md prose stays authoritative over its `verbs:` schema.

## Conventions & assumptions

- Read this repo's `CLAUDE.md` first, especially "Versioning and releases" and
  "Consumer contracts". **Any verb or param change in a SKILL.md must update
  `MANIFEST_SKILLS` in `build.py` in the same commit**, and
  `python3 build.py --check` must pass before release.
- The existing DELETE endpoint for review comments is the one SKILL.md's
  `review` section already documents for amending:
  `DELETE /repos/{owner}/{repo}/pulls/{index}/reviews/{id}/comments/{comment}`.
- Style: 2-space indentation, Yoda naming, no em dashes, and the Oxford comma.
- **Escape hatch:** if the code doesn't match this plan, STOP and surface it.
  Don't improvise.

## The steps

### 1. SKILL.md changes

**`drop-attribution-preflight`** - in `plugin/skills/repos/SKILL.md`:
- remove the trailer-scan bullet from `## Verb: status` step 4 and from
  `## Verb: export` step 1
- in `## Stage directions`, drop the sentence saying export and status enforce
  a commit-trailer scan; stage directions stay as per-repo prose rules
- in `## What this skill does NOT do`, drop "No commit-history rewriting -
  preflight detects AI trailers and instructs"

`export` keeps its directions check for anything statically checkable. Done
when: `grep -n -i 'trailer\|Co-Authored-By' plugin/skills/repos/SKILL.md`
returns nothing.

**`delete-to-resolve`** - in `## Verb: review` and `## Verb: status`: a finding
is closed by **deleting its comment** once the fix is verified, using
`forge delete-comment`. Resolving in the web UI still works and counts the
same. In `## Forge adapter contract`, note that deletion is the supported way
to close a thread, because the API has no resolve endpoint. Done when: the
review section tells the agent to delete verified-fixed comments, and the
status section counts open threads the same either way.

### 2. Tool changes

**`forge-delete-subcommand`** - in `repos_api.py`, `forge delete-comment --repo R
--pr N --comment C`: find the comment's review ID from `forge threads` data,
then DELETE it. Output: `{deleted: true, comment_id}`. Done when: `selftest`
covers the URL building, and on a spike PR on the local forge, a deleted
comment no longer appears in `forge threads`.

**`prune-verb`** - new verb `/repos prune [dryRun]` and tool subcommand
`forge prune [--dry-run]`:
- list every forge repo's PRs and branches
- **exported PRs** (the origin has a PR for the branch, checked with `gh` using
  the origin's host) are deleted with their branches at any time
- **unexported PRs** are deleted only if older than 14 days; otherwise they're
  listed with a warning and kept
- the base branch is never deleted

`dryRun` prints what it would do and changes nothing. Done when: `dryRun` lists
the right items on a forge with one exported and one fresh unexported PR, and a
live run deletes only the exported one.

**`export-existing-pr`** - `github export` gains `--pr N`: when given, skip
creating the origin PR and attach the single pending review to PR `N`, still
replaying comments by `head_line`. The `/repos export` verb documents the new
optional param. Done when: `selftest` covers building the review payload for an
existing PR, and `--dry-run` with `--pr` prints the target PR instead of a
create.

### 3. Release

**`schema-help-manifest`** - update `## Invocation`, the `verbs:` frontmatter
schema (add `prune: { params: [dryRun] }`, and `pr` on `export`), `## Help
output`, and `MANIFEST_SKILLS` in `build.py`, all in the same commit. Done when:
`python3 build.py --check` passes.

**`release-bbpi`** - bump `plugin/.claude-plugin/plugin.json` to the next patch
version and run this repo's BBPI procedure per `CLAUDE.md`. Done when:
`python3 build.py --check` exits 0 and the built zip carries the new version.

## Out of scope

- Other skills (`modes`, `plans`, `seedprompt`, `cleancode`).
- A GitLab adapter.
- Auto-submitting reviews on the origin: a pending review is still the ceiling.
- Any change to ccvi-idea's extraction of this repo's zip (a consumer contract).

## Verification

- No trailer scan remains in `/repos`.
- Deleting a fixed comment removes it from `status` and from `export`'s payload.
- `/repos prune dryRun` lists the right items, and a live run deletes only
  exported PRs and their branches.
- `/repos export {pr} ... pr` attaches to an existing PR.
- `python3 build.py --check` passes on the released version.

## Build notes (2026-10-29)

- **Unverified live checks.** Two done-when checks need a running forge and
  throwaway spike repos, and were NOT run: `forge-delete-subcommand` (a deleted
  comment disappears from `forge threads` on a spike PR) and `prune-verb` (a live
  run on the real forge deletes only the exported PR). The local forge was down,
  and its only repo is a Disney one. What did run: `selftest` (60 cases, including
  URL building, prune classification on a fixed clock, and the export payload),
  plus `forge prune` dry-run and live against a mock forge with a fake `gh`. The
  dry run deleted nothing. The live run deleted exactly the exported PR and the
  14+ day stale PR, with their branches, and kept the fresh PR and `main`.
- **Unprobed endpoint.** Prune deletes a forge PR through `DELETE
  /repos/{owner}/{repo}/issues/{index}` (Gitea's issue delete; the forgejo 16.0.3
  binary carries `DeleteIssue`). The live run above is what would confirm it.
- **Param name.** The new export param is `originPr`, not `pr`, because `pr`
  already names the required forge PR. The tool flag is `github export --pr N`.
  dpp-aa approved this.
- **Dry-run shape change.** `github export --dry-run` now prints
  `target.create_pr` or `target.existing_pr` in place of the old top-level `pr`
  key.
