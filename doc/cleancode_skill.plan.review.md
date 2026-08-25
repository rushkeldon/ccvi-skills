---
plan: "cleancode_skill.plan.md"
model: "claude-fable-5"
---
# Review: cleancode skill — post-stabilization code consolidation

**Overall: near-ready** — a strong, well-railed plan (behavioral done-whens, out-of-scope fence, escape hatch, no open-questions limbo); the findings are scoped wording and repo-integration fixes, not structural rework.

| Dimension | Grade | Notes |
|---|---|---|
| Execution-readiness | ✅ | No unresolved decisions; convention-doc content is explicitly deferred to the collaborative todo 1 and fenced in Out of scope |
| Stale assumptions | ⚠️ | "Final home" conflates the ccvi-skills repo with the frozen `../skills-anthropic` quarry (finding below); staged convention docs verified present in doc/ |
| Cross-surface risk | ⚠️ | No todo covers the repo's manifest consumer contract (finding below); the CLAUDE.md-section writes are properly approval-gated |
| Rails present | ✅ | Stable anchors, per-step why + done-when, conventions explicit, escape hatch binding on every step |
| TODO hygiene | ✅ | 13 atomic todos, unique ids, ordered foundations → verbs → finish with phase keys |
| Mechanical lint | ✅ | `plan-check OK — 13 todos; statuses: pending; isProject=false`; overview/content quoted; version `"1.0"` quoted; lone code fence tagged `diagram` |

## Findings

**skill-scaffold** `[stale]` — the Conventions bullet "Final home" reads "the ccvi-skills repo (`../skills-anthropic`, installed at `~/.ccvi/ccvi-skills`)". The repo's CLAUDE.md (line 118) declares `../skills-anthropic` a frozen, read-only quarry — never write to it. The actual home is this repo's `plugin/skills/cleancode/`, beside the existing modes/plans/seedprompt skill dirs (verified present). A literal implementer following the parenthetical would create the skill inside the forbidden quarry.
Action: reword the Final-home bullet to name this repo (ccvi-skills, `plugin/skills/cleancode/`) and drop the `../skills-anthropic` parenthetical.

**skill-scaffold** `[risky]` — no todo covers the repo's consumer contract: `MANIFEST_SKILLS` in `build.py` (line 91) is the canonical source for manifest.json, and CLAUDE.md requires any SKILL.md verb or param change to update it in the same commit. Adding a whole new skill means adding its seven verbs with ordered param lists there, and `python3 build.py --check` must pass — the plan never mentions build.py, manifest.json, or the check. Grep confirms zero `cleancode` references in build.py today.
Action: add a repo-integration todo (or extend skill-scaffold's done-when): MANIFEST_SKILLS entry for all seven cleancode verbs with ordered params, and `python3 build.py --check` exits 0.

**survey-verb** `[hygiene-issue]` — the Approach's section-template paragraph closes with a machine-specific NOTE: "the GLOBAL section already exists — seeded by hand into Keldon's `~/.claude/CLAUDE.md` on 2026-08-26". This ties the spec to one machine's state (the user has flagged exactly this: the plan should be about writing the skill, not the local setup), and the date is in the future relative to today (2026-08-25). The general rule the skill actually needs — merge with any pre-existing section content, never re-seed over it — is already stated in the survey-verb step and covers the local situation without naming it.
Action: delete the NOTE sentence (the "NOTE: the GLOBAL section already exists…" through "…never re-seed over it" clause) from the Approach; the merge-with-pre-existing-content rule in the survey-verb step already carries the requirement.

**dogfood-run** `[hygiene-issue]` — the dogfood invokes `/cleancode`, but skills run from the installed copy at `~/.ccvi/ccvi-skills`, and the plan never says how the freshly authored skill gets there. Without an install/release step the dogfood run would exercise a stale or absent skill.
Action: state in the dogfood-run step that a release/install cycle (the repo's BBP ritual, then refreshing the installed plugin) precedes the dogfood so `/cleancode` resolves to the new skill.

## Clean todos

**naming-conventions-doc**, **comments-tool**, **verdict-resolution**, **harvest-verb**, **strip-verb**, **refactor-verb**, **rename-verb**, **annotate-verb**, **run-verb**, **docs-and-edges** — `[ready]`; anchors, why, and done-when present; no stale references found.

One no-action note: the plan cites "the modes-skill precedent" for bundling `tools/comments.py`, but modes bundles under `scripts/` — the `tools/` layout precedent is the plans skill. Harmless either way; worth a word tweak only if precision matters at implementation.
