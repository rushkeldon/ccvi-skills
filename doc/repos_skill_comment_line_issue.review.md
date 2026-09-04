---
plan: "repos_skill_comment_line_issue.md"
model: "claude-fable-5"
---
# Review: /repos inline comment line numbers are as-of-comment, not as-of-head

**Overall: strong content, wrong container** - the analysis is probed, correct, and nearly
implementation-ready, but the file is a bug-report doc, not a `*.plan.md`: no frontmatter, no
todos, so it cannot ride the plans lifecycle (`build` has nothing to flip; `update` has no ids
to join on). One real algorithm bug (pure-insertion off-by-one) and two scope gaps found.

| Dimension | Grade | Notes |
|---|---|---|
| Execution-readiness | ⚠️ | Algorithm + edge cases spelled out; one layer ambiguity (which code assembles `head_line` for export) |
| Stale assumptions | ✅ | All code refs verified live: `comment_line`/`line_from_hunk` (repos_api.py:240,270), `forge_threads` line field (repos_api.py:121-131), export replay of `c["line"]` (repos_api.py:306), skill-text claim (SKILL.md:146) |
| Cross-surface risk | ✅ | Additive fields, `line` kept as-is; consumer contract unbroken (no verb/param change, so `manifest.json` untouched) |
| Rails present | ✅ | Behavioral done-when tied to the repro PR; "Not covered here" acts as the out-of-scope fence |
| TODO hygiene | ❌ | No todos at all - the doc is not in plan format |
| Mechanical lint | ❌ | No YAML frontmatter, filename is `.md` not `.plan.md`; several untagged code fences (field dump, git command, verified output) |

## Findings

Because the doc has no todo ids, findings key on section names instead of ids. **This report is
not consumable by `/plans update`** - fold the findings in by hand, or first convert the doc via
`/plans write` and re-key.

**not-a-plan** `[lint]` - The file has no Cursor frontmatter and no `todos:` block, and its name
lacks the `.plan.md` suffix. As written it documents the bug excellently but cannot be built,
verified, or archived by the plans lifecycle. The three "What to change" items and four edge
cases map naturally onto todos.
Action: convert to a proper `*.plan.md` (frontmatter + todos with stable ids), keeping the
current prose as the body; or accept it as a reference doc and plan the fix separately.

**fix-algorithm** `[risky]` - The hunk-walk table has an off-by-one for **pure-insertion hunks**
(`b == 0`). Git's `-a,0` means "inserted after old line a": old line `a` itself does not move,
but the test `a + b <= line` with `b = 0` and `line == a` evaluates true and wrongly adds the
insertion's delta. The repro never exercises this boundary (insertion at 70-71 vs comment at
199), so the "Verified output" section doesn't catch it. The above-test must be
`a + max(b, 1) <= line`; with that, `line == a` falls through to "otherwise: stop", which yields
the correct unshifted line. The deletion-side cases are correct as written.
Action: change the "hunk entirely above" test to `a + max(b, 1) <= line` and add a selftest case
for a comment sitting exactly on a pure-insertion hunk's anchor line.

**what-to-change-2** `[hygiene-issue]` - "`export` - use `head_line`" doesn't name the layer.
`github_export` (repos_api.py:297) replays whatever JSON the caller hands it; the selection of
unresolved threads into that comments file happens in the SKILL.md export workflow. A literal
implementer must decide whether the workflow maps `head_line` → the JSON's `line` key, or
`github_export` grows new logic. The cheapest change: the workflow builds the comments file with
`"line": head_line` and drops/flags outdated entries before `github_export` ever sees them, plus
a belt-and-braces refusal in `github_export` if an entry carries `outdated: true`.
Action: state which layer does the mapping and the refusal, so no decision is left to the
implementer.

**done-when** `[hygiene-issue]` - The skill-text correction in "Done when" names only the "TRUE
new-file line" claim (SKILL.md:146-149), but the same wrong claim lives in the `comment_line`
docstring (repos_api.py:271 "True new-file line for a read-side comment"), and the SKILL.md
`threads[]` JSON example (SKILL.md:138-144) plus the `status` and `export` verb prose must gain
`head_line`/`outdated` in the same commit - SKILL.md prose and behavior may not drift.
Action: extend the done-when to cover the docstring, the JSON example, and the status/export
verb prose.

**position-note** `[ready]` - The plan's `position` observation (199 = true file line) appears
to contradict the probed docstring (repos_api.py:273-277: "position 157/65 vs true lines
205/70"), but the plan resolves it correctly via provenance (API-written comments echo
`new_position` back) and lands on the right rule: prefer the hunk, trust `position` only when
arithmetic agrees. No change needed; consider copying the provenance note into the docstring
when touching it anyway.

**repro-dependency** `[ready]` - The done-when checks depend on live local Forgejo state
(`disney/android-dmgz` PR #1, head `b17c08bdcf6`). Fine for the first verification since /repos
runs against that instance, but the durable guard is the selftest: the plan should require
selftest cases for the remap (unchanged / remapped / outdated / pure-insertion boundary /
`commit_id == pr_head`), so correctness survives the repro PR being merged or the forge reset.
Action: add "selftest covers the remap cases" to the done-when list.

**gh-host-defect** `[ready]` - The "Not covered here" section correctly fences the `GH_HOST`
defect out (claim verified: repos_api.py:287 passes no `env=`). It is real and higher-severity as
stated; it deserves its own plan file, exactly as the doc says. No action within this plan.
