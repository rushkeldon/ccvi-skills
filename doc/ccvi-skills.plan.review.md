---
plan: "ccvi-skills.plan.md"
model: "claude-opus-5[1m]"
---
# Review: ccvi-skills suite - bundle modes, plans, seedprompt as one plugin

**Overall: near-ready** - a well-railed plan whose facts check out against the source repo, with one real sequencing flaw: the `adapt-tests` step names three path constants but the harness carries three more non-path assumptions (version check, cross-surface parity, build.py invocation) that make its done-when unachievable as written; two smaller scope gaps (surface strings in `modes.py`, README row regex) round it out.

| Dimension | Grade | Notes |
|---|---|---|
| Execution-readiness | ⚠️ | Strong overall; `adapt-tests` forces the implementer to derive what "path-shaped" covers - three checks fail for non-path reasons |
| Stale assumptions | ✅ | Every verified fact re-verified: versions 4.6.0/3.2.0/1.1.0, hook registration, marketplace shape, fence states, anchors - all accurate |
| Cross-surface risk | ✅ | Source repo is fenced read-only; edits confined to this repo; LAW byte-lock is explicit and test-enforced |
| Rails present | ✅ | Every step has a done-when, out-of-scope fence is thorough, escape hatch present, anchors are stable (symbols/section names, no line numbers) |
| TODO hygiene | ✅ | 12 atomic todos, unique ids, correct order, phases coherent; each maps to a step |
| Mechanical lint | ✅ | `plan-check OK - 12 todos`; frontmatter quoted correctly; the version-number rule is honored (the `0.0.0` mentions are the decided scheme itself, not a hard-coded app version in a step) |

## Findings

**adapt-tests** `[risky]` - Step 5 says re-point "SCRIPT, SKILL_MD, HOOK" and "change nothing else unless a path-shaped assumption forces it", with done-when "exits 0 against the freshly ported, unedited files". Verified against the source harness: that cannot pass. Three checks fail for reasons beyond those three constants:
1. Check 8 (`help/version-header`) reads `version` from `modes/code/.claude-plugin/plugin.json` (test_modes.py:190) and asserts the help header matches it. Re-pointed to the suite's `plugin/.claude-plugin/plugin.json` (`0.0.0`), it fails at step 5 because the freshly ported help outputs still display `v4.6.0` (re-stamping is step 9). Left at the old path, the file doesn't exist in this repo.
2. Check 17 (`surface/skill-md`, `surface/script`) asserts byte-parity with `modes/cowork/...` and `modes/chat/...` copies (test_modes.py:252-257) - files that deliberately do not exist in the suite.
3. Check 19 (`build/in-sync`) runs `modes/build.py --check` as a subprocess (test_modes.py:275) - the suite's build.py doesn't exist until step 10, lives at repo root, and behaves differently.
The escape hatch would catch this at run time, but it is foreseeable now, and "stop and surface" on a known-in-advance mismatch wastes the round trip.
Action: rewrite step 5 to explicitly license: (a) delete check 17 (cross-surface parity is retired with the surfaces); (b) delete or defer check 19 (or re-point it at the root `build.py` and accept the harness only goes green after step 10 - pick one and say so); (c) re-point check 8's plugin.json path to `plugin/.claude-plugin/plugin.json` AND resolve the ordering - either fold the `4.6.0 → 0.0.0` help-output re-stamp of step 9 into step 5, or restate step 5's done-when as "exits 0 except the version check, which goes green at step 9". Update steps 5/9's done-whens to match the choice.

**strip-surface-branches** `[hygiene-issue]` - Scope/done-when mismatch. The step scopes the sweep to "all three `plugin/skills/*/SKILL.md` files", but its done-when is `grep -ri 'cowork' plugin/skills/` returning nothing - and the ported `modes.py` (which lives under `plugin/skills/modes/scripts/`) contains "Chat/Cowork" and "Chat/Desktop" in comments (source modes.py:127, :322). Verification item 3 greps all of `plugin/`, hitting it too. A literal implementer either fails the done-when or edits a file the step didn't authorize.
Action: extend the step's scope to include comment-level sweeps of `plugin/skills/modes/scripts/modes.py` (safe: the byte-lock covers only the LAW constants and echo contract, not comments - but say that explicitly), or narrow the grep to `plugin/skills/*/SKILL.md`. Extending the scope is the better fit for the plan's intent.

**suite-build-script** `[hygiene-issue]` - Step 10 point 3 says "Update the version shown in `README.md`", derived from the source build.py whose `update_readme` matches a `modes` table row via regex and hard-exits if the row is missing (source build.py:113-118). The suite README is authored fresh in step 11 - AFTER build.py is written and its done-when (`python3 build.py` runs clean) executes in step 10, when README.md does not yet exist. Same foreseeable-failure shape as the adapt-tests finding, in miniature.
Action: reorder README authoring before the build.py done-when run, or specify that build.py treats a missing README as a skip-with-notice in step 10 and step 11 closes the loop (its done-when already re-runs build.py). Either works; pick one and state it. Also specify the README version anchor format (e.g. a `· v0.0.0` idiom or a named table cell) so step 11's author and step 10's regex agree on what to match.

**version-displays** `[ready]` - note only, no action required beyond the adapt-tests resolution: verified the version string appears in exactly three places in the source modes payload (plugin.json, SKILL.md:542 help header, modes.py:97 HELP_TEXT), so the step's inventory is complete; the step's "update the golden data" instruction correctly anticipates the test coupling, but the coupling actually binds at step 5, not step 9 - resolved by the adapt-tests action.

Clean roll-up - **scaffold**, **port-modes**, **port-plans**, **port-seedprompt**, **harden-coupling**, **fence-sweep**, **author-docs**, **release-verify** `[ready]`: all verified against the source. Hook registration matches the plan's quote verbatim (matcher `Write|Edit|MultiEdit|NotebookEdit`, timeout 5, `${CLAUDE_PLUGIN_ROOT}` path). The plans SKILL.md's six bare fence lines are all closers (already tagged, as claimed); modes SKILL.md has genuine untagged openers plus the two LAW fences at lines 56/182 exactly as described; seedprompt has one bare opener (its help block) and the "host consumer (e.g. the CCVI sidecar), if present" anchor exists verbatim. The "Mode-bridge prologue" anchor and its quoted text exist in the plans SKILL.md. The `/plans write where a plans skill is available` hedge exists both inside the agent-loop LAW (line 199, untouchable - the plan correctly fences it) and in the non-LAW "Degradation, never refusal" paragraph (editable, as step 7 directs).
