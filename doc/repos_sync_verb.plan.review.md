---
plan: "repos_sync_verb.plan.md"
model: "claude-fable-5"
---
# Review: repos: add a sync verb so the forge never lags the origin

**Overall: one real gap, otherwise ready** - the design is well-fenced and every anchor
checks out against the live SKILL.md, but the plan misses a fifth registration surface
(`build.py`'s `MANIFEST_SKILLS`) that the repo's consumer contract requires in the same
commit, and the safety net the plan leans on (`build.py --check`) verifiably does NOT
catch that omission.

| Dimension | Grade | Notes |
|---|---|---|
| Execution-readiness | ✅ | No open questions; every decision resolved; force semantics fully specified |
| Stale assumptions | ⚠️ | The `--check`-catches-partial-registration claim is overclaimed (see findings) |
| Cross-surface risk | ⚠️ | `manifest.json` (a ccvi-idea consumer contract) silently drifts if MANIFEST_SKILLS is untouched |
| Rails present | ✅ | Stable anchors, done-whens, why lines, out-of-scope fence, escape hatch all present |
| TODO hygiene | ✅ | Atomic, ordered, unique ids, phase keys consistent |
| Mechanical lint | ✅ | `plan-check OK - 7 todos`; scalars quoted; no hard-coded release number in steps (the 0.0.12 assumption is properly hedged) |

## Findings

**version-and-build** `[stale]` - The plan's "Files that change" bullet and this step's
rationale omit `build.py`. The repo's CLAUDE.md consumer contract is explicit: manifest.json
is "the machine-readable signatures contract" ccvi-idea consumes, `MANIFEST_SKILLS` in
build.py is its canonical source, and "any verb or param change in a SKILL.md must update it
in the same commit". build.py already carries a `repos` entry (verbs init through export,
build.py `MANIFEST_SKILLS`, ~line 186); adding `sync` to SKILL.md without adding it there
ships a manifest that hides the new verb from the host's verb menu - the exact invisibility
step 2's why-line exists to prevent. Worse, the tripwire the plan relies on does not fire:
`manifest_drift()` (build.py, ~line 358) checks only that every MANIFEST verb appears in the
prose - manifest → prose. A new verb present in prose but absent from MANIFEST_SKILLS passes
`--check` clean. Step 7's claim that `--check` "catches a partial registration from steps
2-4" is therefore true for the four SKILL.md surfaces' verb-name spelling at best, and false
for the manifest surface entirely.
Action: add a new todo (e.g. id `manifest-skills`, phase "Skill prose", ordered before
`version-and-build`) - "Add the sync verb to the repos entry of MANIFEST_SKILLS in build.py:
`{\"name\": \"sync\", \"params\": [_param(\"force\", False, \"flag\")]}` between config and
open" - and correct the "Files that change" bullet to include `build.py`, and soften step
7's why-line so it no longer claims `--check` catches a missing manifest entry.

**cross-references** `[hygiene-issue]` - Minor: the status anchor is named as "numbered item
**3. Base drift**"; in the live SKILL.md the item reads `3. **Base drift:**` (bold on the
words, not the number). The unique string to anchor on is `**Base drift:**`. Harmless for a
careful implementer, but the plan's own standard is exact surfaces.
Action: reword the anchor to the literal `**Base drift:**` string.

Clean roll-up: **sync-verb-section**, **verbs-frontmatter**, **invocation-table**,
**help-output**, **readme-verb-list** - `[ready]`. All anchors verified against the live
file (`## Verb: config` / `## Verb: open` boundary, the `| `/repos config {kind}`` table
row, the `• config {kind} [origin] [value]` help bullet, the `**Idempotent re-run:**` note,
and README's `| repos | ` row with its `<li>` list between `config` and `open`). The
current `verbs:` block is exactly init 1 through export 6 as the plan states, and
plugin.json is at 0.0.12 as assumed.
